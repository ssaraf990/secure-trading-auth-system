from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime
import os
import random
from functools import wraps
from dotenv import load_dotenv

# Load .env file if present (for local dev)
load_dotenv()

# 🔒 Import new modules (non-breaking modular additions)
from modules.biometric.biometric_routes import biometric_bp
from modules.biometric.biometric_controller import init_biometric_db
from modules.stocks.stock_routes import stock_bp
from modules.stocks.stock_controller import init_stock_db
from security.threat_routes import threat_bp
from security.security_logger import (
    log_login_attempt, log_otp_attempt, log_brute_force_detection,
    log_account_lock, log_account_unlock, create_readme, generate_security_report
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Security cookie settings
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour
app.config['WTF_CSRF_HEADERS'] = ['X-CSRFToken']  # accept from JS fetch

# CSRF protection — covers all POST forms automatically
csrf = CSRFProtect(app)

# Exempt JSON API endpoints from CSRF (they use session auth instead)
# (applied per-route below via @csrf.exempt)

# Database configuration
DATABASE = 'auth_system.db'

# 🔒 Register new blueprints (non-breaking modular additions)
app.register_blueprint(biometric_bp)
app.register_blueprint(stock_bp)
app.register_blueprint(threat_bp)

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash('Security token expired or missing. Please try again.', 'error')
    return redirect(request.referrer or url_for('index'))

# -------------------- Rate Limiter --------------------
# Simple in-memory sliding window: {key: [timestamp, ...]}
_rate_limit_store = {}

def is_rate_limited(key, max_requests=10, window_seconds=60):
    """Return True if key has exceeded max_requests in window_seconds."""
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(seconds=window_seconds)
    hits = _rate_limit_store.get(key, [])
    hits = [t for t in hits if t > cutoff]
    hits.append(now)
    _rate_limit_store[key] = hits
    return len(hits) > max_requests

# -------------------- Session Timeout --------------------
SESSION_TIMEOUT_MINUTES = 15

def check_session_timeout():
    """Return True if session has timed out due to inactivity."""
    if 'user_id' not in session:
        return False
    last_active = session.get('last_active')
    if not last_active:
        session['last_active'] = datetime.datetime.now().isoformat()
        return False
    last_dt = datetime.datetime.fromisoformat(last_active)
    if (datetime.datetime.now() - last_dt).total_seconds() > SESSION_TIMEOUT_MINUTES * 60:
        return True
    session['last_active'] = datetime.datetime.now().isoformat()
    return False

@app.before_request
def enforce_session_timeout():
    """Auto-logout on inactivity — runs before every request."""
    if request.endpoint and request.endpoint not in ('login', 'register', 'index', 'static', 'logout'):
        if check_session_timeout():
            session.clear()
            flash('Session expired due to inactivity. Please log in again.', 'error')
            return redirect(url_for('login'))

# -------------------- TPIN Lockout --------------------
TPIN_MAX_ATTEMPTS = 5
TPIN_LOCK_MINUTES = 30

def get_tpin_failed_count(user_id, window_minutes=30):
    """Count failed TPIN attempts in the last window_minutes."""
    conn = get_db_connection()
    cutoff = (datetime.datetime.now() - datetime.timedelta(minutes=window_minutes)).isoformat()
    count = conn.execute(
        '''SELECT COUNT(*) FROM tpin_attempts
           WHERE user_id = ? AND success = FALSE AND attempted_at > ?''',
        (user_id, cutoff)
    ).fetchone()[0]
    conn.close()
    return count

def is_tpin_locked(user_id):
    """Check if TPIN is locked due to too many failures."""
    return get_tpin_failed_count(user_id, TPIN_LOCK_MINUTES) >= TPIN_MAX_ATTEMPTS

def record_tpin_attempt(user_id, ip_address, success):
    """Record a TPIN attempt."""
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO tpin_attempts (user_id, ip_address, success) VALUES (?, ?, ?)',
        (user_id, ip_address, success)
    )
    conn.commit()
    conn.close()

def snapshot_portfolio(user_id):
    """Record current net worth to portfolio_history after a trade."""
    from modules.stocks.stock_controller import get_user_positions, get_user_wallet
    positions = get_user_positions(user_id)
    wallet = get_user_wallet(user_id)
    total_value = 0.0
    for pos in positions:
        result = get_cached_price(pos['symbol'])
        total_value += result['price'] * pos['qty']
    net_worth = round(total_value + wallet, 2)
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO portfolio_history (user_id, net_worth) VALUES (?, ?)',
        (user_id, net_worth)
    )
    conn.commit()
    conn.close()

# Email configuration — set via environment variables or .env file
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_locked BOOLEAN DEFAULT FALSE,
            locked_until TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Login attempts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            success BOOLEAN NOT NULL,
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # OTPs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            otp_code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Add tpin_hash column if not exists (safe migration)
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN tpin_hash TEXT NULL')
    except Exception:
        pass

    # Personal watchlist table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, symbol),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # TPIN failed attempts table (for lockout)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tpin_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            success BOOLEAN NOT NULL,
            ip_address TEXT NOT NULL,
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Portfolio net worth history (for P&L graph)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            net_worth REAL NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()

    # 🔒 Initialize new module databases
    init_biometric_db()
    init_stock_db()

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def check_account_locked(username):
    """Check if account is locked due to brute force attempts"""
    conn = get_db_connection()
    user = conn.execute(
        'SELECT is_locked, locked_until FROM users WHERE username = ?', 
        (username,)
    ).fetchone()
    conn.close()
    
    if user and user['is_locked']:
        if user['locked_until'] and datetime.datetime.now() < datetime.datetime.fromisoformat(user['locked_until']):
            return True
        else:
            # Unlock account if lock time has expired
            conn = get_db_connection()
            conn.execute(
                'UPDATE users SET is_locked = FALSE, locked_until = NULL WHERE username = ?',
                (username,)
            )
            conn.commit()
            conn.close()
            # Log the automatic unlock
            log_account_unlock(username, reason='AUTO_EXPIRE')
    return False

def get_account_lock_time_remaining(username):
    """Get remaining lock time for an account in minutes"""
    conn = get_db_connection()
    user = conn.execute(
        'SELECT locked_until FROM users WHERE username = ? AND is_locked = TRUE', 
        (username,)
    ).fetchone()
    conn.close()
    
    if user and user['locked_until']:
        locked_until = datetime.datetime.fromisoformat(user['locked_until'])
        now = datetime.datetime.now()
        if now < locked_until:
            remaining_seconds = (locked_until - now).total_seconds()
            return max(0, int(remaining_seconds / 60))  # Return minutes
    return 0

def record_login_attempt(username, ip_address, success):
    """Record login attempt in database"""
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO login_attempts (username, ip_address, success) VALUES (?, ?, ?)',
        (username, ip_address, success)
    )
    conn.commit()
    conn.close()

def get_failed_attempts_count(username, ip_address, minutes=15):
    """Get count of failed login attempts in the last N minutes"""
    conn = get_db_connection()
    cutoff_time = datetime.datetime.now() - datetime.timedelta(minutes=minutes)
    # Convert cutoff_time to string format for SQLite comparison
    cutoff_time_str = cutoff_time.strftime('%Y-%m-%d %H:%M:%S')
    count = conn.execute(
        '''SELECT COUNT(*) FROM login_attempts 
           WHERE username = ? AND ip_address = ? AND success = FALSE 
           AND attempted_at > ?''',
        (username, ip_address, cutoff_time_str)
    ).fetchone()[0]
    conn.close()
    return count

def lock_account(username, minutes=60):
    """Lock account for specified minutes (default 1 hour)"""
    conn = get_db_connection()
    locked_until = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
    conn.execute(
        'UPDATE users SET is_locked = TRUE, locked_until = ? WHERE username = ?',
        (locked_until.isoformat(), username)
    )
    conn.commit()
    conn.close()
    
    # Log the account lock
    log_account_lock(
        username=username,
        ip_address='system',
        reason='BRUTE_FORCE_PROTECTION',
        lock_duration_minutes=minutes,
        unlock_time=locked_until.isoformat()
    )

def generate_otp():
    """Generate a 6-digit OTP"""
    return str(secrets.randbelow(900000) + 100000)

def send_otp_email(email, otp):
    """Send OTP via email"""
    try:
        # Check if email is configured
        if not EMAIL_PASSWORD or not EMAIL_ADDRESS:
            print(f"⚠️  EMAIL NOT CONFIGURED - OTP for development use: {otp}")
            print("📧 Set EMAIL_ADDRESS and EMAIL_PASSWORD environment variables to enable email sending.")
            return True  # Return True so login can continue
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = email
        msg['Subject'] = "🔐 Your Two-Factor Authentication Code"
        
        # Create HTML email body
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center;">
                <h2>🔐 Two-Factor Authentication</h2>
                <p>Your secure login code</p>
            </div>
            <div style="background: #f8f9fa; padding: 30px; border-radius: 10px; margin: 20px 0;">
                <h3 style="color: #333; text-align: center;">Your OTP Code</h3>
                <div style="background: white; border: 2px dashed #667eea; padding: 20px; text-align: center; margin: 20px 0;">
                    <span style="font-size: 32px; font-weight: bold; color: #667eea; letter-spacing: 5px;">{otp}</span>
                </div>
                <p style="color: #666; text-align: center;">
                    ⏰ This code will expire in <strong>5 minutes</strong>
                </p>
            </div>
            <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p style="margin: 0; color: #856404;">
                    <strong>Security Notice:</strong> Never share this code with anyone. 
                    Our system will never ask for it via phone or other means.
                </p>
            </div>
            <div style="text-align: center; color: #666; font-size: 12px; margin-top: 30px;">
                <p>If you didn't request this code, please ignore this email.</p>
                <p>This is an automated message from your Two-Factor Authentication System.</p>
            </div>
        </body>
        </html>
        """
        
        # Create plain text version
        text_body = f"""
        Two-Factor Authentication Code
        
        Your OTP code is: {otp}
        
        This code will expire in 5 minutes.
        
        Security Notice: Never share this code with anyone. Our system will never ask for it via phone or other means.
        
        If you didn't request this code, please ignore this email.
        """
        
        # Attach both versions
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_ADDRESS, email, text)
        server.quit()
        
        print(f"✅ OTP sent successfully to {email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Email authentication failed: {e}")
        print("🔧 Please check your Gmail App Password")
        print(f"⚠️  FALLBACK - OTP for {email}: {otp}")
        return True
        
    except smtplib.SMTPException as e:
        print(f"❌ SMTP error: {e}")
        print(f"⚠️  FALLBACK - OTP for {email}: {otp}")
        return True
        
    except Exception as e:
        print(f"❌ Unexpected error sending email: {e}")
        print(f"⚠️  FALLBACK - OTP for {email}: {otp}")
        return True

def store_otp(username, otp, expiry_minutes=5):
    """Store OTP in database with expiry"""
    conn = get_db_connection()
    expires_at = datetime.datetime.now() + datetime.timedelta(minutes=expiry_minutes)
    conn.execute(
        'INSERT INTO otps (username, otp_code, expires_at) VALUES (?, ?, ?)',
        (username, otp, expires_at.isoformat())
    )
    conn.commit()
    conn.close()

def verify_otp_code(username, otp):
    """Verify OTP and mark as used if valid"""
    conn = get_db_connection()
    otp_record = conn.execute(
        '''SELECT id, expires_at FROM otps 
           WHERE username = ? AND otp_code = ? AND used = FALSE 
           ORDER BY created_at DESC LIMIT 1''',
        (username, otp)
    ).fetchone()
    
    if not otp_record:
        conn.close()
        return False
    
    # Check if OTP has expired
    if datetime.datetime.now() > datetime.datetime.fromisoformat(otp_record['expires_at']):
        conn.close()
        return False
    
    # Mark OTP as used
    conn.execute(
        'UPDATE otps SET used = TRUE WHERE id = ?',
        (otp_record['id'],)
    )
    conn.commit()
    conn.close()
    return True

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Validation
        if not username or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('register.html')
        
        # Check if user already exists
        conn = get_db_connection()
        existing_user = conn.execute(
            'SELECT id FROM users WHERE username = ? OR email = ?',
            (username, email)
        ).fetchone()
        
        if existing_user:
            flash('Username or email already exists.', 'error')
            conn.close()
            return render_template('register.html')
        
        # Create new user
        password_hash = generate_password_hash(password)
        cursor = conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, password_hash)
        )
        user_id = cursor.lastrowid
        conn.commit()
        
        # 🔒 Handle biometric credential registration if provided
        biometric_credential_id = request.form.get('biometric_credential_id')
        if biometric_credential_id:
            from modules.biometric.biometric_controller import register_credential
            # Store the credential (public key would be extracted from WebAuthn response in production)
            # For now, we store the credential ID
            register_credential(user_id, biometric_credential_id, f"pubkey_{user_id}")
            flash('Registration successful with biometric authentication! Please log in.', 'success')
        else:
            flash('Registration successful! Please log in.', 'success')
        
        conn.close()
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        ip_address = request.remote_addr
        
        # Check if account is locked
        if check_account_locked(username):
            remaining_time = get_account_lock_time_remaining(username)
            if remaining_time > 0:
                flash(f'Account is temporarily locked due to multiple failed attempts. Please try again in {remaining_time} minutes.', 'error')
            else:
                flash('Account is temporarily locked due to multiple failed attempts. Please try again later.', 'error')
            return render_template('login.html')
        
        # Check for too many failed attempts
        failed_attempts = get_failed_attempts_count(username, ip_address)
        if failed_attempts >= 5:
            lock_account(username, 60)  # Lock for 1 hour (60 minutes)
            log_brute_force_detection(username, ip_address, failed_attempts, event_type='LOGIN')
            flash('Account locked due to multiple failed attempts. Please try again in 1 hour.', 'error')
            return render_template('login.html')
        
        # Verify credentials
        conn = get_db_connection()
        try:
            user = conn.execute(
                'SELECT id, username, email, password_hash FROM users WHERE username = ?',
                (username,)
            ).fetchone()
        finally:
            conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            # Successful login
            record_login_attempt(username, ip_address, True)
            remaining_attempts = 5  # Reset for successful login
            log_login_attempt(username, ip_address, success=True, remaining_attempts=remaining_attempts)
            
            # Generate and send OTP
            otp = generate_otp()
            if send_otp_email(user['email'], otp):
                store_otp(username, otp)
                session['temp_user_id'] = user['id']
                session['temp_username'] = username
                flash('Login successful! Please check your email for the OTP code.', 'success')
                return redirect(url_for('verify_otp'))
            else:
                flash('Error sending OTP. Please try again.', 'error')
                return render_template('login.html')
        else:
            # Failed login - calculate remaining attempts BEFORE recording
            remaining_attempts = 4 - failed_attempts
            account_will_lock = remaining_attempts <= 0
            
            # Record the attempt in database
            record_login_attempt(username, ip_address, False)
            
            # Log with remaining attempts count
            log_login_attempt(
                username, 
                ip_address, 
                success=False, 
                remaining_attempts=max(0, remaining_attempts),
                account_locked=account_will_lock
            )
            flash('Invalid username or password.', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """OTP verification with brute force protection"""
    if 'temp_user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login'))
    
    username = session['temp_username']
    
    # Check if account is locked
    if check_account_locked(username):
        remaining_time = get_account_lock_time_remaining(username)
        session.pop('temp_user_id', None)
        session.pop('temp_username', None)
        if remaining_time > 0:
            flash(f'Account is locked due to multiple failed OTP attempts. Please try again in {remaining_time} minutes.', 'error')
        else:
            flash('Account is locked. Please try again later.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        otp = request.form['otp']
        ip_address = request.remote_addr
        
        # Check for too many failed OTP attempts
        failed_attempts = get_failed_attempts_count(username, ip_address)
        if failed_attempts >= 5:
            lock_account(username, 60)  # Lock for 1 hour
            log_brute_force_detection(username, ip_address, failed_attempts, event_type='OTP')
            session.pop('temp_user_id', None)
            session.pop('temp_username', None)
            flash('Too many failed OTP attempts. Account locked for 1 hour.', 'error')
            return redirect(url_for('login'))
        
        if verify_otp_code(username, otp):
            # OTP is valid, complete login
            record_login_attempt(username, ip_address, True)
            log_otp_attempt(username, ip_address, success=True, remaining_attempts=5)
            user_id = session['temp_user_id']
            session['user_id'] = user_id
            session['username'] = username
            session['last_active'] = datetime.datetime.now().isoformat()
            # Sync wallet from DB (stock module uses DB; session mirrors it for templates)
            from modules.stocks.stock_controller import get_user_wallet
            db_wallet = get_user_wallet(user_id)
            session['wallet_inr'] = db_wallet
            if 'transactions' not in session:
                session['transactions'] = []
            session.pop('temp_user_id', None)
            session.pop('temp_username', None)
            flash('Login successful! Welcome to your dashboard.', 'success')
            return redirect(url_for('dashboard'))
        else:
            # Record failed OTP attempt - calculate remaining BEFORE recording
            # failed_attempts is count BEFORE this attempt
            # After recording: (failed_attempts + 1) total failures
            # Remaining = 5 - (failed_attempts + 1) = 4 - failed_attempts
            remaining_attempts = 4 - failed_attempts
            account_will_lock = remaining_attempts <= 0
            
            # Record in database
            record_login_attempt(username, ip_address, False)
            
            # Log with correct remaining count
            log_otp_attempt(
                username,
                ip_address,
                success=False,
                remaining_attempts=max(0, remaining_attempts),
                account_locked=account_will_lock
            )
            if remaining_attempts > 0:
                flash(f'Invalid or expired OTP. {remaining_attempts} attempts remaining.', 'error')
            else:
                flash('Invalid or expired OTP. Please try again.', 'error')
            return render_template('verify_otp.html')
    
    return render_template('verify_otp.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    return render_template('dashboard.html',
        username=session['username'],
        wallet_inr=session.get('wallet_inr', 500000),
        session_timeout_seconds=SESSION_TIMEOUT_MINUTES * 60
    )

# -------------------- Stock Market (Live via yfinance) --------------------
WATCHLIST = ['AAPL', 'TSLA', 'GOOGL', 'AMZN', 'MSFT', 'NFLX', 'NVDA', 'META', 'INTC', 'INFY']

# Simple in-process cache: {symbol: {data: ..., fetched_at: datetime}}
_price_cache = {}
CACHE_TTL_SECONDS = 60

def get_cached_price(symbol):
    """Return cached price if fresh, else fetch and cache."""
    from modules.stocks.stock_controller import get_live_stock_price
    now = datetime.datetime.now()
    cached = _price_cache.get(symbol)
    if cached and (now - cached['fetched_at']).total_seconds() < CACHE_TTL_SECONDS:
        return cached['data']
    result = get_live_stock_price(symbol)
    _price_cache[symbol] = {'data': result, 'fetched_at': now}
    return result

def get_watchlist_prices():
    """Fetch prices for all watchlist symbols."""
    stocks = []
    for symbol in WATCHLIST:
        result = get_cached_price(symbol)
        stocks.append({
            'symbol': result['symbol'],
            'price': result['price'],
            'change_pct': result.get('change_percent', 0),
            'change': result.get('change', 0),
            'volume': result.get('volume', 0),
            'market_cap': result.get('market_cap', 0),
            'source': result.get('source', 'mock')
        })
    return stocks

@app.route('/api/stocks')
@csrf.exempt
@login_required
def api_stocks():
    """Return live stock data as JSON — rate limited."""
    ip = request.remote_addr
    if is_rate_limited(f'stocks:{ip}', max_requests=20, window_seconds=60):
        return jsonify({'error': 'Rate limit exceeded'}), 429
    data = get_watchlist_prices()
    sources = set(s['source'] for s in data)
    source_label = 'live' if 'yfinance' in sources else ('finnhub' if 'finnhub' in sources else 'mock')
    return jsonify({
        'data': data,
        'source': source_label,
        'refreshed_at': datetime.datetime.now().isoformat()
    })

@app.route('/api/stock/search/<symbol>')
@csrf.exempt
@login_required
def search_stock(symbol):
    """Search any stock symbol via yfinance — rate limited."""
    ip = request.remote_addr
    if is_rate_limited(f'search:{ip}', max_requests=15, window_seconds=60):
        return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429
    symbol = symbol.upper().strip()
    if not symbol or len(symbol) > 10:
        return jsonify({'success': False, 'error': 'Invalid symbol'}), 400
    result = get_cached_price(symbol)
    return jsonify(result)

@app.route('/api/stock/history/<symbol>')
@csrf.exempt
@login_required
def stock_history(symbol):
    """Return 30-day OHLC history for candlestick chart."""
    ip = request.remote_addr
    if is_rate_limited(f'history:{ip}', max_requests=10, window_seconds=60):
        return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429
    symbol = symbol.upper().strip()
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='30d', interval='1d')
        if hist.empty:
            return jsonify({'success': False, 'error': 'No history found'})
        candles = []
        for date, row in hist.iterrows():
            candles.append({
                'x': date.strftime('%Y-%m-%d'),
                'o': round(float(row['Open']), 2),
                'h': round(float(row['High']), 2),
                'l': round(float(row['Low']), 2),
                'c': round(float(row['Close']), 2),
                'v': int(row['Volume'])
            })
        return jsonify({'success': True, 'symbol': symbol, 'candles': candles})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/portfolio/history')
@csrf.exempt
@login_required
def portfolio_history_api():
    """Return net worth history for P&L graph."""
    conn = get_db_connection()
    rows = conn.execute(
        '''SELECT net_worth, recorded_at FROM portfolio_history
           WHERE user_id = ? ORDER BY recorded_at ASC LIMIT 90''',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return jsonify({
        'success': True,
        'history': [{'net_worth': r['net_worth'], 'recorded_at': r['recorded_at']} for r in rows]
    })

@app.route('/portfolio')
@login_required
def portfolio():
    """Portfolio page — reads positions and wallet from DB."""
    from modules.stocks.stock_controller import get_user_positions, get_user_wallet
    user_id = session['user_id']

    positions = get_user_positions(user_id)
    wallet_inr = get_user_wallet(user_id)
    session['wallet_inr'] = wallet_inr  # keep session in sync

    enriched = []
    total_value = 0.0
    for pos in positions:
        result = get_cached_price(pos['symbol'])
        price = result['price']
        value = round(price * pos['qty'], 2)
        pnl = round((price - pos['avg_price']) * pos['qty'], 2)
        pnl_pct = round((price - pos['avg_price']) / pos['avg_price'] * 100, 2) if pos['avg_price'] else 0
        total_value += value
        enriched.append({
            'symbol': pos['symbol'],
            'shares': pos['qty'],
            'avg_price': round(pos['avg_price'], 2),
            'price': price,
            'value': value,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'source': result.get('source', 'mock')
        })

    total_value = round(total_value, 2)
    net_worth = round(total_value + wallet_inr, 2)

    # Fetch P&L history for graph
    conn2 = get_db_connection()
    hist_rows = conn2.execute(
        '''SELECT net_worth, recorded_at FROM portfolio_history
           WHERE user_id = ? ORDER BY recorded_at ASC LIMIT 90''',
        (user_id,)
    ).fetchall()
    conn2.close()
    pnl_history = [{'net_worth': r['net_worth'], 'recorded_at': r['recorded_at']} for r in hist_rows]

    return render_template(
        'portfolio.html',
        username=session['username'],
        holdings=enriched,
        total_value=total_value,
        wallet_inr=wallet_inr,
        net_worth=net_worth,
        pnl_history=pnl_history
    )

@app.route('/transactions', methods=['GET', 'POST'])
@login_required
def transactions():
    """Buy/Sell — DB-backed, requires TPIN verification."""
    from modules.stocks.stock_controller import (
        execute_trade, get_transaction_history, get_user_wallet
    )
    from security.security_logger import log_trade_execution

    user_id = session['user_id']
    message = None
    message_type = 'info'

    if request.method == 'POST':
        symbol     = request.form.get('symbol', '').upper().strip()
        side       = request.form.get('side', '').upper().strip()
        shares_str = request.form.get('shares', '0').strip()
        order_type = request.form.get('order_type', 'MARKET').upper().strip()
        limit_price_str = request.form.get('limit_price', '0').strip()
        tpin_verified = request.form.get('tpin_verified', 'false') == 'true'

        try:
            shares = int(shares_str)
        except ValueError:
            shares = 0
        try:
            limit_price = float(limit_price_str) if limit_price_str else 0
        except ValueError:
            limit_price = 0

        if not symbol or side not in ('BUY', 'SELL') or shares <= 0:
            message = '❌ Invalid input. Check symbol, side, and quantity.'
            message_type = 'danger'
        elif not tpin_verified:
            message = '🔒 TPIN verification required before trading.'
            message_type = 'warning'
        else:
            if order_type == 'LIMIT' and limit_price > 0:
                price = round(limit_price, 2)
            else:
                price_data = get_cached_price(symbol)
                price = price_data['price']
                order_type = 'MARKET'

            result = execute_trade(user_id, symbol, shares, price, side,
                                   verified_by=f'tpin_{order_type.lower()}')
            if result['success']:
                new_balance = result['new_balance']
                session['wallet_inr'] = new_balance
                message = f"✅ {order_type} {side} {shares} × {symbol} @ ₹{price:.2f} — Balance: ₹{new_balance:,.2f}"
                message_type = 'success'
                session.pop('tpin_verified', None)
                # Snapshot portfolio for P&L history
                snapshot_portfolio(user_id)
                log_trade_execution(
                    username=session['username'], symbol=symbol,
                    qty=shares, side=side,
                    verified_by=f'tpin_{order_type.lower()}',
                    amount=round(price * shares, 2)
                )
            else:
                message = f"❌ Trade failed: {result['error']}"
                message_type = 'danger'

    txs = get_transaction_history(user_id, limit=50)
    wallet_inr = get_user_wallet(user_id)
    session['wallet_inr'] = wallet_inr

    conn = get_db_connection()
    user = conn.execute('SELECT tpin_hash FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    has_tpin = bool(user and user['tpin_hash'])

    return render_template(
        'transactions.html',
        username=session['username'],
        transactions=txs,
        message=message,
        message_type=message_type,
        wallet_inr=wallet_inr,
        watchlist=WATCHLIST,
        has_tpin=has_tpin
    )

@app.route('/set-tpin', methods=['GET', 'POST'])
@login_required
def set_tpin():
    """Set or update the user's Transaction PIN (TPIN)."""
    if request.method == 'POST':
        tpin = request.form.get('tpin', '').strip()
        tpin_confirm = request.form.get('tpin_confirm', '').strip()
        if len(tpin) != 6 or not tpin.isdigit():
            flash('TPIN must be exactly 6 digits.', 'error')
            return render_template('set_tpin.html')
        if tpin != tpin_confirm:
            flash('TPINs do not match.', 'error')
            return render_template('set_tpin.html')
        tpin_hash = generate_password_hash(tpin)
        conn = get_db_connection()
        conn.execute('UPDATE users SET tpin_hash = ? WHERE id = ?', (tpin_hash, session['user_id']))
        conn.commit()
        conn.close()
        flash('Transaction PIN set successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('set_tpin.html')

@app.route('/api/verify-tpin', methods=['POST'])
@csrf.exempt
@login_required
def verify_tpin():
    """Verify TPIN — with rate limiting and lockout after 5 failures."""
    ip = request.remote_addr
    user_id = session['user_id']

    # Rate limit: max 10 calls per minute per IP
    if is_rate_limited(f'tpin:{ip}', max_requests=10, window_seconds=60):
        return jsonify({'success': False, 'error': 'Too many requests. Slow down.'}), 429

    # Check TPIN lockout
    if is_tpin_locked(user_id):
        return jsonify({
            'success': False,
            'error': f'TPIN locked for {TPIN_LOCK_MINUTES} min due to too many failed attempts.',
            'locked': True
        }), 403

    data = request.json
    tpin = data.get('tpin', '')
    conn = get_db_connection()
    user = conn.execute('SELECT tpin_hash FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()

    if not user or not user['tpin_hash']:
        return jsonify({'success': False, 'error': 'TPIN not set. Please set your TPIN first.', 'needs_setup': True}), 403

    if check_password_hash(user['tpin_hash'], tpin):
        record_tpin_attempt(user_id, ip, True)
        session['tpin_verified'] = True
        session['tpin_verified_at'] = datetime.datetime.now().isoformat()
        from security.security_logger import log_password_verification
        log_password_verification(session['username'], ip, success=True, purpose='TPIN_TRADE')
        return jsonify({'success': True})
    else:
        record_tpin_attempt(user_id, ip, False)
        failed = get_tpin_failed_count(user_id, TPIN_LOCK_MINUTES)
        remaining = max(0, TPIN_MAX_ATTEMPTS - failed)
        from security.security_logger import log_password_verification
        log_password_verification(session['username'], ip, success=False, purpose='TPIN_TRADE',
                                  remaining_attempts=remaining)
        if remaining == 0:
            return jsonify({
                'success': False,
                'error': f'TPIN locked for {TPIN_LOCK_MINUTES} minutes.',
                'locked': True
            }), 403
        return jsonify({
            'success': False,
            'error': f'Incorrect TPIN. {remaining} attempt{"s" if remaining != 1 else ""} remaining.'
        }), 401

@app.route('/api/watchlist', methods=['GET'])
@csrf.exempt
@login_required
def get_watchlist():
    """Get user's personal watchlist."""
    conn = get_db_connection()
    rows = conn.execute('SELECT symbol FROM watchlist WHERE user_id = ? ORDER BY added_at DESC', (session['user_id'],)).fetchall()
    conn.close()
    return jsonify({'success': True, 'watchlist': [r['symbol'] for r in rows]})

@app.route('/api/watchlist/add', methods=['POST'])
@csrf.exempt
@login_required
def add_to_watchlist():
    """Add a symbol to user's watchlist."""
    symbol = (request.json.get('symbol') or '').upper().strip()
    if not symbol or symbol not in WATCHLIST:
        return jsonify({'success': False, 'error': 'Invalid symbol'}), 400
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO watchlist (user_id, symbol) VALUES (?, ?)', (session['user_id'], symbol))
        conn.commit()
    except Exception:
        pass  # Already in watchlist
    conn.close()
    return jsonify({'success': True})

@app.route('/api/watchlist/remove', methods=['POST'])
@csrf.exempt
@login_required
def remove_from_watchlist():
    """Remove a symbol from user's watchlist."""
    symbol = (request.json.get('symbol') or '').upper().strip()
    conn = get_db_connection()
    conn.execute('DELETE FROM watchlist WHERE user_id = ? AND symbol = ?', (session['user_id'], symbol))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/locked')
def locked():
    """Account locked page"""
    username = request.args.get('username', '')
    remaining_time = 0
    if username:
        remaining_time = get_account_lock_time_remaining(username)
    return render_template('locked.html', username=username, remaining_time=remaining_time)

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

# 🔒 New routes for biometric, stocks, and threat modeling (non-breaking modular additions)
@app.route('/biometric-verify')
@login_required
def biometric_verify_page():
    """🔒 Biometric verification page"""
    return render_template('biometric_ui.html', username=session.get('username'))

@app.route('/stock-trading')
@login_required
def stock_trading_page():
    """📈 Stock trading page"""
    return render_template('stock_ui.html', username=session.get('username'))


@app.route('/security-logs')
@login_required
def security_logs_page():
    """Live security audit log viewer."""
    import json
    from pathlib import Path
    logs_dir = Path('security_logs')
    
    events = []
    log_file = logs_dir / 'security_events.log'
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            raw = f.read()
        # Each entry is a [timestamp] followed by JSON then a separator line
        blocks = raw.split('-' * 80)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            try:
                # Extract timestamp and JSON
                lines = block.strip().splitlines()
                timestamp_line = lines[0] if lines else ''
                json_str = '\n'.join(lines[1:])
                data = json.loads(json_str)
                data['_display_time'] = timestamp_line.strip('[]').split(']')[0] if ']' in timestamp_line else timestamp_line
                events.append(data)
            except Exception:
                continue
    
    # Most recent first, cap at 100
    events = list(reversed(events))[:100]
    
    # Stats
    total = len(events)
    critical = sum(1 for e in events if e.get('severity') == 'CRITICAL')
    warnings  = sum(1 for e in events if e.get('severity') == 'WARNING')
    trades    = sum(1 for e in events if e.get('event_type') == 'TRADE_EXECUTED')

    return render_template('security_logs.html',
        username=session['username'],
        events=events,
        total=total, critical=critical, warnings=warnings, trades=trades
    )

@app.route('/security-report')
@login_required
def security_report_page():
    """Generate and display security report"""
    report_file = generate_security_report()
    
    # Read the report content
    with open(report_file, 'r', encoding='utf-8') as f:
        report_content = f.read()
    
    return f"""
    <html>
    <head>
        <title>Security Report</title>
        <style>
            body {{
                font-family: 'Courier New', monospace;
                background: #0d1117;
                color: #c9d1d9;
                padding: 20px;
                margin: 0;
            }}
            pre {{
                background: #161b22;
                padding: 20px;
                border-radius: 6px;
                border: 1px solid #30363d;
                overflow-x: auto;
                white-space: pre-wrap;
                word-wrap: break-word;
            }}
            .header {{
                text-align: center;
                color: #58a6ff;
                margin-bottom: 20px;
            }}
            .download-btn {{
                background: #238636;
                color: white;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 6px;
                display: inline-block;
                margin-bottom: 20px;
            }}
            .download-btn:hover {{
                background: #2ea043;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔒 Security Audit Report</h1>
            <p>Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        <a href="{report_file}" download class="download-btn">📥 Download Report</a>
        <a href="/dashboard" class="download-btn">← Back to Dashboard</a>
        <pre>{report_content}</pre>
    </body>
    </html>
    """

if __name__ == '__main__':
    init_db()
    # Initialize security logging
    create_readme()
    print("=" * 50)
    print("🚀 IS Lab Project Server Starting...")
    print("📍 Server URL: http://127.0.0.1:5001")
    print("📍 Server URL: http://localhost:5001")
    print("📁 Security logs: ./security_logs/")
    print("🛑 Press Ctrl+C to stop the server")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5001)
