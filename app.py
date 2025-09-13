import os
import secrets
import base64
import hashlib
import io
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    send_file, abort
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet

# -----------------------
# App & DB config
# -----------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'links.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# -----------------------
# Models
# -----------------------
class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url_key = db.Column(db.String(128), unique=True, nullable=False, index=True)

    # If file: store metadata and path to encrypted bytes.
    is_file = db.Column(db.Boolean, default=False)
    filename = db.Column(db.String(256), nullable=True)       # original filename
    file_path = db.Column(db.String(512), nullable=True)      # uploads/<key>.bin
    mime_type = db.Column(db.String(128), nullable=True)

    # For text secrets (encrypted string stored as base64 text)
    content = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_time = db.Column(db.DateTime, nullable=True)
    max_views = db.Column(db.Integer, nullable=True)
    views = db.Column(db.Integer, default=0)

# -----------------------
# Encryption helpers
# -----------------------
def _get_fernet():
    """Get a Fernet instance. Prefer FILE_KEY env var, otherwise derive from SECRET_KEY."""
    env_key = os.environ.get('FILE_KEY')
    if env_key:
        key_bytes = env_key.encode() if isinstance(env_key, str) else env_key
        # If user supplied a raw passphrase (not a base64 key), they must supply proper key.
        # We expect a valid base64 urlsafe 32-byte key here.
        return Fernet(key_bytes)
    # derive key from SECRET_KEY so dev runs consistently across restarts
    secret = app.config.get('SECRET_KEY', 'dev-secret-key')
    digest = hashlib.sha256(secret.encode()).digest()   # 32 bytes
    key = base64.urlsafe_b64encode(digest)             # valid Fernet key
    return Fernet(key)

def encrypt_bytes(data: bytes) -> bytes:
    return _get_fernet().encrypt(data)

def decrypt_bytes(token: bytes) -> bytes:
    return _get_fernet().decrypt(token)

def encrypt_text(text: str) -> str:
    return encrypt_bytes(text.encode()).decode()

def decrypt_text(token_str: str) -> str:
    return decrypt_bytes(token_str.encode()).decode()

# -----------------------
# Utility functions
# -----------------------
def generate_unique_key(length=6):
    while True:
        key = secrets.token_urlsafe(length)
        if not Link.query.filter_by(url_key=key).first():
            return key

def parse_expiry(expiry_value, expiry_unit):
    """Return a datetime or None based on expiry_value and unit"""
    if not expiry_value:
        return None
    try:
        v = int(expiry_value)
        if v <= 0:
            return None
    except ValueError:
        return None

    now = datetime.utcnow()
    if expiry_unit == 'minutes':
        return now + timedelta(minutes=v)
    if expiry_unit == 'hours':
        return now + timedelta(hours=v)
    if expiry_unit == 'days':
        return now + timedelta(days=v)
    # default
    return now + timedelta(minutes=v)

# -----------------------
# Routes
# -----------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create', methods=['POST'])
def create():
    # form fields
    # support both the new (expiry_value/unit) and legacy expiry_minutes
    content = request.form.get('content', '').strip()
    expiry_value = request.form.get('expiry_value', '').strip()
    expiry_unit = request.form.get('expiry_unit', 'minutes')
    # backward compat
    legacy_minutes = request.form.get('expiry_minutes', '').strip()
    if not expiry_value and legacy_minutes:
        expiry_value = legacy_minutes
        expiry_unit = 'minutes'

    max_views = request.form.get('max_views', '').strip()

    # file handling
    uploaded_file = request.files.get('file')
    is_file = uploaded_file and uploaded_file.filename != ''

    if not is_file and not content:
        flash('Provide either text content or a file.', 'danger')
        return redirect(url_for('index'))

    expiry_time = parse_expiry(expiry_value, expiry_unit)

    mv = None
    if max_views:
        try:
            mv = int(max_views)
            if mv <= 0:
                mv = None
        except ValueError:
            flash('Max views must be an integer.', 'danger')
            return redirect(url_for('index'))

    key = generate_unique_key()

    encrypted_text = None
    if content:
        encrypted_text = encrypt_text(content)

    file_path = None
    filename = None
    mime_type = None
    is_file_flag = False

    if is_file:
        original_name = secure_filename(uploaded_file.filename)
        raw = uploaded_file.read()
        encrypted = encrypt_bytes(raw)
        file_path = os.path.join(UPLOAD_FOLDER, f'{key}.bin')
        with open(file_path, 'wb') as f:
            f.write(encrypted)
        filename = original_name
        mime_type = uploaded_file.mimetype or 'application/octet-stream'
        is_file_flag = True

    link = Link(
        url_key=key,
        is_file=is_file_flag,
        filename=filename,
        file_path=file_path,
        mime_type=mime_type,
        content=encrypted_text,  # can exist alongside file
        expiry_time=expiry_time,
        max_views=mv
    )


    db.session.add(link)
    db.session.commit()

    short_url = request.host_url.rstrip('/') + '/' + key
    return render_template('result.html', short_url=short_url, key=key, expiry_time=expiry_time, max_views=mv, is_file=link.is_file)

@app.route('/api/create', methods=['POST'])
def api_create():
    data = request.get_json() or {}
    content = data.get('content')
    expiry_value = data.get('expiry_value')
    expiry_unit = data.get('expiry_unit', 'minutes')
    max_views = data.get('max_views')

    if not content:
        return {"error": "content required"}, 400

    expiry_time = parse_expiry(expiry_value, expiry_unit)

    mv = None
    if max_views is not None:
        try:
            mv = int(max_views)
        except Exception:
            mv = None

    key = generate_unique_key()
    encrypted_text = encrypt_text(content)
    link = Link(url_key=key, is_file=False, content=encrypted_text, expiry_time=expiry_time, max_views=mv)
    db.session.add(link)
    db.session.commit()

    return {"short_url": request.host_url.rstrip('/') + '/' + key, "key": key}, 201

# View a link (for text -> show content; for file -> show download page)
@app.route('/<string:key>')
def serve(key):
    link = Link.query.filter_by(url_key=key).first()
    if not link:
        return render_template('expired.html', message="Link not found or expired.")

    # --- time expiry check ---
    if link.expiry_time and datetime.utcnow() > link.expiry_time:
        fp = link.file_path
        db.session.delete(link)
        db.session.commit()
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass
        return render_template('expired.html', message="Link expired (time).")

    # --- views expiry check ---
    if link.max_views is not None and link.views >= link.max_views:
        fp = link.file_path
        db.session.delete(link)
        db.session.commit()
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass
        return render_template('expired.html', message="Link expired (max views reached).")

    # --- Decrypt text if exists ---
    content_plain = None
    if link.content:
        try:
            content_plain = decrypt_text(link.content)
        except Exception:
            content_plain = "[Error: could not decrypt content]"

    # --- Prepare file info if exists ---
    file_info = None
    if link.is_file and link.file_path and os.path.exists(link.file_path):
        file_info = {
            "filename": link.filename,
            "key": key
        }

    # increment views
    link.views += 1
    db.session.commit()

    # delete after view if exceeded
    should_delete = (link.max_views is not None and link.views >= link.max_views)
    if should_delete:
        fp = link.file_path
        db.session.delete(link)
        db.session.commit()
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass

    return render_template(
        "content.html",
        content=content_plain,
        file=file_info,
        remaining=(link.max_views - link.views) if link.max_views else None
    )

# Download endpoint for files (counts as a view)
@app.route('/download/<string:key>')
def download_file(key):
    link = Link.query.filter_by(url_key=key).first()
    if not link or not link.is_file:
        return render_template('expired.html', message="File not found or expired.")

    # time expiry
    if link.expiry_time and datetime.utcnow() > link.expiry_time:
        fp = link.file_path
        db.session.delete(link)
        db.session.commit()
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass
        return render_template('expired.html', message="Link expired (time).")

    # views expiry
    if link.max_views is not None and link.views >= link.max_views:
        fp = link.file_path
        db.session.delete(link)
        db.session.commit()
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass
        return render_template('expired.html', message="Link expired (max views reached).")

    # read encrypted file bytes (in memory), decrypt
    if not link.file_path or not os.path.exists(link.file_path):
        return render_template('expired.html', message="File missing from server.")

    with open(link.file_path, 'rb') as f:
        encrypted = f.read()
    try:
        decrypted = decrypt_bytes(encrypted)
    except Exception:
        return render_template('expired.html', message="Could not decrypt file.")

    # increment view count, commit
    link.views += 1
    db.session.commit()

    should_delete = (link.max_views is not None and link.views >= link.max_views)
    # Remember file_path in local variable before possibly deleting DB row
    file_path_to_remove = link.file_path
    filename = link.filename or f"{key}.bin"
    mime = link.mime_type or 'application/octet-stream'

    if should_delete:
        # remove DB record and file from disk (we already have decrypted in memory)
        try:
            db.session.delete(link)
            db.session.commit()
        except Exception:
            pass
        # delete file from disk
        try:
            if file_path_to_remove and os.path.exists(file_path_to_remove):
                os.remove(file_path_to_remove)
        except Exception:
            pass

    # send decrypted bytes as attachment
    return send_file(
        io.BytesIO(decrypted),
        mimetype=mime,
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    app.run(debug=True)
