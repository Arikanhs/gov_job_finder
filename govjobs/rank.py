"""Rank jobs by keyword matches (config.yaml `rank.keywords`) and flag obvious problems.

Points: each keyword that appears counts its weight once; triple if it's in the title.
Flags marked * mean you're likely ineligible; those jobs sort to the bottom.
"""
import re

# Checks that come from reading real postings.
CHECKS = [
    ("*undergrad years only", "text", re.compile(
        r"must be (a |an )?(currently enrolled )?[^.;]{0,40}\b(freshman|freshmen|sophomores?|juniors?|rising juniors?)\b"
        r"(?![^.;]{0,60}\bgraduate student)", re.I)),
    ("*needs completed grad degree", "title", re.compile(r"post[- ]?(master|graduate|doctora|doc\b)", re.I)),
    # "must be" matters: many postings say "a master's OR enrolled in a PhD program".
    ("*PhD only", "text", re.compile(r"must be (currently )?(enrolled|matriculated)(/matriculated)? in an? (accredited )?"
                                     r"Ph\.?D\.? program", re.I)),
    ("*PhD only", "title", re.compile(r"\bPhD (intern|student)", re.I)),
    # Bare "unpaid" isn't enough: USAJOBS boilerplate mentions unpaid experience in paid postings.
    ("unpaid", "text", re.compile(r"\b(our|an|this|the|is|are) unpaid\b|unpaid (internship|position|role)|\bnon-?paid\b"
                                  r"|student volunteer|volunteer (internship|position|project)|semester of service", re.I)),
]


def _pattern(kw):
    # Short all-caps keywords (AI, HPC, LLM) match case-sensitively as whole words.
    if kw.isupper() or "/" in kw:
        return re.compile(rf"(?<![A-Za-z]){re.escape(kw)}(?![A-Za-z])")
    return re.compile(rf"\b{re.escape(kw)}\b", re.I)


def rank(jobs, cfg):
    kws = [(int(w), kw, _pattern(kw)) for w, words in cfg["rank"]["keywords"].items() for kw in words]
    for job in jobs:
        job.points, job.matched, job.flags = 0, [], []
        for weight, kw, pat in kws:
            if pat.search(job.title):
                job.points += 3 * weight
                job.matched.append(kw)
            elif pat.search(job.description):
                job.points += weight
                job.matched.append(kw)
        for flag, where, pat in CHECKS:
            if flag not in job.flags and pat.search(job.title if where == "title" else job.description):
                job.flags.append(flag)
        if not job.description:
            job.flags.append("no text")
    jobs.sort(key=lambda j: (any(f.startswith("*") for f in j.flags), -j.points, j.deadline or "9999"))
    return jobs
