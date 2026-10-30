# -*- coding: utf-8 -*-
"""
AI Time Keeper — Cloud (Flask) version
লোকাল Python http.server-এর বদলায় এই ফাইলটি Render/Heroku/Gunicornে চালানো যাবে।
ডাটাবেজ: PostgreSQL (Render Free-tier) — এক্সেল/জেসন ফাইলের বদলায় ডাটাবেজে সব সেভ হবে।
"""

import os
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash


# ---------------------------------------------------------------- app setup
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-production')

# Render Deploy কালে DATABASE_URL এনভায়রনমেন্ট ভেরিয়েবল থেকে আসবে
db_uri = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
CORS(app, supports_credentials=True)


# ---------------------------------------------------------------- ডাটাবেজ মডেল
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=True)
    lang = db.Column(db.String(10), default='en')   # 'bn' বা 'en'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class DataSheet(db.Model):
    """আপলোড করা এক্সেল ডাটা — ডিস্কে ফাইল না রেখে ডাটাবেজে জেসন আকারে সেভ।"""
    __tablename__ = 'data_sheets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    filename = db.Column(db.String(200), nullable=False)
    month = db.Column(db.Integer, nullable=True)
    year = db.Column(db.Integer, nullable=True)
    data_json = db.Column(db.Text, nullable=True)      # পărস করা এক্সেল ডাটা (JSON স্ট্রিং)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Invoice(db.Model):
    """③ Add Invoice এবং ① Statement উভয়ই এখানে সেভ হবে।"""
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    client_name = db.Column(db.String(200), nullable=False)
    client_address = db.Column(db.String(300), nullable=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    invoice_no = db.Column(db.String(20), nullable=False)
    kind = db.Column(db.String(20), default='statement')   # 'statement' | 'add_invoice'
    total = db.Column(db.Float, default=0.0)
    net = db.Column(db.Float, default=0.0)
    data_json = db.Column(db.Text, nullable=True)          # পুরো ইনভয়েস বিবরণ (JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class LaborAssign(db.Model):
    """লোক → প্রোভাইডার ম্যাপিং (labor_assign.json-এর বদলায় ডাটাবেজে)।"""
    __tablename__ = 'labor_assign'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    person = db.Column(db.String(100), nullable=False)
    provider = db.Column(db.String(100), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------- ডাটাবেজ তৈরি
with app.app_context():
    db.create_all()


# ---------------------------------------------------------------- Auth রুট
@app.route('/api/auth/register', methods=['POST'], strict_slashes=False)
def register():
    d = request.get_json() or {}
    email = (d.get('email') or '').strip().lower()
    pw = d.get('password') or ''
    name = d.get('name') or email

    if not email or not pw:
        return jsonify({'ok': False, 'error': 'ইমেইল ও পাসওয়ার্ড প্রয়োজন'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'ok': False, 'error': 'এই ইমেইল নথিভুক্ত করা আছে'}), 400

    u = User(email=email, name=name)
    u.set_password(pw)
    db.session.add(u)
    db.session.commit()
    return jsonify({
        'ok': True,
        'user': {'id': u.id, 'email': u.email, 'name': u.name}
    })


@app.route('/api/auth/login', methods=['POST'], strict_slashes=False)
def login():
    d = request.get_json() or {}
    email = (d.get('email') or '').strip().lower()
    pw = d.get('password') or ''
    u = User.query.filter_by(email=email).first()
    if u and u.check_password(pw):
        login_user(u)
        return jsonify({
            'ok': True,
            'user': {'id': u.id, 'email': u.email, 'name': u.name, 'lang': u.lang}
        })
    return jsonify({'ok': False, 'error': 'ভুল আইডি বা পাসওয়ার্ড'}), 401


@app.route('/api/auth/logout', methods=['POST'], strict_slashes=False)
@login_required
def logout():
    logout_user()
    return jsonify({'ok': True})


@app.route('/api/auth/me', methods=['GET'], strict_slashes=False)
def me():
    if current_user.is_authenticated:
        return jsonify({
            'ok': True,
            'user': {
                'id': current_user.id,
                'email': current_user.email,
                'name': current_user.name,
                'lang': current_user.lang
            }
        })
    return jsonify({'ok': False, 'error': 'লগইন নেই'}), 401


# ---------------------------------------------------------------- মাস লিস্ট
@app.route('/api/months', methods=['GET'], strict_slashes=False)
@login_required
def months():
    sheets = (DataSheet.query
              .filter_by(user_id=current_user.id)
              .order_by(DataSheet.year, DataSheet.month)
              .all())
    out = []
    for s in sheets:
        out.append({
            'folder': f"{s.month:02d}-{s.year}",
            'label': f"{s.month:02d}-{s.year}",
            'files': [{'name': s.filename, 'xlsx': True}],
            'size': len(s.data_json or ''),
            'month': s.month,
            'year': s.year
        })
    return jsonify({'ok': True, 'months': out})


# ---------------------------------------------------------------- লেবার / ওয়ার্কার
@app.route('/api/ws/labor', methods=['GET'], strict_slashes=False)
@login_required
def labor():
    assigns = LaborAssign.query.filter_by(user_id=current_user.id).all()
    providers = {}
    for a in assigns:
        providers.setdefault(a.provider, []).append({
            'name': a.person,
            'hours': 0,
            'rate': 0,
            'provider': a.provider
        })
    return jsonify({'ok': True, 'providers': [
        {'provider': k, 'workers': v} for k, v in providers.items()
    ]})


@app.route('/api/ws/labor-assign', methods=['POST'], strict_slashes=False)
@login_required
def labor_assign_save():
    d = request.get_json() or {}
    person = (d.get('person') or '').strip()
    provider = (d.get('provider') or '').strip()
    if not person:
        return jsonify({'ok': False, 'error': 'নাম প্রয়োজন'}), 400

    existing = LaborAssign.query.filter_by(
        user_id=current_user.id, person=person
    ).first()
    if existing:
        existing.provider = provider
    else:
        db.session.add(LaborAssign(user_id=current_user.id, person=person, provider=provider))
    db.session.commit()
    return jsonify({'ok': True, 'person': person, 'provider': provider})


# ---------------------------------------------------------------- ইনভয়েস প্রিভিউ (① Statement)
@app.route('/api/ws/invoice-gen', methods=['GET'], strict_slashes=False)
@login_required
def invoice_gen():
    prov = request.args.get('prov', '')
    month = int(request.args.get('month', 0) or 0)
    year = int(request.args.get('year', 0) or 0)
    return jsonify({
        'ok': True,
        'invoice_no': '01',
        'month': month,
        'year': year,
        'prov': prov,
        'workers': [],
        'total': 0.0,
        'net': 0.0,
        'message': 'ডাটাবেজ-ভিত্তিক Statement প্রিভিউ — পুরনো লগিক এখানে যোগ করুন'
    })


# ---------------------------------------------------------------- ③ Add Invoice প্রিভিউ
@app.route('/api/ws/add-invoice', methods=['GET'], strict_slashes=False)
@login_required
def add_invoice_preview():
    client_key = (request.args.get('client_key') or '').strip()
    client_name = (request.args.get('client_name') or client_key).strip()
    client_address = (request.args.get('client_address') or '').strip()
    month = int(request.args.get('month', 0) or 0)
    year = int(request.args.get('year', 0) or 0)

    if not client_key:
        return jsonify({'ok': False, 'error': 'কোম্পানি/সাইটের নাম দিন'}), 400

    return jsonify({
        'ok': True,
        'invoice_no': '01',
        'client_key': client_key,
        'client_name': client_name,
        'client_address': client_address,
        'month': month,
        'year': year,
        'workers': [],
        'total': 0.0,
        'warn': '',
        'message': 'ডাটাবেজ-ভিত্তিক Add Invoice প্রিভিউ — পুরনো লগিক এখানে যোগ করুন'
    })


# ---------------------------------------------------------------- ③ Add Invoice সেভ
@app.route('/api/ws/add-invoice-save-one', methods=['POST'], strict_slashes=False)
@login_required
def add_invoice_save():
    d = request.get_json() or {}
    client_key = (d.get('client_key') or '').strip()
    client_name = (d.get('client_name') or client_key).strip()
    client_address = d.get('client_address') or ''
    month = int(d.get('month') or 0)
    year = int(d.get('year') or 0)
    rates = d.get('rates') if isinstance(d.get('rates'), dict) else {}
    total = float(d.get('total') or 0)

    if not client_key:
        return jsonify({'ok': False, 'error': 'কোম্পানি/সাইটের নাম দিন'}), 400

    # আলাদা নম্বর চেইন (একই ক্লায়েন্ট+মাস+সাল = একই নম্বর)
    last = (Invoice.query
            .filter_by(user_id=current_user.id, client_name=client_name,
                       month=month, year=year, kind='add_invoice')
            .order_by(Invoice.invoice_no.desc())
            .first())
    next_no = (int(last.invoice_no) + 1) if last and last.invoice_no.isdigit() else 1

    inv = Invoice(
        user_id=current_user.id,
        client_name=client_name,
        client_address=client_address,
        month=month,
        year=year,
        invoice_no=f"{next_no:02d}",
        kind='add_invoice',
        total=total,
        net=total,
        data_json=str({'rates': rates})
    )
    db.session.add(inv)
    db.session.commit()

    return jsonify({
        'ok': True,
        'file': f"{inv.invoice_no}-{client_name}.pdf",
        'invoice_no': inv.invoice_no,
        'dir': 'cloud/database'
    })


# ---------------------------------------------------------------- ফাইল লিস্ট (ক্লাউডে ডাটাবেজ থেকে)
@app.route('/api/files', methods=['GET'], strict_slashes=False)
@login_required
def files():
    sheets = DataSheet.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        'ok': True,
        'files': [{
            'name': s.filename,
            'month': s.month,
            'year': s.year,
            'size': len(s.data_json or ''),
            'xlsx': True
        } for s in sheets]
    })


# ---------------------------------------------------------------- স্ট্যাটিক ফ্রন্টএন্ড সার্ভ (ফিক্সড)
@app.route('/', methods=['GET'])
def index():
    """হোম পেজে গেলে workspace.html খোলবে।"""
    return send_from_directory(app.static_folder, 'workspace.html')


@app.route('/workspace', methods=['GET'])
def workspace():
    return send_from_directory(app.static_folder, 'workspace.html')


@app.route('/<path:path>', methods=['GET'])
def static_proxy(path):
    """
    static ফোল্ডার থেকে HTML/JS/CSS ছবি ইত্যাদি সার্ভ করবে।
    কিন্তু /api/ পাথে যদি কোনো রুট না মেলে, HTML বদলে JSON 404 রিটার্ন করবে
    যাতে ফ্রন্টএন্ডে JSON 파라্স এরর না হয়।
    """
    # API পাথে অনির্ধারিত রুটের場合ে JSON এρ্রor দিন, HTML নয়
    if path.startswith('api/') or path == 'api':
        return jsonify({'ok': False, 'error': 'API endpoint not found'}), 404

    # ডিরেক্টরি ট্রাভার্সাল রোধ
    if '..' in path or path.startswith('/'):
        abort(404)

    full_path = os.path.join(app.static_folder, path)
    if os.path.isfile(full_path):
        return send_from_directory(app.static_folder, path)

    # ফাইল না পাওয়ায় 404
    abort(404)


# ---------------------------------------------------------------- রান
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=False
    )
