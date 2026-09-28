"""Johns Hopkins APL (a DoD UARC): the careers site's own search API (Jibe).
robots.txt: Allow /, crawl-delay 5 (honored)."""
from ._helpers import jibe

NAME = "JHU APL"
HOME = "https://careers.jhuapl.edu/internships"


def fetch(ctx):
    return jibe(ctx, base="https://careers.jhuapl.edu", source="jhuapl",
                org="Johns Hopkins University Applied Physics Laboratory")
