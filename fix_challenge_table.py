#!/usr/bin/env python3
"""
Script to fix the Challenge table schema by adding missing columns
"""
import sqlite3
import os

def fix_challenge_table():
    db_path = 'instance/quizzo.db'
    
    if not os.path.exists(db_path):
        print("Database doesn't exist yet.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check current columns
        cursor.execute("PRAGMA table_info(challenge)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Current Challenge table columns: {columns}")
        
        # Add missing columns one by one
        missing_columns = [
            ("topic", "TEXT"),
            ("difficulty", "TEXT DEFAULT 'medium'"),
            ("time_limit_minutes", "INTEGER"),
            ("ai_generated", "BOOLEAN DEFAULT 0"),
            ("max_participants", "INTEGER"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]
        
        for column_name, column_def in missing_columns:
            if column_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE challenge ADD COLUMN {column_name} {column_def}")
                    print(f"Added column: {column_name}")
                except sqlite3.OperationalError as e:
                    print(f"Could not add column {column_name}: {e}")
        
        conn.commit()
        
        # Verify the update
        cursor.execute("PRAGMA table_info(challenge)")
        updated_columns = [column[1] for column in cursor.fetchall()]
        print(f"Updated Challenge table columns: {updated_columns}")
        
        print("Challenge table schema updated successfully!")
        
    except Exception as e:
        print(f"Error updating challenge table: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_challenge_table()