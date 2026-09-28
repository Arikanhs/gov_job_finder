"""Pacific Northwest National Laboratory: the careers site's own search API (Jibe).
robots.txt: Allow /, crawl-delay 5 (honored)."""
from ._helpers import jibe

NAME = "PNNL"
HOME = "https://careers.pnnl.gov/"


def fetch(ctx):
    return jibe(ctx, base="https://careers.pnnl.gov", source="pnnl", org="Pacific Northwest National Laboratory")
