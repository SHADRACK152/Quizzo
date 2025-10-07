#!/usr/bin/env python3
"""
Fix virtual classroom table schema to match Flask models
"""
import sqlite3
import os


def fix_schema():
    db_path = 'instance/quizzo.db'
    
    if not os.path.exists(db_path):
        print("Database doesn't exist yet. No fix needed.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Fixing virtual classroom table schema...")
        
        # Drop existing tables
        cursor.execute('DROP TABLE IF EXISTS session_recording')
        cursor.execute('DROP TABLE IF EXISTS session_message')
        cursor.execute('DROP TABLE IF EXISTS session_participant')
        cursor.execute('DROP TABLE IF EXISTS live_session')
        
        print("Dropped existing virtual classroom tables...")
        
        # Create LiveSession table with correct schema
        cursor.execute('''
        CREATE TABLE live_session (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            session_name VARCHAR(200) NOT NULL,
            description VARCHAR(500),
            session_id VARCHAR(100) NOT NULL UNIQUE,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            started_at DATETIME,
            ended_at DATETIME,
            max_participants INTEGER NOT NULL DEFAULT 50,
            is_recording BOOLEAN NOT NULL DEFAULT 0,
            session_type VARCHAR(50) NOT NULL DEFAULT 'lecture',
            password_protected BOOLEAN NOT NULL DEFAULT 0,
            session_password VARCHAR(100),
            FOREIGN KEY (teacher_id) REFERENCES user (id)
        )''')
        
        # Create SessionParticipant table
        cursor.execute('''
        CREATE TABLE session_participant (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            left_at DATETIME,
            is_online BOOLEAN NOT NULL DEFAULT 1,
            role_in_session VARCHAR(20) NOT NULL DEFAULT 'participant',
            camera_enabled BOOLEAN NOT NULL DEFAULT 0,
            microphone_enabled BOOLEAN NOT NULL DEFAULT 0,
            screen_sharing BOOLEAN NOT NULL DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES live_session (id),
            FOREIGN KEY (user_id) REFERENCES user (id)
        )''')
        
        # Create SessionMessage table
        cursor.execute('''
        CREATE TABLE session_message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            message_type VARCHAR(20) NOT NULL DEFAULT 'text',
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES live_session (id),
            FOREIGN KEY (user_id) REFERENCES user (id)
        )''')
        
        # Create SessionRecording table
        cursor.execute('''
        CREATE TABLE session_recording (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            recording_path TEXT NOT NULL,
            duration INTEGER,
            file_size INTEGER,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES live_session (id)
        )''')
        
        conn.commit()
        print("Virtual classroom tables recreated successfully!")
        
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
        print(f"Schema fix error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == '__main__':
    fix_schema()