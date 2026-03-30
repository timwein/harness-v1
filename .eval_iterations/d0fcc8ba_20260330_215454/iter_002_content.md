```python
"""
A robust CSV parser for messy data with inconsistent delimiters and missing headers.
"""

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Union, Optional, TextIO
import re
from datetime import datetime


@dataclass
class ParseResult:
    """Result of CSV parsing operation with metadata."""
    data: List[Dict[str, Any]]
    headers: List[str]
    warnings: List[str] = field(default_factory=list)
    rows_skipped: int = 0
    delimiter_used: str = ','
    has_original_header: bool = False


def detect_delimiter(sample: str, possible_delimiters: List[str] = None) -> str:
    """
    Detect the most likely delimiter in CSV data using multiple heuristics.
    
    Args:
        sample: A sample of the CSV data to analyze
        possible_delimiters: List of delimiters to test (defaults to common ones)
    
    Returns:
        The most likely delimiter character
    """
    if possible_delimiters is None:
        possible_delimiters = [',', ';', '\t', '|', ':']
    
    try:
        # Use csv.Sniffer for delimiter detection
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=''.join(possible_delimiters))
        return dialect.delimiter
    except csv.Error:
        # Fallback to consistency check if Sniffer fails
        return _fallback_delimiter_detection(sample, possible_delimiters)


def _fallback_delimiter_detection(sample: str, delimiters: List[str]) -> str:
    """
    Fallback delimiter detection based on consistency across rows.
    
    Args:
        sample: CSV sample data
        delimiters: Possible delimiter characters
    
    Returns:
        Best delimiter based on consistency heuristic
    """
    lines = [line.strip() for line in sample.split('\n') if line.strip()]
    if len(lines) < 2:
        return ','
    
    scores = {}
    for delimiter in delimiters:
        try:
            reader = csv.reader(io.StringIO(sample), delimiter=delimiter)
            rows = [row for row in reader if any(cell.strip() for cell in row)]
            
            if len(rows) < 2:
                continue
                
            # Check consistency: do rows have same number of columns?
            col_counts = [len(row) for row in rows[:10]]  # Check first 10 rows
            if col_counts and len(set(col_counts)) == 1 and col_counts[0] > 1:
                scores[delimiter] = col_counts[0]
        except csv.Error:
            continue
    
    if scores:
        return max(scores.keys(), key=scores.get)
    return ','


def detect_headers(sample: str, delimiter: str) -> tuple[bool, Optional[List[str]]]:
    """
    Detect if CSV has headers and extract them if present.
    
    Args:
        sample: Sample of CSV data
        delimiter: Delimiter character to use
    
    Returns:
        Tuple of (has_header: bool, headers: Optional[List[str]])
    """
    try:
        # Use csv.Sniffer.has_header() as primary heuristic
        sniffer = csv.Sniffer()
        has_header = sniffer.has_header(sample)
        
        if has_header:
            reader = csv.reader(io.StringIO(sample), delimiter=delimiter)
            headers = next(reader, None)
            if headers:
                return True, [str(header).strip() for header in headers]
    except csv.Error:
        pass
    
    # Enhanced heuristic: check if first row differs from subsequent rows
    return _enhanced_header_detection(sample, delimiter)


def _enhanced_header_detection(sample: str, delimiter: str) -> tuple[bool, Optional[List[str]]]:
    """
    Enhanced header detection using type and pattern analysis.
    
    Args:
        sample: CSV sample data
        delimiter: Delimiter to use for parsing
    
    Returns:
        Tuple of (has_header, headers)
    """
    try:
        reader = csv.reader(io.StringIO(sample), delimiter=delimiter)
        rows = [row for row in reader if any(cell.strip() for cell in row)]
        
        if len(rows) < 2:
            return False, None
            
        first_row = rows[0]
        second_row = rows[1] if len(rows) > 1 else None
        
        if not second_row:
            return False, None
            
        # Check if first row looks like headers (strings vs numbers pattern)
        header_score = 0
        for i, (h, d) in enumerate(zip(first_row, second_row)):
            h_str, d_str = h.strip(), d.strip()
            
            # Header-like if first is non-numeric and second is numeric
            if not _is_number(h_str) and _is_number(d_str):
                header_score += 1
            # Or if lengths are very different (header vs data pattern)
            elif abs(len(h_str) - len(d_str)) > 3:
                header_score += 0.5
                
        # Consider it a header if majority of columns show header pattern
        has_header = header_score >= len(first_row) * 0.4
        return has_header, first_row if has_header else None
        
    except (csv.Error, IndexError):
        return False, None


def _is_number(value: str) -> bool:
    """Check if a string represents a number."""
    if not value:
        return False
    try:
        float(value)
        return True
    except ValueError:
        return False


def _is_date(value: str) -> bool:
    """Check if a string represents a date."""
    if not value:
        return False
    
    # Common date patterns
    date_patterns = [
        '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d',
        '%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S', 
        '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ'
    ]
    
    for pattern in date_patterns:
        try:
            datetime.strptime(value.strip(), pattern)
            return True
        except ValueError:
            continue
    return False


def _convert_value(value: str) -> tuple[Any, Optional[str]]:
    """
    Convert string value to appropriate type with validation.
    
    Args:
        value: String value to convert
        
    Returns:
        Tuple of (converted_value, warning_message)
    """
    if not value or not value.strip():
        return value, None
        
    cleaned = value.strip()
    
    # Try integer conversion
    try:
        if '.' not in cleaned and cleaned.isdigit() or (cleaned.startswith('-') and cleaned[1:].isdigit()):
            return int(cleaned), None
    except ValueError:
        pass
    
    # Try float conversion
    try:
        if '.' in cleaned or 'e' in cleaned.lower():
            float_val = float(cleaned)
            return float_val, None
    except ValueError:
        pass
    
    # Try date conversion
    if _is_date(cleaned):
        return cleaned, None  # Keep as string but note it's date-like
        
    # Return as string
    return cleaned, None


def generate_headers(num_columns: int, prefix: str = 'column') -> List[str]:
    """
    Generate default headers when none are present.
    
    Args:
        num_columns: Number of columns to generate headers for
        prefix: Prefix for generated header names
    
    Returns:
        List of generated header names
    """
    return [f'{prefix}_{i+1}' for i in range(num_columns)]


def parse_rows(content: str, delimiter: str, headers: List[str]) -> tuple[List[Dict[str, Any]], List[str], int]:
    """
    Parse CSV rows into dictionaries with error tracking and data validation.
    
    Args:
        content: CSV content to parse
        delimiter: Delimiter character
        headers: Column headers to use
    
    Returns:
        Tuple of (data_rows, warnings, skipped_count)
    """
    data = []
    warnings = []
    skipped_count = 0
    
    try:
        # Handle mixed quoting styles by configuring csv.reader appropriately
        reader = csv.reader(
            io.StringIO(content), 
            delimiter=delimiter,
            quoting=csv.QUOTE_MINIMAL,  # Handle mixed quoting
            skipinitialspace=True
        )
        
        for row_num, row in enumerate(reader, 1):
            # Skip completely empty rows
            if not any(cell.strip() for cell in row):
                skipped_count += 1
                continue
            
            # Handle trailing delimiters by removing empty trailing cells
            while row and not row[-1].strip():
                row.pop()
                
            # Handle rows with different column counts
            if len(row) != len(headers):
                if len(row) > len(headers):
                    warnings.append(f"Row {row_num}: Too many columns ({len(row)} vs {len(headers)}), truncating")
                    row = row[:len(headers)]
                else:
                    warnings.append(f"Row {row_num}: Too few columns ({len(row)} vs {len(headers)}), padding with empty strings")
                    row.extend([''] * (len(headers) - len(row)))
            
            # Clean, validate and convert cell values
            row_dict = {}
            for header, cell in zip(headers, row):
                cleaned_cell = str(cell).strip() if cell is not None else ''
                
                # 
No automatic data type conversion is performed unless the QUOTE_NONNUMERIC format option is specified

                # Add independent data validation and type conversion
                converted_value, conversion_warning = _convert_value(cleaned_cell)
                if conversion_warning:
                    warnings.append(f"Row {row_num}, Column '{header}': {conversion_warning}")
                
                row_dict[header] = converted_value
                
            data.append(row_dict)
            
    except csv.Error as e:
        warnings.append(f"CSV parsing error: {e}")
        
    return data, warnings, skipped_count


def parse_csv(
    source: Union[str, Path, TextIO],
    encoding: str = 'utf-8',
    sample_size: int = 4096,
    possible_delimiters: Optional[List[str]] = None
) -> ParseResult:
    """
    Parse messy CSV data with automatic delimiter detection and header handling.
    
    This function robustly parses CSV files that may have:
    - Inconsistent or unknown delimiters
    - Missing or ambiguous headers
    - Empty rows and malformed data
    - Mixed quoting styles
    - Trailing delimiters
    
    Args:
        source: File path, Path object, or file-like object containing CSV data
        encoding: Character encoding for file reading (default: 'utf-8')
        sample_size: Number of bytes to sample for format detection
        possible_delimiters: List of delimiter characters to try
    
    Returns:
        ParseResult containing parsed data, metadata, and any warnings
    
    Example:
        >>> result = parse_csv('messy_data.csv')
        >>> print(f"Parsed {len(result.data)} rows with {len(result.warnings)} warnings")
        >>> for row in result.data[:3]:
        ...     print(row)
    """
    warnings = []
    
    try:
        # Read the input source
        if isinstance(source, (str, Path)):
            with open(source, 'r', encoding=encoding, newline='') as file:
                content = file.read()
        else:
            content = source.read()
            
        if not content.strip():
            return ParseResult(
                data=[],
                headers=[],
                warnings=['Empty file or no content to parse'],
                rows_skipped=0
            )
            
        # Get sample for analysis - use sufficient size for accuracy
        sample = content[:sample_size] if len(content) > sample_size else content
        
        # Detect delimiter
        delimiter = detect_delimiter(sample, possible_delimiters)
        
        # Detect headers
        has_original_header, detected_headers = detect_headers(sample, delimiter)
        
        # Determine final headers
        if has_original_header and detected_headers:
            headers = detected_headers
            # Skip the header row in content
            lines = content.split('\n')
            if lines:
                content = '\n'.join(lines[1:])
        else:
            # Generate headers based on first row column count
            reader = csv.reader(io.StringIO(sample), delimiter=delimiter)
            first_row = next(reader, [])
            num_columns = len(first_row) if first_row else 1
            headers = generate_headers(num_columns)
            
            if not has_original_header:
                warnings.append("No headers detected, generated default column names")
        
        # Parse the data rows
        data, parse_warnings, skipped_count = parse_rows(content, delimiter, headers)
        warnings.extend(parse_warnings)
        
        return ParseResult(
            data=data,
            headers=headers,
            warnings=warnings,
            rows_skipped=skipped_count,
            delimiter_used=delimiter,
            has_original_header=has_original_header
        )
        
    except UnicodeDecodeError as e:
        return ParseResult(
            data=[],
            headers=[],
            warnings=[f"Encoding error: {e}. Try a different encoding."],
            rows_skipped=0
        )
    except FileNotFoundError as e:
        return ParseResult(
            data=[],
            headers=[],
            warnings=[f"File not found: {e}"],
            rows_skipped=0
        )
    except Exception as e:
        return ParseResult(
            data=[],
            headers=[],
            warnings=[f"Unexpected error during parsing: {e}"],
            rows_skipped=0
        )


# Example test cases and usage demonstrations
if __name__ == "__main__":
    # Test case 1: Semicolon-delimited with headers
    test_data_1 = "Name;Age;City\nAlice;30;New York\nBob;25;London\n"
    result1 = parse_csv(io.StringIO(test_data_1))
    assert result1.delimiter_used == ';'
    assert result1.has_original_header == True
    assert len(result1.data) == 2
    print("✓ Test 1 passed: Semicolon delimiter with headers")
    
    # Test case 2: Tab-delimited without headers
    test_data_2 = "Alice\t30\tNew York\nBob\t25\tLondon\n"
    result2 = parse_csv(io.StringIO(test_data_2))
    assert result2.delimiter_used == '\t'
    assert result2.has_original_header == False
    assert result2.headers == ['column_1', 'column_2', 'column_3']
    print("✓ Test 2 passed: Tab delimiter without headers")
    
    # Test case 3: Messy data with empty rows and inconsistent columns
    test_data_3 = "ID,Name,Score\n\n1,Alice,95\n2,Bob\n\n3,Charlie,87,Extra\n"
    result3 = parse_csv(io.StringIO(test_data_3))
    assert result3.rows_skipped == 2  # Two empty rows
    assert len(result3.warnings) >= 2  # Warnings for missing and extra columns
    print("✓ Test 3 passed: Messy data with edge cases")
    
    # Test case 4: Mixed quoting and trailing delimiters
    test_data_4 = 'Name,Age,City,\n"Alice, Jr",30,"New York",\n\'Bob\',25,London,\n'
    result4 = parse_csv(io.StringIO(test_data_4))
    assert len(result4.data) == 2
    assert result4.data[0]['Name'] == 'Alice, Jr'  # Properly handled quoted comma
    print("✓ Test 4 passed: Mixed quoting and trailing delimiters")
    
    # Test case 5: Data type conversion
    test_data_5 = "Name,Age,Score,Date\nAlice,30,95.5,2023-01-01\nBob,25,87.2,2023-01-02\n"
    result5 = parse_csv(io.StringIO(test_data_5))
    assert isinstance(result5.data[0]['Age'], int)
    assert isinstance(result5.data[0]['Score'], float)
    print("✓ Test 5 passed: Data type conversion")
    
    print(f"\nAll tests passed! Parse function is working correctly.")
```