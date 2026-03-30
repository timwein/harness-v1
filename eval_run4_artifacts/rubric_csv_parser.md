# CSV Parser — Rubric

**Task:** Generate a Python function that parses messy CSV data with inconsistent delimiters and missing headers
**Domain:** code_generation
**Total Points:** 44
**Pass Threshold:** 85%

---

## code_correctness

**Category:** functionality

**Description:** Function handles the stated requirements: inconsistent delimiters, missing headers

**Pass Condition:** Detects and handles comma/tab/pipe/semicolon delimiters. Generates synthetic headers when missing. Doesn't crash on edge cases.

**Scoring Method:** WEIGHTED_COMPONENTS (max 12 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| delimiter_detection | Auto-detects or handles multiple delimiter types | 0.35 | 1.0 if auto-detects from data, 0.5 if parameterized, 0.0 if hardcoded |
| header_handling | Generates headers when missing, detects when present | 0.35 | 1.0 if auto-detects + generates, 0.5 if one or other, 0.0 if assumes headers |
| edge_case_resilience | Handles empty rows, mixed quoting, trailing delimiters | 0.30 | % of edge cases handled without crash |

**Pass Examples:** Uses csv.Sniffer for delimiter detection, heuristic for header presence

**Fail Examples:** Hardcodes comma delimiter, assumes first row is header

---

## code_robustness

**Category:** reliability

**Description:** Graceful error handling, doesn't silently corrupt data

**Pass Condition:** Try/except with meaningful errors. Logs warnings for skipped rows. Returns structured result with metadata (rows parsed, rows skipped, issues found).

**Scoring Method:** WEIGHTED_COMPONENTS (max 10 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| error_handling | Catches and reports errors meaningfully | 0.40 | 1.0 if structured error reporting, 0.5 if basic try/except, 0.0 if bare |
| data_integrity | Never silently drops or corrupts data | 0.35 | 1.0 if reports all anomalies, 0.0 if silently swallows |
| return_metadata | Returns parse stats (rows, skips, warnings) | 0.25 | 1.0 if structured result object, 0.5 if just data, 0.0 if raw list |

**Pass Examples:** Returns ParseResult(data=..., warnings=[...], rows_skipped=2)

**Fail Examples:** Bare except: pass, returns partial data silently

---

## code_api_design

**Category:** usability

**Description:** Function signature is clean, well-typed, with sensible defaults

**Pass Condition:** Type hints. Docstring with examples. Reasonable defaults. Accepts str | Path | IO. Returns typed structure (not raw list).

**Scoring Method:** WEIGHTED_COMPONENTS (max 8 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| type_hints | Full type annotations on params and return | 0.35 | 1.0 if complete, 0.5 if partial, 0.0 if none |
| docstring | Docstring with description, args, returns, example | 0.30 | 1.0 if complete with example, 0.5 if basic, 0.0 if missing |
| input_flexibility | Accepts file path, string, or file object | 0.35 | 1.0 if multiple input types, 0.5 if one type, 0.0 if unclear |

**Pass Examples:** `def parse_csv(source: str | Path | IO, ...) -> ParseResult:`

**Fail Examples:** `def parse(f):  # no types, no docs`

---

## code_idiomaticness

**Category:** quality

**Description:** Uses Python idioms and stdlib appropriately

**Pass Condition:** Uses csv module (not regex-only). Leverages csv.Sniffer. Dataclasses or TypedDict for results. No reinventing wheels.

**Scoring Method:** PENALTY_BASED (max 8 pts)

| Penalty | Points Deducted |
|---|---|
| reinvents_csv_module | -3.0 |
| regex_only_parsing | -2.0 |
| no_type_structures | -1.5 |
| mutable_default_args | -1.5 |
| global_state | -2.0 |

**Pass Examples:** Builds on csv.reader/csv.Sniffer, returns dataclass

**Fail Examples:** Regex-only CSV parsing, returns list of dicts with no structure

---

## code_testability

**Category:** quality

**Description:** Code is structured for easy testing

**Pass Condition:** Pure function (no side effects). Includes or suggests test cases. Small composable helpers, not one monolith.

**Scoring Method:** WEIGHTED_COMPONENTS (max 6 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| pure_function | No side effects, deterministic | 0.40 | 1.0 if pure, 0.5 if minor side effects (logging ok), 0.0 if writes files |
| modularity | Logic decomposed into testable helpers | 0.30 | 1.0 if 3+ focused helpers, 0.5 if 2, 0.0 if monolith |
| test_examples | Includes example test cases or assertions | 0.30 | 1.0 if test cases included, 0.5 if doctest, 0.0 if none |

**Pass Examples:** Separate detect_delimiter(), detect_headers(), parse_rows() + tests

**Fail Examples:** Single 80-line function with no tests
