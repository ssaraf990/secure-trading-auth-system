# Gmail Setup Guide for Two-Factor Authentication System

## 🔐 Step-by-Step Gmail App Password Setup

### 1. Enable 2-Factor Authentication
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Under "Signing in to Google", click **"2-Step Verification"**
3. Follow the prompts to enable 2FA if not already enabled

### 2. Generate App Password
1. In the same security page, scroll down to **"App passwords"**
2. Click **"App passwords"**
3. You may need to sign in again
4. Select **"Mail"** from the dropdown
5. Select **"Other (custom name)"** from the second dropdown
6. Enter: `Two-Factor Auth System`
7. Click **"Generate"**
8. **Copy the 16-character password** (it looks like: `abcd efgh ijkl mnop`)

### 3. Configure the Application
Run the email setup script:
```bash
python setup_email.py
```

Or manually update `app.py`:
```python
EMAIL_ADDRESS = 'ssaraf990@gmail.com'  # Your Gmail
EMAIL_PASSWORD = 'your-16-char-app-password'  # The App Password from step 2
```

### 4. Test Email Sending
```bash
python app.py
```

Then try logging in - you should receive emails!

## 🚨 Important Notes

- **Never use your regular Gmail password** - only use App Passwords
- **App Passwords are 16 characters** with spaces (like: `abcd efgh ijkl mnop`)
- **Remove spaces** when entering in the app (like: `abcdefghijklmnop`)
- **Each App Password is unique** - generate a new one if you lose it

## 🔧 Troubleshooting

### "Authentication failed" error:
- Make sure you're using an App Password, not your regular password
- Ensure 2FA is enabled on your Google account
- Try generating a new App Password

### "SMTP error" or connection issues:
- Check your internet connection
- Try using a different network
- Ensure Gmail SMTP is not blocked by firewall

### Still not working?
1. Check the terminal output for specific error messages
2. Verify the App Password is exactly 16 characters
3. Make sure there are no extra spaces in the password
4. Try generating a fresh App Password

## 📧 Email Features

Once configured, you'll receive beautiful HTML emails with:
- Professional styling
- Clear OTP display
- Security warnings
- Expiry information
- Both HTML and plain text versions

## 🛡️ Security

- App Passwords are safer than regular passwords
- They can be revoked anytime from your Google account
- Each application gets its own unique password
- No need to share your main Gmail password
