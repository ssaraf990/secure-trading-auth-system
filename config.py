# Configuration file for the Two-Factor Authentication System
# Copy this file to config_local.py and update with your settings

# Flask Configuration
SECRET_KEY = 'your-secret-key-change-this-in-production'

# Database Configuration
DATABASE = 'auth_system.db'

# Email Configuration
# Update these with your email provider settings
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_ADDRESS = 'your-email@gmail.com'
EMAIL_PASSWORD = 'your-app-password'

# Security Configuration
MAX_FAILED_ATTEMPTS = 3
ACCOUNT_LOCK_DURATION_MINUTES = 30
OTP_EXPIRY_MINUTES = 5

# Application Configuration
DEBUG = True
HOST = 'localhost'
PORT = 5000
