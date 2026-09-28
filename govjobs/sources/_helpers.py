"""Shared helpers for source modules.

A source module is one file in this folder that defines:
    NAME = "Display name"
    HOME = "https://... page to check by hand"
    def fetch(ctx) -> list[Job]
It raises ManualCheck when the site can't be read reliably. New files are picked
up automatically; turn one off in config.yaml under `sources`.
"""
import json
import re
from dataclasses import dataclass, field

from ..fetch import Fetcher
from ..jobs import Job, html_to_text, parse_date


class ManualCheck(Exception):
    def __init__(self, reason, url=""):
        super().__init__(reason)
        self.url = url


@dataclass
class Ctx:
    cfg: dict
    http: Fetcher
    title_ok: callable
    notes: list = field(default_factory=list)   # (message, url) shown under "check manually"

    def note(self, msg, url=""):
        self.notes.append((msg, url))


def sitemap_urls(http: Fetcher, url: str) -> list[str]:
    """All <loc> URLs in a sitemap, following a sitemap index one level."""
    xml = http.get(url, kind="listing")
    locs = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml)
    if "<sitemapindex" in xml:
        return [u for sub in locs for u in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", http.get(sub, kind="listing"))]
    return locs


def slug_title(slug: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[-_]+", " ", slug)).strip().title()


def jsonld_jobposting(html: str) -> dict | None:
    # Some sites (e.g. USAJOBS) HTML-escape the "+" in the type attribute.
    for block in re.findall(r"<script[^>]*application/ld(?:\+|&#x2B;|&#43;)json[^>]*>(.*?)</script>", html, re.S | re.I):
        try:
            data = json.loads(block.strip(), strict=False)
        except json.JSONDecodeError:
            continue
        for d in (data if isinstance(data, list) else data.get("@graph", [data])):
            if isinstance(d, dict) and d.get("@type") == "JobPosting":
                return d
    return None


def job_from_jsonld(d: dict, *, source, source_id, url, org) -> Job:
    locs = d.get("jobLocation") or []
    locs = [locs] if isinstance(locs, dict) else locs
    where = []
    for l in locs:
        a = (l or {}).get("address") or {}
        where.append(", ".join(x for x in [a.get("addressLocality"), a.get("addressRegion")] if x))
    return Job(source=source, source_id=source_id, url=url, org=org,
               title=html_to_text(d.get("title", "")), location="; ".join(x for x in where if x),
               posted=parse_date(d.get("datePosted")), deadline=parse_date(d.get("validThrough")),
               description=html_to_text(d.get("description", "")))


def workday(ctx: Ctx, *, host, tenant, site, source, org, searches=("intern", "student", "graduate"), student_site=False):
    """Workday job sites: the page's own JSON endpoints.
    student_site=True: every posting is a student role, so only the title exclusions apply."""
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    seen, jobs = set(), []
    for q in searches:
        offset = 0
        while True:
            data = ctx.http.post_json(f"{base}/jobs", {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": q})
            posts = data.get("jobPostings", [])
            for p in posts:
                path, title = p.get("externalPath"), p.get("title", "")
                if not path or path in seen or not ctx.title_ok(title + (" intern" if student_site else "")):
                    continue
                seen.add(path)
                info = ctx.http.get_json(base + path, headers={"Accept": "application/json"}).get("jobPostingInfo", {})
                jobs.append(Job(source=source, source_id=(p.get("bulletFields") or [path])[0], title=title, org=org,
                                url=f"https://{host}/{site}{path}", location=info.get("location") or p.get("locationsText", ""),
                                posted=parse_date(info.get("startDate")), deadline=parse_date(info.get("endDate")),
                                description=html_to_text(info.get("jobDescription", ""))))
            offset += 20
            if offset >= data.get("total", 0) or not posts:
                break
    return jobs


def jibe(ctx: Ctx, *, base, source, org, searches=("intern", "student", "graduate")):
    """Jibe career sites (PNNL, JHU APL): the site's own /api/jobs search."""
    seen, jobs = set(), []
    for q in searches:
        page = 1
        while True:
            data = ctx.http.get_json(f"{base}/api/jobs", params={"keywords": q, "page": page, "limit": 100}, kind="listing")
            for item in data.get("jobs", []):
                d = item.get("data", {})
                rid = str(d.get("req_id") or d.get("slug"))
                if rid in seen or not ctx.title_ok(d.get("title", "")):
                    continue
                seen.add(rid)
                parts = [d.get("description"), d.get("responsibilities"), d.get("qualifications")]
                jobs.append(Job(source=source, source_id=rid, title=d.get("title", ""), org=org,
                                url=f"{base}/jobs/{d.get('slug', rid)}",
                                location=d.get("full_location") or d.get("location_name") or "",
                                posted=parse_date(d.get("posted_date")),
                                description=html_to_text("\n\n".join(p for p in parts if p))))
            if page * 100 >= (data.get("totalCount") or 0):
                break
            page += 1
    return jobs
