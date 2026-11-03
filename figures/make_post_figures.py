"""Extra Outside Engineer graphics for the Substack post (tables shown as images).

Usage: python3 figures/make_post_figures.py      (ONLY=<name> to redo one)
"""
import os
import sys

import pandas as pd
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_figures as MF  # noqa: E402

OUT, A = MF.OUT, MF.A
T1 = MF.T1.set_index("model")
ORDER = MF.ORDER
FOCUS = pd.read_csv(os.path.join(A, "x_rules_in_focus.csv")).set_index("model")
VT = pd.read_csv(os.path.join(A, "x_violation_types.csv"), index_col=0)
MAKER = {"Claude Opus 5.5": "Anthropic", "Claude Sonnet 5.5": "Anthropic", "Claude Haiku 5.5": "Anthropic",
         "DeepSeek V4.1 Flash": "DeepSeek", "GPT-6.1 Sol": "OpenAI", "GPT-6 Luna": "OpenAI",
         "gpt-oss-120b": "OpenAI (open weights)", "Llama 4 Maverick": "Meta (open weights)",
         "Gemini 3.5 Flash Lite": "Google"}
WRAP = "<style>td.q,td.w{white-space:normal}td.w{font-weight:500;font-size:15px}</style>"


def related():
    rows = [["TravelPlanner<br><span style='font-weight:500'>Xie et al., 2024</span>",
             "Multi-day travel plans under a budget and other constraints",
             "GPT-4 produced a valid plan in 0.6% of tasks",
             "Constraints carry no legal or financial cost"],
            ["NATURAL PLAN<br><span style='font-weight:500'>Zheng et al., 2024</span>",
             "Trip planning, meeting planning and calendar scheduling",
             "Best model solved 34.8% of trip plans; all fell below 5% at 10 cities",
             "Puzzles built for testing; one set of rules"],
            ["LLM-Modulo<br><span style='font-weight:500'>Kambhampati et al., 2024</span>",
             "Position paper on whether models can plan and check their own plans",
             "Models plan better in a loop with outside verifiers",
             "Argued, not measured on real rules"],
            ["OptiMUS<br><span style='font-weight:500'>AhmadiTeshnizi et al., 2023</span>",
             "A model writes and debugs solver code for optimization problems",
             "Solved 67% more problems than basic prompting",
             "Not tested on labor rules or scheduling"],
            ["Staff-scheduling reviews<br><span style='font-weight:500'>Ernst et al., 2004; Van den Bergh et al., 2013</span>",
             "Decades of solver methods for building rosters",
             "Rostering is solved as an optimization problem with exact or heuristic methods",
             "Predates asking a chatbot for the schedule"]]
    return MF.page("WHAT PRIOR STUDIES TESTED", "None measured whether AI-built staff schedules follow real labor law",
                   WRAP + MF.table(["Study", "What it tested", "Key finding", "What it left open"], rows, center_from=9,
                                   cls={0: "m", 1: "w", 2: "w", 3: "w"}))


def rules():
    rows = [["Weekly overtime", "Over 40 h at 1.5×", "Over 40 h at 1.5×", "Over 40 h at 1.5×"],
            ["Daily overtime", "—", "Over 8 h at 1.5×; over 12 h at 2×", "—"],
            ["Seventh day in a row", "—", "First 8 h at 1.5×", "—"],
            ["Meal breaks", "—", "30 min, starting within the first 5 h; a second over 10 h; 1 hour's pay if missed", "—"],
            ["Ages 14–15", "Outside school hours; 3 h a school day, 18 h a school week; 7 a.m.–7 p.m.", "Same", "Same"],
            ["Ages 16–17", "—", "Outside school hours; 4 h a school day, 48 h a week; 5 a.m.–10 p.m.", "—"],
            ["Rest between shifts", "—", "—", "Hours inside a gap under 10 h at 1.5×"]]
    return MF.page("THE LABOR RULES TESTED", "Same business, same staff, same shifts, scheduled under three rule sets",
                   WRAP + MF.table(["Rule", "Federal only", "California", "Seattle chain store"], rows, center_from=9,
                                   cls={0: "m", 1: "w", 2: "w", 3: "w"}),
                   "Checked against 29 CFR 570.35, the California Labor Commissioner and Seattle's Secure Scheduling Ordinance. "
                   "The owner also asked for no overtime or other premium pay.")


def levels():
    rows = [["1", "4–6", "—", "One role, two shifts a day"],
            ["2", "7–10", "—", "Shift leads required at open and close"],
            ["3", "11–15", "1–3", "Workers aged 15–17 and a short evening shift"],
            ["4", "16–20", "1–3", "More staff to coordinate"],
            ["5", "21–25", "1–3", "Tight availability: more days off, more shifts to cover"]]
    return MF.page("FIVE LEVELS OF DIFFICULTY", "120 businesses at each level; each level adds to the one before",
                   WRAP + MF.table(["Level", "Staff", "Teen workers", "What changes"], rows, center_from=1,
                                   cls={0: "n", 3: "w"}),
                   "Cafés, retail shops and quick-service restaurants, generated from a fixed seed. "
                   "In 23% of businesses, an impossibility was planted on purpose.")


def setup():
    rows = [[m, MAKER[m], f"{int(T1.loc[m, 'businesses'])}", f"{int(T1.loc[m, 'instances']):,}"] for m in ORDER]
    return MF.page("STUDY SETUP", "Nine models. Each business was run under 3 rule sets × 2 ways of describing staff availability",
                   MF.table(["Model", "Maker", "Businesses", "Scenarios"], rows, cls={1: "q"}),
                   "Smaller samples are whole businesses drawn evenly across the five levels, and every smaller sample sits "
                   "inside every larger one. Temperature 0, default reasoning, run November 2, 2026.")


def focus():
    rows = []
    for m in ORDER:
        f = FOCUS.loc[m]
        rows.append([m, f"{int(VT.loc[m, 'schedules']):,}", f"{f.outside_availability:.0f}%", f"{f.over_own_max_hours:.0f}%",
                     f"{f.teen_rule_broken_levels3to5:.0f}%", f"{f.meal_missed_california:.0f}%"])
    style = "<style>td.n:nth-child(5),td.n:nth-child(6){color:#c8553d}</style>"
    return MF.page("WHICH RULES BROKE", "Share of returned schedules that broke each rule, when a legal schedule existed",
                   style + MF.table(["Model", "Schedules<br><span>returned</span>", "Outside<br><span>availability</span>",
                                     "Over their own<br><span>weekly max</span>", "Teen-worker<br><span>rule</span>",
                                     "California<br><span>meal break</span>"], rows),
                   "Teen rules counted at levels 3–5, the only levels with workers under 18. Meal breaks counted under "
                   "California rules, the only rule set that requires them. Labor-law columns in red.")


def results():
    rows = []
    for m in ORDER:
        r = T1.loc[m]
        prem = f"${r.premium_per_schedule:,.0f}" if r.premium_per_schedule >= 10 else f"${r.premium_per_schedule:.2f}"
        rows.append([m, f"{r.legal_pct:.0f}%", f"{r.breaks_law_pct:.1f}%", f"{r.correct_impossible_pct:.0f}%",
                     f"{r.false_impossible_pct:.0f}%", prem])
    return MF.page("FULL RESULTS", "Text-only condition",
                   MF.table(["Model", "Legal schedule<br><span>when one existed</span>", "Broke a<br><span>labor law</span>",
                             "Caught<br><span>impossible</span>", "Said impossible<br><span>wrongly</span>",
                             "Premium pay owed<br><span>per schedule</span>"], rows),
                   "Premium pay: average extra wages owed (overtime, double time, seventh-day pay, Seattle rest-gap pay, "
                   "missed-meal pay) per schedule returned.")


def hypotheses():
    rows = [["H1", "A model breaks a labor law in 20% or more of schedules", "Supported",
             "Llama 4 Maverick 34%, Gemini 3.5 Flash Lite 31%"],
            ["H2", "Rule-breaking rises with difficulty for most models", "Supported", "7 of 9 models"],
            ["H3", "More labor problems under California and Seattle rules", "Partly", "4 of 9 models"],
            ["H4", "Most models return a schedule instead of saying \"impossible\"", "Not supported",
             "Only 2 of 9; seven caught 96% or more"],
            ["H5", "Running solver code at least halves rule-breaking", "Supported", "Both models tested"]]
    style = ("<style>td.r{font-weight:700;white-space:nowrap}td.r.yes{color:#1b263b}td.r.no{color:#c8553d}</style>")
    body = "<table><tr><th></th><th>Hypothesis</th><th>Result</th><th>Evidence</th></tr>"
    for h, txt, res, ev in rows:
        cls = "no" if res == "Not supported" else "yes"
        body += f"<tr><td class='m'>{h}</td><td class='w' style='white-space:normal'>{txt}</td><td class='r {cls}'>{res}</td><td class='w' style='white-space:normal'>{ev}</td></tr>"
    body += "</table>"
    return MF.page("HYPOTHESES, CHECKED", "Five predictions written before the main run", WRAP + style + body)


def example():
    rows = [["Ages 14–15: outside school hours", "Not before 3:00 p.m. on a school day", "Starts 12:30 p.m., during school"],
            ["Ages 14–15: hours on a school day", "At most 3 hours", "8 hours of work"],
            ["Ages 14–15: time of day", "Done by 7:00 p.m.", "Works until 9:00 p.m."],
            ["Role", "Barista only", "Scheduled as shift lead"],
            ["Availability", "Wednesday 3:30–9:00 p.m.", "Starts three hours early"],
            ["Weekly maximum", "12 hours", "14 hours"]]
    head = ("<div style='margin-top:26px;display:flex;gap:14px;justify-content:center'>"
            "<div style='background:#e3e5e9;border-radius:14px;padding:14px 22px;font-size:17px;line-height:1.45'>"
            "<b>Wren</b>, age 15 · barista · works up to 12 h a week<br>Café with 18 staff (level 4), federal rules</div>"
            "<div style='background:#1b263b;color:#fff;border-radius:14px;padding:14px 22px;font-size:17px;line-height:1.45'>"
            "<b>Gemini's assignment</b><br>Wednesday 12:30–9:00 p.m., as shift lead</div></div>")
    style = "<style>td.bad{color:#c8553d;font-weight:700}</style>"
    body = "<table><tr><th>Rule</th><th>Limit</th><th>Gemini's schedule</th></tr>"
    for r in rows:
        body += f"<tr><td class='m'>{r[0]}</td><td class='q'>{r[1]}</td><td class='bad'>{r[2]}</td></tr>"
    body += "</table>"
    return MF.page("ONE SHIFT, SIX BROKEN RULES", "A real answer from Gemini 3.5 Flash Lite. The schedule came back formatted like any other",
                   head + style + body,
                   "The same schedule broke 46 rules in all, across 18 staff. The first three rows are labor-law violations.")


GRAPHICS = {"post-table-related-work": related, "post-table-labor-rules": rules, "post-table-levels": levels,
            "post-table-setup": setup, "post-table-rules-broken": focus, "post-table-full-results": results,
            "post-table-hypotheses": hypotheses, "post-figure-one-shift": example}

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
