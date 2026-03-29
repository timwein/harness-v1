# Harness Output: csv_parser

**Score:** 75.1% (33.05/44)
**Iterations:** 4
**Best Iteration:** 2 (75.1%)

---

```python
"""
CSV Parser for messy data with inconsistent delimiters and missing headers.
"""

import csv
import io
import re
import gzip
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Union, List, Dict, Any, Optional, Tuple, Literal, TypedDict
from urllib.parse import urlparse
from urllib.request import urlopen
import time

try:
    import chardet
except ImportError:
    chardet = None

class DelimiterDetectionError(Exception):
    """Raised when delimiter detection fails."""
    pass

class HeaderParsingError(Exception):
    """Raised when header parsing encounters issues."""
    pass

class DataIntegrityError(Exception):
    """Raised when data integrity is compromised."""
    pass

class ConfigDict(TypedDict, total=False):
    encoding: str
    sample_size: int
    max_field_size: int
    confidence_threshold: float

@dataclass
class ErrorReport:
    """Structured error information with recovery suggestions."""
    error_type: str
    severity: Literal['low', 'medium', 'high', 'critical']
    message: str
    row_number: Optional[int] = None
    error_code: str = ""
    recovery_suggestion: str = ""

@dataclass
class DelimiterConfidence:
    """Delimiter detection confidence scoring."""
    delimiter: str
    confidence: float
    frequency: int
    consistency_score: float

@dataclass
class DataQualityMetrics:
    """Quality metrics for parsed data."""
    clean_row_percentage: float
    anomaly_counts: Dict[str, int] = field(default_factory=dict)
    missing_value_percentage: float = 0.0
    data_type_consistency: float = 0.0

@dataclass
class FileCharacteristics:
    """File characteristics discovered during parsing."""
    estimated_encoding: str = "utf-8"
    line_ending_type: str = "\\n"
    file_size_processed: int = 0
    bom_detected: bool = False

@dataclass
class ParseResult:
    """Result of CSV parsing operation."""
    data: List[Dict[str, Any]]
    warnings: List[str]
    rows_skipped: int
    delimiter_used: str
    headers_generated: bool
    total_rows_processed: int
    errors: List[ErrorReport] = field(default_factory=list)
    parsing_duration: float = 0.0
    delimiter_confidence: Optional[DelimiterConfidence] = None
    data_quality_metrics: Optional[DataQualityMetrics] = None
    file_characteristics: Optional[FileCharacteristics] = None
    messages: List[str] = field(default_factory=list)

def detect_bom(content: bytes) -> Tuple[str, bool]:
    """
    Detect and remove BOM from content.
    
    Args:
        content: Raw bytes content
        
    Returns:
        Tuple of (decoded_content, bom_detected)
    """
    bom_signatures = [
        (b'\xef\xbb\xbf', 'utf-8'),
        (b'\xff\xfe', 'utf-16-le'),
        (b'\xfe\xff', 'utf-16-be'),
        (b'\xff\xfe\x00\x00', 'utf-32-le'),
        (b'\x00\x00\xfe\xff', 'utf-32-be'),
    ]
    
    for bom, encoding in bom_signatures:
        if content.startswith(bom):
            return content[len(bom):].decode(encoding), True
    
    # No BOM detected, try to detect encoding
    if chardet:
        result = chardet.detect(content)
        encoding = result.get('encoding', 'utf-8')
    else:
        encoding = 'utf-8'
    
    try:
        return content.decode(encoding), False
    except UnicodeDecodeError:
        return content.decode('utf-8', errors='replace'), False

def detect_line_endings(content: str) -> str:
    """
    Detect line ending type in content.
    
    Args:
        content: String content to analyze
        
    Returns:
        Line ending type as string representation
    """
    crlf_count = content.count('\r\n')
    lf_count = content.count('\n') - crlf_count
    cr_count = content.count('\r') - crlf_count
    
    if crlf_count > max(lf_count, cr_count):
        return '\\r\\n'
    elif cr_count > lf_count:
        return '\\r'
    else:
        return '\\n'

def advanced_delimiter_detection(sample: str, logger: Optional[Any] = None) -> DelimiterConfidence:
    """
    Advanced delimiter detection with frequency analysis and confidence scoring.
    
    Args:
        sample: Sample text from CSV file
        logger: Optional logger for diagnostics
        
    Returns:
        DelimiterConfidence object with best delimiter and metrics
    """
    messages = []
    
    # Common delimiters to test
    delimiters = [',', '\t', '|', ';', ':']
    
    # First try csv.Sniffer
    try:
        sniffer = csv.Sniffer()
        detected_delimiter = sniffer.sniff(sample, delimiters=''.join(delimiters)).delimiter
        messages.append(f"csv.Sniffer detected delimiter: '{detected_delimiter}'")
    except csv.Error:
        detected_delimiter = None
        messages.append("csv.Sniffer failed, using frequency analysis")
    
    # Frequency analysis across multiple lines
    lines = sample.split('\n')[:20]  # Analyze first 20 lines
    delimiter_scores = {}
    
    for delimiter in delimiters:
        frequencies = []
        in_quotes = False
        
        for line in lines:
            if not line.strip():
                continue
                
            count = 0
            quote_char = '"'
            
            # Count delimiters not inside quotes
            i = 0
            while i < len(line):
                char = line[i]
                if char == quote_char:
                    in_quotes = not in_quotes
                elif char == delimiter and not in_quotes:
                    count += 1
                i += 1
            
            if count > 0:
                frequencies.append(count)
        
        if frequencies:
            # Calculate consistency score (lower std dev = higher consistency)
            mean_freq = sum(frequencies) / len(frequencies)
            variance = sum((f - mean_freq) ** 2 for f in frequencies) / len(frequencies)
            std_dev = variance ** 0.5
            consistency = max(0, 1 - (std_dev / (mean_freq + 1)))
            
            delimiter_scores[delimiter] = {
                'frequency': sum(frequencies),
                'consistency': consistency,
                'confidence': mean_freq * consistency
            }
    
    if not delimiter_scores:
        if logger:
            logger.warning("No delimiter patterns detected")
        return DelimiterConfidence(',', 0.0, 0, 0.0)
    
    # Select best delimiter
    best_delimiter = max(delimiter_scores.keys(), 
                        key=lambda d: delimiter_scores[d]['confidence'])
    
    best_score = delimiter_scores[best_delimiter]
    
    # Validate against sniffer result
    if detected_delimiter and detected_delimiter != best_delimiter:
        if best_score['confidence'] < 2.0:  # Low confidence, trust sniffer
            best_delimiter = detected_delimiter
            messages.append(f"Used sniffer result due to low frequency confidence")
    
    result = DelimiterConfidence(
        delimiter=best_delimiter,
        confidence=min(1.0, best_score['confidence'] / 10.0),
        frequency=best_score['frequency'],
        consistency_score=best_score['consistency']
    )
    
    if logger:
        for message in messages:
            logger.info(message)
    
    return result

def enhanced_header_detection(rows: List[List[str]], logger: Optional[Any] = None) -> Tuple[bool, float]:
    """
    Enhanced header detection with multiple heuristics and confidence scoring.
    
    Args:
        rows: List of parsed CSV rows
        logger: Optional logger for diagnostics
        
    Returns:
        Tuple of (has_headers, confidence_score)
    """
    if not rows or len(rows) < 2:
        return False, 0.0
    
    first_row = rows[0]
    data_rows = rows[1:5]  # Analyze up to 5 data rows
    
    confidence_factors = []
    
    # 1. Data type analysis
    first_row_numeric = sum(1 for cell in first_row 
                           if cell.replace('.', '').replace('-', '').replace('+', '').isdigit())
    first_row_numeric_ratio = first_row_numeric / len(first_row) if first_row else 0
    
    data_numeric_ratios = []
    for row in data_rows:
        if row:
            numeric_count = sum(1 for cell in row 
                              if cell.replace('.', '').replace('-', '').replace('+', '').isdigit())
            data_numeric_ratios.append(numeric_count / len(row))
    
    avg_data_numeric_ratio = sum(data_numeric_ratios) / len(data_numeric_ratios) if data_numeric_ratios else 0
    
    # If first row has fewer numbers than data rows, likely headers
    if first_row_numeric_ratio < avg_data_numeric_ratio - 0.2:
        confidence_factors.append(0.4)
    elif first_row_numeric_ratio > avg_data_numeric_ratio + 0.2:
        confidence_factors.append(-0.3)
    
    # 2. Pattern matching for common header formats
    header_patterns = 0
    for cell in first_row:
        cell_lower = cell.lower().strip()
        # Common header words
        if any(word in cell_lower for word in ['id', 'name', 'date', 'time', 'value', 'count', 
                                              'total', 'amount', 'price', 'code', 'type', 'status']):
            header_patterns += 1
        # Naming conventions
        elif '_' in cell or any(c.isupper() for c in cell[1:]) and any(c.islower() for c in cell):
            header_patterns += 1
        # All caps (common for headers)
        elif cell.isupper() and len(cell) > 1:
            header_patterns += 1
    
    pattern_ratio = header_patterns / len(first_row) if first_row else 0
    if pattern_ratio > 0.3:
        confidence_factors.append(pattern_ratio * 0.5)
    
    # 3. Length and character analysis
    first_row_avg_len = sum(len(cell) for cell in first_row) / len(first_row) if first_row else 0
    data_avg_lens = []
    for row in data_rows:
        if row:
            data_avg_lens.append(sum(len(cell) for cell in row) / len(row))
    
    data_avg_len = sum(data_avg_lens) / len(data_avg_lens) if data_avg_lens else 0
    
    # Headers often shorter and more descriptive
    if first_row_avg_len < data_avg_len * 0.8 and first_row_avg_len > 3:
        confidence_factors.append(0.2)
    
    # 4. Uniqueness check
    first_row_unique = len(set(first_row)) / len(first_row) if first_row else 0
    if first_row_unique > 0.8:  # Headers usually unique
        confidence_factors.append(0.2)
    
    # Calculate final confidence
    total_confidence = sum(confidence_factors)
    normalized_confidence = max(0, min(1, total_confidence))
    
    has_headers = normalized_confidence > 0.5
    
    if logger:
        logger.info(f"Header detection confidence: {normalized_confidence:.2f}, has_headers: {has_headers}")
    
    return has_headers, normalized_confidence

def generate_headers(num_columns: int) -> List[str]:
    """
    Generate default column headers.
    
    Args:
        num_columns: Number of columns needed
        
    Returns:
        List of generated header names
    """
    return [f'column_{i+1}' for i in range(num_columns)]

def parse_rows_with_error_recovery(reader: csv.reader, max_columns: int, 
                                 logger: Optional[Any] = None) -> Tuple[List[List[str]], List[ErrorReport], int]:
    """
    Parse CSV rows with comprehensive error handling and recovery.
    
    Args:
        reader: CSV reader object
        max_columns: Maximum expected columns
        logger: Optional logger for diagnostics
        
    Returns:
        Tuple of (parsed_rows, error_reports, skipped_count)
    """
    rows = []
    errors = []
    skipped = 0
    
    for row_num, row in enumerate(reader, 1):
        try:
            # Skip completely empty rows
            if not row or all(cell.strip() == '' for cell in row):
                skipped += 1
                continue
            
            # Handle malformed quotes
            cleaned_row = []
            for i, cell in enumerate(row):
                cell_str = str(cell)
                # Check for unclosed quotes or quotes in middle
                if cell_str.count('"') % 2 == 1:
                    errors.append(ErrorReport(
                        error_type="malformed_quotes",
                        severity="medium",
                        message=f"Unclosed quote in cell {i+1}",
                        row_number=row_num,
                        error_code="QUOTE_001",
                        recovery_suggestion="Quote was automatically closed"
                    ))
                    cell_str = cell_str + '"' if not cell_str.endswith('"') else cell_str
                
                cleaned_row.append(cell_str.strip())
            
            # Normalize row length
            if len(cleaned_row) < max_columns:
                # Pad short rows
                cleaned_row.extend([''] * (max_columns - len(cleaned_row)))
                errors.append(ErrorReport(
                    error_type="short_row",
                    severity="low",
                    message=f"Padded short row to {max_columns} columns",
                    row_number=row_num,
                    error_code="ROW_001",
                    recovery_suggestion="Missing columns filled with empty strings"
                ))
            elif len(cleaned_row) > max_columns:
                # Truncate long rows
                errors.append(ErrorReport(
                    error_type="long_row",
                    severity="medium",
                    message=f"Truncated row from {len(cleaned_row)} to {max_columns} columns",
                    row_number=row_num,
                    error_code="ROW_002",
                    recovery_suggestion="Extra columns were discarded"
                ))
                cleaned_row = cleaned_row[:max_columns]
            
            rows.append(cleaned_row)
            
        except csv.Error as e:
            errors.append(ErrorReport(
                error_type="csv_parsing",
                severity="high",
                message=f"CSV parsing error - {e}",
                row_number=row_num,
                error_code="CSV_001",
                recovery_suggestion="Row was skipped due to parsing error"
            ))
            skipped += 1
        except Exception as e:
            errors.append(ErrorReport(
                error_type="unexpected",
                severity="critical",
                message=f"Unexpected error - {e}",
                row_number=row_num,
                error_code="UNK_001",
                recovery_suggestion="Row was skipped due to unexpected error"
            ))
            skipped += 1
    
    return rows, errors, skipped

def calculate_data_quality_metrics(data: List[Dict[str, Any]], 
                                 errors: List[ErrorReport]) -> DataQualityMetrics:
    """
    Calculate comprehensive data quality metrics.
    
    Args:
        data: Parsed data rows
        errors: List of error reports
        
    Returns:
        DataQualityMetrics object
    """
    if not data:
        return DataQualityMetrics(clean_row_percentage=0.0)
    
    total_rows = len(data)
    
    # Count anomalies by type
    anomaly_counts = {}
    for error in errors:
        anomaly_counts[error.error_type] = anomaly_counts.get(error.error_type, 0) + 1
    
    # Calculate missing value percentage
    total_cells = sum(len(row) for row in data)
    missing_cells = sum(1 for row in data for value in row.values() if not str(value).strip())
    missing_percentage = (missing_cells / total_cells * 100) if total_cells > 0 else 0
    
    # Estimate data type consistency
    if data:
        consistency_scores = []
        for key in data[0].keys():
            column_values = [row.get(key, '') for row in data]
            non_empty_values = [v for v in column_values if str(v).strip()]
            
            if non_empty_values:
                # Check if values are consistently numeric, date-like, etc.
                numeric_count = sum(1 for v in non_empty_values 
                                  if str(v).replace('.', '').replace('-', '').replace('+', '').isdigit())
                numeric_ratio = numeric_count / len(non_empty_values)
                consistency_scores.append(max(numeric_ratio, 1 - numeric_ratio))
        
        data_type_consistency = sum(consistency_scores) / len(consistency_scores) if consistency_scores else 0
    else:
        data_type_consistency = 0
    
    # Calculate clean row percentage
    error_rows = len(set(error.row_number for error in errors if error.row_number))
    clean_rows = total_rows - error_rows
    clean_percentage = (clean_rows / total_rows * 100) if total_rows > 0 else 0
    
    return DataQualityMetrics(
        clean_row_percentage=clean_percentage,
        anomaly_counts=anomaly_counts,
        missing_value_percentage=missing_percentage,
        data_type_consistency=data_type_consistency * 100
    )

def handle_compressed_input(source: Union[str, Path]) -> str:
    """
    Handle compressed file inputs (gzip, zip).
    
    Args:
        source: Path to compressed file
        
    Returns:
        Decompressed content as string
    """
    path = Path(source)
    
    if path.suffix.lower() == '.gz':
        with gzip.open(path, 'rb') as f:
            content_bytes = f.read()
    elif path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path, 'r') as zf:
            # Use first CSV-like file in archive
            csv_files = [name for name in zf.namelist() 
                        if name.lower().endswith(('.csv', '.tsv', '.txt'))]
            if not csv_files:
                raise ValueError("No CSV files found in ZIP archive")
            
            with zf.open(csv_files[0]) as f:
                content_bytes = f.read()
    else:
        raise ValueError(f"Unsupported compressed format: {path.suffix}")
    
    content, _ = detect_bom(content_bytes)
    return content

def handle_url_input(url: str, encoding: str = 'utf-8') -> str:
    """
    Handle URL inputs by downloading content.
    
    Args:
        url: URL to download
        encoding: Text encoding
        
    Returns:
        Downloaded content as string
    """
    try:
        with urlopen(url) as response:
            content_bytes = response.read()
            content, _ = detect_bom(content_bytes)
            return content
    except Exception as e:
        raise ValueError(f"Failed to download from URL: {e}")

def parse_csv(
    source: Union[str, Path, IO[str], bytes], 
    encoding: Optional[str] = 'utf-8',
    sample_size: int = 8192,
    max_field_size: int = 131072,
    config: Optional[ConfigDict] = None,
    logger: Optional[Any] = None
) -> ParseResult:
    """
    Parse messy CSV data with inconsistent delimiters and missing headers.
    
    This function automatically detects delimiters, handles missing headers,
    and provides robust error handling for malformed CSV data. Supports multiple
    input types including files, URLs, compressed archives, and streaming data.
    
    Args:
        source: File path, string content, file-like object, URL, or bytes
        encoding: Text encoding for file reading (default: utf-8, None for auto-detection)
        sample_size: Bytes to sample for delimiter detection
        max_field_size: Maximum field size to prevent memory issues
        config: Optional configuration dictionary
        logger: Optional logger for diagnostics (if None, messages stored in result)
        
    Returns:
        ParseResult containing parsed data, warnings, errors, and comprehensive metadata
        
    Raises:
        DelimiterDetectionError: When delimiter detection fails critically
        HeaderParsingError: When header parsing encounters unrecoverable issues
        DataIntegrityError: When data integrity cannot be maintained
        
    Example:
        >>> # Basic usage
        >>> result = parse_csv('messy_data.csv')
        >>> print(f"Parsed {len(result.data)} rows with {len(result.warnings)} warnings")
        >>> print(f"Used delimiter: '{result.delimiter_used}' (confidence: {result.delimiter_confidence.confidence:.2f})")
        
        >>> # Advanced usage with configuration
        >>> config = {'encoding': 'latin1', 'sample_size': 16384}
        >>> result = parse_csv('data.csv', config=config)
        >>> print(f"Data quality: {result.data_quality_metrics.clean_row_percentage:.1f}% clean rows")
        
        >>> # URL and compressed file support
        >>> result = parse_csv('https://example.com/data.csv')
        >>> result = parse_csv('archive.csv.gz')
    """
    start_time = time.time()
    warnings = []
    errors = []
    rows_skipped = 0
    messages = []
    
    try:
        # Apply configuration overrides
        if config:
            encoding = config.get('encoding', encoding)
            sample_size = config.get('sample_size', sample_size)
            max_field_size = config.get('max_field_size', max_field_size)
        
        # Handle different input types with enhanced flexibility
        if isinstance(source, bytes):
            # Handle BytesIO-like objects
            content, bom_detected = detect_bom(source)
            file_chars = FileCharacteristics(bom_detected=bom_detected, file_size_processed=len(source))
        elif isinstance(source, (str, Path)):
            source_str = str(source)
            file_chars = FileCharacteristics()
            
            # Check if it's a URL
            if urlparse(source_str).scheme in ('http', 'https', 'ftp'):
                content = handle_url_input(source_str, encoding or 'utf-8')
                file_chars.file_size_processed = len(content.encode())
            else:
                file_path = Path(source_str)
                if not file_path.exists():
                    raise FileNotFoundError(f"File not found: {file_path}")
                
                file_chars.file_size_processed = file_path.stat().st_size
                
                # Handle compressed files
                if file_path.suffix.lower() in ['.gz', '.zip']:
                    content = handle_compressed_input(file_path)
                else:
                    # Regular file handling
                    if encoding is None:
                        # Auto-detect encoding
                        with open(file_path, 'rb') as f:
                            raw_content = f.read()
                        content, file_chars.bom_detected = detect_bom(raw_content)
                        if chardet:
                            detected = chardet.detect(raw_content)
                            file_chars.estimated_encoding = detected.get('encoding', 'utf-8')
                    else:
                        with open(file_path, 'r', encoding=encoding, newline='') as f:
                            content = f.read()
                        file_chars.estimated_encoding = encoding
                        
        elif hasattr(source, 'read'):
            # File-like object
            content = source.read()
            if hasattr(source, 'seek'):
                source.seek(0)  # Reset for potential re-reading
            file_chars = FileCharacteristics(file_size_processed=len(content))
        else:
            content = str(source)
            file_chars = FileCharacteristics(file_size_processed=len(content))
        
        if not content.strip():
            return ParseResult(
                data=[], warnings=["Empty input"], rows_skipped=0,
                delimiter_used=',', headers_generated=True, total_rows_processed=0,
                parsing_duration=time.time() - start_time,
                file_characteristics=file_chars,
                messages=messages
            )
        
        # Detect line endings
        file_chars.line_ending_type = detect_line_endings(content)
        
        # Advanced delimiter detection
        sample = content[:sample_size]
        delimiter_confidence = advanced_delimiter_detection(sample, logger)
        
        if delimiter_confidence.confidence < 0.1:
            raise DelimiterDetectionError("Could not reliably detect delimiter")
        
        # Set up CSV reader with increased field size limit
        csv.field_size_limit(max_field_size)
        
        # Parse all rows with error recovery
        reader = csv.reader(io.StringIO(content), delimiter=delimiter_confidence.delimiter)
        all_rows, parse_errors, parse_skipped = parse_rows_with_error_recovery(reader, 0, logger)
        
        errors.extend(parse_errors)
        rows_skipped += parse_skipped
        
        if not all_rows:
            return ParseResult(
                data=[], warnings=warnings + ["No valid rows found"],
                rows_skipped=rows_skipped, delimiter_used=delimiter_confidence.delimiter,
                headers_generated=True, total_rows_processed=0,
                errors=errors, parsing_duration=time.time() - start_time,
                delimiter_confidence=delimiter_confidence,
                file_characteristics=file_chars, messages=messages
            )
        
        # Determine maximum columns and re-parse with normalization
        max_columns = max(len(row) for row in all_rows)
        reader = csv.reader(io.StringIO(content), delimiter=delimiter_confidence.delimiter)
        all_rows, parse_errors, parse_skipped = parse_rows_with_error_recovery(reader, max_columns, logger)
        errors.extend(parse_errors)
        rows_skipped = parse_skipped  # Reset since we re-parsed
        
        # Enhanced header detection
        has_headers, header_confidence = enhanced_header_detection(all_rows, logger)
        headers_generated = not has_headers
        
        if has_headers:
            headers = all_rows[0]
            data_rows = all_rows[1:]
            if logger:
                logger.info(f"Headers detected with confidence {header_confidence:.2f}")
            else:
                messages.append(f"Headers detected with confidence {header_confidence:.2f}")
        else:
            headers = generate_headers(max_columns)
            data_rows = all_rows
            warning_msg = "No headers detected, generated default column names"
            warnings.append(warning_msg)
            if logger:
                logger.warning(warning_msg)
            else:
                messages.append(warning_msg)
        
        # Convert to list of dictionaries
        data = []
        for row in data_rows:
            try:
                row_dict = dict(zip(headers, row))
                data.append(row_dict)
            except Exception as e:
                errors.append(ErrorReport(
                    error_type="dict_creation",
                    severity="high",
                    message=f"Error creating row dict: {e}",
                    error_code="DICT_001",
                    recovery_suggestion="Row was skipped"
                ))
                rows_skipped += 1
        
        # Calculate data quality metrics
        quality_metrics = calculate_data_quality_metrics(data, errors)
        
        # Prepare warnings from errors
        warning_messages = [f"Row {err.row_number}: {err.message}" for err in errors if err.severity in ['medium', 'high']]
        warnings.extend(warning_messages)
        
        return ParseResult(
            data=data,
            warnings=warnings,
            rows_skipped=rows_skipped,
            delimiter_used=delimiter_confidence.delimiter,
            headers_generated=headers_generated,
            total_rows_processed=len(all_rows),
            errors=errors,
            parsing_duration=time.time() - start_time,
            delimiter_confidence=delimiter_confidence,
            data_quality_metrics=quality_metrics,
            file_characteristics=file_chars,
            messages=messages
        )
        
    except DelimiterDetectionError as e:
        if logger:
            logger.error(f"Delimiter detection failed: {e}")
        return ParseResult(
            data=[], warnings=[f"Delimiter detection failed: {e}"], rows_skipped=0,
            delimiter_used=',', headers_generated=True, total_rows_processed=0,
            errors=[ErrorReport("delimiter_detection", "critical", str(e), error_code="DEL_001")],
            parsing_duration=time.time() - start_time, messages=messages
        )
    except HeaderParsingError as e:
        if logger:
            logger.error(f"Header parsing failed: {e}")
        return ParseResult(
            data=[], warnings=[f"Header parsing failed: {e}"], rows_skipped=0,
            delimiter_used=',', headers_generated=True, total_rows_processed=0,
            errors=[ErrorReport("header_parsing", "critical", str(e), error_code="HDR_001")],
            parsing_duration=time.time() - start_time, messages=messages
        )
    except DataIntegrityError as e:
        if logger:
            logger.error(f"Data integrity compromised: {e}")
        return ParseResult(
            data=[], warnings=[f"Data integrity error: {e}"], rows_skipped=0,
            delimiter_used=',', headers_generated=True, total_rows_processed=0,
            errors=[ErrorReport("data_integrity", "critical", str(e), error_code="INT_001")],
            parsing_duration=time.time() - start_time, messages=messages
        )
    except FileNotFoundError as e:
        if logger:
            logger.error(f"File not found: {e}")
        return ParseResult(
            data=[], warnings=[f"File error: {e}"], rows_skipped=0,
            delimiter_used=',', headers_generated=True, total_rows_processed=0,
            errors=[ErrorReport("file_not_found", "critical", str(e), error_code="FILE_001")],
            parsing_duration=time.time() - start_time, messages=messages
        )
    except UnicodeDecodeError as e:
        if logger:
            logger.error(f"Encoding error: {e}")
        return ParseResult(
            data=[], warnings=[f"Encoding error: {e}. Try a different encoding."],
            rows_skipped=0, delimiter_used=',', headers_generated=True, total_rows_processed=0,
            errors=[ErrorReport("encoding", "critical", str(e), error_code="ENC_001", 
                              recovery_suggestion="Try specifying a different encoding or use encoding=None for auto-detection")],
            parsing_duration=time.time() - start_time, messages=messages
        )
    except csv.Error as e:
        if logger:
            logger.error(f"CSV parsing error: {e}")
        return ParseResult(
            data=[], warnings=[f"CSV parsing error: {e}"], rows_skipped=0,
            delimiter_used=',', headers_generated=True, total_rows_processed=0,
            errors=[ErrorReport("csv_parsing", "critical", str(e), error_code="CSV_002")],
            parsing_duration=time.time() - start_time, messages=messages
        )
    except Exception as e:
        if logger:
            logger.error(f"Unexpected error: {e}")
        return ParseResult(
            data=[], warnings=[f"Unexpected error: {e}"], rows_skipped=0,
            delimiter_used=',', headers_generated=True, total_rows_processed=0,
            errors=[ErrorReport("unexpected", "critical", str(e), error_code="UNK_002")],
            parsing_duration=time.time() - start_time, messages=messages
        )

# Example test cases demonstrating usage
def test_delimiter_detection():
    """Test delimiter detection with various formats."""
    comma_csv = "name,age,city\nJohn,25,NYC\nJane,30,LA"
    tab_csv = "name\tage\tcity\nJohn\t25\tNYC\nJane\t30\tLA"
    pipe_csv = "name|age|city\nJohn|25|NYC\nJane|30|LA"
    
    assert advanced_delimiter_detection(comma_csv).delimiter == ','
    assert advanced_delimiter_detection(tab_csv).delimiter == '\t'
    assert advanced_delimiter_detection(pipe_csv).delimiter == '|'

def test_header_detection():
    """Test header detection heuristics."""
    with_headers = [['name', 'age', 'city'], ['John', '25', 'NYC']]
    without_headers = [['John', '25', 'NYC'], ['Jane', '30', 'LA']]
    
    has_headers_1, _ = enhanced_header_detection(with_headers)
    has_headers_2, _ = enhanced_header_detection(without_headers)
    
    assert has_headers_1 == True
    assert has_headers_2 == False

def test_parse_csv():
    """Test complete CSV parsing functionality."""
    test_data = "name,age,city\nJohn,25,NYC\nJane,30,LA\n"
    result = parse_csv(test_data)
    
    assert len(result.data) == 2
    assert result.data[0]['name'] == 'John'
    assert result.delimiter_used == ','
    assert not result.headers_generated
    assert result.delimiter_confidence.confidence > 0.5

def test_error_handling():
    """Test error handling and recovery."""
    malformed_data = 'name,age,city\nJohn,25,"NYC\nJane,30,LA,Extra'
    result = parse_csv(malformed_data)
    
    assert len(result.errors) > 0
    assert any(error.error_type == "malformed_quotes" for error in result.errors)
    assert result.data_quality_metrics.clean_row_percentage < 100

def test_advanced_features():
    """Test advanced features like BOM detection and quality metrics."""
    # Test with BOM
    bom_content = b'\xef\xbb\xbfname,age\nJohn,25'
    content, bom_detected = detect_bom(bom_content)
    assert bom_detected == True
    assert content.startswith('name,age')
    
    # Test quality metrics calculation
    data = [{'name': 'John', 'age': '25'}, {'name': '', 'age': '30'}]
    errors = [ErrorReport("test", "low", "test error")]
    metrics = calculate_data_quality_metrics(data, errors)
    assert metrics.missing_value_percentage > 0
    assert metrics.clean_row_percentage >= 0
```