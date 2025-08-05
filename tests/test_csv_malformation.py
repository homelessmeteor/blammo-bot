#!/usr/bin/env python3
"""
Test CSV malformation detection functionality
"""
import sys
import os
import unittest
import tempfile
import csv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_health import DatabaseHealthChecker, DatabaseHealthIssue

class TestCSVMalformationDetection(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for test databases
        self.temp_dir = tempfile.mkdtemp()
        self.checker = DatabaseHealthChecker(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_concatenated_lines_detection(self):
        """Test detection of concatenated CSV lines (missing newlines)"""
        
        # Create CSV with concatenated lines
        test_path = os.path.join(self.temp_dir, 'concatenated.csv')
        malformed_content = """username,question,answer,word,raw,timestamp
user1,question1,answer1,,,1754427436.142541
user2,question2,answer2,,,1754427653.971256user3,question3,answer3,,,1754427773.971256
user4,question4,answer4,,,1754427800.123456"""
        
        with open(test_path, 'w') as f:
            f.write(malformed_content)
        
        self.checker.databases = {'test': test_path}
        issues = self.checker.check_all_databases()
        
        # Should detect concatenated lines
        concatenated_issues = [issue for issue in issues 
                             if issue.issue_type == 'csv_malformation' 
                             and 'concatenated' in issue.description.lower()]
        
        self.assertTrue(len(concatenated_issues) > 0, 
                       "Should detect concatenated CSV lines")
        self.assertEqual(concatenated_issues[0].severity, 'critical')
    
    def test_field_count_mismatch_detection(self):
        """Test detection of field count mismatches"""
        
        test_path = os.path.join(self.temp_dir, 'field_mismatch.csv')
        malformed_content = """username,question,answer
user1,question1,answer1
user2,question2,answer2,extra_field,another_extra
user3,question3"""
        
        with open(test_path, 'w') as f:
            f.write(malformed_content)
        
        self.checker.databases = {'test': test_path}
        issues = self.checker.check_all_databases()
        
        # Should detect field count mismatches
        field_issues = [issue for issue in issues 
                       if issue.issue_type == 'csv_malformation' 
                       and 'field count' in issue.description.lower()]
        
        self.assertTrue(len(field_issues) >= 2, 
                       "Should detect field count mismatches")
    
    def test_quote_issues_detection(self):
        """Test detection of quote-related malformation"""
        
        test_path = os.path.join(self.temp_dir, 'quote_issues.csv')
        malformed_content = """username,question,answer
user1,question1,answer1
user2,question with "unescaped quote,answer2
user3,"properly quoted, question",answer3"""
        
        with open(test_path, 'w') as f:
            f.write(malformed_content)
        
        self.checker.databases = {'test': test_path}
        issues = self.checker.check_all_databases()
        
        # Should detect quote issues
        quote_issues = [issue for issue in issues 
                       if issue.issue_type == 'csv_malformation' 
                       and 'quote' in issue.description.lower()]
        
        self.assertTrue(len(quote_issues) > 0, 
                       "Should detect quote issues")
    
    def test_empty_header_detection(self):
        """Test detection of empty or missing header"""
        
        test_path = os.path.join(self.temp_dir, 'empty_header.csv')
        malformed_content = """
user1,question1,answer1
user2,question2,answer2"""
        
        with open(test_path, 'w') as f:
            f.write(malformed_content)
        
        self.checker.databases = {'test': test_path}
        issues = self.checker.check_all_databases()
        
        # Should detect empty header
        header_issues = [issue for issue in issues 
                        if issue.issue_type == 'csv_malformation' 
                        and 'header' in issue.description.lower()]
        
        self.assertTrue(len(header_issues) > 0, 
                       "Should detect empty header")
        self.assertEqual(header_issues[0].severity, 'critical')
    
    def test_control_character_detection(self):
        """Test detection of control characters"""
        
        test_path = os.path.join(self.temp_dir, 'control_chars.csv')
        # Create content with control character (null byte)
        malformed_content = "username,question,answer\nuser1,question\x00with_null,answer1\n"
        
        with open(test_path, 'w') as f:
            f.write(malformed_content)
        
        self.checker.databases = {'test': test_path}
        issues = self.checker.check_all_databases()
        
        # Should detect control characters
        control_issues = [issue for issue in issues 
                         if issue.issue_type == 'csv_malformation' 
                         and 'control character' in issue.description.lower()]
        
        self.assertTrue(len(control_issues) > 0, 
                       "Should detect control characters")
    
    def test_valid_csv_no_issues(self):
        """Test that valid CSV doesn't trigger false positives"""
        
        test_path = os.path.join(self.temp_dir, 'valid.csv')
        valid_content = """username,question,answer,word,raw,timestamp
user1,What is 2+2?,4,,,1754427436.142541
user2,"Question with, comma","Answer with, comma",,,1754427653.971256
user3,Normal question,Normal answer,,,1754427773.971256"""
        
        with open(test_path, 'w') as f:
            f.write(valid_content)
        
        self.checker.databases = {'test': test_path}
        issues = self.checker.check_all_databases()
        
        # Should not detect any CSV malformation issues
        malformation_issues = [issue for issue in issues if issue.issue_type == 'csv_malformation']
        
        self.assertEqual(len(malformation_issues), 0, 
                        "Valid CSV should not trigger malformation detection")
    
    def test_comprehensive_malformation_example(self):
        """Test with the comprehensive example from the user"""
        
        test_path = os.path.join(self.temp_dir, 'comprehensive.csv')
        # Your exact examples
        malformed_content = """username,question,answer,word,raw,timestamp
homelessmeteor,test ... test,test,,,1754427436.142541
homelessmeteor,,,cramble,,1754427653.971256homelessmeteor,,,crambletwo,,1754427773.971256
homelessmeteor,"question that includes a , for csv test","answer with , again",,,1754427703.927391"""
        
        with open(test_path, 'w') as f:
            f.write(malformed_content)
        
        self.checker.databases = {'test': test_path}
        issues = self.checker.check_all_databases()
        
        malformation_issues = [issue for issue in issues if issue.issue_type == 'csv_malformation']
        
        # Should detect the concatenated line issue
        concatenated_found = any('concatenated' in issue.description.lower() 
                               for issue in malformation_issues)
        self.assertTrue(concatenated_found, "Should detect concatenated lines from user example")
        
        # Should detect field count mismatch on the concatenated line
        field_count_found = any('field count' in issue.description.lower() 
                              for issue in malformation_issues)
        self.assertTrue(field_count_found, "Should detect field count mismatch")
        
        # The properly quoted line should NOT trigger issues
        self.assertTrue(len(malformation_issues) >= 1, "Should detect at least one malformation issue")
    
    def test_encoding_fallback_detection(self):
        """Test detection of files requiring fallback encoding"""
        
        test_path = os.path.join(self.temp_dir, 'latin1_encoding.csv')
        
        # Create content with Latin-1 specific characters that will fail UTF-8
        latin1_content = "username,question,answer\nuser1,Café question,café answer\n"
        
        # Write with Latin-1 encoding to force fallback
        with open(test_path, 'w', encoding='latin-1') as f:
            f.write(latin1_content)
        
        self.checker.databases = {'test': test_path}
        issues = self.checker.check_all_databases()
        
        # Should detect encoding fallback issue
        encoding_issues = [issue for issue in issues 
                          if issue.issue_type == 'encoding_issue']
        
        self.assertTrue(len(encoding_issues) > 0, 
                       "Should detect encoding fallback issues")
        self.assertEqual(encoding_issues[0].severity, 'warning')
        self.assertIn('latin-1', encoding_issues[0].description.lower())
    
    def test_utf8_no_encoding_issues(self):
        """Test that proper UTF-8 files don't trigger encoding issues"""
        
        test_path = os.path.join(self.temp_dir, 'utf8_proper.csv')
        utf8_content = "username,question,answer\nuser1,What is 2+2?,4\n"
        
        with open(test_path, 'w', encoding='utf-8') as f:
            f.write(utf8_content)
        
        self.checker.databases = {'test': test_path}
        issues = self.checker.check_all_databases()
        
        # Should not detect any encoding issues
        encoding_issues = [issue for issue in issues 
                          if issue.issue_type == 'encoding_issue']
        
        self.assertEqual(len(encoding_issues), 0, 
                        "UTF-8 files should not trigger encoding issues")
    
    def test_timestamps_csv_false_positive_fix(self):
        """Test that valid timestamps CSV doesn't trigger concatenation false positive"""
        
        test_path = os.path.join(self.temp_dir, 'timestamps_valid.csv')
        
        # This is the exact content that was causing false positives
        timestamps_content = """trivia_started,scramble_started,roulette_cmd,last_auto_record_write
1733434800.0,1733434700.0,1733434600.0,1733434500.0"""
        
        with open(test_path, 'w') as f:
            f.write(timestamps_content)
        
        self.checker.databases = {'test': test_path}
        issues = self.checker.check_all_databases()
        
        # Should NOT detect any concatenation issues
        concatenation_issues = [issue for issue in issues 
                              if issue.issue_type == 'csv_malformation' 
                              and 'concatenated' in issue.description.lower()]
        
        self.assertEqual(len(concatenation_issues), 0, 
                        "Valid timestamps CSV should not trigger concatenation detection")
    
    def test_actual_concatenation_still_detected(self):
        """Test that actual concatenated lines are still properly detected after fix"""
        
        test_path = os.path.join(self.temp_dir, 'actual_concat.csv')
        
        # This should still be detected as concatenated
        concat_content = """username,data,timestamp
user1,data1,1733434800.0user2,data2,1733434700.0"""
        
        with open(test_path, 'w') as f:
            f.write(concat_content)
        
        self.checker.databases = {'test': test_path}
        issues = self.checker.check_all_databases()
        
        # Should still detect concatenation
        concatenation_issues = [issue for issue in issues 
                              if issue.issue_type == 'csv_malformation' 
                              and 'concatenated' in issue.description.lower()]
        
        self.assertTrue(len(concatenation_issues) > 0, 
                       "Actual concatenated lines should still be detected")
        self.assertEqual(concatenation_issues[0].severity, 'critical')

if __name__ == '__main__':
    unittest.main(verbosity=2)