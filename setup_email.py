#!/usr/bin/env python3
"""
Email Setup Helper for Two-Factor Authentication System
This script helps you configure Gmail SMTP settings
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_email_configuration(email, password):
    """Test email configuration"""
    try:
        print(f"Testing email configuration for {email}...")
        
        # Create test message
        msg = MIMEMultipart()
        msg['From'] = email
        msg['To'] = email
        msg['Subject'] = "Test Email - Two-Factor Authentication System"
        
        body = """
        This is a test email from your Two-Factor Authentication System.
        
        If you receive this email, your configuration is working correctly!
        
        You can now use the system with full email functionality.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Test SMTP connection
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email, password)
        
        # Send test email
        text = msg.as_string()
        server.sendmail(email, email, text)
        server.quit()
        
        print("✅ Email configuration successful!")
        print(f"✅ Test email sent to {email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure you're using an App Password, not your regular password")
        print("2. Enable 2-Factor Authentication on your Google account")
        print("3. Generate a new App Password specifically for this application")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def update_app_config(email, password):
    """Update app.py with email configuration"""
    try:
        # Read current app.py
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Replace email configuration
        content = content.replace(
            "EMAIL_ADDRESS = 'ssaraf990@gmail.com'  # Your email",
            f"EMAIL_ADDRESS = '{email}'  # Your email"
        )
        content = content.replace(
            "EMAIL_PASSWORD = 'your-app-password'  # You need to set this to your Gmail App Password",
            f"EMAIL_PASSWORD = '{password}'  # Gmail App Password"
        )
        
        # Write back to app.py
        with open('app.py', 'w') as f:
            f.write(content)
        
        print("✅ app.py updated with your email configuration")
        return True
        
    except Exception as e:
        print(f"❌ Error updating app.py: {e}")
        return False

def main():
    """Main setup function"""
    print("=" * 60)
    print("📧 EMAIL SETUP FOR TWO-FACTOR AUTHENTICATION SYSTEM")
    print("=" * 60)
    
    print("\n📋 Before we start, you need to:")
    print("1. Enable 2-Factor Authentication on your Google account")
    print("2. Generate an App Password for this application")
    print("3. Have your Gmail address and App Password ready")
    
    print("\n🔗 How to get Gmail App Password:")
    print("1. Go to https://myaccount.google.com/security")
    print("2. Under 'Signing in to Google', click '2-Step Verification'")
    print("3. Scroll down and click 'App passwords'")
    print("4. Select 'Mail' and 'Other (custom name)'")
    print("5. Enter 'Two-Factor Auth System' as the name")
    print("6. Copy the generated 16-character password")
    
    print("\n" + "=" * 60)
    
    # Get email configuration
    email = input("\n📧 Enter your Gmail address: ").strip()
    if not email or '@gmail.com' not in email:
        print("❌ Please enter a valid Gmail address")
        return
    
    password = input("🔑 Enter your Gmail App Password (16 characters): ").strip()
    if len(password) != 16:
        print("❌ App Password should be 16 characters long")
        return
    
    print(f"\n🧪 Testing email configuration...")
    
    # Test email configuration
    if test_email_configuration(email, password):
        print(f"\n📝 Updating app.py with your configuration...")
        if update_app_config(email, password):
            print("\n🎉 Setup complete!")
            print("✅ Your Two-Factor Authentication System is now configured for email sending")
            print("\n🚀 You can now run: python app.py")
            print("📧 OTP codes will be sent to your email address")
        else:
            print("❌ Failed to update configuration file")
    else:
        print("\n❌ Email configuration failed")
        print("Please check your settings and try again")

if __name__ == "__main__":
    main()
