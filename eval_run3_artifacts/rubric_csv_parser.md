# Rubric: csv_parser

**Domain:** code_generation
**Total Points:** 44
**Pass Threshold:** 0.85

## Criterion 1: code_correctness
**Category:** functionality
**Max Points:** N/A
**Description:** Function correctly detects and handles multiple delimiter types (comma, tab, pipe, semicolon)
**Pass Condition:** Successfully parses CSV data using all 4 delimiter types (comma, tab, pipe, semicolon) AND handles edge cases: mixed delimiters within same dataset, escaped delimiters within quoted fields, and delimiter detection when sample data is minimal (<3 rows). Uses automatic delimiter detection with fallback strategy.

## Criterion 2: code_robustness
**Category:** reliability
**Max Points:** N/A
**Description:** Implements proper error handling without silent failures
**Pass Condition:** Uses try/except blocks around parsing operations. Raises or logs meaningful error messages for file access issues, encoding problems, or malformed data. Does not return None or empty results without explanation when errors occur.

## Criterion 3: code_api_design
**Category:** usability
**Max Points:** N/A
**Description:** Function signature is clean, well-typed, with sensible defaults
**Pass Condition:** Type hints. Docstring with examples. Reasonable defaults. Accepts str | Path | IO. Returns typed structure (not raw list).

## Criterion 4: code_idiomaticness
**Category:** quality
**Max Points:** N/A
**Description:** Leverages Python's csv module and standard library appropriately
**Pass Condition:** Uses csv.reader, csv.DictReader, or csv.Sniffer as the primary parsing mechanism. Uses dataclasses, NamedTuple, or TypedDict for structured return values rather than plain dictionaries or tuples.

## Criterion 5: code_testability
**Category:** quality
**Max Points:** N/A
**Description:** Code is structured for easy testing
**Pass Condition:** Pure function (no side effects). Includes or suggests test cases. Small composable helpers, not one monolith.
