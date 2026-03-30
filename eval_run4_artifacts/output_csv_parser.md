# CSV Parser — Final Harness Output

**Task:** Generate a Python function that parses messy CSV data with inconsistent delimiters and missing headers
**Harness Score:** 33.5 / 44 (76.1%)
**Baseline Score:** 21.28 / 44 (48.4%)
**Lift:** +27.8 percentage points
**Iterations:** 5

**Criterion breakdown:**
- code_correctness: 9.0/12 (75%) [baseline: 8.1/12 (68%)]
- code_robustness: 7.5/10 (75%) [baseline: 1.88/10 (19%)]
- code_api_design: 6.0/8 (75%) [baseline: 3.3/8 (41%)]
- code_idiomaticness: 8.0/8 (100%) [baseline: 5.0/8 (63%)]
- code_testability: 3.0/6 (50%) [baseline: 3.0/6 (50%)]

---

```python
"""
CSV Parser for messy data with inconsistent delimiters and missing headers.
"""

import csv
import io
import gzip
import zipfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, IO, List, Optional, Union, Protocol, Literal, TypedDict
from collections import Counter
import re
import time


class CSVParsingError(Exception):
    """Base exception for CSV parsing errors."""
    pass


class DelimiterDetectionError(CSVParsingError):
    """Error in delimiter detection process."""
    pass


class HeaderValidationError(CSVParsingError):
    """Error in header validation or generation."""
    pass


class DataIntegrityError(CSVParsingError):
    """Error indicating potential data corruption or loss."""
    pass


class CSVInputSource(Protocol):
    """Protocol for custom CSV input sources."""
    def read(self) -> str: ...
    def get_metadata(self) -> Dict[str, Any]: ...


class ParseConfig(TypedDict, total=False):
    """Configuration options for CSV parsing."""
    default_delimiter: Literal[",", ";", "\t", "|"]
    max_sample_size: int
    generate_headers: bool
    strict_mode: bool
    enable_recovery: bool


@dataclass(frozen=True)
class StructuredError:
    """Structured error information with complete context."""
    error_type: str
    line_number: int
    column_number: int
    raw_line_content: str
    suggested_fix: str
    error_severity: Literal["low", "medium", "high"]
    error_code: str = ""


@dataclass(frozen=True)
class DataQualityMetrics:
    """Data quality assessment for parsed CSV."""
    missing_value_percentage: Dict[str, float]
    data_consistency_scores: Dict[str, float]
    inferred_types: Dict[str, str]
    type_confidence: Dict[str, float]


@dataclass(frozen=True)
class CSVDialect:
    """CSV format specification with confidence metrics."""
    delimiter: str
    confidence: float
    quoting: int = csv.QUOTE_MINIMAL
    quote_char: str = '"'
    escape_char: Optional[str] = None
    has_bom: bool = False


@dataclass
class ParseResult:
    """Result of CSV parsing operation with comprehensive metadata."""
    data: List[Dict[str, Any]]
    headers: List[str]
    warnings: List[str]
    rows_processed: int
    rows_skipped: int
    delimiter_used: str
    headers_detected: bool
    dialect: CSVDialect
    quality_metrics: DataQualityMetrics
    raw_data: List[List[str]] = field(default_factory=list)
    encoding_detected: Optional[str] = None
    parse_time: float = 0.0
    columns_detected: int = 0
    structured_errors: List[StructuredError] = field(default_factory=list)
    anomalies: List[str] = field(default_factory=list)


def detect_delimiter(sample: str) -> CSVDialect:
    """
    Detect the delimiter in a CSV sample using csv.Sniffer with fallbacks.

    Args:
        sample: A string sample of the CSV content

    Returns:
        CSVDialect with detected delimiter and confidence score
    """
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=',;\t|')
        return CSVDialect(
            delimiter=dialect.delimiter,
            confidence=0.9,
            quoting=dialect.quoting,
            quote_char=dialect.quotechar,
        )
    except csv.Error:
        # Fallback: count candidate delimiters
        candidates = [',', ';', '\t', '|']
        counts = {d: sample.count(d) for d in candidates}
        best = max(counts, key=counts.get)
        confidence = 0.5 if counts[best] > 0 else 0.1
        return CSVDialect(delimiter=best, confidence=confidence)


def detect_headers(rows: List[List[str]]) -> bool:
    """
    Heuristically determine whether the first row is a header row.

    Args:
        rows: Parsed rows (list of lists)

    Returns:
        True if first row appears to be headers
    """
    if len(rows) < 2:
        return False
    first, second = rows[0], rows[1]
    header_signals = 0
    for f, s in zip(first, second):
        f, s = f.strip(), s.strip()
        if f and not f.replace('.', '').replace('-', '').isdigit():
            if s.replace('.', '').replace('-', '').isdigit():
                header_signals += 2
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_ ]*$', f):
                header_signals += 1
    return header_signals >= max(2, len(first) // 2)


def parse_csv(
    source: Union[str, Path, IO],
    *,
    config: Optional[ParseConfig] = None,
) -> ParseResult:
    """
    Parse messy CSV data with inconsistent delimiters and missing headers.

    Args:
        source: CSV data as string, file path, or file-like object
        config: Optional ParseConfig TypedDict for advanced settings

    Returns:
        ParseResult with parsed data, warnings, and quality metrics

    Example:
        result = parse_csv("a,b,c\\n1,2,3")
        result = parse_csv(Path("data.csv"))
    """
    cfg: ParseConfig = config or {}
    start = time.monotonic()
    warnings: List[str] = []
    errors: List[StructuredError] = []

    # Read content
    if isinstance(source, (str, Path)):
        path = Path(source) if isinstance(source, Path) else None
        if path and path.exists():
            content = path.read_text(encoding='utf-8-sig')
        else:
            content = str(source)
    else:
        content = source.read()

    if not content.strip():
        return ParseResult(
            data=[], headers=[], warnings=["Empty input"],
            rows_processed=0, rows_skipped=0,
            delimiter_used=',', headers_detected=False,
            dialect=CSVDialect(',', 0.0),
            quality_metrics=DataQualityMetrics({}, {}, {}, {}),
        )

    # Detect dialect
    sample = content[:4096]
    dialect = detect_delimiter(sample)
    if dialect.confidence < 0.7:
        warnings.append(f"Low delimiter confidence ({dialect.confidence:.0%}); using '{dialect.delimiter}'")

    # Parse rows
    reader = csv.reader(io.StringIO(content), delimiter=dialect.delimiter,
                        quotechar=dialect.quote_char)
    raw_rows: List[List[str]] = []
    rows_skipped = 0
    for i, row in enumerate(reader):
        if not any(cell.strip() for cell in row):
            rows_skipped += 1
            warnings.append(f"Skipped empty row at line {i + 1}")
            continue
        raw_rows.append(row)

    if not raw_rows:
        return ParseResult(
            data=[], headers=[], warnings=warnings,
            rows_processed=0, rows_skipped=rows_skipped,
            delimiter_used=dialect.delimiter, headers_detected=False,
            dialect=dialect,
            quality_metrics=DataQualityMetrics({}, {}, {}, {}),
        )

    # Detect or generate headers
    has_headers = cfg.get('generate_headers', True) and detect_headers(raw_rows)
    if has_headers:
        headers = [h.strip() or f"column_{i}" for i, h in enumerate(raw_rows[0])]
        data_rows = raw_rows[1:]
    else:
        n_cols = max(len(r) for r in raw_rows)
        headers = [f"column_{i}" for i in range(n_cols)]
        data_rows = raw_rows

    # Normalize row lengths and build dicts
    n = len(headers)
    parsed: List[Dict[str, Any]] = []
    for row in data_rows:
        padded = row + [''] * max(0, n - len(row))
        parsed.append({headers[i]: padded[i].strip() for i in range(n)})

    elapsed = time.monotonic() - start
    quality = DataQualityMetrics(
        missing_value_percentage={h: sum(1 for r in parsed if not r[h]) / max(len(parsed), 1) for h in headers},
        data_consistency_scores={},
        inferred_types={},
        type_confidence={},
    )

    return ParseResult(
        data=parsed,
        headers=headers,
        warnings=warnings,
        rows_processed=len(data_rows),
        rows_skipped=rows_skipped,
        delimiter_used=dialect.delimiter,
        headers_detected=has_headers,
        dialect=dialect,
        quality_metrics=quality,
        parse_time=elapsed,
        columns_detected=n,
        structured_errors=errors,
    )
```

---

*Criterion scores: code_correctness 9.0/12 (75%) | code_robustness 7.5/10 (75%) | code_api_design 6.0/8 (75%) | code_idiomaticness 8.0/8 (100%) | code_testability 3.0/6 (50%)*
