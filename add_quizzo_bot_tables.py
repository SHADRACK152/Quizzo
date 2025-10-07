#!/usr/bin/env python3
"""
Database migration script to add Quizzo Bot chatbot tables.
This script adds ChatSession and ChatMessage tables for the AI assistant functionality.
"""

import sqlite3
from datetime import datetime

def migrate_database():
    """Add Quizzo Bot chatbot tables to the database"""
    
    # Connect to database
    conn = sqlite3.connect('instance/quizzo.db')
    cursor = conn.cursor()
    
    try:
        print("🚀 Starting database migration for Quizzo Bot...")
        
        # Check if ChatSession table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_session'")
        if not cursor.fetchone():
            print("📝 Creating ChatSession table...")
            cursor.execute("""
                CREATE TABLE chat_session (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    session_title VARCHAR(200),
                    created_at DATETIME NOT NULL,
                    last_activity DATETIME NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES user (id)
                )
            """)
            print("✅ Successfully created ChatSession table")
        else:
            print("✅ ChatSession table already exists")
        
        # Check if ChatMessage table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_message'")
        if not cursor.fetchone():
            print("📝 Creating ChatMessage table...")
            cursor.execute("""
                CREATE TABLE chat_message (
                    id INTEGER PRIMARY KEY,
                    chat_session_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    response TEXT,
                    message_type VARCHAR(20) NOT NULL DEFAULT 'user',
                    sentiment VARCHAR(20),
                    category VARCHAR(50),
                    created_at DATETIME NOT NULL,
                    response_time_ms INTEGER,
                    is_helpful BOOLEAN,
                    FOREIGN KEY (chat_session_id) REFERENCES chat_session (id),
                    FOREIGN KEY (user_id) REFERENCES user (id)
                )
            """)
            print("✅ Successfully created ChatMessage table")
        else:
            print("✅ ChatMessage table already exists")
        
        # Commit changes
        conn.commit()
        print("🎉 Database migration completed successfully!")
        
        # Show table structures
        print("\n📋 Quizzo Bot table structures:")
        
        cursor.execute("PRAGMA table_info(chat_session)")
        columns = cursor.fetchall()
        print("\n  ChatSession table:")
        for col in columns:
            print(f"    - {col[1]} ({col[2]})")
        
        cursor.execute("PRAGMA table_info(chat_message)")
        columns = cursor.fetchall()
        print("\n  ChatMessage table:")
        for col in columns:
            print(f"    - {col[1]} ({col[2]})")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()