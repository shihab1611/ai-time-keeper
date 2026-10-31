# -*- coding: utf-8 -*-
"""
AI Time Keeper — Cloud (Flask) version
লোকাল http.server ইঞ্জিনের সমস্ত রাউট, এক্সেল প্রসেসিং, ইনভয়েস লজিক,
স্টেটমেন্ট, মাস ক্লায়ার ও ব্যাকআপ সিস্টেম ক্লাউডে পোর্ট করা।
"""

import os
import re
import json
import time
import shutil
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------------------- локал ইঞ্জিন মডিউল ইমপোর্ট
BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in __import__("sys").path:
    __import__("sys").path.insert(0, BASE)
if os.path.join(BASE, "extensions") not in __import__("sys").path:
    __import__("sys").path.insert(0, os.path.join(BASE, "extensions"))

import invoice_gen as G
import add_invoice as AI
import company_invoice as C
import months as M

# ---------------------------------------------------------------- app setup
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-production')

db_uri = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Neon-এর মতো ম্যানেজড Postgres-এ কম্পিউট ঘুমিয়ে গেলে পুরনো কানেকশন কাটা পড়ে —
# pool_pre_ping প্রতি ব্যবহারের আগে কানেকশন যাচাই করে, মৃত কানেকশনের 500 আর হয় না
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# নিরাপত্তা: CORS শুধু অনুমোদিত ওরিজিনে — ক্রেডেনশিয়ালসহ যেকোনো সাইট থেকে কল বন্ধ
_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    'ALLOWED_ORIGINS',
    'https://ai-time-keeper.onrender.com,http://localhost:5000,http://127.0.0.1:5000'
).split(',') if o.strip()]
CORS(app, supports_credentials=True, origins=_ALLOWED_ORIGINS or None)

# নিরাপত্তা: সেশন কুকি ফ্ল্যাগ — Render-এ HTTPS বাধ্যতামূলক, লোকাল টেস্টে http চলে
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if os.environ.get('RENDER'):
    app.config['SESSION_COOKIE_SECURE'] = True


# ---------------------------------------------------------------- ডাটাবেজ মডেল
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=True)
    lang = db.Column(db.String(10), default='bn')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class DataSheet(db.Model):
    __tablename__ = 'data_sheets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    filename = db.Column(db.String(200), nullable=False)
    month = db.Column(db.Integer, nullable=True)
    year = db.Column(db.Integer, nullable=True)
    data_json = db.Column(db.Text, nullable=True)
    file_bytes = db.Column(db.LargeBinary, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    client_name = db.Column(db.String(200), nullable=False)
    client_address = db.Column(db.String(300), nullable=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    invoice_no = db.Column(db.String(20), nullable=False)
    kind = db.Column(db.String(20), default='statement')
    total = db.Column(db.Float, default=0.0)
    net = db.Column(db.Float, default=0.0)
    data_json = db.Column(db.Text, nullable=True)
    pdf_bytes = db.Column(db.LargeBinary, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class LaborAssign(db.Model):
    __tablename__ = 'labor_assign'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    person = db.Column(db.String(100), nullable=False)
    provider = db.Column(db.String(100), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConfigStore(db.Model):
    __tablename__ = 'config_store'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MonthArchive(db.Model):
    """মাস ক্লিয়ারের হিস্ট্রি — বন্ধ মাসের ডাটা শিট ও টোটাল শিট স্থায়ী সংরক্ষণ।
    লোকালের months ফোল্ডার-আর্কাইভের ক্লাউড-সমতুল্য।"""
    __tablename__ = 'month_archives'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(30), nullable=False, default='file')  # data_sheet / total_sheet
    filename = db.Column(db.String(200), nullable=False)
    file_bytes = db.Column(db.LargeBinary, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AdvanceEntry(db.Model):
    """অগ্রিম/বেতন-খাতা — ক্লাউডের মূল লেজার (লোকালের 'Advance sheet বট.xlsx'-এর ক্লাউড-সমতুল্য)।
    status: খালি/'' = বাকি, 'Paide'/'paid'/'clear' জাতীয় = পরিশোধিত (পুরনো শিটের রীতি মেনে)।"""
    __tablename__ = 'advance_entries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    person = db.Column(db.String(120), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(50), default='')
    date = db.Column(db.String(20), default='')
    reason = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class LaborDuty(db.Model):
    """লেবার-শিটের ক্লাউড-সমতুল্য — কে কোন প্রোভাইডারে, কোন সাইটে, রেট/শুরু-তারিখ/বন্ধ + ডিউটি-হিস্ট্রি।
    লোকালের 'working in company Manpower 2 বট.xlsx'-এর ক্লাউড-সমতুল্য (হিস্ট্রি ছিল ঘরের কমেন্টে)।"""
    __tablename__ = 'labor_duty'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    person = db.Column(db.String(120), nullable=False, index=True)
    provider = db.Column(db.String(120), default='')
    site = db.Column(db.String(120), default='')
    start = db.Column(db.String(20), default='')
    rate = db.Column(db.Float, nullable=True)
    off = db.Column(db.Boolean, default=False)
    history = db.Column(db.Text, default='[]')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@login_manager.unauthorized_handler
def _unauthorized():
    # লগইন ছাড়া API কলে redirect নয় — পরিষ্কার 401 JSON
    return jsonify({'ok': False, 'error': 'লগইন প্রয়োজন'}), 401


# ---------------------------------------------------------------- ডাটাবেজ তৈরি
with app.app_context():
    db.create_all()


# ---------------------------------------------------------------- হেল্পার
BACKUP_DIR = os.path.join(BASE, "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)


def backup_file(path, label="backup"):
    if not os.path.isfile(path):
        return None
    ts = time.strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(BACKUP_DIR, "%s.%s.%s" % (label, ts, os.path.basename(path)))
    try:
        shutil.copy2(path, dst)
        return dst
    except Exception:
        return None


def get_user_config(user_id, key, default=None):
    row = ConfigStore.query.filter_by(user_id=user_id, key=key).first()
    return row.value if row else default


def set_user_config(user_id, key, value):
    row = ConfigStore.query.filter_by(user_id=user_id, key=key).first()
    if row:
        row.value = value
    else:
        db.session.add(ConfigStore(user_id=user_id, key=key, value=value))
    db.session.commit()


# ---------------------------------------------------------------- ক্লাউড হেল্পার
def _user_sheet_tmp(sheet_id=None):
    """লগইন করা ইউজারের ডাটা শিটের DB বাইটস → টেম্প ফাইল।
    রিটার্ন (tmp_path, sheet_row) — কলার শেষে os.unlink করবে। Render-এ 'input output'
    ফোল্ডার নেই, তাই ইঞ্জিন সবসময় এই টেম্প ফাইল থেকেই পড়বে।
    বাছাই: নামে 'data sheet' আছে এমন সর্বশেষ শিট (লোকাল ইঞ্জিনের নিয়ম) —
    নইলে সর্বশেষ আপলোড; এতে টেমপ্লেট/অন্য ফাইল আপলোড করলেও ডাটা শিট হারায় না।"""
    q = DataSheet.query.filter_by(user_id=current_user.id)
    if sheet_id:
        sheet = q.filter_by(id=sheet_id).first()
    else:
        rows = q.order_by(DataSheet.created_at.desc(), DataSheet.id.desc()).all()
        sheet = next((s for s in rows
                      if 'data sheet' in (s.filename or '').lower()), None)
        if sheet is None and rows:
            sheet = rows[0]
    if not sheet or not sheet.file_bytes:
        return None, None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    tmp.write(sheet.file_bytes)
    tmp.close()
    return tmp.name, sheet


def _user_cfg(key):
    """ইউজারের DB-সেভ করা কনফিগ (ConfigStore) — না থাকলে বা ভাঙা হলে None।"""
    raw = get_user_config(current_user.id, key)
    if raw:
        try:
            v = json.loads(raw)
            if isinstance(v, dict):
                return v
        except Exception:
            pass
    return None


def _merged_cfg(user_key):
    """ইঞ্জিনের ফাইল-কনফিগের ওপর ইউজারের DB-কনফিগ বসায় — কনফিগ UI-র সেভ বিল্ডারে পৌঁছায়।"""
    cfg = G.load_cfg()
    u = _user_cfg(user_key)
    if u:
        for k in ('settings', 'company', 'providers'):
            if isinstance(u.get(k), dict):
                cfg[k] = u[k]
    return cfg


def _ci_cfg():
    """কোম্পানি-ইনভয়েস কনফিগ — নিজের ফাইল + ইউজারের DB-সেভ ওভারলে।"""
    cfg = C.load_ccfg()
    if not cfg.get('company'):
        cfg['company'] = G.load_cfg().get('company', {})
    u = _user_cfg('company_invoice_config')
    if u:
        for k in ('settings', 'company', 'providers'):
            if isinstance(u.get(k), dict):
                cfg[k] = u[k]
    return cfg


def _db_next_no(kind, client_name, month, year):
    """ইনভয়েস নম্বর DB থেকে — একই ইউজার+ধরন+মাসের (ঐচ্ছিকভাবে একই ক্লায়েন্ট) সংখ্যা+১।
    ক্লাউডে ইঞ্জিনের ফাইল-চেইন ephemeral, তাই ধারাবাহিক নম্বর এখান থেকেই আসে।"""
    q = Invoice.query.filter_by(user_id=current_user.id, kind=kind, month=month, year=year)
    if client_name:
        q = q.filter_by(client_name=client_name)
    return q.count() + 1


# ---------------------------------------------------------------- লগইন রেট-লিমিট (ইন-মেমরি, ছোট ও নির্ভরতা-মুক্ত)
_login_fails = {}
_login_lock = __import__('threading').Lock()
_MAX_FAILS, _LOCK_SECONDS = 5, 900


def _login_blocked(email):
    with _login_lock:
        f, t = _login_fails.get(email, (0, 0))
        if f >= _MAX_FAILS and time.time() - t < _LOCK_SECONDS:
            return True
        if f >= _MAX_FAILS:
            _login_fails.pop(email, None)
    return False


def _login_fail(email):
    with _login_lock:
        f, t = _login_fails.get(email, (0, 0))
        _login_fails[email] = (f + 1, time.time() if f + 1 >= _MAX_FAILS else t)


def _login_ok(email):
    with _login_lock:
        _login_fails.pop(email, None)


# ---------------------------------------------------------------- Auth/Lock রাউট (ফ্রন্টএন্ডের প্রত্যাশা অনুযায়ী)
@app.route('/api/lock/status', methods=['GET'], strict_slashes=False)
def lock_status():
    has = db.session.query(User).first() is not None
    return jsonify({'ok': True, 'has_users': has, 'authed': current_user.is_authenticated})


@app.route('/api/lock/verify', methods=['POST'], strict_slashes=False)
def lock_verify():
    d = request.get_json() or {}
    email = (d.get('id') or d.get('email') or '').strip().lower()
    pw = d.get('password') or ''
    if not email:
        return jsonify({'ok': False, 'error': 'ভুল আইডি বা পাসওয়ার্ড'}), 401
    if _login_blocked(email):
        return jsonify({'ok': False, 'error': 'অনেকবার ভুল চেষ্টা — ১৫ মিনিট পরে আবার করুন'}), 429
    u = User.query.filter_by(email=email).first()
    if u and u.check_password(pw):
        _login_ok(email)
        login_user(u)
        return jsonify({'ok': True, 'user': {'id': u.id, 'email': u.email, 'name': u.name, 'lang': u.lang}})
    _login_fail(email)
    return jsonify({'ok': False, 'error': 'ভুল আইডি বা পাসওয়ার্ড'}), 401


@app.route('/api/lock/register', methods=['POST'], strict_slashes=False)
def lock_register():
    d = request.get_json() or {}
    email = (d.get('id') or d.get('email') or '').strip().lower()
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
    login_user(u)
    return jsonify({'ok': True, 'user': {'id': u.id, 'email': u.email, 'name': u.name}})


@app.route('/api/lock/logout', methods=['POST'], strict_slashes=False)
@login_required
def lock_logout():
    logout_user()
    return jsonify({'ok': True})


@app.route('/api/lock/permanent', methods=['POST'], strict_slashes=False)
@login_required
def lock_permanent():
    return jsonify({'ok': True})


@app.route('/api/lock/passwd', methods=['POST'], strict_slashes=False)
@login_required
def lock_passwd():
    d = request.get_json() or {}
    pw = d.get('password') or ''
    if not pw:
        return jsonify({'ok': False, 'error': 'পাসওয়ার্ড প্রয়োজন'}), 400
    current_user.set_password(pw)
    db.session.commit()
    return jsonify({'ok': True})


#/auth আলাস
@app.route('/api/auth/login', methods=['POST'], strict_slashes=False)
def auth_login():
    return lock_verify()


@app.route('/api/auth/register', methods=['POST'], strict_slashes=False)
def auth_register():
    return lock_register()


@app.route('/api/auth/logout', methods=['POST'], strict_slashes=False)
def auth_logout():
    return lock_logout()


@app.route('/api/auth/me', methods=['GET'], strict_slashes=False)
def auth_me():
    if current_user.is_authenticated:
        return jsonify({'ok': True, 'user': {'id': current_user.id, 'email': current_user.email, 'name': current_user.name, 'lang': current_user.lang}})
    return jsonify({'ok': False, 'error': 'লগইন নেই'}), 401


# ---------------------------------------------------------------- ফাইল আপলোড (এক্সেল)
@app.route('/api/upload-excel', methods=['POST'], strict_slashes=False)
@login_required
def upload_excel():
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'ফাইল পাওয়া যায়নি'}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({'ok': False, 'error': 'ফাইল সিলেক্ট করেন'}), 400
    if not (f.filename.lower().endswith('.xlsx') or f.filename.lower().endswith('.xlsm')):
        return jsonify({'ok': False, 'error': 'শুধু .xlsx / .xlsm ফাইল গ্রহণযোগ্য'}), 400

    try:
        raw = f.read()
        ds = DataSheet(
            user_id=current_user.id,
            filename=f.filename,
            file_bytes=raw,
        )
        db.session.add(ds)
        db.session.commit()

        # মাস/সাল ডিটেক্ট — ফাইলনামের ৩-অক্ষর মাস (sep) আর ৪- বা ২-ডিজিট সাল (sep-2026 / sep-26)
        m, y = None, None
        mm = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', f.filename.lower())
        if mm:
            rev3 = {v[:3]: k for k, v in G.MONTHS.items()}
            m = rev3.get(mm.group(1).upper())
        yr = re.search(r'(\d{4})', f.filename)
        if yr:
            y = int(yr.group(1))
        else:
            # ২-ডিজিট সাল ("sep-26") — ২০-৯৯ পর্সন্তকেই ২০০০+ ধরা হয়, অন্য সংখ্যা নয়
            yr2 = re.search(r'(?:^|\D)([2-9]\d)(?:\D|$)', f.filename)
            if yr2:
                y = 2000 + int(yr2.group(1))
        ds.month = m
        ds.year = y
        db.session.commit()

        return jsonify({
            'ok': True,
            'file_id': ds.id,
            'filename': ds.filename,
            'month': m,
            'year': y,
            'message': 'ফাইল আপলোড সফল'
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


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
        lbl = "%02d-%d" % (s.month, s.year) if (s.month and s.year) else (s.filename or 'untitled')
        out.append({
            'folder': lbl,
            'label': lbl,
            'files': [{'name': s.filename, 'xlsx': True}],
            'size': len(s.data_json or ''),
            'month': s.month,
            'year': s.year,
            'id': s.id
        })
    return jsonify({'ok': True, 'months': out})


# ---------------------------------------------------------------- লেবার
@app.route('/api/ws/labor', methods=['GET'], strict_slashes=False)
@app.route('/api/ws/labor-refresh', methods=['GET'], strict_slashes=False)
@login_required
def labor():
    """Labor Running Duty — LaborDuty খাতা থাকলে সেখান থেকে (ক্লাউড-লেজার);
    না থাকলে পুরনো ফলব্যাক: ডাটা শিটের ওয়ার্কার + ম্যানুয়াল অ্যাসাইনমেন্ট।"""
    rows = LaborDuty.query.filter_by(user_id=current_user.id) \
        .order_by(LaborDuty.provider, LaborDuty.id).all()
    if rows:
        assigns = _labor_index_map(current_user.id)
        provs, order = {}, []
        for e in rows:
            p = e.provider or '(প্রোভাইডার নেই)'
            if p not in provs:
                provs[p] = {'provider': p, 'workers': [], 'onDuty': 0, 'off': 0}
                order.append(p)
            try:
                hist = json.loads(e.history or '[]')
            except Exception:
                hist = []
            b = provs[p]
            b['workers'].append({
                'name': e.person, 'provider': p, 'site': '' if e.off else (e.site or ''),
                'start': e.start or '', 'rate': e.rate, 'off': bool(e.off),
                'history': hist,
            })
        for p in order:
            b = provs[p]
            for w in b['workers']:
                mp = assigns.get(G.norm_person(w['name']))
                if mp and mp != p:
                    w['provider'] = mp
                    w['manual'] = True
            b['onDuty'] = sum(1 for w in b['workers'] if not w['off'])
            b['off'] = sum(1 for w in b['workers'] if w['off'])
        for bi, p in enumerate(order):
            for wi, w in enumerate(provs[p]['workers']):
                w['col'] = bi * 5 + 2
                w['row'] = 5 + wi
        return jsonify({'ok': True, 'providers': [provs[p] for p in order],
                        'file': 'ক্লাউড খাতা (ডেটাবেজ)', 'total': len(rows)})

    # ---- ফলব্যাক: LaborDuty খালি — ডাটা শিটের ওয়ার্কার থেকে ----
    fp = None
    try:
        fp, _sheet = _user_sheet_tmp()
        rows = []
        if fp:
            dm, dy = G.data_month_year(fp)
            rows = AI._all_workers(dm, dy, fp)
    finally:
        if fp:
            try:
                os.unlink(fp)
            except Exception:
                pass
    assigns = {a.person: a.provider for a in
               LaborAssign.query.filter_by(user_id=current_user.id).all()}
    providers = {}
    for w in rows:
        prov = assigns.get(w['name'], w['provider'])
        providers.setdefault(prov, []).append({
            'name': w['name'], 'hours': w['hours'], 'rate': w['rate'], 'provider': prov
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
    existing = LaborAssign.query.filter_by(user_id=current_user.id, person=person).first()
    if existing:
        existing.provider = provider
    else:
        db.session.add(LaborAssign(user_id=current_user.id, person=person, provider=provider))
    db.session.commit()
    return jsonify({'ok': True, 'person': person, 'provider': provider})


# ---------------------------------------------------------------- স্টেটমেন্ট প্রিভিউ (①)
@app.route('/api/ws/invoice-gen', methods=['GET'], strict_slashes=False)
@login_required
def invoice_gen_route():
    prov = (request.args.get('prov') or '').strip()
    month = int(request.args.get('month', 0) or 0)
    year = int(request.args.get('year', 0) or 0)
    adv = request.args.get('adv', '')
    gas = request.args.get('gas', '')
    rates_raw = request.args.get('rates', '')
    rates = {}
    if rates_raw:
        try:
            rates = json.loads(rates_raw)
            if not isinstance(rates, dict):
                rates = {}
        except Exception:
            rates = {}
    client = request.args.get('client', '') or None
    address = request.args.get('address', '') or None
    if not prov:
        return jsonify({'ok': False, 'error': 'প্রোভাইডার সিলেক্ট করুন'}), 400

    fp = None
    try:
        fp, _sheet = _user_sheet_tmp()
        if not fp:
            return jsonify({'ok': False, 'error': 'আগে ডাটা শিট আপলোড করুন'}), 400
        if not (month and year):
            dm, dy = G.data_month_year(fp)
            month, year = (month or dm), (year or dy)
        adv_people, adv_order = _db_advance_people()
        data = G.build_invoice(
            prov, month, year,
            rates=rates or None,
            adv=(adv if str(adv).strip() != '' else None),
            gas=(gas if str(gas).strip() != '' else None),
            client=client, address=address,
            fp=fp, assigned_no=_db_next_no('statement', None, month, year),
            cfg=_merged_cfg('invoice_config'),
            adv_people=adv_people, adv_order=adv_order
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        if fp:
            try:
                os.unlink(fp)
            except Exception:
                pass


# ---------------------------------------------------------------- স্টেটমেন্ট প্রোভাইডার লিস্ট
@app.route('/api/ws/invoice-gen-providers', methods=['GET'], strict_slashes=False)
@login_required
def invoice_gen_providers():
    fp = None
    try:
        fp, _sheet = _user_sheet_tmp()
        if not fp:
            return jsonify({'ok': False, 'error': 'আগে ডাটা শিট আপলোড করুন'}), 400
        ds_path, prov_workers, prov_order = G.read_data_sheet(fp=fp)
        dm, dy = G.data_month_year(fp)
        out = []
        cfg = _merged_cfg('invoice_config')
        for pn in prov_order:
            key = None
            for k, v in cfg.get('providers', {}).items():
                d = G.norm_person(v.get('display', ''))
                if d and d in G.norm_person(pn):
                    key = k
                    break
            if key is None:
                key = G.norm_person(pn).replace(' ', '.')
            out.append({
                'key': key,
                'data_name': pn,
                'display': cfg.get('providers', {}).get(key, {}).get('display', pn),
                'workers': len(prov_workers.get(pn, []))
            })
        return jsonify({
            'ok': True, 'providers': out,
            'data_month': dm, 'data_year': dy,
            'settings': cfg.get('settings', {}),
            'company': cfg.get('company', {}),
            'clients': cfg.get('providers', {})
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        if fp:
            try:
                os.unlink(fp)
            except Exception:
                pass


# ---------------------------------------------------------------- স্টেটমেন্ট সেভ (PDF)
@app.route('/api/ws/invoice-gen-save-one', methods=['POST'], strict_slashes=False)
@login_required
def invoice_gen_save_one():
    d = request.get_json() or {}
    prov = (d.get('prov') or '').strip()
    if not prov:
        return jsonify({'ok': False, 'error': 'প্রোভাইডার সিলেক্ট করুন'}), 400
    month = int(d.get('month') or 0) or None
    year = int(d.get('year') or 0) or None
    rates = d.get('rates') if isinstance(d.get('rates'), dict) else None
    adv = d.get('adv')
    gas = d.get('gas')

    fp = None
    try:
        fp, _sheet = _user_sheet_tmp()
        if not fp:
            return jsonify({'ok': False, 'error': 'আগে ডাটা শিট আপলোড করুন'}), 400
        if not (month and year):
            dm, dy = G.data_month_year(fp)
            month, year = (month or dm), (year or dy)
        adv_people, adv_order = _db_advance_people()
        data = G.build_invoice(
            prov, month, year,
            rates=rates, adv=adv, gas=gas,
            client=d.get('client'), address=d.get('address'),
            fp=fp, assigned_no=_db_next_no('statement', None, month, year),
            cfg=_merged_cfg('invoice_config'),
            adv_people=adv_people, adv_order=adv_order
        )
        # PDF তৈরি করে বাইটস DB-তে — ক্লাউড ডিস্ক ephemeral, ফাইল টেকে না
        pdf_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_tmp.close()
        G.make_pdf(data, pdf_tmp.name, kind='statement')
        with open(pdf_tmp.name, 'rb') as pf:
            pdf_bytes = pf.read()
        os.unlink(pdf_tmp.name)

        inv = Invoice(
            user_id=current_user.id,
            client_name=data.get('client', prov),
            client_address=data.get('address'),
            month=data.get('month', month),
            year=data.get('year', year),
            invoice_no=data.get('invoice_no', '01'),
            kind='statement',
            total=data.get('total', 0),
            net=data.get('net', 0),
            data_json=json.dumps(data, ensure_ascii=False),
            pdf_bytes=pdf_bytes
        )
        db.session.add(inv)
        db.session.commit()
        return jsonify({
            'ok': True,
            'file': "%s-%s.pdf" % (data['invoice_no'], G._safe_name(data['prov_display'])),
            'invoice_no': data['invoice_no'],
            'id': inv.id
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        if fp:
            try:
                os.unlink(fp)
            except Exception:
                pass


# ---------------------------------------------------------------- স্টেটমেন্ট সব সেভ (মাস ক্লায়ার সময়)
@app.route('/api/ws/invoice-gen-save-pdf', methods=['POST'], strict_slashes=False)
@login_required
def invoice_gen_save_pdf():
    d = request.get_json() or {}
    month = int(d.get('month') or 0)
    year = int(d.get('year') or 0)
    if not (month and year):
        now = time.localtime()
        month, year = now.tm_mon, now.tm_year

    fp = None
    try:
        fp, _sheet = _user_sheet_tmp()
        if not fp:
            return jsonify({'ok': False, 'error': 'আগে ডাটা শিট আপলোড করুন'}), 400
        cfg = _merged_cfg('invoice_config')
        adv_people, adv_order = _db_advance_people()
        prov_cfg_all = cfg.get('providers', {})
        ds_path, prov_workers, prov_order = G.read_data_sheet(fp=fp, month=month, year=year)
        if prov_workers and all(sum(w['hours'] for w in ws_list) == 0 for ws_list in prov_workers.values()):
            try:
                arc_path, arc_workers, arc_order = G.read_data_sheet(month=month, year=year, source='archive')
                if arc_workers:
                    ds_path, prov_workers, prov_order = arc_path, arc_workers, arc_order
            except Exception:
                pass

        done, errors, seen = [], [], set()
        for pn in prov_order:
            key = None
            for k, v in prov_cfg_all.items():
                dsp = G.norm_person(v.get('display', ''))
                if dsp and dsp in G.norm_person(pn):
                    key = k
                    break
            if key is None:
                key = G.norm_person(pn).replace(' ', '.')
            if key in seen:
                continue
            seen.add(key)
            pdf_tmp = None
            try:
                data = G.build_invoice(key, month, year, fp=fp,
                                       assigned_no=_db_next_no('statement', None, month, year),
                                       cfg=cfg, adv_people=adv_people, adv_order=adv_order)
                pdf_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                pdf_tmp.close()
                G.make_pdf(data, pdf_tmp.name, kind='statement')
                with open(pdf_tmp.name, 'rb') as pf:
                    pdf_bytes = pf.read()
                fname = "%02d-%s.pdf" % (int(data['invoice_no']), G._safe_name(data['prov_display']))
                inv = Invoice(
                    user_id=current_user.id,
                    client_name=data.get('client', key),
                    client_address=data.get('address'),
                    month=month, year=year,
                    invoice_no=data['invoice_no'],
                    kind='statement',
                    total=data.get('total', 0),
                    net=data.get('net', 0),
                    data_json=json.dumps(data, ensure_ascii=False),
                    pdf_bytes=pdf_bytes
                )
                db.session.add(inv)
                db.session.commit()
                done.append(fname)
            except Exception as e:
                errors.append("%s: %s" % (key, e))
            finally:
                if pdf_tmp:
                    try:
                        os.unlink(pdf_tmp.name)
                    except Exception:
                        pass
        return jsonify({'ok': True, 'saved': done, 'count': len(done), 'errors': errors})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        if fp:
            try:
                os.unlink(fp)
            except Exception:
                pass


# ---------------------------------------------------------------- ③ Add Invoice প্রিভিউ
@app.route('/api/ws/add-invoice', methods=['GET'], strict_slashes=False)
@login_required
def add_invoice_preview():
    client_key = (request.args.get('client_key') or '').strip()
    client_name = (request.args.get('client_name') or client_key).strip()
    client_address = (request.args.get('client_address') or '').strip()
    month = int(request.args.get('month', 0) or 0)
    year = int(request.args.get('year', 0) or 0)
    rates_raw = request.args.get('rates', '{}')
    rates = {}
    if rates_raw:
        try:
            rates = json.loads(rates_raw)
            if not isinstance(rates, dict):
                rates = {}
        except Exception:
            rates = {}
    if not client_key:
        return jsonify({'ok': False, 'error': 'কোম্পানি/সাইটের নাম দিন'}), 400

    fp = None
    try:
        fp, _sheet = _user_sheet_tmp()
        if not fp:
            return jsonify({'ok': False, 'error': 'আগে ডাটা শিট আপলোড করুন'}), 400
        if not (month and year):
            dm, dy = G.data_month_year(fp)
            month, year = (month or dm), (year or dy)
        data = AI.build_add_invoice(
            client_key, client_name, client_address, month, year, rates,
            fp=fp, assigned_no=_db_next_no('add_invoice', client_name, month, year),
            cfg=_merged_cfg('add_invoice_config')
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        if fp:
            try:
                os.unlink(fp)
            except Exception:
                pass


# ---------------------------------------------------------------- ③ Add Invoice ওয়ার্কার লিস্ট
@app.route('/api/ws/add-invoice-providers', methods=['GET'], strict_slashes=False)
@login_required
def add_invoice_providers():
    fp = None
    try:
        fp, _sheet = _user_sheet_tmp()
        if not fp:
            return jsonify({'ok': False, 'error': 'আগে ডাটা শিট আপলোড করুন'}), 400
        month = int(request.args.get('month', 0) or 0)
        year = int(request.args.get('year', 0) or 0)
        dm, dy = G.data_month_year(fp)
        m = int(month) if month else dm
        y = int(year) if year else dy
        all_workers = AI._all_workers(m, y, fp)
        seen, distinct = set(), []
        for w in all_workers:
            key = w['name'].strip().lower()
            if key not in seen:
                seen.add(key)
                distinct.append({
                    'name': w['name'], 'hours': w['hours'],
                    'rate': w['rate'], 'provider': w['provider']
                })
        return jsonify({
            'ok': True, 'workers': distinct,
            'data_month': m, 'data_year': y,
            'month_name': G.MONTHS.get(m, ''),
            'month_names': G.MONTHS
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        if fp:
            try:
                os.unlink(fp)
            except Exception:
                pass


# ---------------------------------------------------------------- ③ Add Invoice সেভ
@app.route('/api/ws/add-invoice-save-one', methods=['POST'], strict_slashes=False)
@login_required
def add_invoice_save():
    d = request.get_json() or {}
    client_key = (d.get('client_key') or '').strip()
    client_name = (d.get('client_name') or client_key).strip()
    client_address = d.get('client_address') or ''
    month = int(d.get('month') or 0) or None
    year = int(d.get('year') or 0) or None
    rates = d.get('rates') if isinstance(d.get('rates'), dict) else {}

    if not client_key:
        return jsonify({'ok': False, 'error': 'কোম্পানি/সাইটের নাম দিন'}), 400

    fp = None
    try:
        fp, _sheet = _user_sheet_tmp()
        if not fp:
            return jsonify({'ok': False, 'error': 'আগে ডাটা শিট আপলোড করুন'}), 400
        if not (month and year):
            dm, dy = G.data_month_year(fp)
            month, year = (month or dm), (year or dy)
        data, out_dir, fname = AI.save_add_invoice_pdf(
            client_key, client_name, client_address, month, year, rates,
            fp=fp, assigned_no=_db_next_no('add_invoice', client_name, month, year),
            cfg=_merged_cfg('add_invoice_config')
        )
        # তৈরি হওয়া PDF ফাইলটা DB-তে নিই — Render-এর ডিস্ক ephemeral
        pdf_bytes = None
        try:
            with open(os.path.join(out_dir, fname), 'rb') as pf:
                pdf_bytes = pf.read()
            os.unlink(os.path.join(out_dir, fname))
        except Exception:
            pdf_bytes = None

        inv = Invoice(
            user_id=current_user.id,
            client_name=client_name,
            client_address=client_address,
            month=data.get('month', month),
            year=data.get('year', year),
            invoice_no=data['invoice_no'],
            kind='add_invoice',
            total=data.get('total', 0),
            net=data.get('net', 0),
            data_json=json.dumps(data, ensure_ascii=False),
            pdf_bytes=pdf_bytes
        )
        db.session.add(inv)
        db.session.commit()
        return jsonify({
            'ok': True, 'file': fname, 'dir': out_dir,
            'invoice_no': data['invoice_no'], 'id': inv.id
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        if fp:
            try:
                os.unlink(fp)
            except Exception:
                pass


# ---------------------------------------------------------------- ইনভয়েস PDF ডাউনলোড
@app.route('/api/invoices', methods=['GET'], strict_slashes=False)
@login_required
def invoices_list():
    rows = (Invoice.query
            .filter_by(user_id=current_user.id)
            .order_by(Invoice.created_at.desc())
            .all())
    return jsonify({'ok': True, 'invoices': [{
        'id': r.id, 'client_name': r.client_name, 'kind': r.kind,
        'month': r.month, 'year': r.year, 'invoice_no': r.invoice_no,
        'total': r.total, 'net': r.net, 'has_pdf': bool(r.pdf_bytes),
        'created_at': r.created_at.isoformat() if r.created_at else None,
    } for r in rows]})


@app.route('/api/invoices/<int:inv_id>/pdf', methods=['GET'], strict_slashes=False)
@login_required
def invoice_pdf(inv_id):
    inv = Invoice.query.filter_by(id=inv_id, user_id=current_user.id).first()
    if not inv or not inv.pdf_bytes:
        return jsonify({'ok': False, 'error': 'PDF পাওয়া যায়নি'}), 404
    from flask import Response
    return Response(inv.pdf_bytes, mimetype='application/pdf', headers={
        'Content-Disposition': 'inline; filename="%s.pdf"' % (
            G._safe_name("%s-%s" % (inv.invoice_no, inv.client_name)) or 'invoice')
    })


# ---------------------------------------------------------------- ② কোম্পানি ইনভয়েস (Company Invoice)
@app.route('/api/ws/company-invoice-providers', methods=['GET'], strict_slashes=False)
@login_required
def company_invoice_providers():
    fp = None
    try:
        fp, _sheet = _user_sheet_tmp()
        if not fp:
            return jsonify({'ok': False, 'error': 'আগে ডাটা শিট আপলোড করুন'}), 400
        _p, prov_workers, prov_order = G.read_data_sheet(fp=fp)
        dm, dy = G.data_month_year(fp)
        ccfg = _ci_cfg()
        out = []
        for pn in prov_order:
            key = None
            for k, v in ccfg.get('providers', {}).items():
                dsp = G.norm_person(v.get('display', ''))
                if dsp and dsp in G.norm_person(pn):
                    key = k
                    break
            if key is None:
                key = G.norm_person(pn).replace(' ', '.')
            pc = ccfg.get('providers', {}).get(key, {})
            out.append({'key': key, 'data_name': pn,
                        'display': pc.get('display', pn),
                        'client': pc.get('client', ''),
                        'client_rate': pc.get('client_rate', 0),
                        'workers': len(prov_workers.get(pn, []))})
        return jsonify({'ok': True, 'providers': out,
                        'data_month': dm, 'data_year': dy,
                        'settings': ccfg.get('settings', {}),
                        'company': ccfg.get('company', {}),
                        'clients': ccfg.get('providers', {})})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        if fp:
            try:
                os.unlink(fp)
            except Exception:
                pass


@app.route('/api/ws/company-invoice', methods=['GET'], strict_slashes=False)
@login_required
def company_invoice_route():
    prov = (request.args.get('prov') or '').strip()
    if not prov:
        return jsonify({'ok': False, 'error': 'প্রোভাইডার সিলেক্ট করুন'}), 400
    month = int(request.args.get('month', 0) or 0)
    year = int(request.args.get('year', 0) or 0)
    rates_raw = request.args.get('rates', '')
    rates = None
    if rates_raw:
        try:
            v = json.loads(rates_raw)
            if isinstance(v, dict):
                rates = v
        except Exception:
            rates = None

    fp = None
    try:
        fp, _sheet = _user_sheet_tmp()
        if not fp:
            return jsonify({'ok': False, 'error': 'আগে ডাটা শিট আপলোড করুন'}), 400
        if not (month and year):
            dm, dy = G.data_month_year(fp)
            month, year = (month or dm), (year or dy)
        data = C.build_company_invoice(
            prov, month, year, rates=rates,
            fp=fp, assigned_no=_db_next_no('company_invoice', None, month, year),
            cfg=_ci_cfg()
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        if fp:
            try:
                os.unlink(fp)
            except Exception:
                pass


@app.route('/api/ws/company-invoice-save-one', methods=['POST'], strict_slashes=False)
@login_required
def company_invoice_save_one():
    d = request.get_json() or {}
    prov = (d.get('prov') or '').strip()
    if not prov:
        return jsonify({'ok': False, 'error': 'প্রোভাইডার সিলেক্ট করুন'}), 400
    month = int(d.get('month') or 0) or None
    year = int(d.get('year') or 0) or None
    rates = d.get('rates') if isinstance(d.get('rates'), dict) else None

    fp = None
    try:
        fp, _sheet = _user_sheet_tmp()
        if not fp:
            return jsonify({'ok': False, 'error': 'আগে ডাটা শিট আপলোড করুন'}), 400
        if not (month and year):
            dm, dy = G.data_month_year(fp)
            month, year = (month or dm), (year or dy)
        data = C.build_company_invoice(
            prov, month, year, rates=rates,
            fp=fp, assigned_no=_db_next_no('company_invoice', None, month, year),
            cfg=_ci_cfg()
        )
        pdf_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_tmp.close()
        G.make_pdf(data, pdf_tmp.name, kind='invoice')
        with open(pdf_tmp.name, 'rb') as pf:
            pdf_bytes = pf.read()
        os.unlink(pdf_tmp.name)

        inv = Invoice(
            user_id=current_user.id,
            client_name=data.get('client', prov),
            client_address=data.get('address'),
            month=month, year=year,
            invoice_no=data['invoice_no'],
            kind='company_invoice',
            total=data.get('total', 0),
            net=data.get('net', 0),
            data_json=json.dumps(data, ensure_ascii=False),
            pdf_bytes=pdf_bytes
        )
        db.session.add(inv)
        db.session.commit()
        return jsonify({
            'ok': True,
            'file': "%s-%s.pdf" % (data['invoice_no'], G._safe_name(data['client'] or data['prov_display'])),
            'invoice_no': data['invoice_no'],
            'id': inv.id
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        if fp:
            try:
                os.unlink(fp)
            except Exception:
                pass


@app.route('/api/ws/company-invoice-config', methods=['POST'], strict_slashes=False)
@login_required
def company_invoice_config():
    d = request.get_json() or {}
    try:
        set_user_config(current_user.id, 'company_invoice_config', json.dumps(d, ensure_ascii=False))
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ---------------------------------------------------------------- ফোন নম্বর (WhatsApp ট্যাব)
@app.route('/api/ws/phones', methods=['GET'], strict_slashes=False)
@login_required
def phones_get():
    try:
        phones = json.loads(get_user_config(current_user.id, 'phones', '{}') or '{}')
    except Exception:
        phones = {}
    return jsonify({'ok': True, 'phones': phones if isinstance(phones, dict) else {}})


@app.route('/api/ws/phones', methods=['POST'], strict_slashes=False)
@login_required
def phones_set():
    d = request.get_json() or {}
    person = (d.get('person') or '').strip()
    if not person:
        return jsonify({'ok': False, 'error': 'নাম প্রয়োজন'}), 400
    try:
        phones = json.loads(get_user_config(current_user.id, 'phones', '{}') or '{}')
    except Exception:
        phones = {}
    if not isinstance(phones, dict):
        phones = {}
    val = str(d.get('set') or d.get('number') or '').strip()
    if val:
        phones[person] = val
    else:
        phones.pop(person, None)
    set_user_config(current_user.id, 'phones', json.dumps(phones, ensure_ascii=False))
    return jsonify({'ok': True, 'phones': phones})


# ---------------------------------------------------------------- ইনকাম/বাবছায়ের খাতা (লোকাল invoice_data.json-এর ক্লাউড রূপ)
def _inv_rows():
    try:
        rows = json.loads(get_user_config(current_user.id, 'invoice_data', '[]') or '[]')
    except Exception:
        rows = []
    return rows if isinstance(rows, list) else []


@app.route('/api/ws/invoice', methods=['GET'], strict_slashes=False)
@login_required
def invoice_rows():
    rows = _inv_rows()
    total_in = sum(float(r.get('amount') or 0) for r in rows if r.get('dir') != 'out')
    total_out = sum(float(r.get('amount') or 0) for r in rows if r.get('dir') == 'out')
    return jsonify({'ok': True, 'entries': rows,
                    'totalIn': round(total_in, 2), 'totalOut': round(total_out, 2),
                    'balance': round(total_in - total_out, 2)})


@app.route('/api/ws/invoice-add', methods=['POST'], strict_slashes=False)
@login_required
def invoice_add():
    d = request.get_json() or {}
    try:
        amt = float(d.get('amount') or 0)
    except (TypeError, ValueError):
        amt = 0.0
    if not amt:
        return jsonify({'ok': False, 'error': 'সঠিক পরিমাণ দিন'}), 400
    rows = _inv_rows()
    rows.append({'amount': amt, 'date': d.get('date') or '',
                 'dir': d.get('dir') or 'in', 'desc': d.get('desc') or ''})
    set_user_config(current_user.id, 'invoice_data', json.dumps(rows, ensure_ascii=False))
    return jsonify({'ok': True, 'count': len(rows)})


@app.route('/api/ws/invoice-remove', methods=['POST'], strict_slashes=False)
@login_required
def invoice_remove():
    d = request.get_json() or {}
    try:
        idx = int(d.get('index'))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'সঠিক সারি নয়'}), 400
    rows = _inv_rows()
    if 0 <= idx < len(rows):
        rows.pop(idx)
        set_user_config(current_user.id, 'invoice_data', json.dumps(rows, ensure_ascii=False))
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'সারি পাওয়া যায়নি'}), 404


# ---------------------------------------------------------------- কর্মচারী তালিকা (ডাটা শিটের ওয়ার্কার)
@app.route('/api/ws/employees', methods=['GET'], strict_slashes=False)
@login_required
def employees():
    fp = None
    try:
        fp, _sheet = _user_sheet_tmp()
        workers = []
        if fp:
            dm, dy = G.data_month_year(fp)
            workers = AI._all_workers(dm, dy, fp)
    finally:
        if fp:
            try:
                os.unlink(fp)
            except Exception:
                pass
    seen, emps = set(), []
    for w in workers:
        key = w['name'].strip().lower()
        if key and key not in seen:
            seen.add(key)
            emps.append({'name': w['name'], 'provider': w['provider'],
                         'files': 0, 'size': 0})
    return jsonify({'ok': True, 'employees': emps})


@app.route('/api/ws/employee-files', methods=['GET'], strict_slashes=False)
@login_required
def employee_files():
    # ক্লাউডে OneDrive/ড্রাইভ ফোল্ডার নেই — প্রতি-কর্মচারীর ডকুমেন্ট ফাইল এখনো নেই
    return jsonify({'ok': True, 'files': []})


# ---------------------------------------------------------------- অগ্রিম/বেতন খাতা (Advance/Salary)
def _status_cleared(s):
    s = (s or '').lower()
    return ('paid' in s) or ('clear' in s)


def _advance_rows(user_id):
    """ইউজারের সব অগ্রিম-এন্ট্রি, স্থিতিশীল ক্রমে (পুরনো আগে) — UI-র index এর সাথে মেলে।"""
    return (AdvanceEntry.query.filter_by(user_id=user_id)
            .order_by(AdvanceEntry.created_at, AdvanceEntry.id).all())


def _db_advance_people():
    """ডেটাবেজ-লেজার → ইঞ্জিনের read_advance()-আকৃতির (people, order) — স্টেটমেন্টে বাদ-যোগের জন্য।"""
    people, order = {}, []
    for e in _advance_rows(current_user.id):
        key = G.norm_person(e.person)
        if not key:
            continue
        if key not in people:
            people[key] = {'name': re.sub(r'\s*\(.*', '', e.person).strip(),
                           'total': 0.0, 'paid': 0.0, 'balance': 0.0}
            order.append(key)
        amt = e.amount or 0.0
        people[key]['total'] += amt
        if _status_cleared(e.status):
            people[key]['paid'] += amt
        else:
            people[key]['balance'] += amt
    return people, order


def _labor_provider_map():
    """অগ্রিম-খাতার প্রোভাইডার-ম্যাপিং: LaborDuty আগে, ম্যানুয়াল LaborAssign জিতে যায়।"""
    return _labor_index_map(current_user.id)


@app.route('/api/ws/advance', methods=['GET'], strict_slashes=False)
@login_required
def advance_get():
    rows = _advance_rows(current_user.id)
    people, order = {}, []
    for e in rows:
        key = G.norm_person(e.person)
        if not key:
            continue
        if key not in people:
            people[key] = {'name': re.sub(r'\s*\(.*', '', e.person).strip(),
                           'entries': [], 'paid': 0.0, 'balance': 0.0, 'total': 0.0}
            order.append(key)
        p = people[key]
        p['entries'].append({'amount': e.amount or 0.0, 'date': e.date or '',
                             'status': e.status or '', 'reason': e.reason or ''})
        amt = e.amount or 0.0
        p['total'] += amt
        if _status_cleared(e.status):
            p['paid'] += amt
        else:
            p['balance'] += amt
    assigns = _labor_provider_map()
    for key in order:
        b = people[key]
        b['provider'] = assigns.get(G.norm_person(b['name']))
        b['labor'] = b['name']
        b['site'] = ''
        b['dutyStart'] = ''
        b['rate'] = None
        b['dutyOff'] = False
    grand = sum(people[k]['total'] for k in order)
    return jsonify({'ok': True, 'people': [people[k] for k in order],
                    'grand': grand, 'count': len(order)})


@app.route('/api/ws/advance-add', methods=['POST'], strict_slashes=False)
@login_required
def advance_add():
    d = request.get_json() or {}
    person = ' '.join(str(d.get('person') or '').split())
    if not person:
        return jsonify({'ok': False, 'error': 'নাম দিন'}), 400
    try:
        amt = float(str(d.get('amount') or '').replace(',', '').strip())
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'সঠিক টাকা লিখুন'}), 400
    if amt <= 0:
        return jsonify({'ok': False, 'error': 'সঠিক টাকা লিখুন'}), 400
    existing = any(G.norm_person(e.person) == G.norm_person(person)
                   for e in _advance_rows(current_user.id))
    new_person = not existing
    db.session.add(AdvanceEntry(
        user_id=current_user.id, person=person, amount=amt,
        status='Paide' if d.get('paid') else '',
        date=str(d.get('date') or '').strip()[:20],
        reason=' '.join(str(d.get('reason') or '').split())[:500],
    ))
    prov = str(d.get('provider') or '').strip()
    if new_person and prov and prov != '__none__':
        has = LaborAssign.query.filter_by(user_id=current_user.id, person=person).first()
        if not has:
            db.session.add(LaborAssign(user_id=current_user.id, person=person, provider=prov))
    db.session.commit()
    return jsonify({'ok': True, 'backup': 'ডেটাবেজ (স্থায়ী)', 'newPerson': new_person})


@app.route('/api/ws/advance-paid', methods=['POST'], strict_slashes=False)
@login_required
def advance_paid():
    d = request.get_json() or {}
    person = str(d.get('person') or '')
    try:
        idx = int(d.get('index'))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'সঠিক সারি নয়'}), 400
    rows = [e for e in _advance_rows(current_user.id)
            if G.norm_person(e.person) == G.norm_person(person)]
    if idx < 0 or idx >= len(rows):
        return jsonify({'ok': False, 'error': 'সারি পাওয়া যায়নি'}), 404
    rows[idx].status = 'Paide'
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/ws/advance-remove', methods=['POST'], strict_slashes=False)
@login_required
def advance_remove():
    d = request.get_json() or {}
    person = str(d.get('person') or '')
    try:
        idx = int(d.get('index'))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'সঠিক সারি নয়'}), 400
    rows = [e for e in _advance_rows(current_user.id)
            if G.norm_person(e.person) == G.norm_person(person)]
    if idx < 0 or idx >= len(rows):
        return jsonify({'ok': False, 'error': 'সারি পাওয়া যায়নি'}), 404
    db.session.delete(rows[idx])
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/ws/advance-import', methods=['POST'], strict_slashes=False)
@login_required
def advance_import():
    f = request.files.get('file')
    if not f or not (f.filename or '').lower().endswith(('.xlsx', '.xlsm')):
        return jsonify({'ok': False, 'error': '.xlsx ফাইল দিন'}), 400
    replace = request.form.get('replace') == '1'
    from openpyxl import load_workbook
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    tmp.write(f.read())
    tmp.close()
    try:
        wb = load_workbook(tmp.name, data_only=True)
        ws = wb[wb.sheetnames[0]]
        blocks = []
        for c in range(1, (ws.max_column or 0) + 1):
            if ' '.join(str(ws.cell(4, c).value or '').split()).lower() == 'name':
                blocks.append((c, c + 1, c + 2, c + 3, c + 4))
        if not blocks:
            return jsonify({'ok': False,
                            'error': 'শিটের ৪ নম্বর সারিতে "Name" হেডার পাওয়া যায়নি — আপনার বট-শিট কি এটা?'}), 400
        if replace:
            AdvanceEntry.query.filter_by(user_id=current_user.id).delete()
        imported, seen_people = 0, set()
        for (_nc, _ac, _dc, _sc, _rc) in blocks:
            for r in range(5, (ws.max_row or 0) + 1):
                name = ' '.join(str(ws.cell(r, _nc).value or '').split())
                if not name:
                    continue
                low = name.lower()
                if low.startswith('total') or low.startswith('grand balance'):
                    continue
                try:
                    amt = float(str(ws.cell(r, _ac).value or '').replace(',', '') or 0)
                except (TypeError, ValueError):
                    amt = 0.0
                dtv = ws.cell(r, _dc).value
                if hasattr(dtv, 'strftime'):
                    dtv = dtv.date().isoformat()
                else:
                    dtv = str(dtv or '').strip()[:20]
                st = ' '.join(str(ws.cell(r, _sc).value or '').split())
                rs = ' '.join(str(ws.cell(r, _rc).value or '').split())[:500]
                db.session.add(AdvanceEntry(user_id=current_user.id, person=name,
                                            amount=amt, status=st, date=dtv, reason=rs))
                imported += 1
                seen_people.add(G.norm_person(name))
        db.session.commit()
        return jsonify({'ok': True, 'imported': imported, 'people': len(seen_people)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


@app.route('/api/ws/advance-export', methods=['GET'], strict_slashes=False)
@login_required
def advance_export():
    """'Advance sheet ক্লাউড.xlsx' — ডেটাবেজ-খাতার Excel প্রতিবিম্ব (ব্যাকআপ/দেখার জন্য)।"""
    from openpyxl import Workbook
    from io import BytesIO
    from flask import Response
    rows = _advance_rows(current_user.id)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Advance'
    ws.append(['Name', 'Amount', 'Date', 'Status', 'Reason'])
    grand = 0.0
    for e in rows:
        ws.append([e.person, e.amount or 0.0, e.date or '', e.status or '', e.reason or ''])
        grand += e.amount or 0.0
    ws.append([])
    ws.append(['GRAND TOTAL', grand])
    buf = BytesIO()
    wb.save(buf)
    from urllib.parse import quote
    fname = 'Advance sheet ক্লাউড.xlsx'
    return Response(buf.getvalue(),
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition':
                             "attachment; filename=\"advance-sheet-cloud.xlsx\"; "
                             "filename*=UTF-8''" + quote(fname)})


# ---------------------------------------------------------------- লেবার/ডিউটি (Labor Running Duty)
DUTY_OFF_WORDS = ("duty off", "end", "off", "duty end")


def _labor_index_map(user_id):
    """person-normkey → provider: LaborDuty আগে, তারপর ম্যানুয়াল LaborAssign (জিতে যায়)।"""
    idx = {}
    for e in LaborDuty.query.filter_by(user_id=user_id).all():
        k = G.norm_person(e.person)
        if k and e.provider:
            idx.setdefault(k, e.provider)
    for a in LaborAssign.query.filter_by(user_id=user_id).all():
        k = G.norm_person(a.person)
        if k and a.provider:
            idx[k] = a.provider
    return idx


@app.route('/api/ws/labor-import', methods=['POST'], strict_slashes=False)
@login_required
def labor_import():
    """'working in company Manpower 2 বট.xlsx' ইমপোর্ট — প্রোভাইডার-ব্লক (row-2 নাম, row-4
    'name' হেডার), ডিউটি-হিস্ট্রি ঘরের কমেন্ট থেকে। replace=1 দিলে আগের খাতা মুছে নতুন করে।"""
    f = request.files.get('file')
    if not f or not (f.filename or '').lower().endswith(('.xlsx', '.xlsm')):
        return jsonify({'ok': False, 'error': '.xlsx ফাইল দিন'}), 400
    replace = request.form.get('replace') == '1'
    from openpyxl import load_workbook
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    tmp.write(f.read())
    tmp.close()
    try:
        wb = load_workbook(tmp.name, data_only=True)
        if replace:
            # নতুন ইনসার্টের আগেই পুরনো খাতা মুছতে হবে — নইলে replace-এ সব মুছে যায়
            LaborDuty.query.filter_by(user_id=current_user.id).delete()
            db.session.commit()
        imported, prov_order, provs = 0, [], {}
        for ws in wb.worksheets:
            for c in range(1, (ws.max_column or 0) + 1):
                if ' '.join(str(ws.cell(4, c).value or '').split()).lower() != 'name':
                    continue
                prov = ' '.join(str(ws.cell(2, c).value or '').split()) or '(প্রোভাইডারের নাম লেখা নেই)'
                if prov not in provs:
                    provs[prov] = True
                    prov_order.append(prov)

                for r in range(5, (ws.max_row or 0) + 1):
                    name = ' '.join(str(ws.cell(r, c).value or '').split())
                    if not name:
                        continue
                    low = name.lower()
                    if low.startswith('total') or low.startswith('grand balance'):
                        continue

                    def _cmt(rr, cc):
                        try:
                            cm = ws.cell(rr, cc).comment
                        except Exception:
                            return ''
                        if cm and cm.text and cm.text.strip():
                            return ' '.join(cm.text.split())
                        return ''

                    hist = []
                    for t in (_cmt(r, c), _cmt(r, c + 1), _cmt(r, c + 3)):
                        if t and t not in hist:
                            hist.append(t)
                    site = ' '.join(str(ws.cell(r, c + 3).value or '').split())
                    off = bool(site) and site.lower() in DUTY_OFF_WORDS
                    try:
                        rate = float(ws.cell(r, c + 2).value) if ws.cell(r, c + 2).value not in (None, '') else None
                    except (TypeError, ValueError):
                        rate = None
                    stv = ws.cell(r, c + 1).value
                    start = stv.strftime('%Y-%m-%d') if hasattr(stv, 'strftime') \
                        else ' '.join(str(stv or '').split())[:20]
                    db.session.add(LaborDuty(user_id=current_user.id, person=name, provider=prov,
                                             site='' if off else site, start=start, rate=rate,
                                             off=off, history=json.dumps(hist, ensure_ascii=False)))
                    imported += 1
        db.session.commit()
        return jsonify({'ok': True, 'imported': imported, 'providers': len(prov_order)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


@app.route('/api/ws/labor-save', methods=['POST'], strict_slashes=False)
@login_required
def labor_save():
    d = request.get_json() or {}
    act = str(d.get('act') or 'add')
    vals = d.get('values') if isinstance(d.get('values'), dict) else d
    person = ' '.join(str(vals.get('name') or vals.get('person') or '').split())
    provider = ' '.join(str(vals.get('provider') or d.get('provider') or '').split())
    site = ' '.join(str(vals.get('site') or '').split())
    start = str(vals.get('start') or '').strip()[:20]
    try:
        rate = float(str(vals.get('rate') or '').replace(',', '')) if vals.get('rate') not in (None, '') else None
    except (TypeError, ValueError):
        rate = None
    off = bool(site) and site.lower() in DUTY_OFF_WORDS

    rows = LaborDuty.query.filter_by(user_id=current_user.id).all()
    row = next((e for e in rows if G.norm_person(e.person) == G.norm_person(person)), None) if person else None

    if act == 'comment':
        cmt = ' '.join(str(d.get('comment') or d.get('siteComment') or '').split())
        if row and cmt:
            try:
                hist = json.loads(row.history or '[]')
            except Exception:
                hist = []
            if cmt not in hist:
                hist.append(cmt)
                row.history = json.dumps(hist, ensure_ascii=False)
                db.session.commit()
        return jsonify({'ok': True})

    if act == 'del':
        if row:
            db.session.delete(row)
            db.session.commit()
        return jsonify({'ok': True})

    if act in ('end', 'off'):
        if row:
            row.off = True
            row.site = ''
            db.session.commit()
        return jsonify({'ok': True})

    if not person:
        return jsonify({'ok': False, 'error': 'নাম দিন'}), 400

    if act == 'edit' and row:
        row.site = '' if off else site
        row.off = off
        if start:
            row.start = start
        if rate is not None:
            row.rate = rate
        if provider:
            row.provider = provider
    else:
        db.session.add(LaborDuty(user_id=current_user.id, person=person, provider=provider,
                                 site='' if off else site, start=start, rate=rate, off=off))
    for cmt in (str(d.get('comment') or '').strip(), str(d.get('siteComment') or '').strip()):
        if row and cmt:
            try:
                hist = json.loads(row.history or '[]')
            except Exception:
                hist = []
            if cmt not in hist:
                hist.append(cmt)
                row.history = json.dumps(hist, ensure_ascii=False)
    db.session.commit()
    return jsonify({'ok': True})


# ---------------------------------------------------------------- মাস-আর্কাইভ (হিস্ট্রি)
@app.route('/api/archives', methods=['GET'], strict_slashes=False)
@login_required
def archives_list():
    rows = (MonthArchive.query.filter_by(user_id=current_user.id)
            .order_by(MonthArchive.year, MonthArchive.month, MonthArchive.created_at)
            .all())
    return jsonify({'ok': True, 'archives': [{
        'id': r.id, 'month': r.month, 'year': r.year, 'kind': r.kind,
        'filename': r.filename, 'size': len(r.file_bytes or b''),
        'created_at': r.created_at.isoformat() if r.created_at else None,
    } for r in rows]})


@app.route('/api/archives/<int:arc_id>/download', methods=['GET'], strict_slashes=False)
@login_required
def archives_download(arc_id):
    arc = MonthArchive.query.filter_by(id=arc_id, user_id=current_user.id).first()
    if not arc or not arc.file_bytes:
        return jsonify({'ok': False, 'error': 'ফাইল পাওয়া যায়নি'}), 404
    from urllib.parse import quote
    from flask import Response
    safe = (arc.filename or 'file').replace('"', '')
    return Response(arc.file_bytes,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition':
                             "attachment; filename=\"archive-%d-%02d.xlsx\"; filename*=UTF-8''%s"
                             % (arc.year, arc.month, quote(safe))})


# ---------------------------------------------------------------- ফুল ব্যাকআপ (ZIP ডাউনলোড)
@app.route('/api/backup', methods=['GET'], strict_slashes=False)
@login_required
def backup_download():
    """আপনার অ্যাকাউন্টের পুরো ডেটার ZIP — শিট, ইনভয়েস+PDF, মাস-আর্কাইভ,
    অগ্রিম-খাতা (JSON + ক্লাউড-শিট xlsx), কনফিগ। পিসি-স্ক্রিপ্ট প্রতিদিন এটাই নামিয়ে OneDrive-এ রাখে।"""
    import io
    import zipfile as _zf
    buf = io.BytesIO()
    counts = {'sheets': 0, 'invoices': 0, 'archives': 0, 'advance': 0, 'config': 0}
    with _zf.ZipFile(buf, 'w', _zf.ZIP_DEFLATED) as z:
        used = set()

        def _zname(folder, name, default):
            base = re.sub(r'[\\/:*?"<>|]+', '_', str(name or default)).strip() or default
            cand, n = '%s/%s' % (folder, base), 1
            while cand in used:
                root, ext = os.path.splitext(base)
                cand = '%s/%s-%d%s' % (folder, root, n, ext or '.bin')
                n += 1
            used.add(cand)
            return cand

        # ১. আপলোড করা সব শিট (ডাটা শিট + টেমপ্লেট)
        for s in DataSheet.query.filter_by(user_id=current_user.id).all():
            if s.file_bytes:
                z.writestr(_zname('data_sheets', s.filename, 'sheet-%d.xlsx' % s.id), s.file_bytes)
                counts['sheets'] += 1

        # ২. ইনভয়েস/স্টেটমেন্ট — PDF + পুরো ডেটা
        inv_meta = []
        for inv in Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.id).all():
            if inv.pdf_bytes:
                z.writestr(_zname('invoices', '%s-%s.pdf' % (inv.invoice_no, inv.client_name),
                                  'invoice-%d.pdf' % inv.id), inv.pdf_bytes)
                counts['invoices'] += 1
            inv_meta.append({'id': inv.id, 'kind': inv.kind, 'client_name': inv.client_name,
                             'client_address': inv.client_address, 'month': inv.month,
                             'year': inv.year, 'invoice_no': inv.invoice_no,
                             'total': inv.total, 'net': inv.net,
                             'data': json.loads(inv.data_json) if inv.data_json else None,
                             'created_at': inv.created_at.isoformat() if inv.created_at else None})
        if inv_meta:
            z.writestr('invoices.json', json.dumps(inv_meta, ensure_ascii=False, indent=1))

        # ৩. মাস-আর্কাইভ
        for a in MonthArchive.query.filter_by(user_id=current_user.id).all():
            if a.file_bytes:
                z.writestr(_zname('archives', a.filename, 'archive-%d.xlsx' % a.id), a.file_bytes)
                counts['archives'] += 1

        # ৪. অগ্রিম-খাতা: JSON + ক্লাউড-শিট
        adv_rows = _advance_rows(current_user.id)
        adv_meta = [{'person': e.person, 'amount': e.amount, 'status': e.status,
                     'date': e.date, 'reason': e.reason,
                     'created_at': e.created_at.isoformat() if e.created_at else None}
                    for e in adv_rows]
        z.writestr('advance_entries.json', json.dumps(adv_meta, ensure_ascii=False, indent=1))
        counts['advance'] = len(adv_meta)
        try:
            from openpyxl import Workbook
            awb = Workbook()
            aws = awb.active
            aws.title = 'Advance'
            aws.append(['Name', 'Amount', 'Date', 'Status', 'Reason'])
            _g = 0.0
            for e in adv_rows:
                aws.append([e.person, e.amount or 0.0, e.date or '', e.status or '', e.reason or ''])
                _g += e.amount or 0.0
            aws.append([])
            aws.append(['GRAND TOTAL', _g])
            abuf = io.BytesIO()
            awb.save(abuf)
            z.writestr('Advance sheet ক্লাউড.xlsx', abuf.getvalue())
        except Exception:
            pass

        # ৫. কনফিগ (ফোন, খাতা, ইনভয়েস-কনফিগ ইত্যাদি)
        cfg_rows = ConfigStore.query.filter_by(user_id=current_user.id).all()
        cfg_out = {}
        for c in cfg_rows:
            try:
                cfg_out[c.key] = json.loads(c.value) if c.value else None
            except Exception:
                cfg_out[c.key] = c.value
            counts['config'] += 1
        z.writestr('config_store.json', json.dumps(cfg_out, ensure_ascii=False, indent=1))

        # ৬. ম্যানিফেস্ট
        z.writestr('manifest.txt', (
            'AI Time Keeper — ক্লাউড ব্যাকআপ\n'
            'তৈরি: %s (UTC)\n'
            'অ্যাকাউন্ট: %s\n'
            'শিট: %d | ইনভয়েস: %d | আর্কাইভ: %d | অগ্রিম-এন্ট্রি: %d | কনফিগ-কি: %d\n'
            % (datetime.utcnow().strftime('%Y-%m-%d %H:%M'), current_user.email,
               counts['sheets'], counts['invoices'], counts['archives'],
               counts['advance'], counts['config'])))
    from flask import Response
    fname = 'AI_Time_Keeper_CLOUD_BACKUP_%s.zip' % datetime.utcnow().strftime('%Y%m%d_%H%M')
    return Response(buf.getvalue(), mimetype='application/zip',
                    headers={'Content-Disposition': 'attachment; filename="%s"' % fname})


# ---------------------------------------------------------------- Profit (রেট/খরচ/পেমেন্ট/ডিউটি)
def _numf(v):
    try:
        return float(v) if v not in (None, '') else 0.0
    except (TypeError, ValueError):
        return 0.0


def _pjson(key, default):
    raw = get_user_config(current_user.id, key)
    if raw:
        try:
            v = json.loads(raw)
            if v is not None:
                return v
        except Exception:
            pass
    return default


def _pjson_save(key, value):
    set_user_config(current_user.id, key, json.dumps(value, ensure_ascii=False))


def _profit_files():
    """আর্কাইভ-করা Total T শিটগুলো — নতুন আগে। file-কি হলো 'archive:<id>'।"""
    rows = (MonthArchive.query.filter_by(user_id=current_user.id, kind='total_sheet')
            .order_by(MonthArchive.created_at.desc()).all())
    files = []
    for r in rows:
        files.append({'file': 'archive:%d' % r.id,
                      'mtime': r.created_at.timestamp() if r.created_at else 0,
                      'label': r.filename, 'month': r.month, 'year': r.year})
    return files


def _profit_workers(file_key):
    """Total T শিট (MonthArchive বাইটস) → [{name, provider, hours, rate, total, adv, gas}]"""
    m = re.match(r'archive:(\d+)', str(file_key or ''))
    if not m:
        raise ValueError('টোটাল শিট আর্কাইভ বাছাই করুন')
    arc = MonthArchive.query.filter_by(id=int(m.group(1)), user_id=current_user.id).first()
    if not arc or not arc.file_bytes:
        raise ValueError('টোটাল শিট পাওয়া যায়নি')
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    tmp.write(arc.file_bytes)
    tmp.close()
    try:
        from generator import preview_total_sheet
        pv = preview_total_sheet(tmp.name)
        workers, cur = [], ''
        for row in pv.get('grand', []):
            if row.get('t') == 'ref':
                cur = str(row.get('text', ''))
            elif row.get('t') == 'w':
                h, rt = _numf(row.get('h')), _numf(row.get('rate'))
                # Total কলাম ফর্মুলা — data_only পড়ায় ক্যাশড ০ আসতে পারে,
                # তাই ঘণ্টা×রেট নিজে হিসাব করি (লোকাল ইঞ্জিনের মতো)
                workers.append({'name': str(row.get('name', '')), 'provider': cur,
                                'hours': h, 'rate': rt, 'total': round(h * rt, 2),
                                'adv': _numf(row.get('adv')), 'gas': _numf(row.get('gas'))})
        return workers
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


@app.route('/api/ws/profit', methods=['GET'], strict_slashes=False)
@login_required
def profit_get():
    files = _profit_files()
    want = request.args.get('file') or (files[0]['file'] if files else '')
    workers, werr = [], None
    if want:
        try:
            workers = _profit_workers(want)
        except Exception as e:
            werr = str(e)
            want = files[0]['file'] if files else ''
            if want:
                try:
                    workers = _profit_workers(want)
                except Exception:
                    workers = []
    return jsonify({'ok': True,
                    'rates': _pjson('profit_rates', {}),
                    'srates': _pjson('profit_srates', {}),
                    'duty': _pjson('profit_duty', {}),
                    'expenses': _pjson('profit_exp', []),
                    'pay': _pjson('profit_pay', {}),
                    'files': files, 'file': want, 'workers': workers,
                    'error': werr})


def _profit_post_load(key, shape):
    v = _pjson(key, shape)
    return v if isinstance(v, type(shape)) else shape


@app.route('/api/ws/profit-rates', methods=['POST'], strict_slashes=False)
@login_required
def profit_rates_post():
    d = request.get_json() or {}
    rates = _profit_post_load('profit_rates', {})
    site = ' '.join(str(d.get('site') or '').split())
    if not site:
        return jsonify({'ok': False, 'error': 'সাইটের নাম দিন'}), 400
    if d.get('del'):
        rates.pop(site, None)
    else:
        rate = _numf(str(d.get('rate') or '').replace(',', ''))
        if rate < 0:
            return jsonify({'ok': False, 'error': 'সঠিক রেট লিখুন'}), 400
        rates[site] = rate
    _pjson_save('profit_rates', rates)
    return jsonify({'ok': True, 'rates': rates, 'backup': 'ডেটাবেজ (স্থায়ী)'})


@app.route('/api/ws/profit-srates', methods=['POST'], strict_slashes=False)
@login_required
def profit_srates_post():
    d = request.get_json() or {}
    srates = _profit_post_load('profit_srates', {})
    person = ' '.join(str(d.get('person') or '').split())
    key = G.norm_person(person)
    if not key:
        return jsonify({'ok': False, 'error': 'লোকের নাম দিন'}), 400
    if d.get('del'):
        srates.pop(key, None)
    else:
        rate = _numf(str(d.get('rate') or '').replace(',', ''))
        if rate <= 0:
            return jsonify({'ok': False, 'error': 'সঠিক রেট লিখুন'}), 400
        srates[key] = {'name': person, 'rate': rate}
    _pjson_save('profit_srates', srates)
    return jsonify({'ok': True, 'srates': srates, 'backup': 'ডেটাবেজ (স্থায়ী)'})


@app.route('/api/ws/profit-duty', methods=['POST'], strict_slashes=False)
@login_required
def profit_duty_post():
    d = request.get_json() or {}
    duty = _profit_post_load('profit_duty', {})
    month = ' '.join(str(d.get('month') or '').split())[:7]
    person = ' '.join(str(d.get('person') or '').split())
    key = G.norm_person(person)
    if not month or not key:
        return jsonify({'ok': False, 'error': 'মাস ও নাম দিন'}), 400
    m = duty.get(month) or {}
    if d.get('del'):
        m.pop(key, None)
        if m:
            duty[month] = m
        else:
            duty.pop(month, None)
    else:
        raw = d.get('splits') or []
        if not isinstance(raw, list) or not raw:
            return jsonify({'ok': False, 'error': 'সাইট ভাগ দিন'}), 400
        splits = []
        for sp in raw:
            sp = sp or {}
            site = ' '.join(str(sp.get('site') or '').split())[:60]
            days = _numf(sp.get('days'))
            hours = _numf(sp.get('hours'))
            if site and (days or hours):
                splits.append({'site': site, 'days': days, 'hours': hours})
        if not splits:
            return jsonify({'ok': False, 'error': 'সাইট ভাগ দিন'}), 400
        m[key] = {'name': re.sub(r'\s*\(.*', '', person).strip(), 'splits': splits}
        duty[month] = m
    _pjson_save('profit_duty', duty)
    return jsonify({'ok': True, 'duty': duty, 'backup': 'ডেটাবেজ (স্থায়ী)'})


@app.route('/api/ws/profit-exp', methods=['POST'], strict_slashes=False)
@login_required
def profit_exp_post():
    d = request.get_json() or {}
    exp = _profit_post_load('profit_exp', [])
    if d.get('del') is not None:
        try:
            idx = int(d.get('del'))
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'সঠিক সারি নয়'}), 400
        if 0 <= idx < len(exp):
            exp.pop(idx)
    else:
        month = ' '.join(str(d.get('month') or '').split())[:7]
        label = ' '.join(str(d.get('label') or '').split())[:60]
        amount = _numf(d.get('amount'))
        if not month or not label:
            return jsonify({'ok': False, 'error': 'মাস ও বিবরণ দিন'}), 400
        exp.append({'month': month, 'label': label, 'amount': amount})
    _pjson_save('profit_exp', exp)
    return jsonify({'ok': True, 'expenses': exp, 'backup': 'ডেটাবেজ (স্থায়ী)'})


@app.route('/api/ws/profit-pay', methods=['POST'], strict_slashes=False)
@login_required
def profit_pay_post():
    d = request.get_json() or {}
    pay = _profit_post_load('profit_pay', {})
    month = ' '.join(str(d.get('month') or '').split())[:7]
    kind = str(d.get('kind') or '')
    if not month or not kind:
        return jsonify({'ok': False, 'error': 'মাস ও ধরন দিন'}), 400
    m = pay.setdefault(month, {})
    if kind == 'income':
        m['income'] = bool(d.get('paid'))
        m['incomeDate'] = str(d.get('date') or '')[:10]
    else:
        prov = ' '.join(str(d.get('provider') or '').split())
        if not prov:
            return jsonify({'ok': False, 'error': 'প্রোভাইডার দিন'}), 400
        pr = m.setdefault('prov', {})
        if d.get('paid'):
            pr[prov] = True
        else:
            pr.pop(prov, None)
    _pjson_save('profit_pay', pay)
    return jsonify({'ok': True, 'pay': pay, 'backup': 'ডেটাবেজ (স্থায়ী)'})


@app.route('/api/ws/provider-save', methods=['POST'], strict_slashes=False)
@login_required
def provider_save():
    d = request.get_json() or {}
    if not isinstance(d, dict) or not d:
        return jsonify({'ok': False, 'error': 'কনফিগ পাওয়া যায়নি'}), 400
    _pjson_save('provider_config', d)
    return jsonify({'ok': True, 'backup': 'ডেটাবেজ (স্থায়ী)'})


# ---------------------------------------------------------------- Monthly Cycle টাইমলাইন
@app.route('/api/cycle', methods=['GET'], strict_slashes=False)
@login_required
def cycle_get():
    import cycle as _cy
    files = _profit_files()
    want = request.args.get('file') or (files[0]['file'] if files else '')
    workers = []
    if want:
        try:
            workers = _profit_workers(want)
        except Exception:
            workers = []
    provs = []
    for w in workers:
        pr = str(w.get('provider') or '').strip()
        if pr and pr not in provs:
            provs.append(pr)
    if not provs:
        for a in LaborAssign.query.filter_by(user_id=current_user.id).all():
            pr = (a.provider or '').strip()
            if pr and pr not in provs:
                provs.append(pr)
    pay = _pjson('profit_pay', {})
    try:
        back = int(request.args.get('back', 3) or 3)
    except (TypeError, ValueError):
        back = 3
    try:
        fwd = int(request.args.get('fwd', 1) or 1)
    except (TypeError, ValueError):
        fwd = 1
    start = request.args.get('start') or '2026-09'
    return jsonify(_cy.cycle_state(providers=provs, pay=pay,
                                   start=start, months_back=back, months_fwd=fwd))


# ---------------------------------------------------------------- ক্লাউড মেমোরি (স্টোরেজ-হিসাব)
@app.route('/api/storage', methods=['GET'], strict_slashes=False)
@login_required
def storage_info():
    """ক্লাউড মেমোরি: মোট/ব্যবহৃত/খালি জায়গা + টেবিল-প্রতি খরচ + আপনার ডেটার হিসাব।"""
    from sqlalchemy import text
    LIMIT_MB = 1024.0   # Neon ফ্রি প্ল্যান — প্রজেক্ট-প্রতি ~১ GB
    total_bytes = 0
    tables = []
    try:
        with db.engine.connect() as conn:
            total_bytes = conn.execute(text("SELECT pg_database_size(current_database())")).scalar() or 0
            trows = conn.execute(text(
                "SELECT c.relname, pg_total_relation_size(c.oid) "
                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind='r' "
                "ORDER BY pg_total_relation_size(c.oid) DESC")).all()
            tables = [{'name': r[0], 'kb': round(r[1] / 1024.0, 1)} for r in trows]
    except Exception:
        tables = []
    used_mb = round(total_bytes / 1048576.0, 2)
    used_pct = round(100.0 * total_bytes / (LIMIT_MB * 1048576.0), 1)
    counts = {
        'sheets': DataSheet.query.filter_by(user_id=current_user.id).count(),
        'invoices': Invoice.query.filter_by(user_id=current_user.id).count(),
        'archives': MonthArchive.query.filter_by(user_id=current_user.id).count(),
        'advance': AdvanceEntry.query.filter_by(user_id=current_user.id).count(),
        'labor': LaborAssign.query.filter_by(user_id=current_user.id).count(),
        'config': ConfigStore.query.filter_by(user_id=current_user.id).count(),
    }
    return jsonify({'ok': True,
                    'limit_mb': LIMIT_MB,
                    'used_mb': used_mb,
                    'used_pct': used_pct,
                    'free_mb': round(LIMIT_MB - used_mb, 2),
                    'tables': tables,
                    'counts': counts,
                    'account': current_user.email,
                    'checked_at': datetime.utcnow().isoformat() + 'Z'})


# ---------------------------------------------------------------- কনফিগ সেভ
@app.route('/api/ws/add-invoice-config', methods=['POST'], strict_slashes=False)
@login_required
def add_invoice_config():
    d = request.get_json() or {}
    try:
        set_user_config(current_user.id, 'add_invoice_config', json.dumps(d, ensure_ascii=False))
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/ws/invoice-gen-config', methods=['POST'], strict_slashes=False)
@login_required
def invoice_gen_config():
    d = request.get_json() or {}
    try:
        set_user_config(current_user.id, 'invoice_config', json.dumps(d, ensure_ascii=False))
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ---------------------------------------------------------------- মাস ক্লায়ার
@app.route('/api/month-clear', methods=['POST'], strict_slashes=False)
@login_required
def month_clear_route():
    d = request.get_json() or {}
    data_id = d.get('data_sheet_id')
    tmpl_id = d.get('template_id')
    month = int(d.get('month') or 0)
    year = int(d.get('year') or 0)
    if not (month and year):
        return jsonify({'ok': False, 'error': 'মাস ও সাল প্রয়োজন'}), 400

    sheet = DataSheet.query.filter_by(id=data_id, user_id=current_user.id).first() if data_id else None
    if not sheet or not sheet.file_bytes:
        return jsonify({'ok': False, 'error': 'ডাটা শিট পাওয়া যায়নি'}), 400
    # নিরাপত্তা: শিটের নিজের মাস আর চাওয়া মাস মিলছে কিনা — ভুল শিটে ভুল মাস ক্লিয়ার ঠেকাতে
    if sheet.month and sheet.year and (sheet.month != month or sheet.year != year):
        return jsonify({'ok': False,
                        'error': 'শিটটার মাস %02d-%d, কিন্তু ক্লিয়ার করতে চেয়েছেন %02d-%d — মিলিয়ে নিন'
                                 % (sheet.month, sheet.year, month, year)}), 400

    tmp_data = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    tmp_data.write(sheet.file_bytes)
    tmp_data.close()
    tmp_tmpl = None
    if tmpl_id:
        tmpl = DataSheet.query.filter_by(id=tmpl_id, user_id=current_user.id).first()
        if tmpl and tmpl.file_bytes:
            tmp_tmpl = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            tmp_tmpl.write(tmpl.file_bytes)
            tmp_tmpl.close()

    try:
        result = M.month_clear(
            tmp_data.name,
            tmp_tmpl.name if tmp_tmpl else None,
            month, year,
            do_generate=True,
            backup_fn=lambda p: backup_file(p, 'month_clear')
        )
        # নতুন মাসের শিটটাও DB-তে রাখি — Render-এর ডিস্ক ephemeral, ফাইল রিস্টার্টে হারায়
        new_path = (result or {}).get('newPath')
        if new_path and os.path.isfile(new_path):
            with open(new_path, 'rb') as nf:
                db.session.add(DataSheet(
                    user_id=current_user.id,
                    filename=(result or {}).get('newFile') or os.path.basename(new_path),
                    month=(result or {}).get('newMonthNum'),
                    year=(result or {}).get('newYear'),
                    file_bytes=nf.read(),
                ))
                db.session.commit()
        # হিস্ট্রি: বন্ধ মাসের ডাটা শিট আর টোটাল শিটও DB-তে স্থায়ী সংরক্ষণ —
        # লোকালের months\ ফোল্ডার-আর্কাইভের ক্লাউড-সমতুল্য (ডিপ্লয়ে হারায় না)
        closed_dir = (result or {}).get('closedDir')
        data_sub = getattr(M, 'DATA_SUB', 'data sheet and total time sheet')
        if closed_dir and os.path.isdir(closed_dir):
            names = [n for n in ((result or {}).get('files') or []) if n]
            if (result or {}).get('totalSheet') and (result or {}).get('totalSheet') not in names:
                names.append((result or {}).get('totalSheet'))
            for name in names:
                path = os.path.join(closed_dir, data_sub, name)
                if not os.path.isfile(path):
                    continue
                kind = 'total_sheet' if name == (result or {}).get('totalSheet') else 'data_sheet'
                dup = MonthArchive.query.filter_by(user_id=current_user.id, month=month,
                                                   year=year, kind=kind, filename=name).first()
                if dup:
                    continue
                with open(path, 'rb') as af:
                    db.session.add(MonthArchive(user_id=current_user.id, month=month, year=year,
                                                kind=kind, filename=name, file_bytes=af.read()))
                db.session.commit()
        return jsonify({'ok': True, 'result': result})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        try:
            os.unlink(tmp_data.name)
        except Exception:
            pass
        if tmp_tmpl:
            try:
                os.unlink(tmp_tmpl.name)
            except Exception:
                pass


# ---------------------------------------------------------------- ফাইল লিস্ট
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
            'size': len(s.file_bytes or b''),
            'xlsx': True,
            'id': s.id
        } for s in sheets]
    })


# ---------------------------------------------------------------- স্ট্যাটিক ফ্রন্টএন্ড
@app.route('/', methods=['GET'])
def index():
    return send_from_directory(app.static_folder, 'workspace.html')


@app.route('/login', methods=['GET'])
def login_page():
    return send_from_directory(app.static_folder, 'login.html')


@app.route('/workspace', methods=['GET'])
def workspace():
    return send_from_directory(app.static_folder, 'workspace.html')


@app.route('/<path:path>', methods=['GET'])
def static_proxy(path):
    if path.startswith('api/') or path == 'api':
        return jsonify({'ok': False, 'error': 'API endpoint not found'}), 404
    if '..' in path or path.startswith('/'):
        abort(404)
    full_path = os.path.join(app.static_folder, path)
    if os.path.isfile(full_path):
        return send_from_directory(app.static_folder, path)
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
