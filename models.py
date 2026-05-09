# models.py - Database Models using SQLAlchemy ORM
# This file defines all the database tables as Python classes

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Create the SQLAlchemy database instance
# This will be initialized with the Flask app in app.py
db = SQLAlchemy()


# ─────────────────────────────────────────────
# USER MODEL
# Stores all registered users
# ─────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80),  unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    avatar_color  = db.Column(db.String(7), default='#6366f1')  # hex color for avatar
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    group_memberships = db.relationship('GroupMember', back_populates='user', lazy='dynamic')
    paid_transactions  = db.relationship('Transaction', foreign_keys='Transaction.paid_by_id',  back_populates='paid_by_user',  lazy='dynamic')
    owed_transactions  = db.relationship('Transaction', foreign_keys='Transaction.paid_to_id',  back_populates='paid_to_user',  lazy='dynamic')
    created_groups     = db.relationship('Group', back_populates='creator', lazy='dynamic')

    def set_password(self, password):
        """Hash and store the password securely"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify a plaintext password against the stored hash"""
        return check_password_hash(self.password_hash, password)

    def get_initials(self):
        """Return the first letter of the username for avatar display"""
        return self.username[0].upper()

    def __repr__(self):
        return f'<User {self.username}>'


# ─────────────────────────────────────────────
# GROUP MODEL
# A group is a collection of friends sharing expenses
# ─────────────────────────────────────────────
class Group(db.Model):
    __tablename__ = 'groups'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), default='')
    invite_code = db.Column(db.String(10),  unique=True, nullable=False)  # Short code to join
    creator_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    creator      = db.relationship('User', back_populates='created_groups')
    members      = db.relationship('GroupMember',  back_populates='group', lazy='dynamic', cascade='all, delete-orphan')
    transactions = db.relationship('Transaction',  back_populates='group',  lazy='dynamic', cascade='all, delete-orphan')

    def get_total_expenses(self):
        """Sum of all non-settled transactions in this group"""
        total = db.session.query(
            db.func.sum(Transaction.amount)
        ).filter(
            Transaction.group_id == self.id,
            Transaction.is_settled == False
        ).scalar()
        return total or 0.0

    def get_member_count(self):
        return self.members.count()

    def __repr__(self):
        return f'<Group {self.name}>'


# ─────────────────────────────────────────────
# GROUP MEMBER MODEL
# Junction table between Users and Groups
# ─────────────────────────────────────────────
class GroupMember(db.Model):
    __tablename__ = 'group_members'

    id         = db.Column(db.Integer, primary_key=True)
    group_id   = db.Column(db.Integer, db.ForeignKey('groups.id'),  nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'),   nullable=False)
    joined_at  = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin   = db.Column(db.Boolean, default=False)  # Group creator gets admin

    # Relationships
    group = db.relationship('Group', back_populates='members')
    user  = db.relationship('User',  back_populates='group_memberships')

    # Prevent duplicate memberships
    __table_args__ = (db.UniqueConstraint('group_id', 'user_id'),)

    def __repr__(self):
        return f'<GroupMember user={self.user_id} group={self.group_id}>'


# ─────────────────────────────────────────────
# TRANSACTION MODEL
# Records every payment between two people in a group
# Example: Rahul paid ₹500 for Aman → paid_by=Rahul, paid_to=Aman, amount=500
# ─────────────────────────────────────────────
class Transaction(db.Model):
    __tablename__ = 'transactions'

    id          = db.Column(db.Integer, primary_key=True)
    group_id    = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    paid_by_id  = db.Column(db.Integer, db.ForeignKey('users.id'),  nullable=False)  # Who paid
    paid_to_id  = db.Column(db.Integer, db.ForeignKey('users.id'),  nullable=False)  # Who received / who owes
    amount      = db.Column(db.Float,   nullable=False)
    description = db.Column(db.String(200), default='')
    is_settled  = db.Column(db.Boolean, default=False)   # Has this been settled?
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    group        = db.relationship('Group', back_populates='transactions')
    paid_by_user = db.relationship('User', foreign_keys=[paid_by_id], back_populates='paid_transactions')
    paid_to_user = db.relationship('User', foreign_keys=[paid_to_id], back_populates='owed_transactions')
    settlement   = db.relationship('Settlement', back_populates='transaction', uselist=False)

    def __repr__(self):
        return f'<Transaction ₹{self.amount} from {self.paid_by_id} to {self.paid_to_id}>'


# ─────────────────────────────────────────────
# SETTLEMENT MODEL
# Records when a debt has been repaid
# ─────────────────────────────────────────────
class Settlement(db.Model):
    __tablename__ = 'settlements'

    id             = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
    settled_by_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Who confirmed the settlement
    settled_at     = db.Column(db.DateTime, default=datetime.utcnow)
    note           = db.Column(db.String(200), default='')

    # Relationships
    transaction = db.relationship('Transaction', back_populates='settlement')
    settled_by  = db.relationship('User')

    def __repr__(self):
        return f'<Settlement for Transaction {self.transaction_id}>'
