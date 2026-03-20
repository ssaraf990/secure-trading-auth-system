#!/usr/bin/env python3
"""
Startup script for IS Lab Project
"""
import sys
import traceback

try:
    print("=" * 60)
    print("🚀 Starting IS Lab Project Server...")
    print("=" * 60)
    
    # Initialize database
    print("\n📦 Initializing database...")
    from app import app, init_db
    init_db()
    print("✅ Database initialized")
    
    # Check modules
    print("\n🔍 Checking modules...")
    from modules.biometric.biometric_routes import biometric_bp
    from modules.stocks.stock_routes import stock_bp
    from security.threat_routes import threat_bp
    print("✅ All modules loaded")
    
    print("\n" + "=" * 60)
    print("📍 Server starting on http://127.0.0.1:5001")
    print("📍 Server starting on http://localhost:5001")
    print("🛑 Press Ctrl+C to stop the server")
    print("=" * 60 + "\n")
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
    
except Exception as e:
    print("\n❌ ERROR starting server:")
    print(f"Error type: {type(e).__name__}")
    print(f"Error message: {str(e)}")
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)

