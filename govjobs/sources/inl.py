"""Idaho National Laboratory: inl.gov serves a Cloudflare bot challenge to scripts."""
from ._helpers import ManualCheck

NAME = "INL"
HOME = "https://inl.gov/internships/"


def fetch(ctx):
    raise ManualCheck("site is behind a Cloudflare bot challenge", HOME)
