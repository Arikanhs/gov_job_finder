"""National Laboratory of the Rockies (formerly NREL): Workday job-site JSON (robots.txt allows /NLR/)."""
from ._helpers import workday

NAME = "NLR (NREL)"
HOME = "https://nrel.wd5.myworkdayjobs.com/NLR"


def fetch(ctx):
    return workday(ctx, host="nrel.wd5.myworkdayjobs.com", tenant="nrel", site="NLR", source="nlr",
                   org="National Laboratory of the Rockies (formerly NREL)")
