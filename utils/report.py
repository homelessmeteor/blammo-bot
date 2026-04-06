import os
import csv
import datetime
import logging
from pathlib import Path
from utils.stringvalidate import check_string_safety
from utils.dbutils import ensure_file_ends_with_newline

logger = logging.getLogger(__name__)

class GameReporter:
    def __init__(self, csv_path: str = "../blammo-bot-private/game_reports.csv"):
        self.csv_path = csv_path
        self.report_cooldown = {}  # username -> last_report_time
        self.cooldown_seconds = 10  # 1 minute cooldown between reports
        self.max_reason_length = 100
        self.report_window_minutes = 10  # Can report within 10 minutes of round ending
        
        # Ensure CSV file exists with proper headers
        self._ensure_csv_exists()
        
    def _ensure_csv_exists(self):
        """Create CSV file with headers if it doesn't exist"""
        if not os.path.exists(self.csv_path):
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
            
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'report_id',
                    'game_type', 
                    'qid',
                    'question_text',
                    'answer_text',
                    'reporting_user',
                    'report_reason',
                    'report_timestamp',
                    'round_ended_timestamp'
                ])
            logger.info(f"Created game_reports.csv at {self.csv_path}")
    
    def _generate_report_id(self) -> str:
        """Generate unique report ID"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        return f"r{timestamp}"
    
    def _is_user_on_cooldown(self, username: str) -> bool:
        """Check if user is on cooldown"""
        if username not in self.report_cooldown:
            return False
            
        last_report = self.report_cooldown[username]
        time_since_last = datetime.datetime.now() - last_report
        return time_since_last.total_seconds() < self.cooldown_seconds
    
    def _validate_reason(self, reason: str) -> tuple[bool, str]:
        """Validate report reason"""
        if not reason or reason.strip() == "":
            return False, "hasCheck Report reason cannot be empty"
            
        reason = reason.strip()
        
        if len(reason) > self.max_reason_length:
            return False, f"NoThanks Report reason too long (max {self.max_reason_length} characters)"
        
        # Check for dangerous strings
        if not check_string_safety(reason):
            return False, "WeirdDude Report reason contains invalid content"
            
        return True, reason
    
    def _is_game_reportable(self, completed_game: dict) -> tuple[bool, str]:
        """Check if completed game is within reporting window"""
        if not completed_game:
            return False, "hasCheck No recent completed game to report"
            
        round_ended = completed_game.get('round_ended_timestamp')
        if not round_ended:
            return False, "hasCheck No completed game found"
            
        time_since_end = datetime.datetime.now() - round_ended
        minutes_since_end = time_since_end.total_seconds() / 60
        
        if minutes_since_end > self.report_window_minutes:
            return False, f"Latege Game is too old to report (ended {minutes_since_end:.1f} minutes ago)"
            
        return True, ""
    
    def _check_duplicate_report(self, username: str, qid: str) -> tuple[bool, str]:
        """Check if user has already reported this specific game"""
        if not os.path.exists(self.csv_path):
            return False, ""
            
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['reporting_user'] == username and row['qid'] == qid:
                        return True, "DankG You have already reported this game"
        except Exception as e:
            logger.error(f"Error checking duplicate reports: {e}")
            
        return False, ""
    
    def submit_report(self, username: str, game_type: str, completed_game: dict, reason: str) -> tuple[bool, str]:
        """Submit a game report"""
        
        # Validate game type
        if game_type not in ['trivia', 'scramble']:
            return False, "Invalid game type. Use 'trivia' or 'scramble'"
        
        # Check cooldown
        if self._is_user_on_cooldown(username):
            time_left = self.cooldown_seconds - (datetime.datetime.now() - self.report_cooldown[username]).total_seconds()
            return False, f"Latege You're on cooldown"
        
        # Validate reason
        reason_valid, reason_result = self._validate_reason(reason)
        if not reason_valid:
            return False, reason_result
        reason = reason_result
        
        # Check if game is reportable
        game_valid, game_error = self._is_game_reportable(completed_game)
        if not game_valid:
            return False, game_error
            
        qid = completed_game.get('qid')
        
        # Check for duplicate report
        is_duplicate, duplicate_error = self._check_duplicate_report(username, qid)
        if is_duplicate:
            return False, duplicate_error
        
        # Generate report data
        report_id = self._generate_report_id()
        report_timestamp = datetime.datetime.now().isoformat()
        round_ended_timestamp = completed_game['round_ended_timestamp'].isoformat()
        
        question_text = completed_game.get('question', completed_game.get('word', ''))
        answer_text = completed_game.get('answer', '')
        
        # Write to CSV
        try:
            # Ensure file ends with newline before appending
            ensure_file_ends_with_newline(self.csv_path)
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    report_id,
                    game_type,
                    qid,
                    question_text,
                    answer_text,
                    username,
                    reason,
                    report_timestamp,
                    round_ended_timestamp
                ])
                
            # Update cooldown
            self.report_cooldown[username] = datetime.datetime.now()
            
            logger.info(f"Report submitted: {username} reported {game_type} {qid} - {reason}")
            return True, f"OKAY Report submitted successfully"
            
        except Exception as e:
            logger.error(f"Error writing report to CSV: {e}")
            return False, "monkaS Failed to submit report. Please try again later"
    
    def submit_report_by_id(self, username: str, game_id: str, reason: str) -> tuple[bool, str]:
        """Submit a report by looking up game data from record_data.csv"""
        
        # Check cooldown
        if self._is_user_on_cooldown(username):
            time_left = self.cooldown_seconds - (datetime.datetime.now() - self.report_cooldown[username]).total_seconds()
            return False, f"Latege You're on cooldown"
        
        # Validate reason
        reason_valid, reason_result = self._validate_reason(reason)
        if not reason_valid:
            return False, reason_result
        reason = reason_result
        
        # Look up game data from record_data.csv
        game_data = self._lookup_game_by_id(game_id)
        if not game_data:
            return False, f"NOPERS Game ID {game_id} not found or too old to report"
        
        # Check for duplicate report
        is_duplicate, duplicate_error = self._check_duplicate_report(username, game_id)
        if is_duplicate:
            return False, duplicate_error
        
        # Generate report data
        report_id = self._generate_report_id()
        report_timestamp = datetime.datetime.now().isoformat()
        
        # Write to CSV
        try:
            # Ensure file ends with newline before appending
            ensure_file_ends_with_newline(self.csv_path)
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    report_id,
                    game_data['game_type'],
                    game_id,
                    game_data['question_string'],
                    game_data['answer_string'],
                    username,
                    reason,
                    report_timestamp,
                    game_data['timestamp']
                ])
                
            # Update cooldown
            self.report_cooldown[username] = datetime.datetime.now()
            
            logger.info(f"Report submitted by ID: {username} reported {game_data['game_type']} {game_id} - {reason}")
            return True, f"OKAY Report submitted successfully for game {game_id}"
            
        except Exception as e:
            logger.error(f"Error writing report to CSV: {e}")
            return False, "monkaS Failed to submit report. Please try again later"
    
    def _lookup_game_by_id(self, game_id: str) -> dict:
        """Look up game data from record_data.csv by game ID"""
        record_data_path = "../blammo-bot-private/record_data.csv"
        
        if not os.path.exists(record_data_path):
            logger.error(f"Record data file not found: {record_data_path}")
            return None
        
        try:
            import pandas as pd
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(record_data_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                logger.error(f"Could not read {record_data_path} with any encoding")
                return None
            
            # Find the game by QID
            game_rows = df[df['qid'] == game_id]
            if game_rows.empty:
                logger.debug(f"Game ID {game_id} not found in record data")
                return None
            
            # Get the most recent entry for this game ID
            game_row = game_rows.iloc[-1]
            
            # Check if game is recent enough to report (within report window)
            try:
                game_timestamp = datetime.datetime.fromtimestamp(float(game_row['timestamp']))
                time_since_game = datetime.datetime.now() - game_timestamp
                if time_since_game.total_seconds() > (self.report_window_minutes * 60):
                    logger.debug(f"Game {game_id} is too old to report ({time_since_game})")
                    return None
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse timestamp for game {game_id}: {e}")
                return None
            
            # Return game data
            return {
                'game_type': game_row['game_type'],
                'question_string': game_row.get('question_string', ''),
                'answer_string': game_row.get('answer_string', ''),
                'timestamp': datetime.datetime.fromtimestamp(float(game_row['timestamp'])).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error looking up game {game_id}: {e}")
            return None

# Global instance
game_reporter = GameReporter()

def submit_report(username: str, game_type: str, completed_game: dict, reason: str) -> tuple[bool, str]:
    """Convenience function for submitting reports"""
    return game_reporter.submit_report(username, game_type, completed_game, reason)

def submit_report_by_id(username: str, game_id: str, reason: str) -> tuple[bool, str]:
    """Convenience function for submitting reports by game ID"""
    return game_reporter.submit_report_by_id(username, game_id, reason)