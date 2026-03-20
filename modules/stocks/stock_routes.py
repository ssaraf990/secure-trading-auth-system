"""
📈 Stock Trading Routes
Flask Blueprint for stock trading endpoints
"""
from flask import Blueprint, request, jsonify, session
from functools import wraps
from modules.stocks.stock_controller import (
    get_live_stock_price, execute_trade, get_user_wallet,
    get_user_positions, get_transaction_history, init_stock_db
)

stock_bp = Blueprint('stock', __name__, url_prefix='/api/stock')

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


@stock_bp.route('/price/<symbol>', methods=['GET'])
@login_required
def get_price(symbol):
    """📈 Get live stock price — rate limited."""
    try:
        from app import is_rate_limited
        if is_rate_limited(f'price:{request.remote_addr}', max_requests=30, window_seconds=60):
            return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429
        result = get_live_stock_price(symbol)
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@stock_bp.route('/trade', methods=['POST'])
@login_required
def trade():
    """📈 Execute a stock trade (requires biometric verification)"""
    try:
        # Check biometric verification
        if not session.get('biometric_verified'):
            return jsonify({
                'success': False,
                'error': 'Biometric verification required',
                'requires_biometric': True
            }), 403
        
        data = request.json
        user_id = session['user_id']
        symbol = data.get('symbol', '').upper().strip()
        qty = int(data.get('qty', 0))
        price = float(data.get('price', 0))
        side = data.get('side', '').upper().strip()
        
        if not symbol or qty <= 0 or price <= 0 or side not in ['BUY', 'SELL']:
            return jsonify({
                'success': False,
                'error': 'Invalid trade parameters'
            }), 400
        
        result = execute_trade(user_id, symbol, qty, price, side, verified_by='biometric')
        
        # Clear biometric verification after trade
        session.pop('biometric_verified', None)
        session.pop('biometric_verified_at', None)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Invalid number format'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@stock_bp.route('/balance', methods=['GET'])
@login_required
def balance():
    """📈 Get user wallet balance"""
    try:
        user_id = session['user_id']
        balance = get_user_wallet(user_id)
        return jsonify({
            'success': True,
            'balance_inr': balance
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@stock_bp.route('/history', methods=['GET'])
@login_required
def history():
    """📈 Get transaction history"""
    try:
        user_id = session['user_id']
        limit = request.args.get('limit', 50, type=int)
        transactions = get_transaction_history(user_id, limit)
        return jsonify({
            'success': True,
            'transactions': transactions
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@stock_bp.route('/positions', methods=['GET'])
@login_required
def positions():
    """📈 Get user positions"""
    try:
        user_id = session['user_id']
        positions = get_user_positions(user_id)
        return jsonify({
            'success': True,
            'positions': positions
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@stock_bp.route('/verify-password', methods=['POST'])
@login_required
def verify_password():
    """🔐 Verify user password for transactions with brute force protection"""
    try:
        from app import get_db_connection, check_password_hash, check_account_locked, get_account_lock_time_remaining, record_login_attempt, get_failed_attempts_count, lock_account
        from security.security_logger import log_password_verification, log_brute_force_detection
        
        username = session.get('username')
        if not username:
            return jsonify({
                'success': False,
                'error': 'Session expired'
            }), 401
        
        # Check if account is locked
        if check_account_locked(username):
            remaining_time = get_account_lock_time_remaining(username)
            if remaining_time > 0:
                return jsonify({
                    'success': False,
                    'error': f'Account locked due to multiple failed attempts. Try again in {remaining_time} minutes.',
                    'locked': True
                }), 403
        
        data = request.json
        password = data.get('password', '')
        ip_address = request.remote_addr
        
        if not password:
            return jsonify({
                'success': False,
                'error': 'Password required'
            }), 400
        
        # Check for too many failed attempts
        failed_attempts = get_failed_attempts_count(username, ip_address)
        if failed_attempts >= 5:
            lock_account(username, 60)  # Lock for 1 hour
            log_brute_force_detection(username, ip_address, failed_attempts, event_type='PASSWORD_VERIFICATION')
            return jsonify({
                'success': False,
                'error': 'Too many failed attempts. Account locked for 1 hour.',
                'locked': True
            }), 403
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT password_hash FROM users WHERE id = ?',
            (session['user_id'],)
        ).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            # Record successful verification
            record_login_attempt(username, ip_address, True)
            log_password_verification(username, ip_address, success=True, purpose='TRADE', remaining_attempts=5)
            # Set verification in session
            session['biometric_verified'] = True
            from datetime import datetime
            session['biometric_verified_at'] = datetime.now().isoformat()
            return jsonify({
                'success': True,
                'message': 'Password verified'
            }), 200
        else:
            # Record failed attempt - calculate remaining BEFORE recording
            # failed_attempts is count BEFORE this attempt
            # After recording: (failed_attempts + 1) total failures
            # Remaining = 5 - (failed_attempts + 1) = 4 - failed_attempts
            remaining_attempts = 4 - failed_attempts
            account_will_lock = remaining_attempts <= 0
            
            # Record in database
            record_login_attempt(username, ip_address, False)
            
            # Log with correct remaining count
            log_password_verification(
                username,
                ip_address,
                success=False,
                purpose='TRADE',
                remaining_attempts=max(0, remaining_attempts),
                account_locked=account_will_lock
            )
            if remaining_attempts > 0:
                return jsonify({
                    'success': False,
                    'error': f'Invalid password. {remaining_attempts} attempts remaining.',
                    'remaining_attempts': remaining_attempts
                }), 401
            else:
                return jsonify({
                    'success': False,
                    'error': 'Invalid password.'
                }), 401
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
