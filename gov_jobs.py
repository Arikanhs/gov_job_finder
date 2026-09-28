#!/usr/bin/env python3
"""Find government internships, rank them, and draft cover letters for the ones you pick.

Never submits applications or logs into any site.

  python gov_jobs.py scrape             # collect from every source, rank, write jobs.csv
  python gov_jobs.py scrape --only lanl # one source
  python gov_jobs.py list [--top 40]    # ranked list from the last scrape
  python gov_jobs.py show <id>          # full posting
  python gov_jobs.py letter <id> [...]  # draft cover letter(s) with the local model
"""
import argparse
import csv
import json
import sys
import textwrap
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv

from govjobs import rank
from govjobs.fetch import FetchError, Fetcher
from govjobs.jobs import Job, is_past, title_filter
from govjobs.sources import all_sources
from govjobs.sources._helpers import Ctx, ManualCheck

ROOT = Path(__file__).resolve().parent
SAVED = ROOT / "data" / "jobs.json"


def load_config():
    load_dotenv(ROOT / ".env")
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    for k in ("inbox", "facts", "cover_letters", "output", "cache_dir"):
        cfg[k] = str(ROOT / cfg[k])
    return cfg


def load_jobs() -> list[Job]:
    if not SAVED.exists():
        sys.exit("No jobs yet. Run: python gov_jobs.py scrape")
    return [Job(**d) for d in json.loads(SAVED.read_text())]


def cmd_scrape(cfg, args):
    ctx = Ctx(cfg=cfg, http=Fetcher(cfg), title_ok=title_filter(cfg))
    previous = {j.id for j in load_jobs()} if SAVED.exists() else set()
    kept = {j.id: j for j in load_jobs()} if (args.only and SAVED.exists()) else {}
    manual = []
    print("Scraping:")
    for src in all_sources():
        name = src.__name__.rsplit(".", 1)[-1]
        if name in cfg["disabled_sources"] or (args.only and args.only.lower() != name):
            continue
        t = time.time()
        try:
            found = src.fetch(ctx)
        except ManualCheck as e:
            manual.append((src.NAME, str(e), e.url or src.HOME))
            print(f"  {src.NAME:<14} check manually: {e}")
            continue
        except (FetchError, KeyError, ValueError, AttributeError, TypeError) as e:
            # A changed or broken site shouldn't stop the run.
            manual.append((src.NAME, f"failed ({type(e).__name__}: {e}); the site may have changed", src.HOME))
            print(f"  {src.NAME:<14} FAILED: {e}")
            continue
        kept = {k: v for k, v in kept.items() if v.source != name}
        open_jobs = [j for j in found if not is_past(j.deadline)]
        kept.update({j.id: j for j in open_jobs})
        print(f"  {src.NAME:<14} {len(open_jobs):>4} open  ({len(found) - len(open_jobs)} past deadline, {time.time() - t:.0f}s)")
    manual += [("note", m, u) for m, u in ctx.notes]

    jobs = rank.rank(list(kept.values()), cfg)
    new = {j.id for j in jobs} - previous if previous else set()
    for j in jobs:
        if j.id in new:
            j.flags.insert(0, "NEW")
    print(f"\n{len(jobs)} open postings; {len(new)} new since last scrape; "
          f"requests: {ctx.http.stats['network']} network, {ctx.http.stats['cached']} cached")
    if not args.dry_run:
        SAVED.parent.mkdir(exist_ok=True)
        SAVED.write_text(json.dumps([asdict(j) for j in jobs], indent=1))
        write_csv(jobs, ROOT / "jobs.csv")
        print("Saved jobs.csv")
    show_table(jobs[:25])
    soon = [j for j in jobs if j.deadline and j.points >= 6 and not any(f.startswith("*") for f in j.flags)
            and (date.fromisoformat(j.deadline) - date.today()).days <= 14]
    if soon:
        print("\nClosing within 14 days:")
        show_table(sorted(soon, key=lambda j: j.deadline))
    if manual:
        print("\nCheck manually:")
        for name, msg, url in manual:
            print(f"  - {name}: {msg}" + (f"\n      {url}" if url else ""))


def write_csv(jobs, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "id", "points", "deadline", "title", "organization", "location", "flags", "matched", "url"])
        for i, j in enumerate(jobs, 1):
            w.writerow([i, j.id, j.points, j.deadline or "", j.title, j.org, j.location,
                        ", ".join(j.flags), ", ".join(j.matched), j.url])


def show_table(jobs):
    print(f"\n{'#':>3} {'pts':>3}  {'deadline':<10}  {'id':<20} {'title':<55} {'org':<28} flags")
    for i, j in enumerate(jobs, 1):
        print(f"{i:>3} {j.points:>3}  {j.deadline or '':<10}  {j.id:<20} {j.title[:55]:<55} {j.org[:28]:<28} "
              f"{', '.join(j.flags)}")


def find(jobs, jid):
    hits = [j for j in jobs if j.id == jid] or [j for j in jobs if j.id.startswith(jid)]
    if len(hits) != 1:
        sys.exit(f"'{jid}' matches {len(hits)} jobs; use an id from `list`.")
    return hits[0]


def cmd_list(cfg, args):
    jobs = load_jobs()
    show_table(jobs[:args.top])
    print(f"\n{min(args.top, len(jobs))} of {len(jobs)} shown. Full list: jobs.csv")


def cmd_show(cfg, args):
    j = find(load_jobs(), args.id)
    print(f"{j.title}\n{j.org} | {j.location}\n{j.url}\nposted {j.posted or '?'}  deadline {j.deadline or '?'}  "
          f"points {j.points}  matched: {', '.join(j.matched)}  flags: {', '.join(j.flags)}\n")
    print(textwrap.indent(j.description or "(no text)", "  "))


def cmd_letter(cfg, args):
    from govjobs import letter
    jobs = load_jobs()
    for jid in args.ids:
        job = find(jobs, jid)
        if not job.description:
            print(f"{job.id}: no posting text; paste it into inbox.md and scrape first.")
            continue
        print(f"Drafting: {job.title} ({job.org}) with {cfg['letters']['model']}...")
        t = time.time()
        try:
            out, warnings, example = letter.write(cfg, job)
        except OSError as e:
            sys.exit(f"Couldn't reach Ollama at {cfg['letters']['ollama_url']} ({e}). Start the Ollama app and retry.")
        print(f"  saved {out.relative_to(ROOT)}/cover_letter.md and .docx ({time.time() - t:.0f}s; voice example: {example})")
        for w in warnings:
            print(f"  CHECK: {w}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("scrape", "run"):
        p = sub.add_parser(name, help="collect and rank" if name == "scrape" else "same as scrape")
        p.add_argument("--only", help="one source by file name, e.g. lanl, usajobs, inbox")
        p.add_argument("--dry-run", action="store_true", help="print results but don't save")
    sub.add_parser("list").add_argument("--top", type=int, default=40)
    sub.add_parser("show").add_argument("id")
    sub.add_parser("letter").add_argument("ids", nargs="+")
    args = ap.parse_args()
    {"scrape": cmd_scrape, "run": cmd_scrape, "list": cmd_list, "show": cmd_show,
     "letter": cmd_letter}[args.cmd](load_config(), args)


if __name__ == "__main__":
    main()
