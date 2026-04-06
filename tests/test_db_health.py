#!/usr/bin/env python3
"""
Test cases for database health check functionality
"""
import unittest
import sys
import os
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_health import DatabaseHealthChecker, DatabaseHealthIssue, run_health_check


class TestDatabaseHealthChecker(unittest.TestCase):
    """Test the DatabaseHealthChecker class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.checker = DatabaseHealthChecker(self.temp_dir)
    
    def tearDown(self):
        """Clean up test files"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_merge_conflict_detection(self):
        """Test detection of git merge conflict markers"""
        # Create a test file with merge conflicts
        test_content = """question,correct_answer,enabled,qid
Normal question,Normal answer,TRUE,t1234567890
<<<<<<< HEAD
Conflict question 1,Answer 1,TRUE,t2345678901
=======
Conflict question 2,Answer 2,TRUE,t2345678901
>>>>>>> branch
Another question,Another answer,TRUE,t3456789012"""
        
        test_file = os.path.join(self.temp_dir, 'trivia.csv')
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        # Run health check
        issues = self.checker.check_all_databases()
        
        # Should detect merge conflict markers
        merge_conflicts = [issue for issue in issues if issue.issue_type == 'merge_conflict']
        self.assertGreater(len(merge_conflicts), 0, "Should detect merge conflict markers")
        
        # Check that specific markers are detected
        marker_types = [issue.description for issue in merge_conflicts]
        self.assertTrue(any("<<<<<<< HEAD" in desc for desc in marker_types))
        self.assertTrue(any("=======" in desc for desc in marker_types))
        self.assertTrue(any(">>>>>>> branch" in desc for desc in marker_types))
        
        # Check that line numbers are included in merge conflict issues
        for issue in merge_conflicts:
            self.assertIsNotNone(issue.line_number, "Merge conflict issues should include line numbers")
            self.assertGreater(issue.line_number, 0, "Line numbers should be positive")
            self.assertIn(f"Line: {issue.line_number}", str(issue), "String representation should include line number")
    
    def test_duplicate_detection(self):
        """Test detection of duplicate entries"""
        # Create a test file with duplicate QIDs
        test_content = """question,correct_answer,enabled,qid
Question 1,Answer 1,TRUE,t1234567890
Question 2,Answer 2,TRUE,t2345678901
Question 3,Answer 3,TRUE,t1234567890
Question 4,Answer 4,TRUE,t3456789012"""
        
        test_file = os.path.join(self.temp_dir, 'trivia.csv')
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        # Run health check
        issues = self.checker.check_all_databases()
        
        # Should detect duplicate QIDs
        duplicate_issues = [issue for issue in issues if issue.issue_type == 'duplicate']
        self.assertGreater(len(duplicate_issues), 0, "Should detect duplicate QIDs")
        
        # Check that line numbers are included
        for issue in duplicate_issues:
            self.assertIsNotNone(issue.line_number, "Duplicate issues should include line numbers")
            self.assertGreater(issue.line_number, 1, "Line numbers should be greater than 1 (header is line 1)")
            self.assertIn(f"Line: {issue.line_number}", str(issue), "String representation should include line number")
    
    def test_malformed_csv(self):
        """Test detection of malformed CSV data"""
        # Create a test file with malformed CSV
        test_content = """question,correct_answer,enabled,qid
"Unescaped quote in middle,Answer,TRUE,t1234567890
Normal question,Answer,TRUE,t2345678901
Question with extra,fields,in,the,middle,TRUE,t3456789012"""
        
        test_file = os.path.join(self.temp_dir, 'trivia.csv')
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        # Run health check
        issues = self.checker.check_all_databases()
        
        # Should detect CSV malformation issues
        csv_issues = [issue for issue in issues if issue.issue_type == 'csv_malformation']
        self.assertGreater(len(csv_issues), 0, "Should detect CSV malformation")

    def test_missing_columns(self):
        """Test detection of missing required columns"""
        # Create a test file missing required columns
        test_content = """question,qid
What is the capital of France?,t1234567890
What is 2 + 2?,t2345678901"""
        
        test_file = os.path.join(self.temp_dir, 'trivia.csv')
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        # Run health check
        issues = self.checker.check_all_databases()
        
        # Should detect missing required columns
        missing_data_issues = [issue for issue in issues if issue.issue_type == 'missing_data']
        self.assertGreater(len(missing_data_issues), 0, "Should detect missing required columns")
    
    def test_healthy_database(self):
        """Test that healthy database files don't generate issues"""
        # Create a healthy test file
        test_content = """question,correct_answer,enabled,qid
What is the capital of France?,Paris,TRUE,t1234567890
What is 2 + 2?,4,TRUE,t2345678901
What planet is closest to the sun?,Mercury,TRUE,t3456789012"""
        
        test_file = os.path.join(self.temp_dir, 'trivia.csv')
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        # Run health check
        issues = self.checker.check_all_databases()
        
        # Filter out issues from missing files (we only created trivia.csv)
        trivia_issues = [issue for issue in issues if issue.database == 'trivia']
        
        # Should not have any critical issues for the trivia file
        critical_trivia_issues = [issue for issue in trivia_issues if issue.severity == 'critical']
        self.assertEqual(len(critical_trivia_issues), 0, "Healthy database should not have critical issues")


class TestDatabaseHealthIssue(unittest.TestCase):
    """Test the DatabaseHealthIssue class"""
    
    def test_issue_creation(self):
        """Test creating health issues"""
        issue = DatabaseHealthIssue(
            database="trivia",
            issue_type="duplicate",
            severity="warning",
            description="Test issue",
            location="line 5",
            affected_data={"qid": "t1234567890"}
        )
        
        self.assertEqual(issue.database, "trivia")
        self.assertEqual(issue.issue_type, "duplicate")
        self.assertEqual(issue.severity, "warning")
        self.assertEqual(issue.description, "Test issue")
        self.assertEqual(issue.location, "line 5")
    
    def test_issue_string_representation(self):
        """Test string representation of issues"""
        # Test with line number
        issue_with_line = DatabaseHealthIssue(
            database="trivia",
            issue_type="duplicate",
            severity="critical",
            description="Duplicate QID found",
            line_number=10
        )
        
        issue_str = str(issue_with_line)
        self.assertIn("🚨", issue_str)  # Critical severity emoji
        self.assertIn("trivia", issue_str)
        self.assertIn("Duplicate QID found", issue_str)
        self.assertIn("Line: 10", issue_str)
        
        # Test with location fallback
        issue_with_location = DatabaseHealthIssue(
            database="trivia",
            issue_type="duplicate",
            severity="warning",
            description="Test issue",
            location="file encoding"
        )
        
        location_str = str(issue_with_location)
        self.assertIn("⚠️", location_str)  # Warning severity emoji
        self.assertIn("Location: file encoding", location_str)


class TestHealthCheckReporting(unittest.TestCase):
    """Test health check reporting functionality"""
    
    def test_report_generation(self):
        """Test that reports are generated correctly"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Create a test file with issues
            test_content = """question,correct_answer,enabled,qid
Question 1,Answer 1,TRUE,t1234567890
<<<<<<< HEAD
Conflict question,Conflict answer,TRUE,t2345678901
=======
Different question,Different answer,TRUE,t2345678901
>>>>>>> branch"""
            
            test_file = os.path.join(temp_dir, 'trivia.csv')
            with open(test_file, 'w') as f:
                f.write(test_content)
            
            checker = DatabaseHealthChecker(temp_dir)
            issues = checker.check_all_databases()
            report = checker.generate_report()
            
            # Report should contain key sections
            self.assertIn("DATABASE HEALTH REPORT", report)
            self.assertIn("CRITICAL ISSUES", report)
            self.assertIn("SUMMARY", report)
            
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()