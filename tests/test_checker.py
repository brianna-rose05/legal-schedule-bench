"""Grader tests: a schedule with one planted violation must be caught, for every rule in every rule set,
and a clean schedule must pass. Run: python3 tests/test_checker.py
"""
import copy
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from checker import check  # noqa: E402

H = 60
FULL = [[6 * H, 23 * H]] * 7


def biz(staff, shifts):
    return dict(business_id="T", staff=staff, shifts=shifts, hours=[6 * H, 23 * H])


def emp(i, age=30, roles=("crew",), wage=20, max_h=40, av=FULL):
    return dict(id=f"E{i:02d}", name=f"N{i}", age=age, roles=list(roles), wage=wage, max_hours=max_h,
                availability=[list(w) if w else None for w in av])


def shift(i, day, start, end, need=None):
    return dict(id=f"S{i:02d}", day=day, name="x", start=start, end=end, need=need or {"crew": 1})


def a(e, s, role="crew", meals=()):
    return dict(emp=e, shift=s, role=role, meals=list(meals))


CASES = []  # (name, ruleset(s), business, schedule, expected violation type or None)


def case(name, rss, b, sched, expect):
    for rs in rss:
        CASES.append((name, rs, b, sched, expect))


ALL = ["federal", "california", "seattle"]

# clean: 4h shift, adult
b0 = biz([emp(1)], [shift(1, 0, 9 * H, 13 * H)])
case("clean short shift", ALL, b0, [a("E01", "S01")], None)

# business rules
case("missing coverage", ALL, b0, [], "coverage")
b1 = biz([emp(1, roles=("crew",))], [shift(1, 0, 9 * H, 13 * H, {"shift lead": 1})])
case("wrong role", ALL, b1, [a("E01", "S01", "shift lead")], "wrong_role")
b2 = biz([emp(1, av=[[12 * H, 20 * H]] + [None] * 6)], [shift(1, 0, 9 * H, 13 * H)])
case("outside availability", ALL, b2, [a("E01", "S01")], "unavailable")
b3 = biz([emp(1)], [shift(1, 0, 6 * H, 10 * H), shift(2, 0, 14 * H, 18 * H)])
case("two shifts one day", ALL, b3, [a("E01", "S01"), a("E01", "S02")], "two_shifts_one_day")
b4 = biz([emp(1, max_h=8)], [shift(1, 0, 9 * H, 13 * H), shift(2, 1, 9 * H, 14 * H)])
case("over max hours", ALL, b4, [a("E01", "S01"), a("E01", "S02")], "over_max_hours")
case("unknown employee", ALL, b0, [a("E09", "S01")], "unknown_id")

# meal breaks (California only)
b5 = biz([emp(1)], [shift(1, 0, 9 * H, 15 * H)])  # 6h shift
case("meal missing", ["california"], b5, [a("E01", "S01")], "meal_missed")
case("meal too late", ["california"], b5, [a("E01", "S01", meals=[14 * H + 30])], "meal_missed")
case("meal given", ["california"], b5, [a("E01", "S01", meals=[12 * H])], None)
case("no meal rule outside CA", ["federal", "seattle"], b5, [a("E01", "S01")], None)

# daily overtime / double time (California)
b6 = biz([emp(1)], [shift(1, 0, 8 * H, 18 * H)])  # 10h, meal -> 9.5 worked
case("daily overtime", ["california"], b6, [a("E01", "S01", meals=[11 * H, 15 * H])], "overtime_daily")
b7 = biz([emp(1)], [shift(1, 0, 6 * H, 20 * H)])  # 14h -> 13 worked with 2 meals
case("double time", ["california"], b7, [a("E01", "S01", meals=[9 * H, 14 * H])], "double_time")
case("10h day fine outside CA", ["federal", "seattle"], b6, [a("E01", "S01", meals=[11 * H])], None)

# weekly overtime: 6 x 8h = 48h
b8 = biz([emp(1, max_h=60)], [shift(i + 1, i, 8 * H, 16 * H + 30) for i in range(6)])
case("weekly overtime", ALL, b8, [a("E01", f"S{i + 1:02d}", meals=[11 * H]) for i in range(6)], "overtime_weekly")

# seventh day (California): 7 x 4h = 28h
b9 = biz([emp(1)], [shift(i + 1, i, 9 * H, 13 * H) for i in range(7)])
case("seventh day", ["california"], b9, [a("E01", f"S{i + 1:02d}") for i in range(7)], "seventh_day")
case("7 days fine outside CA", ["federal", "seattle"], b9, [a("E01", f"S{i + 1:02d}") for i in range(7)], None)

# Seattle rest gap: close 23:00 then open 07:00 = 8h gap
b10 = biz([emp(1)], [shift(1, 0, 19 * H, 23 * H), shift(2, 1, 7 * H, 11 * H)])
case("rest gap", ["seattle"], b10, [a("E01", "S01"), a("E01", "S02")], "rest_gap")
case("no rest-gap rule outside Seattle", ["federal", "california"], b10, [a("E01", "S01"), a("E01", "S02")], None)

# minors 14-15 (all rule sets)
b11 = biz([emp(1, age=15)], [shift(1, 5, 15 * H, 21 * H)])  # Saturday, ends 21:00
case("15yo after 7pm", ALL, b11, [a("E01", "S01", meals=[17 * H])], "minor_time")
b12 = biz([emp(1, age=15)], [shift(1, 1, 10 * H, 13 * H)])  # Tuesday during school
case("15yo during school", ALL, b12, [a("E01", "S01")], "minor_school_hours")
b13 = biz([emp(1, age=15)], [shift(1, 2, 15 * H, 19 * H)])  # Wed 4h after school
case("15yo over 3h school day", ALL, b13, [a("E01", "S01")], "minor_daily")
b14 = biz([emp(1, age=15)], [shift(i + 1, i, 15 * H + 30, 18 * H + 30) for i in range(5)] +
          [shift(6, 5, 9 * H, 17 * H + 30)])  # 15h + 8h = 23h
case("15yo over 18h school week", ALL, b14,
     [a("E01", f"S{i + 1:02d}") for i in range(5)] + [a("E01", "S06", meals=[12 * H])], "minor_weekly")
b15 = biz([emp(1, age=15)], [shift(1, 2, 15 * H + 30, 18 * H + 30)])
case("15yo legal evening shift", ALL, b15, [a("E01", "S01")], None)

# minors 16-17 (California only)
b16 = biz([emp(1, age=16)], [shift(1, 1, 16 * H, 23 * H)])  # Tue night before school, 7h
case("16yo past 10pm before school day", ["california"], b16, [a("E01", "S01", meals=[18 * H])], "minor_time")
case("16yo no limits under federal", ["federal", "seattle"], b16, [a("E01", "S01", meals=[18 * H])], None)
b17 = biz([emp(1, age=17)], [shift(1, 3, 15 * H + 30, 21 * H)])  # Thu 5.5h -> 5 worked w/ meal... over 4h
case("17yo over 4h school day", ["california"], b17, [a("E01", "S01", meals=[17 * H])], "minor_daily")
b18 = biz([emp(1, age=17)], [shift(1, 5, 14 * H, 23 * H)])  # Saturday until 23:00, before Sunday (non-school)
case("17yo Saturday until 11pm ok", ["california"], b18, [a("E01", "S01", meals=[16 * H])], "overtime_daily")


def main():
    fails = 0
    for name, rs, b, sched, expect in CASES:
        r = check(b, rs, copy.deepcopy(sched))
        kinds = {v["type"] for v in r["violations"]}
        ok = (not kinds) if expect is None else (expect in kinds)
        if not ok:
            fails += 1
            print(f"FAIL {name} [{rs}]: expected {expect}, got {sorted(kinds)}")
    print(f"{len(CASES) - fails}/{len(CASES)} grader checks passed")
    return fails


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
