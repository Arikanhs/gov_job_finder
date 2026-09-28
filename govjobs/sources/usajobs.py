"""USAJOBS Search API (developer.usajobs.gov). Needs USAJOBS_API_KEY and USAJOBS_EMAIL in .env.
Queries are in config.yaml under `usajobs`."""
import os

from ..jobs import Job, html_to_text, parse_date
from ._helpers import ManualCheck

NAME = "USAJOBS"
HOME = "https://www.usajobs.gov/"
URL = "https://data.usajobs.gov/api/Search"


def fetch(ctx):
    key, email = os.getenv("USAJOBS_API_KEY", "").strip(), os.getenv("USAJOBS_EMAIL", "").strip()
    if not key or not email:
        raise ManualCheck("USAJOBS_API_KEY / USAJOBS_EMAIL not set in .env", "https://developer.usajobs.gov/apirequest/")
    headers = {"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": key}
    uc, jobs = ctx.cfg["usajobs"], {}
    for q in uc["queries"]:
        params = {**uc.get("defaults", {}), **q, "ResultsPerPage": 250}
        # Keyed official API, not crawling, so robots.txt doesn't apply.
        data = ctx.http.get_json(URL, params=params, headers=headers, kind="listing", robots=False)
        for it in data.get("SearchResult", {}).get("SearchResultItems", []):
            job = _to_job(it)
            jobs.setdefault(job.source_id, job)
    return list(jobs.values())


def _to_job(item) -> Job:
    d = item["MatchedObjectDescriptor"]
    det = (d.get("UserArea") or {}).get("Details") or {}
    duties = det.get("MajorDuties") or []
    sections = [
        ("Summary", det.get("JobSummary")),
        ("Major duties", "\n".join(f"- {x}" for x in duties) if isinstance(duties, list) else duties),
        ("Qualifications", d.get("QualificationSummary")),
        ("Education", det.get("Education")),
        ("Requirements", det.get("Requirements")),
        ("Key requirements", "\n".join(f"- {x}" for x in det.get("KeyRequirements") or [])),
        ("Security clearance", det.get("SecurityClearance")),
        ("Grade", f"GS-{det.get('LowGrade', '')} to GS-{det.get('HighGrade', '')}" if det.get("LowGrade") else ""),
    ]
    org = d.get("OrganizationName", "")
    if d.get("DepartmentName") and d["DepartmentName"] not in org:
        org = f"{org} ({d['DepartmentName']})"
    return Job(source="usajobs", source_id=str(item.get("MatchedObjectId") or d.get("PositionID")),
               title=d.get("PositionTitle", ""), org=org, url=d.get("PositionURI", ""),
               location=d.get("PositionLocationDisplay", ""),
               deadline=parse_date(d.get("ApplicationCloseDate")), posted=parse_date(d.get("PublicationStartDate")),
               description="\n\n".join(f"{h}:\n{html_to_text(str(v))}" for h, v in sections if v))
