from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import random
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = "banking_system_secret_key"


# ================= DATABASE CONNECTION =================

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="akash2005",
    database="banking"
)


# ================= HOME =================

@app.route("/")
def home():
    return render_template("home.html")


# ================= REGISTER =================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form["full_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]

        # Hash password
        password_hash = generate_password_hash(password)

        try:

            cursor = db.cursor()

            query = """
            INSERT INTO users
            (full_name, email, phone, password_hash)
            VALUES (%s, %s, %s, %s)
            """

            cursor.execute(
                query,
                (full_name, email, phone, password_hash)
            )

            db.commit()
            cursor.close()

            return redirect(url_for("login"))

        except mysql.connector.Error as error:

            return "Database Error: " + str(error)

    return render_template("register.html")


# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        cursor = db.cursor(dictionary=True)

        query = """
        SELECT * FROM users
        WHERE email = %s
        """

        cursor.execute(query, (email,))

        user = cursor.fetchone()

        cursor.close()

        if user:

            if check_password_hash(
                user["password_hash"],
                password
            ):

                session["user_id"] = user["id"]
                session["user_name"] = user["full_name"]

                return redirect(url_for("dashboard"))

        return "Invalid email or password"

    return render_template("login.html")


# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():

    # Check login
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    cursor = db.cursor(dictionary=True)

    # Check whether user has a bank account
    query = """
    SELECT *
    FROM accounts
    WHERE user_id = %s
    LIMIT 1
    """

    cursor.execute(query, (user_id,))

    account = cursor.fetchone()

    cursor.close()

    # Send account information to dashboard
    return render_template(
        "dashboard.html",
        name=session["user_name"],
        account=account
    )


# ================= CREATE ACCOUNT =================

@app.route("/create-account", methods=["GET", "POST"])
def create_account():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # Check if account already exists
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id
        FROM accounts
        WHERE user_id = %s
        LIMIT 1
    """, (user_id,))

    existing_account = cursor.fetchone()
    cursor.close()

    if existing_account:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        # Customer profile
        date_of_birth = request.form["date_of_birth"]
        gender = request.form["gender"]
        address = request.form["address"]
        city = request.form["city"]
        state = request.form["state"]
        pincode = request.form["pincode"]
        occupation = request.form["occupation"]

        # Account
        account_type = request.form["account_type"]

        # Initial deposit
        initial_deposit = float(request.form["initial_deposit"])

        # Generate account number
        account_number = str(
            random.randint(1000000000, 9999999999)
        )

        try:

            cursor = db.cursor()

            # --------------------------------
            # 1. CREATE CUSTOMER PROFILE
            # --------------------------------

            profile_query = """
                INSERT INTO profiles
                (
                    user_id,
                    date_of_birth,
                    gender,
                    address,
                    city,
                    state,
                    pincode,
                    occupation
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            cursor.execute(
                profile_query,
                (
                    user_id,
                    date_of_birth,
                    gender,
                    address,
                    city,
                    state,
                    pincode,
                    occupation
                )
            )

            # --------------------------------
            # 2. CREATE BANK ACCOUNT
            # --------------------------------

            account_query = """
                INSERT INTO accounts
                (
                    user_id,
                    account_number,
                    account_type,
                    balance
                )
                VALUES (%s, %s, %s, %s)
            """

            cursor.execute(
                account_query,
                (
                    user_id,
                    account_number,
                    account_type,
                    initial_deposit
                )
            )

            # Get newly created account ID
            account_id = cursor.lastrowid

            # --------------------------------
            # 3. CREATE INITIAL DEPOSIT TRANSACTION
            # --------------------------------

            if initial_deposit > 0:

                transaction_query = """
                    INSERT INTO transactions
                    (
                        account_id,
                        transaction_type,
                        amount,
                        description
                    )
                    VALUES (%s, %s, %s, %s)
                """

                cursor.execute(
                    transaction_query,
                    (
                        account_id,
                        "Deposit",
                        initial_deposit,
                        "Initial account deposit"
                    )
                )

            # --------------------------------
            # 4. SAVE EVERYTHING
            # --------------------------------

            db.commit()

            cursor.close()

            return redirect(url_for("dashboard"))

        except mysql.connector.Error as error:

            db.rollback()

            return "Database Error: " + str(error)

    return render_template("create_account.html")

# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)