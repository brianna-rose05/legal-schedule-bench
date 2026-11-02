"""Answer key: Google OR-Tools CP-SAT finds the cheapest schedule that breaks no rule,
or proves that none exists. "No rule" includes the owner's instruction: no overtime,
no Seattle rest-gap premium, no 7th-day premium.
"""
from ortools.sat.python import cp_model

from rules import SCHOOL_DAYS, SCHOOL_HOURS, MEAL_MIN


def worked(s):
    """Minutes worked if the shift includes a meal break whenever it runs over 5 hours."""
    L = s["end"] - s["start"]
    return L - MEAL_MIN if L > 300 else L


def meal_for(s):
    """Meal break start used in solver schedules (2 hours in, so always before 5 hours of work)."""
    return [s["start"] + 120] if s["end"] - s["start"] > 300 else []


def allowed(e, s, rs):
    w = e["availability"][s["day"]]
    if not w or s["start"] < w[0] or s["end"] > w[1]:
        return False
    age, d, wm = e["age"], s["day"], worked(s)
    in_school = d in SCHOOL_DAYS and s["start"] < SCHOOL_HOURS[1] and s["end"] > SCHOOL_HOURS[0]
    if age <= 15:
        if s["start"] < 420 or s["end"] > 1140 or in_school:
            return False
        if wm > (180 if d in SCHOOL_DAYS else 480):
            return False
    elif age <= 17 and rs == "california":
        latest = 1320 if (d + 1) % 7 in SCHOOL_DAYS else 1470
        if s["start"] < 300 or s["end"] > latest or in_school:
            return False
        if wm > (240 if d in SCHOOL_DAYS else 480):
            return False
    if rs == "california" and wm > 480:
        return False
    return True


def solve(biz, rs, time_limit=5.0):
    m = cp_model.CpModel()
    emps, shifts = biz["staff"], biz["shifts"]
    x = {}
    for e in emps:
        for s in shifts:
            if allowed(e, s, rs):
                for r in s["need"]:
                    if r in e["roles"]:
                        x[e["id"], s["id"], r] = m.NewBoolVar(f"x_{e['id']}_{s['id']}_{r}")
    for s in shifts:
        for r, n in s["need"].items():
            m.Add(sum(v for (ei, si, rr), v in x.items() if si == s["id"] and rr == r) == n)
    sh = {s["id"]: s for s in shifts}
    for e in emps:
        mine = {k: v for k, v in x.items() if k[0] == e["id"]}
        for s in shifts:  # one role per shift
            m.Add(sum(v for k, v in mine.items() if k[1] == s["id"]) <= 1)
        days = {}
        for k, v in mine.items():
            days.setdefault(sh[k[1]]["day"], []).append(v)
        work_day = {}
        for d, vs in days.items():
            m.Add(sum(vs) <= 1)
            work_day[d] = sum(vs)
        total = sum(worked(sh[k[1]]) * v for k, v in mine.items())
        cap = min(e["max_hours"] * 60, 2400)
        if e["age"] <= 15:
            cap = min(cap, 18 * 60)
        elif e["age"] <= 17 and rs == "california":
            cap = min(cap, 48 * 60)
        m.Add(total <= cap)
        if rs == "california" and len(days) == 7:
            m.Add(sum(work_day[d] for d in days) <= 6)
        if rs == "seattle":
            for (ei, si, _), v in mine.items():
                for (ej, sj, _), w in mine.items():
                    a, b = sh[si], sh[sj]
                    if b["day"] == a["day"] + 1 and b["start"] + 1440 - a["end"] < 600:
                        m.Add(v + w <= 1)
    wage = {e["id"]: e["wage"] for e in emps}
    m.Minimize(sum(wage[k[0]] * worked(sh[k[1]]) * v for k, v in x.items()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 1
    solver.parameters.relative_gap_limit = 0.005
    st = solver.Solve(m)
    if st == cp_model.INFEASIBLE:
        return dict(feasible=False, status="infeasible")
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return dict(feasible=None, status=solver.StatusName(st))
    sched = [dict(emp=k[0], shift=k[1], role=k[2], meals=meal_for(sh[k[1]]))
             for k, v in x.items() if solver.Value(v)]
    return dict(feasible=True, status=solver.StatusName(st),
                cost=round(solver.ObjectiveValue() / 60, 2), schedule=sched)
