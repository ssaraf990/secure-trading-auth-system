#!/usr/bin/env python3
"""
Setup script for Two-Factor Authentication System
This script helps configure the application for first-time use
"""

import os
import sys

def create_config_file():
    """Create a local configuration file"""
    config_content = '''# Local configuration file
# This file contains your personal settings

# Flask Configuration
SECRET_KEY = 'your-secret-key-change-this-in-production'

# Email Configuration
# IMPORTANT: Update these with your actual email settings
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_ADDRESS = 'your-email@gmail.com'
EMAIL_PASSWORD = 'your-app-password'

# Security Configuration
MAX_FAILED_ATTEMPTS = 3
ACCOUNT_LOCK_DURATION_MINUTES = 30
OTP_EXPIRY_MINUTES = 5
'''
    
    if not os.path.exists('config_local.py'):
        with open('config_local.py', 'w') as f:
            f.write(config_content)
        print("✅ Created config_local.py - Please update with your email settings")
        return True
    else:
        print("ℹ️  config_local.py already exists")
        return True

def check_dependencies():
    """Check if required packages are installed"""
    print("Checking dependencies...")
    
    required_packages = ['flask', 'werkzeug']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} is missing")
    
    if missing_packages:
        print(f"\nTo install missing packages, run:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    else:
        print("✅ All required packages are installed")
        return True

def show_setup_instructions():
    """Show setup instructions"""
    print("\n" + "="*60)
    print("SETUP INSTRUCTIONS")
    print("="*60)
    print("\n1. EMAIL CONFIGURATION:")
    print("   - Open config_local.py")
    print("   - Update EMAIL_ADDRESS with your email")
    print("   - Update EMAIL_PASSWORD with your app password")
    print("   - For Gmail: Enable 2FA and generate an App Password")
    print("\n2. RUN THE APPLICATION:")
    print("   python app.py")
    print("\n3. ACCESS THE APPLICATION:")
    print("   Open http://localhost:5000 in your browser")
    print("\n4. TEST THE SYSTEM:")
    print("   python test_app.py")
    print("\n" + "="*60)

def main():
    """Main setup function"""
    print("Two-Factor Authentication System - Setup")
    print("="*40)
    
    # Check if we're in the right directory
    if not os.path.exists('app.py'):
        print("❌ Please run this script from the project directory")
        sys.exit(1)
    
    # Check dependencies
    deps_ok = check_dependencies()
    
    # Create config file
    config_ok = create_config_file()
    
    if deps_ok and config_ok:
        print("\n✅ Setup completed successfully!")
        show_setup_instructions()
    else:
        print("\n❌ Setup incomplete. Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
