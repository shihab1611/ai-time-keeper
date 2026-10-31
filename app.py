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
import months as M

# ---------------------------------------------------------------- app setup
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-production')

db_uri = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
    """লগইন করা ইউজারের সর্বশেষ (বা নির্দিষ্ট) ডাটা শিটের DB বাইটস → টেম্প ফাইল।
    রিটার্ন (tmp_path, sheet_row) — কলার শেষে os.unlink করবে। Render-এ 'input output'
    ফোল্ডার নেই, তাই ইঞ্জিন সবসময় এই টেম্প ফাইল থেকেই পড়বে।"""
    q = DataSheet.query.filter_by(user_id=current_user.id)
    if sheet_id:
        q = q.filter_by(id=sheet_id)
    sheet = q.order_by(DataSheet.created_at.desc()).first()
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
    """আপলোড করা ডাটা শিট থেকে আসল ঘণ্টা/রেট; ইউজারের বসানো অ্যাসাইনমেন্ট থাকলে সেই প্রোভাইডার।"""
    fp = None
    rows = []
    try:
        fp, _sheet = _user_sheet_tmp()
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
        data = G.build_invoice(
            prov, month, year,
            rates=rates or None,
            adv=(adv if str(adv).strip() != '' else None),
            gas=(gas if str(gas).strip() != '' else None),
            client=client, address=address,
            fp=fp, assigned_no=_db_next_no('statement', None, month, year),
            cfg=_merged_cfg('invoice_config')
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
        data = G.build_invoice(
            prov, month, year,
            rates=rates, adv=adv, gas=gas,
            client=d.get('client'), address=d.get('address'),
            fp=fp, assigned_no=_db_next_no('statement', None, month, year),
            cfg=_merged_cfg('invoice_config')
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
                                       cfg=cfg)
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
