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
@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


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
            serial_no TEXT,
            item_name TEXT NOT NULL,
            karat TEXT NOT NULL,
            weight REAL NOT NULL,
            bhori REAL DEFAULT 0,
            ana REAL DEFAULT 0,
            rati REAL DEFAULT 0,
            point REAL DEFAULT 0,
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
            rati_weight REAL NOT NULL DEFAULT 0,
            point_weight REAL NOT NULL DEFAULT 0,
            total_weight_gram REAL NOT NULL DEFAULT 0,
            estimated_price REAL NOT NULL DEFAULT 0,
            advance_paid REAL NOT NULL DEFAULT 0,
            delivery_date TEXT,
            special_requests TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_date TEXT DEFAULT (DATE('now', 'localtime')),
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES buy_orders(id) ON DELETE CASCADE
        )
    """)


def run_migrations(conn):
    loan_columns = {row["name"] for row in conn.execute("PRAGMA table_info(loans)")}
    if "voucher_id" not in loan_columns:
        conn.execute("ALTER TABLE loans ADD COLUMN voucher_id INTEGER")

    stock_columns = {row["name"] for row in conn.execute("PRAGMA table_info(gold_stock)")}
    if "serial_no" not in stock_columns:
        conn.execute("ALTER TABLE gold_stock ADD COLUMN serial_no TEXT")
    if "bhori" not in stock_columns:
        conn.execute("ALTER TABLE gold_stock ADD COLUMN bhori REAL DEFAULT 0")
    if "ana" not in stock_columns:
        conn.execute("ALTER TABLE gold_stock ADD COLUMN ana REAL DEFAULT 0")
    if "rati" not in stock_columns:
        conn.execute("ALTER TABLE gold_stock ADD COLUMN rati REAL DEFAULT 0")
    if "point" not in stock_columns:
        conn.execute("ALTER TABLE gold_stock ADD COLUMN point REAL DEFAULT 0")

    order_columns = {row["name"] for row in conn.execute("PRAGMA table_info(buy_orders)")}
    if "rati_weight" not in order_columns:
        conn.execute("ALTER TABLE buy_orders ADD COLUMN rati_weight REAL NOT NULL DEFAULT 0")
    if "point_weight" not in order_columns:
        conn.execute("ALTER TABLE buy_orders ADD COLUMN point_weight REAL NOT NULL DEFAULT 0")
    if "total_weight_gram" not in order_columns:
        conn.execute("ALTER TABLE buy_orders ADD COLUMN total_weight_gram REAL NOT NULL DEFAULT 0")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_date TEXT DEFAULT (DATE('now', 'localtime')),
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES buy_orders(id) ON DELETE CASCADE
        )
    """)


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
# EDIT CUSTOMER
# =========================

@app.route("/customer/edit/<int:customer_id>", methods=["POST"])
@login_required
def edit_customer(customer_id):
    name    = request.form.get("name",    "").strip()
    mobile  = request.form.get("mobile",  "").strip()
    address = request.form.get("address", "").strip()
    age     = request.form.get("age",     "").strip() or None

    if not name or not mobile:
        return redirect(url_for("customers"))

    conn = get_db()
    conn.execute("""
        UPDATE customers
        SET name = ?, mobile = ?, address = ?, age = ?
        WHERE id = ?
    """, (name, mobile, address, age, customer_id))
    conn.commit()
    return redirect(url_for("customers"))


# =========================
# CUSTOMER PROFILE
# =========================

@app.route("/customer/<int:customer_id>")
@login_required
def customer_profile(customer_id):
    conn = get_db()
    customer = conn.execute(
        "SELECT * FROM customers WHERE id = ?", (customer_id,)
    ).fetchone()

    if customer is None:
        return redirect(url_for("customers"))

    invoices = conn.execute("""
        SELECT * FROM invoices
        WHERE customer_name = ?
        ORDER BY id DESC
        LIMIT 10
    """, (customer["name"],)).fetchall()

    loans = conn.execute("""
        SELECT * FROM loans
        WHERE customer_name = ?
        ORDER BY id DESC
        LIMIT 10
    """, (customer["name"],)).fetchall()

    total_spent = conn.execute("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM invoices
        WHERE customer_name = ?
    """, (customer["name"],)).fetchone()[0]

    return render_template(
        "customer_profile.html",
        customer=customer,
        invoices=invoices,
        loans=loans,
        total_spent=total_spent,
    )


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
            bhori = float(request.form.get("bhori") or 0)
            ana = float(request.form.get("ana") or 0)
            rati = float(request.form.get("rati") or 0)
            point = float(request.form.get("point") or 0)
        except ValueError:
            bhori = ana = rati = point = 0

        # Calculate weight in grams: 1 vari = 16 ana = 96 rati = 576 point = 11.664 gram
        # Check if direct weight in gram was supplied or calculated from vari/anna/rati/point
        raw_gram = request.form.get("weight")
        if raw_gram and float(raw_gram) > 0 and (bhori == 0 and ana == 0 and rati == 0 and point == 0):
            weight = float(raw_gram)
            # Reverse calculate approximate bhori/ana for display
            total_bhori = weight / 11.664
            bhori = float(int(total_bhori))
            rem_ana = (total_bhori - bhori) * 16
            ana = float(int(rem_ana))
            rem_rati = (rem_ana - ana) * 6
            rati = float(int(rem_rati))
            point = round((rem_rati - rati) * 6, 1)
        else:
            total_bhori = bhori + (ana / 16.0) + (rati / 96.0) + (point / 576.0)
            weight = round(total_bhori * 11.664, 4)

        try:
            quantity = int(request.form.get("quantity") or 1)
            purchase_rate = float(request.form.get("purchase_rate") or 0)
        except ValueError:
            quantity = 1
            purchase_rate = 0

        total_value = weight * quantity * purchase_rate

        if not serial_no:
            count = conn.execute("SELECT COUNT(*) FROM gold_stock").fetchone()[0] + 1
            serial_no = f"QS-2026-{count:04d}"

        if item_name and karat and weight > 0 and quantity > 0:
            conn.execute("""
                INSERT INTO gold_stock (
                    serial_no,
                    item_name,
                    karat,
                    weight,
                    bhori,
                    ana,
                    rati,
                    point,
                    quantity,
                    purchase_rate,
                    total_value
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                serial_no,
                item_name,
                karat,
                weight,
                bhori,
                ana,
                rati,
                point,
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
        customer_name   = request.form.get("customer_name",   "").strip()
        mobile          = request.form.get("mobile",          "").strip()
        item_details    = request.form.get("item_details",    "").strip()
        grade           = request.form.get("grade", "22K Gold").strip()
        delivery_date   = request.form.get("delivery_date",   "").strip()
        special_requests = request.form.get("special_requests", "").strip()

        try:
            bhori_weight   = float(request.form.get("bhori_weight")  or 0)
            ana_weight     = float(request.form.get("ana_weight")    or 0)
            rati_weight    = float(request.form.get("rati_weight")   or 0)
            point_weight   = float(request.form.get("point_weight")  or 0)
            estimated_price = float(request.form.get("estimated_price") or 0)
            advance_paid   = float(request.form.get("advance_paid")  or 0)
        except ValueError:
            bhori_weight = ana_weight = rati_weight = point_weight = estimated_price = advance_paid = 0

        # ভরি → গ্রাম রূপান্তর
        # 1 ভরি = 16 আনা = 96 রতি = 576 পয়েন্ট = 11.664 গ্রাম
        total_bhori = (
            bhori_weight
            + ana_weight   / 16
            + rati_weight  / 96
            + point_weight / 576
        )
        total_weight_gram = round(total_bhori * 11.664, 4)

        if customer_name and item_details and estimated_price >= 0 and advance_paid >= 0:
            conn.execute("""
                INSERT INTO buy_orders (
                    customer_name, mobile, item_details, grade,
                    bhori_weight, ana_weight, rati_weight, point_weight,
                    total_weight_gram,
                    estimated_price, advance_paid, delivery_date,
                    special_requests
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                customer_name, mobile, item_details, grade,
                bhori_weight, ana_weight, rati_weight, point_weight,
                total_weight_gram,
                estimated_price, advance_paid, delivery_date,
                special_requests
            ))
            conn.commit()
            return redirect(url_for("buy_now"))


    orders_raw = conn.execute("SELECT * FROM buy_orders ORDER BY id DESC").fetchall()
    orders = []
    for row in orders_raw:
        od = dict(row)
        payments = conn.execute(
            "SELECT * FROM order_payments WHERE order_id = ? ORDER BY id ASC",
            (od["id"],)
        ).fetchall()
        installment_sum = sum(p["amount"] for p in payments)
        od["payments"] = payments
        od["installment_sum"] = installment_sum
        od["total_paid"] = od["advance_paid"] + installment_sum
        od["due_amount"] = max(0.0, od["estimated_price"] - od["total_paid"])
        orders.append(od)

    return render_template("buy_now.html", orders=orders)


@app.route("/buy-now/payment/<int:order_id>", methods=["POST"])
@login_required
def add_order_payment(order_id):
    conn = get_db()
    order = conn.execute("SELECT * FROM buy_orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        return redirect(url_for("buy_now"))

    try:
        amount = float(request.form.get("amount") or 0)
    except ValueError:
        amount = 0

    payment_date = request.form.get("payment_date", "").strip()
    note = request.form.get("note", "").strip()

    if amount > 0:
        if payment_date:
            conn.execute("""
                INSERT INTO order_payments (order_id, amount, payment_date, note)
                VALUES (?, ?, ?, ?)
            """, (order_id, amount, payment_date, note))
        else:
            conn.execute("""
                INSERT INTO order_payments (order_id, amount, note)
                VALUES (?, ?, ?)
            """, (order_id, amount, note))

        # Check if fully paid, update status to Completed if requested or fully paid
        all_payments = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM order_payments WHERE order_id = ?",
            (order_id,)
        ).fetchone()[0]
        total_paid = order["advance_paid"] + all_payments
        if total_paid >= order["estimated_price"]:
            conn.execute("UPDATE buy_orders SET status = 'Completed' WHERE id = ?", (order_id,))

        conn.commit()

    return redirect(url_for("buy_now"))


@app.route("/buy-now/payment/delete/<int:payment_id>", methods=["POST"])
@login_required
def delete_order_payment(payment_id):
    conn = get_db()
    payment = conn.execute("SELECT * FROM order_payments WHERE id = ?", (payment_id,)).fetchone()
    if payment:
        order_id = payment["order_id"]
        conn.execute("DELETE FROM order_payments WHERE id = ?", (payment_id,))
        # Re-check status
        order = conn.execute("SELECT * FROM buy_orders WHERE id = ?", (order_id,)).fetchone()
        if order:
            all_payments = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM order_payments WHERE order_id = ?",
                (order_id,)
            ).fetchone()[0]
            total_paid = order["advance_paid"] + all_payments
            if total_paid < order["estimated_price"] and order["status"] == "Completed":
                conn.execute("UPDATE buy_orders SET status = 'Pending' WHERE id = ?", (order_id,))
        conn.commit()
    return redirect(url_for("buy_now"))


@app.route("/buy-now/delete/<int:order_id>", methods=["GET", "POST"])
@login_required
def delete_buy_order(order_id):
    conn = get_db()
    conn.execute("DELETE FROM order_payments WHERE order_id = ?", (order_id,))
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
# GOLD SALE / RATE UPDATE
# =========================

@app.route("/gold-sale", methods=["GET", "POST"])
@login_required
def gold_sale():
    conn = get_db()
    message = None

    if request.method == "POST":
        for karat in ["24K", "22K", "21K", "18K"]:
            rate_val = request.form.get(f"rate_{karat}", "").strip()
            if rate_val:
                try:
                    conn.execute(
                        "UPDATE gold_rates SET rate = ? WHERE karat = ?",
                        (float(rate_val), karat)
                    )
                except ValueError:
                    pass
        conn.commit()
        message = "Gold rates updated successfully!"

    rates = conn.execute("SELECT karat, rate FROM gold_rates ORDER BY karat DESC").fetchall()
    return render_template("gold_sale.html", rates=rates, message=message)


# =========================
# REPORTS
# =========================

@app.route("/reports")
@login_required
def reports():
    conn = get_db()

    total_sales = conn.execute(
        "SELECT COALESCE(SUM(grand_total), 0) FROM invoices"
    ).fetchone()[0]

    total_invoices = conn.execute(
        "SELECT COUNT(*) FROM invoices"
    ).fetchone()[0]

    monthly_sales = conn.execute("""
        SELECT strftime('%Y-%m', created_at) AS month,
               COUNT(*) AS count,
               COALESCE(SUM(grand_total), 0) AS total
        FROM invoices
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
    """).fetchall()

    active_loans = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM loans WHERE status = 'Active'"
    ).fetchone()[0]

    pending_orders = conn.execute(
        "SELECT COUNT(*) FROM buy_orders WHERE status = 'Pending'"
    ).fetchone()[0]

    return render_template(
        "reports.html",
        total_sales=total_sales,
        total_invoices=total_invoices,
        monthly_sales=monthly_sales,
        active_loans=active_loans,
        pending_orders=pending_orders
    )


# =========================
# SETTINGS
# =========================

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    message = None
    error = None

    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "").strip()
        confirm_pw = request.form.get("confirm_password", "").strip()

        if current_pw != "1234":
            error = "Current password is incorrect."
        elif not new_pw or len(new_pw) < 4:
            error = "New password must be at least 4 characters."
        elif new_pw != confirm_pw:
            error = "Passwords do not match."
        else:
            # In production, store hashed passwords in DB.
            # For now we just confirm success (stateless demo).
            message = "Password changed successfully! Please restart the app to apply."

    return render_template("settings.html", message=message, error=error)


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
