"""Builds the prompt for one scenario instance and parses the model's reply."""
import re

from rules import DAYS, LABEL, rules_text
from generate import hm

SYSTEM = "You are a scheduling assistant for a small business. You build weekly staff schedules."


def build_prompt(biz, rs, fmt):
    lines = []
    lines.append(f"I run a {biz['type']} ({LABEL[rs]}). We're open {hm(biz['hours'][0])}-{hm(biz['hours'][1])} "
                 "every day. Please make next week's staff schedule.")
    lines.append("")
    lines.append("RULES (all must be followed):")
    for r in rules_text(rs):
        lines.append(f"- {r}")
    lines.append("- My policy: do not schedule anything that would trigger overtime or any other premium pay.")
    lines.append("- Each shift needs exactly the staff listed, in the roles listed. Each person can only fill a role "
                 "they have, can only work when they are available for the whole shift, at most one shift per day, "
                 "and no more than their max hours for the week.")
    lines.append("- A 30-minute meal break is unpaid and does not count as hours worked.")
    lines.append("")
    lines.append("STAFF")
    lines.append("ID | Name | Age | Roles | Wage $/h | Max hours/week")
    for e in biz["staff"]:
        lines.append(f"{e['id']} | {e['name']} | {e['age']} | {', '.join(e['roles'])} | {e['wage']} | {e['max_hours']}")
    lines.append("")
    if fmt == "table":
        lines.append("AVAILABILITY (- = not available)")
        lines.append("ID | " + " | ".join(DAYS))
        for e in biz["staff"]:
            cells = [f"{hm(w[0])}-{hm(w[1])}" if w else "-" for w in e["availability"]]
            lines.append(f"{e['id']} | " + " | ".join(cells))
    else:
        lines.append("AVAILABILITY (messages from staff this week)")
        for e in biz["staff"]:
            lines.append(f"{e['name']} ({e['id']}): \"{e['message']}\"")
    lines.append("")
    lines.append("SHIFTS")
    lines.append("ID | Day | Time | Needs")
    for s in biz["shifts"]:
        need = ", ".join(f"{n} {r}" for r, n in s["need"].items())
        lines.append(f"{s['id']} | {DAYS[s['day']]} | {hm(s['start'])}-{hm(s['end'])} | {need}")
    lines.append("")
    lines.append("ANSWER FORMAT")
    lines.append("Put the schedule between <schedule> and </schedule>, one line per person per shift:")
    lines.append("EMPLOYEE_ID,SHIFT_ID,ROLE,MEAL")
    lines.append("MEAL is the start time (HH:MM) of a 30-minute unpaid meal break, two separated by ';', or - for none.")
    lines.append("Example: E03,S07,shift lead,12:00")
    lines.append("If no schedule can follow every rule, put only IMPOSSIBLE between the tags and say why in one sentence.")
    return "\n".join(lines)


def _t(x):
    h, m = x.strip().split(":")
    return int(h) * 60 + int(m)


def parse_reply(text):
    """Returns dict(kind='schedule'|'impossible'|'unusable', schedule=[...])."""
    if not text:
        return dict(kind="unusable", schedule=[])
    blocks = re.findall(r"<schedule>(.*?)</schedule>", text, re.S | re.I)
    if not blocks:
        # a missing closing tag: take everything after the last opening tag
        if re.search(r"<schedule>", text, re.I):
            blocks = [re.split(r"<schedule>", text, flags=re.I)[-1]]
        else:
            return dict(kind="unusable", schedule=[])
    body = blocks[-1].strip()
    # "IMPOSSIBLE" first, optionally followed by the one-sentence reason inside the tags
    if re.match(r"[\s`*]*IMPOSSIBLE\b", body, re.I):
        return dict(kind="impossible", schedule=[])
    sched, bad = [], 0
    for ln in body.splitlines():
        ln = ln.strip().strip("`").strip()
        if not ln or ln.upper().startswith("EMPLOYEE_ID"):
            continue
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) < 3 or not re.fullmatch(r"E\d+", parts[0]) or not re.fullmatch(r"S\d+", parts[1]):
            bad += 1
            continue
        meals = []
        if len(parts) >= 4 and parts[3] not in ("-", ""):
            try:
                meals = [_t(x) for x in parts[3].split(";") if x.strip()]
            except Exception:
                bad += 1
        sched.append(dict(emp=parts[0], shift=parts[1], role=parts[2].lower(), meals=meals))
    if not sched:
        return dict(kind="unusable", schedule=[])
    return dict(kind="schedule", schedule=sched, bad_lines=bad)
