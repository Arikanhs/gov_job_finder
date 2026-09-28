"""The Job record every source returns, plus small text/date helpers."""
import html as htmllib
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from bs4 import BeautifulSoup


@dataclass
class Job:
    source: str            # module name, e.g. "lanl", "usajobs", "inbox"
    source_id: str         # stable id within that source
    title: str
    org: str
    url: str
    location: str = ""
    deadline: str | None = None    # ISO date if the posting states one
    posted: str | None = None
    description: str = ""
    # filled in by rank.py
    points: int = 0
    matched: list = field(default_factory=list)
    flags: list = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.source}-{re.sub(r'[^A-Za-z0-9]', '', self.source_id)[:10]}".lower()


def html_to_text(s: str) -> str:
    if not s:
        return ""
    if "<" not in s:
        s = htmllib.unescape(s)      # some JSON-LD carries entity-escaped HTML
        if "<" not in s:
            return clean_ws(s)
    soup = BeautifulSoup(s, "html.parser")
    for t in soup(["script", "style", "noscript", "nav", "header", "footer", "form", "svg"]):
        t.decompose()
    for el in soup.find_all(["br", "p", "li", "div", "h1", "h2", "h3", "h4", "tr"]):
        el.append("\n")
    return clean_ws(soup.get_text(" "))


def clean_ws(s: str) -> str:
    s = re.sub(r"[ \t ]+", " ", s)
    s = re.sub(r" *\n[ \n]*", "\n", s)
    return s.strip()


_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%Y/%m/%d",
                 "%a %b %d %H:%M:%S UTC %Y"]


def parse_date(s) -> str | None:
    if not s:
        return None
    s = str(s).strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})[T ]", s)
    if m:
        return m.group(1)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def is_past(iso: str | None) -> bool:
    try:
        return bool(iso) and date.fromisoformat(iso) < date.today()
    except ValueError:
        return False


def title_filter(cfg: dict):
    """Keep internship-type titles; drop postdoc, new-grad, high-school, undergrad-only roles."""
    tf = cfg["title_filter"]
    inc, exc = re.compile(tf["include"], re.I), re.compile(tf["exclude"], re.I)
    grad = re.compile(r"(?<!under)graduate|\bgrad\b|master|m\.s\.|ph\.?d|doctoral", re.I)

    def ok(title: str) -> bool:
        if not inc.search(title) or exc.search(title):
            return False
        return not (re.search(r"undergrad", title, re.I) and not grad.search(title))
    return ok
