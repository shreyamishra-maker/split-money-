# database.py - Database initialization and helper functions
# This file handles database setup and provides utility functions

from models import db, User, Group, GroupMember, Transaction, Settlement
from datetime import datetime
import random
import string


def init_db(app):
    """Initialize the database with the Flask app and create all tables"""
    db.init_app(app)
    with app.app_context():
        db.create_all()
        print("✅ Database tables created successfully")


def generate_invite_code(length=6):
    """Generate a random uppercase invite code for groups (e.g., 'XKCD42')"""
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=length))
        # Make sure this code doesn't already exist
        if not Group.query.filter_by(invite_code=code).first():
            return code


def calculate_balances(group_id):
    """
    Calculate net balance for every member in a group.

    Returns a dict:  { user_id: net_amount }
    Positive net  → this user is OWED money (others owe them)
    Negative net  → this user OWES money (they owe others)

    Example:
        Rahul paid ₹500 for Aman
        → Rahul's balance: +500  (he is owed 500)
        → Aman's  balance: -500  (he owes 500)
    """
    balances = {}

    # Fetch all unsettled transactions for this group
    transactions = Transaction.query.filter_by(
        group_id=group_id,
        is_settled=False
    ).all()

    for txn in transactions:
        payer = txn.paid_by_id   # Person who spent money
        ower  = txn.paid_to_id   # Person who received / owes

        # payer gets credit (positive)
        balances[payer] = balances.get(payer, 0) + txn.amount
        # ower gets debit (negative)
        balances[ower]  = balances.get(ower, 0) - txn.amount

    return balances


def simplify_debts(balances):
    """
    Take a raw balance dict and compute the minimum number of
    transactions needed to settle all debts.

    Returns a list of dicts:
        [ { 'from': user_id, 'to': user_id, 'amount': float }, ... ]

    Algorithm:
        1. Split users into 'creditors' (positive balance) and
           'debtors' (negative balance).
        2. Greedily match the largest debtor with the largest creditor.
        3. Repeat until all balances are zero.
    """
    # Separate into creditors and debtors
    creditors = sorted(
        [(uid, amt) for uid, amt in balances.items() if amt > 0.01],
        key=lambda x: x[1], reverse=True
    )
    debtors = sorted(
        [(uid, abs(amt)) for uid, amt in balances.items() if amt < -0.01],
        key=lambda x: x[1], reverse=True
    )

    settlements = []
    ci, di = 0, 0  # creditor index, debtor index

    while ci < len(creditors) and di < len(debtors):
        cred_id, cred_amt = creditors[ci]
        debt_id, debt_amt = debtors[di]

        # The settlement amount is the smaller of the two
        settle_amount = round(min(cred_amt, debt_amt), 2)

        settlements.append({
            'from':   debt_id,   # This person pays
            'to':     cred_id,   # This person receives
            'amount': settle_amount
        })

        # Reduce balances
        creditors[ci] = (cred_id, round(cred_amt - settle_amount, 2))
        debtors[di]   = (debt_id, round(debt_amt - settle_amount, 2))

        # Move past fully settled entries
        if creditors[ci][1] < 0.01:
            ci += 1
        if debtors[di][1] < 0.01:
            di += 1

    return settlements


def seed_demo_data(app):
    """
    Insert sample data so the app works right out of the box.
    Creates 4 users, 2 groups, and several transactions.
    Run this only once (checks for existing data first).
    """
    with app.app_context():
        # Skip if data already exists
        if User.query.count() > 0:
            print("ℹ️  Demo data already exists, skipping seed.")
            return

        print("🌱 Seeding demo data...")

        # ── Create Users ──────────────────────────────────────────
        colors = ['#f59e0b', '#10b981', '#3b82f6', '#ec4899']
        names  = [
            ('rahul',  'rahul@demo.com',  'password123'),
            ('aman',   'aman@demo.com',   'password123'),
            ('priya',  'priya@demo.com',  'password123'),
            ('arjun',  'arjun@demo.com',  'password123'),
        ]

        users = []
        for (uname, email, pwd), color in zip(names, colors):
            u = User(username=uname, email=email, avatar_color=color)
            u.set_password(pwd)
            db.session.add(u)
            users.append(u)

        db.session.flush()  # Assign IDs without committing

        # ── Create Groups ─────────────────────────────────────────
        g1 = Group(
            name='Goa Trip 🏖️',
            description='Our epic Goa trip expenses',
            invite_code=generate_invite_code(),
            creator_id=users[0].id
        )
        g2 = Group(
            name='Flat Expenses 🏠',
            description='Monthly rent, electricity, groceries',
            invite_code=generate_invite_code(),
            creator_id=users[0].id
        )
        db.session.add_all([g1, g2])
        db.session.flush()

        # ── Add Members to Groups ─────────────────────────────────
        for u in users:
            db.session.add(GroupMember(
                group_id=g1.id,
                user_id=u.id,
                is_admin=(u.id == users[0].id)
            ))
        for u in users[:3]:  # Only 3 members in flat group
            db.session.add(GroupMember(
                group_id=g2.id,
                user_id=u.id,
                is_admin=(u.id == users[0].id)
            ))

        db.session.flush()

        # ── Create Transactions ───────────────────────────────────
        # Goa Trip transactions
        txns = [
            # (group, paid_by, paid_to, amount, description)
            (g1, users[0], users[1], 1200, 'Hotel booking - Aman\'s share'),
            (g1, users[0], users[2], 1200, 'Hotel booking - Priya\'s share'),
            (g1, users[0], users[3], 1200, 'Hotel booking - Arjun\'s share'),
            (g1, users[1], users[2], 450,  'Beach shack dinner - Priya\'s share'),
            (g1, users[1], users[3], 450,  'Beach shack dinner - Arjun\'s share'),
            (g1, users[2], users[0], 300,  'Taxi to airport - Rahul\'s share'),
            # Flat expenses
            (g2, users[0], users[1], 3500, 'Rent - Aman\'s share'),
            (g2, users[0], users[2], 3500, 'Rent - Priya\'s share'),
            (g2, users[1], users[0], 600,  'Electricity bill - Rahul\'s share'),
            (g2, users[2], users[0], 250,  'Internet bill - Rahul\'s share'),
        ]

        for grp, payer, ower, amt, desc in txns:
            db.session.add(Transaction(
                group_id=grp.id,
                paid_by_id=payer.id,
                paid_to_id=ower.id,
                amount=amt,
                description=desc
            ))

        db.session.commit()
        print("✅ Demo data seeded! Login with: rahul / password123")
