# gov_jobs

Finds government and national-lab internships, ranks them by keyword match, and
drafts a cover letter with a local model for the ones you choose.
**It never applies for you, never logs into any site, and never solves CAPTCHAs.**

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env     # add USAJOBS_API_KEY and USAJOBS_EMAIL (from developer.usajobs.gov)
```

For cover letters, install [Ollama](https://ollama.com), open the app, and run
`ollama pull gemma4:12b`. The model is set in `config.yaml` under `letters.model`.

## Use

```bash
.venv/bin/python gov_jobs.py scrape           # collect everything, rank, write jobs.csv
.venv/bin/python gov_jobs.py list --top 40    # ranked list from the last scrape
.venv/bin/python gov_jobs.py show jhuapl-60084
.venv/bin/python gov_jobs.py letter jhuapl-60084 nlr-r14416   # draft letters
```

- `scrape --only lanl` runs a single source; `--dry-run` prints without saving.
- Letters go to `output/<date>_<org>_<title>/` as `cover_letter.md` and
  `cover_letter.docx`, with the posting text saved next to them.
- Any number in a letter that isn't in `materials/facts.yaml` or the posting is
  printed as `CHECK:`, so you can verify it.

## Ranking

Each keyword in `config.yaml` under `rank.keywords` adds its weight once, and
triple if it appears in the title. Edit the list to change what rises to the top.

Flags:
- `*undergrad years only`, `*PhD only`, `*needs completed grad degree`: you're
  probably not eligible. These jobs sort to the bottom.
- `unpaid`: the posting describes the role as unpaid or volunteer.
- `no text`: title only; Sandia's postings are JavaScript.
- `NEW`: appeared since the last scrape.

`scrape` also prints a **closing within 14 days** list.

## Sources

Each site is one file in `govjobs/sources/`. To skip one, list it in
`config.yaml` under `disabled_sources`.

| Source | How it reads the site |
|---|---|
| usajobs | USAJOBS API, student hiring path. Queries in config.yaml. |
| lanl, mitre | sitemap, then JSON-LD on each posting |
| sandia | sitemap (titles only) |
| llnl | LLNL's job list page, then SmartRecruiters posting pages |
| ornl | job-board search pages |
| pnnl, jhuapl | the careers site's own search API |
| nlr, argonne | Workday job-site JSON |
| lbnl, inl | **check manually**: they block scripts (403 / Cloudflare) |
| inbox | links or text you paste into `inbox.md`, separated by `---` lines |

**Adding a site:** create `govjobs/sources/<name>.py` with `NAME`, `HOME`, and
`fetch(ctx)`, which returns a list of `Job`. It's picked up automatically.
Copy the closest existing file:
- `lanl.py` if the site has a sitemap with JSON-LD pages;
- `pnnl.py` if it runs on Jibe;
- `nlr.py` if it runs on Workday.

`_helpers.py` has the shared pieces. If a site can't be read reliably, raise
`ManualCheck`; the run continues and the site is listed under "check manually".

## Politeness

All requests go through `govjobs/fetch.py`, which:
- checks robots.txt before every fetch;
- waits at least 3 s between requests to the same site, longer if its crawl-delay asks;
- caches responses in `data/cache/`: 6 h for listings, 7 days for postings.

robots.txt was checked for every source on 2026-09-26. The linked terms pages
had no restriction on automated access, except MITRE, whose terms page returned
403 and wasn't reviewed.
