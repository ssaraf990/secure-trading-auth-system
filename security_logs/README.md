# Security Logs Directory

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
