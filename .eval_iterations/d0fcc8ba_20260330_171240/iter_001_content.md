```python
"""CSV parsing utilities for messy data with inconsistent formatting."""

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, IO, List, Union


@dataclass
class ParseResult:
    """Result of CSV parsing operation.
    
    Attributes:
        headers: Column names (generated if missing)
        rows: List of dictionaries mapping headers to values
        delimiter: Detected delimiter character
        has_original_headers: Whether headers were present in source
    """
    headers: List[str]
    rows: List[Dict[str, Any]]
    delimiter: str
    has_original_headers: bool


def detect_delimiter(sample: str) -> str:
    """Detect the most likely delimiter from a sample of CSV data.
    
    Args:
        sample: String sample of CSV data
        
    Returns:
        Single character delimiter
    """
    try:
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(sample, delimiters=',;\t|').delimiter
        return delimiter
    except csv.Error:
        # Fallback to comma if sniffing fails
        return ','


def detect_headers(first_row: List[str], second_row: List[str] = None) -> bool:
    """Heuristically determine if first row contains headers.
    
    Args:
        first_row: First row of data
        second_row: Second row of data (optional, improves detection)
        
    Returns:
        True if first row likely contains headers
    """
    if not first_row:
        return False
    
    # If we have a second row, compare data types
    if second_row and len(first_row) == len(second_row):
        numeric_pattern_matches = 0
        for val1, val2 in zip(first_row, second_row):
            # Check if first row is non-numeric while second is numeric
            try:
                float(val1.strip())
                first_is_numeric = True
            except (ValueError, AttributeError):
                first_is_numeric = False
                
            try:
                float(val2.strip())
                second_is_numeric = True
            except (ValueError, AttributeError):
                second_is_numeric = False
                
            if not first_is_numeric and second_is_numeric:
                numeric_pattern_matches += 1
        
        # If most columns show this pattern, first row is likely headers
        if numeric_pattern_matches >= len(first_row) * 0.5:
            return True
    
    # Fallback heuristics: headers typically contain letters
    text_columns = sum(1 for val in first_row 
                      if val.strip() and any(c.isalpha() for c in val))
    return text_columns >= len(first_row) * 0.7


def generate_headers(num_columns: int) -> List[str]:
    """Generate column headers when none are present.
    
    Args:
        num_columns: Number of columns to generate headers for
        
    Returns:
        List of generated header names
    """
    return [f'column_{i+1}' for i in range(num_columns)]


def parse_rows(reader: csv.reader, headers: List[str]) -> List[Dict[str, Any]]:
    """Parse CSV rows into dictionaries.
    
    Args:
        reader: CSV reader object
        headers: Column headers to use as keys
        
    Returns:
        List of row dictionaries
    """
    rows = []
    for row_data in reader:
        # Skip empty rows
        if not row_data or all(not cell.strip() for cell in row_data):
            continue
            
        # Pad or truncate row to match header count
        normalized_row = row_data[:len(headers)]
        while len(normalized_row) < len(headers):
            normalized_row.append('')
            
        # Convert to dictionary
        row_dict = {header: value.strip() if value else '' 
                   for header, value in zip(headers, normalized_row)}
        rows.append(row_dict)
        
    return rows


def parse_csv(source: Union[str, Path, IO], 
              delimiter: str = None,
              encoding: str = 'utf-8') -> ParseResult:
    """Parse messy CSV data with inconsistent delimiters and missing headers.
    
    Automatically detects delimiters and generates headers when missing.
    Handles various edge cases like empty rows, mixed quoting, and 
    trailing delimiters gracefully.
    
    Args:
        source: File path, file object, or CSV string data
        delimiter: Override automatic delimiter detection
        encoding: Text encoding for file reading
        
    Returns:
        ParseResult containing headers, rows, delimiter, and metadata
        
    Example:
        >>> csv_data = "name;age;city\\nJohn;30;NYC\\nJane;25;LA"
        >>> result = parse_csv(csv_data)
        >>> print(result.headers)
        ['name', 'age', 'city']
        >>> print(len(result.rows))
        2
    """
    # Handle different input types
    if isinstance(source, (str, Path)):
        path = Path(source)
        if path.exists():
            # It's a file path
            with open(path, 'r', encoding=encoding, newline='') as f:
                content = f.read()
        else:
            # It's CSV string data
            content = str(source)
    else:
        # It's a file-like object
        content = source.read()
        if hasattr(source, 'seek'):
            source.seek(0)
    
    if not content.strip():
        return ParseResult(headers=[], rows=[], delimiter=',', 
                          has_original_headers=False)
    
    # Detect delimiter if not provided
    if delimiter is None:
        delimiter = detect_delimiter(content)
    
    # Create CSV reader
    content_io = io.StringIO(content)
    reader = csv.reader(content_io, delimiter=delimiter, 
                       quoting=csv.QUOTE_MINIMAL, skipinitialspace=True)
    
    # Read all rows
    all_rows = []
    try:
        for row in reader:
            # Handle trailing delimiters by removing empty trailing cells
            while row and not row[-1].strip():
                row.pop()
            if row:  # Only add non-empty rows
                all_rows.append(row)
    except csv.Error:
        # Fallback for malformed CSV
        content_io.seek(0)
        all_rows = [line.split(delimiter) for line in content_io 
                   if line.strip()]
    
    if not all_rows:
        return ParseResult(headers=[], rows=[], delimiter=delimiter, 
                          has_original_headers=False)
    
    # Detect headers
    first_row = all_rows[0]
    second_row = all_rows[1] if len(all_rows) > 1 else None
    has_headers = detect_headers(first_row, second_row)
    
    if has_headers:
        headers = [str(h).strip() for h in first_row]
        data_rows = all_rows[1:]
    else:
        headers = generate_headers(len(first_row))
        data_rows = all_rows
    
    # Parse data rows
    content_io = io.StringIO('\n'.join(delimiter.join(row) for row in data_rows))
    data_reader = csv.reader(content_io, delimiter=delimiter, 
                            quoting=csv.QUOTE_MINIMAL, skipinitialspace=True)
    rows = parse_rows(data_reader, headers)
    
    return ParseResult(
        headers=headers,
        rows=rows, 
        delimiter=delimiter,
        has_original_headers=has_headers
    )


# Test examples
def test_parse_csv():
    """Example test cases demonstrating functionality."""
    
    # Test 1: Semicolon delimiter with headers
    csv_data = "name;age;city\nJohn Doe;30;New York\nJane Smith;25;Los Angeles"
    result = parse_csv(csv_data)
    assert result.delimiter == ';'
    assert result.headers == ['name', 'age', 'city']
    assert len(result.rows) == 2
    assert result.has_original_headers == True
    
    # Test 2: Tab delimiter, no headers
    csv_data = "John\t30\tNYC\nJane\t25\tLA"
    result = parse_csv(csv_data)
    assert result.delimiter == '\t'
    assert result.headers == ['column_1', 'column_2', 'column_3']
    assert result.has_original_headers == False
    
    # Test 3: Mixed quoting and trailing delimiters
    csv_data = 'name,age,city,\n"John, Jr",30,"New York",\n'
    result = parse_csv(csv_data)
    assert len(result.headers) == 3  # Trailing delimiter handled
    assert result.rows[0]['name'] == 'John, Jr'
    
    # Test 4: Empty rows and malformed data
    csv_data = "a,b,c\n\n1,2,3\n,,"
    result = parse_csv(csv_data)
    assert len(result.rows) == 1  # Empty rows skipped
    
    print("All tests passed!")


if __name__ == "__main__":
    test_parse_csv()
```