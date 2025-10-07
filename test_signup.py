#!/usr/bin/env python3
"""
Test script to verify signup functionality
"""
import requests
import json

def test_signup():
    url = 'http://localhost:5000/signup'
    
    # Test data
    test_data = {
        'username': 'testuser123',
        'email': 'test@example.com',
        'password': 'password123',
        'confirm_password': 'password123',
        'role': 'student',
        'terms': 'on'
    }
    
    try:
        response = requests.post(url, data=test_data, allow_redirects=False)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 302:
            print("✓ Signup successful! Redirected to login page.")
            print(f"Redirect location: {response.headers.get('Location', 'Unknown')}")
        elif response.status_code == 200:
            if 'error' in response.text.lower():
                print("✗ Signup failed with error in response")
                # Try to extract error message
                if 'Username already exists' in response.text:
                    print("Error: Username already exists")
                elif 'Email already exists' in response.text:
                    print("Error: Email already exists")
                else:
                    print("Error: Unknown signup error")
            else:
                print("? Signup returned 200 but no redirect - check response")
        else:
            print(f"✗ Unexpected status code: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to the app. Make sure it's running on localhost:5000")
    except Exception as e:
        print(f"✗ Test error: {e}")

if __name__ == '__main__':
    print("Testing QUIZZO signup functionality...")
    test_signup()