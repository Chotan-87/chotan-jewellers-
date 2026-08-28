from functools import wraps
from pathlib import Path
import sqlite3

from flask import Flask, g, render_template, request, redirect, session, url_for


app = Flask(__name__)
app.secret_key = "amine-jewellers-secret-key"

DATABASE = Path(__file__).with_name("database.db")


# =========================
# DATABASE CONNECTION
# =========================

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# =========================
# DATABASE TABLES
# =========================

def create_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            mobile TEXT NOT NULL,
            address TEXT,
            age INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS gold_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            karat TEXT UNIQUE NOT NULL,
            rate REAL NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS gold_stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            karat TEXT NOT NULL,
            weight REAL NOT NULL,
            quantity INTEGER NOT NULL,
            purchase_rate REAL NOT NULL,
            total_value REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            mobile TEXT,
            karat TEXT NOT NULL,
            weight REAL NOT NULL,
            rate REAL NOT NULL,
            gold_value REAL NOT NULL,
            making REAL NOT NULL,
            bat REAL NOT NULL,
            stone REAL NOT NULL,
            vat REAL NOT NULL,
            grand_total REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_id INTEGER,
            customer_name TEXT NOT NULL,
            mobile TEXT,
            item_details TEXT NOT NULL,
            weight REAL,
            amount REAL NOT NULL,
            interest_rate REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS loan_vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            mobile TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS buy_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            mobile TEXT,
            item_details TEXT NOT NULL,
            grade TEXT NOT NULL,
            bhori_weight REAL NOT NULL DEFAULT 0,
            ana_weight REAL NOT NULL DEFAULT 0,
            estimated_price REAL NOT NULL DEFAULT 0,
            advance_paid REAL NOT NULL DEFAULT 0,
            delivery_date TEXT,
            special_requests TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def run_migrations(conn):
    loan_columns = {row["name"] for row in conn.execute("PRAGMA table_info(loans)")}
    if "voucher_id" not in loan_columns:
        conn.execute("ALTER TABLE loans ADD COLUMN voucher_id INTEGER")

    stock_columns = {row["name"] for row in conn.execute("PRAGMA table_info(gold_stock)")}
    if "serial_no" not in stock_columns:
        conn.execute("ALTER TABLE gold_stock ADD COLUMN serial_no TEXT")


def seed_default_rates(conn):
    default_rates = [
        ("24K", 201818),
        ("22K", 185000),
        ("21K", 176500),
        ("18K", 151364)
    ]

    for karat, rate in default_rates:
        conn.execute("""
            INSERT OR IGNORE INTO gold_rates (karat, rate)
            VALUES (?, ?)
        """, (karat, rate))


def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    run_migrations(conn)
    seed_default_rates(conn)
    conn.commit()
    conn.close()


# =========================
# AUTH DECORATOR
# =========================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function


# =========================
# LOGIN
# =========================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "1234":
            session["user"] = username
            return redirect("/dashboard")

        return render_template(
            "login.html",
            error="Username অথবা Password ভুল!"
        )

    return render_template("login.html")


# =========================
# DASHBOARD
# =========================

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()

    customer_count = conn.execute(
        "SELECT COUNT(*) FROM customers"
    ).fetchone()[0]

    stock_count = conn.execute(
        "SELECT COUNT(*) FROM gold_stock"
    ).fetchone()[0]

    today_sales = conn.execute("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM invoices
        WHERE DATE(created_at) = DATE('now', 'localtime')
    """).fetchone()[0]

    invoice_count = conn.execute(
        "SELECT COUNT(*) FROM invoices"
    ).fetchone()[0]

    return render_template(
        "dashboard.html",
        username=session["user"],
        customer_count=customer_count,
        stock_count=stock_count,
        today_sales=today_sales,
        invoice_count=invoice_count
    )


# =========================
# CUSTOMER LIST
# =========================

@app.route("/customers")
@login_required
def customers():
    search = request.args.get("search", "").strip()
    conn = get_db()

    if search:
        customer_list = conn.execute("""
            SELECT *
            FROM customers
            WHERE name LIKE ?
               OR mobile LIKE ?
            ORDER BY id DESC
        """, (
            "%" + search + "%",
            "%" + search + "%"
        )).fetchall()
    else:
        customer_list = conn.execute("""
            SELECT *
            FROM customers
            ORDER BY id DESC
        """).fetchall()

    return render_template(
        "customer.html",
        customers=customer_list,
        search=search
    )


# =========================
# ADD CUSTOMER
# =========================

@app.route("/customer/add", methods=["POST"])
@login_required
def add_customer():
    name = request.form.get("name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    address = request.form.get("address", "").strip()
    age = request.form.get("age", "").strip() or None

    if not name or not mobile:
        return redirect("/customers")

    conn = get_db()

    conn.execute("""
        INSERT INTO customers (name, mobile, address, age)
        VALUES (?, ?, ?, ?)
    """, (name, mobile, address, age))

    conn.commit()

    return redirect("/customers")


# =========================
# DELETE CUSTOMER
# =========================

@app.route("/customer/delete/<int:customer_id>", methods=["GET", "POST"])
@login_required
def delete_customer(customer_id):
    conn = get_db()

    conn.execute(
        "DELETE FROM customers WHERE id = ?",
        (customer_id,)
    )

    conn.commit()

    return redirect(url_for("customers"))


# =========================
# GOLD STOCK
# =========================

@app.route("/gold-stock", methods=["GET", "POST"])
@login_required
def gold_stock():
    conn = get_db()

    if request.method == "POST":
        item_name = request.form.get("item_name", "").strip()
        karat = request.form.get("karat", "").strip()
        serial_no = request.form.get("serial_no", "").strip()

        try:
            weight = float(request.form.get("weight") or 0)
            quantity = int(request.form.get("quantity") or 0)
            purchase_rate = float(request.form.get("purchase_rate") or 0)
        except ValueError:
            weight = quantity = purchase_rate = 0

        total_value = weight * quantity * purchase_rate

        if not serial_no:
            count = conn.execute("SELECT COUNT(*) FROM gold_stock").fetchone()[0] + 1
            serial_no = f"GS-2026-{count:04d}"

        if item_name and karat and weight > 0 and quantity > 0:
            conn.execute("""
                INSERT INTO gold_stock (
                    serial_no,
                    item_name,
                    karat,
                    weight,
                    quantity,
                    purchase_rate,
                    total_value
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                serial_no,
                item_name,
                karat,
                weight,
                quantity,
                purchase_rate,
                total_value
            ))

            conn.commit()
            return redirect(url_for("gold_stock"))

    stocks = conn.execute("""
        SELECT *
        FROM gold_stock
        ORDER BY id DESC
    """).fetchall()

    return render_template(
        "gold_stock.html",
        stocks=stocks
    )


@app.route("/gold-stock/delete/<int:stock_id>", methods=["GET", "POST"])
@login_required
def delete_gold_stock(stock_id):
    conn = get_db()
    conn.execute("DELETE FROM gold_stock WHERE id = ?", (stock_id,))
    conn.commit()

    return redirect(url_for("gold_stock"))


# =========================
# LOANS
# =========================

@app.route("/loans", methods=["GET", "POST"])
@login_required
def loans():
    conn = get_db()

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        item_details = request.form.get("item_details", "").strip()

        try:
            weight = float(request.form.get("weight") or 0)
            amount = float(request.form.get("amount") or 0)
            interest_rate = float(request.form.get("interest_rate") or 0)
        except ValueError:
            weight = amount = interest_rate = 0

        if customer_name and item_details and amount > 0 and weight >= 0 and interest_rate >= 0:
            voucher = conn.execute("""
                SELECT id, mobile
                FROM loan_vouchers
                WHERE customer_name = ? COLLATE NOCASE
                   OR (? != '' AND mobile = ?)
            """, (customer_name, mobile, mobile)).fetchone()

            if voucher is None:
                cursor = conn.execute("""
                    INSERT INTO loan_vouchers (customer_name, mobile)
                    VALUES (?, ?)
                """, (customer_name, mobile))
                voucher_id = cursor.lastrowid
            else:
                voucher_id = voucher["id"]
                if mobile and not voucher["mobile"]:
                    conn.execute(
                        "UPDATE loan_vouchers SET mobile = ? WHERE id = ?",
                        (mobile, voucher_id)
                    )

            conn.execute("""
                INSERT INTO loans (
                    voucher_id, customer_name, mobile, item_details, weight, amount, interest_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                voucher_id, customer_name, mobile, item_details,
                weight, amount, interest_rate
            ))
            conn.commit()
            return redirect(url_for("loans"))

    loan_list = conn.execute("SELECT * FROM loans ORDER BY id DESC").fetchall()

    total_active_loan = conn.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM loans WHERE status = 'Active'
    """).fetchone()[0]

    total_interest = conn.execute("""
        SELECT COALESCE(SUM(amount * interest_rate / 100), 0) FROM loans WHERE status = 'Active'
    """).fetchone()[0]

    return render_template(
        "loan.html",
        loans=loan_list,
        total_active_loan=total_active_loan,
        total_interest=total_interest
    )


@app.route("/loan-voucher/<int:voucher_id>")
@login_required
def loan_voucher(voucher_id):
    conn = get_db()
    voucher = conn.execute(
        "SELECT * FROM loan_vouchers WHERE id = ?", (voucher_id,)
    ).fetchone()

    if voucher is None:
        return redirect("/loans")

    entries = conn.execute("""
        SELECT * FROM loans
        WHERE voucher_id = ?
        ORDER BY id DESC
    """, (voucher_id,)).fetchall()
    totals = conn.execute("""
        SELECT
            COALESCE(SUM(amount), 0) AS amount,
            COALESCE(SUM(amount * interest_rate / 100), 0) AS interest
        FROM loans
        WHERE voucher_id = ? AND status = 'Active'
    """, (voucher_id,)).fetchone()

    return render_template(
        "loan_voucher.html", voucher=voucher, loans=entries, totals=totals
    )


@app.route("/loans/delete/<int:loan_id>", methods=["GET", "POST"])
@login_required
def delete_loan(loan_id):
    conn = get_db()
    conn.execute("DELETE FROM loans WHERE id = ?", (loan_id,))
    conn.commit()
    return redirect(url_for("loans"))


# =========================
# BUY NOW ORDERS
# =========================

@app.route("/buy-now", methods=["GET", "POST"])
@login_required
def buy_now():
    conn = get_db()

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        item_details = request.form.get("item_details", "").strip()
        grade = request.form.get("grade", "22K Gold").strip()
        delivery_date = request.form.get("delivery_date", "").strip()
        special_requests = request.form.get("special_requests", "").strip()

        try:
            bhori_weight = float(request.form.get("bhori_weight") or 0)
            ana_weight = float(request.form.get("ana_weight") or 0)
            estimated_price = float(request.form.get("estimated_price") or 0)
            advance_paid = float(request.form.get("advance_paid") or 0)
        except ValueError:
            bhori_weight = ana_weight = estimated_price = advance_paid = 0

        if customer_name and item_details and estimated_price >= 0 and advance_paid >= 0:
            conn.execute("""
                INSERT INTO buy_orders (
                    customer_name, mobile, item_details, grade, bhori_weight,
                    ana_weight, estimated_price, advance_paid, delivery_date,
                    special_requests
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                customer_name, mobile, item_details, grade, bhori_weight,
                ana_weight, estimated_price, advance_paid, delivery_date,
                special_requests
            ))
            conn.commit()
            return redirect(url_for("buy_now"))

    orders = conn.execute("SELECT * FROM buy_orders ORDER BY id DESC").fetchall()
    return render_template("buy_now.html", orders=orders)


@app.route("/buy-now/delete/<int:order_id>", methods=["GET", "POST"])
@login_required
def delete_buy_order(order_id):
    conn = get_db()
    conn.execute("DELETE FROM buy_orders WHERE id = ?", (order_id,))
    conn.commit()
    return redirect(url_for("buy_now"))


# =========================
# CALCULATOR
# =========================

@app.route("/calculator", methods=["GET", "POST"])
@login_required
def calculator():
    conn = get_db()

    rates = conn.execute("""
        SELECT karat, rate
        FROM gold_rates
        ORDER BY karat DESC
    """).fetchall()

    result = None

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        karat = request.form.get("karat", "")

        try:
            weight = float(request.form.get("weight") or 0)
            making = float(request.form.get("making") or 0)
            bat = float(request.form.get("bat") or 0)
            stone = float(request.form.get("stone") or 0)
            vat_percent = float(request.form.get("vat") or 0)
        except ValueError:
            weight = making = bat = stone = vat_percent = 0

        selected_rate = next(
            (
                row["rate"]
                for row in rates
                if row["karat"] == karat
            ),
            0
        )

        # ১ ভরি = 11.664 গ্রাম
        gold_value = (weight / 11.664) * selected_rate
        vat = (gold_value * vat_percent) / 100

        grand_total = (
            gold_value
            + making
            + bat
            + stone
            + vat
        )

        result = {
            "customer_name": customer_name,
            "mobile": mobile,
            "karat": karat,
            "weight": weight,
            "rate": selected_rate,
            "gold_value": gold_value,
            "making": making,
            "bat": bat,
            "stone": stone,
            "vat": vat,
            "grand_total": grand_total
        }

    return render_template(
        "calculator.html",
        rates=rates,
        result=result
    )


# =========================
# INVOICE
# =========================

@app.route("/invoice/create", methods=["POST"])
@login_required
def create_invoice():
    fields = (
        "rate", "gold_value", "making", "bat",
        "stone", "vat", "grand_total", "weight"
    )

    try:
        values = {field: float(request.form.get(field, 0)) for field in fields}
    except ValueError:
        return redirect("/calculator")

    customer_name = request.form.get("customer_name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    karat = request.form.get("karat", "").strip()

    if not customer_name or not karat or values["weight"] <= 0:
        return redirect("/calculator")

    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO invoices (
            customer_name, mobile, karat, weight, rate, gold_value,
            making, bat, stone, vat, grand_total
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        customer_name, mobile, karat, values["weight"], values["rate"],
        values["gold_value"], values["making"], values["bat"],
        values["stone"], values["vat"], values["grand_total"]
    ))
    invoice = conn.execute(
        "SELECT * FROM invoices WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    conn.commit()

    return render_template("invoice.html", invoice=invoice)


@app.route("/invoices")
@login_required
def invoices():
    conn = get_db()
    invoice_list = conn.execute("""
        SELECT * FROM invoices
        ORDER BY id DESC
    """).fetchall()

    return render_template("invoices.html", invoices=invoice_list)


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# =========================
# START APP
# =========================

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)
