"""
🔒 Biometric Verification Controller
Handles WebAuthn registration, verification, and assertion
"""
import json
import secrets
from datetime import datetime, timedelta
from flask import session
import sqlite3

# Mock WebAuthn implementation (for development)
# In production, use proper WebAuthn library like webauthn

def get_db_connection():
    """Get database connection"""
    from app import DATABASE
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_biometric_db():
    """Initialize biometric credentials table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS biometric_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            credential_id TEXT UNIQUE NOT NULL,
            public_key TEXT NOT NULL,
            counter INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS biometric_challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            challenge TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE
        )
    ''')
    
    conn.commit()
    conn.close()

def generate_challenge():
    """Generate a random challenge for WebAuthn (base64url encoded)"""
    import base64
    challenge_bytes = secrets.token_bytes(32)
    return base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')

def store_challenge(user_id, challenge, expiry_minutes=5):
    """Store challenge for verification"""
    conn = get_db_connection()
    expires_at = datetime.now() + timedelta(minutes=expiry_minutes)
    conn.execute(
        'INSERT INTO biometric_challenges (user_id, challenge, expires_at) VALUES (?, ?, ?)',
        (user_id, challenge, expires_at.isoformat())
    )
    conn.commit()
    conn.close()

def verify_challenge(user_id, challenge):
    """Verify and mark challenge as used"""
    conn = get_db_connection()
    challenge_record = conn.execute(
        '''SELECT id, expires_at FROM biometric_challenges 
           WHERE user_id = ? AND challenge = ? AND used = FALSE 
           ORDER BY created_at DESC LIMIT 1''',
        (user_id, challenge)
    ).fetchone()
    
    if not challenge_record:
        conn.close()
        return False
    
    if datetime.now() > datetime.fromisoformat(challenge_record['expires_at']):
        conn.close()
        return False
    
    conn.execute(
        'UPDATE biometric_challenges SET used = TRUE WHERE id = ?',
        (challenge_record['id'],)
    )
    conn.commit()
    conn.close()
    return True

def register_credential(user_id, credential_id, public_key):
    """Store WebAuthn credential"""
    conn = get_db_connection()
    try:
        # Check if credential already exists for this user
        existing = conn.execute(
            'SELECT id FROM biometric_credentials WHERE user_id = ? AND credential_id = ?',
            (user_id, credential_id)
        ).fetchone()
        
        if existing:
            # Update existing credential — recreate with new public key
            conn.execute(
                'DELETE FROM biometric_credentials WHERE user_id = ? AND credential_id = ?',
                (user_id, credential_id)
            )
            conn.execute(
                'INSERT INTO biometric_credentials (user_id, credential_id, public_key) VALUES (?, ?, ?)',
                (user_id, credential_id, public_key)
            )
        else:
            # Insert new credential
            conn.execute(
                'INSERT INTO biometric_credentials (user_id, credential_id, public_key) VALUES (?, ?, ?)',
                (user_id, credential_id, public_key)
            )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # If unique constraint fails, try update
        try:
            conn.execute(
                'UPDATE biometric_credentials SET public_key = ? WHERE credential_id = ?',
                (public_key, credential_id)
            )
            conn.commit()
            return True
        except:
            return False
    finally:
        conn.close()

def get_user_credentials(user_id):
    """Get all credentials for a user"""
    conn = get_db_connection()
    credentials = conn.execute(
        'SELECT credential_id, public_key FROM biometric_credentials WHERE user_id = ?',
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(cred) for cred in credentials]

def verify_biometric_assertion(user_id, credential_id, signature, challenge):
    """Verify biometric assertion (simplified mock)"""
    import os
    
    # Special handling for PIN fallback
    DEV_PIN = os.environ.get('DEV_PIN', '123456')  # Default dev PIN
    if credential_id == 'pin_fallback':
        # Verify challenge first
        if verify_challenge(user_id, challenge):
            # Then verify PIN matches
            return signature == DEV_PIN
        return False
    
    # In production, this would verify the WebAuthn signature
    # For now, we'll verify the challenge was valid
    if verify_challenge(user_id, challenge):
        conn = get_db_connection()
        credential = conn.execute(
            'SELECT credential_id FROM biometric_credentials WHERE user_id = ? AND credential_id = ?',
            (user_id, credential_id)
        ).fetchone()
        conn.close()
        return credential is not None
    return False
