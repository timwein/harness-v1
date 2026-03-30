```python
from typing import Union, List, Dict, Any, TextIO
from dataclasses import dataclass
from pathlib import Path
import csv
import io
import re


@dataclass
class ParseResult:
    """Result of CSV parsing operation."""
    data: List[Dict[str, str]]
    warnings: List[str]
    rows_processed: int
    rows_skipped: int
    delimiter: str
    has_header: bool


def detect_delimiter(sample: str) -> str:
    """
    Detect the most likely delimiter in a CSV sample.
    
    Args:
        sample: Sample text from CSV file
        
    Returns:
        Detected delimiter character
    """
    try:
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(sample, delimiters=',;\t|').delimiter
        return delimiter
    except csv.Error:
        # Fallback: count occurrences of common delimiters
        delimiters = [',', ';', '\t', '|']
        counts = {d: sample.count(d) for d in delimiters}
        return max(counts, key=counts.get) or ','


def detect_headers(first_row: List[str], second_row: List[str] = None) -> bool:
    """
    Heuristically determine if first row contains headers.
    
    Args:
        first_row: First row of data
        second_row: Second row of data (optional, improves accuracy)
        
    Returns:
        True if first row appears to be headers
    """
    if not first_row:
        return False
    
    # Check for numeric patterns - headers are rarely all numeric
    numeric_count = sum(1 for cell in first_row if cell.strip().replace('.', '').replace('-', '').isdigit())
    if numeric_count == len(first_row) and len(first_row) > 1:
        return False
    
    # Headers often contain letters and common header words
    header_indicators = ['id', 'name', 'date', 'time', 'value', 'count', 'type', 'status']
    has_header_words = any(any(indicator in cell.lower() for indicator in header_indicators) 
                          for cell in first_row)
    
    # Compare with second row if available
    if second_row and len(second_row) == len(first_row):
        # If second row is more numeric than first, first is likely header
        first_numeric = sum(1 for cell in first_row if cell.strip().replace('.', '').replace('-', '').isdigit())
        second_numeric = sum(1 for cell in second_row if cell.strip().replace('.', '').replace('-', '').isdigit())
        if second_numeric > first_numeric:
            return True
    
    return has_header_words or len([cell for cell in first_row if cell.strip().isalpha()]) >= len(first_row) // 2


def generate_headers(num_columns: int) -> List[str]:
    """
    Generate default column headers.
    
    Args:
        num_columns: Number of columns needed
        
    Returns:
        List of generated header names
    """
    return [f'column_{i+1}' for i in range(num_columns)]


def clean_row(row: List[str], expected_columns: int) -> List[str]:
    """
    Clean and normalize a row of data.
    
    Args:
        row: Raw row data
        expected_columns: Expected number of columns
        
    Returns:
        Cleaned row with consistent column count
    """
    # Strip whitespace from all cells
    cleaned = [cell.strip() for cell in row]
    
    # Handle column count mismatches
    if len(cleaned) > expected_columns:
        # Truncate extra columns
        cleaned = cleaned[:expected_columns]
    elif len(cleaned) < expected_columns:
        # Pad with empty strings
        cleaned.extend([''] * (expected_columns - len(cleaned)))
    
    return cleaned


def parse_csv_content(content: str, 
                     delimiter: str = None,
                     has_header: bool = None,
                     skip_empty_rows: bool = True) -> ParseResult:
    """
    Parse messy CSV data with inconsistent delimiters and missing headers.
    
    This function automatically detects delimiters and headers in CSV data,
    handling common formatting issues like mixed quoting, empty rows, and
    inconsistent column counts.
    
    Args:
        content: CSV content as string
        delimiter: Force specific delimiter (None for auto-detection)
        has_header: Force header presence (None for auto-detection)  
        skip_empty_rows: Whether to skip completely empty rows
        
    Returns:
        ParseResult containing:
            - data: List of dictionaries with parsed rows
            - warnings: List of parsing warnings
            - rows_processed: Number of data rows processed
            - rows_skipped: Number of rows skipped
            - delimiter: Delimiter used for parsing
            - has_header: Whether headers were detected/used
            
    Example:
        >>> content = '''name;age;city
        ... John;30;New York
        ... Jane,25,Boston'''
        >>> result = parse_csv_content(content)
        >>> result.data[0]
        {'name': 'John', 'age': '30', 'city': 'New York'}
        
    Raises:
        ValueError: If content is empty or unparseable
        TypeError: If content is not a string
    """
    if not isinstance(content, str):
        raise TypeError("Content must be a string")
    
    content = content.strip()
    if not content:
        raise ValueError("Content cannot be empty")
    
    warnings = []
    rows_skipped = 0
    
    try:
        # Auto-detect delimiter if not provided
        if delimiter is None:
            delimiter = detect_delimiter(content)
            
        # Parse all rows
        reader = csv.reader(io.StringIO(content), delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)
        all_rows = []
        
        for row_num, row in enumerate(reader, 1):
            # Skip completely empty rows if requested
            if skip_empty_rows and not any(cell.strip() for cell in row):
                rows_skipped += 1
                continue
                
            all_rows.append(row)
        
        if not all_rows:
            return ParseResult(
                data=[],
                warnings=["No data rows found"],
                rows_processed=0,
                rows_skipped=rows_skipped,
                delimiter=delimiter,
                has_header=False
            )
        
        # Auto-detect headers if not specified
        if has_header is None:
            second_row = all_rows[1] if len(all_rows) > 1 else None
            has_header = detect_headers(all_rows[0], second_row)
        
        # Determine column count and headers
        max_columns = max(len(row) for row in all_rows)
        
        if has_header:
            headers = clean_row(all_rows[0], max_columns)
            data_rows = all_rows[1:]
        else:
            headers = generate_headers(max_columns)
            data_rows = all_rows
            warnings.append("No headers detected, generated default column names")
        
        # Process data rows
        processed_data = []
        for row_num, row in enumerate(data_rows, 1):
            try:
                cleaned_row = clean_row(row, len(headers))
                row_dict = dict(zip(headers, cleaned_row))
                processed_data.append(row_dict)
            except Exception as e:
                warnings.append(f"Error processing row {row_num}: {str(e)}")
                rows_skipped += 1
                continue
        
        # Add warnings for data quality issues
        if any(len(row) != max_columns for row in all_rows):
            warnings.append("Inconsistent column counts detected and normalized")
            
        return ParseResult(
            data=processed_data,
            warnings=warnings,
            rows_processed=len(processed_data),
            rows_skipped=rows_skipped,
            delimiter=delimiter,
            has_header=has_header
        )
        
    except csv.Error as e:
        raise ValueError(f"CSV parsing error: {str(e)}")
    except Exception as e:
        raise ValueError(f"Unexpected error during parsing: {str(e)}")


# Example test cases
def test_parse_csv_content():
    """Test cases demonstrating the function's capabilities."""
    
    # Test 1: Mixed delimiters with headers
    content1 = """name,age;city
John,30;New York
Jane,25;Boston"""
    result1 = parse_csv_content(content1)
    assert result1.has_header == True
    assert len(result1.data) == 2
    assert result1.data[0]['name'] == 'John'
    
    # Test 2: No headers, inconsistent columns
    content2 = """John,30
Jane,25,Boston,Extra"""
    result2 = parse_csv_content(content2)
    assert result2.has_header == False
    assert len(result2.data) == 2
    assert 'column_1' in result2.data[0]
    
    # Test 3: Empty rows and whitespace
    content3 = """name,age
    
John, 30 
    
Jane,25"""
    result3 = parse_csv_content(content3)
    assert result3.rows_skipped == 2
    assert len(result3.data) == 2
    
    print("All tests passed!")


if __name__ == "__main__":
    test_parse_csv_content()
```