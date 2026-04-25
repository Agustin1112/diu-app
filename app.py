"""
DIU — Droguería Industrial Uruguaya
Flask App — Sitio Web + Panel Admin
"""

import os, sqlite3, hashlib, secrets, json
from functools import wraps
from datetime import datetime
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, g, jsonify, abort)
from werkzeug.utils import secure_filename

# ── Cargar .env si existe (desarrollo local) ───
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # En producción las vars vienen del entorno del sistema

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
app = Flask(__name__)

# SECRET_KEY: en producción debe setearse como variable de entorno
# Generá una con: python -c "import secrets; print(secrets.token_hex(32))"
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

app.config['DATABASE']           = os.path.join(app.instance_path, 'diu.db')
app.config['UPLOAD_FOLDER']      = os.path.join('static', 'img', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Credenciales del admin inicial — leídas desde variables de entorno
ADMIN_EMAIL    = os.environ.get('ADMIN_EMAIL',    'admin@diu.com.uy')
ADMIN_NAME     = os.environ.get('ADMIN_NAME',     'Administrador')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'cambiar-contrasena')

os.makedirs(app.instance_path, exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ──────────────────────────────────────────────
# DATABASE
# ──────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'],
                               detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

def query(sql, args=(), one=False):
    db  = get_db()
    cur = db.execute(sql, args)
    rv  = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        email       TEXT UNIQUE NOT NULL,
        password    TEXT NOT NULL,
        role        TEXT NOT NULL DEFAULT 'customer',  -- admin | staff | customer
        active      INTEGER DEFAULT 1,
        created_at  TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS categories (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        slug        TEXT UNIQUE NOT NULL,
        description TEXT,
        color       TEXT DEFAULT '#1a4a8a',
        icon        TEXT DEFAULT '📦',
        sort_order  INTEGER DEFAULT 0,
        active      INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS products (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        slug        TEXT UNIQUE NOT NULL,
        description TEXT,
        unit        TEXT,
        price       REAL,
        stock       INTEGER DEFAULT 0,
        category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
        image       TEXT,
        icon        TEXT DEFAULT '📦',
        featured    INTEGER DEFAULT 0,
        active      INTEGER DEFAULT 1,
        created_at  TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS orders (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
        name        TEXT NOT NULL,
        email       TEXT NOT NULL,
        phone       TEXT,
        company     TEXT,
        notes       TEXT,
        items_json  TEXT NOT NULL,
        status      TEXT DEFAULT 'pending',  -- pending | confirmed | shipped | delivered | cancelled
        total_items INTEGER DEFAULT 0,
        created_at  TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS news (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        slug        TEXT UNIQUE NOT NULL,
        summary     TEXT,
        content     TEXT,
        badge       TEXT,
        badge_color TEXT DEFAULT 'badge-navy',
        icon        TEXT DEFAULT '📰',
        active      INTEGER DEFAULT 1,
        created_at  TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS contacts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        email       TEXT NOT NULL,
        phone       TEXT,
        subject     TEXT,
        message     TEXT NOT NULL,
        read        INTEGER DEFAULT 0,
        created_at  TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS settings (
        key         TEXT PRIMARY KEY,
        value       TEXT
    );
    """)
    db.commit()

    # Seed admin user — credenciales desde variables de entorno
    if not query("SELECT id FROM users WHERE role='admin'", one=True):
        pw = hash_password(ADMIN_PASSWORD)
        execute("INSERT INTO users (name, email, password, role) VALUES (?,?,?,?)",
                (ADMIN_NAME, ADMIN_EMAIL, pw, "admin"))

    # Seed categories
    cats = [
        ("Laboratorio-Farma", "laboratorio", "Reactivos, solventes y materiales para laboratorio", "#1a4a8a", "🧬"),
        ("Veterinaria",       "veterinaria", "Insumos y medicamentos veterinarios",               "#1e6c45", "🐄"),
        ("Consumo Masivo",    "consumo",     "Productos de limpieza e higiene doméstica",          "#8a5a00", "🛍️"),
        ("Industria y Servicios","industria","Químicos técnicos para empresas e industria",        "#006b7a", "🏭"),
        ("Piscinas",          "piscinas",    "Tratamiento y mantenimiento de piscinas",            "#0e9eb4", "🏊"),
        ("Envases",           "envases",     "Material de vidrio y plástico de laboratorio",       "#7c5cbf", "🫙"),
    ]
    for i, (name, slug, desc, color, icon) in enumerate(cats):
        if not query("SELECT id FROM categories WHERE slug=?", (slug,), one=True):
            execute("INSERT INTO categories (name,slug,description,color,icon,sort_order) VALUES (?,?,?,?,?,?)",
                    (name, slug, desc, color, icon, i))

    # Seed products
    prods = [
        ("Alcohol etílico 96°",    "alcohol-etilico-96",    "Puro para análisis, alta pureza",    "1 litro",  None, 10, "laboratorio", "🧪", 1),
        ("Ácido clorhídrico 37%",  "acido-clorhidrico-37",  "Técnico, uso industrial y lab",      "1 litro",  None, 8,  "laboratorio", "⚗️", 0),
        ("Acetona pura",           "acetona-pura",           "Para análisis, grado reactivo",      "1 litro",  None, 6,  "laboratorio", "🔬", 0),
        ("Cloruro de sodio",       "cloruro-de-sodio",       "Puro para análisis",                 "500 g",    None, 12, "laboratorio", "🧫", 0),
        ("Solución salina isotónica","solucion-salina",      "Uso veterinario estéril",            "500 ml",   None, 5,  "veterinaria", "💉", 1),
        ("Yodo tintura 2%",        "yodo-tintura-2",         "Antiséptico de uso veterinario",     "1 litro",  None, 7,  "veterinaria", "🌿", 0),
        ("Agua destilada inyectable","agua-destilada",       "Estéril, libre de pirógenos",        "1 litro",  None, 9,  "veterinaria", "💧", 0),
        ("Agua oxigenada 30 vol",  "agua-oxigenada-30",      "Desinfectante de uso doméstico",     "1 litro",  None, 15, "consumo",     "🧴", 1),
        ("Alcohol isopropílico 70°","alcohol-isopropilico",  "Desinfectante de superficies",       "1 litro",  None, 11, "consumo",     "✨", 0),
        ("Cloro granulado 65%",    "cloro-granulado-65",     "Tratamiento de agua de piscina",     "5 kg",     None, 4,  "piscinas",    "🏊", 1),
        ("Algicida concentrado",   "algicida-concentrado",   "Prevención y eliminación de algas",  "1 litro",  None, 6,  "piscinas",    "🌊", 0),
        ("pH minus",               "ph-minus",               "Regulador de pH descendente",        "3 kg",     None, 5,  "piscinas",    "📊", 0),
        ("Solvente alifático",     "solvente-alifatico",     "Industrial, alta pureza",            "20 litros",None, 3,  "industria",   "🏭", 0),
        ("Hipoclorito de sodio",   "hipoclorito-sodio",      "Desinfectante industrial al 10%",    "5 litros", None, 8,  "industria",   "🧼", 0),
        ("Frasco vidrio ámbar 250ml","frasco-vidrio-ambar",  "Con tapa, vidrio neutro",            "Unidad",   None, 20, "envases",     "🫙", 0),
        ("Pipeta Pasteur",         "pipeta-pasteur",         "Vidrio borosilicato",                "x 100",    None, 3,  "envases",     "🧪", 0),
        ("Matraz Erlenmeyer 250ml","matraz-erlenmeyer-250",  "Vidrio borosilicato grado A",        "Unidad",   None, 7,  "envases",     "🔭", 0),
    ]
    for (name, slug, desc, unit, price, stock, cat_slug, icon, featured) in prods:
        if not query("SELECT id FROM products WHERE slug=?", (slug,), one=True):
            cat = query("SELECT id FROM categories WHERE slug=?", (cat_slug,), one=True)
            cat_id = cat['id'] if cat else None
            execute("""INSERT INTO products (name,slug,description,unit,price,stock,category_id,icon,featured)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (name, slug, desc, unit, price, stock, cat_id, icon, featured))

    # Seed news
    news_items = [
        ("Suplemento 90º aniversario DIU", "aniversario-90", "Celebramos 90 años de historia con un suplemento especial.", "Aniversario", "badge-navy", "📰"),
        ("Horarios y días especiales marzo 2026", "horarios-marzo-2026", "Informamos los horarios durante los días especiales de marzo.", "Locales", "badge-blue", "🕐"),
        ("Feriado de Carnaval 2026", "feriado-carnaval-2026", "Comunicamos los horarios durante los días de Carnaval.", "Avisos", "badge-green", "🎉"),
        ("Campaña de piscinas — temporada", "campana-piscinas", "Preparate para el verano con nuestra línea completa de piscinas.", "Tienda", "badge-teal", "🏊"),
    ]
    for (title, slug, summary, badge, badge_color, icon) in news_items:
        if not query("SELECT id FROM news WHERE slug=?", (slug,), one=True):
            execute("INSERT INTO news (title,slug,summary,badge,badge_color,icon) VALUES (?,?,?,?,?,?)",
                    (title, slug, summary, badge, badge_color, icon))

    # Default settings
    defaults = {
        'site_name':    'DIU — Droguería Industrial Uruguaya',
        'site_phone':   '(598) 2900 8190',
        'site_email':   'diu@diu.com.uy',
        'site_address': 'Paysandú 1024, Montevideo',
        'site_facebook':'https://www.facebook.com/DIUruguaya',
        'site_instagram':'https://www.instagram.com/drogueriaindustrialuruguaya/',
    }
    for k, v in defaults.items():
        if not query("SELECT key FROM settings WHERE key=?", (k,), one=True):
            execute("INSERT INTO settings (key,value) VALUES (?,?)", (k, v))


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def slugify(text):
    import re, unicodedata
    text = unicodedata.normalize('NFD', text.lower())
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return text

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def get_setting(key, default=''):
    row = query("SELECT value FROM settings WHERE key=?", (key,), one=True)
    return row['value'] if row else default

def get_settings():
    rows = query("SELECT key, value FROM settings")
    return {r['key']: r['value'] for r in rows}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Iniciá sesión para continuar.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('user_role') not in ('admin', 'staff'):
            abort(403)
        return f(*args, **kwargs)
    return decorated

def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_globals():
    cats = query("SELECT * FROM categories WHERE active=1 ORDER BY sort_order")
    settings = get_settings()
    return dict(categories=cats, site=settings,
                current_user_id=session.get('user_id'),
                current_user_name=session.get('user_name'),
                current_user_role=session.get('user_role'))

# ──────────────────────────────────────────────
# AUTH ROUTES
# ──────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        pw    = hash_password(request.form.get('password', ''))
        user  = query("SELECT * FROM users WHERE email=? AND password=? AND active=1",
                      (email, pw), one=True)
        if user:
            session['user_id']   = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            if user['role'] in ('admin', 'staff'):
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        flash('Email o contraseña incorrectos.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/registro', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name  = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        pw    = request.form.get('password', '')
        if not name or not email or not pw:
            flash('Completá todos los campos.', 'error')
            return render_template('register.html')
        if query("SELECT id FROM users WHERE email=?", (email,), one=True):
            flash('Ese email ya está registrado.', 'error')
            return render_template('register.html')
        execute("INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
                (name, email, hash_password(pw), 'customer'))
        flash('¡Cuenta creada! Iniciá sesión.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# ──────────────────────────────────────────────
# PUBLIC ROUTES
# ──────────────────────────────────────────────
@app.route('/')
def index():
    featured   = query("SELECT p.*, c.name as cat_name, c.color, c.slug as cat_slug FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.featured=1 AND p.active=1 LIMIT 6")
    cats       = query("SELECT * FROM categories WHERE active=1 ORDER BY sort_order")
    news_items = query("SELECT * FROM news WHERE active=1 ORDER BY created_at DESC LIMIT 4")
    return render_template('index.html', featured=featured, cats=cats, news_items=news_items)

@app.route('/tienda')
def shop():
    cat_slug = request.args.get('cat', '')
    search   = request.args.get('q', '').strip()
    page     = max(1, int(request.args.get('page', 1)))
    per_page = 12

    sql    = "SELECT p.*, c.name as cat_name, c.color, c.slug as cat_slug FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.active=1"
    args   = []
    if cat_slug:
        sql += " AND c.slug=?"
        args.append(cat_slug)
    if search:
        sql += " AND (p.name LIKE ? OR p.description LIKE ?)"
        args += [f'%{search}%', f'%{search}%']

    total    = query(f"SELECT COUNT(*) as n FROM ({sql})", args, one=True)['n']
    sql     += f" ORDER BY p.featured DESC, p.name LIMIT {per_page} OFFSET {(page-1)*per_page}"
    products = query(sql, args)

    cats         = query("SELECT * FROM categories WHERE active=1 ORDER BY sort_order")
    total_pages  = (total + per_page - 1) // per_page
    current_cat  = query("SELECT * FROM categories WHERE slug=?", (cat_slug,), one=True) if cat_slug else None

    return render_template('shop.html', products=products, cats=cats,
                           cat_slug=cat_slug, search=search, page=page,
                           total_pages=total_pages, total=total,
                           current_cat=current_cat)

@app.route('/producto/<slug>')
def product_detail(slug):
    prod = query("""SELECT p.*, c.name as cat_name, c.color, c.slug as cat_slug, c.icon as cat_icon
                    FROM products p LEFT JOIN categories c ON p.category_id=c.id
                    WHERE p.slug=? AND p.active=1""", (slug,), one=True)
    if not prod:
        abort(404)
    related = query("""SELECT p.*, c.name as cat_name, c.color FROM products p
                       LEFT JOIN categories c ON p.category_id=c.id
                       WHERE p.category_id=? AND p.id!=? AND p.active=1 LIMIT 4""",
                    (prod['category_id'], prod['id']))
    return render_template('product.html', prod=prod, related=related)

@app.route('/empresa')
def empresa():
    return render_template('empresa.html')

@app.route('/novedades')
def novedades():
    news = query("SELECT * FROM news WHERE active=1 ORDER BY created_at DESC")
    return render_template('novedades.html', news=news)

@app.route('/contacto', methods=['GET', 'POST'])
def contacto():
    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        email   = request.form.get('email', '').strip()
        phone   = request.form.get('phone', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        if not name or not email or not message:
            flash('Completá los campos requeridos.', 'error')
        else:
            execute("INSERT INTO contacts (name,email,phone,subject,message) VALUES (?,?,?,?,?)",
                    (name, email, phone, subject, message))
            flash('¡Mensaje enviado! Te contactaremos pronto.', 'success')
            return redirect(url_for('contacto'))
    return render_template('contacto.html')

# ── Cart (session-based) ───────────────────────
@app.route('/api/cart', methods=['GET'])
def cart_get():
    return jsonify(session.get('cart', []))

@app.route('/api/cart/add', methods=['POST'])
def cart_add():
    data    = request.get_json()
    prod_id = data.get('id')
    prod    = query("SELECT * FROM products WHERE id=? AND active=1", (prod_id,), one=True)
    if not prod:
        return jsonify({'ok': False, 'msg': 'Producto no encontrado'})
    cart    = session.get('cart', [])
    for item in cart:
        if item['id'] == prod_id:
            item['qty'] += 1
            break
    else:
        cart.append({'id': prod_id, 'name': prod['name'], 'unit': prod['unit'],
                     'icon': prod['icon'], 'qty': 1})
    session['cart'] = cart
    session.modified = True
    return jsonify({'ok': True, 'cart': cart, 'count': sum(i['qty'] for i in cart)})

@app.route('/api/cart/remove', methods=['POST'])
def cart_remove():
    prod_id = request.get_json().get('id')
    cart    = [i for i in session.get('cart', []) if i['id'] != prod_id]
    session['cart'] = cart
    session.modified = True
    return jsonify({'ok': True, 'cart': cart, 'count': sum(i['qty'] for i in cart)})

@app.route('/api/cart/update', methods=['POST'])
def cart_update():
    data    = request.get_json()
    prod_id = data.get('id')
    qty     = int(data.get('qty', 1))
    cart    = session.get('cart', [])
    if qty <= 0:
        cart = [i for i in cart if i['id'] != prod_id]
    else:
        for item in cart:
            if item['id'] == prod_id:
                item['qty'] = qty
    session['cart'] = cart
    session.modified = True
    return jsonify({'ok': True, 'cart': cart, 'count': sum(i['qty'] for i in cart)})

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', [])
    if not cart:
        flash('Tu carrito está vacío.', 'warning')
        return redirect(url_for('shop'))
    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        email   = request.form.get('email', '').strip()
        phone   = request.form.get('phone', '').strip()
        company = request.form.get('company', '').strip()
        notes   = request.form.get('notes', '').strip()
        if not name or not email:
            flash('Completá nombre y email.', 'error')
            return render_template('checkout.html', cart=cart)
        user_id = session.get('user_id')
        execute("""INSERT INTO orders (user_id,name,email,phone,company,notes,items_json,total_items)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (user_id, name, email, phone, company, notes,
                 json.dumps(cart), sum(i['qty'] for i in cart)))
        session['cart'] = []
        session.modified = True
        flash('¡Pedido enviado! Nos contactaremos por email.', 'success')
        return redirect(url_for('index'))
    return render_template('checkout.html', cart=cart)

# ──────────────────────────────────────────────
# ADMIN ROUTES
# ──────────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin_dashboard():
    stats = {
        'products':  query("SELECT COUNT(*) as n FROM products WHERE active=1", one=True)['n'],
        'categories':query("SELECT COUNT(*) as n FROM categories WHERE active=1", one=True)['n'],
        'orders':    query("SELECT COUNT(*) as n FROM orders", one=True)['n'],
        'users':     query("SELECT COUNT(*) as n FROM users", one=True)['n'],
        'contacts':  query("SELECT COUNT(*) as n FROM contacts WHERE read=0", one=True)['n'],
        'news':      query("SELECT COUNT(*) as n FROM news WHERE active=1", one=True)['n'],
    }
    recent_orders   = query("SELECT * FROM orders ORDER BY created_at DESC LIMIT 8")
    recent_contacts = query("SELECT * FROM contacts ORDER BY created_at DESC LIMIT 6")
    return render_template('admin/dashboard.html', stats=stats,
                           recent_orders=recent_orders,
                           recent_contacts=recent_contacts)

# ── PRODUCTS ───────────────────────────────────
@app.route('/admin/productos')
@admin_required
def admin_products():
    search   = request.args.get('q', '').strip()
    cat_slug = request.args.get('cat', '')
    sql      = """SELECT p.*, c.name as cat_name, c.color FROM products p
                  LEFT JOIN categories c ON p.category_id=c.id WHERE 1=1"""
    args     = []
    if search:
        sql  += " AND (p.name LIKE ? OR p.description LIKE ?)"
        args += [f'%{search}%', f'%{search}%']
    if cat_slug:
        sql  += " AND c.slug=?"
        args.append(cat_slug)
    sql += " ORDER BY p.created_at DESC"
    products = query(sql, args)
    cats     = query("SELECT * FROM categories WHERE active=1 ORDER BY name")
    return render_template('admin/products.html', products=products, cats=cats,
                           search=search, cat_slug=cat_slug)

@app.route('/admin/productos/nuevo', methods=['GET', 'POST'])
@admin_required
def admin_product_new():
    cats = query("SELECT * FROM categories WHERE active=1 ORDER BY name")
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        desc     = request.form.get('description', '').strip()
        unit     = request.form.get('unit', '').strip()
        price    = request.form.get('price') or None
        stock    = int(request.form.get('stock', 0))
        cat_id   = request.form.get('category_id') or None
        icon     = request.form.get('icon', '📦').strip()
        featured = 1 if request.form.get('featured') else 0
        active   = 1 if request.form.get('active') else 0
        slug     = slugify(name)
        # Ensure unique slug
        base, n = slug, 1
        while query("SELECT id FROM products WHERE slug=?", (slug,), one=True):
            slug = f"{base}-{n}"; n += 1
        image = None
        f = request.files.get('image')
        if f and allowed_file(f.filename):
            fname = secure_filename(f"{slug}.{f.filename.rsplit('.',1)[1]}")
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            image = fname
        execute("""INSERT INTO products (name,slug,description,unit,price,stock,category_id,icon,featured,active,image)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (name, slug, desc, unit, price, stock, cat_id, icon, featured, active, image))
        flash(f'Producto "{name}" creado.', 'success')
        return redirect(url_for('admin_products'))
    return render_template('admin/product_form.html', cats=cats, prod=None)

@app.route('/admin/productos/<int:pid>/editar', methods=['GET', 'POST'])
@admin_required
def admin_product_edit(pid):
    prod = query("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if not prod:
        abort(404)
    cats = query("SELECT * FROM categories WHERE active=1 ORDER BY name")
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        desc     = request.form.get('description', '').strip()
        unit     = request.form.get('unit', '').strip()
        price    = request.form.get('price') or None
        stock    = int(request.form.get('stock', 0))
        cat_id   = request.form.get('category_id') or None
        icon     = request.form.get('icon', '📦').strip()
        featured = 1 if request.form.get('featured') else 0
        active   = 1 if request.form.get('active') else 0
        image    = prod['image']
        f = request.files.get('image')
        if f and allowed_file(f.filename):
            fname = secure_filename(f"{prod['slug']}.{f.filename.rsplit('.',1)[1]}")
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            image = fname
        execute("""UPDATE products SET name=?,description=?,unit=?,price=?,stock=?,
                   category_id=?,icon=?,featured=?,active=?,image=? WHERE id=?""",
                (name, desc, unit, price, stock, cat_id, icon, featured, active, image, pid))
        flash(f'Producto "{name}" actualizado.', 'success')
        return redirect(url_for('admin_products'))
    return render_template('admin/product_form.html', cats=cats, prod=prod)

@app.route('/admin/productos/<int:pid>/eliminar', methods=['POST'])
@admin_required
def admin_product_delete(pid):
    execute("UPDATE products SET active=0 WHERE id=?", (pid,))
    flash('Producto desactivado.', 'success')
    return redirect(url_for('admin_products'))

# ── CATEGORIES ─────────────────────────────────
@app.route('/admin/categorias')
@admin_required
def admin_categories():
    cats = query("""SELECT c.*, COUNT(p.id) as product_count
                    FROM categories c LEFT JOIN products p ON p.category_id=c.id AND p.active=1
                    GROUP BY c.id ORDER BY c.sort_order""")
    return render_template('admin/categories.html', cats=cats)

@app.route('/admin/categorias/nueva', methods=['GET', 'POST'])
@admin_required
def admin_category_new():
    if request.method == 'POST':
        name  = request.form.get('name', '').strip()
        desc  = request.form.get('description', '').strip()
        color = request.form.get('color', '#1a4a8a').strip()
        icon  = request.form.get('icon', '📦').strip()
        order = int(request.form.get('sort_order', 0))
        slug  = slugify(name)
        base, n = slug, 1
        while query("SELECT id FROM categories WHERE slug=?", (slug,), one=True):
            slug = f"{base}-{n}"; n += 1
        execute("INSERT INTO categories (name,slug,description,color,icon,sort_order) VALUES (?,?,?,?,?,?)",
                (name, slug, desc, color, icon, order))
        flash(f'Categoría "{name}" creada.', 'success')
        return redirect(url_for('admin_categories'))
    return render_template('admin/category_form.html', cat=None)

@app.route('/admin/categorias/<int:cid>/editar', methods=['GET', 'POST'])
@admin_required
def admin_category_edit(cid):
    cat = query("SELECT * FROM categories WHERE id=?", (cid,), one=True)
    if not cat:
        abort(404)
    if request.method == 'POST':
        name   = request.form.get('name', '').strip()
        desc   = request.form.get('description', '').strip()
        color  = request.form.get('color', '#1a4a8a').strip()
        icon   = request.form.get('icon', '📦').strip()
        order  = int(request.form.get('sort_order', 0))
        active = 1 if request.form.get('active') else 0
        execute("UPDATE categories SET name=?,description=?,color=?,icon=?,sort_order=?,active=? WHERE id=?",
                (name, desc, color, icon, order, active, cid))
        flash(f'Categoría "{name}" actualizada.', 'success')
        return redirect(url_for('admin_categories'))
    return render_template('admin/category_form.html', cat=cat)

@app.route('/admin/categorias/<int:cid>/eliminar', methods=['POST'])
@admin_required
def admin_category_delete(cid):
    execute("UPDATE categories SET active=0 WHERE id=?", (cid,))
    flash('Categoría desactivada.', 'success')
    return redirect(url_for('admin_categories'))

# ── USERS ──────────────────────────────────────
@app.route('/admin/usuarios')
@admin_required
def admin_users():
    users = query("SELECT * FROM users ORDER BY created_at DESC")
    return render_template('admin/users.html', users=users)

@app.route('/admin/usuarios/nuevo', methods=['GET', 'POST'])
@admin_required
def admin_user_new():
    if request.method == 'POST':
        name   = request.form.get('name', '').strip()
        email  = request.form.get('email', '').strip()
        pw     = request.form.get('password', '')
        role   = request.form.get('role', 'customer')
        active = 1 if request.form.get('active') else 0
        if query("SELECT id FROM users WHERE email=?", (email,), one=True):
            flash('Ese email ya existe.', 'error')
            return render_template('admin/user_form.html', user=None)
        execute("INSERT INTO users (name,email,password,role,active) VALUES (?,?,?,?,?)",
                (name, email, hash_password(pw), role, active))
        flash(f'Usuario "{name}" creado.', 'success')
        return redirect(url_for('admin_users'))
    return render_template('admin/user_form.html', user=None)

@app.route('/admin/usuarios/<int:uid>/editar', methods=['GET', 'POST'])
@admin_required
def admin_user_edit(uid):
    user = query("SELECT * FROM users WHERE id=?", (uid,), one=True)
    if not user:
        abort(404)
    if request.method == 'POST':
        name   = request.form.get('name', '').strip()
        email  = request.form.get('email', '').strip()
        role   = request.form.get('role', 'customer')
        active = 1 if request.form.get('active') else 0
        pw     = request.form.get('password', '').strip()
        if pw:
            execute("UPDATE users SET name=?,email=?,role=?,active=?,password=? WHERE id=?",
                    (name, email, role, active, hash_password(pw), uid))
        else:
            execute("UPDATE users SET name=?,email=?,role=?,active=? WHERE id=?",
                    (name, email, role, active, uid))
        flash(f'Usuario "{name}" actualizado.', 'success')
        return redirect(url_for('admin_users'))
    return render_template('admin/user_form.html', user=user)

@app.route('/admin/usuarios/<int:uid>/eliminar', methods=['POST'])
@super_admin_required
def admin_user_delete(uid):
    if uid == session.get('user_id'):
        flash('No podés eliminar tu propia cuenta.', 'error')
    else:
        execute("UPDATE users SET active=0 WHERE id=?", (uid,))
        flash('Usuario desactivado.', 'success')
    return redirect(url_for('admin_users'))

# ── ORDERS ─────────────────────────────────────
@app.route('/admin/pedidos')
@admin_required
def admin_orders():
    status  = request.args.get('status', '')
    sql     = "SELECT * FROM orders WHERE 1=1"
    args    = []
    if status:
        sql += " AND status=?"; args.append(status)
    sql    += " ORDER BY created_at DESC"
    orders  = query(sql, args)
    return render_template('admin/orders.html', orders=orders, status=status)

@app.route('/admin/pedidos/<int:oid>')
@admin_required
def admin_order_detail(oid):
    order = query("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    if not order:
        abort(404)
    items = json.loads(order['items_json'])
    return render_template('admin/order_detail.html', order=order, items=items)

@app.route('/admin/pedidos/<int:oid>/estado', methods=['POST'])
@admin_required
def admin_order_status(oid):
    status = request.form.get('status')
    valid  = ('pending','confirmed','shipped','delivered','cancelled')
    if status in valid:
        execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
        flash('Estado actualizado.', 'success')
    return redirect(url_for('admin_order_detail', oid=oid))

# ── NEWS ───────────────────────────────────────
@app.route('/admin/novedades')
@admin_required
def admin_news():
    news = query("SELECT * FROM news ORDER BY created_at DESC")
    return render_template('admin/news.html', news=news)

@app.route('/admin/novedades/nueva', methods=['GET', 'POST'])
@admin_required
def admin_news_new():
    if request.method == 'POST':
        title       = request.form.get('title', '').strip()
        summary     = request.form.get('summary', '').strip()
        content     = request.form.get('content', '').strip()
        badge       = request.form.get('badge', '').strip()
        badge_color = request.form.get('badge_color', 'badge-navy')
        icon        = request.form.get('icon', '📰').strip()
        active      = 1 if request.form.get('active') else 0
        slug        = slugify(title)
        base, n = slug, 1
        while query("SELECT id FROM news WHERE slug=?", (slug,), one=True):
            slug = f"{base}-{n}"; n += 1
        execute("INSERT INTO news (title,slug,summary,content,badge,badge_color,icon,active) VALUES (?,?,?,?,?,?,?,?)",
                (title, slug, summary, content, badge, badge_color, icon, active))
        flash(f'Novedad "{title}" creada.', 'success')
        return redirect(url_for('admin_news'))
    return render_template('admin/news_form.html', item=None)

@app.route('/admin/novedades/<int:nid>/editar', methods=['GET', 'POST'])
@admin_required
def admin_news_edit(nid):
    item = query("SELECT * FROM news WHERE id=?", (nid,), one=True)
    if not item:
        abort(404)
    if request.method == 'POST':
        title       = request.form.get('title', '').strip()
        summary     = request.form.get('summary', '').strip()
        content     = request.form.get('content', '').strip()
        badge       = request.form.get('badge', '').strip()
        badge_color = request.form.get('badge_color', 'badge-navy')
        icon        = request.form.get('icon', '📰').strip()
        active      = 1 if request.form.get('active') else 0
        execute("UPDATE news SET title=?,summary=?,content=?,badge=?,badge_color=?,icon=?,active=? WHERE id=?",
                (title, summary, content, badge, badge_color, icon, active, nid))
        flash(f'Novedad "{title}" actualizada.', 'success')
        return redirect(url_for('admin_news'))
    return render_template('admin/news_form.html', item=item)

@app.route('/admin/novedades/<int:nid>/eliminar', methods=['POST'])
@admin_required
def admin_news_delete(nid):
    execute("UPDATE news SET active=0 WHERE id=?", (nid,))
    flash('Novedad desactivada.', 'success')
    return redirect(url_for('admin_news'))

# ── CONTACTS ───────────────────────────────────
@app.route('/admin/contactos')
@admin_required
def admin_contacts():
    contacts = query("SELECT * FROM contacts ORDER BY created_at DESC")
    return render_template('admin/contacts.html', contacts=contacts)

@app.route('/admin/contactos/<int:cid>/leer', methods=['POST'])
@admin_required
def admin_contact_read(cid):
    execute("UPDATE contacts SET read=1 WHERE id=?", (cid,))
    return redirect(url_for('admin_contacts'))

@app.route('/admin/contactos/<int:cid>/eliminar', methods=['POST'])
@admin_required
def admin_contact_delete(cid):
    execute("DELETE FROM contacts WHERE id=?", (cid,))
    flash('Contacto eliminado.', 'success')
    return redirect(url_for('admin_contacts'))

# ── SETTINGS ───────────────────────────────────
@app.route('/admin/configuracion', methods=['GET', 'POST'])
@super_admin_required
def admin_settings():
    if request.method == 'POST':
        for key in ('site_name','site_phone','site_email','site_address',
                    'site_facebook','site_instagram'):
            val = request.form.get(key, '').strip()
            execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, val))
        flash('Configuración guardada.', 'success')
        return redirect(url_for('admin_settings'))
    settings = get_settings()
    return render_template('admin/settings.html', settings=settings)

# ── 403/404 ────────────────────────────────────
@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', code=403, msg="Acceso denegado"), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404, msg="Página no encontrada"), 404

# ──────────────────────────────────────────────
# INICIALIZAR DB — corre siempre (local y producción con gunicorn)
# ──────────────────────────────────────────────
with app.app_context():
    init_db()

# ──────────────────────────────────────────────
# MAIN (solo desarrollo local)
# ──────────────────────────────────────────────
if __name__ == '__main__':
    print("\n" + "="*50)
    print("  DIU — Droguería Industrial Uruguaya")
    print("  http://localhost:5000")
    print("  Admin: http://localhost:5000/admin")
    print(f"  Admin email: {ADMIN_EMAIL}")
    print("  (contraseña definida en variable ADMIN_PASSWORD)")
    print("="*50 + "\n")
    app.run(debug=True, port=5000)
