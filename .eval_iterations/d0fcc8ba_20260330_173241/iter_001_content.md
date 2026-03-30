```python
from dataclasses import dataclass
from pathlib import Path
from typing import IO, List, Dict, Any, Union
import csv
import io


@dataclass
class ParseResult:
    """Result of CSV parsing operation."""
    data: List[Dict[str, Any]]
    headers: List[str]
    delimiter: str
    had_headers: bool


def detect_delimiter(sample: str) -> str:
    """Detect the most likely delimiter from a sample of CSV data.
    
    Args:
        sample: First few lines of CSV data
        
    Returns:
        Detected delimiter character
    """
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=',;\t|')
        return dialect.delimiter
    except csv.Error:
        # Fallback: count occurrences of common delimiters
        delimiters = [',', ';', '\t', '|']
        counts = {d: sample.count(d) for d in delimiters}
        return max(counts, key=counts.get) if max(counts.values()) > 0 else ','


def detect_headers(first_row: List[str], second_row: List[str] = None) -> bool:
    """Heuristically determine if first row contains headers.
    
    Args:
        first_row: First row of parsed data
        second_row: Second row of parsed data (optional)
        
    Returns:
        True if first row likely contains headers
    """
    if not first_row:
        return False
    
    # If all values are strings and contain non-numeric characters, likely headers
    non_numeric_count = sum(1 for cell in first_row 
                           if isinstance(cell, str) and not cell.strip().replace('.', '').replace('-', '').isdigit())
    
    if non_numeric_count >= len(first_row) * 0.7:  # 70% threshold
        return True
    
    # If we have a second row, compare types
    if second_row and len(second_row) == len(first_row):
        type_differences = 0
        for i, (first, second) in enumerate(zip(first_row, second_row)):
            first_is_num = first.strip().replace('.', '').replace('-', '').isdigit() if first.strip() else False
            second_is_num = second.strip().replace('.', '').replace('-', '').isdigit() if second.strip() else False
            if first_is_num != second_is_num:
                type_differences += 1
        
        return type_differences >= len(first_row) * 0.5  # 50% threshold
    
    return False


def generate_headers(num_columns: int) -> List[str]:
    """Generate default column headers.
    
    Args:
        num_columns: Number of columns needed
        
    Returns:
        List of generated header names
    """
    return [f'column_{i+1}' for i in range(num_columns)]


def parse_rows(reader: csv.reader, delimiter: str) -> List[List[str]]:
    """Parse all rows from CSV reader, handling edge cases.
    
    Args:
        reader: CSV reader object
        delimiter: Delimiter being used
        
    Returns:
        List of parsed rows (excluding empty rows)
    """
    rows = []
    for row in reader:
        # Skip completely empty rows
        if not row or all(cell.strip() == '' for cell in row):
            continue
        
        # Handle trailing delimiters by removing empty trailing cells
        while row and row[-1].strip() == '':
            row.pop()
        
        if row:  # Only add non-empty rows
            rows.append(row)
    
    return rows


def parse_csv(source: Union[str, Path, IO], 
              encoding: str = 'utf-8',
              sample_size: int = 1024) -> ParseResult:
    """Parse messy CSV data with inconsistent delimiters and missing headers.
    
    This function automatically detects delimiters, handles missing headers by
    generating them, and gracefully manages common CSV edge cases like empty
    rows, mixed quoting, and trailing delimiters.
    
    Args:
        source: File path, file-like object, or CSV string data
        encoding: Text encoding for file reading (default: 'utf-8')
        sample_size: Bytes to sample for delimiter detection (default: 1024)
        
    Returns:
        ParseResult containing parsed data, headers, delimiter used, and
        whether original headers were detected
        
    Example:
        >>> result = parse_csv('messy_data.csv')
        >>> print(f"Found {len(result.data)} rows with delimiter '{result.delimiter}'")
        >>> print(f"Headers: {result.headers}")
    """
    # Handle different input types
    if isinstance(source, (str, Path)) and Path(source).exists():
        with open(source, 'r', encoding=encoding, newline='') as f:
            content = f.read()
    elif hasattr(source, 'read'):
        content = source.read()
        if hasattr(content, 'decode'):  # bytes
            content = content.decode(encoding)
    else:
        content = str(source)
    
    if not content.strip():
        return ParseResult(data=[], headers=[], delimiter=',', had_headers=False)
    
    # Detect delimiter from sample
    sample = content[:sample_size]
    delimiter = detect_delimiter(sample)
    
    # Parse all rows
    string_io = io.StringIO(content)
    reader = csv.reader(string_io, delimiter=delimiter)
    rows = parse_rows(reader, delimiter)
    
    if not rows:
        return ParseResult(data=[], headers=[], delimiter=delimiter, had_headers=False)
    
    # Detect headers
    first_row = rows[0]
    second_row = rows[1] if len(rows) > 1 else None
    has_headers = detect_headers(first_row, second_row)
    
    if has_headers:
        headers = first_row
        data_rows = rows[1:]
    else:
        headers = generate_headers(len(first_row))
        data_rows = rows
    
    # Convert to list of dictionaries
    data = []
    for row in data_rows:
        # Pad or trim row to match header count
        padded_row = row + [''] * (len(headers) - len(row))
        padded_row = padded_row[:len(headers)]
        data.append(dict(zip(headers, padded_row)))
    
    return ParseResult(
        data=data,
        headers=headers,
        delimiter=delimiter,
        had_headers=has_headers
    )


# Example test cases demonstrating functionality
if __name__ == "__main__":
    # Test 1: Semicolon delimiter with headers
    test_data_1 = "name;age;city\nJohn;30;NYC\nJane;25;LA"
    result1 = parse_csv(test_data_1)
    assert result1.delimiter == ';'
    assert result1.had_headers == True
    assert len(result1.data) == 2
    assert result1.data[0]['name'] == 'John'
    
    # Test 2: Tab delimiter without headers
    test_data_2 = "John\t30\tNYC\nJane\t25\tLA"
    result2 = parse_csv(test_data_2)
    assert result2.delimiter == '\t'
    assert result2.had_headers == False
    assert result2.headers == ['column_1', 'column_2', 'column_3']
    
    # Test 3: Mixed content with empty rows
    test_data_3 = "id,value,desc\n1,100,item1\n\n2,200,item2\n,,\n3,300,item3"
    result3 = parse_csv(test_data_3)
    assert len(result3.data) == 3  # Empty rows filtered out
    
    # Test 4: Pipe delimiter with trailing delimiters
    test_data_4 = "a|b|c|\n1|2|3|\n4|5|6|"
    result4 = parse_csv(test_data_4)
    assert result4.delimiter == '|'
    assert all(len(row) == 3 for row in [result4.headers] + [list(d.values()) for d in result4.data])
    
    print("All tests passed!")
```