# MATACS-TH-2026-02: AI Proposal Triage Design

**Name:** Areeba Khan
**Reference:** MATACS-TH-2026-02
**Time actually spent:** [FILL IN: your real total, for example "about X hours over Y sessions"]

## Files
- [WRITEUP.md](WRITEUP.md): answers to the five questions, assumptions, and results on the sample set
- [PROMPTS.md](PROMPTS.md): the extraction prompt (the only AI prompt), exactly as sent
- [ranking.json](ranking.json): expected ranking of proposals A to E
- [diagram/process_flow.png](diagram/process_flow.png): process flow with AI steps, rule steps and human checkpoints
- [prototype/](prototype/) (optional):
  - [scoring.py](prototype/scoring.py): eligibility checks, scoring and ranking, driven by config
  - [explain.py](prototype/explain.py): rule-based one-line reasons
  - [extract.py](prototype/extract.py): builds the exact prompt, optionally calls the model, validates the reply
  - [criteria_config.json](prototype/criteria_config.json): the admin's criteria for this category, as data
  - [sample_facts.json](prototype/sample_facts.json): my reading of the facts in proposals A to E (values only, no proposal text)
  - [new_proposal_example.json](prototype/new_proposal_example.json): a made-up extra proposal, to show no code change is needed
  - [test_prototype.py](prototype/test_prototype.py): tests for the code above
  - [prompts/](prototype/prompts/): the prompt files the code sends

## Summary
AI extracts facts with quotes; this is the only AI step. Code validates the facts, decides eligibility, scores, ranks and writes the reasons, all using admin-set criteria. People confirm facts, resolve flags, override with a reason, and make the award.

## Running the prototype
Requires Python 3.9 or later. No packages are needed except for `--call`.

```
python3 prototype/scoring.py --detail     # ranking with per-criterion breakdown
python3 prototype/scoring.py --json       # produces ranking.json
python3 prototype/test_prototype.py       # runs the tests
```

To try the prompt, save a proposal as plain text in `prototype/proposals/` (git-ignored, because the brief asks not to copy proposal text into the repository). Then do either of the following:

- **By hand:** run `python3 prototype/extract.py prototype/proposals/B.txt --id B --print`. Paste the messages into a chat tool, save the reply, and validate it with `--reply reply.json`.
- **Through the API:** copy `.env.example` to `.env`, add a key, run `pip install anthropic`, then use `--call`.

## What is and is not built
- **Built and tested:** eligibility checks, scoring, ranking, the reasons, prompt construction, and validation of a model's reply.
- **Design only:** PDF text extraction and OCR, the database and audit log, the review screens, and versioning.
- **Tested by hand:** the prompt on proposals B, C and D through a chat interface. Results and the change it led to are in the Test log in PROMPTS.md.

## How I used AI tools
[FILL IN with 2 to 3 true sentences in your own words: which AI tool(s) you used and for what, what you checked or rewrote yourself, and at least one specific place where you disagreed with or corrected the AI and why.]
