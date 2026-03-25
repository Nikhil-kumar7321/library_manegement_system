from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "super_secret_key_change_this"

DB_NAME = "library.db"

# ---------------- DATABASE ----------------
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Admin table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Books table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available'
        )
    """)

    # Members table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL
        )
    """)

    # Transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT NOT NULL,
            member_id TEXT NOT NULL,
            action TEXT NOT NULL,
            issue_date TEXT,
            due_date TEXT,
            return_date TEXT,
            fine INTEGER DEFAULT 0
        )
    """)

    # Default admin create
    admin = cursor.execute("SELECT * FROM admin WHERE username = ?", ("admin",)).fetchone()
    if not admin:
        cursor.execute(
            "INSERT INTO admin (username, password) VALUES (?, ?)",
            ("admin", "admin123")
        )

    conn.commit()
    conn.close()

# ---------------- AUTH ----------------
def is_logged_in():
    return "admin_logged_in" in session

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        admin = conn.execute(
            "SELECT * FROM admin WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if admin:
            session["admin_logged_in"] = True
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password!", "error")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))

# ---------------- DASHBOARD ----------------
@app.route("/")
@app.route("/dashboard")
def dashboard():
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db_connection()

    total_books = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    issued_books = conn.execute("SELECT COUNT(*) FROM books WHERE status='Issued'").fetchone()[0]
    available_books = conn.execute("SELECT COUNT(*) FROM books WHERE status='Available'").fetchone()[0]
    total_members = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
    total_transactions = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        total_books=total_books,
        issued_books=issued_books,
        available_books=available_books,
        total_members=total_members,
        total_transactions=total_transactions
    )

# ---------------- BOOKS ----------------
@app.route("/books")
def books():
    if not is_logged_in():
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()

    conn = get_db_connection()
    if search:
        books = conn.execute("""
            SELECT * FROM books
            WHERE title LIKE ? OR author LIKE ? OR book_id LIKE ? OR category LIKE ?
        """, (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        books = conn.execute("SELECT * FROM books ORDER BY id DESC").fetchall()
    conn.close()

    return render_template("books.html", books=books, search=search)

@app.route("/add_book", methods=["POST"])
def add_book():
    if not is_logged_in():
        return redirect(url_for("login"))

    title = request.form["title"].strip()
    author = request.form["author"].strip()
    book_id = request.form["book_id"].strip()
    category = request.form["category"].strip()

    if not title or not author or not book_id or not category:
        flash("All book fields are required!", "error")
        return redirect(url_for("books"))

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO books (book_id, title, author, category)
            VALUES (?, ?, ?, ?)
        """, (book_id, title, author, category))
        conn.commit()
        flash("Book added successfully!", "success")
    except sqlite3.IntegrityError:
        flash("Book ID already exists!", "error")
    finally:
        conn.close()

    return redirect(url_for("books"))

@app.route("/delete_book/<book_id>")
def delete_book(book_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db_connection()
    book = conn.execute("SELECT * FROM books WHERE book_id=?", (book_id,)).fetchone()

    if book:
        if book["status"] == "Issued":
            flash("Cannot delete an issued book!", "error")
        else:
            conn.execute("DELETE FROM books WHERE book_id=?", (book_id,))
            conn.commit()
            flash("Book deleted successfully!", "success")

    conn.close()
    return redirect(url_for("books"))

# ---------------- MEMBERS ----------------
@app.route("/members")
def members():
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db_connection()
    members = conn.execute("SELECT * FROM members ORDER BY id DESC").fetchall()
    conn.close()

    return render_template("members.html", members=members)

@app.route("/add_member", methods=["POST"])
def add_member():
    if not is_logged_in():
        return redirect(url_for("login"))

    name = request.form["name"].strip()
    member_id = request.form["member_id"].strip()
    email = request.form["email"].strip()
    phone = request.form["phone"].strip()

    if not name or not member_id or not email or not phone:
        flash("All member fields are required!", "error")
        return redirect(url_for("members"))

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO members (member_id, name, email, phone)
            VALUES (?, ?, ?, ?)
        """, (member_id, name, email, phone))
        conn.commit()
        flash("Member registered successfully!", "success")
    except sqlite3.IntegrityError:
        flash("Member ID already exists!", "error")
    finally:
        conn.close()

    return redirect(url_for("members"))

# ---------------- TRANSACTIONS ----------------
@app.route("/transactions")
def transactions():
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_db_connection()
    transactions = conn.execute("""
        SELECT * FROM transactions
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    return render_template("transactions.html", transactions=transactions)

@app.route("/issue_book", methods=["POST"])
def issue_book():
    if not is_logged_in():
        return redirect(url_for("login"))

    book_id = request.form["book_id"].strip()
    member_id = request.form["member_id"].strip()

    conn = get_db_connection()

    book = conn.execute("SELECT * FROM books WHERE book_id=?", (book_id,)).fetchone()
    member = conn.execute("SELECT * FROM members WHERE member_id=?", (member_id,)).fetchone()

    if not book:
        flash("Book not found!", "error")
        conn.close()
        return redirect(url_for("transactions"))

    if not member:
        flash("Member not found!", "error")
        conn.close()
        return redirect(url_for("transactions"))

    if book["status"] == "Issued":
        flash("Book is already issued!", "error")
        conn.close()
        return redirect(url_for("transactions"))

    issue_date = datetime.now()
    due_date = issue_date + timedelta(days=14)

    conn.execute("UPDATE books SET status='Issued' WHERE book_id=?", (book_id,))
    conn.execute("""
        INSERT INTO transactions (book_id, member_id, action, issue_date, due_date)
        VALUES (?, ?, ?, ?, ?)
    """, (
        book_id,
        member_id,
        "Issued",
        issue_date.strftime("%Y-%m-%d"),
        due_date.strftime("%Y-%m-%d")
    ))
    conn.commit()
    conn.close()

    flash("Book issued successfully!", "success")
    return redirect(url_for("transactions"))

@app.route("/return_book", methods=["POST"])
def return_book():
    if not is_logged_in():
        return redirect(url_for("login"))

    book_id = request.form["book_id"].strip()
    member_id = request.form["member_id"].strip()

    conn = get_db_connection()

    book = conn.execute("SELECT * FROM books WHERE book_id=?", (book_id,)).fetchone()
    if not book:
        flash("Book not found!", "error")
        conn.close()
        return redirect(url_for("transactions"))

    # latest unreturned issue transaction
    txn = conn.execute("""
        SELECT * FROM transactions
        WHERE book_id=? AND member_id=? AND action='Issued' AND return_date IS NULL
        ORDER BY id DESC
        LIMIT 1
    """, (book_id, member_id)).fetchone()

    if not txn:
        flash("No active issued record found for this book and member!", "error")
        conn.close()
        return redirect(url_for("transactions"))

    return_date = datetime.now()
    due_date = datetime.strptime(txn["due_date"], "%Y-%m-%d")

    late_days = (return_date.date() - due_date.date()).days
    fine = late_days * 5 if late_days > 0 else 0

    # Update issued record as returned
    conn.execute("""
        UPDATE transactions
        SET return_date=?, fine=?
        WHERE id=?
    """, (
        return_date.strftime("%Y-%m-%d"),
        fine,
        txn["id"]
    ))

    # Optional return log entry
    conn.execute("""
        INSERT INTO transactions (book_id, member_id, action, return_date, fine)
        VALUES (?, ?, ?, ?, ?)
    """, (
        book_id,
        member_id,
        "Returned",
        return_date.strftime("%Y-%m-%d"),
        fine
    ))

    conn.execute("UPDATE books SET status='Available' WHERE book_id=?", (book_id,))
    conn.commit()
    conn.close()

    if fine > 0:
        flash(f"Book returned successfully! Fine: ₹{fine}", "success")
    else:
        flash("Book returned successfully! No fine.", "success")

    return redirect(url_for("transactions"))

# ---------------- MAIN ----------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)