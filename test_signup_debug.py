#!/usr/bin/env python3
"""
Test signup with browser simulation to see what's happening
"""
import requests
import time

def test_signup_with_debug():
    base_url = 'http://localhost:5000'
    
    # Test data
    test_data = {
        'username': f'testuser{int(time.time())}',  # Unique username
        'email': f'test{int(time.time())}@example.com',  # Unique email  
        'password': 'password123',
        'confirm_password': 'password123',
        'role': 'student',
        'terms': 'on'
    }
    
    print(f"Testing signup with data: {test_data}")
    
    try:
        # Create a session to maintain cookies
        session = requests.Session()
        
        # First get the signup page to establish session
        get_response = session.get(f'{base_url}/signup')
        print(f"GET /signup status: {get_response.status_code}")
        
        # Now submit the form
        post_response = session.post(f'{base_url}/signup', data=test_data, allow_redirects=False)
        print(f"POST /signup status: {post_response.status_code}")
        
        if post_response.status_code == 302:
            print("✓ Signup successful! Redirected.")
            redirect_url = post_response.headers.get('Location', '')
            print(f"Redirect location: {redirect_url}")
            
            # Follow the redirect to see if success message appears
            if redirect_url:
                if redirect_url.startswith('/'):
                    redirect_url = base_url + redirect_url
                login_response = session.get(redirect_url)
                print(f"Login page status: {login_response.status_code}")
                
                if 'Account created successfully' in login_response.text:
                    print("✓ Success message found on login page!")
                else:
                    print("⚠ Success message not found on login page")
                    
        elif post_response.status_code == 200:
            print("✗ Signup failed - stayed on signup page")
            if 'error' in post_response.text.lower():
                # Try to extract error message
                import re
                error_match = re.search(r'<span[^>]*>([^<]*error[^<]*)</span>', post_response.text, re.IGNORECASE)
                if error_match:
                    print(f"Error found: {error_match.group(1)}")
                else:
                    print("Error indicated but message not found")
            else:
                print("No error message found in response")
        else:
            print(f"✗ Unexpected status code: {post_response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to the app. Make sure it's running on localhost:5000")
    except Exception as e:
        print(f"✗ Test error: {e}")

if __name__ == '__main__':
    print("Testing QUIZZO signup functionality with detailed debugging...")
    test_signup_with_debug()