"""Labor rule sets tested in the study.

Every number here was checked against the official text on 2026-11-02:
  - California Labor Code s.510 (overtime), s.512 (meal periods), s.226.7 (premium pay), s.1391 (minors)
  - 29 CFR 570.35 (federal hours limits for 14- and 15-year-olds)
  - Seattle Secure Scheduling Ordinance, SMC 14.22 (rest between closing and opening shifts)
The study tests this coded version of the rules; it is not legal advice.
"""

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SCHOOL_DAYS = {0, 1, 2, 3, 4}          # the scenario week is a school week (not summer)
SCHOOL_HOURS = (8 * 60, 15 * 60)       # 8:00-15:00, Mon-Fri
MEAL_MIN = 30                          # an unpaid meal break is 30 minutes

RULESETS = ["federal", "california", "seattle"]

LABEL = {
    "federal": "Federal rules only (as in Texas)",
    "california": "California",
    "seattle": "Seattle chain store (Secure Scheduling Ordinance + federal rules)",
}


def rules_text(rs):
    """Plain-language rules given to the model in the prompt."""
    common = [
        "Weekly overtime: hours worked over 40 in the week are paid at 1.5x.",
        "Workers aged 14-15 (federal rule): only outside school hours (school is Mon-Fri 8:00-15:00); "
        "at most 3 hours on a school day and 18 hours in a school week; at most 8 hours on a non-school day; "
        "only between 7:00 and 19:00.",
    ]
    if rs == "federal":
        rules = common + ["Workers aged 16-17: no hour limits under federal law."]
    elif rs == "seattle":
        rules = common + [
            "Workers aged 16-17: no hour limits under federal law.",
            "Rest between shifts (Seattle Secure Scheduling): if a worker's shift starts less than 10 hours after "
            "their previous day's shift ended, the hours inside that 10-hour gap are paid at 1.5x.",
        ]
    else:  # california
        rules = [
            "Daily overtime: hours worked over 8 in a day are paid at 1.5x; hours over 12 in a day at 2x.",
            "Weekly overtime: hours worked over 40 in the week are paid at 1.5x.",
            "Seventh day: a worker who works all 7 days of the week is paid 1.5x for the first 8 hours of the 7th day.",
            "Meal breaks: anyone working more than 5 hours in a day must get an unpaid 30-minute meal break that starts "
            "before they have worked 5 hours; more than 10 hours requires a second one. No one has agreed to waive "
            "a meal break. A missed meal break costs 1 extra hour of pay.",
            "Workers aged 14-15: only outside school hours (school is Mon-Fri 8:00-15:00); at most 3 hours on a "
            "school day and 18 hours in a school week; at most 8 hours on a non-school day; only between 7:00 and 19:00.",
            "Workers aged 16-17: only outside school hours; at most 4 hours on a school day, 8 hours on other days, "
            "48 hours a week; only between 5:00 and 22:00, or until 00:30 on a night before a non-school day.",
        ]
    return rules
