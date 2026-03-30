```python
from typing import Union, List, Dict, Any, TextIO
from dataclasses import dataclass
from pathlib import Path
import csv
import io
import re
import codecs


@dataclass
class ParseResult:
    """Result of CSV parsing operation."""
    data: List[Dict[str, str]]
    warnings: List[str]
    rows_processed: int
    rows_skipped: int
    delimiter: str
    has_header: bool


def validate_input(source: Union[str, Path, TextIO]) -> str:
    """
    Validate and convert input to string content.
    
    Args:
        source: Input source (file path, string, or file object)
        
    Returns:
        String content from the source
    """
    if isinstance(source, (str, Path)):
        if isinstance(source, str) and (len(source) < 260 and ('\n' in source or ',' in source or ';' in source or '\t' in source)):
            # Likely CSV content, not a file path
            return source
        # Treat as file path
        try:
            path = Path(source)
            with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
                return f.read()
        except (UnicodeDecodeError, IOError, OSError) as e:
            # If file reading fails, treat as content string
            return str(source)
    elif hasattr(source, 'read'):
        # File-like object
        original_position = None
        if hasattr(source, 'tell'):
            try:
                original_position = source.tell()
            except (OSError, io.UnsupportedOperation):
                pass
        
        content = source.read()
        
        # Reset file position to maintain pure function behavior
        if hasattr(source, 'seek') and original_position is not None:
            try:
                source.seek(original_position)
            except (OSError, io.UnsupportedOperation):
                pass
        
        return content
    else:
        return str(source)


def normalize_content(content: str) -> tuple[str, List[str]]:
    """
    Normalize CSV content by handling encoding issues and line endings.
    
    Args:
        content: Raw content string
        
    Returns:
        Tuple of (normalized_content, warnings)
    """
    warnings = []
    
    # Remove BOM if present
    if content.startswith('\ufeff'):
        content = content[1:]
        warnings.append("Removed BOM (Byte Order Mark) from content")
    
    # Normalize line endings
    original_endings = set(re.findall(r'\r\n|\r|\n', content))
    if len(original_endings) > 1:
        warnings.append(f"Mixed line endings detected: {original_endings}")
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Check for extremely long fields that might cause issues
    lines = content.split('\n')
    max_field_length = 0
    for line in lines[:100]:  # Check first 100 lines for performance
        if len(line) > max_field_length:
            max_field_length = len(line)
    
    if max_field_length > 131072:  # 128KB limit
        warnings.append(f"Very long fields detected (max: {max_field_length} chars), may cause performance issues")
    
    return content.strip(), warnings


def detect_delimiter(sample: str) -> tuple[str, List[str]]:
    """
    Detect the most likely delimiter in a CSV sample using advanced analysis.
    
    Args:
        sample: Sample text from CSV file
        
    Returns:
        Tuple of (detected_delimiter, warnings)
    """
    warnings = []
    
    # First try csv.Sniffer with comprehensive delimiter set
    try:
        sniffer = csv.Sniffer()
        # Use larger sample for better detection
        sample_size = min(len(sample), 8192)
        delimiter = sniffer.sniff(sample[:sample_size], delimiters=',;\t|:').delimiter
        
        # Validate the detected delimiter makes sense
        lines = sample.split('\n')[:10]  # Check first 10 lines
        field_counts = []
        for line in lines:
            if line.strip():
                field_counts.append(line.count(delimiter))
        
        if field_counts and len(set(field_counts)) <= 2:  # Consistent field counts
            return delimiter, warnings
    except (csv.Error, AttributeError) as e:
        warnings.append(f"csv.Sniffer failed with {type(e).__name__}: {str(e)}, using fallback delimiter detection")
    
    # Advanced fallback: analyze delimiter patterns in context
    delimiters = [',', ';', '\t', '|', ':']
    lines = [line for line in sample.split('\n')[:20] if line.strip()]
    
    if not lines:
        return ',', warnings
    
    delimiter_scores = {}
    
    for delim in delimiters:
        score = 0
        field_counts = []
        
        for line in lines:
            count = line.count(delim)
            field_counts.append(count)
            
            # Bonus for consistent field counts across lines
            if count > 0:
                score += count
        
        # Consistency bonus
        if field_counts:
            unique_counts = len(set(field_counts))
            if unique_counts <= 2:  # Very consistent
                score *= 2
            elif unique_counts <= 3:  # Moderately consistent
                score *= 1.5
        
        # Penalty for delimiters that appear in quoted content
        quote_sections = re.findall(r'"[^"]*"', sample)
        for quote_section in quote_sections:
            if delim in quote_section:
                score *= 0.8  # Reduce score if delimiter appears in quotes
        
        delimiter_scores[delim] = score
    
    best_delimiter = max(delimiter_scores, key=delimiter_scores.get)
    
    if delimiter_scores[best_delimiter] == 0:
        warnings.append("No clear delimiter pattern detected, defaulting to comma")
        return ',', warnings
    
    return best_delimiter, warnings


def detect_headers(first_row: List[str], second_row: List[str] = None, all_rows: List[List[str]] = None) -> tuple[bool, List[str]]:
    """
    Enhanced heuristic determination of header presence with data type analysis.
    
    Args:
        first_row: First row of data
        second_row: Second row of data (optional)
        all_rows: All rows for statistical analysis (optional)
        
    Returns:
        Tuple of (has_header, warnings)
    """
    warnings = []
    
    if not first_row:
        return False, warnings
    
    header_indicators = 0
    total_checks = 0
    
    # Check 1: Numeric pattern analysis
    first_numeric = sum(1 for cell in first_row if cell.strip().replace('.', '').replace('-', '').replace('+', '').isdigit())
    if first_numeric == len(first_row) and len(first_row) > 1:
        # All numeric suggests data row
        header_indicators -= 2
    elif first_numeric == 0:
        # No numeric suggests header row
        header_indicators += 1
    total_checks += 1
    
    # Check 2: Data type consistency analysis
    if second_row and len(second_row) == len(first_row):
        second_numeric = sum(1 for cell in second_row if cell.strip().replace('.', '').replace('-', '').replace('+', '').isdigit())
        if second_numeric > first_numeric:
            header_indicators += 2  # Strong indicator
        total_checks += 1
    
    # Check 3: Header keyword detection (enhanced)
    header_keywords = ['id', 'name', 'date', 'time', 'value', 'count', 'type', 'status', 
                      'code', 'description', 'amount', 'price', 'quantity', 'total',
                      'email', 'phone', 'address', 'city', 'state', 'zip', 'country']
    
    keyword_matches = sum(1 for cell in first_row 
                         if any(keyword in cell.lower().replace('_', '').replace('-', '') 
                               for keyword in header_keywords))
    if keyword_matches > 0:
        header_indicators += keyword_matches
    total_checks += 1
    
    # Check 4: Alphabetic content analysis
    alpha_ratio = len([cell for cell in first_row if cell.strip().isalpha()]) / len(first_row)
    if alpha_ratio >= 0.5:
        header_indicators += 1
    total_checks += 1
    
    # Check 5: Statistical variance analysis (if multiple rows available)
    if all_rows and len(all_rows) > 2:
        try:
            # Analyze variance in column content types
            for col_idx in range(min(len(first_row), len(all_rows[1]) if len(all_rows) > 1 else 0)):
                first_is_numeric = first_row[col_idx].strip().replace('.', '').replace('-', '').isdigit()
                
                # Check if subsequent rows in this column are different type
                subsequent_numeric_count = 0
                for row in all_rows[1:6]:  # Check up to 5 subsequent rows
                    if col_idx < len(row):
                        if row[col_idx].strip().replace('.', '').replace('-', '').isdigit():
                            subsequent_numeric_count += 1
                
                if not first_is_numeric and subsequent_numeric_count > 0:
                    header_indicators += 0.5  # Mild indicator
            
            total_checks += 1
        except (IndexError, ValueError) as e:
            warnings.append(f"Header analysis error during statistical variance check: {type(e).__name__}")
    
    # Check 6: Pattern consistency
    if len(first_row) > 1:
        # Headers often have consistent naming patterns
        has_underscores = sum(1 for cell in first_row if '_' in cell)
        has_camelcase = sum(1 for cell in first_row if re.search(r'[a-z][A-Z]', cell))
        
        if has_underscores > len(first_row) * 0.3 or has_camelcase > len(first_row) * 0.3:
            header_indicators += 1
        total_checks += 1
    
    # Decision logic
    is_header = header_indicators > 0
    
    # Additional validation
    if is_header and all_rows and len(all_rows) > 1:
        # Ensure first row isn't identical to others (which would suggest data)
        identical_to_second = first_row == all_rows[1] if len(all_rows) > 1 else False
        if identical_to_second:
            is_header = False
            warnings.append("First row identical to second row, treating as data")
    
    if total_checks > 0:
        confidence = abs(header_indicators) / total_checks
        if confidence < 0.3:
            warnings.append(f"Low confidence in header detection ({confidence:.2f})")
    
    return is_header, warnings


def generate_headers(num_columns: int) -> List[str]:
    """
    Generate default column headers.
    
    Args:
        num_columns: Number of columns needed
        
    Returns:
        List of generated header names
    """
    return [f'column_{i+1}' for i in range(num_columns)]


def clean_row(row: List[str], expected_columns: int) -> tuple[List[str], List[str]]:
    """
    Clean and normalize a row of data with anomaly detection.
    
    Args:
        row: Raw row data
        expected_columns: Expected number of columns
        
    Returns:
        Tuple of (cleaned_row, warnings)
    """
    warnings = []
    
    # Strip whitespace from all cells
    cleaned = [cell.strip() for cell in row]
    
    # Detect suspicious patterns
    if len(set(cleaned)) == 1 and len(cleaned) > 1 and cleaned[0]:
        warnings.append(f"All cells in row contain identical value: '{cleaned[0]}'")
    
    # Handle column count mismatches
    original_length = len(cleaned)
    if original_length > expected_columns:
        # Truncate extra columns
        cleaned = cleaned[:expected_columns]
        warnings.append(f"Row truncated from {original_length} to {expected_columns} columns")
    elif original_length < expected_columns:
        # Pad with empty strings
        cleaned.extend([''] * (expected_columns - original_length))
        warnings.append(f"Row padded from {original_length} to {expected_columns} columns")
    
    return cleaned, warnings


def analyze_structure(all_rows: List[List[str]], delimiter: str) -> List[str]:
    """
    Analyze CSV structure for potential issues and patterns.
    
    Args:
        all_rows: All parsed rows
        delimiter: Delimiter used for parsing
        
    Returns:
        List of structural analysis warnings
    """
    warnings = []
    
    if not all_rows:
        return warnings
    
    # Analyze column count distribution
    column_counts = [len(row) for row in all_rows]
    unique_counts = set(column_counts)
    
    if len(unique_counts) > 1:
        most_common_count = max(unique_counts, key=column_counts.count)
        irregular_rows = sum(1 for count in column_counts if count != most_common_count)
        warnings.append(f"Irregular column counts: {irregular_rows}/{len(all_rows)} rows differ from mode ({most_common_count})")
    
    # Check for potential delimiter confusion
    total_quotes = sum(row_str.count('"') for row_str in [delimiter.join(row) for row in all_rows[:10]])
    if total_quotes > len(all_rows) * 2:
        warnings.append("High quote usage detected, potential delimiter confusion")
    
    # Analyze data type patterns by column
    if len(all_rows) > 1:
        max_cols = max(len(row) for row in all_rows)
        for col_idx in range(max_cols):
            numeric_count = 0
            date_like_count = 0
            empty_count = 0
            total_count = 0
            
            for row in all_rows[:50]:  # Sample first 50 rows
                if col_idx < len(row):
                    cell = row[col_idx].strip()
                    total_count += 1
                    
                    if not cell:
                        empty_count += 1
                    elif re.match(r'^-?\d+\.?\d*$', cell):
                        numeric_count += 1
                    elif re.match(r'^\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}$', cell):
                        date_like_count += 1
            
            if total_count > 0:
                empty_ratio = empty_count / total_count
                if empty_ratio > 0.5:
                    warnings.append(f"Column {col_idx + 1}: {empty_ratio:.1%} empty cells")
                
                # Check for data type inconsistencies
                if numeric_count > 0 and (total_count - numeric_count - empty_count) > 0:
                    mixed_ratio = (total_count - numeric_count - empty_count) / total_count
                    if mixed_ratio > 0.1:
                        warnings.append(f"Column {col_idx + 1}: Mixed data types detected ({mixed_ratio:.1%} non-numeric)")
    
    return warnings


def build_result_metadata(processed_data: List[Dict[str, str]], 
                         all_warnings: List[str],
                         rows_skipped: int,
                         delimiter: str,
                         has_header: bool) -> ParseResult:
    """
    Build the final ParseResult with comprehensive metadata.
    
    Args:
        processed_data: Successfully processed data rows
        all_warnings: All accumulated warnings
        rows_skipped: Count of skipped rows
        delimiter: Used delimiter
        has_header: Whether headers were detected/used
        
    Returns:
        Complete ParseResult object
    """
    # Add performance warnings for large datasets
    if len(processed_data) > 10000:
        all_warnings.append(f"Large dataset: {len(processed_data)} rows processed")
    
    # Add encoding warnings if any non-ASCII characters detected
    has_unicode = any(any(ord(char) > 127 for char in str(cell)) 
                     for row in processed_data for cell in row.values())
    if has_unicode:
        all_warnings.append("Unicode characters detected in data")
    
    return ParseResult(
        data=processed_data,
        warnings=all_warnings,
        rows_processed=len(processed_data),
        rows_skipped=rows_skipped,
        delimiter=delimiter,
        has_header=has_header
    )


def parse_csv_content(source: Union[str, Path, TextIO], 
                     delimiter: str = None,
                     has_header: bool = None,
                     skip_empty_rows: bool = True) -> ParseResult:
    """
    Parse messy CSV data with inconsistent delimiters and missing headers.
    
    This function automatically detects delimiters and headers in CSV data,
    handling common formatting issues like mixed quoting, empty rows, and
    inconsistent column counts.
    
    Args:
        source: CSV source (file path, string content, or file object)
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
            
    Examples:
        >>> # Example 1: Semicolon-delimited with headers
        >>> content1 = '''name;age;city
        ... John;30;New York
        ... Jane;25;Boston'''
        >>> result1 = parse_csv_content(content1)
        >>> result1.data[0]
        {'name': 'John', 'age': '30', 'city': 'New York'}
        >>> result1.delimiter
        ';'
        >>> result1.has_header
        True
        
        >>> # Example 2: Tab-delimited without headers
        >>> content2 = '''John\t30\tNew York
        ... Jane\t25\tBoston'''
        >>> result2 = parse_csv_content(content2)
        >>> result2.data[0]
        {'column_1': 'John', 'column_2': '30', 'column_3': 'New York'}
        >>> result2.delimiter
        '\t'
        >>> result2.has_header
        False
        
        >>> # Example 3: Pipe-delimited with empty rows
        >>> content3 = '''name|age
        ... 
        ... John|30
        ... 
        ... Jane|25'''
        >>> result3 = parse_csv_content(content3)
        >>> result3.data
        [{'name': 'John', 'age': '30'}, {'name': 'Jane', 'age': '25'}]
        >>> result3.rows_skipped
        2
        >>> result3.warnings
        ['No headers detected, generated default column names']
        
    Raises:
        None: All errors are captured in ParseResult.warnings
    """
    all_warnings = []
    rows_skipped = 0
    processed_data = []
    detected_delimiter = ','
    detected_has_header = False
    
    try:
        # Input validation and conversion
        content = validate_input(source)
        
        # Normalize content
        content, norm_warnings = normalize_content(content)
        all_warnings.extend(norm_warnings)
        
        if not content:
            all_warnings.append("Content is empty after normalization")
            return build_result_metadata([], all_warnings, 0, detected_delimiter, detected_has_header)
        
        # Use provided delimiter or auto-detect
        if delimiter is not None:
            # Validate provided delimiter works with data format
            detected_delimiter = delimiter
            test_lines = content.split('\n')[:5]  # Check first 5 lines
            delimiter_counts = [line.count(delimiter) for line in test_lines if line.strip()]
            if delimiter_counts and max(delimiter_counts) == 0:
                all_warnings.append(f"Provided delimiter '{delimiter}' not found in data, results may be incorrect")
        else:
            detected_delimiter, delim_warnings = detect_delimiter(content)
            all_warnings.extend(delim_warnings)
        
        # Parse all rows with error handling
        all_rows = []
        try:
            # Handle malformed quotes by trying different quoting modes
            for quote_mode in [csv.QUOTE_MINIMAL, csv.QUOTE_ALL, csv.QUOTE_NONE]:
                try:
                    reader = csv.reader(io.StringIO(content), 
                                      delimiter=detected_delimiter, 
                                      quoting=quote_mode,
                                      skipinitialspace=True)
                    all_rows = list(reader)
                    break
                except (csv.Error, ValueError) as e:
                    if quote_mode == csv.QUOTE_NONE:  # Last attempt failed
                        all_warnings.append(f"CSV parsing failed with all quote modes, last error: {type(e).__name__}: {str(e)}")
                    continue
            
            if not all_rows:
                # Last resort: manual parsing
                all_warnings.append("Standard CSV parsing failed, using manual line splitting")
                lines = content.split('\n')
                all_rows = [line.split(detected_delimiter) for line in lines if line.strip()]
                
        except (MemoryError, OverflowError) as e:
            all_warnings.append(f"Resource exhaustion during CSV parsing: {type(e).__name__}: {str(e)}")
            return build_result_metadata([], all_warnings, 0, detected_delimiter, detected_has_header)
        
        # Filter empty rows
        filtered_rows = []
        for row in all_rows:
            if skip_empty_rows and not any(cell.strip() for cell in row):
                rows_skipped += 1
                continue
            filtered_rows.append(row)
        
        if not filtered_rows:
            all_warnings.append("No data rows found after filtering")
            return build_result_metadata([], all_warnings, rows_skipped, detected_delimiter, detected_has_header)
        
        # Handle edge case: only header row, no data rows
        if len(filtered_rows) == 1:
            if has_header is True or (has_header is None and len(filtered_rows[0]) > 0):
                all_warnings.append("File contains only header row with no data rows")
                return build_result_metadata([], all_warnings, rows_skipped, detected_delimiter, True)
        
        # Auto-detect headers if not specified
        if has_header is None:
            second_row = filtered_rows[1] if len(filtered_rows) > 1 else None
            detected_has_header, header_warnings = detect_headers(filtered_rows[0], second_row, filtered_rows)
            all_warnings.extend(header_warnings)
        else:
            detected_has_header = has_header
        
        # Analyze structure for additional warnings
        structure_warnings = analyze_structure(filtered_rows, detected_delimiter)
        all_warnings.extend(structure_warnings)
        
        # Determine column count and headers
        max_columns = max(len(row) for row in filtered_rows) if filtered_rows else 0
        
        # Full integration of header handling
        if detected_has_header and filtered_rows:
            header_row, header_clean_warnings = clean_row(filtered_rows[0], max_columns)
            all_warnings.extend(header_clean_warnings)
            headers = header_row
            data_rows = filtered_rows[1:]
        else:
            # Auto-generate headers when missing
            headers = generate_headers(max_columns)
            data_rows = filtered_rows
            all_warnings.append("No headers detected, generated default column names")
        
        # Process data rows
        for row_num, row in enumerate(data_rows, 1):
            try:
                cleaned_row, row_warnings = clean_row(row, len(headers))
                all_warnings.extend(row_warnings)
                row_dict = dict(zip(headers, cleaned_row))
                processed_data.append(row_dict)
            except (IndexError, ValueError, TypeError) as e:
                all_warnings.append(f"Error processing row {row_num}: {type(e).__name__}: {str(e)}")
                rows_skipped += 1
                continue
        
        return build_result_metadata(processed_data, all_warnings, rows_skipped, detected_delimiter, detected_has_header)
        
    except (MemoryError, SystemError) as e:
        all_warnings.append(f"System error during parsing: {type(e).__name__}: {str(e)}")
        return build_result_metadata([], all_warnings, 0, detected_delimiter, detected_has_header)


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
    
    # Test 4: File path input
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("id,name\n1,Test")
        temp_path = f.name
    
    result4 = parse_csv_content(temp_path)
    assert len(result4.data) == 1
    assert result4.data[0]['name'] == 'Test'
    
    # Test 5: Error handling (invalid input type)
    result5 = parse_csv_content(123)
    assert len(result5.warnings) > 0
    
    print("All tests passed!")


if __name__ == "__main__":
    test_parse_csv_content()
```