"""Figures and tables for the paper, in the Outside Engineer style.

Reads results/analysis/*.csv (run analysis.py first) and writes <name>.html and <name>@3x.png here.
Usage: python3 figures/make_figures.py      (ONLY=<name> to redo one)
"""
import math
import os
import sys

import pandas as pd
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "figures")
A = os.path.join(ROOT, "results", "analysis")
sys.path.insert(0, ROOT)

N, G, LG, RED = "#1b263b", "#c3c7cf", "#e3e5e9", "#c8553d"

HEAD = """<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
body{width:1100px;font-family:Poppins,sans-serif;color:#1b263b;background:transparent}
.card{background:#f5f5f5;border-radius:34px;padding:46px 40px 36px}
h1{text-align:center;font-size:40px;font-weight:700;letter-spacing:.5px;line-height:1.05}
.sub{text-align:center;font-size:20px;line-height:1.35;font-weight:500;margin-top:14px;opacity:.8}
svg{display:block;font-family:Poppins,sans-serif}
.src{text-align:center;font-size:15px;font-weight:500;opacity:.7;margin-top:14px;line-height:1.4}
.logo{display:flex;align-items:center;gap:7px;justify-content:center;margin-top:26px}
.logo .mk{width:64px;height:64px;background:#1b263b;color:#fff;font-weight:700;font-size:35px;display:flex;align-items:center;justify-content:center;letter-spacing:-1.5px}
.logo .tx{font-size:28px;line-height:1.0}
table{width:100%;border-collapse:collapse;margin-top:28px;border-top:2px solid #1b263b;border-bottom:2px solid #1b263b}
th{font-size:15px;font-weight:700;line-height:1.35;padding:14px 14px 10px 0;border-bottom:1.5px solid #1b263b;text-align:left;vertical-align:bottom}
th span{font-weight:500}
td{padding:14px 14px 14px 0;border-bottom:1px solid #1b263b22;font-size:16px;line-height:1.45;vertical-align:middle}
tr:last-child td{border-bottom:none}
td.m{font-weight:700;font-size:16.5px;white-space:nowrap}
td.n{font-size:19px;font-weight:700;white-space:nowrap}
td.q{font-weight:500}
.c{text-align:center}
</style></head><body><div class="card">"""
LOGO = '<div class="logo"><div class="mk">OE</div><div class="tx">Outside<br>Engineer</div></div>'
TAIL = "</div></body></html>"


def page(title, sub, body, src=""):
    s = f"<div class='src'>{src}</div>" if src else ""
    return HEAD + f"<h1>{title}</h1><div class='sub'>{sub}</div>" + body + s + LOGO + TAIL


def svg(w, h, s, top=26):
    return f'<div style="margin-top:{top}px"><svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">{s}</svg></div>'


def text(x, y, t, size=19, weight=600, anchor="start", fill=N, op=1):
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
            f'fill="{fill}" opacity="{op}">{t}</text>')


def table(headers, rows, center_from=1, cls=None):
    cls = cls or {}
    h = "".join(f"<th class='{'c' if i >= center_from else ''}'>{x}</th>" for i, x in enumerate(headers))
    b = "".join("<tr>" + "".join(
        f"<td class='{cls.get(i, 'm' if i == 0 else 'n')} {'c' if i >= center_from else ''}'>{x}</td>"
        for i, x in enumerate(r)) + "</tr>" for r in rows)
    return f"<table><tr>{h}</tr>{b}</table>"


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - h), min(1, c + h)


T1 = pd.read_csv(os.path.join(A, "table1_outcomes_by_model.csv"))
ORDER = T1.model.tolist()


def model_rows(W, nameW, rh, y_top):
    s = ""
    for i, name in enumerate(ORDER):
        yc = y_top + i * rh + rh / 2
        s += f'<rect x="0" y="{yc - rh / 2 + 6}" width="{nameW}" height="{rh - 12}" fill="{LG}"/>'
        s += text(nameW / 2, yc + 7, name, 18, 600, "middle")
    return s


# ---------- Figure 1 ----------
def fig_legal_rate():
    W, nameW, x0, x1, rh, y_top = 1020, 250, 290, 930, 62, 96
    X = lambda v: x0 + v * (x1 - x0)
    s = f'<circle cx="{x0}" cy="30" r="10" fill="{N}"/>' + text(x0 + 20, 37, "Legal schedule, when one existed", 19)
    s += f'<circle cx="{x0 + 385}" cy="30" r="10" fill="{G}"/>' + text(x0 + 405, 37, "Said “impossible,” when it was", 19)
    y_end = y_top + len(ORDER) * rh
    for t in [0, .25, .5, .75, 1]:
        s += f'<line x1="{X(t)}" x2="{X(t)}" y1="{y_top - 8}" y2="{y_end}" stroke="{N}" stroke-opacity=".12" stroke-width="1.5"/>'
        s += text(X(t), y_end + 32, f"{int(t * 100)}%", 18, 500, "middle", op=.75)
    s += f'<line x1="0" x2="{W}" y1="{y_top - 14}" y2="{y_top - 14}" stroke="{N}" stroke-width="2"/>'
    s += model_rows(W, nameW, rh, y_top)
    for i, r in T1.iterrows():
        yc = y_top + i * rh + rh / 2
        for (k, n, col, dy) in [(r.correct_impossible_n, r.impossible, G, 0), (r.legal_n, r.possible, N, 0)]:
            lo, hi = wilson(k, n)
            s += f'<line x1="{X(lo)}" x2="{X(hi)}" y1="{yc + dy}" y2="{yc + dy}" stroke="{col}" stroke-width="5" stroke-linecap="round"/>'
            s += f'<circle cx="{X(k / n)}" cy="{yc + dy}" r="11" fill="{col}" stroke="#f5f5f5" stroke-width="3"/>'
        v = r.legal_pct
        lx = X(v / 100)
        s += text(lx + 18 if v < 80 else lx - 18, yc - 14, f"{v:.0f}%", 17, 700, "start" if v < 80 else "end")
    s += text((x0 + x1) / 2, y_end + 66, "Share of scenarios (dot) and 95% interval (line)", 18, 600, "middle")
    return page("WHICH MODELS BUILT A LEGAL SCHEDULE?", "Every model, on the same kind of task: build one week's staff schedule that follows "
                "the rules,<br>or say it can't be done", svg(W, y_end + 80, s),
                "Text-only condition. Opus 120 scenarios, Sonnet 150, Haiku and DeepSeek 1,200, GPT-6.1 Sol 600, others 3,552 each.")


# ---------- Figure 2 ----------
def fig_what_went_wrong():
    cats = [("legal", "Legal", N, "#fff"), ("breaks_law", "Broke a labor law", RED, "#fff"),
            ("breaks_business_rule", "Broke a business rule", "#6c7a92", "#fff"),
            ("premium_pay", "Owed premium pay", "#a3acbd", N), ("false_impossible", "Said “impossible” wrongly", G, N),
            ("unusable", "No usable answer", "#e8e9ec", N)]
    W, nameW, x0, x1, rh, y_top = 1020, 250, 266, 1010, 56, 96
    X = lambda v: x0 + v / 100 * (x1 - x0)
    s, lx, ly = "", 0, 24
    for key, lab, col, _ in cats:
        w = 22 + len(lab) * 9.6 + 34
        if lx + w > W:
            lx, ly = 0, ly + 36
        s += f'<rect x="{lx}" y="{ly - 13}" width="22" height="22" rx="4" fill="{col}" stroke="{N}" stroke-opacity=".25"/>' + text(lx + 30, ly + 5, lab, 17, 600)
        lx += w
    s += model_rows(W, nameW, rh, y_top)
    for i, r in T1.iterrows():
        y = y_top + i * rh + 9
        acc = 0
        for key, lab, col, tc in cats:
            v = r[f"{key}_pct"]
            if v <= 0:
                continue
            s += f'<rect x="{X(acc)}" y="{y}" width="{X(acc + v) - X(acc)}" height="{rh - 18}" fill="{col}"/>'
            if v >= 6:
                s += text((X(acc) + X(acc + v)) / 2, y + (rh - 18) / 2 + 6, f"{v:.0f}%", 16, 700, "middle", tc)
            acc += v
    y_end = y_top + len(ORDER) * rh
    return page("WHAT WENT WRONG", "Outcome of every scenario where a legal schedule existed, by model",
                svg(W, y_end + 8, s), "A schedule that broke several kinds of rule is counted once, under the most serious:<br>"
                "labor law, then business rule, then premium pay.")


# ---------- Figure 3 ----------
def fig_by_level():
    lv = pd.read_csv(os.path.join(A, "fail_by_level.csv"), index_col=0)
    desc = ["Level 1<br><span>4–6 staff</span>", "Level 2<br><span>7–10, shift leads</span>",
            "Level 3<br><span>11–15, teen workers</span>", "Level 4<br><span>16–20 staff</span>",
            "Level 5<br><span>21–25, tight availability</span>"]
    rows = []
    for name in ORDER:
        cells = []
        for c in lv.columns:
            v = lv.loc[name, c]
            a = min(1, v / 100)
            fg = "#fff" if a > .45 else N
            cells.append(f"<div style='background:rgba(27,38,59,{0.06 + .94 * a:.2f});color:{fg};border-radius:10px;padding:10px 0'>{v:.0f}%</div>")
        rows.append([name] + cells)
    style = "<style>td{padding:6px 8px 6px 0}td.n div{font-size:19px}</style>"
    return page("FAILURES RISE WITH DIFFICULTY", "Share of scenarios with a legal answer available where the model did not give one",
                style + table(["Model"] + desc, rows), "Levels 3–5 also have teen workers and a short evening shift. Darker = more failures.")


# ---------- Figure 4 ----------
def fig_rulesets():
    h3 = pd.read_csv(os.path.join(A, "h3_rulesets.csv"))
    sig = h3.groupby("model").p_holm.max()
    names = [n for n in ORDER if sig[n] < 0.05]
    W, nameW, x0, x1, rh, y_top = 1020, 250, 290, 960, 74, 96
    X = lambda v: x0 + v / 80 * (x1 - x0)
    keys = [("federal", "Federal only", G), ("seattle", "Seattle", "#6c7a92"), ("california", "California", N)]
    s, lx = "", x0
    for _, lab, col in keys:
        s += f'<circle cx="{lx}" cy="30" r="10" fill="{col}"/>' + text(lx + 20, 37, lab, 19)
        lx += 60 + len(lab) * 11
    y_end = y_top + len(names) * rh
    for t in [0, 20, 40, 60, 80]:
        s += f'<line x1="{X(t)}" x2="{X(t)}" y1="{y_top - 8}" y2="{y_end}" stroke="{N}" stroke-opacity=".12" stroke-width="1.5"/>'
        s += text(X(t), y_end + 32, f"{t}%", 18, 500, "middle", op=.75)
    s += f'<line x1="0" x2="{W}" y1="{y_top - 14}" y2="{y_top - 14}" stroke="{N}" stroke-width="2"/>'
    for i, name in enumerate(names):
        yc = y_top + i * rh + rh / 2
        s += f'<rect x="0" y="{yc - rh / 2 + 6}" width="{nameW}" height="{rh - 12}" fill="{LG}"/>' + text(nameW / 2, yc + 7, name, 18, 600, "middle")
        g = h3[h3.model == name].set_index("vs")
        vals = {"federal": g.federal_pct.iloc[0], "seattle": g.loc["seattle", "other_pct"], "california": g.loc["california", "other_pct"]}
        s += f'<line x1="{X(min(vals.values()))}" x2="{X(max(vals.values()))}" y1="{yc}" y2="{yc}" stroke="{N}" stroke-opacity=".25" stroke-width="4"/>'
        for k, lab, col in keys:
            s += f'<circle cx="{X(vals[k])}" cy="{yc}" r="11" fill="{col}" stroke="#f5f5f5" stroke-width="3"/>'
        s += text(X(vals["california"]) + 20, yc + 7, f"{vals['california']:.0f}%", 18, 700)
        s += text(X(vals["federal"]) - 20, yc + 7, f"{vals['federal']:.0f}%", 18, 700, "end", op=.6)
    s += text((x0 + x1) / 2, y_end + 66, "Share of scenarios where the schedule broke a labor law or owed premium pay", 18, 600, "middle")
    return page("MORE RULES, MORE BROKEN ONES", "Same businesses, same staff, three sets of labor rules. "
                "The models that struggled broke more rules<br>where there were more to follow",
                svg(W, y_end + 80, s), "Shown: the four models with a significant difference under both California and Seattle rules. "
                "The other five stayed at or below 2% under every rule set.")


# ---------- Figure 5 ----------
def fig_solver():
    h5 = pd.read_csv(os.path.join(A, "h5_solver.csv")).set_index("model")
    W, x0, x1, rh, y_top = 1020, 330, 960, 76, 96
    X = lambda v: x0 + v / 100 * (x1 - x0)
    rows = []
    for name in ["GPT-6 Luna", "Gemini 3.5 Flash Lite"]:
        r = h5.loc[name]
        rows.append((name, "Legal schedule, when one existed", r.text_legal_pct, r.solver_legal_pct))
        rows.append((name, "Broke a rule, when a legal one existed", r.text_violation_pct, r.solver_violation_pct))
    s = f'<circle cx="{x0}" cy="30" r="10" fill="{G}"/>' + text(x0 + 20, 37, "Text only", 19)
    s += f'<circle cx="{x0 + 160}" cy="30" r="10" fill="{N}"/>' + text(x0 + 180, 37, "Could write and run code", 19)
    y_end = y_top + len(rows) * rh + 24
    for t in [0, 25, 50, 75, 100]:
        s += f'<line x1="{X(t)}" x2="{X(t)}" y1="{y_top - 8}" y2="{y_end}" stroke="{N}" stroke-opacity=".12" stroke-width="1.5"/>'
        s += text(X(t), y_end + 32, f"{t}%", 18, 500, "middle", op=.75)
    s += f'<line x1="0" x2="{W}" y1="{y_top - 14}" y2="{y_top - 14}" stroke="{N}" stroke-width="2"/>'
    y = y_top
    for j, (name, lab, a, b) in enumerate(rows):
        if j % 2 == 0:
            if j:
                y += 24
                s += f'<line x1="0" x2="{W}" y1="{y - 12}" y2="{y - 12}" stroke="{N}" stroke-opacity=".18"/>'
            s += f'<rect x="0" y="{y + 6}" width="300" height="{2 * rh - 12}" fill="{LG}"/>' + text(150, y + rh + 7, name, 19, 700, "middle")
        yc = y + rh / 2
        s += text(x0 - 10, yc - 22, lab, 15, 600, "start", op=.7)
        s += f'<line x1="{X(a)}" x2="{X(b)}" y1="{yc + 6}" y2="{yc + 6}" stroke="{N}" stroke-opacity=".3" stroke-width="4"/>'
        s += f'<circle cx="{X(a)}" cy="{yc + 6}" r="11" fill="{G}" stroke="#f5f5f5" stroke-width="3"/>'
        s += f'<circle cx="{X(b)}" cy="{yc + 6}" r="11" fill="{N}" stroke="#f5f5f5" stroke-width="3"/>'
        for v, op in [(a, .6), (b, 1)]:
            other = b if v == a else a
            right = v >= other
            s += text(X(v) + (20 if right else -20), yc + 13, f"{v:.0f}%", 18, 700, "start" if right else "end", op=op)
        y += rh
    return page("LETTING THE MODEL RUN CODE", "Same scenarios, with and without a Python tool that includes a constraint solver",
                svg(W, y_end + 46, s), "GPT-6 Luna: 300 scenarios (240 with a legal schedule). Gemini 3.5 Flash Lite: 120 scenarios (96). "
                "With code, Gemini gave no usable answer on 21 of its 24 impossible scenarios.")


# ---------- Tables ----------
def tab_setup():
    t = T1.set_index("model")
    ids = {"Claude Opus 5.5": "Anthropic", "Claude Sonnet 5.5": "Anthropic", "Claude Haiku 5.5": "Anthropic",
           "DeepSeek V4.1 Flash": "DeepSeek", "GPT-6.1 Sol": "OpenAI", "GPT-6 Luna": "OpenAI", "gpt-oss-120b": "OpenAI (open weights)",
           "Llama 4 Maverick": "Meta (open weights)", "Gemini 3.5 Flash Lite": "Google"}
    rows = [[n, ids[n], f"{int(t.loc[n, 'businesses'])}", f"{int(t.loc[n, 'instances']):,}", f"${t.loc[n, 'cost_total']:.2f}",
             f"{t.loc[n, 'cost_per_instance'] * 100:.2f}¢"] for n in ORDER]
    return page("STUDY SETUP", "Nine models. Each business was run under 3 rule sets × 2 ways of describing staff availability",
                table(["Model", "Maker", "Businesses", "Scenarios", "Total cost", "Cost per<br><span>scenario</span>"], rows,
                      cls={1: "q"}),
                "Smaller samples are whole businesses drawn evenly across the five levels, so every smaller sample sits inside every larger one.")


def tab_results():
    rows = []
    for _, r in T1.iterrows():
        rows.append([r.model, f"{r.legal_pct:.0f}%", f"{r.breaks_law_pct:.1f}%", f"{r.correct_impossible_pct:.0f}%",
                     (f"${r.premium_per_schedule:,.0f}" if r.premium_per_schedule >= 10 else f"${r.premium_per_schedule:.2f}"), f"{r.cost_per_legal * 100:.1f}¢"])
    return page("FULL RESULTS", "Text-only condition",
                table(["Model", "Legal schedule<br><span>when one existed</span>", "Broke a<br><span>labor law</span>",
                       "Caught<br><span>impossible</span>", "Premium pay owed<br><span>per schedule</span>",
                       "Cost per<br><span>legal schedule</span>"], rows),
                "Premium pay: average extra wages owed (overtime, double time, seventh-day pay, Seattle rest-gap pay, missed-meal pay) "
                "per schedule returned. Cost per legal schedule: API cost of every scenario with a legal answer, divided by legal schedules.")


def tab_grading():
    rows = [["Legal", "Breaks no rule and owes no premium pay", "Pass"],
            ["Broke a labor law", "Teen-worker hours or times; missed California meal break", "Fail"],
            ["Broke a business rule", "Shift not covered, wrong role, outside availability, two shifts a day, over max hours", "Fail"],
            ["Owed premium pay", "Overtime, double time, seventh-day pay, Seattle rest-gap pay (the owner asked to avoid these)", "Fail"],
            ["Caught impossible", "Answered IMPOSSIBLE when no schedule could follow every rule", "Pass"],
            ["Said impossible wrongly", "Answered IMPOSSIBLE when a legal schedule existed", "Fail"],
            ["No usable answer", "No schedule in the required format, or cut off at the length limit", "Fail"]]
    return page("HOW EACH ANSWER WAS GRADED", "Code checked every answer against the rules; no AI judge",
                table(["Outcome", "What it means", "Result"], rows, center_from=2, cls={1: "q", 2: "m"}))


GRAPHICS = {"figure-1-legal-schedule-rate": fig_legal_rate, "figure-2-what-went-wrong": fig_what_went_wrong,
            "figure-3-failures-by-difficulty": fig_by_level, "figure-4-rule-sets": fig_rulesets,
            "figure-5-running-code": fig_solver, "table-1-study-setup": tab_setup, "table-2-grading": tab_grading,
            "table-3-full-results": tab_results}

if __name__ == "__main__":
    only = os.environ.get("ONLY")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1100, "height": 400}, device_scale_factor=3)
        for name, fn in GRAPHICS.items():
            if only and name != only:
                continue
            html = os.path.join(OUT, name + ".html")
            open(html, "w").write(fn())
            pg.goto("file://" + html)
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(300)
            pg.screenshot(path=os.path.join(OUT, name + "@3x.png"), full_page=True, omit_background=True)
            print("wrote", name)
        b.close()
