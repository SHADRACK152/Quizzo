#!/usr/bin/env python3
"""
Database migration script to add the missing 'level' column to teacher_stats table.
"""

import sqlite3

def migrate_teacher_stats():
    """Add level column to teacher_stats table"""
    
    # Connect to database
    conn = sqlite3.connect('instance/quizzo.db')
    cursor = conn.cursor()
    
    try:
        print("🚀 Starting teacher_stats migration...")
        
        # Check if level column exists
        cursor.execute("PRAGMA table_info(teacher_stats)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'level' not in columns:
            print("📝 Adding 'level' column to teacher_stats table...")
            cursor.execute("ALTER TABLE teacher_stats ADD COLUMN level INTEGER NOT NULL DEFAULT 1")
            print("✅ Successfully added 'level' column")
        else:
            print("ℹ️ 'level' column already exists")
        
        # Update existing records to have proper level values based on points
        cursor.execute("UPDATE teacher_stats SET level = MAX(1, total_points / 100) WHERE level IS NULL OR level = 0")
        affected_rows = cursor.rowcount
        if affected_rows > 0:
            print(f"✅ Updated {affected_rows} teacher records with proper level values")
        
        # Commit changes
        conn.commit()
        print("🎉 Teacher stats migration completed successfully!")
        
        # Show updated table structure
        cursor.execute("PRAGMA table_info(teacher_stats)")
        columns = cursor.fetchall()
        print("\n📋 Updated teacher_stats table structure:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_teacher_stats()