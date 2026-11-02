"""Scenario generator: fictional small businesses, their staff and the week's shifts.

Everything is built from a fixed seed, so every scenario can be rebuilt exactly.
"""
import json
import random

from rules import DAYS

SEED = 2026
N_BUSINESSES = 600

FIRST = ["Ana", "Ben", "Carla", "Dev", "Eli", "Fatima", "Gabe", "Hana", "Ivan", "Jada", "Kai", "Lena",
         "Marco", "Nia", "Omar", "Priya", "Quinn", "Rosa", "Sam", "Tara", "Uma", "Victor", "Wren", "Xavi",
         "Yara", "Zoe", "Alex", "Bea", "Cole", "Dina"]

# business type: (open, close) in minutes, shift templates (name, start, end), main role
TYPES = {
    "cafe":   dict(hours=(6 * 60, 21 * 60), role="barista",
                   shifts=[("open", 6 * 60, 14 * 60 + 30), ("mid", 10 * 60, 16 * 60), ("close", 12 * 60 + 30, 21 * 60)]),
    "retail": dict(hours=(9 * 60, 22 * 60), role="sales",
                   shifts=[("open", 9 * 60, 17 * 60 + 30), ("mid", 12 * 60, 18 * 60), ("close", 13 * 60 + 30, 22 * 60)]),
    "quick-service restaurant": dict(hours=(7 * 60, 23 * 60), role="crew",
                   shifts=[("open", 7 * 60, 15 * 60 + 30), ("mid", 11 * 60, 16 * 60), ("close", 14 * 60 + 30, 23 * 60)]),
}
EVENING = ("evening", 15 * 60 + 30, 18 * 60 + 30)   # short shift, levels 3+

LEVELS = {1: (4, 6), 2: (7, 10), 3: (11, 15), 4: (16, 20), 5: (21, 25)}


def hm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def make_business(i, rng):
    level = 1 + i % 5
    btype = rng.choice(sorted(TYPES))
    T = TYPES[btype]
    n = rng.randint(*LEVELS[level])
    open_, close = T["hours"]
    role = T["role"]
    use_lead = level >= 2

    # --- staff
    staff = []
    n_minor = 0 if level < 3 else rng.randint(1, 3)
    names = rng.sample(FIRST, n)
    for k in range(n):
        minor = k >= n - n_minor
        age = rng.choice([15, 16, 17]) if minor else rng.randint(18, 60)
        roles = [role]
        if use_lead and not minor and rng.random() < 0.4:
            roles.append("shift lead")
        wage = rng.choice([17, 18, 19, 20, 21, 22, 23, 24]) + (2 if "shift lead" in roles else 0)
        max_h = rng.choice([12, 16, 20, 24]) if minor else rng.choice([16, 24, 32, 40, 40])
        staff.append(dict(id=f"E{k + 1:02d}", name=names[k], age=age, roles=roles, wage=wage, max_hours=max_h))
    if use_lead and sum("shift lead" in s["roles"] for s in staff) < 3:
        for s in staff:
            if s["age"] >= 18 and "shift lead" not in s["roles"]:
                s["roles"].append("shift lead")
                s["wage"] += 2
            if sum("shift lead" in x["roles"] for x in staff) >= 3:
                break

    # --- availability: per day a window (start, end) or None
    tight = level == 5
    for s in staff:
        av = []
        for d in range(7):
            if s["age"] < 18 and d < 5:
                # minors say they're free after school; some say evenings late (a trap for minor-hour rules)
                av.append([15 * 60 + 30, close] if rng.random() < 0.75 else None)
                continue
            r = rng.random()
            off = 0.35 if tight else 0.2
            if r < off:
                av.append(None)
            elif r < off + 0.25:
                av.append([open_, 14 * 60 + 30 + (open_ - 6 * 60) if btype != "cafe" else 14 * 60 + 30])
            elif r < off + 0.5:
                av.append([10 * 60 if btype == "cafe" else 11 * 60, close])
            else:
                av.append([open_, close])
        s["availability"] = av

    # --- shifts and coverage
    from solver import allowed, worked
    templates = {t[0]: t for t in T["shifts"]}
    if level >= 3:
        templates["evening"] = EVENING
    lead_role = "shift lead" if use_lead else role

    def mk(d, name):
        _, st, en = templates[name]
        return dict(day=d, name=name, start=st, end=en)

    # Coverage is built from a hidden schedule that follows every rule of every rule set at once
    # (California + Seattle + minors). So each business has at least one legal schedule under all
    # three rule sets, unless an impossibility is planted below on purpose.
    hours = {e["id"]: 0 for e in staff}
    works = {e["id"]: {} for e in staff}  # day -> shift dict

    def can(e, s, r):
        if r not in e["roles"] or s["day"] in works[e["id"]]:
            return False
        if not all(allowed(e, s, rs) for rs in ("federal", "california", "seattle")):
            return False
        cap = min(e["max_hours"], 40)
        if e["age"] <= 15:
            cap = min(cap, 18)
        if hours[e["id"]] + worked(s) / 60 > cap:
            return False
        if len(works[e["id"]]) >= 6:
            return False
        prev, nxt = works[e["id"]].get(s["day"] - 1), works[e["id"]].get(s["day"] + 1)
        if prev and s["start"] + 1440 - prev["end"] < 600:
            return False
        if nxt and nxt["start"] + 1440 - s["end"] < 600:
            return False
        return True

    def take(e, s):
        hours[e["id"]] += worked(s) / 60
        works[e["id"]][s["day"]] = s

    supply = sum(min(e["max_hours"], 40) for e in staff)
    ratio = rng.uniform(0.65, 0.8) if level == 5 else rng.uniform(0.5, 0.7)
    slots = {}
    # every day: open and close each get one lead if one can be found
    for d in range(7):
        for nm in ("open", "close"):
            s = mk(d, nm)
            cands = [e for e in staff if can(e, s, lead_role)]
            if cands:
                e = rng.choice(cands)
                take(e, s)
                slots[(d, nm)] = {lead_role: 1}
    names = [nm for nm in templates if not (nm == "mid" and level == 1)]
    used = sum(hours.values())
    for _ in range(600):
        if used >= ratio * supply:
            break
        d, nm = rng.randrange(7), rng.choice(names)
        s = mk(d, nm)
        nd = slots.setdefault((d, nm), {})
        if sum(nd.values()) >= 4:
            continue
        cands = [e for e in staff if can(e, s, role)]
        if not cands:
            if not nd:
                del slots[(d, nm)]
            continue
        e = rng.choice(cands)
        take(e, s)
        nd[role] = nd.get(role, 0) + 1
        used = sum(hours.values())

    # --- planted impossibility for about 1 in 5 businesses: more lead (or staff) hours needed
    # than the people who hold that role are allowed to work
    trap = rng.random() < 0.22
    if trap:
        holders = [e for e in staff if lead_role in e["roles"]]
        need_h = sum(worked(mk(d, nm)) * nd.get(lead_role, 0) for (d, nm), nd in slots.items()) / 60
        def cap():
            return sum(min(e["max_hours"], 40) for e in holders)
        while cap() >= need_h:
            cut = [e for e in holders if e["max_hours"] > 8]
            if not cut:
                break
            e = max(cut, key=lambda x: x["max_hours"])
            e["max_hours"] -= 4
        trap = cap() < need_h

    shifts = []
    order = list(templates)
    for (d, nm) in sorted(slots, key=lambda k: (k[0], order.index(k[1]))):
        nd = {k: v for k, v in slots[(d, nm)].items() if v > 0}
        s = mk(d, nm)
        shifts.append(dict(id=f"S{len(shifts) + 1:02d}", need=nd, **s))

    return dict(business_id=f"B{i + 1:03d}", level=level, type=btype, planted_trap=trap,
                hours=[open_, close], staff=staff, shifts=shifts)


def generate():
    rng = random.Random(SEED)
    return [make_business(i, rng) for i in range(N_BUSINESSES)]


# ---------------- messy messages (template-built, so they carry exactly the table's information)

def _fmt_t(m):
    h, mi = divmod(m, 60)
    suf = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}{'' if mi == 0 else f':{mi:02d}'}{suf}"


def availability_message(s, rng):
    groups = {}
    for d, w in enumerate(s["availability"]):
        groups.setdefault(tuple(w) if w else None, []).append(d)
    parts = []
    for w, ds in sorted(groups.items(), key=lambda kv: kv[1][0]):
        days = "/".join(DAYS[d] for d in ds)
        if w is None:
            parts.append(rng.choice(["can't do {d}", "no {d} for me", "I'm out {d}"]).format(d=days))
        else:
            parts.append(rng.choice(["{d} {a}-{b} works", "free {d} from {a} to {b}", "{d}: {a}-{b}"]).format(
                d=days, a=_fmt_t(w[0]), b=_fmt_t(w[1])))
    opener = rng.choice(["Hey! ", "Hi, ", "", "Quick update - "])
    return opener + "; ".join(parts) + rng.choice([".", "!", " thx", ""])


def parse_message(msg):
    """Round-trip check: rebuild the availability from a message."""
    import re
    av = [None] * 7

    def t(x):
        m = re.fullmatch(r"(\d+)(?::(\d+))?(am|pm)", x)
        h, mi, suf = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        h = h % 12 + (12 if suf == "pm" else 0)
        return h * 60 + mi
    for days, a, b in re.findall(r"((?:[A-Z][a-z]{2}/?)+)(?: |: | from )(\d[\d:]*[ap]m)(?:-| to )(\d[\d:]*[ap]m)", msg):
        for d in days.split("/"):
            av[DAYS.index(d)] = [t(a), t(b)]
    return av


if __name__ == "__main__":
    bs = generate()
    rng = random.Random(SEED + 1)
    bad = 0
    for b in bs:
        for s in b["staff"]:
            s["message"] = availability_message(s, rng)
            if parse_message(s["message"]) != s["availability"]:
                bad += 1
    json.dump(bs, open("scenarios/businesses.json", "w"), indent=1)
    print("businesses", len(bs), "round-trip failures", bad)
