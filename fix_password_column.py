#!/usr/bin/env python3
"""
Database Schema Update: Increase password field length
Fixes the 'value too long for type character varying(120)' error
for PostgreSQL compatibility with scrypt password hashes.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add current directory to path to import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app import app, db

def update_password_column_length():
    """Update the password column length from 120 to 255 characters"""
    
    print("🔧 Updating User password column length...")
    
    try:
        with app.app_context():
            # Get the database engine
            engine = db.engine
            
            print(f"📊 Database type: {engine.dialect.name}")
            
            if engine.dialect.name == 'postgresql':
                # PostgreSQL command to alter column length
                with engine.connect() as conn:
                    # Use transaction to ensure atomicity
                    trans = conn.begin()
                    try:
                        # Alter the password column to support longer hashes
                        sql_command = text('ALTER TABLE "user" ALTER COLUMN password TYPE VARCHAR(255);')
                        conn.execute(sql_command)
                        trans.commit()
                        print("✅ SUCCESS: Password column updated to VARCHAR(255)")
                        
                        # Verify the change
                        verify_sql = text("""
                            SELECT column_name, data_type, character_maximum_length 
                            FROM information_schema.columns 
                            WHERE table_name = 'user' AND column_name = 'password';
                        """)
                        result = conn.execute(verify_sql)
                        row = result.fetchone()
                        if row:
                            print(f"✅ Verified: password column is now {row[1]}({row[2]})")
                        
                    except Exception as e:
                        trans.rollback()
                        raise e
                        
            elif engine.dialect.name == 'sqlite':
                print("📝 SQLite detected - column length is flexible, no migration needed")
                
            else:
                print(f"⚠️  Unknown database type: {engine.dialect.name}")
                
    except Exception as e:
        print(f"❌ ERROR updating password column: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    return True

if __name__ == "__main__":
    print("🔄 Starting password column migration...")
    
    success = update_password_column_length()
    
    if success:
        print("🎉 Migration completed successfully!")
        print("💡 You can now signup with scrypt password hashes")
    else:
        print("💥 Migration failed - check errors above")
        sys.exit(1)