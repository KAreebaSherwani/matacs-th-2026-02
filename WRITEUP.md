# Design write-up: MATACS-TH-2026-02

**In one line:** AI extracts facts with quotes. Code validates, checks eligibility, scores, ranks and writes reasons. People confirm, override and award.

## Assumptions (the brief does not say)
- **Hard limits:** a price over $260,000 or a schedule over 16 weeks is ineligible. A missing price or schedule is flagged, because the limit cannot be checked.
- **Licence:** must be held by the bidder. Work assigned to a subcontractor does not demonstrate this, so the proposal is ineligible (a reviewer can override). A licence not mentioned at all is flagged as a possible omission.
- **Five-year window, counted by year:** for 2026, "since 2021" is inside it. "Since 2020" may include older installs, so the count cannot be confirmed and the proposal is flagged.
- **Reference values:** 12 installs, 25-year panel and 12-year workmanship warranties earn full marks (admin-editable defaults).

## 1. AI vs. rules
**AI does one job:** read the proposal text and extract facts into a fixed JSON form, each with a word-for-word quote and page number.

**Code does everything else:**
- file checks, text extraction (OCR for scans) and loading the admin's criteria;
- validating the AI's reply;
- mandatory checks, project limits and the five-year window;
- scoring, ranking and tie-breaks;
- writing the reasons and the audit log.

**Why this line:** AI copes with varied wording but is weak at repeatability and arithmetic. Anything that decides a position must be repeatable and explainable, so it is code. The AI never outputs a score or reason.

## 2. Consistency and explainability
- **Fixed formulas**, stored as admin settings:
  - experience = installs ÷ 12, capped at 100;
  - price = lowest ranked price ÷ this price;
  - timeline = fewest ranked weeks ÷ this bid's weeks;
  - warranty = average of panel ÷ 25 and workmanship ÷ 12 (each capped);
  - team = 25 points per item stated (named lead, crew, safety plan, monitoring).
- **Missing information is never guessed.** If experience, warranty, price or timeline is missing, the proposal is flagged. An unstated team item scores 0 and is listed in the reason.
- **Benchmarks use ranked bids only**, so unresolved or ineligible bids cannot shift other scores.
- **Repeat runs:** temperature 0 reduces variation but does not guarantee identical AI output. So facts are validated, confirmed and saved, and scoring is code: the same saved facts always give the same ranking, with no new AI call.
- **Ties** are broken by total, then experience, then lower price, then fewer weeks. Anything still tied is shown as tied.
- **Reasons** come from one rule-based generator that reads only computed scores and checked facts, for any proposal or category. It lists the strongest and weakest areas with their numbers.
- **Breakdown:** each criterion's quote, page, formula and points are visible to the reviewer.

## 3. Human in the loop
1. **After extraction:** the reviewer confirms or corrects facts, with ambiguous and failed items first.
2. **Flags:** flagged proposals stay unranked until a reviewer resolves them (for example by asking D for a schedule) or overrides with a reason.
3. **Ranked list:** the reviewer can override a rank or an eligibility result, with a required written reason.
4. **Award:** the tool has no "award" action. A person decides outside it.

**Audit log (append-only):** who and when; file hash; criteria, prompt and model versions and settings; raw AI output; validation results; confirmed facts; scores; every override with its reason; the final decision.

## 4. Changing criteria
Checks, limits, criteria, scoring methods and tie-breaks are admin data, not code. Saving is blocked unless weights total 100.

Criteria are versioned. An edit creates a new version, and old results keep the version they were scored under. Re-scoring is a button:
- **Weights or formulas changed:** code re-runs on saved facts, instantly, with no AI calls.
- **A new criterion needs new facts:** only that field is extracted again.

Both result sets are kept for comparison.

## 5. Risks and safeguards
- **Wrong extraction:** code checks the reply's structure, types, quotes (must appear in the source) and page numbers. Failing fields are dropped and shown to the reviewer, who confirms before scoring.
- **Made-up facts:** "not_stated" is an allowed answer, no value is accepted without a matching quote, and "not mentioned" is kept separate from "explicitly absent".
- **Manipulation (prompt injection):** the proposal goes inside randomly named tags it cannot close early. The AI is told the text is data and to report instructions in it; a pattern scan adds a second warning but cannot catch everything. The real protection is structural: the AI cannot set scores, reasons or criteria, and a flagged proposal stays unranked until a person checks it.
- **Bias:** only the admin's criteria are scoring inputs, not company name or size.
- **Unfair price comparison:** price scope is captured and shown (only A states what its price includes).
- **Cost:** one cached extraction call per proposal; size limits; re-ranking reuses saved facts.

## Results on the sample set
- **A, rank 1 (98.8):** most experience, lowest ranked price, fastest schedule, full team plan.
- **E, rank 2 (88.4):** best warranty and full team plan, but fewer installs and one week slower.
- **C, flagged:**
  - It contains an instruction aimed at automated reviewers, which was ignored; a person should see it first.
  - Its experience period ("since 2020") reaches past five years, so the count cannot be confirmed.
  - If both are cleared, C ranks third (81.0).
- **D, flagged:** no completion time, so the 16-week limit cannot be checked. If D confirms 12 weeks or fewer it ranks second; 13 to 16 weeks puts it third.
- **B, ineligible:** the bidder-held licence is not demonstrated; electrical work goes to a subcontractor still to be confirmed. Its low price is not used as a benchmark.
