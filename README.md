# 💰 SplitSmart — Expense Sharing App

A full-stack expense splitting app for groups of friends built with **Python Flask**, **SQLite**, and a **dark glassmorphism UI**.

---

## 🚀 Quick Start (Run Locally)

### 1. Clone / Download the project

```bash
cd expense_app
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
python app.py
```

### 5. Open in your browser

```
http://127.0.0.1:5000
```

> The first run automatically creates the database and seeds demo data.

---

## 🔑 Demo Accounts

| Username | Password     |
|----------|--------------|
| rahul    | password123  |
| aman     | password123  |
| priya    | password123  |
| arjun    | password123  |

---

## 📁 Project Structure

```
expense_app/
│
├── app.py          # Flask app factory & entry point
├── models.py       # SQLAlchemy database models
├── routes.py       # All URL routes (organized in Blueprints)
├── database.py     # DB init, balance calculation, debt simplification
├── requirements.txt
│
├── static/
│   ├── css/
│   │   └── style.css       # Full UI styling (glassmorphism dark theme)
│   └── js/
│       └── app.js          # Client-side interactions & API calls
│
└── templates/
    ├── base.html           # Shared layout (navbar, flashes, blobs)
    ├── login.html          # Login page
    ├── register.html       # Registration page
    ├── dashboard.html      # User dashboard with all groups
    ├── group_detail.html   # Group page (members, balances, transactions)
    ├── add_transaction.html
    ├── create_group.html
    └── join_group.html
```

---

## 🗄️ Database Schema

### `users`
| Column       | Type    | Notes                  |
|--------------|---------|------------------------|
| id           | Integer | Primary key            |
| username     | String  | Unique                 |
| email        | String  | Unique                 |
| password_hash| String  | Bcrypt hashed          |
| avatar_color | String  | Hex color for UI       |

### `groups`
| Column      | Type    | Notes                      |
|-------------|---------|----------------------------|
| id          | Integer | Primary key                |
| name        | String  |                            |
| description | String  |                            |
| invite_code | String  | Unique 6-char code         |
| creator_id  | FK      | → users.id                 |

### `group_members`
| Column    | Type    | Notes                   |
|-----------|---------|-------------------------|
| id        | Integer | Primary key             |
| group_id  | FK      | → groups.id             |
| user_id   | FK      | → users.id              |
| is_admin  | Boolean | Group creator = True    |

### `transactions`
| Column      | Type    | Notes                          |
|-------------|---------|--------------------------------|
| id          | Integer | Primary key                    |
| group_id    | FK      | → groups.id                    |
| paid_by_id  | FK      | → users.id (who paid)          |
| paid_to_id  | FK      | → users.id (who owes)          |
| amount      | Float   |                                |
| description | String  |                                |
| is_settled  | Boolean | False = pending                |

### `settlements`
| Column         | Type    | Notes                   |
|----------------|---------|-------------------------|
| id             | Integer | Primary key             |
| transaction_id | FK      | → transactions.id       |
| settled_by_id  | FK      | → users.id              |
| note           | String  | Optional note           |

---

## ✨ Features

- 🔐 Authentication (register, login, logout, password hashing)
- 👥 Create groups with auto-generated invite codes
- 🔗 Join groups using invite codes
- 💸 Add transactions (who paid for whom)
- 📊 Automatic balance calculation per group
- 🧮 Smart debt simplification (minimum settlements needed)
- ✅ Settle individual transactions with notes
- 🔍 Search and filter transactions by description and date
- 📄 Export transactions to PDF
- 📱 Fully mobile responsive
- 🌙 Dark glassmorphism UI
- ⚡ Real-time balance polling (every 30s via REST API)

---

## 🛡️ Security

- Passwords hashed with Werkzeug (PBKDF2-SHA256)
- Flask-Login session management
- CSRF protection via Flask-WTF
- Route-level login_required decorators
- Membership validation before any group/transaction access

---

## 📦 Dependencies

```
Flask              - Web framework
Flask-SQLAlchemy   - ORM for database
Flask-Login        - Session / authentication
Flask-WTF          - CSRF protection
Werkzeug           - Password hashing
reportlab          - PDF export
python-dateutil    - Date parsing
```
