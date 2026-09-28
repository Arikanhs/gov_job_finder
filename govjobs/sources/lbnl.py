"""Lawrence Berkeley National Laboratory: jobs.lbl.gov returns 403 to scripts and has no feed."""
from ._helpers import ManualCheck

NAME = "Berkeley Lab"
HOME = "https://jobs.lbl.gov/"


def fetch(ctx):
    raise ManualCheck("job pages block automated requests (HTTP 403)", HOME)
