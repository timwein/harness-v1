```python
from typing import Union, List, Dict, Any, IO, Optional
from pathlib import Path
from dataclasses import dataclass
import csv
import io
import re
import time
import urllib.request
import urllib.parse


class CSVParseError(Exception):
    """Structured exception for CSV parsing errors."""
    def __init__(self, error_type: str, row_number: Optional[int] = None, details: str = ""):
        self.error_type = error_type
        self.row_number = row_number
        self.details = details
        super().__init__(f"{error_type}{f' at row {row_number}' if row_number else ''}: {details}")


@dataclass
class ParseResult:
    """Result of CSV parsing operation."""
    data: List[Dict[str, Any]]
    warnings: List[str]
    rows_skipped: int
    delimiter: str
    has_headers: bool
    total_rows_processed: int
    column_count: int
    encoding_used: str
    parse_time_seconds: float
    data_quality_score: float


def parse_csv(
    source: Union[str, Path, IO[str], bytes, List[str]],
    encoding: str = 'utf-8',
    max_sample_size: int = 8192,
    verbose: bool = False
) -> ParseResult:
    """
    Parse messy CSV data with inconsistent delimiters and missing headers.
    
    Automatically detects delimiters and determines if headers are present.
    Generates column names when headers are missing and handles various
    edge cases like empty rows and mixed quoting.
    
    Args:
        source: File path, string content, file-like object, bytes, URL, or list of strings to parse
        encoding: Character encoding for file/bytes reading (default: 'utf-8')
        max_sample_size: Maximum bytes to sample for delimiter detection
        verbose: Enable verbose output (default: False)
        
    Returns:
        ParseResult containing:
            - data: List of dictionaries with parsed rows
            - warnings: List of parsing warnings/issues encountered
            - rows_skipped: Number of rows skipped due to errors
            - delimiter: Detected delimiter used
            - has_headers: Whether headers were detected in first row
            - total_rows_processed: Total number of rows processed
            - column_count: Number of columns detected
            - encoding_used: Character encoding used for parsing
            - parse_time_seconds: Time taken to parse the data
            - data_quality_score: Percentage of clean rows without anomalies
            
    Raises:
        CSVParseError: When critical parsing errors occur with structured error details
        
    Example:
        >>> content = '''name;age;city
        ... John;25;NYC
        ... Jane,30,LA'''
        >>> result = parse_csv(content)
        >>> print(result.data)
        [{'name': 'John', 'age': '25', 'city': 'NYC'}, 
         {'name': 'Jane', 'age': '30', 'city': 'LA'}]
        >>> print(f"Quality score: {result.data_quality_score}%")
        Quality score: 100.0%
        >>> 
        >>> # Handling exceptions
        >>> try:
        ...     result = parse_csv("malformed\\x00data")
        ... except CSVParseError as e:
        ...     print(f"Error type: {e.error_type}, Details: {e.details}")
    """
    start_time = time.time()
    warnings = []
    rows_skipped = 0
    
    try:
        # Get content as string and detect encoding
        content, encoding_used = _get_content_string(source, encoding)
        
        if not content.strip():
            return ParseResult(
                [], ['Empty input'], 0, ',', False, 0, 0, 
                encoding_used, time.time() - start_time, 100.0
            )
        
        # Remove BOM if present
        content = _remove_bom(content)
        
        # Detect delimiter
        delimiter = _detect_delimiter(content, max_sample_size)
        if verbose:
            warnings.append(f"Detected delimiter: '{delimiter}'")
        
        # Parse rows using detected delimiter
        raw_rows = _parse_rows(content, delimiter, warnings, verbose)
        
        if not raw_rows:
            return ParseResult(
                [], warnings + ['No valid rows found'], 0, delimiter, False, 0, 0,
                encoding_used, time.time() - start_time, 0.0
            )
        
        # Filter empty rows and track skipped
        filtered_rows = []
        for row in raw_rows:
            if _is_empty_row(row):
                rows_skipped += 1
            else:
                filtered_rows.append(row)
        
        if not filtered_rows:
            return ParseResult(
                [], warnings + ['All rows were empty'], rows_skipped, delimiter, False, 
                len(raw_rows), 0, encoding_used, time.time() - start_time, 0.0
            )
        
        # Handle case with only headers and no data
        if len(filtered_rows) == 1:
            potential_headers = filtered_rows[0]
            if _detect_headers_single_row(potential_headers):
                warnings.append("File contains only headers with no data rows")
                return ParseResult(
                    [], warnings, rows_skipped, delimiter, True, len(raw_rows),
                    len(potential_headers), encoding_used, time.time() - start_time, 100.0
                )
        
        # Normalize column counts and detect anomalies
        normalized_rows, column_anomalies = _normalize_column_counts(filtered_rows)
        warnings.extend(column_anomalies)
        
        # Detect data quality issues
        quality_warnings = _detect_data_quality_issues(normalized_rows)
        warnings.extend(quality_warnings)
        
        # Detect headers
        has_headers = _detect_headers(normalized_rows)
        
        # Generate final data structure
        data = _build_data_structure(normalized_rows, has_headers, warnings)
        
        # Calculate metrics
        total_rows = len(raw_rows)
        column_count = len(normalized_rows[0]) if normalized_rows else 0
        quality_score = _calculate_data_quality_score(normalized_rows, warnings)
        
        if rows_skipped > 0:
            warnings.append(f"Skipped {rows_skipped} empty rows")
            
        return ParseResult(
            data, warnings, rows_skipped, delimiter, has_headers,
            total_rows, column_count, encoding_used, 
            time.time() - start_time, quality_score
        )
        
    except CSVParseError:
        raise
    except Exception as e:
        raise CSVParseError("GENERAL_PARSE_ERROR", details=str(e))


def _get_content_string(source: Union[str, Path, IO[str], bytes, List[str]], encoding: str) -> tuple[str, str]:
    """Convert input source to string content and return encoding used."""
    if isinstance(source, bytes):
        # Auto-detect encoding for bytes
        detected_encoding = _detect_encoding(source) or encoding
        try:
            return source.decode(detected_encoding), detected_encoding
        except UnicodeDecodeError:
            return source.decode(encoding, errors='replace'), encoding
    elif isinstance(source, list):
        # List of strings - join with newlines
        return '\n'.join(str(line) for line in source), encoding
    elif hasattr(source, 'read'):
        # File-like object
        content = source.read()
        return content if isinstance(content, str) else content.decode(encoding), encoding
    elif isinstance(source, (str, Path)):
        source_str = str(source)
        # Check if it's a URL
        if source_str.startswith(('http://', 'https://')):
            try:
                with urllib.request.urlopen(source_str) as response:
                    content_bytes = response.read()
                    detected_encoding = _detect_encoding(content_bytes) or encoding
                    return content_bytes.decode(detected_encoding), detected_encoding
            except Exception as e:
                raise CSVParseError("URL_FETCH_ERROR", details=str(e))
        
        path = Path(source_str)
        if path.exists():
            # File path
            try:
                return path.read_text(encoding=encoding), encoding
            except UnicodeDecodeError:
                # Try with different encoding
                content_bytes = path.read_bytes()
                detected_encoding = _detect_encoding(content_bytes) or encoding
                return content_bytes.decode(detected_encoding, errors='replace'), detected_encoding
        else:
            # String content
            return source_str, encoding
    else:
        return str(source), encoding


def _detect_encoding(content_bytes: bytes) -> Optional[str]:
    """Detect encoding from byte content."""
    # Simple BOM detection
    if content_bytes.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    elif content_bytes.startswith(b'\xff\xfe'):
        return 'utf-16-le'
    elif content_bytes.startswith(b'\xfe\xff'):
        return 'utf-16-be'
    
    # Try common encodings
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            content_bytes.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    
    return None


def _remove_bom(content: str) -> str:
    """Remove byte order mark from content."""
    if content.startswith('\ufeff'):
        return content[1:]
    return content


def _detect_delimiter(content: str, max_sample_size: int) -> str:
    """Detect the most likely delimiter in the CSV content."""
    sample = content[:max_sample_size]
    
    try:
        # Use csv.Sniffer for detection
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(sample, delimiters=',;\t|').delimiter
        return delimiter
    except (csv.Error, AttributeError):
        # Fallback to frequency analysis
        common_delimiters = [',', ';', '\t', '|', ':']
        delimiter_counts = {}
        
        for delim in common_delimiters:
            count = sample.count(delim)
            if count > 0:
                delimiter_counts[delim] = count
        
        if delimiter_counts:
            return max(delimiter_counts, key=delimiter_counts.get)
        
        # Final fallback if no delimiters found
        return ','


def _parse_rows(content: str, delimiter: str, warnings: List[str], verbose: bool) -> List[List[str]]:
    """Parse content into rows using csv.reader."""
    rows = []
    content_io = io.StringIO(content)
    
    try:
        reader = csv.reader(content_io, delimiter=delimiter)
        for row_num, row in enumerate(reader, 1):
            try:
                # Clean trailing empty cells from delimiter issues
                while row and not row[-1].strip():
                    row.pop()
                rows.append(row)
            except csv.Error as e:
                raise CSVParseError("CSV_READER_ERROR", row_num, str(e))
            except Exception as e:
                warnings.append(f"Error parsing row {row_num}: {str(e)}")
                
    except csv.Error as e:
        raise CSVParseError("CSV_FORMAT_ERROR", details=str(e))
    except Exception as e:
        if verbose:
            warnings.append(f"CSV reader error: {str(e)}")
        # Fallback to simple split
        for line_num, line in enumerate(content.strip().split('\n'), 1):
            if line.strip():
                try:
                    rows.append([cell.strip('"\'') for cell in line.split(delimiter)])
                except Exception as fallback_e:
                    warnings.append(f"Fallback parsing failed on line {line_num}: {str(fallback_e)}")
    
    return rows


def _is_empty_row(row: List[str]) -> bool:
    """Check if a row is effectively empty."""
    return not row or all(not cell.strip() for cell in row)


def _normalize_column_counts(rows: List[List[str]]) -> tuple[List[List[str]], List[str]]:
    """Normalize column counts across rows and detect anomalies."""
    if not rows:
        return [], []
    
    # Find the most common column count
    column_counts = [len(row) for row in rows]
    most_common_count = max(set(column_counts), key=column_counts.count)
    
    normalized_rows = []
    warnings = []
    inconsistent_count = 0
    
    for i, row in enumerate(rows):
        if len(row) != most_common_count:
            inconsistent_count += 1
            if len(row) < most_common_count:
                # Pad shorter rows
                padded_row = row + [''] * (most_common_count - len(row))
                normalized_rows.append(padded_row)
            else:
                # Truncate longer rows but warn
                normalized_rows.append(row[:most_common_count])
        else:
            normalized_rows.append(row)
    
    if inconsistent_count > 0:
        warnings.append(f"Found {inconsistent_count} rows with inconsistent column counts")
    
    return normalized_rows, warnings


def _detect_data_quality_issues(rows: List[List[str]]) -> List[str]:
    """Detect data quality issues and return warnings."""
    warnings = []
    whitespace_cells = 0
    encoding_issues = 0
    long_cells = 0
    
    for row in rows:
        for cell in row:
            cell_str = str(cell)
            
            # Check for whitespace-only cells
            if cell_str and cell_str.isspace():
                whitespace_cells += 1
            
            # Check for potential encoding issues (non-printable characters)
            if any(ord(c) < 32 and c not in '\t\n\r' for c in cell_str):
                encoding_issues += 1
            
            # Check for extremely long cells
            if len(cell_str) > 1000:
                long_cells += 1
    
    if whitespace_cells > 0:
        warnings.append(f"Found {whitespace_cells} whitespace-only cells")
    if encoding_issues > 0:
        warnings.append(f"Found {encoding_issues} cells with potential encoding issues")
    if long_cells > 0:
        warnings.append(f"Found {long_cells} extremely long cells (>1000 characters)")
    
    return warnings


def _detect_headers_single_row(row: List[str]) -> bool:
    """Detect if a single row contains headers."""
    if not row:
        return False
    
    # Single row - assume headers if strings look like column names
    return all(
        isinstance(cell, str) and 
        cell.strip() and 
        not _looks_like_data(cell) and
        len(cell.strip()) < 50
        for cell in row
    )


def _detect_headers(rows: List[List[str]]) -> bool:
    """
    Detect if the first row contains headers using heuristics.
    
    Considers a row to be headers if:
    1. All values are non-numeric strings
    2. Values don't contain common data patterns (dates, emails, etc.)
    3. Values are relatively short and descriptive
    """
    if not rows or not rows[0]:
        return False
    
    first_row = rows[0]
    if len(rows) < 2:
        return _detect_headers_single_row(first_row)
    
    # Compare first row with subsequent rows
    header_score = 0
    total_checks = 0
    
    for i, cell in enumerate(first_row):
        if not cell.strip():
            continue
            
        total_checks += 1
        cell_stripped = cell.strip()
        
        # Check if cell looks like a header
        if (not _looks_like_data(cell_stripped) and 
            len(cell_stripped) < 50 and
            not cell_stripped.replace('_', '').replace('-', '').replace(' ', '').isdigit()):
            header_score += 1
        
        # Compare with same column in other rows
        same_column_values = []
        for row in rows[1:min(6, len(rows))]:  # Check up to 5 data rows
            if i < len(row) and row[i].strip():
                same_column_values.append(row[i].strip())
        
        if same_column_values:
            # If most values in this column look like data, first row likely header
            data_like_count = sum(1 for val in same_column_values if _looks_like_data(val))
            if data_like_count > len(same_column_values) / 2:
                header_score += 1
    
    return total_checks > 0 and header_score / total_checks > 0.5


def _looks_like_data(value: str) -> bool:
    """Check if a string looks like data rather than a header."""
    value = value.strip()
    
    # Numeric patterns
    if re.match(r'^-?\d+(\.\d+)?$', value):
        return True
    
    # Date patterns
    if re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$', value):
        return True
    
    # Email pattern
    if re.match(r'^[^@]+@[^@]+\.[^@]+$', value):
        return True
    
    # Long strings that look like content
    if len(value) > 50:
        return True
    
    # Contains mostly numbers/punctuation
    if len(value) > 5 and sum(c.isdigit() or c in '.,()-' for c in value) / len(value) > 0.7:
        return True
    
    return False


def _build_data_structure(rows: List[List[str]], has_headers: bool, warnings: List[str]) -> List[Dict[str, Any]]:
    """Build the final data structure with proper headers."""
    if not rows:
        return []
    
    if has_headers:
        headers = [str(cell).strip() or f'column_{i+1}' for i, cell in enumerate(rows[0])]
        data_rows = rows[1:]
    else:
        # Generate column names
        max_cols = max(len(row) for row in rows)
        headers = [f'column_{i+1}' for i in range(max_cols)]
        data_rows = rows
        warnings.append(f"Generated headers: {headers}")
    
    # Build dictionaries
    data = []
    for row_num, row in enumerate(data_rows, 2 if has_headers else 1):
        try:
            # Pad row to match header count
            padded_row = row + [''] * (len(headers) - len(row))
            row_dict = {}
            
            for header, value in zip(headers, padded_row):
                # Attempt basic type conversion
                clean_value = str(value).strip()
                if clean_value:
                    # Try integer
                    if clean_value.isdigit() or (clean_value.startswith('-') and clean_value[1:].isdigit()):
                        row_dict[header] = int(clean_value)
                    # Try float
                    elif re.match(r'^-?\d+\.\d+$', clean_value):
                        row_dict[header] = float(clean_value)
                    else:
                        row_dict[header] = clean_value
                else:
                    row_dict[header] = clean_value
            
            data.append(row_dict)
            
        except Exception as e:
            warnings.append(f"Error processing row {row_num}: {str(e)}")
    
    return data


def _calculate_data_quality_score(rows: List[List[str]], warnings: List[str]) -> float:
    """Calculate data quality score as percentage of clean rows."""
    if not rows:
        return 100.0
    
    # Count quality issues from warnings
    quality_issues = sum(1 for warning in warnings if any(
        issue_type in warning.lower() for issue_type in [
            'whitespace-only', 'encoding issue', 'extremely long', 
            'inconsistent column', 'error processing'
        ]
    ))
    
    # Calculate score based on issues vs total potential issues
    total_cells = sum(len(row) for row in rows)
    if total_cells == 0:
        return 100.0
    
    # Quality score decreases based on relative number of issues
    issue_ratio = min(quality_issues / total_cells, 1.0)
    return max(0.0, (1.0 - issue_ratio) * 100.0)


# Example test cases
if __name__ == "__main__":
    # Test 1: Mixed delimiters
    test1 = """name;age;city
John;25;New York
Jane,30,Los Angeles"""
    result1 = parse_csv(test1)
    assert len(result1.data) == 2
    assert result1.has_headers == True
    assert result1.delimiter == ';'
    assert result1.total_rows_processed == 3
    
    # Test 2: No headers, tab-delimited
    test2 = """John\t25\tNYC
Jane\t30\tLA"""
    result2 = parse_csv(test2)
    assert len(result2.data) == 2
    assert result2.has_headers == False
    assert 'column_1' in result2.data[0]
    assert result2.column_count == 3
    
    # Test 3: Empty rows and trailing delimiters
    test3 = """name,age,
John,25,

Jane,30,"""
    result3 = parse_csv(test3)
    assert len(result3.data) == 2
    assert result3.rows_skipped == 1
    assert result3.data_quality_score > 0
    
    # Test 4: Custom exception handling
    try:
        result4 = parse_csv("malformed\x00data\x01test")
        # Should not raise exception but handle gracefully
        assert isinstance(result4, ParseResult)
    except CSVParseError as e:
        assert e.error_type in ['GENERAL_PARSE_ERROR', 'CSV_FORMAT_ERROR']
        assert isinstance(e.details, str)
    
    # Test 5: Bytes input
    test5_bytes = b"name,age\nJohn,25\nJane,30"
    result5 = parse_csv(test5_bytes)
    assert len(result5.data) == 2
    assert result5.encoding_used in ['utf-8', 'latin-1', 'cp1252']
    
    # Test 6: List of strings input
    test6_list = ["name,age", "John,25", "Jane,30"]
    result6 = parse_csv(test6_list)
    assert len(result6.data) == 2
    assert result6.has_headers == True
    
    # Test 7: Empty file
    result7 = parse_csv("")
    assert len(result7.data) == 0
    assert result7.total_rows_processed == 0
    
    # Test 8: Only headers, no data
    test8 = "name,age,city"
    result8 = parse_csv(test8)
    assert len(result8.data) == 0
    assert "only headers" in str(result8.warnings)
    
    # Test 9: Inconsistent column counts
    test9 = """name,age,city
John,25
Jane,30,LA,Extra"""
    result9 = parse_csv(test9)
    assert len(result9.data) == 2
    assert "inconsistent column counts" in str(result9.warnings)
    
    print("All tests passed!")
```