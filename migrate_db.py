#!/usr/bin/env python3
"""
Database migration script to add email column to User table
and create virtual classroom tables
"""
import sqlite3
import os


def migrate_database():
    db_path = 'instance/quizzo.db'
    
    if not os.path.exists(db_path):
        print("Database doesn't exist yet. No migration needed.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if email column exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'email' not in columns:
            print("Adding email column to User table...")
            cursor.execute("ALTER TABLE user ADD COLUMN email TEXT")
            conn.commit()
            print("Email column added successfully!")
        else:
            print("Email column already exists.")
        
        # Add missing columns to Challenge table
        print("Checking Challenge table columns...")
        cursor.execute("PRAGMA table_info(challenge)")
        challenge_columns = [column[1] for column in cursor.fetchall()]
        
        if 'max_attempts' not in challenge_columns:
            print("Adding max_attempts column to Challenge table...")
            cursor.execute("ALTER TABLE challenge ADD COLUMN max_attempts INTEGER DEFAULT 3")
            conn.commit()
            print("max_attempts column added successfully!")
        else:
            print("max_attempts column already exists.")
            
        if 'passing_score' not in challenge_columns:
            print("Adding passing_score column to Challenge table...")
            cursor.execute("ALTER TABLE challenge ADD COLUMN passing_score INTEGER DEFAULT 70")
            conn.commit()
            print("passing_score column added successfully!")
        else:
            print("passing_score column already exists.")
        
        # Create virtual classroom tables
        print("Creating virtual classroom tables...")
        
        # LiveSession table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS live_session (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            session_name TEXT NOT NULL,
            description TEXT,
            session_id TEXT UNIQUE NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            max_participants INTEGER DEFAULT 50,
            is_recording BOOLEAN DEFAULT 0,
            session_type TEXT DEFAULT 'lecture',
            password_protected BOOLEAN DEFAULT 0,
            session_password TEXT,
            FOREIGN KEY (teacher_id) REFERENCES user (id)
        )''')
        
        # SessionParticipant table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_participant (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            left_at TIMESTAMP,
            is_online BOOLEAN DEFAULT 1,
            role_in_session TEXT DEFAULT 'participant',
            camera_enabled BOOLEAN DEFAULT 0,
            microphone_enabled BOOLEAN DEFAULT 0,
            screen_sharing BOOLEAN DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES live_session (id),
            FOREIGN KEY (user_id) REFERENCES user (id),
            UNIQUE(session_id, user_id)
        )''')
        
        # SessionMessage table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            message_type TEXT DEFAULT 'text',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES live_session (id),
            FOREIGN KEY (user_id) REFERENCES user (id)
        )''')
        
        # SessionRecording table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_recording (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            recording_path TEXT NOT NULL,
            duration INTEGER,
            file_size INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES live_session (id)
        )''')
        
        conn.commit()
        print("Virtual classroom tables created successfully!")
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [table[0] for table in cursor.fetchall()]
        
        virtual_tables = ['live_session', 'session_participant',
                          'session_message', 'session_recording']
        for table in virtual_tables:
            if table in tables:
                print(f"✓ Table '{table}' exists")
            else:
                print(f"✗ Table '{table}' missing")
            
    except Exception as e:
        print(f"Migration error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == '__main__':
    migrate_database()