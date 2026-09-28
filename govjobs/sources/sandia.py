"""Sandia National Laboratories: sandia.jobs sitemap (robots.txt allows all but /*feed/).
Posting text loads by JavaScript from a keyed API, so only title/location/link are available.
Paste the text of promising ones into inbox.md."""
import re

from ..jobs import Job
from ._helpers import sitemap_urls, slug_title

NAME = "Sandia"
HOME = "https://sandia.jobs"
ORG = "Sandia National Laboratories"


def fetch(ctx):
    jobs = []
    for url in sitemap_urls(ctx.http, "https://sandia.jobs/sitemaps/index.xml"):
        m = re.search(r"sandia\.jobs/([^/]+)/([^/]+)/([0-9A-F]{32})/job", url)
        if m and ctx.title_ok(slug_title(m.group(2))):
            city, _, state = m.group(1).rpartition("-")
            jobs.append(Job(source="sandia", source_id=m.group(3), title=slug_title(m.group(2)), org=ORG, url=url,
                            location=f"{city.replace('-', ' ').title()}, {state.upper()}"))
    if jobs:
        ctx.note(f"Sandia: {len(jobs)} titles only (text is JavaScript). Paste promising ones into inbox.md.", HOME)
    return jobs
