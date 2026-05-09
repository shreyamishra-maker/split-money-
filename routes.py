# routes.py - All Flask URL routes organized into Blueprints
# Each blueprint groups related routes together for cleaner code.

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Group, GroupMember, Transaction, Settlement
from database import generate_invite_code, calculate_balances, simplify_debts
from datetime import datetime
from io import BytesIO
import json

# ─────────────────────────────────────────────
# BLUEPRINTS
# ─────────────────────────────────────────────
auth_bp        = Blueprint('auth',        __name__)
main_bp        = Blueprint('main',        __name__)
group_bp       = Blueprint('groups',      __name__, url_prefix='/groups')
transaction_bp = Blueprint('transactions',__name__, url_prefix='/transactions')
api_bp         = Blueprint('api',         __name__, url_prefix='/api')


# ══════════════════════════════════════════════
# AUTH ROUTES  –  /login  /register  /logout
# ══════════════════════════════════════════════

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page - validate credentials and start a session"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Basic validation
        if not username or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            # Redirect to the page the user was trying to visit, or dashboard
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}! 👋', 'success')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page - create a new user account"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        # ── Validation ────────────────────────────────────────────
        errors = []
        if not all([username, email, password, confirm]):
            errors.append('All fields are required.')
        if len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if User.query.filter_by(username=username).first():
            errors.append('Username already taken.')
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('register.html')

        # ── Create User ───────────────────────────────────────────
        # Pick a random avatar color from a palette
        import random
        colors = ['#f59e0b','#10b981','#3b82f6','#ec4899','#8b5cf6','#ef4444','#14b8a6']
        new_user = User(
            username=username,
            email=email,
            avatar_color=random.choice(colors)
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash(f'Account created! Welcome, {username}! 🎉', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Log the user out and clear their session"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


# ══════════════════════════════════════════════
# MAIN ROUTES  –  /  /dashboard
# ══════════════════════════════════════════════

@main_bp.route('/')
def index():
    """Landing page - redirect to dashboard if logged in"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Main dashboard - show all groups the current user belongs to,
    plus a summary of how much they owe / are owed overall.
    """
    # Get all groups this user is a member of
    memberships = GroupMember.query.filter_by(user_id=current_user.id).all()
    group_ids   = [m.group_id for m in memberships]
    groups      = Group.query.filter(Group.id.in_(group_ids)).all()

    # Calculate a per-group balance summary
    group_summaries = []
    total_owed_to_me = 0
    total_i_owe      = 0

    for group in groups:
        balances = calculate_balances(group.id)
        my_balance = balances.get(current_user.id, 0)

        if my_balance > 0:
            total_owed_to_me += my_balance
        else:
            total_i_owe += abs(my_balance)

        group_summaries.append({
            'group':      group,
            'my_balance': round(my_balance, 2),
            'total_exp':  round(group.get_total_expenses(), 2),
            'members':    group.get_member_count()
        })

    return render_template(
        'dashboard.html',
        group_summaries  = group_summaries,
        total_owed_to_me = round(total_owed_to_me, 2),
        total_i_owe      = round(total_i_owe, 2)
    )


# ══════════════════════════════════════════════
# GROUP ROUTES  –  /groups/...
# ══════════════════════════════════════════════

@group_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new expense group"""
    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        if not name:
            flash('Group name is required.', 'error')
            return render_template('create_group.html')

        group = Group(
            name        = name,
            description = description,
            invite_code = generate_invite_code(),
            creator_id  = current_user.id
        )
        db.session.add(group)
        db.session.flush()  # Get the group.id before commit

        # Add creator as admin member
        db.session.add(GroupMember(
            group_id = group.id,
            user_id  = current_user.id,
            is_admin = True
        ))
        db.session.commit()

        flash(f'Group "{name}" created! 🎉 Invite code: {group.invite_code}', 'success')
        return redirect(url_for('groups.detail', group_id=group.id))

    return render_template('create_group.html')


@group_bp.route('/join', methods=['GET', 'POST'])
@login_required
def join():
    """Join an existing group using an invite code"""
    if request.method == 'POST':
        code = request.form.get('invite_code', '').strip().upper()

        if not code:
            flash('Please enter an invite code.', 'error')
            return render_template('join_group.html')

        group = Group.query.filter_by(invite_code=code).first()

        if not group:
            flash('Invalid invite code. Please check and try again.', 'error')
            return render_template('join_group.html')

        # Check if already a member
        existing = GroupMember.query.filter_by(
            group_id=group.id, user_id=current_user.id
        ).first()

        if existing:
            flash(f'You are already a member of "{group.name}".', 'info')
            return redirect(url_for('groups.detail', group_id=group.id))

        db.session.add(GroupMember(group_id=group.id, user_id=current_user.id))
        db.session.commit()

        flash(f'You joined "{group.name}"! 🎊', 'success')
        return redirect(url_for('groups.detail', group_id=group.id))

    return render_template('join_group.html')


@group_bp.route('/<int:group_id>')
@login_required
def detail(group_id):
    """
    Group detail page - shows members, balances, transactions,
    and simplified settlement suggestions.
    """
    group = Group.query.get_or_404(group_id)

    # Make sure the current user is a member
    membership = GroupMember.query.filter_by(
        group_id=group_id, user_id=current_user.id
    ).first()
    if not membership:
        flash('You are not a member of this group.', 'error')
        return redirect(url_for('main.dashboard'))

    # ── Members ───────────────────────────────────────────────────
    members_raw = GroupMember.query.filter_by(group_id=group_id).all()
    members     = [m.user for m in members_raw]

    # ── Balances ──────────────────────────────────────────────────
    balances  = calculate_balances(group_id)
    suggested = simplify_debts(balances)

    # Enrich suggested settlements with user objects
    settlements_display = []
    for s in suggested:
        from_user = User.query.get(s['from'])
        to_user   = User.query.get(s['to'])
        if from_user and to_user:
            settlements_display.append({
                'from_user': from_user,
                'to_user':   to_user,
                'amount':    s['amount']
            })

    # ── Transactions (most recent first) ──────────────────────────
    search = request.args.get('search', '').strip()
    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')

    txn_query = Transaction.query.filter_by(group_id=group_id)

    if search:
        txn_query = txn_query.filter(Transaction.description.ilike(f'%{search}%'))
    if date_from:
        try:
            txn_query = txn_query.filter(
                Transaction.created_at >= datetime.strptime(date_from, '%Y-%m-%d')
            )
        except ValueError:
            pass
    if date_to:
        try:
            txn_query = txn_query.filter(
                Transaction.created_at <= datetime.strptime(date_to + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
            )
        except ValueError:
            pass

    transactions = txn_query.order_by(Transaction.created_at.desc()).all()

    # Build a balance display list for each member
    member_balances = []
    for member in members:
        bal = round(balances.get(member.id, 0), 2)
        member_balances.append({'user': member, 'balance': bal})
    member_balances.sort(key=lambda x: x['balance'], reverse=True)

    return render_template(
        'group_detail.html',
        group               = group,
        members             = members,
        member_balances     = member_balances,
        transactions        = transactions,
        settlements_display = settlements_display,
        is_admin            = membership.is_admin,
        search              = search,
        date_from           = date_from,
        date_to             = date_to
    )


@group_bp.route('/<int:group_id>/export')
@login_required
def export_pdf(group_id):
    """Export the group's transactions to a PDF file"""
    group = Group.query.get_or_404(group_id)

    # Ensure membership
    if not GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first():
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))

    transactions = Transaction.query.filter_by(group_id=group_id)\
        .order_by(Transaction.created_at.desc()).all()

    # Generate PDF using reportlab
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch

        buffer = BytesIO()
        doc    = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch)
        styles = getSampleStyleSheet()
        story  = []

        # Title
        title_style = ParagraphStyle('Title', parent=styles['Title'],
                                     fontSize=18, textColor=colors.HexColor('#6366f1'))
        story.append(Paragraph(f'Expense Report: {group.name}', title_style))
        story.append(Paragraph(f'Generated on {datetime.now().strftime("%d %b %Y")}', styles['Normal']))
        story.append(Spacer(1, 0.3*inch))

        # Table header
        data = [['#', 'Description', 'Paid By', 'Paid To', 'Amount (₹)', 'Status', 'Date']]

        for i, txn in enumerate(transactions, 1):
            data.append([
                str(i),
                txn.description or '—',
                txn.paid_by_user.username,
                txn.paid_to_user.username,
                f'₹{txn.amount:,.2f}',
                '✓ Settled' if txn.is_settled else 'Pending',
                txn.created_at.strftime('%d %b %Y')
            ])

        table = Table(data, colWidths=[0.4*inch, 2.2*inch, 1*inch, 1*inch, 1*inch, 0.9*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#6366f1')),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTSIZE',   (0,0), (-1,0), 9),
            ('FONTSIZE',   (0,1), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8f9ff')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('ALIGN', (4,0), (4,-1), 'RIGHT'),
            ('ALIGN', (0,0), (0,-1), 'CENTER'),
            ('LEFTPADDING',  (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(table)

        doc.build(story)
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'{group.name.replace(" ","_")}_expenses.pdf',
            mimetype='application/pdf'
        )

    except ImportError:
        flash('PDF export requires reportlab. Run: pip install reportlab', 'error')
        return redirect(url_for('groups.detail', group_id=group_id))


# ══════════════════════════════════════════════
# TRANSACTION ROUTES  –  /transactions/...
# ══════════════════════════════════════════════

@transaction_bp.route('/add/<int:group_id>', methods=['GET', 'POST'])
@login_required
def add(group_id):
    """Add a new transaction (expense) to a group"""
    group = Group.query.get_or_404(group_id)

    # Ensure membership
    if not GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first():
        flash('You are not a member of this group.', 'error')
        return redirect(url_for('main.dashboard'))

    # Get all group members for the paid_by / paid_to dropdowns
    members_raw = GroupMember.query.filter_by(group_id=group_id).all()
    members     = [m.user for m in members_raw]

    if request.method == 'POST':
        paid_by_id  = request.form.get('paid_by', type=int)
        paid_to_id  = request.form.get('paid_to', type=int)
        amount      = request.form.get('amount', type=float)
        description = request.form.get('description', '').strip()

        # ── Validation ────────────────────────────────────────────
        errors = []
        if not all([paid_by_id, paid_to_id, amount]):
            errors.append('Paid by, Paid to, and Amount are required.')
        if amount and amount <= 0:
            errors.append('Amount must be greater than 0.')
        if paid_by_id == paid_to_id:
            errors.append('Paid By and Paid To cannot be the same person.')

        # Make sure both users are group members
        member_ids = [m.id for m in members]
        if paid_by_id not in member_ids or paid_to_id not in member_ids:
            errors.append('Both users must be members of this group.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('add_transaction.html', group=group, members=members)

        txn = Transaction(
            group_id    = group_id,
            paid_by_id  = paid_by_id,
            paid_to_id  = paid_to_id,
            amount      = amount,
            description = description
        )
        db.session.add(txn)
        db.session.commit()

        payer = User.query.get(paid_by_id)
        ower  = User.query.get(paid_to_id)
        flash(f'Transaction added: {payer.username} paid ₹{amount:,.2f} for {ower.username}', 'success')
        return redirect(url_for('groups.detail', group_id=group_id))

    return render_template('add_transaction.html', group=group, members=members)


@transaction_bp.route('/settle/<int:txn_id>', methods=['POST'])
@login_required
def settle(txn_id):
    """Mark a transaction as settled"""
    txn   = Transaction.query.get_or_404(txn_id)
    group = Group.query.get(txn.group_id)

    # Only the payer or payee can settle
    if current_user.id not in [txn.paid_by_id, txn.paid_to_id]:
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    if txn.is_settled:
        return jsonify({'success': False, 'message': 'Already settled'})

    txn.is_settled = True
    note = request.json.get('note', '') if request.is_json else ''
    db.session.add(Settlement(
        transaction_id=txn.id,
        settled_by_id=current_user.id,
        note=note
    ))
    db.session.commit()

    return jsonify({'success': True, 'message': 'Transaction settled!'})


@transaction_bp.route('/delete/<int:txn_id>', methods=['POST'])
@login_required
def delete(txn_id):
    """Delete a transaction (only the person who created the transaction can delete it)"""
    txn = Transaction.query.get_or_404(txn_id)

    # Only the payer can delete
    if current_user.id != txn.paid_by_id:
        flash('You can only delete transactions you created.', 'error')
        return redirect(url_for('groups.detail', group_id=txn.group_id))

    group_id = txn.group_id
    db.session.delete(txn)
    db.session.commit()
    flash('Transaction deleted.', 'success')
    return redirect(url_for('groups.detail', group_id=group_id))


# ══════════════════════════════════════════════
# API ROUTES  –  /api/...  (JSON responses)
# ══════════════════════════════════════════════

@api_bp.route('/group/<int:group_id>/balances')
@login_required
def api_balances(group_id):
    """Return current balances for a group as JSON (for real-time UI updates)"""
    if not GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first():
        return jsonify({'error': 'Not a member'}), 403

    balances  = calculate_balances(group_id)
    suggested = simplify_debts(balances)

    # Build enriched response
    balance_list = []
    for uid, amt in balances.items():
        user = User.query.get(uid)
        if user:
            balance_list.append({
                'user_id':  uid,
                'username': user.username,
                'balance':  round(amt, 2)
            })

    suggest_list = []
    for s in suggested:
        fu = User.query.get(s['from'])
        tu = User.query.get(s['to'])
        if fu and tu:
            suggest_list.append({
                'from': fu.username,
                'to':   tu.username,
                'amount': s['amount']
            })

    return jsonify({
        'balances':    balance_list,
        'settlements': suggest_list
    })


@api_bp.route('/group/<int:group_id>/transactions')
@login_required
def api_transactions(group_id):
    """Return all transactions for a group as JSON"""
    if not GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first():
        return jsonify({'error': 'Not a member'}), 403

    transactions = Transaction.query.filter_by(group_id=group_id)\
        .order_by(Transaction.created_at.desc()).limit(50).all()

    return jsonify([{
        'id':          t.id,
        'paid_by':     t.paid_by_user.username,
        'paid_to':     t.paid_to_user.username,
        'amount':      t.amount,
        'description': t.description,
        'is_settled':  t.is_settled,
        'date':        t.created_at.strftime('%d %b %Y')
    } for t in transactions])
