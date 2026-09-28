"""Argonne National Laboratory: public Workday sites (robots.txt allows /Argonne_Careers/ and /EDU_PUB/).
www.anl.gov itself is behind a Cloudflare challenge."""
from ._helpers import workday

NAME = "Argonne"
HOME = "https://argonne.wd1.myworkdayjobs.com/EDU_PUB"
ORG = "Argonne National Laboratory"
HOST = "argonne.wd1.myworkdayjobs.com"


def fetch(ctx):
    return (workday(ctx, host=HOST, tenant="argonne", site="EDU_PUB", source="argonne", org=ORG,
                    searches=("",), student_site=True)
            + workday(ctx, host=HOST, tenant="argonne", site="Argonne_Careers", source="argonne", org=ORG))
