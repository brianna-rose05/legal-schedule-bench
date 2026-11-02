"""Solver condition: the model may write and run Python (with Google OR-Tools installed) before answering.

Same prompt and answer format as the text-only condition, plus a run_python tool.
Up to 10 tool calls; each run has a 60-second limit and output is cut to 8,000 characters.

Usage:
  python3 solver_run.py --models openai/gpt-6-luna --instances main_300 --out results/solver
"""
import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import tempfile
import time

import requests

from prompt import SYSTEM, build_prompt
from run import URL, instances, load_key

MAX_STEPS = 10
TOOL_NOTE = ("\n\nTOOLS\nYou can call run_python to run Python 3 code (Google OR-Tools is installed as `ortools`; "
             "no internet). Use it as much as helps, up to 10 times, then give your final answer in the format above.")
TOOLS = [{"type": "function", "function": {
    "name": "run_python",
    "description": "Run a Python 3 script and return its stdout and stderr. OR-Tools is installed. 60-second limit.",
    "parameters": {"type": "object", "properties": {"code": {"type": "string", "description": "Python source"}},
                   "required": ["code"]}}}]


def run_python(code):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "main.py")
        open(path, "w").write(code)
        try:
            p = subprocess.run([sys.executable, "-I", path], cwd=d, capture_output=True, text=True, timeout=60,
                               env={"PATH": "/usr/bin:/bin", "HOME": d})
            out = (p.stdout + ("\nSTDERR:\n" + p.stderr if p.stderr else ""))
        except subprocess.TimeoutExpired:
            out = "ERROR: timed out after 60 seconds"
    return out[:8000] if len(out) <= 8000 else out[:8000] + "\n[output cut at 8000 characters]"


def post(key, body):
    last = None
    for attempt in range(4):
        try:
            r = requests.post(URL, headers={"Authorization": "Bearer " + key}, json=body, timeout=600)
            if r.status_code == 200:
                j = r.json()
                if j.get("choices"):
                    return j, None
                last = str(j)[:300]
            else:
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code in (400, 401, 402, 403):
                    break
        except Exception as e:
            last = repr(e)[:300]
        time.sleep(5 * (attempt + 1))
    return None, last


def episode(key, model, prompt, max_tokens=64000):
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt + TOOL_NOTE}]
    cost, steps, t0, usage_tot = 0.0, 0, time.time(), {"prompt_tokens": 0, "completion_tokens": 0}
    finish = None
    while True:
        body = dict(model=model, temperature=0, max_tokens=max_tokens, messages=msgs, usage={"include": True})
        if steps < MAX_STEPS:
            body["tools"] = TOOLS
        j, err = post(key, body)
        if j is None:
            return dict(ok=False, error=err, steps=steps, usage=dict(cost=cost, **usage_tot))
        u = j.get("usage", {})
        cost += float(u.get("cost") or 0)
        for k in usage_tot:
            usage_tot[k] += int(u.get(k) or 0)
        ch = j["choices"][0]
        msg, finish = ch["message"], ch.get("finish_reason")
        calls = msg.get("tool_calls") or []
        if not calls or steps >= MAX_STEPS:
            return dict(ok=True, text=msg.get("content") or "", steps=steps, finish=finish,
                        seconds=round(time.time() - t0, 1), usage=dict(cost=cost, **usage_tot))
        msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for c in calls:
            steps += 1
            try:
                code = json.loads(c["function"]["arguments"]).get("code", "")
            except Exception:
                code = ""
            out = run_python(code) if code else "ERROR: no code given"
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": out})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--instances", default="main_300")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    key = load_key()
    bs = {b["business_id"]: b for b in json.load(open("scenarios/businesses.json"))}
    os.makedirs(a.out, exist_ok=True)
    inst = instances(a.instances)[:a.limit]
    jobs = []
    for model in a.models.split(","):
        fn = os.path.join(a.out, model.replace("/", "__") + ".jsonl")
        done = set()
        if os.path.exists(fn):
            done = {(r["business_id"], r["ruleset"], r["format"]) for r in map(json.loads, open(fn)) if r.get("ok")}
        jobs += [(model, fn, i) for i in inst if i not in done]
    print(f"{len(jobs)} episodes to run")

    def work(job):
        model, fn, (bid, rs, fmt) = job
        res = episode(key, model, build_prompt(bs[bid], rs, fmt))
        res.update(model=model, business_id=bid, ruleset=rs, format=fmt, condition="solver")
        return fn, res

    spent, n = 0.0, 0
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for fn, res in ex.map(work, jobs):
            with open(fn, "a") as f:
                f.write(json.dumps(res) + "\n")
            n += 1
            spent += float(res["usage"].get("cost") or 0)
            if n % 25 == 0 or n == len(jobs):
                print(f"{n}/{len(jobs)} done, ${spent:.2f} spent", flush=True)


if __name__ == "__main__":
    main()
