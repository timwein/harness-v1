```python
"""
CSV parser for messy data with inconsistent delimiters and missing headers.
"""

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, IO, List, Dict, Union, Optional, Tuple


@dataclass
class ParseResult:
    """Result of CSV parsing operation."""
    headers: List[str]
    rows: List[Dict[str, Any]]
    delimiter: str
    has_original_headers: bool
    total_rows: int


def detect_delimiter(sample: str) -> str:
    """
    Detect the most likely delimiter in a CSV sample.
    
    Args:
        sample: String sample of CSV data
        
    Returns:
        The detected delimiter character
    """
    try:
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(sample, delimiters=',;\t|').delimiter
        return delimiter
    except csv.Error:
        # Fallback: count occurrences of common delimiters
        delimiters = [',', ';', '\t', '|']
        counts = {d: sample.count(d) for d in delimiters}
        return max(counts, key=counts.get) if any(counts.values()) else ','


def detect_headers(first_row: List[str], second_row: Optional[List[str]] = None) -> bool:
    """
    Heuristically determine if the first row contains headers.
    
    Args:
        first_row: First row of CSV data
        second_row: Second row of CSV data (optional, for comparison)
        
    Returns:
        True if first row appears to be headers, False otherwise
    """
    if not first_row:
        return False
    
    # Check if all cells are non-empty strings (typical for headers)
    if all(isinstance(cell, str) and cell.strip() for cell in first_row):
        # If we have a second row, compare data types
        if second_row and len(second_row) == len(first_row):
            # Headers are likely if first row is all strings and second row has numbers
            try:
                numeric_in_second = sum(1 for cell in second_row if _is_numeric(cell.strip()))
                if numeric_in_second > 0 and numeric_in_second >= len(second_row) * 0.3:
                    return True
            except (ValueError, AttributeError):
                pass
        
        # Default to True for non-empty string rows (common header pattern)
        return True
    
    return False


def _is_numeric(value: str) -> bool:
    """Check if a string represents a numeric value."""
    if not value:
        return False
    try:
        float(value)
        return True
    except ValueError:
        return False


def generate_headers(num_columns: int) -> List[str]:
    """
    Generate default column headers.
    
    Args:
        num_columns: Number of columns to generate headers for
        
    Returns:
        List of generated header names
    """
    return [f"column_{i+1}" for i in range(num_columns)]


def parse_rows(reader: csv.reader, has_headers: bool) -> Tuple[List[str], List[List[str]]]:
    """
    Parse rows from CSV reader, handling headers appropriately.
    
    Args:
        reader: CSV reader object
        has_headers: Whether the first row contains headers
        
    Returns:
        Tuple of (headers, data_rows)
    """
    rows = []
    headers = []
    
    try:
        first_row = next(reader)
        if not first_row or all(not cell.strip() for cell in first_row):
            # Skip empty first row
            first_row = next(reader)
    except StopIteration:
        return [], []
    
    if has_headers:
        headers = [col.strip() for col in first_row]
    else:
        headers = generate_headers(len(first_row))
        rows.append([cell.strip() for cell in first_row])
    
    # Process remaining rows
    for row in reader:
        # Skip completely empty rows
        if not row or all(not cell.strip() for cell in row):
            continue
            
        # Normalize row length to match headers
        normalized_row = row[:len(headers)]
        while len(normalized_row) < len(headers):
            normalized_row.append('')
            
        rows.append([cell.strip() for cell in normalized_row])
    
    return headers, rows


def parse_csv(
    source: Union[str, Path, IO[str]], 
    encoding: str = 'utf-8',
    max_sample_size: int = 8192
) -> ParseResult:
    """
    Parse messy CSV data with automatic delimiter detection and header handling.
    
    This function automatically detects delimiters, determines if headers are present,
    and handles common CSV parsing edge cases like empty rows and inconsistent quoting.
    
    Args:
        source: CSV data source - file path, Path object, or file-like object
        encoding: Text encoding to use when reading files (default: utf-8)
        max_sample_size: Maximum bytes to sample for delimiter detection
        
    Returns:
        ParseResult containing parsed headers, rows, and metadata
        
    Example:
        >>> result = parse_csv('data.csv')
        >>> print(f"Found {len(result.rows)} rows with delimiter '{result.delimiter}'")
        >>> for row_dict in result.rows:
        ...     print(row_dict)
    """
    # Handle different input types
    if isinstance(source, (str, Path)):
        with open(source, 'r', encoding=encoding, newline='') as file:
            content = file.read()
    elif hasattr(source, 'read'):
        if hasattr(source, 'seek'):
            source.seek(0)
        content = source.read()
    else:
        raise TypeError("source must be a file path, Path object, or file-like object")
    
    if not content.strip():
        return ParseResult([], [], ',', False, 0)
    
    # Sample content for delimiter detection
    sample = content[:max_sample_size]
    delimiter = detect_delimiter(sample)
    
    # Create reader and detect headers
    reader = csv.reader(io.StringIO(content), delimiter=delimiter, quotechar='"')
    
    # Peek at first two rows for header detection
    content_lines = content.strip().split('\n')
    if len(content_lines) >= 2:
        first_parsed = list(csv.reader([content_lines[0]], delimiter=delimiter))[0]
        second_parsed = list(csv.reader([content_lines[1]], delimiter=delimiter))[0]
        has_headers = detect_headers(first_parsed, second_parsed)
    elif len(content_lines) == 1:
        first_parsed = list(csv.reader([content_lines[0]], delimiter=delimiter))[0]
        has_headers = detect_headers(first_parsed)
    else:
        has_headers = False
    
    # Parse all rows
    reader = csv.reader(io.StringIO(content), delimiter=delimiter, quotechar='"')
    headers, data_rows = parse_rows(reader, has_headers)
    
    # Convert to list of dictionaries
    rows_as_dicts = []
    for row in data_rows:
        row_dict = {}
        for i, value in enumerate(row):
            header = headers[i] if i < len(headers) else f"column_{i+1}"
            row_dict[header] = value
        rows_as_dicts.append(row_dict)
    
    return ParseResult(
        headers=headers,
        rows=rows_as_dicts,
        delimiter=delimiter,
        has_original_headers=has_headers,
        total_rows=len(rows_as_dicts)
    )


# Example test cases
def test_parse_csv():
    """Test cases demonstrating the parser functionality."""
    
    # Test 1: CSV with headers and comma delimiter
    csv_with_headers = "name,age,city\nJohn,25,NYC\nJane,30,LA"
    result = parse_csv(io.StringIO(csv_with_headers))
    assert result.headers == ['name', 'age', 'city']
    assert len(result.rows) == 2
    assert result.delimiter == ','
    assert result.has_original_headers == True
    
    # Test 2: CSV without headers, semicolon delimiter
    csv_no_headers = "John;25;NYC\nJane;30;LA"
    result = parse_csv(io.StringIO(csv_no_headers))
    assert result.headers == ['column_1', 'column_2', 'column_3']
    assert len(result.rows) == 2
    assert result.delimiter == ';'
    assert result.has_original_headers == False
    
    # Test 3: Empty and malformed rows
    messy_csv = "name,age,city\n,25,\nJane,30,LA\n\n,,"
    result = parse_csv(io.StringIO(messy_csv))
    assert len(result.rows) == 2  # Empty rows filtered out
    assert result.rows[0]['name'] == ''
    assert result.rows[1]['name'] == 'Jane'
    
    # Test 4: Tab-delimited data
    tab_csv = "name\tage\tcity\nJohn\t25\tNYC"
    result = parse_csv(io.StringIO(tab_csv))
    assert result.delimiter == '\t'
    assert result.rows[0]['name'] == 'John'


if __name__ == "__main__":
    test_parse_csv()
    print("All tests passed!")
```