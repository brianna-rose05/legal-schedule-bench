"""Grades every model reply against the answer key.

Usage: python3 grade.py results/pilot   ->  results/pilot/graded.csv
"""
import csv
import glob
import json
import os
import sys

from checker import check
from prompt import parse_reply


def main(folder):
    bs = {b["business_id"]: b for b in json.load(open("scenarios/businesses.json"))}
    key = {(k["business_id"], k["ruleset"]): k for k in json.load(open("scenarios/answer_key.json"))}
    rows = []
    for fn in sorted(glob.glob(os.path.join(folder, "*.jsonl"))):
        for line in open(fn):
            r = json.loads(line)
            if not r.get("ok"):
                continue
            b = bs[r["business_id"]]
            k = key.get((r["business_id"], r["ruleset"]))
            if k is None:
                continue
            p = parse_reply(r["text"])
            u = r.get("usage", {})
            row = dict(model=r["model"], business_id=r["business_id"], level=b["level"], type=b["type"],
                       ruleset=r["ruleset"], format=r["format"], feasible=k["feasible"],
                       reply=p["kind"], cost_usd=u.get("cost"), prompt_tokens=u.get("prompt_tokens"),
                       completion_tokens=u.get("completion_tokens"),
                       reasoning_tokens=(u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                       seconds=r.get("seconds"), finish=r.get("finish"))
            if p["kind"] == "unusable":
                row.update(outcome="unusable")
            elif p["kind"] == "impossible":
                row.update(outcome="correct_impossible" if k["feasible"] is False else "false_impossible")
            else:
                c = check(b, r["ruleset"], p["schedule"])
                kinds = sorted({v["type"] for v in c["violations"]})
                row.update(outcome=c["outcome"], violations=";".join(kinds), n_violations=len(c["violations"]),
                           premium_usd=c["premium_dollars"], labor_cost=c["labor_cost"],
                           best_cost=k.get("best_cost"),
                           over_best=(round(c["labor_cost"] - k["best_cost"], 2)
                                      if k.get("best_cost") is not None and c["outcome"] == "legal" else None))
            rows.append(row)
    cols = ["model", "business_id", "level", "type", "ruleset", "format", "feasible", "reply", "outcome", "violations",
            "n_violations", "premium_usd", "labor_cost", "best_cost", "over_best", "cost_usd", "prompt_tokens",
            "completion_tokens", "reasoning_tokens", "seconds", "finish"]
    out = os.path.join(folder, "graded.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) for c in cols})
    print(f"{len(rows)} graded -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
