# Design write-up: MATACS-TH-2026-02

**In one line:** AI extracts facts with quotes. Code validates, checks eligibility, scores, ranks and writes reasons. People confirm, override and award. Flow: `diagram/process_flow.png`.

**Statuses:** **ranked** = official score; **flagged** = a person must resolve something first; **ineligible** = fails a mandatory requirement.

## Assumptions (the brief does not say)
- **Hard limits:** a price over $260,000 or a schedule over 16 weeks is ineligible. A missing price or schedule is flagged, because the limit cannot be checked.
- **Licence:** must be held by the bidder. Work assigned to a subcontractor does not demonstrate this, so it is ineligible (a reviewer can override). No mention at all is flagged.
- **Five-year window:** "since 2020" may include older installs, so it is flagged. "Since 2021" starts in the window's first year, so it is accepted with a note to confirm early-2021 installs. A stricter admin setting would flag A and E too.
- **Full marks:** 12 installs, 25-year panel and 12-year workmanship warranties (admin-editable).

## 1. AI vs. rules
**AI does one job:** read the proposal text and extract facts into a fixed JSON form, each with a word-for-word quote and page number.

**Code does everything else:**
file checks, text extraction (OCR for scans), validating the AI's reply, mandatory checks, limits, the five-year window, scoring, ranking, reasons and the audit log.

**Why this line:** AI copes with varied wording but is weak at repeatability and arithmetic. Anything that decides a position must be repeatable and explainable, so it is code. The AI never outputs a score or a reason.

## 2. Consistency and explainability
- **Fixed formulas**, stored as admin settings:
  - experience = installs ÷ 12, capped at 100;
  - price = lowest eligible ranked price ÷ this price;
  - timeline = fewest eligible ranked weeks ÷ this bid's weeks;
  - warranty = average of panel ÷ 25 and workmanship ÷ 12 (each capped);
  - team = 25 points per item stated (named lead, crew, safety plan, monitoring).
- **Missing information is never guessed.** If experience, warranty, price or timeline is missing or cannot be confirmed, the proposal is flagged. An unstated team item scores 0 and is listed.
- **Benchmarks use ranked bids only**, so flagged or ineligible bids cannot shift other scores.
- **Repeat runs:** temperature 0 reduces but does not remove AI variation. So facts are validated, confirmed and saved; the same saved facts always give the same ranking.
- **Ties:** total, then experience, then lower price, then fewer weeks; still tied is shown as tied.
- **Reasons** come from a rule-based generator using only computed scores and checked facts. Each criterion's quote, page and points are visible to the reviewer.

## 3. Human in the loop
1. **After extraction:** the reviewer confirms or corrects facts, with ambiguous and rejected items first.
2. **Flags:** flagged proposals stay unranked until a reviewer resolves them (for example, asking D for a schedule) or overrides.
3. **Ranked list:** the reviewer acknowledges notes (boundary-year experience, security text) and can override a rank or eligibility result with a written reason.
4. **Award:** the tool has no "award" action. A person decides outside it.

**Audit log (append-only):** who and when; file hash; criteria, prompt and model versions and settings; raw AI output; validation results; confirmed facts; scores; every override with its reason; the final decision.

## 4. Changing criteria
Checks, limits, criteria, scoring methods and tie-breaks are admin data, not code. Saving is blocked unless weights total 100.

Criteria are versioned: an edit creates a new version, and old results keep theirs. Re-scoring is a button:
- **Weights or formulas changed:** code re-runs on saved facts, instantly, with no AI calls.
- **A new criterion needs new facts:** only that field is extracted again. Both result sets are kept.

## 5. Risks and safeguards
- **Wrong extraction:** code checks structure, types, quotes (must appear in the source) and pages; failing fields are dropped and shown to the reviewer. In testing, it dropped one unconfirmed field from B, and showed "named project lead" was defined too strictly, which I fixed and re-tested (PROMPTS.md).
- **Made-up facts:** "not_stated" is an allowed answer, no value is accepted without a matching quote, and "not mentioned" is kept separate from "explicitly absent".
- **Prompt injection:** the proposal sits inside randomly named tags it cannot close early; the AI treats it as data and reports instructions, and a pattern scan adds a warning. The real protection is structural: the AI cannot set scores, reasons or criteria, so detected text is logged for acknowledgment but does not block ranking.
- **Bias:** only the admin's criteria are scoring inputs, not company name or size.
- **Unfair price comparison:** price scope is captured and shown (only A states what its price includes).
- **Cost:** one cached extraction call per proposal; size limits; re-ranking reuses saved facts.

## Results on the sample set

| | Status | Score | Why |
|---|---|---|---|
| **A** | Ranked 1 | 98.8 | Most experience, lowest eligible ranked price, fastest schedule, full team plan. |
| **E** | Ranked 2 | 88.4 | Best warranty and full team plan, but fewer installs and one week slower. |
| **C** | Flagged | – | "Since 2020" reaches past five years; if the count is confirmed, C ranks third (81.0). Its embedded instruction was ignored and logged. |
| **D** | Flagged | – | No completion time to check against 16 weeks. At 12 weeks or fewer it ranks second; 13 to 16, third. |
| **B** | Ineligible | – | Bidder-held licence not demonstrated (unconfirmed subcontractor). Its low price is not a benchmark. |

A and E carry a note to confirm installs from early 2021.