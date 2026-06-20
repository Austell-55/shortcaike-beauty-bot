import secrets
import sqlite3
import json
import csv
import re
import httpx
import smtplib
import asyncio
from email.message import EmailMessage
from datetime import datetime, timedelta
from io import StringIO
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext

# ========== Import from config ==========
from config import Config

WHATSAPP_PHONE_NUMBER_ID = Config.WHATSAPP_PHONE_NUMBER_ID
WHATSAPP_ACCESS_TOKEN = Config.WHATSAPP_ACCESS_TOKEN
VERIFY_TOKEN = Config.WHATSAPP_VERIFY_TOKEN

# ========== Database ==========
def get_db():
    conn = sqlite3.connect('messages.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # dashboard_users
    cur.execute('''
        CREATE TABLE IF NOT EXISTS dashboard_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT,
            email TEXT,
            role TEXT NOT NULL,
            pickup_station_id INTEGER,
            company_name TEXT,
            active INTEGER DEFAULT 1,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute("PRAGMA table_info(dashboard_users)")
    cols = [c[1] for c in cur.fetchall()]
    if 'pickup_station_id' not in cols:
        cur.execute("ALTER TABLE dashboard_users ADD COLUMN pickup_station_id INTEGER")
    if 'company_name' not in cols:
        cur.execute("ALTER TABLE dashboard_users ADD COLUMN company_name TEXT")
    if 'email' not in cols:
        cur.execute("ALTER TABLE dashboard_users ADD COLUMN email TEXT")

    # audit_logs
    cur.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_username TEXT,
            user_role TEXT,
            impersonated_role TEXT,
            action TEXT NOT NULL,
            details TEXT,
            field TEXT,
            old_value TEXT,
            new_value TEXT,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute("PRAGMA table_info(audit_logs)")
    audit_cols = [c[1] for c in cur.fetchall()]
    if 'field' not in audit_cols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN field TEXT")
    if 'old_value' not in audit_cols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN old_value TEXT")
    if 'new_value' not in audit_cols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN new_value TEXT")
    if 'impersonated_role' not in audit_cols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN impersonated_role TEXT")

    # orders (full schema with tracking columns)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            customer_phone TEXT,
            customer_name TEXT,
            items TEXT,
            total REAL,
            status TEXT DEFAULT 'pending_payment',
            payment_status TEXT DEFAULT 'unpaid',
            payment_method TEXT,
            receipt_url TEXT,
            delivery_type TEXT,
            address TEXT,
            pickup_station_id INTEGER,
            company_name TEXT,
            delivered_by INTEGER,
            delivered_at TIMESTAMP,
            tracking_status TEXT DEFAULT 'processing',
            gps_lat REAL,
            gps_lng REAL,
            eta TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute("PRAGMA table_info(orders)")
    order_cols = [c[1] for c in cur.fetchall()]
    if 'payment_method' not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT")
    if 'receipt_url' not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN receipt_url TEXT")
    if 'customer_phone' not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN customer_phone TEXT")
    if 'delivered_by' not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN delivered_by INTEGER")
    if 'delivered_at' not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN delivered_at TIMESTAMP")
    if 'address' not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN address TEXT")
    if 'tracking_status' not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN tracking_status TEXT DEFAULT 'processing'")
    if 'gps_lat' not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN gps_lat REAL")
    if 'gps_lng' not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN gps_lng REAL")
    if 'eta' not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN eta TEXT")

    # delivery_fees
    cur.execute('''
        CREATE TABLE IF NOT EXISTS delivery_fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT UNIQUE NOT NULL,
            fee REAL NOT NULL,
            active INTEGER DEFAULT 1
        )
    ''')
    # products (with concern column)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER DEFAULT 0,
            available INTEGER DEFAULT 1,
            concern TEXT
        )
    ''')
    # conversation_flags
    cur.execute('''
        CREATE TABLE IF NOT EXISTS conversation_flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_phone TEXT NOT NULL,
            flagged_by INTEGER,
            reason TEXT,
            resolved INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # pickup_stations
    cur.execute('''
        CREATE TABLE IF NOT EXISTS pickup_stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT
        )
    ''')
    # messages (bot schema)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP
        )
    ''')
    # customers
    cur.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            phone_number TEXT PRIMARY KEY,
            name TEXT,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP
        )
    ''')
    # cart (optional – not used by dashboard, but kept)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cart (
            user_id TEXT,
            product TEXT,
            quantity INTEGER,
            price REAL,
            PRIMARY KEY (user_id, product)
        )
    ''')

    # Insert default admin
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_admin = pwd.hash("admin123")
    cur.execute("INSERT OR IGNORE INTO dashboard_users (username, full_name, email, role, password_hash) VALUES (?,?,?,?,?)",
                ('admin', 'Administrator', 'admin@shortcaike.com', 'admin', hashed_admin))

    # Sample delivery fees
    cur.execute("INSERT OR IGNORE INTO delivery_fees (location, fee) VALUES ('Ikeja', 1000)")
    cur.execute("INSERT OR IGNORE INTO delivery_fees (location, fee) VALUES ('Lekki', 1500)")
    cur.execute("INSERT OR IGNORE INTO delivery_fees (location, fee) VALUES ('Abuja', 2000)")

    # Sample products with concerns
    cur.execute("INSERT OR IGNORE INTO products (name, price, stock, available, concern) VALUES ('Hydrating Serum', 7000, 20, 1, 'dry')")
    cur.execute("INSERT OR IGNORE INTO products (name, price, stock, available, concern) VALUES ('Brightening Face Cream', 5500, 15, 1, 'dull')")
    cur.execute("INSERT OR IGNORE INTO products (name, price, stock, available, concern) VALUES ('Acne Treatment Gel', 4500, 10, 1, 'acne')")
    cur.execute("INSERT OR IGNORE INTO products (name, price, stock, available, concern) VALUES ('Sunscreen SPF 50', 6000, 20, 1, 'sunburn')")
    cur.execute("INSERT OR IGNORE INTO products (name, price, stock, available, concern) VALUES ('Aloe Vera Gel', 3500, 15, 1, 'redness')")

    # Sample pickup stations
    cur.execute("INSERT OR IGNORE INTO pickup_stations (id, name, address) VALUES (1, 'Ikeja Station', '15 Bishop Street, Ikeja, Lagos')")
    cur.execute("INSERT OR IGNORE INTO pickup_stations (id, name, address) VALUES (2, 'Lekki Station', '5 Admiralty Way, Lekki Phase 1, Lagos')")

    conn.commit()
    conn.close()
    print("✅ Database initialized.")

init_db()

# ========== FastAPI Setup ==========
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="shortcaike_dashboard_2025")
templates = Jinja2Templates(directory="templates/dashboard")  # adjust if your templates are in 'dashboards'
app.mount("/static", StaticFiles(directory="static"), name="static")

# ========== Auth Helpers ==========
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_pw(pw): return pwd_ctx.hash(pw)
def verify_pw(plain, hashed): return pwd_ctx.verify(plain, hashed)

def get_user_by_username(username):
    with get_db() as conn:
        user = conn.execute("SELECT * FROM dashboard_users WHERE username = ?", (username,)).fetchone()
        return dict(user) if user else None

def authenticate_user(username, password):
    user = get_user_by_username(username)
    if user and verify_pw(password, user["password_hash"]) and user["active"] == 1:
        return user
    return None

def get_all_users():
    with get_db() as conn:
        return [dict(u) for u in conn.execute(
            "SELECT id, username, full_name, email, role, active, pickup_station_id, company_name FROM dashboard_users").fetchall()]

def create_user(username, full_name, email, role, password, pickup_station_id=None, company_name=None):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO dashboard_users (username, full_name, email, role, pickup_station_id, company_name, password_hash) VALUES (?,?,?,?,?,?,?)",
            (username, full_name, email, role, pickup_station_id, company_name, hash_pw(password))
        )
        conn.commit()

def deactivate_user(uid):
    with get_db() as conn:
        conn.execute("UPDATE dashboard_users SET active = 0 WHERE id = ?", (uid,))
        conn.commit()

def delete_user(uid):
    with get_db() as conn:
        conn.execute("DELETE FROM dashboard_users WHERE id = ?", (uid,))
        conn.commit()

def log_audit(user_id, username, user_role, action, details, ip, field=None, old_val=None, new_val=None, impersonated_role=None):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO audit_logs (user_id, user_username, user_role, impersonated_role, action, details, field, old_value, new_value, ip_address) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (user_id, username, user_role, impersonated_role, action, details, field, old_val, new_val, ip)
        )
        conn.commit()

def get_all_delivery_fees(active_only=True):
    with get_db() as conn:
        if active_only:
            fees = conn.execute("SELECT * FROM delivery_fees WHERE active=1").fetchall()
        else:
            fees = conn.execute("SELECT * FROM delivery_fees").fetchall()
        return [dict(f) for f in fees]

def add_delivery_fee(location, fee):
    with get_db() as conn:
        conn.execute("INSERT INTO delivery_fees (location, fee) VALUES (?,?)", (location, fee))
        conn.commit()

def delete_delivery_fee(fid):
    with get_db() as conn:
        conn.execute("DELETE FROM delivery_fees WHERE id = ?", (fid,))
        conn.commit()

def update_delivery_fee(fid, amount):
    with get_db() as conn:
        conn.execute("UPDATE delivery_fees SET fee = ? WHERE id = ?", (amount, fid))
        conn.commit()

def get_pickup_stations():
    with get_db() as conn:
        return [dict(s) for s in conn.execute("SELECT * FROM pickup_stations").fetchall()]

def add_pickup_station(name, address):
    with get_db() as conn:
        conn.execute("INSERT INTO pickup_stations (name, address) VALUES (?,?)", (name, address))
        conn.commit()

def delete_pickup_station(sid):
    with get_db() as conn:
        conn.execute("DELETE FROM pickup_stations WHERE id = ?", (sid,))
        conn.commit()

def update_pickup_station(sid, name, address):
    with get_db() as conn:
        conn.execute("UPDATE pickup_stations SET name = ?, address = ? WHERE id = ?", (name, address, sid))
        conn.commit()

def get_current_user(request: Request):
    return request.session.get("user")

# ========== WhatsApp Sending Helper (for Monitor manual replies) ==========
async def send_whatsapp_meta(to_phone: str, message: str):
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": False, "body": message}
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            print(f"Meta API error: {response.text}")
        else:
            print(f"WhatsApp send status: {response.status_code}")

# ========== Dashboard Routes ==========
@app.get("/dashboard/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/dashboard/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    request.session["user"] = {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"],
        "email": user.get("email"),
        "pickup_station_id": user.get("pickup_station_id"),
        "company_name": user.get("company_name"),
        "impersonated_role": None
    }
    log_audit(user["id"], user["username"], user["role"], "LOGIN", f"Logged in from {request.client.host}", request.client.host)
    return RedirectResponse("/dashboard/", 302)

@app.get("/dashboard/logout")
def logout(request: Request):
    user = get_current_user(request)
    if user:
        log_audit(user["id"], user["username"], user["role"], "LOGOUT", "", request.client.host)
    request.session.clear()
    return RedirectResponse("/dashboard/login")

@app.get("/dashboard/")
def dashboard_main(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/dashboard/login", 302)
    display_role = user.get("impersonated_role") or user["role"]
    return templates.TemplateResponse("all_dashboards.html", {"request": request, "user": {**user, "role": display_role}})

@app.get("/dashboard/switch_role")
def switch_role(request: Request, role: str):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    request.session["user"]["impersonated_role"] = role
    log_audit(user["id"], user["username"], user["role"], "SWITCH_ROLE", f"Switched to {role}", request.client.host, impersonated_role=role)
    return RedirectResponse("/dashboard/", 302)

# ========== Admin API Endpoints ==========
@app.get("/api/admin/users")
def api_admin_users(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    users = get_all_users()
    return JSONResponse({"users": users})

@app.post("/api/admin/add_user")
async def api_add_user(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    username = form.get("username")
    full_name = form.get("full_name")
    email = form.get("email")
    role = form.get("role")
    pickup_station_id = form.get("pickup_station_id") or None
    company_name = form.get("company_name") or None
    password = secrets.token_urlsafe(6)
    try:
        create_user(username, full_name, email, role, password, pickup_station_id, company_name)
        log_audit(user["id"], user["username"], user["role"], "ADD_USER", f"{username} ({role})", request.client.host)
        # Optionally send email invite (commented)
        return JSONResponse({"status": "ok", "password": password})
    except sqlite3.IntegrityError:
        return JSONResponse({"error": "Username already exists"}, 400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)

@app.post("/api/admin/deactivate_user")
async def api_deactivate_user(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    uid = int(form.get("user_id"))
    deactivate_user(uid)
    log_audit(user["id"], user["username"], user["role"], "DEACTIVATE_USER", str(uid), request.client.host)
    return JSONResponse({"status": "ok"})

@app.post("/api/admin/delete_user")
async def api_delete_user(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    uid = int(form.get("user_id"))
    delete_user(uid)
    log_audit(user["id"], user["username"], user["role"], "DELETE_USER", str(uid), request.client.host)
    return JSONResponse({"status": "ok"})

@app.get("/api/admin/fees")
def api_admin_fees(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    return JSONResponse(get_all_delivery_fees())

@app.post("/api/admin/add_fee")
async def api_add_fee(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    location = form.get("location")
    fee = float(form.get("fee"))
    add_delivery_fee(location, fee)
    log_audit(user["id"], user["username"], user["role"], "ADD_DELIVERY_FEE", location, request.client.host)
    return JSONResponse({"status": "ok"})

@app.post("/api/admin/remove_fee")
async def api_remove_fee(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    fid = int(form.get("fee_id"))
    delete_delivery_fee(fid)
    log_audit(user["id"], user["username"], user["role"], "REMOVE_DELIVERY_FEE", str(fid), request.client.host)
    return JSONResponse({"status": "ok"})

@app.post("/api/admin/update_fee")
async def api_update_fee(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    fid = int(form.get("fee_id"))
    amount = float(form.get("amount"))
    update_delivery_fee(fid, amount)
    log_audit(user["id"], user["username"], user["role"], "UPDATE_DELIVERY_FEE", f"fee {fid} to {amount}", request.client.host)
    return JSONResponse({"status": "ok"})

@app.get("/api/admin/pickup_stations")
def api_pickup_stations(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    return JSONResponse(get_pickup_stations())

@app.post("/api/admin/add_station")
async def api_add_station(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    name = form.get("station_name")
    address = form.get("address", "")
    add_pickup_station(name, address)
    log_audit(user["id"], user["username"], user["role"], "ADD_PICKUP_STATION", name, request.client.host)
    return JSONResponse({"status": "ok"})

@app.post("/api/admin/delete_station")
async def api_delete_station(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    sid = int(form.get("station_id"))
    delete_pickup_station(sid)
    log_audit(user["id"], user["username"], user["role"], "DELETE_PICKUP_STATION", str(sid), request.client.host)
    return JSONResponse({"status": "ok"})

@app.post("/api/admin/update_station")
async def api_update_station(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    sid = int(form.get("station_id"))
    name = form.get("name")
    address = form.get("address", "")
    update_pickup_station(sid, name, address)
    log_audit(user["id"], user["username"], user["role"], "UPDATE_PICKUP_STATION", f"{sid}: {name}", request.client.host)
    return JSONResponse({"status": "ok"})

@app.get("/api/admin/search")
def api_admin_search(request: Request, q: str):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return JSONResponse({"error": "Unauthorized"}, 403)
    with get_db() as conn:
        orders = conn.execute("SELECT * FROM orders WHERE order_id LIKE ? OR customer_name LIKE ?", (f"%{q}%", f"%{q}%")).fetchall()
    return JSONResponse([dict(o) for o in orders])

# ========== Sales API Endpoints ==========
@app.get("/api/sales/products")
def api_sales_products(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["sales", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    with get_db() as conn:
        products = conn.execute("SELECT * FROM products").fetchall()
    return JSONResponse([dict(p) for p in products])

@app.post("/api/sales/update_product")
async def api_update_product(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["sales", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    pid = int(form.get("product_id"))
    available = form.get("available") == "on"
    stock = int(form.get("stock"))
    with get_db() as conn:
        old = conn.execute("SELECT stock, available FROM products WHERE id=?", (pid,)).fetchone()
        conn.execute("UPDATE products SET available=?, stock=? WHERE id=?", (1 if available else 0, stock, pid))
        conn.commit()
        log_audit(user["id"], user["username"], user["role"], "UPDATE_PRODUCT", f"id {pid}", request.client.host,
                  field="stock/available", old_val=f"stock={old['stock']},avail={old['available']}", new_val=f"stock={stock},avail={available}")
    return JSONResponse({"status": "ok"})

@app.get("/api/sales/orders")
def api_sales_orders(request: Request, status: str = None):
    user = get_current_user(request)
    if not user or user["role"] not in ["sales", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    with get_db() as conn:
        if status and status != "all":
            if status == "pending_availability":
                orders = conn.execute("SELECT * FROM orders WHERE status='pending_availability'").fetchall()
                return JSONResponse({"pending_avail": [dict(o) for o in orders], "awaiting_payment": [], "delivered_confirm": [], "completed": []})
            elif status == "awaiting_payment":
                orders = conn.execute("SELECT * FROM orders WHERE status='awaiting_payment'").fetchall()
                return JSONResponse({"pending_avail": [], "awaiting_payment": [dict(o) for o in orders], "delivered_confirm": [], "completed": []})
            elif status == "delivered_waiting_confirm":
                orders = conn.execute("SELECT * FROM orders WHERE status='delivered_waiting_confirm'").fetchall()
                return JSONResponse({"pending_avail": [], "awaiting_payment": [], "delivered_confirm": [dict(o) for o in orders], "completed": []})
            elif status == "completed":
                orders = conn.execute("SELECT * FROM orders WHERE status='completed'").fetchall()
                return JSONResponse({"pending_avail": [], "awaiting_payment": [], "delivered_confirm": [], "completed": [dict(o) for o in orders]})
        pending_avail = conn.execute("SELECT * FROM orders WHERE status='pending_availability'").fetchall()
        awaiting_payment = conn.execute("SELECT * FROM orders WHERE status='awaiting_payment'").fetchall()
        delivered_confirm = conn.execute("SELECT * FROM orders WHERE status='delivered_waiting_confirm'").fetchall()
        completed = conn.execute("SELECT * FROM orders WHERE status='completed'").fetchall()
    return JSONResponse({
        "pending_avail": [dict(o) for o in pending_avail],
        "awaiting_payment": [dict(o) for o in awaiting_payment],
        "delivered_confirm": [dict(o) for o in delivered_confirm],
        "completed": [dict(o) for o in completed]
    })

@app.post("/api/sales/confirm_availability")
async def api_confirm_availability(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["sales", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    order_id = form.get("order_id")
    with get_db() as conn:
        order = conn.execute("SELECT status, customer_phone, customer_name, total FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if not order:
            return JSONResponse({"error": "Order not found"}, 404)
        old_status = order["status"]
        if old_status != "pending_availability":
            return JSONResponse({"status": "ok", "message": "Order already confirmed"})
        conn.execute("UPDATE orders SET status='awaiting_payment' WHERE order_id=?", (order_id,))
        conn.commit()
        log_audit(user["id"], user["username"], user["role"], "CONFIRM_AVAILABILITY", order_id, request.client.host,
                  field="status", old_val=old_status, new_val="awaiting_payment")
        if order["customer_phone"]:
            msg = f"Your order {order_id} (₦{order['total']}) is now ready for payment. How would you like to pay?\n1. Bank Transfer\n2. Cash on Delivery\n3. Card Payment"
            await send_whatsapp_meta(order["customer_phone"], msg)
    return JSONResponse({"status": "ok"})

@app.post("/api/sales/confirm_payment")
async def api_confirm_payment(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["sales", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    order_id = form.get("order_id")
    with get_db() as conn:
        order = conn.execute("SELECT status, payment_status, customer_phone, customer_name, total, items FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if not order:
            return JSONResponse({"error": "Order not found"}, 404)
        old_status = order["status"]
        old_payment = order["payment_status"]
        if old_payment == "paid":
            return JSONResponse({"status": "ok", "message": "Payment already confirmed"})
        conn.execute("UPDATE orders SET status='ready_for_delivery', payment_status='paid' WHERE order_id=?", (order_id,))
        # Deduct stock
        items = json.loads(order["items"])
        for item in items:
            product_name = item["name"]
            qty = int(item["quantity"])
            conn.execute("UPDATE products SET stock = stock - ? WHERE name = ? AND stock >= ?", (qty, product_name, qty))
        conn.commit()
        log_audit(user["id"], user["username"], user["role"], "CONFIRM_PAYMENT", order_id, request.client.host,
                  field="status/payment", old_val=f"status={old_status},payment={old_payment}", new_val="status=ready_for_delivery,payment=paid")
        if order["customer_phone"]:
            msg = f"✅ Payment confirmed for order {order_id}.\n\nHere is your order ID: {order_id}\nYou can use this ID to track your delivery.\nYour order will be delivered to the address you provided.\nThank you for shopping with Shortcaike Beauty Stores!"
            await send_whatsapp_meta(order["customer_phone"], msg)
    return JSONResponse({"status": "ok"})

@app.post("/api/sales/double_confirm")
async def api_double_confirm(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["sales", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    order_id = form.get("order_id")
    with get_db() as conn:
        order = conn.execute("SELECT status, customer_phone, customer_name FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if not order:
            return JSONResponse({"error": "Order not found"}, 404)
        old_status = order["status"]
        conn.execute("UPDATE orders SET status='completed' WHERE order_id=?", (order_id,))
        conn.commit()
        log_audit(user["id"], user["username"], user["role"], "DOUBLE_CONFIRM_DELIVERY", order_id, request.client.host,
                  field="status", old_val=old_status, new_val="completed")
        if order["customer_phone"]:
            msg = f"Thank you for shopping with Shortcaike Beauty Stores. Your order {order_id} has been marked as delivered. We hope you love your products! Please share your feedback."
            await send_whatsapp_meta(order["customer_phone"], msg)
    return JSONResponse({"status": "ok"})

# ========== Delivery API Endpoints ==========
@app.get("/api/delivery/orders")
def api_delivery_orders(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["delivery", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    with get_db() as conn:
        pending = conn.execute("SELECT * FROM orders WHERE status='ready_for_delivery'").fetchall()
        transit = conn.execute("SELECT * FROM orders WHERE status='out_for_delivery' AND delivered_by=?", (user["id"],)).fetchall()
    return JSONResponse({"pending": [dict(o) for o in pending], "transit": [dict(o) for o in transit]})

@app.get("/api/delivery/history")
def api_delivery_history(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["delivery", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    with get_db() as conn:
        history = conn.execute("SELECT order_id, customer_name, delivered_at FROM orders WHERE delivered_by=? AND status IN ('completed','delivered') ORDER BY delivered_at DESC", (user["id"],)).fetchall()
    return JSONResponse([dict(h) for h in history])

@app.post("/api/delivery/start")
async def api_start_delivery(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["delivery", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    order_id = form.get("order_id")
    with get_db() as conn:
        old = conn.execute("SELECT status FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if not old:
            return JSONResponse({"error": "Order not found"}, 404)
        conn.execute("UPDATE orders SET status='out_for_delivery', delivered_by=? WHERE order_id=?", (user["id"], order_id))
        conn.commit()
        log_audit(user["id"], user["username"], user["role"], "START_DELIVERY", order_id, request.client.host,
                  field="status", old_val=old["status"], new_val="out_for_delivery")
    return JSONResponse({"status": "ok"})

@app.post("/api/delivery/mark_delivered")
async def api_mark_delivered(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["delivery", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    order_id = form.get("order_id")
    with get_db() as conn:
        old = conn.execute("SELECT status FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if not old:
            return JSONResponse({"error": "Order not found"}, 404)
        conn.execute("UPDATE orders SET status='delivered_waiting_confirm', delivered_at=CURRENT_TIMESTAMP WHERE order_id=?", (order_id,))
        conn.commit()
        log_audit(user["id"], user["username"], user["role"], "MARK_DELIVERED", order_id, request.client.host,
                  field="status", old_val=old["status"], new_val="delivered_waiting_confirm")
    return JSONResponse({"status": "ok"})

@app.post("/api/delivery/update_gps")
async def api_update_gps(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["delivery", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    data = await request.json()
    lat = data.get("lat")
    lng = data.get("lng")
    log_audit(user["id"], user["username"], user["role"], "UPDATE_GPS", f"{lat},{lng}", request.client.host)
    return JSONResponse({"status": "ok"})

# ========== Monitor API Endpoints ==========
@app.get("/api/monitor/conversations")
def api_monitor_conversations(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["monitor", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    with get_db() as conn:
        convs = conn.execute("""
            SELECT m.user_id as customer_phone, c.name as customer_name,
                   (SELECT content FROM messages WHERE user_id = m.user_id ORDER BY timestamp DESC LIMIT 1) as last_msg
            FROM messages m
            LEFT JOIN customers c ON m.user_id = c.phone_number
            WHERE m.user_id IS NOT NULL
            GROUP BY m.user_id
            ORDER BY MAX(m.timestamp) DESC
        """).fetchall()
    return JSONResponse([dict(c) for c in convs])

@app.get("/api/monitor/flagged")
def api_monitor_flagged(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["monitor", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    with get_db() as conn:
        flagged = conn.execute("""
            SELECT f.id, f.customer_phone, f.reason, c.name as customer_name
            FROM conversation_flags f
            LEFT JOIN customers c ON f.customer_phone = c.phone_number
            WHERE f.resolved = 0
        """).fetchall()
    return JSONResponse([dict(f) for f in flagged])

@app.get("/api/monitor/conversation/{customer_phone}")
def api_get_conversation(customer_phone: str, request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["monitor", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    with get_db() as conn:
        msgs = conn.execute("SELECT role as direction, content as body, timestamp as created_at FROM messages WHERE user_id = ? ORDER BY timestamp", (customer_phone,)).fetchall()
    return JSONResponse([dict(m) for m in msgs])

@app.post("/api/monitor/send_reply")
async def api_monitor_send_reply(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["monitor", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    customer_phone = form.get("customer_phone")
    message = form.get("message")
    if not customer_phone or not message:
        return JSONResponse({"error": "Missing phone or message"}, 400)
    await send_whatsapp_meta(customer_phone, message)
    with get_db() as conn:
        conn.execute("INSERT INTO messages (user_id, role, content, timestamp) VALUES (?, 'assistant', ?, ?)",
                     (customer_phone, message, datetime.utcnow().isoformat()))
        conn.commit()
        log_audit(user["id"], user["username"], user["role"], "MANUAL_REPLY", f"To {customer_phone}: {message[:50]}", request.client.host)
    return JSONResponse({"status": "ok"})

@app.post("/api/monitor/flag")
async def api_monitor_flag(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["monitor", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    customer_phone = form.get("customer_phone")
    reason = form.get("reason")
    if not customer_phone:
        return JSONResponse({"error": "Missing customer phone"}, 400)
    with get_db() as conn:
        conn.execute("INSERT INTO conversation_flags (customer_phone, flagged_by, reason) VALUES (?,?,?)", (customer_phone, user["id"], reason))
        conn.commit()
        log_audit(user["id"], user["username"], user["role"], "FLAG_CONVERSATION", f"customer {customer_phone}: {reason}", request.client.host)
    return JSONResponse({"status": "ok"})

# ========== Security API Endpoints ==========
@app.get("/api/security/audit_logs")
def api_audit_logs(request: Request, action: str = None, user: str = None, from_date: str = None, to_date: str = None):
    user_obj = get_current_user(request)
    if not user_obj or user_obj["role"] not in ["security", "admin", "sales"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = []
    if action:
        query += " AND action = ?"
        params.append(action)
    if user:
        query += " AND user_username = ?"
        params.append(user)
    if from_date:
        query += " AND date(timestamp) >= ?"
        params.append(from_date)
    if to_date:
        query += " AND date(timestamp) <= ?"
        params.append(to_date)
    query += " ORDER BY timestamp DESC LIMIT 200"
    with get_db() as conn:
        logs = conn.execute(query, params).fetchall()
    return JSONResponse([dict(l) for l in logs])

@app.get("/api/security/export")
def api_export_audit(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["security", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    with get_db() as conn:
        logs = conn.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC").fetchall()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "user_username", "action", "details", "field", "old_value", "new_value", "ip_address", "timestamp"])
    for row in logs:
        writer.writerow([row["id"], row["user_username"], row["action"], row["details"], row["field"], row["old_value"], row["new_value"], row["ip_address"], row["timestamp"]])
    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=audit_logs.csv"
    return response

# ========== Auditor API Endpoints ==========
@app.get("/api/auditor/orders")
def api_auditor_orders(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["auditor", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    with get_db() as conn:
        orders = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    return JSONResponse([dict(o) for o in orders])

@app.get("/api/auditor/audit_trail")
def api_audit_trail(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["auditor", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    with get_db() as conn:
        trail = conn.execute("SELECT * FROM audit_logs WHERE action LIKE '%DELIVERY%' OR action LIKE '%CONFIRM%' OR action LIKE '%UPDATE%' ORDER BY timestamp DESC").fetchall()
    return JSONResponse([dict(t) for t in trail])

@app.post("/api/auditor/verify")
async def api_verify_order(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["auditor", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    order_id = form.get("order_id")
    log_audit(user["id"], user["username"], user["role"], "VERIFY_ORDER", f"Order {order_id} verified", request.client.host)
    return JSONResponse({"status": "ok"})

@app.get("/api/auditor/export_orders")
def api_export_orders(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["auditor", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    with get_db() as conn:
        orders = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["order_id", "customer_name", "items", "total", "status", "payment_status", "created_at"])
    for row in orders:
        writer.writerow([row["order_id"], row["customer_name"], row["items"], row["total"], row["status"], row["payment_status"], row["created_at"]])
    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=orders.csv"
    return response

# ========== Pickup Staff API Endpoints ==========
@app.get("/api/pickup/orders")
def api_pickup_orders(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["pickup_staff", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    station_id = user.get("pickup_station_id")
    if not station_id:
        return JSONResponse({"error": "No pickup station assigned"}, 400)
    with get_db() as conn:
        orders = conn.execute("SELECT * FROM orders WHERE pickup_station_id=? AND delivery_type='pickup' AND status != 'completed'", (station_id,)).fetchall()
    return JSONResponse([dict(o) for o in orders])

@app.get("/api/pickup/completed")
def api_pickup_completed(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["pickup_staff", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    station_id = user.get("pickup_station_id")
    if not station_id:
        return JSONResponse({"error": "No pickup station assigned"}, 400)
    with get_db() as conn:
        orders = conn.execute("SELECT * FROM orders WHERE pickup_station_id=? AND delivery_type='pickup' AND status='completed'", (station_id,)).fetchall()
    return JSONResponse([dict(o) for o in orders])

@app.post("/api/pickup/ready")
async def api_pickup_ready(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["pickup_staff", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    order_id = form.get("order_id")
    # Here you could set a flag 'pickup_ready' in orders table
    log_audit(user["id"], user["username"], user["role"], "PICKUP_READY", order_id, request.client.host)
    return JSONResponse({"status": "ok"})

@app.post("/api/pickup/picked")
async def api_pickup_picked(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["pickup_staff", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    order_id = form.get("order_id")
    with get_db() as conn:
        old = conn.execute("SELECT status FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if not old:
            return JSONResponse({"error": "Order not found"}, 404)
        conn.execute("UPDATE orders SET status='completed' WHERE order_id=?", (order_id,))
        conn.commit()
        log_audit(user["id"], user["username"], user["role"], "PICKUP_COMPLETED", order_id, request.client.host,
                  field="status", old_val=old["status"], new_val="completed")
    return JSONResponse({"status": "ok"})

# ========== Company Coordinator API Endpoints ==========
@app.get("/api/company/orders")
def api_company_orders(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["company_coordinator", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    company = user.get("company_name")
    if not company:
        return JSONResponse({"error": "No company assigned"}, 400)
    with get_db() as conn:
        orders = conn.execute("SELECT * FROM orders WHERE company_name=? AND delivery_type='company' AND status != 'completed'", (company,)).fetchall()
    return JSONResponse([dict(o) for o in orders])

@app.get("/api/company/received")
def api_company_received(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["company_coordinator", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    company = user.get("company_name")
    if not company:
        return JSONResponse({"error": "No company assigned"}, 400)
    with get_db() as conn:
        orders = conn.execute("SELECT * FROM orders WHERE company_name=? AND delivery_type='company' AND status='completed'", (company,)).fetchall()
    return JSONResponse([dict(o) for o in orders])

@app.post("/api/company/receive")
async def api_company_receive(request: Request):
    user = get_current_user(request)
    if not user or user["role"] not in ["company_coordinator", "admin"]:
        return JSONResponse({"error": "Unauthorized"}, 403)
    form = await request.form()
    order_id = form.get("order_id")
    with get_db() as conn:
        old = conn.execute("SELECT status FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if not old:
            return JSONResponse({"error": "Order not found"}, 404)
        conn.execute("UPDATE orders SET status='completed', payment_status='paid' WHERE order_id=?", (order_id,))
        conn.commit()
        log_audit(user["id"], user["username"], user["role"], "COMPANY_RECEIVED", order_id, request.client.host,
                  field="status", old_val=old["status"], new_val="completed")
    return JSONResponse({"status": "ok"})

# ========== Order Details ==========
@app.get("/api/orders/{order_id}/details")
def api_order_details(order_id: str, request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, 403)
    with get_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if not order:
            return JSONResponse({"error": "Order not found"}, 404)
        return JSONResponse(dict(order))

# ========== WhatsApp Webhook ==========
# Import the webhook handler from webhook.py (the bot logic)
from webhook import handle_whatsapp

@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode and token and mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, status_code=200)
    return Response(content="Forbidden", status_code=403)

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    return await handle_whatsapp(request)

# ========== Run ==========
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=True)