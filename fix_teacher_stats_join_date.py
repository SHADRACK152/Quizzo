#!/usr/bin/env python3
"""
Database migration script to add join_date column to TeacherStats model.
"""

import sqlite3
from datetime import datetime

def migrate_database():
    """Add join_date column to TeacherStats table"""
    
    # Connect to database
    conn = sqlite3.connect('instance/quizzo.db')
    cursor = conn.cursor()
    
    try:
        print("🚀 Starting database migration for TeacherStats join_date...")
        
        # Check if join_date column exists
        cursor.execute("PRAGMA table_info(teacher_stats)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'join_date' not in columns:
            print("📝 Adding 'join_date' column...")
            cursor.execute("ALTER TABLE teacher_stats ADD COLUMN join_date DATETIME")
            
            # Update existing records with current timestamp
            current_time = datetime.now().isoformat()
            cursor.execute("""
                UPDATE teacher_stats 
                SET join_date = ? 
                WHERE join_date IS NULL
            """, (current_time,))
            
            print("✅ Successfully added 'join_date' column")
        else:
            print("✅ 'join_date' column already exists")
        
        # Commit changes
        conn.commit()
        print("🎉 Database migration completed successfully!")
        
        # Show updated table structure
        cursor.execute("PRAGMA table_info(teacher_stats)")
        columns = cursor.fetchall()
        print("\n📋 Updated TeacherStats table structure:")
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