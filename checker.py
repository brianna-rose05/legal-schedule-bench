"""Rule checker: grades one schedule against one scenario and rule set.

A schedule is a list of assignments: dict(emp, shift, role, meals=[start minute, ...]).
Returns every violation found, the premium pay each one would cost, and the labor cost.
"""
from rules import SCHOOL_DAYS, SCHOOL_HOURS, MEAL_MIN

LAW = {"minor_time", "minor_school_hours", "minor_daily", "minor_weekly", "meal_missed"}
PREMIUM = {"overtime_weekly", "overtime_daily", "double_time", "seventh_day", "rest_gap"}
BUSINESS = {"coverage", "wrong_role", "unavailable", "two_shifts_one_day", "over_max_hours", "unknown_id", "duplicate"}


def worked_minutes(shift, meals):
    """Minutes worked in a shift, after valid 30-minute meal breaks."""
    valid = [m for m in meals if shift["start"] <= m and m + MEAL_MIN <= shift["end"]]
    return shift["end"] - shift["start"] - MEAL_MIN * len(valid), sorted(valid)


def check(biz, rs, schedule):
    emps = {e["id"]: e for e in biz["staff"]}
    shifts = {s["id"]: s for s in biz["shifts"]}
    v = []  # (type, emp, day, detail, dollars)

    def add(t, emp=None, day=None, detail="", dollars=0.0):
        v.append(dict(type=t, emp=emp, day=day, detail=detail, dollars=round(dollars, 2)))

    seen = set()
    per_emp = {}
    cover = {sid: {} for sid in shifts}
    for a in schedule:
        e, s = emps.get(a["emp"]), shifts.get(a["shift"])
        if not e or not s:
            add("unknown_id", a.get("emp"), None, f"{a.get('emp')} / {a.get('shift')}")
            continue
        if (a["emp"], a["shift"]) in seen:
            add("duplicate", a["emp"], s["day"], a["shift"])
            continue
        seen.add((a["emp"], a["shift"]))
        role = a.get("role")
        if role not in e["roles"]:
            add("wrong_role", a["emp"], s["day"], f"{role} in {a['shift']}")
        else:
            cover[s["id"]][role] = cover[s["id"]].get(role, 0) + 1
        w = e["availability"][s["day"]]
        if not w or s["start"] < w[0] or s["end"] > w[1]:
            add("unavailable", a["emp"], s["day"], a["shift"])
        per_emp.setdefault(a["emp"], []).append((s, a.get("meals") or []))

    for sid, s in shifts.items():
        for role, n in s["need"].items():
            if cover[sid].get(role, 0) < n:
                add("coverage", None, s["day"], f"{sid} needs {n} {role}, has {cover[sid].get(role, 0)}")

    labor = 0.0
    for eid, items in per_emp.items():
        e = emps[eid]
        wage = e["wage"]
        age = e["age"]
        by_day = {}
        for s, meals in items:
            by_day.setdefault(s["day"], []).append((s, meals))
        daily = {}
        for d, lst in by_day.items():
            if len(lst) > 1:
                add("two_shifts_one_day", eid, d, ",".join(s["id"] for s, _ in lst))
            mins = 0
            for s, meals in lst:
                wm, valid = worked_minutes(s, meals)
                mins += wm
                labor += wage * wm / 60
                # --- California meal periods
                if rs == "california":
                    span = s["end"] - s["start"]
                    if wm > 300:
                        first_ok = valid and valid[0] <= s["start"] + 300
                        second_needed = wm > 600
                        second_ok = len(valid) >= 2 and valid[1] <= s["start"] + 600 + MEAL_MIN
                        if not first_ok or (second_needed and not second_ok):
                            add("meal_missed", eid, d, s["id"], wage)
                # --- minors
                if age <= 15:
                    if s["start"] < 7 * 60 or s["end"] > 19 * 60:
                        add("minor_time", eid, d, f"age {age}, {s['id']}")
                    if d in SCHOOL_DAYS and s["start"] < SCHOOL_HOURS[1] and s["end"] > SCHOOL_HOURS[0]:
                        add("minor_school_hours", eid, d, f"age {age}, {s['id']}")
                elif age <= 17 and rs == "california":
                    nxt_school = (d + 1) % 7 in SCHOOL_DAYS
                    latest = 22 * 60 if nxt_school else 24 * 60 + 30
                    if s["start"] < 5 * 60 or s["end"] > latest:
                        add("minor_time", eid, d, f"age {age}, {s['id']}")
                    if d in SCHOOL_DAYS and s["start"] < SCHOOL_HOURS[1] and s["end"] > SCHOOL_HOURS[0]:
                        add("minor_school_hours", eid, d, f"age {age}, {s['id']}")
            daily[d] = mins
            if age <= 15:
                cap = 180 if d in SCHOOL_DAYS else 480
                if mins > cap:
                    add("minor_daily", eid, d, f"age {age}, {mins / 60:.1f} h")
            elif age <= 17 and rs == "california":
                cap = 240 if d in SCHOOL_DAYS else 480
                if mins > cap:
                    add("minor_daily", eid, d, f"age {age}, {mins / 60:.1f} h")

        total = sum(daily.values())
        if total > e["max_hours"] * 60:
            add("over_max_hours", eid, None, f"{total / 60:.1f} > {e['max_hours']}")
        if age <= 15 and total > 18 * 60:
            add("minor_weekly", eid, None, f"age {age}, {total / 60:.1f} h")
        if 16 <= age <= 17 and rs == "california" and total > 48 * 60:
            add("minor_weekly", eid, None, f"age {age}, {total / 60:.1f} h")

        # --- premium pay
        if rs == "california":
            all7 = len([d for d in daily if daily[d] > 0]) == 7
            reg = 0
            for d, m in daily.items():
                h = m / 60
                if all7 and d == 6:
                    p = min(h, 8) * 0.5 + max(0, h - 8) * 1.0
                    if p:
                        add("seventh_day", eid, d, f"{h:.1f} h", wage * p)
                    continue
                if h > 8:
                    add("overtime_daily", eid, d, f"{h:.1f} h", wage * 0.5 * (min(h, 12) - 8))
                if h > 12:
                    add("double_time", eid, d, f"{h:.1f} h", wage * 1.0 * (h - 12))
                reg += min(h, 8)
            if reg > 40:
                add("overtime_weekly", eid, None, f"{reg:.1f} regular h", wage * 0.5 * (reg - 40))
        else:
            if total > 2400:
                add("overtime_weekly", eid, None, f"{total / 60:.1f} h", wage * 0.5 * (total - 2400) / 60)
        if rs == "seattle":
            for d in range(6):
                if d in by_day and d + 1 in by_day:
                    end = max(s["end"] for s, _ in by_day[d])
                    nxt = min(by_day[d + 1], key=lambda x: x[0]["start"])[0]
                    gap = nxt["start"] + 1440 - end
                    if gap < 600:
                        inside = min(600 - gap, nxt["end"] - nxt["start"]) / 60
                        add("rest_gap", eid, d + 1, f"{gap / 60:.1f} h gap", wage * 0.5 * inside)

    kinds = {x["type"] for x in v}
    if kinds & LAW:
        outcome = "breaks_law"
    elif kinds & BUSINESS:
        outcome = "breaks_business_rule"
    elif kinds & PREMIUM:
        outcome = "premium_pay"
    else:
        outcome = "legal"
    return dict(outcome=outcome, violations=v,
                premium_dollars=round(sum(x["dollars"] for x in v), 2),
                labor_cost=round(labor, 2))
