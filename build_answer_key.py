"""Solve every business under every rule set and save the answer key.
Also confirms that each solver schedule passes the rule checker.
Usage: python3 build_answer_key.py [first_n]
"""
import json
import sys
from multiprocessing import Pool

from checker import check
from solver import solve

RULESETS = ["federal", "california", "seattle"]


def job(args):
    b, rs = args
    r = solve(b, rs, 5.0)
    out = dict(business_id=b["business_id"], ruleset=rs, feasible=r["feasible"], status=r["status"],
               best_cost=r.get("cost"))
    if r["feasible"]:
        c = check(b, rs, r["schedule"])
        out["solver_schedule_legal"] = c["outcome"] == "legal"
        out["solver_schedule"] = r["schedule"]
    return out


if __name__ == "__main__":
    bs = json.load(open("scenarios/businesses.json"))
    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(bs)
    jobs = [(b, rs) for b in bs[:n] for rs in RULESETS]
    with Pool(2) as p:
        res = p.map(job, jobs, chunksize=4)
    json.dump(res, open("scenarios/answer_key.json", "w"))
    import collections
    c = collections.Counter((r["ruleset"], r["feasible"]) for r in res)
    print(dict(c))
    print("solver schedules failing the checker:", sum(1 for r in res if r["feasible"] and not r["solver_schedule_legal"]))
    print("timeouts without a solution:", sum(1 for r in res if r["feasible"] is None))
