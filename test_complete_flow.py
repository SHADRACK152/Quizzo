#!/usr/bin/env python3
"""
Complete end-to-end test of signup and login flow
"""
import requests
import time

def test_complete_flow():
    base_url = 'http://localhost:5000'
    timestamp = int(time.time())
    
    # Test data
    test_username = f'endtoend{timestamp}'
    test_email = f'endtoend{timestamp}@example.com'
    test_password = 'testpass123'
    
    signup_data = {
        'username': test_username,
        'email': test_email,
        'password': test_password,
        'confirm_password': test_password,
        'role': 'student',
        'terms': 'on'
    }
    
    print(f"🧪 Testing complete signup → login flow")
    print(f"📝 Username: {test_username}")
    print(f"📧 Email: {test_email}")
    
    try:
        session = requests.Session()
        
        # Step 1: Sign up
        print("\n📋 Step 1: Creating account...")
        signup_response = session.post(f'{base_url}/signup', data=signup_data, allow_redirects=False)
        
        if signup_response.status_code == 302:
            print("✅ Signup successful!")
            
            # Step 2: Check login page for success message
            print("\n📋 Step 2: Checking success message...")
            login_page = session.get(f'{base_url}/login')
            if 'Account created successfully' in login_page.text:
                print("✅ Success message displayed correctly!")
            else:
                print("⚠️ Success message not found")
            
            # Step 3: Try to login with new credentials
            print("\n📋 Step 3: Testing login...")
            login_data = {
                'username': test_username,
                'password': test_password
            }
            
            login_response = session.post(f'{base_url}/login', data=login_data, allow_redirects=False)
            
            if login_response.status_code == 302:
                redirect_location = login_response.headers.get('Location', '')
                if 'dashboard' in redirect_location:
                    print("✅ Login successful! Redirected to dashboard")
                    
                    # Step 4: Access dashboard
                    print("\n📋 Step 4: Accessing dashboard...")
                    dashboard_response = session.get(f'{base_url}/dashboard')
                    if dashboard_response.status_code == 200:
                        print("✅ Dashboard accessible!")
                        print("\n🎉 Complete flow test PASSED!")
                        return True
                    else:
                        print(f"❌ Dashboard not accessible: {dashboard_response.status_code}")
                else:
                    print(f"❌ Login redirect unexpected: {redirect_location}")
            else:
                print(f"❌ Login failed: {login_response.status_code}")
                
        else:
            print(f"❌ Signup failed: {signup_response.status_code}")
            if signup_response.status_code == 200:
                print("Response stayed on signup page - likely validation error")
                
    except Exception as e:
        print(f"❌ Test error: {e}")
        
    print("\n❌ Complete flow test FAILED!")
    return False

if __name__ == '__main__':
    test_complete_flow()