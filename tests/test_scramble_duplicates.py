#!/usr/bin/env python3
"""
Test scramble duplicate detection functionality
"""
import sys
import os
import unittest
import tempfile
import csv
from unittest.mock import AsyncMock, Mock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock twitchbot before importing
import sys
from unittest.mock import MagicMock
sys.modules['twitchbot'] = MagicMock()
sys.modules['twitchbot.message'] = MagicMock()

from mock_twitchbot import Message
sys.modules['twitchbot'].message.Message = Message

from utils.submit import _check_scramble_duplicate

class TestScrambleDuplicates(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary CSV file for testing
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        self.temp_path = self.temp_file.name
        
        # Write test data to temp file
        test_data = [
            {'word': 'apple', 'enabled': 'TRUE', 'qid': 'SCR001'},
            {'word': 'banana', 'enabled': 'TRUE', 'qid': 'SCR002'},
            {'word': 'cherry', 'enabled': 'FALSE', 'qid': 'SCR003'},
            {'word': 'ORANGE', 'enabled': 'TRUE', 'qid': 'SCR004'}
        ]
        
        writer = csv.DictWriter(self.temp_file, fieldnames=['word', 'enabled', 'qid'])
        writer.writeheader()
        writer.writerows(test_data)
        self.temp_file.close()
        
        # Patch the SCRAMBLE_PATH in submit module
        import utils.submit
        self.original_path = utils.submit.SCRAMBLE_PATH
        utils.submit.SCRAMBLE_PATH = self.temp_path
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Restore original path
        import utils.submit
        utils.submit.SCRAMBLE_PATH = self.original_path
        
        # Remove temp file
        if os.path.exists(self.temp_path):
            os.unlink(self.temp_path)
    
    def test_duplicate_detection_exact_match(self):
        """Test detection of exact duplicate words"""
        import asyncio
        result = asyncio.run(_check_scramble_duplicate('apple'))
        self.assertFalse(result, "Should detect exact duplicate 'apple'")
    
    def test_duplicate_detection_case_insensitive(self):
        """Test case-insensitive duplicate detection"""
        import asyncio
        result = asyncio.run(_check_scramble_duplicate('APPLE'))
        self.assertFalse(result, "Should detect case-insensitive duplicate 'APPLE'")
        
        result = asyncio.run(_check_scramble_duplicate('Orange'))
        self.assertFalse(result, "Should detect case-insensitive duplicate 'Orange'")
    
    def test_new_word_allowed(self):
        """Test that new words are allowed"""
        import asyncio
        result = asyncio.run(_check_scramble_duplicate('grape'))
        self.assertTrue(result, "Should allow new word 'grape'")
    
    def test_disabled_word_still_blocked(self):
        """Test that disabled words are still considered duplicates"""
        import asyncio
        result = asyncio.run(_check_scramble_duplicate('cherry'))
        self.assertFalse(result, "Should block disabled word 'cherry' as duplicate")
    
    def test_missing_file_allows_submission(self):
        """Test behavior when scramble file doesn't exist"""
        import asyncio
        import utils.submit
        original_path = utils.submit.SCRAMBLE_PATH
        utils.submit.SCRAMBLE_PATH = '/nonexistent/path.csv'
        
        try:
            result = asyncio.run(_check_scramble_duplicate('newword'))
            self.assertTrue(result, "Should allow submission when file doesn't exist")
        finally:
            utils.submit.SCRAMBLE_PATH = original_path

class TestScrambleDuplicatesRunner:
    """Test runner for async tests"""
    
    def run_tests(self):
        import asyncio
        
        print("🧪 Testing Scramble Duplicate Detection")
        print("=" * 45)
        
        test_instance = TestScrambleDuplicates()
        test_instance.setUp()
        
        async def run_async_tests():
            tests_passed = 0
            tests_total = 0
            
            test_methods = [
                ('test_duplicate_detection_exact_match', test_instance.test_duplicate_detection_exact_match),
                ('test_duplicate_detection_case_insensitive', test_instance.test_duplicate_detection_case_insensitive),
                ('test_new_word_allowed', test_instance.test_new_word_allowed),
                ('test_disabled_word_still_blocked', test_instance.test_disabled_word_still_blocked),
                ('test_missing_file_allows_submission', test_instance.test_missing_file_allows_submission)
            ]
            
            for test_name, test_method in test_methods:
                tests_total += 1
                try:
                    await test_method()
                    print(f"✅ {test_name}")
                    tests_passed += 1
                except Exception as e:
                    print(f"❌ {test_name}: {e}")
            
            print("\n" + "=" * 45)
            print(f"Tests passed: {tests_passed}/{tests_total}")
            
            if tests_passed == tests_total:
                print("✅ All scramble duplicate tests passed!")
                return True
            else:
                print("❌ Some tests failed")
                return False
        
        try:
            result = asyncio.run(run_async_tests())
            test_instance.tearDown()
            return result
        except Exception as e:
            print(f"Error running async tests: {e}")
            test_instance.tearDown()
            return False

if __name__ == "__main__":
    runner = TestScrambleDuplicatesRunner()
    success = runner.run_tests()
    sys.exit(0 if success else 1)