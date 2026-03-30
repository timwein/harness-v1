```python
import csv
import io
from pathlib import Path
from typing import Union, List, Dict, Any, Optional, IO
from dataclasses import dataclass
from collections import Counter


@dataclass
class ParseResult:
    """Result of CSV parsing operation with metadata."""
    data: List[Dict[str, Any]]
    warnings: List[str]
    rows_skipped: int
    delimiter: str
    has_header: bool
    total_rows: int


def parse_csv(
    source: Union[str, Path, IO[str]],
    max_sample_size: int = 8192,
    encoding: str = "utf-8",
    fallback_delimiter: str = ","
) -> ParseResult:
    """
    Parse messy CSV data with inconsistent delimiters and missing headers.
    
    Automatically detects delimiters and header presence, handles edge cases
    like empty rows and mixed quoting gracefully.
    
    Args:
        source: File path, string content, or file-like object to parse
        max_sample_size: Maximum bytes to sample for delimiter detection
        encoding: Text encoding (used only for file paths)
        fallback_delimiter: Delimiter to use if detection fails
        
    Returns:
        ParseResult with parsed data, warnings, and metadata
        
    Example:
        >>> result = parse_csv("data.csv")
        >>> print(f"Parsed {len(result.data)} rows with delimiter '{result.delimiter}'")
        >>> for warning in result.warnings:
        ...     print(f"Warning: {warning}")
    """
    try:
        content = _read_source(source, encoding)
        if not content.strip():
            return ParseResult([], ["Empty file"], 0, ",", False, 0)
            
        delimiter = _detect_delimiter(content[:max_sample_size], fallback_delimiter)
        lines = content.splitlines()
        non_empty_lines = [line for line in lines if line.strip()]
        
        if not non_empty_lines:
            return ParseResult([], ["No non-empty lines found"], 0, delimiter, False, 0)
            
        has_header = _detect_headers(non_empty_lines[:5], delimiter)
        data, warnings, rows_skipped = _parse_rows(non_empty_lines, delimiter, has_header)
        
        return ParseResult(
            data=data,
            warnings=warnings,
            rows_skipped=rows_skipped,
            delimiter=delimiter,
            has_header=has_header,
            total_rows=len(lines)
        )
        
    except Exception as e:
        return ParseResult(
            data=[],
            warnings=[f"Parse error: {str(e)}"],
            rows_skipped=0,
            delimiter=fallback_delimiter,
            has_header=False,
            total_rows=0
        )


def _read_source(source: Union[str, Path, IO[str]], encoding: str) -> str:
    """Read content from various source types."""
    if hasattr(source, 'read'):
        # File-like object
        pos = source.tell() if hasattr(source, 'tell') else None
        content = source.read()
        if pos is not None and hasattr(source, 'seek'):
            source.seek(pos)  # Reset position for caller
        return content
    elif isinstance(source, (str, Path)):
        path = Path(source)
        if path.exists():
            # File path
            return path.read_text(encoding=encoding)
        else:
            # Assume it's CSV content as string
            return str(source)
    else:
        raise ValueError(f"Unsupported source type: {type(source)}")


def _detect_delimiter(sample: str, fallback: str) -> str:
    """Detect the most likely delimiter in the CSV sample."""
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except (csv.Error, AttributeError):
        # Fallback to frequency analysis
        candidates = [',', ';', '\t', '|']
        delimiter_counts = Counter()
        
        for line in sample.splitlines()[:10]:  # Check first 10 lines
            if line.strip():
                for delim in candidates:
                    delimiter_counts[delim] += line.count(delim)
        
        if delimiter_counts:
            return delimiter_counts.most_common(1)[0][0]
        return fallback


def _detect_headers(lines: List[str], delimiter: str) -> bool:
    """Detect if first row contains headers using heuristic analysis."""
    if len(lines) < 2:
        return False
        
    try:
        first_row = list(csv.reader([lines[0]], delimiter=delimiter))[0]
        second_row = list(csv.reader([lines[1]], delimiter=delimiter))[0]
        
        # If rows have different lengths, likely has headers
        if len(first_row) != len(second_row):
            return True
            
        # Check if first row contains non-numeric data while second row is numeric
        first_numeric = sum(1 for cell in first_row if _is_numeric(cell.strip()))
        second_numeric = sum(1 for cell in second_row if _is_numeric(cell.strip()))
        
        # If first row is less numeric than second, likely headers
        if len(first_row) > 0 and first_numeric < second_numeric:
            return True
            
        # Check for typical header patterns
        header_indicators = ['id', 'name', 'date', 'time', 'value', 'count', 'total']
        first_row_lower = [cell.lower().strip() for cell in first_row]
        
        if any(indicator in ' '.join(first_row_lower) for indicator in header_indicators):
            return True
            
        return False
        
    except (csv.Error, IndexError):
        return False


def _is_numeric(value: str) -> bool:
    """Check if a string represents a numeric value."""
    if not value:
        return False
    try:
        float(value.replace(',', ''))
        return True
    except ValueError:
        return False


def _parse_rows(lines: List[str], delimiter: str, has_header: bool) -> tuple[List[Dict[str, Any]], List[str], int]:
    """Parse CSV rows into dictionaries with comprehensive error handling."""
    data = []
    warnings = []
    rows_skipped = 0
    headers = []
    
    try:
        reader = csv.reader(lines, delimiter=delimiter)
        
        # Handle headers
        if has_header and lines:
            try:
                headers = next(reader)
                headers = [f"col_{i}" if not h.strip() else h.strip() for i, h in enumerate(headers)]
            except (StopIteration, csv.Error) as e:
                warnings.append(f"Failed to read header row: {e}")
                has_header = False
        
        # Process data rows
        for row_num, row in enumerate(reader, start=2 if has_header else 1):
            try:
                if not any(cell.strip() for cell in row):  # Skip empty rows
                    rows_skipped += 1
                    continue
                    
                # Generate headers if needed
                if not headers:
                    headers = [f"col_{i}" for i in range(len(row))]
                
                # Handle column count mismatches
                while len(row) < len(headers):
                    row.append("")  # Pad with empty strings
                    
                if len(row) > len(headers):
                    warnings.append(f"Row {row_num}: Extra columns truncated")
                    row = row[:len(headers)]
                
                # Create row dictionary with type conversion
                row_dict = {}
                for i, (header, value) in enumerate(zip(headers, row)):
                    cleaned_value = value.strip()
                    row_dict[header] = _convert_value(cleaned_value)
                
                data.append(row_dict)
                
            except csv.Error as e:
                warnings.append(f"Row {row_num}: Parse error - {e}")
                rows_skipped += 1
            except Exception as e:
                warnings.append(f"Row {row_num}: Unexpected error - {e}")
                rows_skipped += 1
                
    except Exception as e:
        warnings.append(f"Reader initialization failed: {e}")
        
    return data, warnings, rows_skipped


def _convert_value(value: str) -> Any:
    """Convert string value to appropriate Python type."""
    if not value:
        return None
        
    # Try integer
    try:
        if '.' not in value and ',' not in value:
            return int(value)
    except ValueError:
        pass
        
    # Try float
    try:
        return float(value.replace(',', ''))
    except ValueError:
        pass
        
    # Try boolean
    lower_val = value.lower()
    if lower_val in ('true', 'yes', '1'):
        return True
    elif lower_val in ('false', 'no', '0'):
        return False
        
    # Return as string
    return value


# Test examples
def test_parse_csv():
    """Test cases demonstrating function behavior."""
    
    # Test 1: Mixed delimiters with headers
    csv_data = "name,age;score\nAlice,25;95\nBob,30;87"
    result = parse_csv(csv_data)
    assert len(result.data) == 2
    assert result.has_header == True
    assert result.data[0]['name'] == 'Alice'
    
    # Test 2: No headers, tab-delimited
    csv_data = "Alice\t25\t95\nBob\t30\t87"
    result = parse_csv(csv_data)
    assert len(result.data) == 2
    assert result.has_header == False
    assert 'col_0' in result.data[0]
    
    # Test 3: Empty rows and malformed data
    csv_data = "name,age\n\nAlice,25\n,30\nBob,invalid"
    result = parse_csv(csv_data)
    assert result.rows_skipped >= 1
    assert len(result.warnings) > 0


if __name__ == "__main__":
    test_parse_csv()
    print("All tests passed!")
```