#!/usr/bin/env python3
"""
Simple run script for the Two-Factor Authentication System
This script starts the Flask application with proper configuration
"""

import os
import sys
from app import app, init_db

def main():
    """Start the Flask application"""
    print("Starting Two-Factor Authentication System...")
    print("=" * 50)
    
    # Initialize database
    print("Initializing database...")
    init_db()
    print("✅ Database initialized")
    
    # Check if email configuration is set
    from app import EMAIL_ADDRESS, EMAIL_PASSWORD
    if EMAIL_ADDRESS == 'your-email@gmail.com' or EMAIL_PASSWORD == 'your-app-password':
        print("\n⚠️  WARNING: Email configuration not set!")
        print("Please update EMAIL_ADDRESS and EMAIL_PASSWORD in app.py")
        print("Or create config_local.py with your email settings")
        print("\nThe application will start but email features won't work.")
        print("Press Ctrl+C to stop and configure email settings.")
        
        try:
            input("\nPress Enter to continue anyway...")
        except KeyboardInterrupt:
            print("\nExiting...")
            sys.exit(1)
    
    print("\n🚀 Starting Flask application...")
    print("📍 Application URL: http://localhost:5001")
    print("🛑 Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5001)
    except KeyboardInterrupt:
        print("\n\n👋 Application stopped. Goodbye!")

if __name__ == "__main__":
    main()
