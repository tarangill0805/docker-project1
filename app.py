import functools
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import click
from flask import Flask, abort, flash, g, redirect, render_template, request, send_from_directory, session, url_for
from PIL import Image, UnidentifiedImageError
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
TYPES = ['House', 'Villa', 'Apartment', 'Plot', 'Land', 'Commercial']
BUSINESS = dict(name='New Address', email='newaddressofficial@gmail.com', phone='+91 9417566773', phone_link='+919417566773', address='Sector 68, near Jubilee Walk, Mohali, Punjab')

def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    key_path = Path(app.instance_path) / 'secret.key'
    if not key_path.exists():
        try:
            with key_path.open('x') as f:
                f.write(secrets.token_hex(32))
            key_path.chmod(0o600)
        except FileExistsError:
            pass
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or key_path.read_text(), DATABASE=str(Path(app.instance_path) / 'newaddress.sqlite3'), UPLOAD_FOLDER=str(Path(app.instance_path) / 'uploads'), MAX_CONTENT_LENGTH=20 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('HTTPS_ONLY') == '1', PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
    if config:
        app.config.update(config)
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'], timeout=15)
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_):
        if 'db' in g:
            g.pop('db').close()

    def csrf():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(32)
        return session['csrf']

    @app.context_processor
    def context():
        return dict(csrf_token=csrf, business=BUSINESS, types=TYPES)

    @app.before_request
    def protect():
        if request.method == 'POST' and (not session.get('csrf') or not hmac.compare_digest(str(session.get('csrf', '')).encode(), str(request.form.get('csrf_token', '')).encode())):
            abort(400, 'This form expired. Refresh the page and try again.')

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if request.path.startswith('/admin'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    def admin_only(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            admin = db().execute('SELECT * FROM admin WHERE id=1').fetchone()
            if not admin or session.get('admin_version') != admin['version']:
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapped

    def decode(row):
        p = dict(row)
        p['images'] = json.loads(p['images'])
        return p

    def get_property(pid):
        row = db().execute('SELECT * FROM properties WHERE id=?', (pid,)).fetchone()
        if not row:
            abort(404)
        return decode(row)

    with app.app_context():
        db().executescript('''CREATE TABLE IF NOT EXISTS properties (id TEXT PRIMARY KEY,title TEXT NOT NULL,city TEXT NOT NULL,type TEXT NOT NULL,mode TEXT NOT NULL,price TEXT NOT NULL,area TEXT NOT NULL,beds INTEGER NOT NULL,description TEXT NOT NULL,images TEXT NOT NULL,demo INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS enquiries (id TEXT PRIMARY KEY,name TEXT,phone TEXT,email TEXT,message TEXT,property_id TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY CHECK(id=1),email TEXT,password_hash TEXT,version TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS attempts (key TEXT PRIMARY KEY,count INTEGER,until REAL);''')
        if not db().execute("SELECT 1 FROM settings WHERE key='seeded'").fetchone():
            for p in json.loads((ROOT / 'sample_properties.json').read_text(encoding='utf-8')):
                db().execute('INSERT OR IGNORE INTO properties VALUES (?,?,?,?,?,?,?,?,?,?,?)', tuple(p[k] for k in ['id','title','city','type','mode','price','area','beds','description']) + (json.dumps(p['images']),1))
            db().execute("INSERT INTO settings VALUES ('seeded','yes')")
        db().commit()

    def limited(key, limit, seconds):
        now = time.time()
        row = db().execute('SELECT * FROM attempts WHERE key=?', (key,)).fetchone()
        if row and row['until'] > now and row['count'] >= limit:
            return True
        count, until = (row['count']+1, row['until']) if row and row['until'] > now else (1, now+seconds)
        db().execute('INSERT OR REPLACE INTO attempts VALUES (?,?,?)', (key,count,until))
        db().execute('DELETE FROM attempts WHERE until < ?', (now,))
        db().commit()
        return False

    @app.route('/')
    def home():
        clauses, params = [], []
        for k in ['mode','city','type']:
            value = request.args.get(k, 'all')
            if value and value != 'all':
                clauses.append(k+'=?')
                params.append(value)
        query = 'SELECT * FROM properties' + (' WHERE '+' AND '.join(clauses) if clauses else '') + ' ORDER BY rowid DESC'
        return render_template('home.html', properties=[decode(r) for r in db().execute(query,params)], cities=[r[0] for r in db().execute('SELECT DISTINCT city FROM properties ORDER BY city')])

    @app.route('/properties/<pid>')
    def property_detail(pid):
        return render_template('property.html', p=get_property(pid))

    @app.post('/enquiry')
    def enquiry():
        if request.form.get('website'):
            abort(400)
        name, phone, email, message = [request.form.get(k,'').strip() for k in ['name','phone','email','message']]
        if not (1 <= len(name) <= 100 and 10 <= len(re.sub(r'\D','',phone)) <= 15 and re.fullmatch(r'[+0-9 ()-]+',phone) and len(email) <= 200 and (not email or re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)) and 5 <= len(message) <= 3000):
            abort(400, 'Check your name, phone, email and message, then try again.')
        if limited('enquiry:'+str(request.remote_addr), 10, 3600):
            abort(429, 'Please wait before sending another enquiry.')
        pid = request.form.get('property_id','')
        if pid:
            get_property(pid)
        ref = uuid4().hex
        db().execute('INSERT INTO enquiries (id,name,phone,email,message,property_id) VALUES (?,?,?,?,?,?)',(ref,name,phone,email,message,pid))
        db().commit()
        flash('Your enquiry has been saved. Reference: '+ref[:8].upper())
        return redirect(url_for('home')+'#inquiry')

    @app.route('/admin/login', methods=['GET','POST'])
    def login():
        configured = bool(db().execute('SELECT 1 FROM admin').fetchone())
        if request.method == 'POST':
            if limited('login:'+str(request.remote_addr), 10, 900):
                abort(429, 'Too many attempts. Try again in 15 minutes.')
            row = db().execute('SELECT * FROM admin WHERE id=1').fetchone()
            if row and hmac.compare_digest(row['email'].encode(),request.form.get('email','').strip().lower().encode()) and check_password_hash(row['password_hash'],request.form.get('password','')):
                session.clear()
                session['admin_version'] = row['version']
                session.permanent = True
                return redirect(url_for('admin'))
            flash('Email or password is incorrect.')
        return render_template('login.html',configured=configured)

    @app.post('/admin/logout')
    def logout():
        session.clear()
        return redirect(url_for('home'))

    @app.route('/admin')
    @admin_only
    def admin():
        return render_template('admin.html', properties=[decode(r) for r in db().execute('SELECT * FROM properties ORDER BY rowid DESC')], enquiries=db().execute('SELECT * FROM enquiries ORDER BY created_at DESC').fetchall())

    @app.route('/admin/property/new', methods=['GET','POST'])
    @app.route('/admin/property/<pid>/edit', methods=['GET','POST'])
    @admin_only
    def edit_property(pid=None):
        p = get_property(pid) if pid else None
        if request.method == 'POST':
            fields = {k:request.form.get(k,'').strip() for k in ['title','city','type','mode','price','area','description']}
            try:
                beds = int(request.form.get('beds','0'))
            except ValueError:
                abort(400, 'Bedrooms must be a whole number.')
            if not all(fields.values()) or any(len(v)>3000 for v in fields.values()) or fields['type'] not in TYPES or fields['mode'] not in ['buy','rent'] or not 0 <= beds <= 100:
                abort(400, 'Complete every property field with valid values.')
            images = [s.strip() for s in request.form.get('images','').splitlines() if s.strip()]
            if len(images)>20 or any(len(s)>2000 or not (re.match(r'^https://[^/\s]+/[^\s]*$',s) or re.fullmatch(r'/uploads/[a-f0-9]{32}\.jpg',s)) for s in images):
                abort(400, 'Use HTTPS image URLs, one per line (maximum 20).')
            uploads = [f for f in request.files.getlist('photos') if f.filename]
            if len(images)+len(uploads)>20:
                abort(400, 'Maximum 20 images per property.')
            prepared = []
            try:
                for f in uploads:
                    image = Image.open(f.stream)
                    if image.format not in ['JPEG','PNG','WEBP'] or image.width*image.height>25_000_000:
                        raise ValueError()
                    image.load()
                    image = image.convert('RGB')
                    image.thumbnail((2400,2400))
                    prepared.append(image)
            except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
                abort(400, 'Upload valid JPG, PNG or WebP images, up to 25 megapixels each.')
            for image in prepared:
                filename=uuid4().hex+'.jpg'
                image.save(Path(app.config['UPLOAD_FOLDER'])/filename,quality=88)
                images.append('/uploads/'+filename)
            if not images:
                abort(400, 'Add at least one image URL or upload.')
            pid = pid or uuid4().hex
            db().execute('INSERT OR REPLACE INTO properties VALUES (?,?,?,?,?,?,?,?,?,?,?)',(pid,fields['title'],fields['city'],fields['type'],fields['mode'],fields['price'],fields['area'],beds,fields['description'],json.dumps(images),int(request.form.get('demo')=='1')))
            db().commit()
            flash('Property saved.')
            return redirect(url_for('admin'))
        return render_template('edit.html',p=p)

    @app.post('/admin/property/<pid>/delete')
    @admin_only
    def delete_property(pid):
        get_property(pid)
        db().execute('DELETE FROM properties WHERE id=?',(pid,))
        db().commit()
        flash('Property deleted.')
        return redirect(url_for('admin'))

    @app.route('/uploads/<filename>')
    def uploads(filename):
        if not re.fullmatch(r'[a-f0-9]{32}\.jpg',filename):
            abort(404)
        return send_from_directory(app.config['UPLOAD_FOLDER'],filename)

    @app.cli.command('set-admin')
    @click.option('--email', prompt='Admin email')
    @click.password_option(confirmation_prompt=True)
    def set_admin(email,password):
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(password)<12:
            raise click.ClickException('Use a valid email and a password with at least 12 characters.')
        db().execute('INSERT OR REPLACE INTO admin VALUES (1,?,?,?)',(email.strip().lower(),generate_password_hash(password),secrets.token_hex(24)))
        db().commit()
        click.echo('Private admin saved. Previous admin sessions invalidated.')

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    @app.errorhandler(429)
    def error(e):
        return render_template('error.html',error=e),e.code
    return app

if __name__ == '__main__':
    create_app().run(host='0.0.0.0',port=5000)
