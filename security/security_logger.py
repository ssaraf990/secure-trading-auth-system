"""
🔒 Security Event Logger
Comprehensive logging system for all security-related events
Logs authentication attempts, brute force detection, account locks, and more
"""
import os
import json
from datetime import datetime
from pathlib import Path

# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).parent.parent / 'security_logs'
LOGS_DIR.mkdir(exist_ok=True)

# Log file paths
LOGIN_ATTEMPTS_LOG = LOGS_DIR / 'login_attempts.log'
SECURITY_EVENTS_LOG = LOGS_DIR / 'security_events.log'
BRUTE_FORCE_LOG = LOGS_DIR / 'brute_force_detection.log'
ACCOUNT_LOCKS_LOG = LOGS_DIR / 'account_locks.log'
OTP_ATTEMPTS_LOG = LOGS_DIR / 'otp_attempts.log'
PASSWORD_VERIFICATION_LOG = LOGS_DIR / 'password_verification.log'

def log_event(log_file, event_data):
    """Write event to log file with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {json.dumps(event_data, indent=2)}\n"
    log_entry += "-" * 80 + "\n"
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_entry)

def log_login_attempt(username, ip_address, success, remaining_attempts=None, account_locked=False):
    """Log a login attempt"""
    event = {
        'event_type': 'LOGIN_ATTEMPT',
        'username': username,
        'ip_address': ip_address,
        'success': success,
        'remaining_attempts': remaining_attempts,
        'account_locked': account_locked,
        'timestamp': datetime.now().isoformat()
    }
    
    log_event(LOGIN_ATTEMPTS_LOG, event)
    
    if not success:
        log_event(SECURITY_EVENTS_LOG, {
            **event,
            'severity': 'WARNING' if remaining_attempts and remaining_attempts > 0 else 'CRITICAL'
        })

def log_otp_attempt(username, ip_address, success, remaining_attempts=None, account_locked=False):
    """Log an OTP verification attempt"""
    event = {
        'event_type': 'OTP_VERIFICATION',
        'username': username,
        'ip_address': ip_address,
        'success': success,
        'remaining_attempts': remaining_attempts,
        'account_locked': account_locked,
        'timestamp': datetime.now().isoformat()
    }
    
    log_event(OTP_ATTEMPTS_LOG, event)
    
    if not success:
        log_event(SECURITY_EVENTS_LOG, {
            **event,
            'severity': 'WARNING' if remaining_attempts and remaining_attempts > 0 else 'CRITICAL'
        })

def log_password_verification(username, ip_address, success, purpose='TRADE', remaining_attempts=None, account_locked=False):
    """Log a password verification attempt (for transactions)"""
    event = {
        'event_type': 'PASSWORD_VERIFICATION',
        'purpose': purpose,
        'username': username,
        'ip_address': ip_address,
        'success': success,
        'remaining_attempts': remaining_attempts,
        'account_locked': account_locked,
        'timestamp': datetime.now().isoformat()
    }
    
    log_event(PASSWORD_VERIFICATION_LOG, event)
    
    if not success:
        log_event(SECURITY_EVENTS_LOG, {
            **event,
            'severity': 'WARNING' if remaining_attempts and remaining_attempts > 0 else 'CRITICAL'
        })

def log_brute_force_detection(username, ip_address, failed_attempts, event_type='LOGIN'):
    """Log brute force attack detection"""
    event = {
        'event_type': 'BRUTE_FORCE_DETECTED',
        'attack_type': event_type,
        'username': username,
        'ip_address': ip_address,
        'failed_attempts': failed_attempts,
        'timestamp': datetime.now().isoformat(),
        'severity': 'CRITICAL',
        'action': 'ACCOUNT_LOCKED'
    }
    
    log_event(BRUTE_FORCE_LOG, event)
    log_event(SECURITY_EVENTS_LOG, event)

def log_account_lock(username, ip_address, reason, lock_duration_minutes, unlock_time):
    """Log account lockout event"""
    event = {
        'event_type': 'ACCOUNT_LOCKED',
        'username': username,
        'ip_address': ip_address,
        'reason': reason,
        'lock_duration_minutes': lock_duration_minutes,
        'unlock_time': unlock_time,
        'timestamp': datetime.now().isoformat(),
        'severity': 'CRITICAL'
    }
    
    log_event(ACCOUNT_LOCKS_LOG, event)
    log_event(SECURITY_EVENTS_LOG, event)

def log_account_unlock(username, reason='AUTO_EXPIRE'):
    """Log account unlock event"""
    event = {
        'event_type': 'ACCOUNT_UNLOCKED',
        'username': username,
        'reason': reason,
        'timestamp': datetime.now().isoformat(),
        'severity': 'INFO'
    }
    
    log_event(ACCOUNT_LOCKS_LOG, event)
    log_event(SECURITY_EVENTS_LOG, event)

def log_biometric_attempt(username, success, method='WEBAUTHN'):
    """Log biometric authentication attempt"""
    event = {
        'event_type': 'BIOMETRIC_AUTH',
        'method': method,
        'username': username,
        'success': success,
        'timestamp': datetime.now().isoformat()
    }
    
    log_event(SECURITY_EVENTS_LOG, event)

def log_trade_execution(username, symbol, qty, side, verified_by, amount):
    """Log trade execution with verification method"""
    event = {
        'event_type': 'TRADE_EXECUTED',
        'username': username,
        'symbol': symbol,
        'quantity': qty,
        'side': side,
        'verified_by': verified_by,
        'amount': amount,
        'timestamp': datetime.now().isoformat()
    }
    
    log_event(SECURITY_EVENTS_LOG, event)

def generate_security_report():
    """Generate a comprehensive security report"""
    report_file = LOGS_DIR / f'security_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("SECURITY AUDIT REPORT\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        # Summary section
        f.write("SUMMARY OF SECURITY LOGS\n")
        f.write("-" * 80 + "\n\n")
        
        log_files = [
            ('Login Attempts', LOGIN_ATTEMPTS_LOG),
            ('OTP Verifications', OTP_ATTEMPTS_LOG),
            ('Password Verifications', PASSWORD_VERIFICATION_LOG),
            ('Brute Force Detections', BRUTE_FORCE_LOG),
            ('Account Locks', ACCOUNT_LOCKS_LOG),
            ('All Security Events', SECURITY_EVENTS_LOG)
        ]
        
        for log_name, log_path in log_files:
            if log_path.exists():
                line_count = sum(1 for _ in open(log_path, encoding='utf-8'))
                f.write(f"  {log_name}: {line_count} entries\n")
                f.write(f"    File: {log_path}\n\n")
            else:
                f.write(f"  {log_name}: No entries yet\n\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("SECURITY MEASURES IMPLEMENTED\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("1. BRUTE FORCE PROTECTION\n")
        f.write("   - Maximum failed attempts: 5\n")
        f.write("   - Lock duration: 60 minutes\n")
        f.write("   - Tracking window: 15 minutes\n")
        f.write("   - Tracking method: Username + IP Address\n\n")
        
        f.write("2. AUTHENTICATION LAYERS\n")
        f.write("   - Primary: Username + Password\n")
        f.write("   - Secondary: OTP (Email-based 2FA)\n")
        f.write("   - Optional: Biometric (WebAuthn/Fingerprint)\n\n")
        
        f.write("3. TRANSACTION SECURITY\n")
        f.write("   - Biometric verification for trades\n")
        f.write("   - Password re-verification option\n")
        f.write("   - Session-based verification\n\n")
        
        f.write("4. LOGGING & MONITORING\n")
        f.write("   - All login attempts logged\n")
        f.write("   - Failed attempts with remaining count\n")
        f.write("   - Brute force detection alerts\n")
        f.write("   - Account lock/unlock events\n")
        f.write("   - Trade execution audit trail\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")
    
    return report_file

def create_readme():
    """Create README for security logs"""
    readme_file = LOGS_DIR / 'README.md'
    
    content = """# Security Logs Directory

This directory contains comprehensive security logs for the IS Lab Project.

## Log Files

### 1. login_attempts.log
Records all login attempts with:
- Username
- IP Address
- Success/Failure status
- Remaining attempts before lock
- Account lock status
- Timestamp

### 2. otp_attempts.log
Records all OTP verification attempts with:
- Username
- IP Address
- Success/Failure status
- Remaining attempts
- Timestamp

### 3. password_verification.log
Records password verification for sensitive operations:
- Username
- IP Address
- Purpose (TRADE, etc.)
- Success/Failure status
- Remaining attempts
- Timestamp

### 4. brute_force_detection.log
Records detected brute force attacks:
- Attack type (LOGIN, OTP, PASSWORD)
- Username targeted
- IP Address of attacker
- Number of failed attempts
- Action taken (ACCOUNT_LOCKED)
- Severity level

### 5. account_locks.log
Records account lock/unlock events:
- Lock/Unlock events
- Reason for lock
- Lock duration
- Unlock time
- Timestamp

### 6. security_events.log
Master log containing all security events:
- All authentication events
- Security alerts
- Severity levels (INFO, WARNING, CRITICAL)
- Complete audit trail

## Security Measures

### Brute Force Protection
- **Maximum Attempts**: 5 failed attempts
- **Lock Duration**: 60 minutes (1 hour)
- **Tracking Window**: 15 minutes rolling window
- **Tracking Method**: Username + IP Address combination

### Protected Endpoints
1. **Login** (`/login`)
2. **OTP Verification** (`/verify-otp`)
3. **Password Verification** (`/api/stock/verify-password`)

### Features
- ✅ Real-time attempt tracking
- ✅ Remaining attempts display
- ✅ Automatic account unlock after duration
- ✅ IP-based tracking
- ✅ Comprehensive logging
- ✅ Security event monitoring

## Viewing Logs

All logs are in JSON format with timestamps. Each entry contains:
```json
{
  "event_type": "LOGIN_ATTEMPT",
  "username": "user123",
  "ip_address": "192.168.1.100",
  "success": false,
  "remaining_attempts": 3,
  "account_locked": false,
  "timestamp": "2025-11-10T15:30:45.123456"
}
```

## Security Report

Generate a comprehensive security report using:
```python
from security.security_logger import generate_security_report
report_file = generate_security_report()
```

This creates a formatted report summarizing all security activity.

## For Presentation

These logs demonstrate:
1. **Proactive Security**: All authentication attempts are logged
2. **Brute Force Prevention**: Automatic detection and account locking
3. **Audit Trail**: Complete record of security events
4. **User Feedback**: Remaining attempts shown to legitimate users
5. **Compliance**: Detailed logging for security audits

---
**Project**: IS Lab Project - Secure Authentication System
**Date**: November 2025
"""
    
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return readme_file

# Initialize on import
if __name__ == '__main__':
    # Create README
    readme = create_readme()
    print(f"✅ Created README: {readme}")
    
    # Generate sample report
    report = generate_security_report()
    print(f"✅ Generated security report: {report}")
    print(f"\n📁 Security logs directory: {LOGS_DIR}")
