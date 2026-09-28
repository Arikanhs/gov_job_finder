"""Manual inbox: blocks in inbox.md separated by '---' lines. A block can be a link (fetched
politely), pasted posting text, or both. Optional first lines: Title:, Org:, Deadline:, Location:."""
import hashlib
import re
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from ..fetch import FetchError
from ..jobs import Job, html_to_text, parse_date
from ._helpers import job_from_jsonld, jsonld_jobposting

NAME = "Inbox"
HOME = ""
META = re.compile(r"^(title|org|deadline|location)\s*:\s*(.+)$", re.I)
LINK = re.compile(r"https?://[^\s<>)\]]+")
CLOSE = re.compile(r"(?:clos(?:ed|ing|es)\s*(?:date|on)?|deadline|apply by)\s*:?\s*(?:</?[^>]+>\s*|\|\s*)*"
                   r"(\d{1,2}/\d{1,2}/20\d\d|20\d\d-\d\d-\d\d|[A-Z][a-z]+ \d{1,2}, 20\d\d)", re.I)


def fetch(ctx):
    path = Path(ctx.cfg["inbox"])
    if not path.exists():
        return []
    jobs = []
    for i, block in enumerate(re.split(r"(?m)^\s*---\s*$", path.read_text())[1:], 1):
        meta, body = {}, []
        for line in block.strip().splitlines():
            m = META.match(line.strip())
            if m and not body:
                meta[m.group(1).lower()] = m.group(2).strip()
            else:
                body.append(line)
        body = "\n".join(body).strip()
        links, pasted = LINK.findall(body), LINK.sub("", body).strip()
        if not links and not pasted:
            continue
        job = Job(source="inbox", source_id=hashlib.sha1((links[0] if links else pasted).encode()).hexdigest()[:10],
                  title=meta.get("title", ""), org=meta.get("org", ""), url=links[0] if links else "",
                  location=meta.get("location", ""), deadline=parse_date(meta.get("deadline")), description=pasted)
        if links and len(pasted) < 300:
            try:
                got = _fetch_page(ctx.http, links[0])
                job.description = max(got.description, pasted, key=len)
                job.title, job.org = job.title or got.title, job.org or got.org
                job.location, job.deadline = job.location or got.location, job.deadline or got.deadline
            except FetchError as e:
                if not pasted:
                    ctx.note(f"inbox block {i}: couldn't fetch link ({e}); paste the posting text under it", links[0])
        job.title = job.title or (pasted.splitlines()[0][:120] if pasted else links[0])
        job.org = job.org or (_org_from_url(job.url) if job.url else "unknown")
        jobs.append(job)
    return jobs


def _org_from_url(url):
    p = urlsplit(url)
    if p.netloc.endswith("smartrecruiters.com"):
        return p.path.strip("/").split("/")[0]
    return p.netloc.removeprefix("www.")


def _fetch_page(http, url) -> Job:
    html = http.get(url)
    soup = BeautifulSoup(html, "html.parser")
    og = soup.find("meta", property="og:title")
    main = soup.find("main") or soup.find("article") or soup.body or soup
    job = Job(source="inbox", source_id="", url=url, org="", description=html_to_text(str(main)),
              title=og["content"] if og and og.get("content") else (soup.title.get_text(strip=True) if soup.title else ""))
    d = jsonld_jobposting(html)
    if d:
        org = d.get("hiringOrganization") or {}
        ld = job_from_jsonld(d, source="inbox", source_id="", url=url,
                             org=org.get("name", "") if isinstance(org, dict) else str(org))
        ld.description = max(ld.description, job.description, key=len)
        job = ld
    if not job.deadline and (m := CLOSE.search(html)):
        job.deadline = parse_date(m.group(1))
    if len(job.description) < 200:
        raise FetchError("page has almost no readable text (JavaScript-rendered or login-only)")
    return job
