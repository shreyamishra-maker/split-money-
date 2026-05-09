# app.py - Main Flask Application Entry Point
# This file creates and configures the Flask app, then starts the server.

import os
from flask import Flask
from flask_login import LoginManager
from models import db, User
from database import init_db, seed_demo_data

# ─────────────────────────────────────────────
# APP FACTORY
# ─────────────────────────────────────────────
def create_app():
    """
    Create and configure the Flask application.
    Using an app factory pattern makes the app easier to test and extend.
    """
    app = Flask(__name__)

    # ── Configuration ──────────────────────────────────────────────
    # SECRET_KEY is used to sign session cookies (keep this secret in production!)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # SQLite database file stored in the project root
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'expense_tracker.db')

    # Disable modification tracking (saves memory)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # WTF CSRF protection secret
    app.config['WTF_CSRF_SECRET_KEY'] = os.environ.get('WTF_CSRF_SECRET_KEY', 'csrf-secret-key')

    # ── Initialize Extensions ──────────────────────────────────────
    init_db(app)  # SQLAlchemy

    # Flask-Login setup
    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'         # Redirect to this route if not logged in
    login_manager.login_message = 'Please log in to continue.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        """Tell Flask-Login how to load a user from the session"""
        return User.query.get(int(user_id))

    # ── Register Blueprints (Route Groups) ────────────────────────
    from routes import auth_bp, main_bp, group_bp, transaction_bp, api_bp
    app.register_blueprint(auth_bp)        # /login, /register, /logout
    app.register_blueprint(main_bp)        # /, /dashboard
    app.register_blueprint(group_bp)       # /groups/...
    app.register_blueprint(transaction_bp) # /transactions/...
    app.register_blueprint(api_bp)         # /api/...

    return app


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == '__main__':
    app = create_app()

    # Seed demo data on first run
    seed_demo_data(app)

    print("\n🚀 Starting Expense Tracker...")
    print("📌 Open your browser at: http://127.0.0.1:5000")
    print("👤 Demo login: rahul / password123\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
