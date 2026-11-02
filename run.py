"""Runs models on scenario instances through OpenRouter and saves every reply, its usage and its cost.

Usage:
  python3 run.py --models anthropic/claude-haiku-5.5,... --instances pilot --out results/pilot
"""
import argparse
import concurrent.futures as cf
import json
import os
import random
import time

import requests

from prompt import SYSTEM, build_prompt

KEY_FILE = "/home/claude/bench/.env"
URL = "https://openrouter.ai/api/v1/chat/completions"


def load_key():
    for line in open(KEY_FILE):
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("no OpenRouter key")


def instances(kind):
    """Scenario instances: (business_id, ruleset, format)."""
    bs = json.load(open("scenarios/businesses.json"))
    all_inst = [(b["business_id"], rs, fmt) for b in bs for rs in ("federal", "california", "seattle")
                for fmt in ("table", "messages")]
    if kind == "all":
        return all_inst
    rng = random.Random(7)
    if kind == "pilot":
        # 24 instances: 8 businesses (levels 1-5, at least 2 with planted traps) x 3 rule sets, alternating format
        by_lvl = {}
        for b in bs[500:]:   # pilot businesses come from the end of the list
            by_lvl.setdefault(b["level"], []).append(b)
        pick = [by_lvl[l][0] for l in range(1, 6)] + [by_lvl[3][1], by_lvl[5][1], by_lvl[4][1]]
        if not any(b["planted_trap"] for b in pick):
            pick[-1] = next(b for b in bs[500:] if b["planted_trap"])
        out = []
        for i, b in enumerate(pick):
            for j, rs in enumerate(("federal", "california", "seattle")):
                out.append((b["business_id"], rs, ("table", "messages")[(i + j) % 2]))
        return out
    # main run: every business except the 8 pilot businesses
    pilot_ids = {b for b, _, _ in instances("pilot")}
    main = [b for b in bs if b["business_id"] not in pilot_ids]
    if kind == "main":
        return [i for i in all_inst if i[0] not in pilot_ids]
    if kind.startswith("main_"):
        # nested subsets: n businesses per level, taken from one fixed shuffle per level,
        # so every smaller subset is inside every larger one. Each business runs under
        # all 3 rule sets x 2 formats (6 instances), keeping the within-business pairs.
        n_inst = int(kind.split("_")[1])
        per_level = n_inst // 30
        pick = set()
        for lvl in range(1, 6):
            ids = sorted(b["business_id"] for b in main if b["level"] == lvl)
            random.Random(100 + lvl).shuffle(ids)
            pick.update(ids[:per_level])
        return [i for i in all_inst if i[0] in pick]
    raise SystemExit(f"unknown instance set {kind}")


def call(key, model, prompt, max_tokens=64000):
    body = dict(model=model, temperature=0, max_tokens=max_tokens,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                usage={"include": True})
    last = None
    for attempt in range(4):
        try:
            t = time.time()
            r = requests.post(URL, headers={"Authorization": "Bearer " + key}, json=body, timeout=600)
            dt = time.time() - t
            if r.status_code == 200:
                j = r.json()
                if "choices" in j and j["choices"]:
                    msg = j["choices"][0]["message"]
                    return dict(ok=True, text=msg.get("content") or "", seconds=round(dt, 1),
                                usage=j.get("usage", {}), provider=j.get("provider"),
                                finish=j["choices"][0].get("finish_reason"))
                last = str(j)[:300]
            else:
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code in (400, 401, 402, 403):
                    break
        except Exception as e:  # network errors are retried
            last = repr(e)[:300]
        time.sleep(5 * (attempt + 1))
    return dict(ok=False, error=last)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--instances", default="pilot")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-spend", type=float, default=None, help="stop a model once its spend passes this (US$)")
    a = ap.parse_args()
    key = load_key()
    bs = {b["business_id"]: b for b in json.load(open("scenarios/businesses.json"))}
    os.makedirs(a.out, exist_ok=True)
    inst = instances(a.instances)
    jobs = []
    for model in a.models.split(","):
        fn = os.path.join(a.out, model.replace("/", "__") + ".jsonl")
        done = set()
        if os.path.exists(fn):
            for line in open(fn):
                r = json.loads(line)
                if r.get("ok"):
                    done.add((r["business_id"], r["ruleset"], r["format"]))
        for i in inst:
            if i not in done:
                jobs.append((model, fn, i))
    print(f"{len(jobs)} calls to make")

    def work(job):
        model, fn, (bid, rs, fmt) = job
        p = build_prompt(bs[bid], rs, fmt)
        res = call(key, model, p)
        res.update(model=model, business_id=bid, ruleset=rs, format=fmt)
        return fn, res

    spent, n = 0.0, 0
    per_model = {}
    stopped = set()

    def guarded(job):
        if job[0] in stopped:
            return None
        return work(job)

    with cf.ThreadPoolExecutor(a.workers) as ex:
        for out in ex.map(guarded, jobs):
            if out is None:
                continue
            fn, res = out
            c = float(res.get("usage", {}).get("cost") or 0)
            per_model[res["model"]] = per_model.get(res["model"], 0) + c
            if a.max_spend and per_model[res["model"]] > a.max_spend and res["model"] not in stopped:
                stopped.add(res["model"])
                print(f"STOP {res['model']}: spend ${per_model[res['model']]:.2f} passed ${a.max_spend}", flush=True)
            with open(fn, "a") as f:
                f.write(json.dumps(res) + "\n")
            n += 1
            spent += c
            if n % 25 == 0 or n == len(jobs):
                print(f"{n}/{len(jobs)} done, ${spent:.2f} spent", flush=True)


if __name__ == "__main__":
    main()
