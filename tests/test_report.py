import unittest
import os
import csv
import tempfile
import datetime
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add the project root to the path so we can import utils modules
import sys
sys.path.append(str(Path(__file__).parent.parent))

from utils.report import GameReporter, submit_report
from utils.stringvalidate import check_string_safety


class TestStringValidation(unittest.TestCase):
    """Test string validation functionality"""
    
    def test_valid_strings(self):
        """Test that valid strings pass validation"""
        valid_strings = [
            "This is a normal report reason",
            "Answer is wrong",
            "Too easy question",
            "Question has typo",
            "Answer should be Paris not London",
            "Good question but answer is incorrect",
            "I think the answer is wrong...",  # Test ellipsis
        ]
        
        for string in valid_strings:
            with self.subTest(string=string):
                self.assertTrue(check_string_safety(string))
    
    def test_invalid_strings(self):
        """Test that dangerous strings fail validation"""
        invalid_strings = [
            "../etc/passwd",  # Path traversal
            "test .. test",   # Double dots (but not ellipsis)
            "a" * 501,        # Too long
            "",               # Empty string
            "__init__",       # Python internals
            "eval(test)",     # Code execution
            "exec(code)",     # Code execution
            "open(file)",     # File operations
            "content\nwith\nnewlines",  # Newlines
        ]
        
        for string in invalid_strings:
            with self.subTest(string=string):
                self.assertFalse(check_string_safety(string))
    
    def test_ellipsis_allowed(self):
        """Test that ellipsis (...) is allowed but double dots (..) are not"""
        self.assertTrue(check_string_safety("This is fine..."))
        self.assertFalse(check_string_safety("This is not.. fine"))


class TestGameReporter(unittest.TestCase):
    """Test the GameReporter class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.temp_dir, "test_reports.csv")
        self.reporter = GameReporter(csv_path=self.csv_path)
        
        # Sample completed games
        self.sample_trivia = {
            'qid': 't12345',
            'question': 'What is the capital of France?',
            'answer': 'Paris',
            'round_ended_timestamp': datetime.datetime.now() - datetime.timedelta(minutes=2)
        }
        
        self.sample_scramble = {
            'qid': 's67890',
            'word': 'TAC',
            'answer': 'CAT',
            'round_ended_timestamp': datetime.datetime.now() - datetime.timedelta(minutes=1)
        }
        
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.csv_path):
            os.remove(self.csv_path)
        os.rmdir(self.temp_dir)
    
    def test_csv_creation(self):
        """Test that CSV file is created with proper headers"""
        self.assertTrue(os.path.exists(self.csv_path))
        
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            expected_headers = [
                'report_id', 'game_type', 'qid', 'question_text', 
                'answer_text', 'reporting_user', 'report_reason',
                'report_timestamp', 'round_ended_timestamp'
            ]
            self.assertEqual(headers, expected_headers)
    
    def test_successful_trivia_report(self):
        """Test successful trivia report submission"""
        success, message = self.reporter.submit_report(
            username="testuser",
            game_type="trivia", 
            completed_game=self.sample_trivia,
            reason="Answer is wrong"
        )
        
        self.assertTrue(success)
        self.assertIn("Report submitted successfully", message)
        
        # Verify CSV content
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            reports = list(reader)
            self.assertEqual(len(reports), 1)
            
            report = reports[0]
            self.assertEqual(report['game_type'], 'trivia')
            self.assertEqual(report['qid'], 't12345')
            self.assertEqual(report['question_text'], 'What is the capital of France?')
            self.assertEqual(report['answer_text'], 'Paris')
            self.assertEqual(report['reporting_user'], 'testuser')
            self.assertEqual(report['report_reason'], 'Answer is wrong')
    
    def test_successful_scramble_report(self):
        """Test successful scramble report submission"""
        success, message = self.reporter.submit_report(
            username="testuser2",
            game_type="scramble",
            completed_game=self.sample_scramble, 
            reason="Too easy"
        )
        
        self.assertTrue(success)
        self.assertIn("Report submitted successfully", message)
        
        # Verify CSV content  
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            reports = list(reader)
            self.assertEqual(len(reports), 1)
            
            report = reports[0]
            self.assertEqual(report['game_type'], 'scramble')
            self.assertEqual(report['qid'], 's67890')
            self.assertEqual(report['question_text'], 'TAC')
            self.assertEqual(report['answer_text'], 'CAT')
    
    def test_invalid_game_type(self):
        """Test rejection of invalid game type"""
        success, message = self.reporter.submit_report(
            username="testuser",
            game_type="invalid",
            completed_game=self.sample_trivia,
            reason="Test reason"
        )
        
        self.assertFalse(success)
        self.assertIn("Invalid game type", message)
    
    def test_empty_reason(self):
        """Test rejection of empty reason"""
        success, message = self.reporter.submit_report(
            username="testuser",
            game_type="trivia",
            completed_game=self.sample_trivia,
            reason=""
        )
        
        self.assertFalse(success)
        self.assertIn("cannot be empty", message)
    
    def test_reason_too_long(self):
        """Test rejection of overly long reason"""
        long_reason = "x" * 201  # Exceeds max length
        success, message = self.reporter.submit_report(
            username="testuser",
            game_type="trivia",
            completed_game=self.sample_trivia,
            reason=long_reason
        )
        
        self.assertFalse(success)
        self.assertIn("too long", message)
    
    def test_dangerous_reason(self):
        """Test rejection of dangerous content in reason"""
        success, message = self.reporter.submit_report(
            username="testuser",
            game_type="trivia",
            completed_game=self.sample_trivia,
            reason="../etc/passwd"
        )
        
        self.assertFalse(success)
        self.assertIn("invalid content", message)
    
    def test_cooldown_enforcement(self):
        """Test that cooldown prevents rapid submissions"""
        # First report should succeed
        success1, _ = self.reporter.submit_report(
            username="testuser",
            game_type="trivia",
            completed_game=self.sample_trivia,
            reason="First report"
        )
        self.assertTrue(success1)
        
        # Second report within cooldown should fail
        success2, message2 = self.reporter.submit_report(
            username="testuser", 
            game_type="trivia",
            completed_game=self.sample_trivia,
            reason="Second report"
        )
        self.assertFalse(success2)
        self.assertIn("cooldown", message2)
    
    def test_duplicate_report_prevention(self):
        """Test that duplicate reports are prevented"""
        # First report
        success1, _ = self.reporter.submit_report(
            username="testuser",
            game_type="trivia",
            completed_game=self.sample_trivia,
            reason="First report"
        )
        self.assertTrue(success1)
        
        # Clear cooldown
        self.reporter.report_cooldown.clear()
        
        # Same user, same QID should be rejected
        success2, message2 = self.reporter.submit_report(
            username="testuser",
            game_type="trivia", 
            completed_game=self.sample_trivia,
            reason="Duplicate report"
        )
        self.assertFalse(success2)
        self.assertIn("already reported", message2)
    
    def test_no_completed_game(self):
        """Test handling when no completed game exists"""
        success, message = self.reporter.submit_report(
            username="testuser",
            game_type="trivia",
            completed_game=None,
            reason="Test reason"
        )
        
        self.assertFalse(success)
        self.assertIn("No recent completed game", message)
    
    def test_old_game_rejection(self):
        """Test rejection of games that are too old to report"""
        old_game = {
            'qid': 't99999',
            'question': 'Old question?',
            'answer': 'Old answer', 
            'round_ended_timestamp': datetime.datetime.now() - datetime.timedelta(minutes=15)
        }
        
        success, message = self.reporter.submit_report(
            username="testuser",
            game_type="trivia",
            completed_game=old_game,
            reason="This is too old"
        )
        
        self.assertFalse(success)
        self.assertIn("too old", message)
    
    def test_multiple_users_can_report_same_game(self):
        """Test that different users can report the same game"""
        # User 1 reports
        success1, _ = self.reporter.submit_report(
            username="user1",
            game_type="trivia",
            completed_game=self.sample_trivia,
            reason="User 1 reason"
        )
        self.assertTrue(success1)
        
        # User 2 should be able to report the same game
        success2, _ = self.reporter.submit_report(
            username="user2", 
            game_type="trivia",
            completed_game=self.sample_trivia,
            reason="User 2 reason"
        )
        self.assertTrue(success2)
        
        # Verify both reports are recorded
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            reports = list(reader)
            self.assertEqual(len(reports), 2)
            
            usernames = [report['reporting_user'] for report in reports]
            self.assertIn('user1', usernames)
            self.assertIn('user2', usernames)


class TestConvenienceFunction(unittest.TestCase):
    """Test the convenience submit_report function"""
    
    def test_convenience_function(self):
        """Test that the convenience function works properly"""
        # Use a temporary file to avoid conflicts with other tests
        temp_dir = tempfile.mkdtemp()
        csv_path = os.path.join(temp_dir, "test_convenience.csv")
        
        # Create a fresh reporter instance
        test_reporter = GameReporter(csv_path=csv_path)
        
        sample_game = {
            'qid': 't999',  # Use unique QID
            'question': 'Test question?',
            'answer': 'Test answer',
            'round_ended_timestamp': datetime.datetime.now() - datetime.timedelta(minutes=1)
        }
        
        # This should work without errors
        success, message = test_reporter.submit_report("testuser_convenience", "trivia", sample_game, "Test reason")
        
        # Debug if it fails
        if not success:
            print(f"Convenience function failed: {message}")
        
        # Should be successful
        self.assertTrue(success)
        self.assertIsInstance(message, str)
        
        # Clean up
        if os.path.exists(csv_path):
            os.remove(csv_path)
        os.rmdir(temp_dir)


if __name__ == '__main__':
    unittest.main()