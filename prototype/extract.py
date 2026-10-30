"""
Extraction step: builds the exact prompt shown in PROMPTS.md, optionally sends
it to a model, then validates the reply in code before anything is scored.

Proposal text is NOT stored in this repository (the brief asks candidates not to
copy it). To try the prompt, save each proposal as plain text in
prototype/proposals/<letter>.txt on your own machine; that folder is git-ignored.
Use a form-feed character (\f) between pages if a document has several pages.

Usage
  python3 extract.py proposals/B.txt --id B --print
      Print the system and user messages, to paste into any chat tool by hand.
  python3 extract.py proposals/B.txt --id B --reply reply_B.json
      Validate a reply you saved, and print the facts that scoring.py would use.
  python3 extract.py proposals/B.txt --id B --call
      Call the model API (needs ANTHROPIC_API_KEY and MODEL in a .env file;
      see .env.example), save the reply to outputs/, then validate it.

Validation (all in code, nothing is taken on trust from the model):
  - exact top-level keys, exactly the configured field names, exactly the four
    keys per field, allowed status values, correct value types;
  - every evidence quote and security-flag quote must appear word for word in
    the source text (whitespace-normalised), and pages must be in range;
  - a field that fails any check is dropped (treated as not stated) and reported.
A separate pattern scan looks for wording aimed at automated reviewers. It is a
warning signal only and cannot catch every manipulation attempt.
"""
import argparse
import json
import os
import re
import secrets
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATUSES = {"confirmed", "not_stated", "ambiguous", "conflicting"}
FIELD_KEYS = {"value", "status", "evidence", "page"}
TOP_KEYS = {"proposal_id", "fields", "security_flags"}
WARNING_PATTERNS = [
    r"automated\s+(review|reviewer|reviewing|system|systems|tool|tools)",
    r"ignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+instructions",
    r"\brank\s+(it|this|us|this\s+proposal)\b[^.]{0,30}\bfirst\b",
    r"\b(full|maximum|top)\s+(marks|score|points)\b",
    r"\bpre-?approved\b",
    r"\b(system|developer)\s+(prompt|message)\b",
]


def load_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_config():
    with open(os.path.join(HERE, "criteria_config.json")) as f:
        return json.load(f)


def field_definitions(cfg):
    return "\n".join(f"{f['name']}: {f['definition']}" for f in cfg["extraction_fields"])


def add_page_markers(text):
    pages = text.split("\f")
    body = "\n".join(f"[[PAGE {i}]]\n{p.strip()}" for i, p in enumerate(pages, 1))
    return body, len(pages)


def build_messages(cfg, proposal_id, text, code=None):
    """Return (system, user, page_count). The random code makes the tag names
    unguessable; any copy of the code inside the document is removed first."""
    code = code or secrets.token_hex(6)
    text = re.sub(re.escape(code), "[removed]", text, flags=re.IGNORECASE)
    body, pages = add_page_markers(text)
    system = load_text(os.path.join(HERE, "prompts", "extraction_system.txt"))
    user = load_text(os.path.join(HERE, "prompts", "extraction_user_template.txt"))
    user = (user.replace("{{category_name}}", cfg["category"])
                .replace("{{field_definitions}}", field_definitions(cfg))
                .replace("{{proposal_id}}", proposal_id)
                .replace("{{random_code}}", code)
                .replace("{{proposal_text_with_PAGE_markers}}", body))   # last, so document text is never substituted
    return system, user, pages


def _norm(s):
    return " ".join(s.split())


def pattern_scan(text):
    return [m.group(0) for p in WARNING_PATTERNS for m in re.finditer(p, text, flags=re.IGNORECASE)]


def _type_ok(field, v):
    t = field["type"]
    if t == "enum":
        return v in field["values"]
    if v is None:
        return True
    if t == "string":
        return isinstance(v, str)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0
    if t == "boolean":
        return isinstance(v, bool)
    return False


def validate(cfg, reply, source_text, page_count):
    """Return (errors_by_field, general_errors). Empty means the reply passed."""
    errors, general = {}, []
    source = _norm(source_text)
    if not isinstance(reply, dict):
        return {}, ["reply is not a JSON object"]
    if set(reply) != TOP_KEYS:
        general.append(f"top-level keys must be exactly {sorted(TOP_KEYS)}, got {sorted(reply)}")
    fields = reply.get("fields") if isinstance(reply.get("fields"), dict) else {}
    expected = {f["name"]: f for f in cfg["extraction_fields"]}
    for extra in sorted(set(fields) - set(expected)):
        general.append(f"unexpected field: {extra}")
    for name, spec in expected.items():
        e = []
        item = fields.get(name)
        if not isinstance(item, dict):
            errors[name] = ["missing"]
            continue
        if set(item) != FIELD_KEYS:
            e.append(f"keys must be exactly {sorted(FIELD_KEYS)}")
        status, value, ev, page = item.get("status"), item.get("value"), item.get("evidence"), item.get("page")
        if status not in STATUSES:
            e.append(f"invalid status {status!r}")
        if not _type_ok(spec, value):
            e.append(f"wrong type or value {value!r}")
        if spec["type"] != "enum" and status != "confirmed" and value is not None:
            e.append("value must be null unless status is confirmed")
        if ev is not None:
            if not isinstance(ev, str) or _norm(ev) not in source:
                e.append("evidence quote not found in the source text")
        elif status == "confirmed":
            e.append("confirmed value has no evidence quote")
        if page is not None and not (isinstance(page, int) and not isinstance(page, bool) and 1 <= page <= page_count):
            e.append(f"page {page!r} out of range")
        if e:
            errors[name] = e
    flags = reply.get("security_flags")
    if not isinstance(flags, list):
        general.append("security_flags must be a list")
    else:
        for fl in flags:
            if not isinstance(fl, dict) or not isinstance(fl.get("quote"), str) or _norm(fl["quote"]) not in source:
                general.append("security flag quote not found in the source text")
    return errors, general


def to_facts(cfg, reply, errors, source_text):
    """Facts for scoring.py. Anything unconfirmed or failing validation becomes None
    (or 'not_stated' for enum fields), so it can never pass a check by accident."""
    facts = {}
    fields = reply.get("fields", {}) if isinstance(reply, dict) else {}
    for spec in cfg["extraction_fields"]:
        item = fields.get(spec["name"]) or {}
        ok = spec["name"] not in errors and item.get("status") == "confirmed"
        if spec["type"] == "enum":
            facts[spec["name"]] = item.get("value") if ok else "not_stated"
        else:
            facts[spec["name"]] = item.get("value") if ok else None
    model_flags = reply.get("security_flags") if isinstance(reply, dict) else None
    facts["security_flag"] = bool(model_flags) or bool(pattern_scan(source_text))
    return facts


def load_env(path):
    if not os.path.exists(path):
        return
    for line in load_text(path).splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def call_model(system, user):
    load_env(os.path.join(HERE, "..", ".env"))
    if not os.environ.get("ANTHROPIC_API_KEY") or not os.environ.get("MODEL"):
        sys.exit("Set ANTHROPIC_API_KEY and MODEL in .env (see .env.example), or use --print instead.")
    import anthropic                                  # pip install anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(model=os.environ["MODEL"], max_tokens=4000, temperature=0,
                                 system=system, messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proposal_file")
    ap.add_argument("--id", required=True, help="proposal ID, for example B")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--print", action="store_true", help="print the messages to send")
    mode.add_argument("--reply", help="path to a saved model reply (JSON) to validate")
    mode.add_argument("--call", action="store_true", help="call the model API, then validate")
    a = ap.parse_args()

    cfg = load_config()
    text = load_text(a.proposal_file)
    system, user, pages = build_messages(cfg, a.id, text)
    if a.print:
        print("===== SYSTEM MESSAGE =====\n" + system + "\n===== USER MESSAGE =====\n" + user)
        return
    if a.call:
        raw = call_model(system, user)
        os.makedirs(os.path.join(HERE, "outputs"), exist_ok=True)
        out = os.path.join(HERE, "outputs", f"{a.id}.reply.json")
        with open(out, "w", encoding="utf-8") as f:
            f.write(raw)
        print(f"raw reply saved to {out}", file=sys.stderr)
    else:
        raw = load_text(a.reply)
    try:
        reply = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"reply is not valid JSON: {exc}")
    errors, general = validate(cfg, reply, text, pages)
    for g in general:
        print(f"[invalid] {g}", file=sys.stderr)
    for name, errs in errors.items():
        print(f"[invalid] {name}: {'; '.join(errs)} (dropped)", file=sys.stderr)
    hits = pattern_scan(text)
    if hits:
        print(f"[warning] pattern scan matched: {hits}", file=sys.stderr)
    print(json.dumps({a.id: to_facts(cfg, reply, errors, text)}, indent=1))


if __name__ == "__main__":
    main()
