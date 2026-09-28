"""Draft a cover letter for one job with the local Ollama model.

The header and sign-off are built here; the model writes only the body, from
materials/facts.yaml (the only allowed facts) and the closest of your recent
letters (for voice). Numbers the letter uses that aren't in the facts or the
posting are printed as warnings.
"""
import re
from datetime import date
from pathlib import Path

import docx
import requests
import yaml
from pypdf import PdfReader

from .jobs import Job, clean_ws

EMPLOYER_NOTE = {
    "usajobs": "a U.S. federal agency. Include one sentence that he is an NSF CyberCorps (SFS) scholar and this "
               "placement fits his federal service commitment.",
    "mitre": "MITRE, which operates federally funded research and development centers (FFRDCs). Include one sentence "
             "that he is an NSF CyberCorps (SFS) scholar and this placement fits his service commitment.",
    "jhuapl": "Johns Hopkins APL, a University Affiliated Research Center. You may say he is an NSF CyberCorps (SFS) "
              "scholar committed to public service, but do NOT claim this placement counts toward the commitment.",
    "inbox": "unknown; decide from the posting. Only if it is a government agency or national lab, include one "
             "sentence that he is an NSF CyberCorps (SFS) scholar and this placement fits his service commitment.",
}
LAB_NOTE = ("a DOE national laboratory. Include one sentence that he is an NSF CyberCorps (SFS) scholar and a "
            "national-lab placement counts toward his federal service commitment.")

SYSTEM = """You write cover letters for {name} in his own voice.

HIS VOICE (from his recent letters)
- Short, confident sentences. First person. Contractions are fine.
- Open with a strong hook: name the role and his genuine connection to it, or make a sharp claim about the problem
  the team works on. Never open with "I am excited to apply" or a resume summary.
- Show genuine interest in the mission: say something specific and true about why this work matters.
- Pick 2-3 facts from his background and tie each one to what THIS role needs. Do not list skills.
- Be humble and specific about what he'd learn: name the real gap for this role and how he'd close it.
- Close with availability and a short thank-you.
- Never use: "passionate", "perfect fit", "cutting-edge", "excellent fit", "strongly aligns", "leverage".

HARD RULES
- Use ONLY facts from the FACTS section. Never invent experience, skills, tools, numbers, dates, awards,
  certifications, courses, or people's names. If the posting asks for something he lacks, say so honestly.
- Respect every item under never_claim.
- Availability: school year up to 10 hours/week; summer full-time; willing to relocate. Say what fits this role.
- 330-430 words. 4-5 paragraphs. Plain text paragraphs separated by blank lines.
- Output ONLY the body: no header, no date, no "Dear ...", no sign-off, no name at the end.

FACTS
{facts}

A RECENT LETTER OF HIS (match this voice and structure; do not copy its content)
{example}"""

USER = """Write the body of the cover letter for this posting.

Title: {title}
Organization: {org}
Employer type: {employer}
Location: {location}

POSTING
{text}"""


def _letter_text(path: Path) -> str:
    text = "\n".join((p.extract_text() or "") for p in PdfReader(path).pages) if path.suffix == ".pdf" else \
        "\n".join(p.text for p in docx.Document(path).paragraphs)
    text = clean_ws(text)
    m = re.search(r"Dear[^\n]*\n(.*?)\n\s*Sincerely", text, re.S)   # body only
    return m.group(1).strip() if m else text


def pick_example(cfg, job: Job) -> tuple[str, str]:
    """The style example sharing the most topic keywords with the posting. Uses the config rank
    keywords: weight-4+ keywords decide; the generic weight-2 ones only break ties."""
    has = lambda text, kw: re.search(rf"(?<![A-Za-z]){re.escape(kw)}(?![A-Za-z])", text,
                                     0 if kw.isupper() else re.I) is not None
    job_text = job.title + " " + job.description
    topics = [(int(w), kw) for w, words in cfg["rank"]["keywords"].items() for kw in words if has(job_text, kw)]
    best = None
    for name in cfg["letters"]["style_examples"]:
        body = _letter_text(Path(cfg["cover_letters"]) / name)
        shared = [w for w, kw in topics if has(body, kw)]
        key = (sum(w for w in shared if w >= 4), len(shared))
        if best is None or key > best[0]:
            best = (key, name, body)
    return best[1], best[2]


def check(body: str, facts: str, posting: str) -> list[str]:
    """Flag numbers not found (as whole numbers) in the facts or the posting, and banned phrases."""
    nums = lambda t: {n.replace(",", "").rstrip(".") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", t)}
    known = nums(facts) | nums(posting)
    warnings = [f"number '{n}' isn't in facts.yaml or the posting" for n in sorted(nums(body) - known)]
    for phrase in ("passionate", "perfect fit", "cutting-edge", "excellent fit", "strongly aligns", "leverage"):
        if phrase in body.lower():
            warnings.append(f"uses '{phrase}'")
    return warnings


def write(cfg, job: Job) -> tuple[Path, list[str], str]:
    facts_text = Path(cfg["facts"]).read_text()
    facts = yaml.safe_load(facts_text)
    example_name, example = pick_example(cfg, job)
    employer = EMPLOYER_NOTE.get(job.source, LAB_NOTE)
    lc = cfg["letters"]
    r = requests.post(lc["ollama_url"].rstrip("/") + "/api/chat", timeout=900, json={
        "model": lc["model"], "stream": False, "think": False,
        "options": {"temperature": 0.6, "num_ctx": 16384},
        "messages": [
            {"role": "system", "content": SYSTEM.format(name=facts["person"]["name"], facts=facts_text, example=example)},
            {"role": "user", "content": USER.format(title=job.title, org=job.org, employer=employer,
                                                    location=job.location or "?", text=job.description[:12000])},
        ]})
    r.raise_for_status()
    body = r.json()["message"]["content"].strip()
    body = re.sub(r"^\s*Dear[^\n]*\n+", "", body)                       # in case the model adds them anyway
    body = re.sub(r"\n+\s*(Sincerely|Best regards|Regards),?.*$", "", body, flags=re.S).strip()

    p = facts["person"]
    header = [p["name"], f"{p['location']}  ·  {p['email']}  ·  {p['phone']}", date.today().strftime("%B %-d, %Y"),
              "", job.org, f"Re: {job.title}", "", "Dear Hiring Team,"]
    footer = ["Sincerely,", p["name"]]

    slug = lambda s: re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:40]
    out = Path(cfg["output"]) / f"{date.today().isoformat()}_{slug(job.org)}_{slug(job.title)}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "cover_letter.md").write_text("\n".join(header) + "\n\n" + body + "\n\n" + "\n".join(footer) + "\n")
    d = docx.Document()
    for line in header[:3]:
        d.add_paragraph(line)
    d.add_paragraph(job.org)
    d.add_paragraph(f"Re: {job.title}")
    d.add_paragraph("Dear Hiring Team,")
    for para in re.split(r"\n\s*\n", body):
        d.add_paragraph(" ".join(para.split()))
    d.add_paragraph("Sincerely,")
    d.add_paragraph(p["name"])
    d.save(out / "cover_letter.docx")
    (out / "posting.txt").write_text(f"{job.title}\n{job.org}\n{job.url}\n\n{job.description}")
    return out, check(body, facts_text, job.description), example_name
