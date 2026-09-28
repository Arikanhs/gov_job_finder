"""Oak Ridge National Laboratory: jobs.ornl.gov search pages + schema.org microdata.
robots.txt disallows /services/ (no RSS) but allows /search/ and /job/. Most ORNL student
programs are on its education pages, so those are listed for a manual check."""
import re

from bs4 import BeautifulSoup

from ..jobs import Job, html_to_text, parse_date

NAME = "ORNL"
HOME = "https://www.ornl.gov/content/graduate-student-opportunities"
ORG = "Oak Ridge National Laboratory"


def fetch(ctx):
    seen, jobs = set(), []
    for q in ("intern", "student", "graduate"):
        for start in range(0, 200, 25):
            html = ctx.http.get("https://jobs.ornl.gov/search/", kind="listing",
                                params={"q": q, "startrow": start, "sortColumn": "referencedate", "sortDirection": "desc"})
            links = re.findall(r'<a[^>]*href="(/job/[^"]+/(\d+)/)"[^>]*class="jobTitle-link"[^>]*>([^<]+)<', html)
            links += re.findall(r'<a[^>]*class="jobTitle-link"[^>]*href="(/job/[^"]+/(\d+)/)"[^>]*>([^<]+)<', html)
            for path, jid, title in links:
                if jid not in seen and ctx.title_ok(title):
                    seen.add(jid)
                    jobs.append(_detail(ctx, "https://jobs.ornl.gov" + path, jid, title.strip()))
            if len({l[1] for l in links}) < 25:
                break
    ctx.note("ORNL: student internships are mostly on ORNL's education program pages.", HOME)
    return jobs


def _detail(ctx, url, jid, title):
    s = BeautifulSoup(ctx.http.get(url), "html.parser")

    def prop(name):
        e = s.select_one(f'[itemprop="{name}"]')
        return (e.get("content") or e.get_text(" ", strip=True)) if e else ""

    desc = s.select_one('[itemprop="description"]')
    return Job(source="ornl", source_id=jid, title=title, org=ORG, url=url, posted=parse_date(prop("datePosted")),
               location=", ".join(x for x in (prop("addressLocality"), prop("addressRegion")) if x),
               description=html_to_text(str(desc)) if desc else "")
