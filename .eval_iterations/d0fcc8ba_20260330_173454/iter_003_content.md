```python
"""CSV parser for messy data with inconsistent delimiters and missing headers."""

import csv
import io
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, IO, List, Dict, Union, Optional, Tuple
from collections import Counter


@dataclass
class ErrorInfo:
    """Structured error information."""
    error_type: str
    error_message: str
    line_number: Optional[int] = None
    severity_level: str = "warning"  # "warning", "error", "critical"


@dataclass
class ParseResult:
    """Result of CSV parsing operation."""
    data: List[Dict[str, str]]
    warnings: List[ErrorInfo]
    rows_skipped: int
    delimiter_used: str
    headers_detected: bool
    total_rows: int
    processing_time_ms: float
    confidence_score: float
    detected_encoding: str
    estimated_data_quality_score: float
    column_statistics: Dict[str, Dict[str, Any]]
    data_quality_issues: List[ErrorInfo]


def parse_csv(
    source: Union[str, Path, IO],
    fallback_delimiter: str = ',',
    max_header_detection_rows: int = 5,
    generate_headers: bool = True
) -> ParseResult:
    """
    Parse messy CSV data with inconsistent delimiters and missing headers.
    
    Auto-detects delimiters and handles missing headers by generating column names
    or detecting existing headers heuristically. The csv.reader automatically handles
    quoted fields and escaped quotes according to CSV standards.
    
    Args:
        source: File path, string content, or file-like object
        fallback_delimiter: Delimiter to use if detection fails
        max_header_detection_rows: Number of rows to examine for header detection
        generate_headers: Whether to generate headers when none detected
    
    Returns:
        ParseResult with parsed data, warnings, and metadata
    
    Example:
        >>> content = "name;age;city\\nAlice;30;NYC\\nBob;25;LA"
        >>> result = parse_csv(content)
        >>> result.data[0]
        {'name': 'Alice', 'age': '30', 'city': 'NYC'}
    """
    start_time = time.time()
    warnings: List[ErrorInfo] = []
    data_quality_issues: List[ErrorInfo] = []
    
    try:
        # Normalize input to string content
        content, detected_encoding = _get_content_string(source)
        if not content.strip():
            return ParseResult(
                data=[],
                warnings=[ErrorInfo("input", "Empty input", severity_level="error")],
                rows_skipped=0,
                delimiter_used=fallback_delimiter,
                headers_detected=False,
                total_rows=0,
                processing_time_ms=(time.time() - start_time) * 1000,
                confidence_score=0.0,
                detected_encoding=detected_encoding,
                estimated_data_quality_score=0.0,
                column_statistics={},
                data_quality_issues=[]
            )
        
        # Enhanced delimiter detection
        delimiter, confidence = _detect_delimiter_with_confidence(content, fallback_delimiter)
        
        # Parse initial rows for header detection
        sample_rows = _parse_sample_rows(content, delimiter, max_header_detection_rows)
        if not sample_rows:
            return ParseResult(
                data=[],
                warnings=[ErrorInfo("parsing", "No valid rows found", severity_level="error")],
                rows_skipped=0,
                delimiter_used=delimiter,
                headers_detected=False,
                total_rows=0,
                processing_time_ms=(time.time() - start_time) * 1000,
                confidence_score=confidence,
                detected_encoding=detected_encoding,
                estimated_data_quality_score=0.0,
                column_statistics={},
                data_quality_issues=[]
            )
        
        # Detect if headers are present
        has_headers = _detect_headers(sample_rows)
        
        # Parse all data
        all_rows, skipped_count, parse_warnings = _parse_all_rows(content, delimiter)
        warnings.extend(parse_warnings)
        
        # Process headers and data
        if has_headers and all_rows:
            headers = all_rows[0]
            data_rows = all_rows[1:]
        else:
            headers = _generate_headers(sample_rows[0] if sample_rows else [], generate_headers)
            data_rows = all_rows
        
        # Validate data integrity
        integrity_warnings = _validate_data_integrity(headers, data_rows)
        data_quality_issues.extend(integrity_warnings)
        
        # Convert to list of dictionaries
        data, conversion_warnings = _rows_to_dicts(headers, data_rows)
        warnings.extend(conversion_warnings)
        
        # Calculate column statistics
        column_stats = _calculate_column_statistics(headers, data_rows)
        
        # Estimate data quality score
        quality_score = _estimate_data_quality(data_quality_issues, warnings, len(data_rows))
        
        return ParseResult(
            data=data,
            warnings=warnings,
            rows_skipped=skipped_count,
            delimiter_used=delimiter,
            headers_detected=has_headers,
            total_rows=len(all_rows),
            processing_time_ms=(time.time() - start_time) * 1000,
            confidence_score=confidence,
            detected_encoding=detected_encoding,
            estimated_data_quality_score=quality_score,
            column_statistics=column_stats,
            data_quality_issues=data_quality_issues
        )
    
    except FileNotFoundError:
        return ParseResult(
            data=[],
            warnings=[ErrorInfo("file", "File not found", severity_level="error")],
            rows_skipped=0,
            delimiter_used=fallback_delimiter,
            headers_detected=False,
            total_rows=0,
            processing_time_ms=(time.time() - start_time) * 1000,
            confidence_score=0.0,
            detected_encoding="unknown",
            estimated_data_quality_score=0.0,
            column_statistics={},
            data_quality_issues=[]
        )
    except UnicodeDecodeError as e:
        return ParseResult(
            data=[],
            warnings=[ErrorInfo("encoding", f"Encoding error: {str(e)}", severity_level="error")],
            rows_skipped=0,
            delimiter_used=fallback_delimiter,
            headers_detected=False,
            total_rows=0,
            processing_time_ms=(time.time() - start_time) * 1000,
            confidence_score=0.0,
            detected_encoding="error",
            estimated_data_quality_score=0.0,
            column_statistics={},
            data_quality_issues=[]
        )
    except Exception as e:
        return ParseResult(
            data=[],
            warnings=[ErrorInfo("parsing", f"Parse error: {str(e)}", severity_level="critical")],
            rows_skipped=0,
            delimiter_used=fallback_delimiter,
            headers_detected=False,
            total_rows=0,
            processing_time_ms=(time.time() - start_time) * 1000,
            confidence_score=0.0,
            detected_encoding="unknown",
            estimated_data_quality_score=0.0,
            column_statistics={},
            data_quality_issues=[]
        )


def _get_content_string(source: Union[str, Path, IO]) -> Tuple[str, str]:
    """Convert various input types to string content with encoding detection."""
    detected_encoding = "utf-8"
    
    if isinstance(source, (str, Path)):
        if isinstance(source, Path) or (isinstance(source, str) and 
                                       (source.endswith('.csv') or '/' in source or '\\' in source)):
            # Treat as file path
            try:
                with open(source, 'r', encoding='utf-8-sig', newline='') as f:
                    content = f.read()
                detected_encoding = "utf-8-sig"
            except UnicodeDecodeError:
                # Fallback to latin-1 if UTF-8 fails
                with open(source, 'r', encoding='latin-1', newline='') as f:
                    content = f.read()
                detected_encoding = "latin-1"
        else:
            # Treat as string content
            content = str(source)
    else:
        # File-like object
        content = source.read()
    
    # Normalize line endings and handle whitespace-only content
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Check for non-printable characters that might indicate encoding issues
    non_printable_count = sum(1 for c in content if ord(c) < 32 and c not in '\n\t\r')
    if non_printable_count > len(content) * 0.01:  # More than 1% non-printable
        detected_encoding += "-with-issues"
    
    return content, detected_encoding


def _detect_delimiter_with_confidence(content: str, fallback: str) -> Tuple[str, float]:
    """Enhanced delimiter detection with confidence scoring."""
    try:
        # Handle edge cases first
        if not content.strip():
            return fallback, 0.0
        
        lines = [line for line in content.split('\n') if line.strip()]
        if len(lines) < 2:
            return fallback, 0.0
        
        # Use reasonable sample size, handle extremely long lines
        sample_lines = []
        for line in lines[:10]:  # Use more lines for better detection
            if len(line) > 10000:  # Handle extremely long lines
                sample_lines.append(line[:10000])
            else:
                sample_lines.append(line)
        
        sample = '\n'.join(sample_lines)
        
        # Try csv.Sniffer first
        sniffer = csv.Sniffer()
        detected_delimiter = sniffer.sniff(sample, delimiters=',;\t|').delimiter
        
        # Validate delimiter produces consistent column counts
        consistency_score = _validate_delimiter_consistency(sample_lines, detected_delimiter)
        
        if consistency_score > 0.8:
            return detected_delimiter, consistency_score
        
    except (csv.Error, AttributeError):
        pass
    
    # Enhanced fallback: statistical analysis across multiple lines
    delimiters = [',', ';', '\t', '|']
    delimiter_scores = {}
    
    sample_lines = [line for line in content.split('\n')[:10] if line.strip()]
    
    for delim in delimiters:
        counts = [line.count(delim) for line in sample_lines if line.strip()]
        if not counts:
            delimiter_scores[delim] = 0.0
            continue
            
        # Score based on frequency and consistency
        avg_count = sum(counts) / len(counts)
        consistency = 1.0 - (max(counts) - min(counts)) / max(1, max(counts))
        delimiter_scores[delim] = avg_count * consistency
    
    if delimiter_scores:
        best_delimiter = max(delimiter_scores, key=delimiter_scores.get)
        confidence = min(1.0, delimiter_scores[best_delimiter] / 10.0)  # Normalize to 0-1
        
        # Validate the best delimiter
        sample_lines = content.split('\n')[:5]
        consistency = _validate_delimiter_consistency(sample_lines, best_delimiter)
        
        return best_delimiter, confidence * consistency
    
    return fallback, 0.1


def _validate_delimiter_consistency(lines: List[str], delimiter: str) -> float:
    """Validate that delimiter produces consistent column counts."""
    try:
        column_counts = []
        for line in lines:
            if line.strip():
                # Use csv.reader for proper parsing
                reader = csv.reader(io.StringIO(line), delimiter=delimiter)
                row = next(reader)
                column_counts.append(len(row))
        
        if not column_counts:
            return 0.0
        
        # Calculate consistency score
        unique_counts = set(column_counts)
        if len(unique_counts) == 1:
            return 1.0  # Perfect consistency
        
        # Penalize inconsistency
        consistency = 1.0 - (len(unique_counts) - 1) / len(column_counts)
        return max(0.0, consistency)
        
    except (csv.Error, StopIteration):
        return 0.0


def _parse_sample_rows(content: str, delimiter: str, max_rows: int) -> List[List[str]]:
    """Parse first few rows for header detection with enhanced error handling."""
    try:
        reader = csv.reader(io.StringIO(content), delimiter=delimiter, skipinitialspace=True)
        rows = []
        
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            if any(field.strip() for field in row):  # Skip empty rows
                # Handle potential quoting issues within unquoted fields
                cleaned_row = []
                for field in row:
                    cleaned_field = field.strip()
                    # Check for delimiter appearing in unquoted fields (data quality issue)
                    if delimiter in cleaned_field and not (cleaned_field.startswith('"') and cleaned_field.endswith('"')):
                        cleaned_field = cleaned_field.replace(delimiter, f"[{delimiter}]")  # Escape for safety
                    cleaned_row.append(cleaned_field)
                rows.append(cleaned_row)
                
    except csv.Error:
        return []
    
    return rows


def _detect_headers(sample_rows: List[List[str]]) -> bool:
    """Heuristically detect if first row contains headers."""
    if len(sample_rows) < 2:
        return False
    
    first_row = sample_rows[0]
    
    # Check for numeric patterns - headers are typically non-numeric
    numeric_count = sum(1 for field in first_row if field.replace('.', '').replace('-', '').isdigit())
    if numeric_count > len(first_row) * 0.5:
        return False
    
    # Check for common header patterns
    header_indicators = ['name', 'id', 'date', 'time', 'count', 'value', 'type']
    header_score = sum(1 for field in first_row 
                      if any(indicator in field.lower() for indicator in header_indicators))
    
    # Compare with subsequent rows for consistency
    if len(sample_rows) > 1:
        second_row = sample_rows[1]
        if len(first_row) == len(second_row):
            # Headers often have different character patterns than data
            first_alpha_ratio = sum(1 for field in first_row if field.isalpha()) / len(first_row)
            second_alpha_ratio = sum(1 for field in second_row if field.isalpha()) / len(second_row)
            
            if first_alpha_ratio > 0.5 and second_alpha_ratio < 0.3:
                return True
    
    return header_score > 0


def _read_csv_rows(content: str, delimiter: str) -> List[List[str]]:
    """Read CSV rows using csv.reader with enhanced error handling."""
    try:
        reader = csv.reader(io.StringIO(content), delimiter=delimiter, skipinitialspace=True)
        rows = []
        
        for row in reader:
            rows.append(row)
        
        return rows
        
    except csv.Error as e:
        # Handle inconsistent quoting styles
        if "newline inside string" in str(e).lower():
            # Try with different quoting style
            try:
                reader = csv.reader(io.StringIO(content), delimiter=delimiter, 
                                  skipinitialspace=True, quoting=csv.QUOTE_NONE)
                return list(reader)
            except csv.Error:
                return []
        raise


def _process_parsed_rows(rows: List[List[str]]) -> Tuple[List[List[str]], int, List[ErrorInfo]]:
    """Process parsed rows with enhanced validation and error reporting."""
    valid_rows = []
    skipped = 0
    warnings: List[ErrorInfo] = []
    
    for line_num, row in enumerate(rows, 1):
        try:
            # Skip completely empty rows (whitespace only)
            if not any(field.strip() for field in row):
                skipped += 1
                continue
            
            # Clean up row data and detect anomalies
            cleaned_row = []
            for field in row:
                cleaned_field = field.strip()
                
                # Check for extremely long fields (potential data quality issue)
                if len(cleaned_field) > 1000:
                    warnings.append(ErrorInfo(
                        "data_quality", 
                        f"Extremely long field in row {line_num} (length: {len(cleaned_field)})",
                        line_num, 
                        "warning"
                    ))
                
                cleaned_row.append(cleaned_field)
            
            valid_rows.append(cleaned_row)
            
        except Exception as e:
            skipped += 1
            warnings.append(ErrorInfo(
                "parsing", 
                f"Skipped malformed row {line_num}: {str(e)}",
                line_num, 
                "error"
            ))
    
    return valid_rows, skipped, warnings


def _parse_all_rows(content: str, delimiter: str) -> Tuple[List[List[str]], int, List[ErrorInfo]]:
    """Parse all rows with comprehensive error handling."""
    try:
        raw_rows = _read_csv_rows(content, delimiter)
        return _process_parsed_rows(raw_rows)
    except csv.Error as e:
        return [], 0, [ErrorInfo("parsing", f"CSV parsing error: {str(e)}", severity_level="critical")]


def _generate_headers(first_row: List[str], generate: bool) -> List[str]:
    """Generate column headers when none are detected."""
    if not generate:
        return [f"column_{i}" for i in range(len(first_row))]
    
    return [f"col_{i+1}" for i in range(len(first_row))]


def _validate_data_integrity(headers: List[str], data_rows: List[List[str]]) -> List[ErrorInfo]:
    """Validate data integrity and detect anomalies."""
    issues: List[ErrorInfo] = []
    
    # Check for duplicate headers
    header_counts = Counter(headers)
    duplicates = [header for header, count in header_counts.items() if count > 1]
    if duplicates:
        issues.append(ErrorInfo(
            "data_integrity", 
            f"Duplicate headers found: {duplicates}",
            severity_level="warning"
        ))
    
    # Check for rows where all fields are identical
    for row_num, row in enumerate(data_rows, 1):
        if len(set(row)) == 1 and row[0].strip():  # All identical non-empty values
            issues.append(ErrorInfo(
                "data_quality", 
                f"Row {row_num}: All fields contain identical value '{row[0]}'",
                row_num, 
                "warning"
            ))
    
    # Check for encoding issues (non-printable characters)
    for row_num, row in enumerate(data_rows, 1):
        for col_num, field in enumerate(row):
            non_printable = [c for c in field if ord(c) < 32 and c not in '\n\t\r']
            if non_printable:
                issues.append(ErrorInfo(
                    "encoding", 
                    f"Non-printable characters in row {row_num}, column {col_num+1}",
                    row_num, 
                    "warning"
                ))
    
    return issues


def _rows_to_dicts(headers: List[str], data_rows: List[List[str]]) -> Tuple[List[Dict[str, str]], List[ErrorInfo]]:
    """Convert rows to list of dictionaries with enhanced error reporting."""
    result = []
    warnings: List[ErrorInfo] = []
    header_count = len(headers)
    
    for row_num, row in enumerate(data_rows, 1):
        if len(row) != header_count:
            if len(row) > header_count:
                warnings.append(ErrorInfo(
                    "data_integrity", 
                    f"Row {row_num}: Extra columns truncated ({len(row)} -> {header_count})",
                    row_num, 
                    "warning"
                ))
                row = row[:header_count]
            else:
                warnings.append(ErrorInfo(
                    "data_integrity", 
                    f"Row {row_num}: Missing columns padded with empty strings ({len(row)} -> {header_count})",
                    row_num, 
                    "warning"
                ))
                row.extend([''] * (header_count - len(row)))
        
        result.append(dict(zip(headers, row)))
    
    return result, warnings


def _calculate_column_statistics(headers: List[str], data_rows: List[List[str]]) -> Dict[str, Dict[str, Any]]:
    """Calculate basic statistics for each column."""
    stats = {}
    
    for col_idx, header in enumerate(headers):
        column_values = []
        non_empty_count = 0
        
        for row in data_rows:
            if col_idx < len(row):
                value = row[col_idx].strip()
                column_values.append(value)
                if value:
                    non_empty_count += 1
        
        unique_values = list(set(column_values))
        unique_sample = unique_values[:5]  # Sample of unique values
        
        stats[header] = {
            "non_empty_count": non_empty_count,
            "unique_values_sample": unique_sample,
            "total_unique": len(unique_values),
            "fill_rate": non_empty_count / len(data_rows) if data_rows else 0.0
        }
    
    return stats


def _estimate_data_quality(data_quality_issues: List[ErrorInfo], warnings: List[ErrorInfo], total_rows: int) -> float:
    """Estimate overall data quality score (0.0 to 1.0)."""
    if total_rows == 0:
        return 0.0
    
    # Count different types of issues
    critical_issues = len([w for w in warnings + data_quality_issues if w.severity_level == "critical"])
    error_issues = len([w for w in warnings + data_quality_issues if w.severity_level == "error"])
    warning_issues = len([w for w in warnings + data_quality_issues if w.severity_level == "warning"])
    
    # Calculate penalty based on issue severity
    penalty = (critical_issues * 0.3 + error_issues * 0.2 + warning_issues * 0.1) / max(1, total_rows)
    quality_score = max(0.0, 1.0 - penalty)
    
    return min(1.0, quality_score)


# Test examples
def _test_parse_csv():
    """Test cases demonstrating functionality."""
    
    # Test 1: Semicolon delimiter with headers
    test1 = "name;age;city\nAlice;30;NYC\nBob;25;LA"
    result1 = parse_csv(test1)
    assert result1.delimiter_used == ';'
    assert result1.headers_detected == True
    assert len(result1.data) == 2
    assert result1.data[0]['name'] == 'Alice'
    
    # Test 2: No headers, comma delimiter
    test2 = "Alice,30,NYC\nBob,25,LA"
    result2 = parse_csv(test2)
    assert result2.headers_detected == False
    assert 'col_1' in result2.data[0]
    
    # Test 3: Messy data with empty rows
    test3 = "name|age|city\n\nAlice|30|NYC\n|||\nBob|25|LA"
    result3 = parse_csv(test3)
    assert result3.rows_skipped == 2
    assert len(result3.data) == 2
    
    # Test 4: Quoted fields with escaped quotes
    test4 = 'name,description\nAlice,"Product with ""quotes"" inside"\nBob,"Simple text"'
    result4 = parse_csv(test4)
    assert result4.data[0]['description'] == 'Product with "quotes" inside'
    assert len(result4.data) == 2
    
    # Test 5: Multi-line quoted fields
    test5 = 'name,address\nAlice,"123 Main St\nApt 4B"\nBob,"456 Oak Ave"'
    result5 = parse_csv(test5)
    assert '\n' in result5.data[0]['address']
    assert len(result5.data) == 2
    
    # Test 6: Mixed line endings
    test6 = "name,age\r\nAlice,30\rBob,25\n"
    result6 = parse_csv(test6)
    assert len(result6.data) == 2
    assert result6.data[0]['name'] == 'Alice'
    
    # Test 7: Empty file
    test7 = ""
    result7 = parse_csv(test7)
    assert len(result7.data) == 0
    assert any("Empty input" in w.error_message for w in result7.warnings)
    
    # Test 8: Single column data
    test8 = "names\nAlice\nBob\nCharlie"
    result8 = parse_csv(test8)
    assert result8.headers_detected == True
    assert len(result8.data) == 3
    assert result8.data[0]['names'] == 'Alice'
    
    # Test 9: File with only headers
    test9 = "name,age,city"
    result9 = parse_csv(test9)
    assert result9.headers_detected == False  # Single row can't be determined as header
    assert len(result9.data) == 1
    
    # Test 10: File with BOM (simulated)
    test10 = "\ufeffname,age\nAlice,30\nBob,25"
    result10 = parse_csv(test10)
    assert len(result10.data) == 2
    assert result10.data[0]['name'] == 'Alice'
    
    # Test 11: Malformed CSV with inconsistent quotes
    test11 = 'name,desc\nAlice,"unclosed quote\nBob,"proper quote"'
    result11 = parse_csv(test11)
    assert len(result11.warnings) > 0 or len(result11.data) >= 1  # Should handle gracefully
    
    # Test 12: Check warnings content
    test12 = "a,b,c\n1,2\n3,4,5,6"
    result12 = parse_csv(test12)
    warning_messages = ' '.join([w.error_message for w in result12.warnings])
    assert "Missing columns padded" in warning_messages
    assert "Extra columns truncated" in warning_messages
    
    print("All tests passed!")


if __name__ == "__main__":
    _test_parse_csv()
```