#!/usr/bin/env python3
"""
Create Example Data Script

This script creates minimal example CSV files that allow main.py to run
without the private database files. Useful for development and testing.
"""

import os
import csv
import datetime
from pathlib import Path

def create_directory(path):
    """Create directory if it doesn't exist"""
    Path(path).mkdir(parents=True, exist_ok=True)
    print(f"✅ Created directory: {path}")

def create_csv_with_headers(filepath, headers, sample_data=None):
    """Create CSV file with headers and optional sample data"""
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        if sample_data:
            for row in sample_data:
                writer.writerow(row)
    
    print(f"✅ Created: {filepath}")

def main():
    """Create all required CSV files for development"""
    
    # Create the private directory
    private_dir = "../blammo-bot-private"
    create_directory(private_dir)
    
    print("\n🗂️  Creating database files...")
    
    # 1. User data (points, gambling losses)
    create_csv_with_headers(
        os.path.join(private_dir, "user_data.csv"),
        ["username", "points", "total_gamble_loss"],
        [
            ["testuser1", "100", "50"],
            ["testuser2", "200", "25"],
            ["admin", "500", "0"]
        ]
    )
    
    # 2. Trivia questions
    create_csv_with_headers(
        os.path.join(private_dir, "trivia.csv"),
        ["qid", "question", "correct_answer", "enabled"],
        [
            ["t001", "What is 2 + 2?", "4", "1"],
            ["t002", "What is the capital of France?", "Paris", "1"],
            ["t003", "Name the largest planet in our solar system", "Jupiter", "1"]
        ]
    )
    
    # 3. Scramble words  
    create_csv_with_headers(
        os.path.join(private_dir, "scramble.csv"),
        ["qid", "word", "enabled"],
        [
            ["s001", "cat", "1"],
            ["s002", "dog", "1"], 
            ["s003", "house", "1"]
        ]
    )
    
    # 4. Timestamps (horizontal format expected by code)
    current_time = datetime.datetime.now().timestamp()
    create_csv_with_headers(
        os.path.join(private_dir, "timestamps.csv"),
        ["trivia_started", "scramble_started", "roulette_cmd", "last_auto_record_write"],
        [
            [str(current_time - 3600), str(current_time - 1800), str(current_time - 900), str(current_time - 300)]
        ]
    )
    
    # 5. Submissions
    create_csv_with_headers(
        os.path.join(private_dir, "submissions.csv"),
        ["submission_id", "username", "content_type", "content", "timestamp", "status"]
    )
    
    # 6. Record data (game results)
    create_csv_with_headers(
        os.path.join(private_dir, "record_data.csv"),
        ["timestamp", "qid", "game_type", "outcome", "time_elapsed", "username", "points_awarded", "guess_string", "guess_similarity", "question_string", "answer_string"]
    )
    
    # 7. Game reports (our new file)
    create_csv_with_headers(
        os.path.join(private_dir, "game_reports.csv"),
        [
            "report_id", "game_type", "qid", "question_text", "answer_text",
            "reporting_user", "report_reason", "report_timestamp", "round_ended_timestamp"
        ]
    )
    
    print(f"\n🎉 All example database files created in {private_dir}/")
    print("\n📝 Files created:")
    
    for file in os.listdir(private_dir):
        if file.endswith('.csv'):
            filepath = os.path.join(private_dir, file)
            size = os.path.getsize(filepath)
            print(f"   • {file} ({size} bytes)")
    
    print("\n✅ You can now run 'python main.py' for development/testing!")
    print("⚠️  Remember: These are minimal example files for development only.")

if __name__ == "__main__":
    main()