#!/usr/bin/env python3
"""
Test script to verify virtual classroom functionality
"""
import requests
import json

BASE_URL = 'http://127.0.0.1:5000'

def test_virtual_classroom():
    """Test virtual classroom endpoints"""
    print("Testing Virtual Classroom Functionality")
    print("=" * 50)
    
    # Test 1: Check if virtual classroom page loads
    try:
        response = requests.get(f'{BASE_URL}/virtual-classroom')
        print(f"✓ Virtual classroom page: Status {response.status_code}")
        if response.status_code != 200:
            print(f"  Error: {response.text[:100]}...")
    except Exception as e:
        print(f"✗ Virtual classroom page failed: {e}")
    
    # Test 2: Check create session endpoint (GET)
    try:
        response = requests.get(f'{BASE_URL}/create-session')
        print(f"✓ Create session page: Status {response.status_code}")
        if response.status_code != 200:
            print(f"  Error: {response.text[:100]}...")
    except Exception as e:
        print(f"✗ Create session page failed: {e}")
    
    # Test 3: Check if live session templates exist
    endpoints_to_check = [
        '/virtual-classroom',
        '/create-session'
    ]
    
    for endpoint in endpoints_to_check:
        try:
            response = requests.get(f'{BASE_URL}{endpoint}')
            if 'error' in response.text.lower() or response.status_code >= 400:
                print(f"✗ {endpoint}: Potential issues detected")
                if response.status_code >= 400:
                    print(f"  Status: {response.status_code}")
            else:
                print(f"✓ {endpoint}: Loading properly")
        except Exception as e:
            print(f"✗ {endpoint}: {e}")

def test_database_tables():
    """Test if database tables exist"""
    import sqlite3
    import os
    
    print("\nTesting Database Tables")
    print("=" * 30)
    
    db_path = 'instance/quizzo.db'
    if not os.path.exists(db_path):
        print("✗ Database file doesn't exist")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if virtual classroom tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [table[0] for table in cursor.fetchall()]
        
        virtual_tables = ['live_session', 'session_participant', 
                         'session_message', 'session_recording']
        
        for table in virtual_tables:
            if table in tables:
                print(f"✓ Table '{table}' exists")
                
                # Check table structure
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                print(f"  Columns: {len(columns)}")
            else:
                print(f"✗ Table '{table}' missing")
    
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    test_database_tables()
    test_virtual_classroom()
    
    print("\nTest completed! Check the results above.")
    print("If you see any ✗ marks, those indicate issues that need fixing.")