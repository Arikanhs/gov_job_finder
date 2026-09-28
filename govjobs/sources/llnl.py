"""Lawrence Livermore National Laboratory: LLNL's own job list page (all openings), then each
posting's public SmartRecruiters page. The SmartRecruiters API isn't used: its robots.txt disallows it."""
import re

from bs4 import BeautifulSoup

from ..jobs import Job, html_to_text, parse_date

NAME = "LLNL"
HOME = "https://www.llnl.gov/join-our-team/careers/find-your-job"
ORG = "Lawrence Livermore National Laboratory"


def fetch(ctx):
    jobs = []
    for row in BeautifulSoup(ctx.http.get(HOME, kind="listing"), "html.parser").select("div.job-post"):
        a = row.select_one('a[href*="jobs.smartrecruiters.com/LLNL/"]')
        if not a:
            continue
        cells = [c for c in row.get_text("|", strip=True).split("|") if c.strip()]
        title = row.select_one(".article-api-title").get_text("|", strip=True).split("|")[0]
        is_intern = "Intern" in cells or "Internship" in cells
        if not ctx.title_ok(title + (" intern" if is_intern else "")):
            continue
        url = a["href"].split("?")[0]
        page = BeautifulSoup(ctx.http.get(url), "html.parser")
        body, details = page.select_one(".job-sections"), page.select_one(".job-details")
        jobs.append(Job(source="llnl", source_id=re.search(r"/LLNL/(\d+)", url).group(1), title=title, org=ORG, url=url,
                        location=next((c for c in cells if re.search(r", [A-Z]{2}$", c)), ""),
                        posted=next((parse_date(c) for c in cells if re.fullmatch(r"\d{2}/\d{2}/\d{4}", c)), None),
                        description=((details.get_text(" ", strip=True) + "\n\n") if details else "")
                        + (html_to_text(str(body)) if body else "")))
    return jobs
