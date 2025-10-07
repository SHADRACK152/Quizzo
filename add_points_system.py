#!/usr/bin/env python3
"""
Database migration script to add points system to ChallengeSession model.
This script adds the 'points_breakdown' column and renames 'points_earned' to 'points'.
"""

import sqlite3
import json
from datetime import datetime

def migrate_database():
    """Add points system columns to ChallengeSession table"""
    
    # Connect to database
    conn = sqlite3.connect('instance/quizzo.db')
    cursor = conn.cursor()
    
    try:
        print("🚀 Starting database migration for points system...")
        
        # Check if we need to rename points_earned to points
        cursor.execute("PRAGMA table_info(challenge_session)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'points_earned' in columns and 'points' not in columns:
            print("📝 Renaming 'points_earned' column to 'points'...")
            # SQLite doesn't support column renaming directly, so we need to recreate the table
            
            # Get current table structure
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='challenge_session'")
            create_sql = cursor.fetchone()[0]
            
            # Get all data from current table
            cursor.execute("SELECT * FROM challenge_session")
            all_data = cursor.fetchall()
            
            # Get column names
            cursor.execute("PRAGMA table_info(challenge_session)")
            column_info = cursor.fetchall()
            old_columns = [col[1] for col in column_info]
            
            # Drop existing table
            cursor.execute("DROP TABLE challenge_session")
            
            # Create new table with updated schema
            new_create_sql = """
            CREATE TABLE challenge_session (
                id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                challenge_id INTEGER NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
                score INTEGER NOT NULL DEFAULT 0,
                percentage FLOAT NOT NULL DEFAULT 0.0,
                time_taken_minutes FLOAT,
                rank INTEGER,
                points INTEGER NOT NULL DEFAULT 0,
                points_breakdown TEXT,
                FOREIGN KEY (student_id) REFERENCES user (id),
                FOREIGN KEY (challenge_id) REFERENCES challenge (id)
            )
            """
            cursor.execute(new_create_sql)
            
            # Insert data back with column mapping
            if all_data:
                # Map old column positions to new columns
                insert_columns = []
                insert_values = []
                
                for row in all_data:
                    values = []
                    for i, col_name in enumerate(old_columns):
                        if col_name == 'points_earned':
                            # Map points_earned to points
                            values.append(row[i])
                        elif col_name in ['id', 'student_id', 'challenge_id', 'start_time', 'end_time', 
                                        'status', 'score', 'percentage', 'time_taken_minutes', 'rank']:
                            values.append(row[i])
                    
                    # Add None for points_breakdown column (new column)
                    values.append(None)
                    insert_values.append(values)
                
                # Insert the data
                placeholders = ','.join(['?' for _ in range(len(values))])
                cursor.executemany(f"""
                    INSERT INTO challenge_session 
                    (id, student_id, challenge_id, start_time, end_time, status, score, 
                     percentage, time_taken_minutes, rank, points, points_breakdown)
                    VALUES ({placeholders})
                """, insert_values)
            
            print("✅ Successfully renamed 'points_earned' to 'points'")
        
        elif 'points' not in columns:
            print("📝 Adding 'points' column...")
            cursor.execute("ALTER TABLE challenge_session ADD COLUMN points INTEGER NOT NULL DEFAULT 0")
            print("✅ Successfully added 'points' column")
        
        # Check if points_breakdown column exists
        cursor.execute("PRAGMA table_info(challenge_session)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'points_breakdown' not in columns:
            print("📝 Adding 'points_breakdown' column...")
            cursor.execute("ALTER TABLE challenge_session ADD COLUMN points_breakdown TEXT")
            print("✅ Successfully added 'points_breakdown' column")
        
        # Commit changes
        conn.commit()
        print("🎉 Database migration completed successfully!")
        
        # Show updated table structure
        cursor.execute("PRAGMA table_info(challenge_session)")
        columns = cursor.fetchall()
        print("\n📋 Updated ChallengeSession table structure:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()