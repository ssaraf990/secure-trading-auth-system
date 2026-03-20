"""
📈 Stock Trading Controller
Handles live stock prices from yfinance (primary) and Finnhub API (fallback)
"""
import requests
import os
from datetime import datetime
import sqlite3
from dotenv import load_dotenv
import random

load_dotenv()

FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY', 'd4874m1r01qk80bjo15gd4874m1r01qk80bjo160')
FINNHUB_BASE_URL = 'https://finnhub.io/api/v1'

# Try to import yfinance
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("⚠️  yfinance not installed. Using Finnhub API or mock data.")

def get_db_connection():
    """Get database connection"""
    from app import DATABASE
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_stock_db():
    """Initialize stock trading database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Positions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            qty INTEGER NOT NULL,
            avg_price REAL NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, symbol),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            side TEXT NOT NULL,
            verified_by TEXT,
            tx_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Wallet table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            balance_inr REAL DEFAULT 500000.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_user_wallet(user_id):
    """Get or create user wallet"""
    conn = get_db_connection()
    wallet = conn.execute(
        'SELECT balance_inr FROM wallets WHERE user_id = ?',
        (user_id,)
    ).fetchone()
    
    if not wallet:
        # Create wallet with default balance
        conn.execute(
            'INSERT INTO wallets (user_id, balance_inr) VALUES (?, ?)',
            (user_id, 500000.0)
        )
        conn.commit()
        balance = 500000.0
    else:
        balance = wallet['balance_inr']
    
    conn.close()
    return balance

def update_wallet(user_id, new_balance):
    """Update user wallet balance"""
    conn = get_db_connection()
    conn.execute(
        'UPDATE wallets SET balance_inr = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?',
        (new_balance, user_id)
    )
    conn.commit()
    conn.close()

def get_live_price_yfinance(symbol):
    """Fetch live stock price using yfinance (no API key needed)"""
    if not YFINANCE_AVAILABLE:
        return None
    
    try:
        ticker = yf.Ticker(symbol.upper())
        info = ticker.info
        
        # Get current price
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not current_price:
            # Try fast_info as fallback
            try:
                current_price = ticker.fast_info.get('lastPrice')
            except:
                return None
        
        if current_price:
            previous_close = info.get('previousClose', current_price)
            change = current_price - previous_close
            change_percent = (change / previous_close * 100) if previous_close else 0
            
            return {
                'success': True,
                'symbol': symbol.upper(),
                'price': round(current_price, 2),
                'change': round(change, 2),
                'change_percent': round(change_percent, 2),
                'high': info.get('dayHigh', current_price),
                'low': info.get('dayLow', current_price),
                'open': info.get('open', current_price),
                'previous_close': previous_close,
                'volume': info.get('volume', 0),
                'market_cap': info.get('marketCap', 0),
                'source': 'yfinance'
            }
    except Exception as e:
        print(f"yfinance error for {symbol}: {e}")
        return None
    
    return None

def get_live_price_finnhub(symbol):
    """Fetch live stock price from Finnhub API (requires API key)"""
    try:
        url = f'{FINNHUB_BASE_URL}/quote'
        params = {
            'symbol': symbol.upper(),
            'token': FINNHUB_API_KEY
        }
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('c'):  # Current price
                return {
                    'success': True,
                    'symbol': symbol.upper(),
                    'price': round(data['c'], 2),
                    'change': round(data.get('d', 0), 2),
                    'change_percent': round(data.get('dp', 0), 2),
                    'high': round(data.get('h', 0), 2),
                    'low': round(data.get('l', 0), 2),
                    'open': round(data.get('o', 0), 2),
                    'previous_close': round(data.get('pc', 0), 2),
                    'timestamp': data.get('t', 0),
                    'source': 'finnhub'
                }
    except Exception as e:
        print(f"Finnhub error for {symbol}: {e}")
    
    return None

def get_mock_price(symbol):
    """Generate mock price data as final fallback"""
    # Use symbol hash to generate consistent prices per symbol
    seed = sum(ord(c) for c in symbol)
    random.seed(seed)
    
    base_price = random.uniform(50, 500)
    change_pct = random.uniform(-5, 5)
    
    return {
        'success': True,
        'symbol': symbol.upper(),
        'price': round(base_price, 2),
        'change': round(base_price * change_pct / 100, 2),
        'change_percent': round(change_pct, 2),
        'high': round(base_price * 1.05, 2),
        'low': round(base_price * 0.95, 2),
        'open': round(base_price * 0.98, 2),
        'previous_close': round(base_price * (1 - change_pct/100), 2),
        'volume': random.randint(100000, 50000000),
        'market_cap': random.randint(10, 2500) * 1_000_000_000,
        'source': 'mock'
    }

def get_live_stock_price(symbol):
    """
    Fetch live stock price with fallback chain:
    1. Try yfinance (free, no API key)
    2. Try Finnhub API (requires key)
    3. Fall back to mock data
    """
    # Try yfinance first (no API key needed)
    result = get_live_price_yfinance(symbol)
    if result:
        return result
    
    # Try Finnhub as fallback
    result = get_live_price_finnhub(symbol)
    if result:
        return result
    
    # Final fallback to mock data
    return get_mock_price(symbol)

def get_user_positions(user_id):
    """Get user's stock positions"""
    conn = get_db_connection()
    positions = conn.execute(
        'SELECT symbol, qty, avg_price FROM positions WHERE user_id = ? AND qty > 0',
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(pos) for pos in positions]

def execute_trade(user_id, symbol, qty, price, side, verified_by='biometric'):
    """Execute a buy or sell trade"""
    conn = get_db_connection()
    
    try:
        # Get current wallet balance
        wallet = get_user_wallet(user_id)
        
        if side == 'BUY':
            cost = qty * price
            if wallet < cost:
                return {'success': False, 'error': 'Insufficient balance'}
            
            # Update wallet
            new_balance = wallet - cost
            update_wallet(user_id, new_balance)
            
            # Update or create position
            existing = conn.execute(
                'SELECT qty, avg_price FROM positions WHERE user_id = ? AND symbol = ?',
                (user_id, symbol)
            ).fetchone()
            
            if existing:
                total_qty = existing['qty'] + qty
                total_cost = (existing['qty'] * existing['avg_price']) + cost
                new_avg_price = total_cost / total_qty
                conn.execute(
                    'UPDATE positions SET qty = ?, avg_price = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND symbol = ?',
                    (total_qty, new_avg_price, user_id, symbol)
                )
            else:
                conn.execute(
                    'INSERT INTO positions (user_id, symbol, qty, avg_price) VALUES (?, ?, ?, ?)',
                    (user_id, symbol, qty, price)
                )
        
        elif side == 'SELL':
            # Check if user has enough shares
            position = conn.execute(
                'SELECT qty FROM positions WHERE user_id = ? AND symbol = ?',
                (user_id, symbol)
            ).fetchone()
            
            if not position or position['qty'] < qty:
                return {'success': False, 'error': 'Insufficient shares'}
            
            proceeds = qty * price
            new_balance = wallet + proceeds
            update_wallet(user_id, new_balance)
            
            # Update position
            new_qty = position['qty'] - qty
            if new_qty > 0:
                conn.execute(
                    'UPDATE positions SET qty = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND symbol = ?',
                    (new_qty, user_id, symbol)
                )
            else:
                conn.execute(
                    'DELETE FROM positions WHERE user_id = ? AND symbol = ?',
                    (user_id, symbol)
                )
        
        # Record transaction
        conn.execute(
            '''INSERT INTO transactions (user_id, symbol, qty, price, side, verified_by, tx_time)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
            (user_id, symbol, qty, price, side, verified_by)
        )
        
        conn.commit()
        return {
            'success': True,
            'message': f'{side} {qty} {symbol} at ₹{price:.2f}',
            'new_balance': new_balance
        }
        
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()

def get_transaction_history(user_id, limit=50):
    """Get user's transaction history"""
    conn = get_db_connection()
    transactions = conn.execute(
        '''SELECT symbol, qty, price, side, verified_by, tx_time
           FROM transactions
           WHERE user_id = ?
           ORDER BY tx_time DESC
           LIMIT ?''',
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(tx) for tx in transactions]
