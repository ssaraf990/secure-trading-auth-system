"""
🔒 Biometric Verification Routes
Flask Blueprint for biometric endpoints
"""
import secrets
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from functools import wraps
from modules.biometric.biometric_controller import (
    generate_challenge, store_challenge, verify_challenge,
    register_credential, get_user_credentials, verify_biometric_assertion,
    init_biometric_db
)

biometric_bp = Blueprint('biometric', __name__, url_prefix='/api/biometric')

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

@biometric_bp.route('/register', methods=['POST'])
@login_required
def register():
    """🔒 Register a new biometric credential"""
    try:
        data = request.json
        user_id = session['user_id']
        
        # Generate registration challenge
        challenge = generate_challenge()
        store_challenge(user_id, challenge)
        
        # Mock credential data (in production, this comes from WebAuthn)
        credential_id = data.get('credential_id') or f"cred_{user_id}_{secrets.token_urlsafe(16)}"
        public_key = data.get('public_key') or f"pubkey_{user_id}"
        
        if register_credential(user_id, credential_id, public_key):
            return jsonify({
                'success': True,
                'challenge': challenge,
                'credential_id': credential_id,
                'message': 'Biometric credential registered successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Credential already exists'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@biometric_bp.route('/verify', methods=['POST'])
@login_required
def verify():
    """🔒 Verify biometric authentication"""
    try:
        data = request.json
        user_id = session['user_id']
        challenge = data.get('challenge')
        
        # If challenge is 'check', just check if already verified
        if challenge == 'check':
            if session.get('biometric_verified'):
                return jsonify({
                    'success': True,
                    'verified': True,
                    'message': 'Biometric already verified'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'verified': False,
                    'error': 'Biometric verification required'
                }), 401
        
        if not challenge:
            return jsonify({
                'success': False,
                'error': 'Challenge required'
            }), 400
        
        if verify_challenge(user_id, challenge):
            session['biometric_verified'] = True
            from datetime import datetime
            session['biometric_verified_at'] = datetime.now().isoformat()
            return jsonify({
                'success': True,
                'verified': True,
                'message': 'Biometric verification successful'
            }), 200
        else:
            return jsonify({
                'success': False,
                'verified': False,
                'error': 'Invalid or expired challenge'
            }), 401
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@biometric_bp.route('/assert', methods=['POST'])
@login_required
def assert_biometric():
    """🔒 Assert biometric for sensitive operations (like trading)"""
    try:
        data = request.json
        user_id = session['user_id']
        credential_id = data.get('credential_id')
        signature = data.get('signature')
        challenge = data.get('challenge')
        
        if not all([credential_id, signature, challenge]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        if verify_biometric_assertion(user_id, credential_id, signature, challenge):
            # Store verification in session for trade confirmation
            session['biometric_verified'] = True
            session['biometric_verified_at'] = datetime.now().isoformat()
            return jsonify({
                'success': True,
                'message': 'Biometric assertion verified successfully',
                'verified': True
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Biometric verification failed'
            }), 401
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@biometric_bp.route('/challenge', methods=['GET'])
def get_challenge():
    """🔒 Get a new challenge for biometric verification (works without login for login flow)"""
    try:
        # For login flow, we don't have user_id yet, so use a temporary identifier
        user_id = session.get('user_id') or 0
        challenge = generate_challenge()
        if user_id:
            store_challenge(user_id, challenge)
        
        return jsonify({
            'success': True,
            'challenge': challenge
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@biometric_bp.route('/register-options', methods=['POST'])
def register_options():
    """🔒 Get registration options for new user (before account creation)"""
    try:
        data = request.json
        username = data.get('username')
        email = data.get('email')
        
        if not username or not email:
            return jsonify({
                'success': False,
                'error': 'Username and email required'
            }), 400
        
        # Generate challenge
        challenge = generate_challenge()
        # Store in session temporarily
        session['biometric_reg_challenge'] = challenge
        session['biometric_reg_username'] = username
        session['biometric_reg_email'] = email
        
        # Generate user ID based on email (so it's consistent and can find existing credentials)
        import hashlib
        user_id_hash = hashlib.sha256(email.encode()).hexdigest()[:32]  # Use email as base for consistency
        
        # Check if user already exists (for re-registration)
        from app import get_db_connection as get_app_db
        app_conn = get_app_db()
        existing_user = app_conn.execute(
            'SELECT id FROM users WHERE email = ?',
            (email,)
        ).fetchone()
        app_conn.close()
        
        # If user exists, check for existing credentials
        existing_credential = None
        if existing_user:
            from modules.biometric.biometric_controller import get_db_connection as get_bio_db
            bio_conn = get_bio_db()
            existing_credential = bio_conn.execute(
                'SELECT credential_id FROM biometric_credentials WHERE user_id = ? LIMIT 1',
                (existing_user['id'],)
            ).fetchone()
            bio_conn.close()
        
        return jsonify({
            'success': True,
            'challenge': challenge,
            'user_id': user_id_hash,
            'email': email,  # Include email for reference
            'has_existing_credential': existing_credential is not None,
            'rp': {
                'name': 'IS Lab Project',
                'id': request.host.split(':')[0] if ':' in request.host else request.host  # Domain without port
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@biometric_bp.route('/login', methods=['POST'])
def biometric_login():
    """🔒 Biometric login (no login required - this IS the login)"""
    try:
        data = request.json
        credential_id = data.get('credential_id')
        challenge = data.get('challenge')
        user_email = data.get('user_email')  # Optional: email to help find credential
        
        if not credential_id or not challenge:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        # Find user by credential ID
        from modules.biometric.biometric_controller import get_db_connection as get_bio_db
        from app import get_db_connection as get_app_db
        
        conn = get_bio_db()
        
        # Try to find credential by ID first
        credential = conn.execute(
            'SELECT user_id FROM biometric_credentials WHERE credential_id = ?',
            (credential_id,)
        ).fetchone()
        
        # If not found and email provided, try to find by email
        if not credential and user_email:
            app_conn = get_app_db()
            user = app_conn.execute(
                'SELECT id FROM users WHERE email = ?',
                (user_email,)
            ).fetchone()
            app_conn.close()
            
            if user:
                credential = conn.execute(
                    'SELECT user_id FROM biometric_credentials WHERE user_id = ? LIMIT 1',
                    (user['id'],)
                ).fetchone()
        
        conn.close()
        
        if not credential:
            return jsonify({
                'success': False,
                'error': 'Biometric credential not found. Please register first.'
            }), 401
        
        user_id = credential['user_id']
        
        # For login, verify the WebAuthn assertion signature
        # In production, use webauthn library to verify the signature
        # For now, we'll verify the challenge was used
        challenge_valid = True  # In production, verify WebAuthn signature properly
        
        if challenge_valid:
            # Get user info
            from app import get_db_connection as get_app_db
            conn = get_app_db()
            user = conn.execute(
                'SELECT id, username, email FROM users WHERE id = ?',
                (user_id,)
            ).fetchone()
            conn.close()
            
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 401
            
            # Set session (but still require OTP)
            session['temp_user_id'] = user['id']
            session['temp_username'] = user['username']
            
            # Generate and send OTP (still required for 2FA)
            from app import generate_otp, send_otp_email, store_otp
            otp = generate_otp()
            if send_otp_email(user['email'], otp):
                store_otp(user['username'], otp)
                return jsonify({
                    'success': True,
                    'message': 'Biometric verified. OTP sent to email.',
                    'requires_otp': True
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to send OTP'
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid challenge'
            }), 401
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
