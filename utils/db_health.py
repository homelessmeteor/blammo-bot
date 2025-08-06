#!/usr/bin/env python3
"""
Database Health Validation Module

Provides comprehensive health checks for all BlammoBot CSV databases:
- Trivia questions database
- Scramble words database  
- User data database
- Timestamps database
- Submissions database

Detects issues like merge conflicts, duplicates, and data corruption.
"""

import pandas as pd
import logging
import os
import re
import csv
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
from difflib import SequenceMatcher

from log.loggers.rotating_logger import get_rotating_logger

# Set up rotating logger with 10MB max size and 5 backup files
logger = get_rotating_logger(__name__)


class DatabaseHealthIssue:
    """Represents a database health issue"""
    
    def __init__(self, database: str, issue_type: str, severity: str, 
                 description: str, location: Optional[str] = None, 
                 affected_data: Optional[Any] = None, line_number: Optional[int] = None):
        self.database = database
        self.issue_type = issue_type  # 'merge_conflict', 'duplicate', 'corruption', 'missing_data'
        self.severity = severity      # 'critical', 'warning', 'info'
        self.description = description
        self.location = location      # line number, column, etc.
        self.affected_data = affected_data
        self.line_number = line_number  # specific line number for easier debugging
    
    def __str__(self):
        severity_emoji = {
            'critical': '🚨',
            'warning': '⚠️',
            'info': 'ℹ️'
        }
        
        result = f"{severity_emoji.get(self.severity, '•')} {self.database}: {self.description}"
        
        # Always include line number when available, with fallback to location
        if self.line_number is not None:
            result += f" (Line: {self.line_number})"
        elif self.location:
            result += f" (Location: {self.location})"
            
        return result


class DatabaseHealthChecker:
    """Main database health validation class"""
    
    def __init__(self, private_data_path: str = "../blammo-bot-private"):
        self.private_data_path = private_data_path
        self.issues: List[DatabaseHealthIssue] = []
        
        # Database file paths
        self.databases = {
            'trivia': os.path.join(private_data_path, 'trivia.csv'),
            'scramble': os.path.join(private_data_path, 'scramble.csv'),
            'user_data': os.path.join(private_data_path, 'user_data.csv'),
            'timestamps': os.path.join(private_data_path, 'timestamps.csv'),
            'submissions': os.path.join(private_data_path, 'submissions.csv'),
            'record_data': os.path.join(private_data_path, 'record_data.csv')
        }
    
    def check_all_databases(self) -> List[DatabaseHealthIssue]:
        """Run comprehensive health checks on all databases"""
        self.issues = []
        
        logger.info("🔍 Starting comprehensive database health check...")
        
        for db_name, db_path in self.databases.items():
            logger.debug(f"Checking {db_name} database: {db_path}")
            
            if not os.path.exists(db_path):
                self.issues.append(DatabaseHealthIssue(
                    database=db_name,
                    issue_type='missing_file',
                    severity='warning',
                    description=f"Database file not found: {db_path}"
                ))
                continue
            
            # Check for merge conflicts
            self._check_merge_conflicts(db_name, db_path)
            
            # Check for duplicates
            self._check_duplicates(db_name, db_path)
            
            # Check for malformed CSV lines
            self._check_csv_malformation(db_name, db_path)
            
            # Check data integrity
            self._check_data_integrity(db_name, db_path)
            
            # Check file permissions
            self._check_file_permissions(db_name, db_path)
        
        logger.info(f"✅ Database health check complete. Found {len(self.issues)} issues.")
        return self.issues
    
    def _check_merge_conflicts(self, db_name: str, db_path: str):
        """Check for git merge conflict markers"""
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for merge conflict markers
            conflict_patterns = [
                r'<{7}.*?HEAD',
                r'={7}',
                r'>{7}.*?[a-f0-9]{7}',
                r'<{7}.*?[a-f0-9]{7}',
                r'>{7}.*?branch'
            ]
            
            lines = content.split('\n')
            for line_num, line in enumerate(lines, 1):
                for pattern in conflict_patterns:
                    if re.search(pattern, line):
                        self.issues.append(DatabaseHealthIssue(
                            database=db_name,
                            issue_type='merge_conflict',
                            severity='critical',
                            description=f"Git merge conflict marker detected: {line.strip()}",
                            location=f"line {line_num}",
                            affected_data=line.strip(),
                            line_number=line_num
                        ))
                        break
                        
        except Exception as e:
            self.issues.append(DatabaseHealthIssue(
                database=db_name,
                issue_type='read_error',
                severity='critical',
                description=f"Could not read file for merge conflict check: {e}"
            ))
    
    def _check_duplicates(self, db_name: str, db_path: str):
        """Check for duplicate entries based on database type"""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(db_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Could not read file with any encoding")
            
            if df.empty:
                return
            
            # Check for duplicate QIDs (if column exists)
            if 'qid' in df.columns:
                duplicate_qids = df[df['qid'].duplicated(keep=False)]
                if not duplicate_qids.empty:
                    for idx, row in duplicate_qids.iterrows():
                        self.issues.append(DatabaseHealthIssue(
                            database=db_name,
                            issue_type='duplicate',
                            severity='critical',
                            description=f"Duplicate QID found: {row['qid']}",
                            affected_data=row.to_dict(),
                            line_number=idx + 2  # +2 because pandas index starts at 0, and we skip header
                        ))
            
            # Check database-specific duplicates
            if db_name == 'trivia':
                self._check_trivia_duplicates(df, db_name)
            elif db_name == 'scramble':
                self._check_scramble_duplicates(df, db_name)
            elif db_name == 'user_data':
                self._check_user_data_duplicates(df, db_name)
                
        except Exception as e:
            self.issues.append(DatabaseHealthIssue(
                database=db_name,
                issue_type='read_error',
                severity='critical',
                description=f"Could not read file for duplicate check: {e}"
            ))
    
    def _check_trivia_duplicates(self, df: pd.DataFrame, db_name: str):
        """Check for duplicate trivia questions using fuzzy matching"""
        if 'question' in df.columns:
            # Check for exact duplicate questions
            duplicate_questions = df[df['question'].duplicated(keep=False)]
            if not duplicate_questions.empty:
                for idx, row in duplicate_questions.iterrows():
                    self.issues.append(DatabaseHealthIssue(
                        database=db_name,
                        issue_type='duplicate',
                        severity='warning',
                        description=f"Exact duplicate question: {row['question'][:50]}...",
                        affected_data=row.to_dict(),
                        line_number=idx + 2  # +2 because pandas index starts at 0, and we skip header
                    ))
            
            # Check for similar questions using fuzzy matching
            self._check_similar_trivia_questions(df, db_name)
        
        # Check for duplicate answers (exact matches)
        if 'correct_answer' in df.columns:
            self._check_duplicate_answers(df, db_name)
            # Check for similar answers (fuzzy matches)
            self._check_similar_trivia_answers(df, db_name)
    
    def _check_similar_trivia_questions(self, df: pd.DataFrame, db_name: str, similarity_threshold=0.8):
        """Check for similar questions using fuzzy string matching"""
        questions = df['question'].dropna().astype(str).tolist()
        
        for i, q1 in enumerate(questions):
            for j, q2 in enumerate(questions[i+1:], i+1):
                similarity = SequenceMatcher(None, q1.lower(), q2.lower()).ratio()
                if similarity >= similarity_threshold:
                    qid1 = df.iloc[i]['qid'] if 'qid' in df.columns else f"row_{i}"
                    qid2 = df.iloc[j]['qid'] if 'qid' in df.columns else f"row_{j}"
                    
                    # Use the first occurrence line number for reporting
                    line_num1 = i + 2  # +2 because pandas index starts at 0, and we skip header
                    line_num2 = j + 2
                    
                    self.issues.append(DatabaseHealthIssue(
                        database=db_name,
                        issue_type='duplicate',
                        severity='warning',
                        description=f"Similar questions detected (similarity: {similarity:.3f}): QID {qid1} (line {line_num1}) and QID {qid2} (line {line_num2})",
                        affected_data={
                            'qid1': qid1, 'question1': q1, 'line1': line_num1,
                            'qid2': qid2, 'question2': q2, 'line2': line_num2,
                            'similarity': similarity
                        },
                        line_number=line_num1  # Report primary line number
                    ))
    
    def _check_duplicate_answers(self, df: pd.DataFrame, db_name: str, answer_col='correct_answer'):
        """Check for duplicate answers"""
        if answer_col not in df.columns:
            return
            
        answers = df[answer_col].dropna().astype(str)
        answer_counts = answers.str.lower().value_counts()
        duplicates = answer_counts[answer_counts > 1]
        
        for answer, count in duplicates.items():
            # Find all questions with this answer
            matching_rows = df[df[answer_col].str.lower() == answer.lower()]
            qids = []
            questions = []
            line_numbers = []
            
            for idx, row in matching_rows.iterrows():
                qid = row['qid'] if 'qid' in df.columns else "unknown"
                question = row['question'] if 'question' in df.columns else "unknown"
                line_num = idx + 2  # +2 because pandas index starts at 0, and we skip header
                qids.append(qid)
                questions.append(question)
                line_numbers.append(line_num)
            
            # Use the first occurrence line number for reporting
            primary_line = line_numbers[0] if line_numbers else None
            line_nums_str = ', '.join(map(str, line_numbers))
            
            self.issues.append(DatabaseHealthIssue(
                database=db_name,
                issue_type='duplicate',
                severity='info' if count <= 3 else 'warning',
                description=f"Answer '{answer}' appears {count} times - QIDs: {', '.join(map(str, qids))} (lines: {line_nums_str})",
                affected_data={
                    'answer': answer,
                    'count': count,
                    'qids': qids,
                    'questions': questions,
                    'line_numbers': line_numbers
                },
                line_number=primary_line
            ))
    
    def _check_similar_trivia_answers(self, df: pd.DataFrame, db_name: str, answer_col='correct_answer', similarity_threshold=0.85):
        """Check for similar answers using fuzzy string matching"""
        if answer_col not in df.columns:
            return
            
        answers = df[answer_col].dropna().astype(str).tolist()
        processed_pairs = set()
        
        for i, a1 in enumerate(answers):
            for j, a2 in enumerate(answers[i+1:], i+1):
                # Skip exact matches (handled by duplicate check)
                if a1.lower() == a2.lower():
                    continue
                    
                similarity = SequenceMatcher(None, a1.lower().strip(), a2.lower().strip()).ratio()
                if similarity >= similarity_threshold:
                    pair_key = tuple(sorted([i, j]))
                    if pair_key not in processed_pairs:
                        processed_pairs.add(pair_key)
                        
                        qid1 = df.iloc[i]['qid'] if 'qid' in df.columns else f"row_{i}"
                        qid2 = df.iloc[j]['qid'] if 'qid' in df.columns else f"row_{j}"
                        q1 = df.iloc[i]['question'] if 'question' in df.columns else "unknown"
                        q2 = df.iloc[j]['question'] if 'question' in df.columns else "unknown"
                        
                        # Use the first occurrence line number for reporting
                        line_num1 = i + 2  # +2 because pandas index starts at 0, and we skip header
                        line_num2 = j + 2
                        
                        self.issues.append(DatabaseHealthIssue(
                            database=db_name,
                            issue_type='duplicate',
                            severity='warning',
                            description=f"Similar answers detected (similarity: {similarity:.3f}): '{a1}' (line {line_num1}) and '{a2}' (line {line_num2}) (QIDs: {qid1}, {qid2})",
                            affected_data={
                                'qid1': qid1, 'question1': q1, 'answer1': a1, 'line1': line_num1,
                                'qid2': qid2, 'question2': q2, 'answer2': a2, 'line2': line_num2,
                                'similarity': similarity
                            },
                            line_number=line_num1  # Report primary line number
                        ))
    
    def _check_scramble_duplicates(self, df: pd.DataFrame, db_name: str):
        """Check for duplicate scramble words"""
        if 'word' in df.columns:
            duplicate_words = df[df['word'].duplicated(keep=False)]
            if not duplicate_words.empty:
                for idx, row in duplicate_words.iterrows():
                    self.issues.append(DatabaseHealthIssue(
                        database=db_name,
                        issue_type='duplicate',
                        severity='warning',
                        description=f"Duplicate scramble word: {row['word']}",
                        affected_data=row.to_dict(),
                        line_number=idx + 2  # +2 because pandas index starts at 0, and we skip header
                    ))
    
    def _check_user_data_duplicates(self, df: pd.DataFrame, db_name: str):
        """Check for duplicate users"""
        if 'username' in df.columns:
            duplicate_users = df[df['username'].duplicated(keep=False)]
            if not duplicate_users.empty:
                for idx, row in duplicate_users.iterrows():
                    self.issues.append(DatabaseHealthIssue(
                        database=db_name,
                        issue_type='duplicate',
                        severity='critical',
                        description=f"Duplicate user found: {row['username']}",
                        affected_data=row.to_dict(),
                        line_number=idx + 2  # +2 because pandas index starts at 0, and we skip header
                    ))
    
    def _check_csv_malformation(self, db_name: str, db_path: str):
        """Check for malformed CSV lines that could cause parsing issues"""
        try:
            with open(db_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            
            # Try fallback encodings if UTF-8 fails
            used_fallback_encoding = False
            fallback_encoding_used = None
            if not lines or any('�' in line for line in lines):
                for encoding in ['latin-1', 'cp1252']:
                    try:
                        with open(db_path, 'r', encoding=encoding) as f:
                            lines = f.readlines()
                        used_fallback_encoding = True
                        fallback_encoding_used = encoding
                        break
                    except UnicodeDecodeError:
                        continue
            
            # Report if fallback encoding was used
            if used_fallback_encoding:
                self.issues.append(DatabaseHealthIssue(
                    database=db_name,
                    issue_type='encoding_issue',
                    severity='warning',
                    description=f"File required fallback encoding '{fallback_encoding_used}' instead of UTF-8, indicating potential encoding issues",
                    location="file encoding"
                ))
            
            if not lines:
                return
                
            # Get expected field count from header
            header_line = lines[0].strip()
            if not header_line:
                self.issues.append(DatabaseHealthIssue(
                    database=db_name,
                    issue_type='csv_malformation',
                    severity='critical',
                    description="CSV file has empty or missing header line",
                    location="line 1"
                ))
                return
            
            # Parse header to get expected field count
            try:
                header_fields = list(csv.reader([header_line]))[0]
                expected_field_count = len(header_fields)
            except Exception as e:
                self.issues.append(DatabaseHealthIssue(
                    database=db_name,
                    issue_type='csv_malformation',
                    severity='critical',
                    description=f"Could not parse header line: {e}",
                    location="line 1",
                    affected_data=header_line
                ))
                return
            
            # Check each data line for malformation
            for line_num, line in enumerate(lines[1:], 2):  # Start from line 2
                raw_line = line.rstrip('\n\r')
                
                # Skip empty lines
                if not raw_line.strip():
                    continue
                
                # Check for concatenated lines (missing newlines)
                if self._detect_concatenated_lines(raw_line, expected_field_count):
                    self.issues.append(DatabaseHealthIssue(
                        database=db_name,
                        issue_type='csv_malformation',
                        severity='critical',
                        description="Multiple CSV records concatenated without newline separator",
                        location=f"line {line_num}",
                        affected_data=raw_line[:100] + "..." if len(raw_line) > 100 else raw_line
                    ))
                
                # Check field count consistency
                try:
                    parsed_fields = list(csv.reader([raw_line]))[0]
                    actual_field_count = len(parsed_fields)
                    
                    if actual_field_count != expected_field_count:
                        self.issues.append(DatabaseHealthIssue(
                            database=db_name,
                            issue_type='csv_malformation',
                            severity='warning',
                            description=f"Field count mismatch: expected {expected_field_count}, got {actual_field_count}",
                            location=f"line {line_num}",
                            affected_data=raw_line[:100] + "..." if len(raw_line) > 100 else raw_line
                        ))
                
                except csv.Error as e:
                    self.issues.append(DatabaseHealthIssue(
                        database=db_name,
                        issue_type='csv_malformation',
                        severity='critical',
                        description=f"CSV parsing error: {e}",
                        location=f"line {line_num}",
                        affected_data=raw_line[:100] + "..." if len(raw_line) > 100 else raw_line
                    ))
                
                # Check for unescaped quotes and commas
                if self._detect_quote_issues(raw_line):
                    self.issues.append(DatabaseHealthIssue(
                        database=db_name,
                        issue_type='csv_malformation',
                        severity='warning',
                        description="Potentially unescaped quotes or malformed quoting",
                        location=f"line {line_num}",
                        affected_data=raw_line[:100] + "..." if len(raw_line) > 100 else raw_line
                    ))
                    
                # Check for control characters or unusual characters
                if self._detect_control_characters(raw_line):
                    self.issues.append(DatabaseHealthIssue(
                        database=db_name,
                        issue_type='csv_malformation',
                        severity='warning',
                        description="Line contains control characters or unusual whitespace",
                        location=f"line {line_num}",
                        affected_data=repr(raw_line[:100]) + "..." if len(raw_line) > 100 else repr(raw_line)
                    ))
                    
        except Exception as e:
            self.issues.append(DatabaseHealthIssue(
                database=db_name,
                issue_type='csv_malformation',
                severity='critical',
                description=f"Could not check CSV malformation: {e}"
            ))
    
    def _detect_concatenated_lines(self, line: str, expected_field_count: int) -> bool:
        """Detect if line contains multiple concatenated CSV records"""
        # Look for patterns that suggest concatenated lines:
        # 1. Too many fields (significantly more than expected)
        # 2. Records concatenated without proper CSV separation
        # 3. Multiple complete record patterns with specific indicators
        
        try:
            # Quick field count check - only flag if significantly more fields
            rough_field_count = line.count(',') + 1
            if rough_field_count > expected_field_count * 2.0:  # Double the expected fields
                return True
            
            # Look for concatenation patterns that indicate missing newlines
            # Pattern 1: timestamp followed immediately by text without comma
            # Example: "1234.567username" or "1234.567user1,data"
            if re.search(r'\d{10,13}\.\d+[a-zA-Z_]\w*', line):
                return True
            
            # Pattern 2: Multiple complete record structures in one line
            # Look for patterns like: "data,data,timestampuser,data,data,timestamp"
            # This is more specific than just counting timestamps
            if re.search(r'\d{10,13}\.\d+[a-zA-Z_]+[^,]*,.*\d{10,13}\.\d+', line):
                return True
            
            # Pattern 3: Excessive field count combined with timestamp patterns
            # Only trigger if we have way too many fields AND multiple timestamps
            if rough_field_count > expected_field_count * 1.8:
                timestamp_pattern = r'\d{10,13}\.\d+'
                timestamps = re.findall(timestamp_pattern, line)
                # Only flag if we have both too many fields AND it's not just a timestamps-only record
                if len(timestamps) > 1:
                    # Check if this looks like a timestamps file (all fields are timestamps)
                    fields = [field.strip() for field in line.split(',')]
                    timestamp_fields = [field for field in fields if re.match(r'^\d{10,13}\.\d+$', field)]
                    # If most fields are timestamps, this is likely a valid timestamps file
                    if len(timestamp_fields) < len(fields) * 0.8:  # Less than 80% are timestamps
                        return True
                
            return False
            
        except Exception:
            return False
    
    def _detect_quote_issues(self, line: str) -> bool:
        """Detect potential quoting issues in CSV line"""
        # Count quotes - should be even number for properly quoted fields
        quote_count = line.count('"')
        if quote_count > 0 and quote_count % 2 != 0:
            return True
            
        # Look for unescaped quotes in the middle of fields
        # Pattern: text"text (quote not at field boundary)
        if re.search(r'[^,"]"[^,"]', line):
            return True
            
        return False
    
    def _detect_control_characters(self, line: str) -> bool:
        """Detect control characters that shouldn't be in CSV data"""
        # Check for control characters except tab, newline, carriage return
        for char in line:
            if ord(char) < 32 and char not in ['\t', '\n', '\r']:
                return True
        
        # Check for unusual Unicode characters that might indicate encoding issues
        if any(ord(char) > 65535 for char in line):
            return True
            
        return False
    
    def _check_data_integrity(self, db_name: str, db_path: str):
        """Check data integrity and required columns"""
        try:
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(db_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Could not read file with any encoding")
            
            # Database-specific integrity checks
            if db_name == 'trivia':
                self._check_trivia_integrity(df, db_name)
            elif db_name == 'scramble':
                self._check_scramble_integrity(df, db_name)
            elif db_name == 'user_data':
                self._check_user_data_integrity(df, db_name)
                
        except Exception as e:
            self.issues.append(DatabaseHealthIssue(
                database=db_name,
                issue_type='integrity_error',
                severity='critical',
                description=f"Could not check data integrity: {e}"
            ))
    
    def _check_trivia_integrity(self, df: pd.DataFrame, db_name: str):
        """Check trivia database integrity"""
        required_columns = ['question', 'correct_answer']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            self.issues.append(DatabaseHealthIssue(
                database=db_name,
                issue_type='missing_data',
                severity='critical',
                description=f"Missing required columns: {missing_columns}"
            ))
        
        # Check for empty questions or answers
        if 'question' in df.columns:
            empty_questions = df[df['question'].isna() | (df['question'] == '')]
            if not empty_questions.empty:
                for idx, row in empty_questions.iterrows():
                    self.issues.append(DatabaseHealthIssue(
                        database=db_name,
                        issue_type='missing_data',
                        severity='critical',
                        description=f"Empty question found",
                        affected_data=row.to_dict(),
                        line_number=idx + 2  # +2 because pandas index starts at 0, and we skip header
                    ))
        
        if 'correct_answer' in df.columns:
            empty_answers = df[df['correct_answer'].isna() | (df['correct_answer'] == '')]
        else:
            empty_answers = pd.DataFrame()  # No answer column found
            
        if not empty_answers.empty:
            for idx, row in empty_answers.iterrows():
                self.issues.append(DatabaseHealthIssue(
                    database=db_name,
                    issue_type='missing_data',
                    severity='critical',
                    description=f"Empty answer found",
                    affected_data=row.to_dict(),
                    line_number=idx + 2  # +2 because pandas index starts at 0, and we skip header
                ))
    
    def _check_scramble_integrity(self, df: pd.DataFrame, db_name: str):
        """Check scramble database integrity"""
        required_columns = ['word']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            self.issues.append(DatabaseHealthIssue(
                database=db_name,
                issue_type='missing_data',
                severity='critical',
                description=f"Missing required columns: {missing_columns}"
            ))
        
        # Check for empty words
        if 'word' in df.columns:
            empty_words = df[df['word'].isna() | (df['word'] == '')]
            if not empty_words.empty:
                for idx, row in empty_words.iterrows():
                    self.issues.append(DatabaseHealthIssue(
                        database=db_name,
                        issue_type='missing_data',
                        severity='critical',
                        description=f"Empty word found",
                        affected_data=row.to_dict(),
                        line_number=idx + 2  # +2 because pandas index starts at 0, and we skip header
                    ))
            
            # Check for words with spaces (should be single words)
            if not df.empty and 'word' in df.columns:
                multi_word = df[df['word'].str.contains(' ', na=False)]
                if not multi_word.empty:
                    for idx, row in multi_word.iterrows():
                        self.issues.append(DatabaseHealthIssue(
                            database=db_name,
                            issue_type='data_format',
                            severity='warning',
                            description=f"Multi-word entry found: '{row['word']}' (should be single word)",
                            affected_data=row.to_dict(),
                            line_number=idx + 2  # +2 because pandas index starts at 0, and we skip header
                        ))
    
    def _check_user_data_integrity(self, df: pd.DataFrame, db_name: str):
        """Check user data integrity"""
        required_columns = ['username']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            self.issues.append(DatabaseHealthIssue(
                database=db_name,
                issue_type='missing_data',
                severity='critical',
                description=f"Missing required columns: {missing_columns}"
            ))
        
        # Check for empty usernames
        if 'username' in df.columns:
            empty_usernames = df[df['username'].isna() | (df['username'] == '')]
            if not empty_usernames.empty:
                for idx, row in empty_usernames.iterrows():
                    self.issues.append(DatabaseHealthIssue(
                        database=db_name,
                        issue_type='missing_data',
                        severity='critical',
                        description=f"Empty username found",
                        affected_data=row.to_dict(),
                        line_number=idx + 2  # +2 because pandas index starts at 0, and we skip header
                    ))
    
    def _check_file_permissions(self, db_name: str, db_path: str):
        """Check file permissions"""
        try:
            # Check if file is readable
            if not os.access(db_path, os.R_OK):
                self.issues.append(DatabaseHealthIssue(
                    database=db_name,
                    issue_type='permissions',
                    severity='critical',
                    description=f"File is not readable: {db_path}"
                ))
            
            # Check if file is writable
            if not os.access(db_path, os.W_OK):
                self.issues.append(DatabaseHealthIssue(
                    database=db_name,
                    issue_type='permissions',
                    severity='warning',
                    description=f"File is not writable: {db_path}"
                ))
                
        except Exception as e:
            self.issues.append(DatabaseHealthIssue(
                database=db_name,
                issue_type='permissions',
                severity='warning',
                description=f"Could not check file permissions: {e}"
            ))
    
    def generate_report(self) -> str:
        """Generate a comprehensive health report"""
        if not self.issues:
            return "✅ All databases are healthy! No issues detected."
        
        report = []
        report.append("🏥 DATABASE HEALTH REPORT")
        report.append("=" * 50)
        
        # Group issues by severity
        critical_issues = [i for i in self.issues if i.severity == 'critical']
        warning_issues = [i for i in self.issues if i.severity == 'warning']
        info_issues = [i for i in self.issues if i.severity == 'info']
        
        if critical_issues:
            report.append(f"\n🚨 CRITICAL ISSUES ({len(critical_issues)}):")
            for issue in critical_issues:
                report.append(f"  {issue}")
        
        if warning_issues:
            report.append(f"\n⚠️  WARNING ISSUES ({len(warning_issues)}):")
            for issue in warning_issues:
                report.append(f"  {issue}")
        
        if info_issues:
            report.append(f"\nℹ️  INFO ISSUES ({len(info_issues)}):")
            for issue in info_issues:
                report.append(f"  {issue}")
        
        report.append(f"\n📊 SUMMARY:")
        report.append(f"  Total Issues: {len(self.issues)}")
        report.append(f"  Critical: {len(critical_issues)}")
        report.append(f"  Warnings: {len(warning_issues)}")
        report.append(f"  Info: {len(info_issues)}")
        
        return "\n".join(report)
    
    def get_critical_issues(self) -> List[DatabaseHealthIssue]:
        """Get only critical issues that need immediate attention"""
        return [issue for issue in self.issues if issue.severity == 'critical']


def run_health_check(private_data_path: str = "../blammo-bot-private") -> List[DatabaseHealthIssue]:
    """Convenience function to run a full health check"""
    checker = DatabaseHealthChecker(private_data_path)
    issues = checker.check_all_databases()
    
    # Print report
    report = checker.generate_report()
    print(report)
    
    return issues


if __name__ == "__main__":
    # Run health check when called directly
    issues = run_health_check()
    
    # Exit with error code if critical issues found
    critical_issues = [i for i in issues if i.severity == 'critical']
    exit(1 if critical_issues else 0)