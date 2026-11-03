"""Runs the pre-specified analysis (PREREGISTRATION.md, section 4) plus the listed exploratory checks.

Reads results/main/graded.csv and results/solver/graded.csv (run grade.py first).
Writes CSV tables and a plain-text report to results/analysis/.
The mixed-effects model is fitted in R (lme4::glmer); Rscript must be installed.

Usage: python3 analysis.py
"""
import json
import os
import re
import subprocess

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint

from checker import BUSINESS, LAW, PREMIUM, check
from prompt import parse_reply

OUT = "results/analysis"
SEED = 2026
BOOT = 2000
LABOR = LAW | PREMIUM  # H3: a labor-rule violation or premium pay

NAMES = {
    "anthropic/claude-opus-5.5": "Claude Opus 5.5",
    "anthropic/claude-sonnet-5.5": "Claude Sonnet 5.5",
    "anthropic/claude-haiku-5.5": "Claude Haiku 5.5",
    "deepseek/deepseek-v4.1-flash": "DeepSeek V4.1 Flash",
    "openai/gpt-6.1-sol": "GPT-6.1 Sol",
    "openai/gpt-6-luna": "GPT-6 Luna",
    "openai/gpt-oss-120b": "gpt-oss-120b",
    "meta-llama/llama-4-maverick": "Llama 4 Maverick",
    "google/gemini-3.5-flash-lite": "Gemini 3.5 Flash Lite",
}
KEY = ["business_id", "ruleset", "format"]
report = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    report.append(s)


def wilson(k, n):
    if n == 0:
        return np.nan, np.nan
    lo, hi = proportion_confint(k, n, method="wilson")
    return lo, hi


def pct(k, n):
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]" if n else "n/a"


def holm(p):
    return multipletests(p, method="holm")[1]


def mcnemar(a, b):
    """Exact McNemar on paired booleans. Returns (a_only, b_only, two-sided p)."""
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    n10, n01 = int((a & ~b).sum()), int((~a & b).sum())
    p = stats.binomtest(n10, n10 + n01, 0.5).pvalue if n10 + n01 else 1.0
    return n10, n01, p


def boot_mean_by_business(df, col, rng, reps=BOOT):
    """Mean of col with a bootstrap interval that resamples whole businesses."""
    g = df.groupby("business_id")[col].agg(["sum", "count"])
    s, c = g["sum"].to_numpy(), g["count"].to_numpy()
    idx = rng.integers(0, len(g), size=(reps, len(g)))
    means = s[idx].sum(1) / c[idx].sum(1)
    return s.sum() / c.sum(), np.percentile(means, 2.5), np.percentile(means, 97.5)


def load(fn):
    d = pd.read_csv(fn)
    d["feasible"] = d["feasible"].astype(str) == "True"
    d["vset"] = d["violations"].fillna("").apply(lambda x: set(filter(None, x.split(";"))))
    d["legal"] = d["outcome"] == "legal"
    d["violation"] = d["outcome"].isin(["breaks_law", "breaks_business_rule", "premium_pay"])
    d["law"] = d["outcome"] == "breaks_law"
    d["labor"] = d["vset"].apply(lambda s: bool(s & LABOR))
    d["success"] = np.where(d["feasible"], d["legal"], d["outcome"] == "correct_impossible")
    d["name"] = d["model"].map(NAMES)
    return d


def lenient_regrade(folder):
    """Sensitivity check: also accept employee names instead of IDs and SHIFT,EMPLOYEE order."""
    bs = {b["business_id"]: b for b in json.load(open("scenarios/businesses.json"))}
    rows = []
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith(".jsonl"):
            continue
        for line in open(os.path.join(folder, fn)):
            r = json.loads(line)
            if not r.get("ok"):
                continue
            b = bs[r["business_id"]]
            names = {}
            for e in b["staff"]:
                names.setdefault(e["name"].lower(), []).append(e["id"])
            text = r.get("text") or ""
            fixed = []
            for ln in text.splitlines():
                parts = [p.strip() for p in ln.strip().strip("`").split(",")]
                if len(parts) >= 3 and re.fullmatch(r"S\d+", parts[0]) and re.fullmatch(r"E\d+", parts[1]):
                    parts[0], parts[1] = parts[1], parts[0]
                elif len(parts) >= 3 and re.fullmatch(r"S\d+", parts[1]) and len(names.get(parts[0].lower(), [])) == 1:
                    parts[0] = names[parts[0].lower()][0]
                fixed.append(",".join(parts) if len(parts) >= 3 else ln)
            p = parse_reply("\n".join(fixed))
            rows.append(dict(model=r["model"], business_id=r["business_id"], ruleset=r["ruleset"],
                             format=r["format"], reply=p["kind"],
                             outcome=p["kind"] if p["kind"] != "schedule" else
                             check(b, r["ruleset"], p["schedule"])["outcome"]))
    return pd.DataFrame(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)
    m, s = load("results/main/graded.csv"), load("results/solver/graded.csv")
    order = (m[m.feasible].groupby("model")["legal"].mean().sort_values(ascending=False).index.tolist())

    # ---------- Table 1: outcomes per model ----------
    say("== Table 1. Outcomes per model (text-only condition) ==")
    t1 = []
    for mo in order:
        g = m[m.model == mo]
        p, i = g[g.feasible], g[~g.feasible]
        sched = p[p.reply == "schedule"]
        prem, plo, phi = boot_mean_by_business(sched.assign(x=sched.premium_usd.fillna(0)), "x", rng)
        leg = p[p.legal]
        ob, olo, ohi = (boot_mean_by_business(leg.assign(x=leg.over_best), "x", rng) if len(leg) else (np.nan,) * 3)
        row = dict(model=NAMES[mo], instances=len(g), businesses=g.business_id.nunique(), possible=len(p),
                   impossible=len(i))
        for o in ["legal", "breaks_law", "breaks_business_rule", "premium_pay", "false_impossible", "unusable"]:
            k = int((p.outcome == o).sum())
            lo, hi = wilson(k, len(p))
            row.update({f"{o}_n": k, f"{o}_pct": 100 * k / len(p), f"{o}_lo": 100 * lo, f"{o}_hi": 100 * hi})
        k = int(p.violation.sum())
        lo, hi = wilson(k, len(p))
        row.update(violation_n=k, violation_pct=100 * k / len(p), violation_lo=100 * lo, violation_hi=100 * hi)
        for o in ["correct_impossible"]:
            k = int((i.outcome == o).sum())
            lo, hi = wilson(k, len(i))
            row.update({f"{o}_n": k, f"{o}_pct": 100 * k / len(i), f"{o}_lo": 100 * lo, f"{o}_hi": 100 * hi})
        row.update(impossible_gave_schedule_n=int((i.reply == "schedule").sum()),
                   premium_per_schedule=prem, premium_lo=plo, premium_hi=phi,
                   over_best_mean=ob, over_best_lo=olo, over_best_hi=ohi,
                   over_best_zero_pct=100 * (leg.over_best <= 0.005).mean() if len(leg) else np.nan,
                   cost_total=g.cost_usd.sum(), cost_per_instance=g.cost_usd.mean(),
                   cost_per_legal=(p.cost_usd.sum() / max(1, p.legal.sum())),
                   median_completion_tokens=g.completion_tokens.median(), median_seconds=g.seconds.median())
        t1.append(row)
        say(f"{NAMES[mo]:24s} n={len(g):5d}  legal {pct(int(p.legal.sum()), len(p)):22s} "
            f"law {pct(int(p.law.sum()), len(p)):22s} any-violation {pct(int(p.violation.sum()), len(p)):22s} "
            f"caught-impossible {pct(int((i.outcome == 'correct_impossible').sum()), len(i))}  "
            f"premium/schedule ${prem:.0f} [{plo:.0f}, {phi:.0f}]  cost ${g.cost_usd.sum():.2f}")
    pd.DataFrame(t1).to_csv(f"{OUT}/table1_outcomes_by_model.csv", index=False)

    # ---------- H1 ----------
    say("\n== H1. Breaks a law in >= 20% of schedules (possible scenarios); one-sided exact binomial, Holm ==")
    rows = []
    for mo in order:
        p = m[(m.model == mo) & m.feasible]
        k, n = int(p.law.sum()), len(p)
        rows.append(dict(model=NAMES[mo], k=k, n=n, pct=100 * k / n,
                         p=stats.binomtest(k, n, 0.20, alternative="greater").pvalue))
    h1 = pd.DataFrame(rows)
    h1["p_holm"] = holm(h1.p)
    h1.to_csv(f"{OUT}/h1_law_breaks.csv", index=False)
    for r in h1.itertuples():
        say(f"{r.model:24s} {r.k}/{r.n} = {r.pct:.1f}%  p_holm={r.p_holm:.3g}")
    say("H1 supported:", bool((h1.p_holm < 0.05).any()), "| models significantly above 20%:",
        ", ".join(h1[h1.p_holm < 0.05].model))

    # ---------- H2 ----------
    say("\n== H2. Violation rises with level: Kendall tau-b between level and each business's violation share ==")
    say("(one-sided, businesses as the unit, Holm across models)")
    rows = []
    for mo in order:
        p = m[(m.model == mo) & m.feasible]
        b = p.groupby(["business_id", "level"]).violation.mean().reset_index()
        tau, p2 = stats.kendalltau(b.level, b.violation)
        p1 = p2 / 2 if tau > 0 else 1 - p2 / 2
        by = p.groupby("level").violation.mean().mul(100).round(1).to_dict()
        rows.append(dict(model=NAMES[mo], tau=tau, p=p1, **{f"L{k}": v for k, v in by.items()}))
    h2 = pd.DataFrame(rows)
    h2["p_holm"] = holm(h2.p)
    h2.to_csv(f"{OUT}/h2_level_trend.csv", index=False)
    for r in h2.itertuples():
        say(f"{r.model:24s} L1-L5 violation % {r.L1:5.1f} {r.L2:5.1f} {r.L3:5.1f} {r.L4:5.1f} {r.L5:5.1f}  "
            f"tau={r.tau:.2f} p_holm={r.p_holm:.3g}")
    nsig = int((h2.p_holm < 0.05).sum())
    say(f"H2 supported: {nsig > len(h2) / 2} ({nsig} of {len(h2)} models show a significant rising trend)")
    fail_lvl = (m[m.feasible].assign(fail=~m[m.feasible].legal)
                .pivot_table(index="name", columns="level", values="fail", aggfunc="mean").mul(100)
                .loc[[NAMES[x] for x in order]])
    fail_lvl.to_csv(f"{OUT}/fail_by_level.csv")

    # ---------- RQ2: pooled mixed-effects logistic regression (lme4) ----------
    say("\n== RQ2. Mixed-effects logistic regression (lme4::glmer), possible scenarios ==")
    say("any_violation ~ model + level + ruleset + format + (1 | business); reference: Claude Opus 5.5, federal, table")
    dd = m[m.feasible][["name", "business_id", "level", "ruleset", "format", "violation"]].copy()
    dd["violation"] = dd.violation.astype(int)
    dd.to_csv(f"{OUT}/_glmer_input.csv", index=False)
    r_code = f"""
suppressMessages(library(lme4))
d <- read.csv("{OUT}/_glmer_input.csv")
d$name <- relevel(factor(d$name), ref = "Claude Opus 5.5")
d$ruleset <- relevel(factor(d$ruleset), ref = "federal")
d$format <- relevel(factor(d$format), ref = "table")
f <- glmer(violation ~ name + level + ruleset + format + (1 | business_id), data = d, family = binomial,
           control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5)), nAGQ = 1)
co <- summary(f)$coefficients
out <- data.frame(term = rownames(co), estimate = co[, 1], se = co[, 2], z = co[, 3], p = co[, 4])
out$or <- exp(out$estimate); out$or_lo <- exp(out$estimate - 1.96 * out$se); out$or_hi <- exp(out$estimate + 1.96 * out$se)
write.csv(out, "{OUT}/rq2_glmer.csv", row.names = FALSE)
cat("business random-intercept SD:", attr(VarCorr(f)$business_id, "stddev"), "\\n")
cat("converged warnings:", length(f@optinfo$conv$lme4$messages), "\\n")
"""
    res = subprocess.run(["Rscript", "-e", r_code], capture_output=True, text=True)
    say(res.stdout.strip())
    if res.returncode != 0:
        say("glmer failed:", res.stderr[-800:])
    else:
        g = pd.read_csv(f"{OUT}/rq2_glmer.csv")
        for _, r in g.iterrows():
            say(f"{r['term']:32s} OR={r['or']:.3g} [{r['or_lo']:.3g}, {r['or_hi']:.3g}] p={r['p']:.3g}")
    os.remove(f"{OUT}/_glmer_input.csv")

    # ---------- H3 ----------
    say("\n== H3. Labor-rule violation or premium pay: California / Seattle vs federal, same business and format ==")
    say("(exact McNemar on pairs where a legal schedule exists under both rule sets; Holm across models)")
    rows = []
    for mo in order:
        g = m[(m.model == mo) & m.feasible].set_index(KEY)
        fed = g.xs("federal", level="ruleset")
        for other in ["california", "seattle"]:
            o = g.xs(other, level="ruleset")
            j = fed.join(o, how="inner", lsuffix="_fed", rsuffix="_x")
            a, b = j.labor_x.to_numpy(), j.labor_fed.to_numpy()
            n10, n01, p = mcnemar(a, b)
            rows.append(dict(model=NAMES[mo], vs=other, pairs=len(j), other_pct=100 * a.mean(),
                             federal_pct=100 * b.mean(), other_only=n10, federal_only=n01, p=p))
    h3 = pd.DataFrame(rows)
    h3["p_holm"] = np.nan
    for c in ["california", "seattle"]:
        h3.loc[h3.vs == c, "p_holm"] = holm(h3[h3.vs == c].p)
    h3.to_csv(f"{OUT}/h3_rulesets.csv", index=False)
    for r in h3.itertuples():
        say(f"{r.model:24s} {r.vs:10s} {r.other_pct:5.1f}% vs federal {r.federal_pct:5.1f}%  "
            f"({r.other_only} vs {r.federal_only} discordant) p_holm={r.p_holm:.3g}")
    both = [mo for mo in h3.model.unique()
            if all((h3[(h3.model == mo) & (h3.vs == c)].p_holm.iloc[0] < 0.05) and
                   (h3[(h3.model == mo) & (h3.vs == c)].other_pct.iloc[0] >
                    h3[(h3.model == mo) & (h3.vs == c)].federal_pct.iloc[0]) for c in ["california", "seattle"])]
    say(f"Models significantly higher under both California and Seattle: {len(both)} of {h3.model.nunique()}:",
        ", ".join(both))

    # ---------- H4 / RQ4 ----------
    say("\n== H4 / RQ4. Impossible scenarios: schedule vs 'impossible' (exact binomial, Holm) ==")
    rows = []
    for mo in order:
        i = m[(m.model == mo) & ~m.feasible]
        ns, ni = int((i.reply == "schedule").sum()), int((i.outcome == "correct_impossible").sum())
        p = stats.binomtest(ns, ns + ni, 0.5, alternative="greater").pvalue if ns + ni else 1.0
        fp = m[(m.model == mo) & m.feasible]
        rows.append(dict(model=NAMES[mo], n=len(i), gave_schedule=ns, said_impossible=ni,
                         unusable=len(i) - ns - ni, said_impossible_pct=100 * ni / len(i),
                         lo=100 * wilson(ni, len(i))[0], hi=100 * wilson(ni, len(i))[1], p=p,
                         false_impossible_pct=100 * (fp.outcome == "false_impossible").mean()))
    h4 = pd.DataFrame(rows)
    h4["p_holm"] = holm(h4.p)
    h4.to_csv(f"{OUT}/h4_impossible.csv", index=False)
    for r in h4.itertuples():
        say(f"{r.model:24s} said impossible {r.said_impossible}/{r.n} = {r.said_impossible_pct:.1f}% "
            f"[{r.lo:.1f}, {r.hi:.1f}], gave schedule {r.gave_schedule}, unusable {r.unusable}; "
            f"false 'impossible' on possible: {r.false_impossible_pct:.1f}%  p_holm(schedule>impossible)={r.p_holm:.3g}")
    k = int(((h4.gave_schedule > h4.said_impossible) & (h4.p_holm < 0.05)).sum())
    say(f"H4 supported: {k > len(h4) / 2} ({k} of {len(h4)} models gave a schedule significantly more often)")

    # ---------- H5 / RQ5 ----------
    say("\n== H5 / RQ5. Solver vs text-only on the same instances ==")
    rows = []
    for mo in s.model.unique():
        a = s[s.model == mo].set_index(KEY)
        b = m[m.model == mo].set_index(KEY).loc[a.index]
        pos = a.feasible.to_numpy()
        n10, n01, p = mcnemar(b.violation.to_numpy()[pos], a.violation.to_numpy()[pos])
        # ratio of violation shares with a business-level bootstrap
        bb = pd.DataFrame(dict(business_id=a.index.get_level_values(0)[pos],
                               t=b.violation.to_numpy()[pos], s=a.violation.to_numpy()[pos]))
        gb = bb.groupby("business_id")[["t", "s"]].sum()
        idx = rng.integers(0, len(gb), size=(BOOT, len(gb)))
        ts, ss = gb.t.to_numpy()[idx].sum(1), gb.s.to_numpy()[idx].sum(1)
        ratio = ss / np.where(ts == 0, np.nan, ts)
        sn10, sn01, sp = mcnemar(b.success.to_numpy(), a.success.to_numpy())
        imp = a[~a.feasible]
        rows.append(dict(model=NAMES[mo], instances=len(a), possible=int(pos.sum()),
                         text_violation_pct=100 * b.violation.to_numpy()[pos].mean(),
                         solver_violation_pct=100 * a.violation.to_numpy()[pos].mean(),
                         ratio=bb.s.sum() / bb.t.sum(), ratio_lo=np.nanpercentile(ratio, 2.5),
                         ratio_hi=np.nanpercentile(ratio, 97.5), text_only_violations=n10,
                         solver_only_violations=n01, p=p,
                         text_legal_pct=100 * b.legal.to_numpy()[pos].mean(),
                         solver_legal_pct=100 * a.legal.to_numpy()[pos].mean(),
                         text_success_pct=100 * b.success.mean(), solver_success_pct=100 * a.success.mean(),
                         fixed=sn01, broke=sn10, success_p=sp,
                         solver_impossible_caught=int((imp.outcome == "correct_impossible").sum()),
                         solver_impossible_unusable=int((imp.outcome == "unusable").sum()),
                         solver_possible_unusable=int((a[a.feasible].outcome == "unusable").sum()),
                         solver_cost=a.cost_usd.sum(), text_cost=b.cost_usd.sum()))
    h5 = pd.DataFrame(rows)
    h5["p_holm"] = holm(h5.p)
    # tool runs per episode, from the raw solver files
    steps = {}
    for fn in os.listdir("results/solver"):
        if fn.endswith(".jsonl"):
            st = [json.loads(x).get("steps", 0) for x in open(os.path.join("results/solver", fn))]
            steps[NAMES[fn.replace("__", "/")[:-6]]] = (np.mean(st), int(np.sum(np.array(st) >= 10)))
    h5["solver_mean_runs"] = h5.model.map(lambda x: steps[x][0])
    h5["solver_hit_run_limit"] = h5.model.map(lambda x: steps[x][1])
    h5.to_csv(f"{OUT}/h5_solver.csv", index=False)
    for r in h5.itertuples():
        say(f"{r.model:24s} violation on possible: text {r.text_violation_pct:.1f}% -> solver {r.solver_violation_pct:.1f}% "
            f"(ratio {r.ratio:.2f} [{r.ratio_lo:.2f}, {r.ratio_hi:.2f}]) McNemar p_holm={r.p_holm:.3g}")
        say(f"{'':24s} legal on possible: {r.text_legal_pct:.1f}% -> {r.solver_legal_pct:.1f}%; overall right answer "
            f"{r.text_success_pct:.1f}% -> {r.solver_success_pct:.1f}% (fixed {r.fixed}, broke {r.broke}, p={r.success_p:.3g})")
        say(f"{'':24s} impossible caught {r.solver_impossible_caught}, impossible unusable {r.solver_impossible_unusable}, "
            f"possible unusable {r.solver_possible_unusable}; mean runs {r.solver_mean_runs:.1f}, "
            f"hit limit {r.solver_hit_run_limit}; cost text ${r.text_cost:.2f} vs solver ${r.solver_cost:.2f}")
    ok = (h5.ratio <= 0.5) & (h5.p_holm < 0.05)
    say(f"H5 supported for: {', '.join(h5[ok].model)} ({int(ok.sum())} of {len(h5)})")

    # ---------- Exploratory ----------
    say("\n== Exploratory. Format: staff messages vs clean table (same business and rule set, exact McNemar, Holm) ==")
    rows = []
    for mo in order:
        g = m[(m.model == mo) & m.feasible].set_index(["business_id", "ruleset", "format"])
        t = g.xs("table", level="format")
        j = t.join(g.xs("messages", level="format"), how="inner", lsuffix="_t", rsuffix="_m")
        n10, n01, p = mcnemar(~j.legal_m, ~j.legal_t)
        rows.append(dict(model=NAMES[mo], pairs=len(j), messages_fail_pct=100 * (~j.legal_m).mean(),
                         table_fail_pct=100 * (~j.legal_t).mean(), p=p))
    fm = pd.DataFrame(rows)
    fm["p_holm"] = holm(fm.p)
    fm.to_csv(f"{OUT}/x_format.csv", index=False)
    for r in fm.itertuples():
        say(f"{r.model:24s} messages {r.messages_fail_pct:5.1f}% vs table {r.table_fail_pct:5.1f}% fail  p_holm={r.p_holm:.3g}")

    say("\n== Exploratory. Share of returned schedules (possible scenarios) with each violation type ==")
    sch = m[m.feasible & (m.reply == "schedule")]
    types = sorted(set().union(*sch.vset))
    vt = pd.DataFrame({t: sch.groupby("name").vset.apply(lambda x: 100 * x.apply(lambda s: t in s).mean())
                       for t in types}).loc[[NAMES[x] for x in order]]
    vt.insert(0, "schedules", sch.groupby("name").size())
    vt.round(1).to_csv(f"{OUT}/x_violation_types.csv")
    say(vt.round(1).to_string())

    say("\n== Exploratory. Rules in focus, as a share of returned schedules (possible scenarios) ==")
    minor = {"minor_daily", "minor_school_hours", "minor_time", "minor_weekly"}
    rows = []
    for mo in order:
        g = sch[sch.model == mo]
        teen = g[g.level >= 3]
        ca = g[g.ruleset == "california"]
        leg = m[(m.model == mo) & m.legal]
        pct_over = 100 * leg.over_best / leg.best_cost
        p = m[(m.model == mo) & m.feasible]
        l5 = p[p.level == 5]
        rows.append(dict(model=NAMES[mo],
                         teen_rule_broken_levels3to5=100 * teen.vset.apply(lambda s: bool(s & minor)).mean(),
                         meal_missed_california=100 * ca.vset.apply(lambda s: "meal_missed" in s).mean(),
                         outside_availability=100 * g.vset.apply(lambda s: "unavailable" in s).mean(),
                         over_own_max_hours=100 * g.vset.apply(lambda s: "over_max_hours" in s).mean(),
                         level5_false_impossible=100 * (l5.outcome == "false_impossible").mean(),
                         legal_cost_over_cheapest_median_pct=pct_over.median()))
    focus = pd.DataFrame(rows)
    focus.to_csv(f"{OUT}/x_rules_in_focus.csv", index=False)
    say(focus.round(1).to_string(index=False))

    say("\n== Exploratory. Outcome shares by rule set (possible scenarios) ==")
    rs = (m[m.feasible].assign(fail=~m[m.feasible].legal)
          .pivot_table(index="name", columns="ruleset", values="fail", aggfunc="mean").mul(100)
          .loc[[NAMES[x] for x in order]])
    rs.round(1).to_csv(f"{OUT}/fail_by_ruleset.csv")
    say(rs.round(1).to_string())

    # ---------- Sensitivity: lenient parsing ----------
    say("\n== Sensitivity. Lenient grading (names accepted for IDs; SHIFT,EMPLOYEE order accepted) ==")
    le = lenient_regrade("results/main")
    le = le.merge(m[KEY + ["model", "feasible"]], on=KEY + ["model"])
    imp = le.outcome == "impossible"
    le.loc[imp, "outcome"] = np.where(le.loc[imp, "feasible"], "false_impossible", "correct_impossible")
    rows = []
    for mo in order:
        p = le[(le.model == mo) & le.feasible]
        st = m[(m.model == mo) & m.feasible]
        rows.append(dict(model=NAMES[mo], strict_legal_pct=100 * st.legal.mean(),
                         lenient_legal_pct=100 * (p.outcome == "legal").mean(),
                         strict_law_pct=100 * st.law.mean(), lenient_law_pct=100 * (p.outcome == "breaks_law").mean(),
                         changed=int((p.set_index(KEY).outcome != st.set_index(KEY).outcome.reindex(
                             p.set_index(KEY).index)).sum())))
    sens = pd.DataFrame(rows)
    sens.to_csv(f"{OUT}/sensitivity_lenient.csv", index=False)
    say(sens.round(1).to_string(index=False))

    say("\n== Spend ==")
    say(f"Text-only main run ${m.cost_usd.sum():.2f}; solver ${s.cost_usd.sum():.2f}; "
        f"pilot ${pd.read_csv('results/pilot/graded.csv').cost_usd.sum():.2f} "
        f"+ 64k-cap pilot check ${pd.read_csv('results/pilot_64k/graded.csv').cost_usd.sum():.2f}")
    open(f"{OUT}/report.txt", "w").write("\n".join(report) + "\n")


if __name__ == "__main__":
    main()
