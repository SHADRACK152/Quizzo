#!/usr/bin/env python3
"""
QUIZZO Startup Script for Render Deployment
Ensures proper database initialization and app startup
"""

import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """Main startup function for Render deployment"""
    print("🚀 Starting QUIZZO Educational Platform")
    print("=" * 50)
    
    # Import and start the app
    from app import app, init_db, update_database
    
    # Initialize database
    print("📊 Initializing database...")
    init_db()
    
    # Update schema if needed
    print("🔄 Updating database schema...")
    update_database()
    
    # Get configuration
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"🌐 Starting server on port {port}")
    print(f"🔧 Debug mode: {debug_mode}")
    db_type = 'PostgreSQL' if os.environ.get('DATABASE_URL') else 'SQLite'
    print(f"💾 Database: {db_type}")
    print("=" * 50)
    
    # Start the Flask application
    app.run(debug=debug_mode, host='0.0.0.0', port=port)


if __name__ == '__main__':
    main()