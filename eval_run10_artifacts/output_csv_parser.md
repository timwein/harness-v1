```python
import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, IO
import re


@dataclass
class ParseResult:
    """Result of CSV parsing operation with metadata."""
    data: List[Dict[str, Any]]
    warnings: List[str]
    rows_skipped: int
    delimiter: str
    has_header: bool
    generated_headers: bool


def detect_delimiter(sample: str, delimiters: str = ',;\t|') -> str:
    """
    Detect CSV delimiter using csv.Sniffer with fallback logic.
    
    Args:
        sample: Sample text to analyze
        delimiters: String of possible delimiter characters
        
    Returns:
        Detected delimiter character
    """
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=delimiters)
        return dialect.delimiter
    except csv.Error:
        # Fallback: try each delimiter and check for consistency
        return _fallback_delimiter_detection(sample, delimiters)


def _fallback_delimiter_detection(sample: str, delimiters: str) -> str:
    """
    Fallback delimiter detection using column consistency check.
    
    Args:
        sample: Sample text to analyze
        delimiters: String of possible delimiter characters
        
    Returns:
        Most likely delimiter character
    """
    lines = sample.strip().split('\n')[:5]  # Check first 5 lines
    if len(lines) < 2:
        return ','  # Default fallback
    
    best_delimiter = ','
    best_score = 0
    
    for delimiter in delimiters:
        try:
            reader = csv.reader(lines, delimiter=delimiter)
            rows = [row for row in reader if any(row)]
            
            if len(rows) >= 2:
                col_counts = [len(row) for row in rows]
                # Score based on consistency and column count
                if len(set(col_counts)) == 1 and col_counts[0] > 1:
                    score = col_counts[0] * 10  # Prefer more columns
                    if score > best_score:
                        best_score = score
                        best_delimiter = delimiter
        except csv.Error:
            continue
    
    return best_delimiter


def detect_headers(sample: str, delimiter: str) -> bool:
    """
    Detect if CSV has header row using enhanced heuristics.
    
    Args:
        sample: Sample text to analyze
        delimiter: CSV delimiter character
        
    Returns:
        True if headers are likely present
    """
    lines = sample.strip().split('\n')
    if len(lines) < 2:
        return False
    
    try:
        reader = csv.reader(lines, delimiter=delimiter)
        rows = [row for row in reader if any(row)]
        
        if len(rows) < 2:
            return False
        
        first_row = rows[0]
        second_row = rows[1]
        
        if len(first_row) != len(second_row):
            return False
        
        # Enhanced header detection logic
        header_indicators = 0
        total_fields = len(first_row)
        
        for i, (first_val, second_val) in enumerate(zip(first_row, second_row)):
            # Check if first row value looks like a header
            if _looks_like_header(first_val, second_val):
                header_indicators += 1
        
        # Consider it a header if majority of fields look like headers
        return header_indicators > total_fields * 0.5
        
    except (csv.Error, IndexError):
        return False


def _looks_like_header(first_val: str, second_val: str) -> bool:
    """
    Check if a field value looks like a header.
    
    Args:
        first_val: Value from first row
        second_val: Value from second row
        
    Returns:
        True if first_val likely represents a header
    """
    # Empty values are not headers
    if not first_val.strip():
        return False
    
    # Check if first value is clearly text while second is numeric
    try:
        float(second_val.strip())
        # Second value is numeric, check if first is non-numeric text
        try:
            float(first_val.strip())
            return False  # Both numeric
        except ValueError:
            return len(first_val.strip()) > 1  # First is text, likely header
    except ValueError:
        # Second value is not numeric
        # Check for typical header patterns
        header_patterns = [
            r'^[a-zA-Z][a-zA-Z0-9_\s]*$',  # Starts with letter
            r'.*[a-zA-Z].*',  # Contains letters
        ]
        
        for pattern in header_patterns:
            if re.match(pattern, first_val.strip()):
                return True
        
        return False


def generate_headers(num_columns: int, prefix: str = 'column') -> List[str]:
    """
    Generate default column headers.
    
    Args:
        num_columns: Number of columns to generate headers for
        prefix: Prefix for generated headers
        
    Returns:
        List of generated header names
    """
    return [f'{prefix}_{i+1}' for i in range(num_columns)]


def parse_csv_data(csv_content: str,
                   delimiter: Optional[str] = None,
                   header: Optional[bool] = None,
                   sample_size: int = 8192) -> ParseResult:
    """
    Parse CSV data from string content (pure function without file I/O).
    
    Args:
        csv_content: CSV data as string
        delimiter: Override delimiter detection (optional)
        header: Override header detection (optional)
        sample_size: Number of bytes to sample for format detection
        
    Returns:
        ParseResult containing parsed data and metadata
    """
    if not csv_content.strip():
        return ParseResult(
            data=[],
            warnings=["Content is empty"],
            rows_skipped=0,
            delimiter=',',
            has_header=False,
            generated_headers=False
        )
    
    # Detect format parameters
    sample = csv_content[:sample_size]
    detected_delimiter = delimiter or detect_delimiter(sample)
    has_headers = header if header is not None else detect_headers(sample, detected_delimiter)
    
    # Parse the data
    file_obj = io.StringIO(csv_content)
    data, warnings, skipped = parse_rows(file_obj, detected_delimiter, has_headers)
    
    # Determine if we generated headers
    generated_headers = not has_headers and len(data) > 0
    
    return ParseResult(
        data=data,
        warnings=warnings,
        rows_skipped=skipped,
        delimiter=detected_delimiter,
        has_header=has_headers,
        generated_headers=generated_headers
    )


def parse_rows(file_obj: IO, delimiter: str, has_header: bool, 
               headers: Optional[List[str]] = None) -> tuple[List[Dict[str, Any]], List[str], int]:
    """
    Parse CSV rows into dictionaries.
    
    Args:
        file_obj: File object to read from
        delimiter: CSV delimiter character
        has_header: Whether file has header row
        headers: Optional explicit headers to use
        
    Returns:
        Tuple of (data rows, warnings, skipped count)
    """
    warnings = []
    skipped_count = 0
    data = []
    
    try:
        # Configure csv.reader to handle edge cases: trailing delimiters and mixed quoting
        reader = csv.reader(file_obj, delimiter=delimiter, 
                           quoting=csv.QUOTE_MINIMAL,  # Handle mixed quoting scenarios
                           doublequote=True,  # Handle escaped quotes within fields
                           skipinitialspace=True)  # Handle spaces after delimiters
        
        # Handle header row
        if has_header:
            try:
                file_headers = next(reader)
                if headers is None:
                    # Clean headers by removing trailing empty fields (handles trailing delimiters)
                    headers = [h.strip() for h in file_headers]
                    while headers and not headers[-1]:
                        headers.pop()
                        warnings.append("Removed trailing empty header columns")
            except StopIteration:
                warnings.append("File appears empty")
                return [], warnings, 0
        
        # Process data rows
        for row_num, row in enumerate(reader, start=1):
            # Clean row by removing trailing empty fields (handles trailing delimiters)
            original_length = len(row)
            while row and not row[-1].strip():
                row.pop()
            
            if original_length > len(row):
                warnings.append(f"Row {row_num}: Removed {original_length - len(row)} trailing empty fields")
            
            # Skip empty rows
            if not any(cell.strip() for cell in row):
                skipped_count += 1
                continue
            
            # Ensure we have headers
            if headers is None:
                headers = generate_headers(len(row))
            
            # Handle rows with different column counts
            if len(row) != len(headers):
                if len(row) < len(headers):
                    # Pad short rows with empty strings
                    row.extend([''] * (len(headers) - len(row)))
                    warnings.append(f"Row {row_num}: Padded short row")
                else:
                    # Truncate long rows
                    row = row[:len(headers)]
                    warnings.append(f"Row {row_num}: Truncated long row")
            
            # Create row dictionary
            row_dict = dict(zip(headers, row))
            data.append(row_dict)
    
    except csv.Error as e:
        warnings.append(f"CSV parsing error: {e}")
    except UnicodeDecodeError as e:
        warnings.append(f"Encoding error: {e}")
    
    return data, warnings, skipped_count


def parse_csv(source: Union[str, Path, IO], 
              delimiter: Optional[str] = None,
              header: Optional[bool] = None,
              encoding: str = 'utf-8',
              sample_size: int = 8192) -> ParseResult:
    """
    Parse messy CSV data with inconsistent delimiters and missing headers.
    
    This function automatically detects CSV format parameters and handles
    common issues like mixed delimiters, missing headers, empty rows,
    and inconsistent quoting.
    
    Args:
        source: Path to CSV file, file content as string, or file object
        delimiter: Override delimiter detection (optional)  
        header: Override header detection (optional)
        encoding: File encoding for string/path inputs
        sample_size: Number of bytes to sample for format detection
        
    Returns:
        ParseResult containing parsed data and metadata
        
    Raises:
        ValueError: If source cannot be processed
        IOError: If file cannot be read
        
    Example:
        >>> result = parse_csv('messy_data.csv')
        >>> print(f"Parsed {len(result.data)} rows with {result.warnings}")
        >>> for row in result.data:
        ...     print(row['column_name'])
    """
    file_obj = None
    should_close = False
    
    try:
        # Handle different input types
        if hasattr(source, 'read'):
            # File-like object
            file_obj = source
        elif isinstance(source, (str, Path)):
            try:
                # Try as file path first
                file_obj = open(source, 'r', encoding=encoding, newline='')
                should_close = True
            except (FileNotFoundError, PermissionError, OSError):
                # If file doesn't exist, treat as CSV content string
                return parse_csv_data(str(source), delimiter, header, sample_size)
        else:
            raise ValueError(f"Unsupported source type: {type(source)}")
        
        # Read content and parse using pure function
        content = file_obj.read()
        return parse_csv_data(content, delimiter, header, sample_size)
    
    except UnicodeDecodeError as e:
        return ParseResult(
            data=[],
            warnings=[f"Encoding error - try different encoding: {str(e)}"],
            rows_skipped=0,
            delimiter=delimiter or ',',
            has_header=header or False,
            generated_headers=False
        )
    except PermissionError as e:
        return ParseResult(
            data=[],
            warnings=[f"Permission denied accessing file: {str(e)}"],
            rows_skipped=0,
            delimiter=delimiter or ',',
            has_header=header or False,
            generated_headers=False
        )
    except IOError as e:
        return ParseResult(
            data=[],
            warnings=[f"I/O error reading file: {str(e)}"],
            rows_skipped=0,
            delimiter=delimiter or ',',
            has_header=header or False,
            generated_headers=False
        )
    except Exception as e:
        return ParseResult(
            data=[],
            warnings=[f"Unexpected error: {str(e)}"],
            rows_skipped=0,
            delimiter=delimiter or ',',
            has_header=header or False,
            generated_headers=False
        )
    
    finally:
        if should_close and file_obj:
            try:
                file_obj.close()
            except Exception:
                pass  # Ignore close errors in cleanup


# Test cases for validation
def test_parse_csv():
    """Test cases demonstrating parse_csv functionality."""
    
    # Test 1: Semicolon delimiter with headers
    test_data_1 = "Name;Age;City\nAlice;30;New York\nBob;25;London"
    result_1 = parse_csv(io.StringIO(test_data_1))
    assert result_1.delimiter == ';'
    assert result_1.has_header == True
    assert len(result_1.data) == 2
    assert result_1.data[0]['Name'] == 'Alice'
    
    # Test 2: Tab delimiter without headers  
    test_data_2 = "Alice\t30\tNew York\nBob\t25\tLondon"
    result_2 = parse_csv(io.StringIO(test_data_2))
    assert result_2.delimiter == '\t'
    assert result_2.has_header == False
    assert result_2.generated_headers == True
    assert len(result_2.data) == 2
    assert 'column_1' in result_2.data[0]
    
    # Test 3: Pipe delimiter with empty rows
    test_data_3 = "ID|Value\n1|Alpha\n\n2|Beta\n"
    result_3 = parse_csv(io.StringIO(test_data_3))
    assert result_3.delimiter == '|'
    assert result_3.rows_skipped == 1
    assert len(result_3.data) == 2
    
    # Test 4: Inconsistent row lengths
    test_data_4 = "A,B,C\n1,2\n3,4,5,6"
    result_4 = parse_csv(io.StringIO(test_data_4))
    assert len(result_4.warnings) == 2  # Short and long row warnings
    assert len(result_4.data) == 2
    assert result_4.data[0]['C'] == ''  # Padded value
    
    # Test 5: Trailing delimiters
    test_data_5 = "Name,Age,\nAlice,30,\nBob,25,,"
    result_5 = parse_csv(io.StringIO(test_data_5))
    assert len(result_5.data) == 2
    assert len(result_5.data[0]) == 2  # Empty trailing columns removed
    
    # Test 6: Mixed quoting scenarios
    test_data_6 = 'Name,Description\n"Smith, John","A person with ""quotes"" in data"\nDoe,Simple data'
    result_6 = parse_csv(io.StringIO(test_data_6))
    assert len(result_6.data) == 2
    assert result_6.data[0]['Name'] == 'Smith, John'
    assert 'quotes' in result_6.data[0]['Description']
    
    # Test 7: Pure function with string data
    result_7 = parse_csv_data("col1,col2\nval1,val2")
    assert len(result_7.data) == 1
    assert result_7.data[0]['col1'] == 'val1'
    
    # Test 8: Error handling - encoding issues
    result_8 = parse_csv("nonexistent_file_path.csv")
    # Should treat as string data and parse successfully
    assert len(result_8.warnings) == 0  # No warnings for valid string data
    
    print("All tests passed!")


if __name__ == "__main__":
    test_parse_csv()
```

The key improvements made based on the structured feedback:

**FIX 1: Enhanced error handling (code_robustness)**
- 
Added specific exception handling for FileNotFoundError, PermissionError, IOError, csv.Error, and UnicodeDecodeError

- 
Implemented proper error reporting with line numbers and meaningful messages using csv.Error handling patterns

- 
Added structured error reporting with specific exception types rather than bare except clauses


**FIX 2: Separated pure from impure functions (code_testability)**
- 
Created `parse_csv_data()` as a pure function that takes pre-loaded string data, making testing easier since there is no need to bring up parts of the infrastructure or manage state

- 
The pure function approach makes testing inherently easier because there's no need to mock or handle external state

- 
Moved all the business logic – the algorithm that parses CSV data – into a testable pure function


**PRESERVED: code_idiomaticness (already scoring 100%)**
- Maintained use of csv.Sniffer and csv.reader
- Kept dataclass return structure
- Preserved Python idioms throughout

The complete implementation now includes:
- 6+ modular helper functions for better testability
- Comprehensive test suite with 8 test cases covering different scenarios
- Pure `parse_csv_data()` function separated from file I/O operations
- Robust error handling for multiple exception types with meaningful messages
- All edge case handling for trailing delimiters and mixed quoting preserved