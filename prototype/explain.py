"""
Generic, deterministic explanation generator. No AI.

It reads only the generic result built by the scoring engine: status, rank,
total, blocking reasons, notes, and one entry per configured criterion (label,
score, weight, points, detail, missing-information flag). It contains no
proposal IDs, contractor names or criterion names, so new proposals and new
categories need no change here. Every number it prints is copied from that
result, and tests check this.
"""

DEFAULTS = {"strong_at": 80, "weak_below": 50, "max_items": 3}


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _passed(r):
    n, m = r["checks_total"], r.get("limits_total", 0)
    def words(k, noun):
        return f"the {noun}" if k == 1 else f"both {noun}s" if k == 2 else f"all {k} {noun}s"
    text = "Passed " + words(n, "mandatory check")
    if m:
        text += " and " + words(m, "project limit")
    return text + "."


def _area(c):
    return f"{c['label']} {c['score']:.0f}/100 ({c['detail']})"


def _list(title, items, limit, empty_text):
    if not items:
        return empty_text
    text = f"{title}: " + "; ".join(_area(c) for c in items[:limit])
    if len(items) > limit:
        text += f"; plus {_plural(len(items) - limit, 'more area')}"
    return text + "."


def generate_reason(r, settings=None):
    s = {**DEFAULTS, **(settings or {})}
    if r["status"] == "ineligible":
        return "Ineligible: " + "; ".join(r["blocking"]) + "."
    if r["status"] == "flagged":
        return "Not ranked until a reviewer resolves: " + "; ".join(r["blocking"]) + "."

    tied = " (tied)" if r.get("tied") else ""
    text = f"Ranked {r['rank']} of {r['ranked_count']}{tied}, score {r['total']:g}/100. {_passed(r)}"
    crit = r["criteria"]
    strong = sorted((c for c in crit if c["score"] >= s["strong_at"] and not c["missing_info"]),
                    key=lambda c: (-c["points"], c["label"]))
    weak = sorted((c for c in crit if c["score"] < s["weak_below"] or c["missing_info"]),
                  key=lambda c: (-(c["weight"] - c["points"]), c["label"]))
    text += " " + _list("Strongest areas", strong, s["max_items"], f"No criterion scored {s['strong_at']} or above.")
    text += " " + _list("Weak or incomplete areas", weak, s["max_items"], "No weak or incomplete areas.")
    if r.get("notes"):
        text += " Notes: " + "; ".join(r["notes"]) + "."
    return text
