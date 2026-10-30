# MATACS-TH-2026-02: AI Proposal Triage Design

**Name:** Areeba Khan
**Reference:** MATACS-TH-2026-02
**Time actually spent:** **Time actually spent:** Approximately 2.5 hours across design, architecture planning, prompt development, prototype implementation, testing with sample proposals, debugging, refining validation rules, and preparing the final documentation and submission files.

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

I used Claude Opus 5.5 as a design assistant to help draft the workflow, prompts, write-up and prototype. In a separate chat, I used Claude Sonnet 5.5 (Medium) to test the extraction prompt on proposals B, C and D. I reviewed the files, ran the tests myself and checked the outputs against the proposal content.

I also challenged and corrected several AI suggestions. When it proposed fixed reason templates, I required a generic explanation generator that could work across different proposals. When it blocked Proposal C's ranking because of an embedded instruction, I changed the approach to log the instruction as a security note rather than let it affect scoring, since the AI does not control the scoring logic. I also identified inconsistent treatment of A and E ("since 2021") versus C ("since 2020"), which led me to define an explicit, administrator-configurable boundary-year rule. Finally, my prompt testing showed that the definition of "named project lead" was too strict for C and D, so I revised the definition and re-tested the extraction.