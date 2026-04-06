import unittest
import tempfile
import os
import sys
import datetime
from unittest.mock import patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.poll import PollData


class TestPollData(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.poll_file = os.path.join(self.temp_dir, "test_poll.csv")
        self.votes_file = os.path.join(self.temp_dir, "test_votes.csv")
        self.poll = PollData(self.poll_file, self.votes_file)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_poll_initialization(self):
        """Test that poll system initializes correctly"""
        self.assertFalse(self.poll.active)
        self.assertEqual(self.poll.question, "")
        self.assertEqual(self.poll.options, [])
        self.assertEqual(self.poll.votes, {})
    
    def test_parse_duration_valid(self):
        """Test valid duration parsing"""
        test_cases = [
            ("30s", 30),
            ("5m", 300),
            ("2h", 7200),
            ("1d", 86400),
            ("2w", 1209600)
        ]
        
        for duration_str, expected in test_cases:
            with self.subTest(duration=duration_str):
                result = self.poll.parse_duration(duration_str)
                self.assertEqual(result, expected)
    
    def test_parse_duration_invalid(self):
        """Test invalid duration parsing"""
        invalid_cases = ["4s", "3w", "invalid", "5x", ""]
        
        for duration_str in invalid_cases:
            with self.subTest(duration=duration_str):
                with self.assertRaises(ValueError):
                    self.poll.parse_duration(duration_str)
    
    def test_start_poll_success(self):
        """Test successful poll creation"""
        question = "What's your favorite color?"
        options = ["Red", "Blue", "Green"]
        duration = "5m"
        creator = "testuser"
        
        result = self.poll.start_poll(question, options, duration, creator)
        
        self.assertIn("NOTED Poll started", result)
        self.assertTrue(self.poll.active)
        self.assertEqual(self.poll.question, question)
        self.assertEqual(self.poll.options, options)
        self.assertEqual(self.poll.creator, creator)
    
    def test_start_poll_already_active(self):
        """Test starting poll when one is already active"""
        self.poll.start_poll("Test?", ["A", "B"], "1m", "user1")
        
        result = self.poll.start_poll("Another?", ["X", "Y"], "1m", "user2")
        
        self.assertIn("already active", result)
    
    def test_start_poll_invalid_options(self):
        """Test poll creation with invalid options"""
        # Too few options
        result = self.poll.start_poll("Test?", ["A"], "1m", "user")
        self.assertIn("at least 2 options", result)
        
        # Too many options
        too_many = [f"Option {i}" for i in range(11)]
        result = self.poll.start_poll("Test?", too_many, "1m", "user")
        self.assertIn("cannot have more than 10 options", result)
    
    def test_vote_success(self):
        """Test successful voting"""
        self.poll.start_poll("Test?", ["A", "B", "C"], "5m", "user")
        
        # Vote by number - should return empty string (silent)
        result = self.poll.vote("voter1", "2")
        self.assertEqual(result, "")
        
        # Vote by text - should return empty string (silent)
        result = self.poll.vote("voter2", "A")
        self.assertEqual(result, "")
        
        # Verify votes were recorded
        self.assertEqual(self.poll.votes["voter1"], 1)  # B is index 1
        self.assertEqual(self.poll.votes["voter2"], 0)  # A is index 0
    
    def test_vote_change(self):
        """Test changing votes"""
        self.poll.start_poll("Test?", ["A", "B"], "5m", "user")
        
        # Initial vote
        result1 = self.poll.vote("voter", "A")
        self.assertEqual(result1, "")  # Silent
        
        # Change vote - should also be silent
        result2 = self.poll.vote("voter", "B")
        self.assertEqual(result2, "")  # Silent
        
        # Verify only latest vote counts
        self.assertEqual(self.poll.votes["voter"], 1)  # B is index 1
    
    def test_vote_invalid_option(self):
        """Test voting for invalid options"""
        self.poll.start_poll("Test?", ["A", "B"], "5m", "user")
        
        # Invalid number
        result = self.poll.vote("voter", "3")
        self.assertIn("Weirdge Invalid vote", result)
        
        # Invalid text
        result = self.poll.vote("voter", "C")
        self.assertIn("Weirdge Invalid vote", result)
    
    def test_vote_no_active_poll(self):
        """Test voting when no poll is active"""
        result = self.poll.vote("voter", "A")
        self.assertIn("No active poll", result)
    
    def test_extend_poll(self):
        """Test extending poll duration"""
        with patch('utils.poll.datetime') as mock_dt:
            # Mock current time
            start_time = datetime.datetime(2023, 1, 1, 12, 0, 0)
            mock_dt.datetime.now.return_value = start_time
            mock_dt.datetime.side_effect = datetime.datetime
            mock_dt.timedelta = datetime.timedelta
            
            self.poll.start_poll("Test?", ["A", "B"], "5m", "user")
            
            # Move forward in time
            current_time = start_time + datetime.timedelta(minutes=2)
            mock_dt.datetime.now.return_value = current_time
            
            result = self.poll.extend_poll("3m")
            self.assertIn("Waiting Poll extended by 3m", result)
    
    def test_extend_poll_max_duration(self):
        """Test extending poll beyond maximum duration"""
        self.poll.start_poll("Test?", ["A", "B"], "1w", "user")
        
        result = self.poll.extend_poll("2w")
        self.assertIn("Cannot extend poll beyond 2 weeks", result)
    
    def test_get_results(self):
        """Test getting poll results"""
        self.poll.start_poll("Test?", ["A", "B", "C"], "5m", "user")
        
        # Add some votes
        self.poll.vote("user1", "A")
        self.poll.vote("user2", "A") 
        self.poll.vote("user3", "B")
        
        result = self.poll.get_results()
        
        self.assertIn("Results: 'Test?'", result)
        self.assertIn("A: 2 votes (66.7%)", result)
        self.assertIn("B: 1 votes (33.3%)", result)
        self.assertIn("C: 0 votes (0.0%)", result)
        self.assertIn("Total votes: 3", result)
    
    def test_stop_poll(self):
        """Test stopping poll"""
        self.poll.start_poll("Test?", ["A", "B"], "5m", "user")
        self.poll.vote("voter", "A")
        
        result = self.poll.stop_poll()
        
        self.assertIn("Latege", result)
        self.assertFalse(self.poll.active)
        self.assertIn("Results:", result)
    
    def test_poll_expiration(self):
        """Test poll expiration"""
        with patch('utils.poll.datetime') as mock_dt:
            start_time = datetime.datetime(2023, 1, 1, 12, 0, 0)
            mock_dt.datetime.now.return_value = start_time
            mock_dt.datetime.side_effect = datetime.datetime
            mock_dt.timedelta = datetime.timedelta
            
            self.poll.start_poll("Test?", ["A", "B"], "1m", "user")
            
            # Move past expiration
            expired_time = start_time + datetime.timedelta(minutes=2)
            mock_dt.datetime.now.return_value = expired_time
            
            self.assertTrue(self.poll.is_expired())
            
            result = self.poll.check_and_end_expired()
            self.assertIn("Latege", result)
            self.assertFalse(self.poll.active)
    
    def test_persistence_poll_data(self):
        """Test that poll data persists to CSV"""
        question = "Test?"
        options = ["A", "B"]
        creator = "user"
        
        self.poll.start_poll(question, options, "5m", creator)
        
        # Create new instance to test loading
        new_poll = PollData(self.poll_file, self.votes_file)
        
        self.assertTrue(new_poll.active)
        self.assertEqual(new_poll.question, question)
        self.assertEqual(new_poll.options, options)
        self.assertEqual(new_poll.creator, creator)
    
    def test_persistence_votes(self):
        """Test that votes persist to CSV"""
        self.poll.start_poll("Test?", ["A", "B"], "5m", "user")
        self.poll.vote("voter1", "A")
        self.poll.vote("voter2", "B")
        
        # Create new instance to test loading
        new_poll = PollData(self.poll_file, self.votes_file)
        
        expected_votes = {"voter1": 0, "voter2": 1}  # A=0, B=1
        self.assertEqual(new_poll.votes, expected_votes)
    
    def test_format_duration(self):
        """Test duration formatting"""
        test_cases = [
            (30, "30s"),
            (90, "1m 30s"), 
            (3661, "1h 1m"),
            (90061, "1d 1h")
        ]
        
        for seconds, expected in test_cases:
            with self.subTest(seconds=seconds):
                result = self.poll._format_duration(seconds)
                self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()