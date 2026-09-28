"""MITRE (operates FFRDCs): careers sitemap -> JSON-LD on each posting.
robots.txt allows /us/en/job/ (checked 2026-09-26). MITRE's terms page returned 403 and wasn't reviewed."""
import re

from ..jobs import Job
from ._helpers import job_from_jsonld, jsonld_jobposting, sitemap_urls, slug_title

NAME = "MITRE"
HOME = "https://careers.mitre.org/us/en"
ORG = "MITRE"


def fetch(ctx):
    jobs = []
    for url in sitemap_urls(ctx.http, "https://careers.mitre.org/us/en/sitemap.xml"):
        m = re.search(r"/job/(R\d+)/([^/?]+)", url)
        if not m or not ctx.title_ok(slug_title(m.group(2))):
            continue
        d = jsonld_jobposting(ctx.http.get(url))
        jobs.append(job_from_jsonld(d, source="mitre", source_id=m.group(1), url=url, org=ORG) if d else
                    Job(source="mitre", source_id=m.group(1), title=slug_title(m.group(2)), org=ORG, url=url))
    return jobs
