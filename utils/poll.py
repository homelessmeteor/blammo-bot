import csv
import datetime
import logging
import re
import asyncio
import threading
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PollData:
    def __init__(self, poll_file="../blammo-bot-private/poll_data.csv", votes_file="../blammo-bot-private/poll_votes.csv"):
        self.poll_file = poll_file
        self.votes_file = votes_file
        
        # Poll state
        self.active = False
        self.question = ""
        self.options = []
        self.start_time = None
        self.end_time = None
        self.creator = ""
        self.channel_name = ""
        
        # Vote tracking
        self.votes = {}  # {username: option_index}
        
        # Timer management
        self._timer_task = None
        self._timer_thread = None
        self._stop_timer = threading.Event()
        self._result_callback = None
        self._main_loop = None
        
        # Load existing poll if available
        self._load_poll()
        self._load_votes()
        
        # Start timer if poll is active
        if self.active and not self.is_expired():
            self._start_timer()
    
    def parse_duration(self, duration_str: str) -> int:
        """Parse duration string into seconds.
        
        Supports formats like: 30s, 5m, 2h, 1d, 2w
        Returns duration in seconds.
        """
        pattern = r'^(\d+)([smhdw])$'
        match = re.match(pattern, duration_str.lower())
        
        if not match:
            raise ValueError(f"Invalid duration format: {duration_str}. Use format like 30s, 5m, 2h, 1d, 2w")
        
        amount, unit = match.groups()
        amount = int(amount)
        
        multipliers = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400,
            'w': 604800
        }
        
        total_seconds = amount * multipliers[unit]
        
        # Enforce limits: 5 seconds to 2 weeks
        if total_seconds < 5:
            raise ValueError("Minimum poll duration is 5 seconds")
        if total_seconds > 1209600:  # 2 weeks
            raise ValueError("Maximum poll duration is 2 weeks")
            
        return total_seconds
    
    def set_result_callback(self, callback):
        """Set callback function to be called when poll expires."""
        self._result_callback = callback
    
    def set_main_loop(self, loop):
        """Set the main event loop for scheduling callbacks."""
        self._main_loop = loop
    
    def _start_timer(self):
        """Start the poll expiration timer."""
        if not self.active or self.is_expired():
            return
            
        remaining_time = (self.end_time - datetime.datetime.now()).total_seconds()
        if remaining_time <= 0:
            return
            
        self._stop_timer.clear()
        self._timer_thread = threading.Thread(target=self._timer_worker, args=(remaining_time,), daemon=True)
        self._timer_thread.start()
        logger.debug(f"Started poll timer for {remaining_time} seconds")
    
    def _stop_timer_thread(self):
        """Stop the current timer thread."""
        if self._timer_thread and self._timer_thread.is_alive():
            self._stop_timer.set()
            self._timer_thread.join(timeout=1.0)
            logger.debug("Stopped poll timer")
    
    def _timer_worker(self, delay_seconds):
        """Timer worker that runs in a separate thread."""
        if self._stop_timer.wait(timeout=delay_seconds):
            # Timer was stopped
            return
            
        # Timer expired - end the poll
        logger.info("Poll timer expired, ending poll")
        result = self._stop_poll_internal()
        
        # Call result callback if set
        if self._result_callback:
            try:
                # Since we're in a thread, we need to schedule the async callback
                # in the main event loop
                if self._main_loop:
                    # Schedule the callback in the main event loop
                    asyncio.run_coroutine_threadsafe(self._result_callback(result), self._main_loop)
                else:
                    logger.warning("No main event loop available for poll expiration callback")
            except Exception as e:
                logger.error(f"Error calling poll result callback: {e}")
    
    def start_poll(self, question: str, options: List[str], duration: str, creator: str, channel_name: str = "") -> str:
        """Start a new poll."""
        if self.active:
            return "A poll is already active. Stop it first with #poll stop"
        
        if len(options) < 2:
            return "Poll must have at least 2 options"
        
        if len(options) > 10:
            return "Poll cannot have more than 10 options"
        
        try:
            duration_seconds = self.parse_duration(duration)
        except ValueError as e:
            return str(e)
        
        # Set poll state
        self.active = True
        self.question = question
        self.options = options
        self.start_time = datetime.datetime.now()
        self.end_time = self.start_time + datetime.timedelta(seconds=duration_seconds)
        self.creator = creator
        self.channel_name = channel_name
        self.votes = {}
        
        # Save to file
        self._save_poll()
        self._save_votes()
        
        # Start the timer
        self._start_timer()
        
        # Format options for display
        options_text = "\n".join([f"{i+1}). {option}" for i, option in enumerate(options)])
        
        duration_display = self._format_duration(duration_seconds)
        
        return (f"NOTED Poll started by {creator}: {question}\n"
                f"{options_text}\n|| "
                f"Vote with #pollvote <number> or #pollvote <option> || Duration: {duration_display}")
    
    def _stop_poll_internal(self) -> str:
        """Internal method to stop poll without stopping timer (for use within timer thread)."""
        if not self.active:
            return "No active poll to stop"
        
        results = self.get_results()
        self.active = False
        self._save_poll()
        self._clear_votes()
        
        return f"Latege \n{results}"
    
    def stop_poll(self) -> str:
        """Stop the current poll and return results."""
        if not self.active:
            return "No active poll to stop"
        
        # Stop the timer (only if not called from within timer thread)
        self._stop_timer_thread()
        
        return self._stop_poll_internal()
    
    def extend_poll(self, duration: str) -> str:
        """Extend the current poll duration."""
        if not self.active:
            return "No active poll to extend"
        
        try:
            extension_seconds = self.parse_duration(duration)
        except ValueError as e:
            return str(e)
        
        old_end = self.end_time
        self.end_time = self.end_time + datetime.timedelta(seconds=extension_seconds)
        
        # Check if new end time exceeds 2 weeks from start
        max_end = self.start_time + datetime.timedelta(weeks=2)
        if self.end_time > max_end:
            self.end_time = old_end
            return "Cannot extend poll beyond 2 weeks total duration"
        
        self._save_poll()
        
        # Restart timer with new end time
        self._stop_timer_thread()
        self._start_timer()
        
        extension_display = self._format_duration(extension_seconds)
        new_remaining = self._format_duration(int((self.end_time - datetime.datetime.now()).total_seconds()))
        
        return f"Waiting Poll extended by {extension_display}. Time remaining: {new_remaining}"
    
    def vote(self, username: str, vote_input: str) -> str:
        """Cast or change a vote."""
        if not self.active:
            return "No active poll"
        
        if self.is_expired():
            return "Poll has ended"
        
        # Try to parse as option number first
        option_index = None
        try:
            option_num = int(vote_input)
            if 1 <= option_num <= len(self.options):
                option_index = option_num - 1
        except ValueError:
            # Try to match option text
            vote_lower = vote_input.lower()
            for i, option in enumerate(self.options):
                if vote_lower == option.lower():
                    option_index = i
                    break
        
        if option_index is None:
            options_list = ", ".join([f"{i+1}={opt}" for i, opt in enumerate(self.options)])
            return f"Weirdge Invalid vote. Options: {options_list}"
        
        # Record vote
        old_vote = self.votes.get(username)
        self.votes[username] = option_index
        self._save_votes()
        
        # Return empty string for successful votes (no chat response)
        return ""
    
    def get_results(self) -> str:
        """Get current poll results."""
        if not self.active and not self.votes:
            return "No poll results available"
        
        # Count votes
        vote_counts = [0] * len(self.options)
        for vote in self.votes.values():
            vote_counts[vote] += 1
        
        total_votes = sum(vote_counts)
        
        if total_votes == 0:
            return f"'{self.question}' has ended. No one voted Sadge RainTime"
        
        # Format results
        results = [f"Results: '{self.question}'"]
        
        for i, (option, count) in enumerate(zip(self.options, vote_counts)):
            percentage = (count / total_votes) * 100 if total_votes > 0 else 0
            results.append(f"{i+1}). {option}: {count} votes ({percentage:.1f}%)")
        
        results.append(f"Total votes: {total_votes}")
        
        return "\n".join(results)
    
    def get_status(self) -> str:
        """Get current poll status."""
        if not self.active:
            return "DankG No active poll"
        
        if self.is_expired():
            return "Poll has ended but results not yet displayed"
        
        remaining = int((self.end_time - datetime.datetime.now()).total_seconds())
        remaining_display = self._format_duration(remaining)
        
        total_votes = len(self.votes)
        
        return (f"Active poll by {self.creator}: '{self.question}'\n"
                f"Time remaining: {remaining_display}\n"
                f"Total votes: {total_votes}")
    
    def is_expired(self) -> bool:
        """Check if the poll has expired."""
        if not self.active:
            return False
        return datetime.datetime.now() >= self.end_time
    
    def check_and_end_expired(self) -> Optional[str]:
        """Check if poll is expired and end it if so. Returns results if ended.
        Note: This is now primarily for safety/backup - the timer should handle expiration."""
        if self.active and self.is_expired():
            return self.stop_poll()
        return None
    
    def _format_duration(self, seconds: int) -> str:
        """Format seconds into human readable duration."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"{days}d {hours}h"
    
    def _save_poll(self):
        """Save poll state to CSV."""
        try:
            with open(self.poll_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['active', 'question', 'options', 'start_time', 'end_time', 'creator', 'channel_name'])
                
                if self.active:
                    options_str = '|'.join(self.options)
                    start_str = self.start_time.isoformat()
                    end_str = self.end_time.isoformat()
                    writer.writerow([self.active, self.question, options_str, start_str, end_str, self.creator, self.channel_name])
                else:
                    writer.writerow([False, '', '', '', '', '', ''])
        except Exception as e:
            logger.error(f"Error saving poll data: {e}")
    
    def _load_poll(self):
        """Load poll state from CSV."""
        try:
            with open(self.poll_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['active'].lower() == 'true':
                        self.active = True
                        self.question = row['question']
                        self.options = row['options'].split('|')
                        self.start_time = datetime.datetime.fromisoformat(row['start_time'])
                        self.end_time = datetime.datetime.fromisoformat(row['end_time'])
                        self.creator = row['creator']
                        self.channel_name = row.get('channel_name', '')  # Handle legacy files without channel_name
                    break
        except FileNotFoundError:
            logger.info("No existing poll data file found")
        except Exception as e:
            logger.error(f"Error loading poll data: {e}")
    
    def _save_votes(self):
        """Save votes to CSV."""
        try:
            with open(self.votes_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['username', 'vote_option'])
                
                for username, vote in self.votes.items():
                    writer.writerow([username, vote])
        except Exception as e:
            logger.error(f"Error saving vote data: {e}")
    
    def _load_votes(self):
        """Load votes from CSV."""
        try:
            with open(self.votes_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                self.votes = {}
                for row in reader:
                    self.votes[row['username']] = int(row['vote_option'])
        except FileNotFoundError:
            logger.info("No existing vote data file found")
        except Exception as e:
            logger.error(f"Error loading vote data: {e}")
    
    def _clear_votes(self):
        """Clear votes file."""
        try:
            with open(self.votes_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['username', 'vote_option'])
        except Exception as e:
            logger.error(f"Error clearing vote data: {e}")