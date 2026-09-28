"""Los Alamos National Laboratory: lanl.jobs sitemap -> JSON-LD on each posting.
robots.txt allows all (checked 2026-09-26)."""
import re

from ..jobs import Job
from ._helpers import job_from_jsonld, jsonld_jobposting, sitemap_urls, slug_title

NAME = "LANL"
HOME = "https://lanl.jobs/search/searchjobs"
ORG = "Los Alamos National Laboratory"


def fetch(ctx):
    jobs = []
    for url in sitemap_urls(ctx.http, "https://lanl.jobs/jobs-site.xml"):
        m = re.search(r"/jobdetails/([^/]+)/([0-9a-f-]{36})", url)
        if not m or not ctx.title_ok(slug_title(m.group(1))):
            continue
        d = jsonld_jobposting(ctx.http.get(url))
        jobs.append(job_from_jsonld(d, source="lanl", source_id=m.group(2), url=url, org=ORG) if d else
                    Job(source="lanl", source_id=m.group(2), title=slug_title(m.group(1)), org=ORG, url=url))
    return jobs
