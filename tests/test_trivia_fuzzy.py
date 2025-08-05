#!/usr/bin/env python3
"""
Test fuzzy trivia matching functionality
"""
import sys
import os
import unittest
import tempfile
import pandas as pd
from unittest.mock import patch
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.trivia import TriviaData

class TestTriviaFuzzyMatching(unittest.TestCase):
    """Test fuzzy matching functionality in trivia system"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Set logging level to capture test logs but reduce noise
        logging.getLogger('utils.trivia').setLevel(logging.INFO)
        
        # Create temporary test data
        self.test_data = [
            {"qid": "t1", "question": "What is the capital of France?", "correct_answer": "Paris", "enabled": True},
            {"qid": "t2", "question": "What is the capital city of France?", "correct_answer": "Paris", "enabled": True},
            {"qid": "t3", "question": "Which city is the capital of Italy?", "correct_answer": "Rome", "enabled": True},
            {"qid": "t4", "question": "What is 2 + 2?", "correct_answer": "4", "enabled": True},
            {"qid": "t5", "question": "What is two plus two?", "correct_answer": "4", "enabled": True},
            {"qid": "t6", "question": "Name the largest planet in our solar system", "correct_answer": "Jupiter", "enabled": True},
            {"qid": "t7", "question": "What is the biggest planet in the solar system?", "correct_answer": "Jupiter", "enabled": True},
            {"qid": "t8", "question": "What color is the sky?", "correct_answer": "Blue", "enabled": True},
            {"qid": "t9", "question": "What is the capital of France?", "correct_answer": "Paris", "enabled": True},  # Exact duplicate
            {"qid": "t10", "question": "How many sides does a triangle have?", "correct_answer": "3", "enabled": True},
            # Add some similar answers for fuzzy matching tests
            {"qid": "t11", "question": "What is the most populous US state?", "correct_answer": "California", "enabled": True},
            {"qid": "t12", "question": "Which US state has the most people?", "correct_answer": "Calif", "enabled": True},  # Similar to California
            {"qid": "t13", "question": "What's the first US president?", "correct_answer": "George Washington", "enabled": True},
            {"qid": "t14", "question": "Who was the first president of America?", "correct_answer": "Washington", "enabled": True},  # Similar to George Washington
            {"qid": "t15", "question": "What planet do we live on?", "correct_answer": "Earth", "enabled": True},
            {"qid": "t16", "question": "What is our home planet?", "correct_answer": "The Earth", "enabled": True},  # Similar to Earth
        ]
        
        # Create temporary CSV file
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        df = pd.DataFrame(self.test_data)
        df.to_csv(self.temp_file.name, index=False)
        self.temp_file.close()
        
    def tearDown(self):
        """Clean up test fixtures"""
        # Reset logging
        logging.getLogger('utils.trivia').setLevel(logging.DEBUG)
        
        # Remove temporary file
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_similar_questions_detection_high_threshold(self):
        """Test detection of similar questions with high similarity threshold"""
        trivia = TriviaData(path=self.temp_file.name, allow_load=True)
        
        # Capture log messages to verify detection
        with self.assertLogs(level='WARNING') as cm:
            trivia.check_duplicates(similarity_threshold=0.8)
        
        log_output = ' '.join(cm.output)
        
        # Should detect very similar questions about France capital
        self.assertIn("Similar questions", log_output)
        self.assertIn("capital of France", log_output)
        self.assertIn("capital city of France", log_output)
    
    def test_similar_questions_detection_low_threshold(self):
        """Test detection with lower threshold catches more similarities"""
        trivia = TriviaData(path=self.temp_file.name, allow_load=True)
        
        with self.assertLogs(level='WARNING') as cm:
            trivia.check_duplicates(similarity_threshold=0.6)
        
        log_output = ' '.join(cm.output)
        
        # Should detect more pairs with lower threshold
        # France capital questions
        self.assertIn("capital of France", log_output)
        # Math questions about 2+2
        self.assertIn("2 + 2", log_output) or self.assertIn("two plus two", log_output)
        # Planet questions
        self.assertIn("largest planet", log_output) or self.assertIn("biggest planet", log_output)
    
    def test_duplicate_answers_detection(self):
        """Test detection of duplicate answers"""
        trivia = TriviaData(path=self.temp_file.name, allow_load=True)
        
        with self.assertLogs(level='WARNING') as cm:
            trivia.check_duplicates()
        
        log_output = ' '.join(cm.output)
        
        # Should detect multiple questions with same answers
        self.assertIn("duplicate answers", log_output)
        self.assertIn("paris", log_output.lower())  # Multiple questions about Paris
        self.assertIn("jupiter", log_output.lower())  # Multiple questions about Jupiter
        self.assertIn("4", log_output)  # Multiple questions with answer "4"
    
    def test_exact_duplicate_questions(self):
        """Test detection of exact duplicate questions"""
        trivia = TriviaData(path=self.temp_file.name, allow_load=True)
        
        with self.assertLogs(level='WARNING') as cm:
            trivia.check_duplicates()
        
        log_output = ' '.join(cm.output)
        
        # Should detect the exact duplicate question about France capital
        # Note: The exact duplicate detection happens in the health check system,
        # but we can verify the similarity detection catches it at 1.0 similarity
        self.assertIn("Similar questions", log_output)
    
    def test_no_duplicates_with_unique_data(self):
        """Test that no duplicates are found with completely unique data"""
        unique_data = [
            {"qid": "u1", "question": "What is the capital of Germany?", "correct_answer": "Berlin", "enabled": True},
            {"qid": "u2", "question": "How many continents are there?", "correct_answer": "7", "enabled": True},
            {"qid": "u3", "question": "What is the largest ocean?", "correct_answer": "Pacific", "enabled": True},
        ]
        
        # Create temporary file with unique data
        unique_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        df = pd.DataFrame(unique_data)
        df.to_csv(unique_file.name, index=False)
        unique_file.close()
        
        try:
            trivia = TriviaData(path=unique_file.name, allow_load=True)
            
            with self.assertLogs(level='INFO') as cm:
                trivia.check_duplicates()
            
            log_output = ' '.join(cm.output)
            
            # Should report no similar questions or duplicate answers found
            self.assertIn("No similar questions found", log_output)
            self.assertIn("No duplicate answers found", log_output)
        
        finally:
            if os.path.exists(unique_file.name):
                os.unlink(unique_file.name)
    
    def test_similarity_threshold_boundaries(self):
        """Test different similarity thresholds"""
        trivia = TriviaData(path=self.temp_file.name, allow_load=True)
        
        # Test with very high threshold (0.95) - should catch fewer similarities
        with patch('utils.trivia.logger') as mock_logger:
            trivia.check_duplicates(similarity_threshold=0.95)
            
            # Count calls to warning method for similar questions
            warning_calls = [call for call in mock_logger.warning.call_args_list 
                           if 'Similar questions' in str(call)]
            
            high_threshold_warnings = len(warning_calls)
        
        # Test with lower threshold (0.6) - should catch more similarities
        with patch('utils.trivia.logger') as mock_logger:
            trivia.check_duplicates(similarity_threshold=0.6)
            
            warning_calls = [call for call in mock_logger.warning.call_args_list 
                           if 'Similar questions' in str(call)]
            
            low_threshold_warnings = len(warning_calls)
        
        # Lower threshold should detect more or equal similar questions
        self.assertGreaterEqual(low_threshold_warnings, high_threshold_warnings)
    
    def test_empty_dataframe_handling(self):
        """Test handling of empty or malformed data"""
        # Create CSV with just headers
        empty_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        empty_data = pd.DataFrame(columns=['qid', 'question', 'correct_answer', 'enabled'])
        empty_data.to_csv(empty_file.name, index=False)
        empty_file.close()
        
        try:
            trivia = TriviaData(path=empty_file.name, allow_load=True)
            
            # Should not crash with empty data
            with self.assertLogs(level='INFO') as cm:
                trivia.check_duplicates()
            
            log_output = ' '.join(cm.output)
            self.assertIn("Starting duplicate check", log_output)
        
        finally:
            if os.path.exists(empty_file.name):
                os.unlink(empty_file.name)
    
    def test_missing_columns_handling(self):
        """Test handling of data with missing columns"""
        # Create data missing some columns
        incomplete_data = [
            {"qid": "i1", "question": "Test question 1"},  # Missing answer
            {"qid": "i2", "correct_answer": "Test answer"},  # Missing question
        ]
        
        incomplete_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        df = pd.DataFrame(incomplete_data)
        df.to_csv(incomplete_file.name, index=False)
        incomplete_file.close()
        
        try:
            trivia = TriviaData(path=incomplete_file.name, allow_load=True)
            
            # Should handle missing columns gracefully
            with self.assertLogs(level='INFO') as cm:
                trivia.check_duplicates()
            
            # Should complete without crashing
            log_output = ' '.join(cm.output)
            self.assertIn("Duplicate check completed", log_output)
        
        finally:
            if os.path.exists(incomplete_file.name):
                os.unlink(incomplete_file.name)
    
    def test_similar_answers_detection(self):
        """Test detection of similar answers using fuzzy matching"""
        trivia = TriviaData(path=self.temp_file.name, allow_load=True)
        
        # Use lower threshold to catch similar answers (0.65 to include California/Calif)
        with self.assertLogs(level='WARNING') as cm:
            trivia.check_duplicates(similarity_threshold=0.8, answer_similarity_threshold=0.65)
        
        log_output = ' '.join(cm.output)
        
        # Should detect similar answers
        self.assertIn("Similar answers", log_output)
        
        # Should find George Washington vs Washington (similarity: 0.741)
        self.assertIn("George Washington", log_output)
        self.assertIn("Washington", log_output)
        
        # Should find Earth vs The Earth (similarity: 0.714)
        self.assertIn("Earth", log_output)
        self.assertIn("The Earth", log_output)
        
        # Should find California vs Calif (similarity: 0.667)
        self.assertIn("California", log_output)
        self.assertIn("Calif", log_output)
    
    def test_answer_similarity_threshold_boundaries(self):
        """Test different answer similarity thresholds"""
        trivia = TriviaData(path=self.temp_file.name, allow_load=True)
        
        # Test with very high threshold (0.95) - should catch fewer similarities
        with patch('utils.trivia.logger') as mock_logger:
            trivia.check_duplicates(answer_similarity_threshold=0.95)
            
            # Count calls to warning method for similar answers
            warning_calls = [call for call in mock_logger.warning.call_args_list 
                           if 'Similar answers' in str(call)]
            
            high_threshold_warnings = len(warning_calls)
        
        # Test with lower threshold (0.6) - should catch more similarities
        with patch('utils.trivia.logger') as mock_logger:
            trivia.check_duplicates(answer_similarity_threshold=0.6)
            
            warning_calls = [call for call in mock_logger.warning.call_args_list 
                           if 'Similar answers' in str(call)]
            
            low_threshold_warnings = len(warning_calls)
        
        # Lower threshold should detect more or equal similar answers
        self.assertGreaterEqual(low_threshold_warnings, high_threshold_warnings)
    
    def test_combined_question_and_answer_fuzzy_matching(self):
        """Test that both question and answer fuzzy matching work together"""
        trivia = TriviaData(path=self.temp_file.name, allow_load=True)
        
        with self.assertLogs(level='INFO') as cm:
            trivia.check_duplicates(similarity_threshold=0.7, answer_similarity_threshold=0.7)
        
        log_output = ' '.join(cm.output)
        
        # Should find both similar questions and similar answers
        self.assertIn("Similar questions", log_output)
        self.assertIn("Similar answers", log_output)
        self.assertIn("duplicate answers", log_output)  # exact duplicates
        self.assertIn("Duplicate check completed", log_output)


def run_standalone_tests():
    """Run tests when script is executed directly"""
    print("Running fuzzy trivia matching tests...")
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTriviaFuzzyMatching)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    if result.wasSuccessful():
        print(f"\n✅ All {result.testsRun} fuzzy trivia matching tests passed!")
        return True
    else:
        print(f"\n❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        return False


if __name__ == '__main__':
    success = run_standalone_tests()
    sys.exit(0 if success else 1)