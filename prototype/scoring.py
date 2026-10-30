"""
Generic eligibility, scoring and ranking engine (prototype). No AI, no network.

Everything category-specific is data in criteria_config.json (what an admin
edits on the criteria screens): mandatory checks, project limits, weighted
criteria and their scoring methods, tie-break order, explanation thresholds and
the extraction field list. This file contains no criterion names, proposal IDs
or contractor names.

Input : validated facts per proposal (in the full design: AI extraction output
        after schema validation, the quote check and reviewer confirmation).
        None means "not stated or unclear".
Output: status (ranked / flagged / ineligible), criterion scores, rank, and a
        rule-based reason from explain.py.

Rules applied, in order:
  1. A mandatory check or project limit that explicitly fails -> ineligible.
  2. One that cannot be checked, a security flag, or missing information on a
     criterion whose on_missing is "flag" -> flagged (no official score or rank).
  3. Otherwise ranked. Price and timeline benchmarks come from ranked bids only,
     so unresolved or ineligible bids cannot shift anyone's score.

Usage: python3 scoring.py [facts.json ...] [--config criteria_config.json] [--json] [--detail]
"""
import json
import os
import re
import sys
from decimal import Decimal, ROUND_HALF_UP
from string import Formatter

from explain import generate_reason

HERE = os.path.dirname(os.path.abspath(__file__))
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
SEVERITY = {"ranked": 0, "flagged": 1, "ineligible": 2}


def round_half_up(x, places):
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def check_one(c, v):
    """Return (outcome, message); outcome is 'pass', 'fail' or 'missing'."""
    kind = c["kind"]
    if kind == "enum":
        if v in c["pass"]:
            return "pass", None
        if v in c["fail"]:
            return "fail", c["fail"][v]
        return "missing", c["missing"]
    if v is None:
        return "missing", c["missing"]
    if kind == "boolean":
        return ("pass", None) if v else ("fail", c["fail"])
    if kind == "min_number":
        return ("pass", None) if v >= c["min"] else ("fail", c["fail"])
    if kind == "max_number":
        return ("pass", None) if v <= c["max"] else ("fail", c["fail"])
    raise ValueError(f"unknown check kind: {kind}")


def period_within(text, as_of_year, years):
    """True if the stated period lies inside the window, False if it may reach
    outside it, None if the wording cannot be interpreted (a person must check)."""
    if not text:
        return None
    t = text.lower()
    m = re.search(r"since\s+(\d{4})", t)
    if m:
        return int(m.group(1)) >= as_of_year - years
    m = re.search(r"(?:last|past)\s+(\w+)\s+years?", t)
    if m:
        g = m.group(1)
        n = int(g) if g.isdigit() else NUMBER_WORDS.get(g)
        if n is not None:
            return n <= years
    return None


def fill(template, values):
    names = [n for _, n, _, _ in Formatter().parse(template) if n]
    if any(values.get(n) is None for n in names):
        return "not stated"
    return template.format(**values)


def item_state(v):
    if v is None:
        return "unknown"
    if v is True or (isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0):
        return "yes"
    return "no"


def missing_reason(cfg, c, p):
    """None if the criterion has what it needs, otherwise a short plain-language reason."""
    m = c["method"]
    if m in ("capped_linear", "ratio_to_best"):
        if p.get(c["fact"]) is None:
            return f"{c['label']}: not stated"
        w = c.get("window")
        if w:
            text = p.get(w["period_fact"])
            ok = period_within(text, cfg["as_of_year"], w["years"])
            if ok is None:
                return f"{c['label']}: the time period is not clear, so the {w['years']}-year window cannot be checked"
            if ok is False:
                return (f"{c['label']}: the period \"{text}\" reaches beyond the {w['years']}-year window, "
                        f"so the qualifying count cannot be confirmed")
        return None
    if m == "capped_average":
        gaps = [f["label"] for f in c["facts"] if p.get(f["fact"]) is None]
        return f"{c['label']}: not stated ({', '.join(gaps)})" if gaps else None
    if m == "checklist":
        gaps = [it["label"] for it in c["items"] if p.get(it["fact"]) is None]
        return f"{c['label']}: not stated ({', '.join(gaps)})" if gaps else None
    raise ValueError(f"unknown scoring method: {m}")


def score_criterion(c, p, bests):
    """Return (score 0-100, missing_info, detail). Missing information scores 0, never guessed."""
    m = c["method"]
    values = {**p, "best": bests.get(c.get("fact"))}
    if m == "capped_linear":
        v = p.get(c["fact"])
        if v is None:
            return 0.0, True, "not stated"
        return 100 * min(v / c["full_marks"], 1), False, fill(c["detail"], values)
    if m == "ratio_to_best":
        v = p.get(c["fact"])
        if not v:
            return 0.0, True, "not stated"
        best = bests[c["fact"]]
        ratio = best / v if c.get("lower_is_better", True) else v / best
        return 100 * min(ratio, 1), False, fill(c["detail"], values)
    if m == "capped_average":
        parts = [min((p.get(f["fact"]) or 0) / f["full_marks"], 1) for f in c["facts"]]
        missing = any(p.get(f["fact"]) is None for f in c["facts"])
        return 100 * sum(parts) / len(parts), missing, fill(c["detail"], values)
    if m == "checklist":
        states = [(it["label"], item_state(p.get(it["fact"]))) for it in c["items"]]
        score = 100 * sum(s == "yes" for _, s in states) / len(states)
        groups = [("has", "yes"), ("not stated", "unknown"), ("stated absent", "no")]
        detail = "; ".join(f"{title}: " + ", ".join(lbl for lbl, s in states if s == key)
                           for title, key in groups if any(s == key for _, s in states))
        return score, any(s == "unknown" for _, s in states), detail
    raise ValueError(f"unknown scoring method: {m}")


def validate_config(cfg):
    total = sum(c["weight"] for c in cfg["criteria"])
    if total != 100:
        raise ValueError(f"weights must total 100 (got {total})")


def run(cfg, facts):
    validate_config(cfg)
    results = {}
    for k, p in facts.items():
        r = {"id": k, "status": "ranked", "blocking": [], "notes": [], "criteria": None,
             "total": None, "rank": None, "tied": False,
             "checks_total": len(cfg["mandatory_checks"]), "limits_total": len(cfg.get("project_limits", []))}

        def mark(status, msg, r=r):
            if SEVERITY[status] > SEVERITY[r["status"]]:
                r["status"] = status
            r["blocking"].append(msg)

        for c in cfg["mandatory_checks"] + cfg.get("project_limits", []):
            outcome, msg = check_one(c, p.get(c["fact"]))
            if outcome == "fail":
                mark("ineligible", msg)
            elif outcome == "missing":
                mark("flagged", msg)
        if r["status"] != "ineligible":
            if p.get("security_flag"):
                mark("flagged", cfg["security_flag_message"])
            limit_facts = {c["fact"] for c in cfg.get("project_limits", [])}
            for c in cfg["criteria"]:
                if c.get("fact") in limit_facts and p.get(c["fact"]) is None:
                    continue                     # already reported by the project limit
                why = missing_reason(cfg, c, p)
                if why and c.get("on_missing", "flag") == "flag":
                    mark("flagged", why)
        results[k] = r

    ranked = [k for k, r in results.items() if r["status"] == "ranked"]
    bests = {}
    for c in cfg["criteria"]:
        if c["method"] == "ratio_to_best":
            vals = [facts[k][c["fact"]] for k in ranked]
            if vals:
                bests[c["fact"]] = min(vals) if c.get("lower_is_better", True) else max(vals)
    for k in ranked:
        rows = []
        for c in cfg["criteria"]:
            score, missing, detail = score_criterion(c, facts[k], bests)
            rows.append({"id": c["id"], "label": c["label"], "weight": c["weight"], "score": score,
                         "points": score * c["weight"] / 100, "missing_info": missing, "detail": detail})
        results[k]["criteria"] = rows
        results[k]["total"] = round_half_up(sum(r["points"] for r in rows), cfg.get("rounding", 1))

    def key(k):
        out = []
        for t in cfg["tie_break"]:
            if t["by"] == "total":
                out.append(-results[k]["total"])
            elif t["by"] == "score":
                out.append(-round(next(r["score"] for r in results[k]["criteria"] if r["id"] == t["id"]), 6))
            else:
                v = facts[k].get(t["name"])
                v = float("inf") if v is None else v
                out.append(v if t.get("order", "asc") == "asc" else -v)
        return tuple(out)

    order = sorted(ranked, key=lambda k: (key(k), k))
    for i, k in enumerate(order):
        same_as_prev = i > 0 and key(order[i - 1]) == key(k)
        results[k]["rank"] = results[order[i - 1]]["rank"] if same_as_prev else i + 1
        results[k]["tied"] = same_as_prev or (i + 1 < len(order) and key(order[i + 1]) == key(k))
        results[k]["ranked_count"] = len(order)
    return results


def to_ranking(cfg, results):
    keys = sorted(results, key=lambda k: (SEVERITY[results[k]["status"]], results[k]["rank"] or 10**9, k))
    return [{"proposal": k, "rank": results[k]["rank"], "status": results[k]["status"],
             "score": results[k]["total"],
             "reason": generate_reason(results[k], cfg.get("explanation"))} for k in keys]


def load(path):
    with open(path) as f:
        return json.load(f)


def main(argv):
    cfg_path = os.path.join(HERE, "criteria_config.json")
    if "--config" in argv:
        i = argv.index("--config")
        cfg_path = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    paths = [a for a in argv if not a.startswith("--")] or [os.path.join(HERE, "sample_facts.json")]
    cfg = load(cfg_path)
    facts = {}
    for pth in paths:
        facts.update(load(pth))
    results = run(cfg, facts)
    ranking = to_ranking(cfg, results)
    if "--json" in argv:
        print(json.dumps(ranking, indent=2))
        return
    for row in ranking:
        print(f"{row['proposal']}: rank={row['rank']} status={row['status']} score={row['score']}")
        print("   ", row["reason"])
        if "--detail" in argv and results[row["proposal"]]["criteria"]:
            for c in results[row["proposal"]]["criteria"]:
                print(f"      {c['label']:<20} {c['score']:6.1f} x {c['weight']}% = {c['points']:5.2f}   {c['detail']}")
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
