from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import random
import pandas as pd
import pickle

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
with open("business_loan_model.pkl", "rb") as file:
    business_loan_model = pickle.load(file)

with open("education_loan_model.pkl", "rb") as file:
    education_loan_model = pickle.load(file)

with open("home_loan_model.pkl", "rb") as file:
    home_loan_model = pickle.load(file)

with open("personal_loan_model.pkl", "rb") as file:
    personal_loan_model = pickle.load(file)

with open("vehicle_loan_model.pkl", "rb") as file:
    vehicle_loan_model = pickle.load(file)

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


# ================= DEPOSIT =================

@app.route("/deposite", methods=["GET", "POST"])
def deposite():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, balance
        FROM accounts
        WHERE user_id = %s
        LIMIT 1
    """, (user_id,))

    account = cursor.fetchone()
    cursor.close()

    if not account:
        return redirect(url_for("create_account"))

    if request.method == "POST":

        amount = float(request.form["amount"])

        if amount <= 0:
            return "Invalid deposit amount"

        try:

            cursor = db.cursor()

            # Update account balance
            cursor.execute("""
                UPDATE accounts
                SET balance = balance + %s
                WHERE id = %s
            """, (amount, account["id"]))

            # Save transaction
            cursor.execute("""
                INSERT INTO transactions
                (
                    account_id,
                    transaction_type,
                    amount,
                    description
                )
                VALUES (%s, %s, %s, %s)
            """, (
                account["id"],
                "Deposit",
                amount,
                "Money deposited"
            ))

            db.commit()
            cursor.close()

            return redirect(url_for("dashboard"))

        except mysql.connector.Error as error:

            db.rollback()

            return "Database Error: " + str(error)

    return render_template(
        "deposite.html",
        balance=account["balance"]
    )


# ================= WITHDRAW =================

@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, balance
        FROM accounts
        WHERE user_id = %s
        LIMIT 1
    """, (user_id,))

    account = cursor.fetchone()
    cursor.close()

    if not account:
        return redirect(url_for("create_account"))

    if request.method == "POST":

        amount = float(request.form["amount"])

        if amount <= 0:
            return "Invalid withdrawal amount"

        if amount > float(account["balance"]):
            return "Insufficient balance"

        try:

            cursor = db.cursor()

            # Update account balance
            cursor.execute("""
                UPDATE accounts
                SET balance = balance - %s
                WHERE id = %s
            """, (amount, account["id"]))

            # Save transaction
            cursor.execute("""
                INSERT INTO transactions
                (
                    account_id,
                    transaction_type,
                    amount,
                    description
                )
                VALUES (%s, %s, %s, %s)
            """, (
                account["id"],
                "Withdrawal",
                amount,
                "Money withdrawn"
            ))

            db.commit()
            cursor.close()

            return redirect(url_for("dashboard"))

        except mysql.connector.Error as error:

            db.rollback()

            return "Database Error: " + str(error)

    return render_template(
        "withdraw.html",
        balance=account["balance"]
    )
    
    
# ================= TRANSFER MONEY =================

@app.route("/transfer", methods=["GET", "POST"])
def transfer():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # Get sender's account
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, account_number, balance
        FROM accounts
        WHERE user_id = %s
        LIMIT 1
    """, (user_id,))

    sender = cursor.fetchone()
    cursor.close()

    if not sender:
        return redirect(url_for("create_account"))

    if request.method == "POST":

        receiver_account_number = request.form["receiver_account_number"]
        amount = float(request.form["amount"])

        # Basic validation
        if amount <= 0:
            return "Invalid transfer amount"

        # Sender cannot transfer to himself
        if receiver_account_number == sender["account_number"]:
            return "You cannot transfer money to your own account"

        # Check sender balance
        if amount > float(sender["balance"]):
            return "Insufficient balance"

        try:

            cursor = db.cursor(dictionary=True)

            # Find receiver
            cursor.execute("""
                SELECT id, account_number
                FROM accounts
                WHERE account_number = %s
                LIMIT 1
            """, (receiver_account_number,))

            receiver = cursor.fetchone()

            if not receiver:
                cursor.close()
                return "Receiver account not found"

            # --------------------------------
            # 1. DEDUCT MONEY FROM SENDER
            # --------------------------------

            cursor.execute("""
                UPDATE accounts
                SET balance = balance - %s
                WHERE id = %s
            """, (
                amount,
                sender["id"]
            ))

            # --------------------------------
            # 2. ADD MONEY TO RECEIVER
            # --------------------------------

            cursor.execute("""
                UPDATE accounts
                SET balance = balance + %s
                WHERE id = %s
            """, (
                amount,
                receiver["id"]
            ))

            # --------------------------------
            # 3. RECORD SENDER TRANSACTION
            # --------------------------------

            cursor.execute("""
                INSERT INTO transactions
                (
                    account_id,
                    transaction_type,
                    amount,
                    description
                )
                VALUES (%s, %s, %s, %s)
            """, (
                sender["id"],
                "Transfer",
                amount,
                "Money transferred to account "
                + receiver_account_number
            ))

            # --------------------------------
            # 4. RECORD RECEIVER TRANSACTION
            # --------------------------------

            cursor.execute("""
                INSERT INTO transactions
                (
                    account_id,
                    transaction_type,
                    amount,
                    description
                )
                VALUES (%s, %s, %s, %s)
            """, (
                receiver["id"],
                "Transfer",
                amount,
                "Money received from account "
                + sender["account_number"]
            ))

            # --------------------------------
            # 5. SAVE EVERYTHING
            # --------------------------------

            db.commit()

            cursor.close()

            return redirect(url_for("dashboard"))

        except mysql.connector.Error as error:

            db.rollback()

            return "Database Error: " + str(error)

    return render_template(
        "transfer.html",
        balance=sender["balance"],
        account_number=sender["account_number"]
    )
    
# ================= TRANSACTION HISTORY =================

@app.route("/transactions")
def transactions():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    cursor = db.cursor(dictionary=True)

    query = """
        SELECT
            transactions.transaction_type,
            transactions.amount,
            transactions.description,
            transactions.transaction_date
        FROM transactions
        JOIN accounts
        ON transactions.account_id = accounts.id
        WHERE accounts.user_id = %s
        ORDER BY transactions.transaction_date DESC
    """

    cursor.execute(query, (user_id,))

    transaction_list = cursor.fetchall()

    cursor.close()

    return render_template(
        "transactions.html",
        transactions=transaction_list
    )
    
# ================= ACCOUNT DETAILS =================

@app.route("/account-details")
def account_details():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    cursor = db.cursor(dictionary=True)

    query = """
        SELECT
            users.full_name,
            users.email,
            users.phone,

            profiles.date_of_birth,
            profiles.gender,
            profiles.address,
            profiles.city,
            profiles.state,
            profiles.pincode,
            profiles.occupation,

            accounts.account_number,
            accounts.account_type,
            accounts.balance,
            accounts.created_at
            

        FROM users

        JOIN profiles
        ON users.id = profiles.user_id

        JOIN accounts
        ON users.id = accounts.user_id

        WHERE users.id = %s
        LIMIT 1
    """

    cursor.execute(query, (user_id,))

    account = cursor.fetchone()

    cursor.close()

    if not account:
        return redirect(url_for("create_account"))

    return render_template(
        "account_details.html",
        account=account
    )
    
@app.route('/apply-loan')
def apply_loan():
    return render_template('apply_loan.html')

# ================= BUSINESS LOAN =================

@app.route("/business-loan", methods=["GET", "POST"])
def business_loan():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        user_id = session["user_id"]

        # Get Business Loan form data
        Applicant_Age = request.form["Applicant_Age"]
        Business_Type = request.form["Business_Type"]
        Business_Age = request.form["Business_Age"]
        Monthly_Business_Revenue = request.form["Monthly_Business_Revenue"]
        Monthly_Business_Expenses = request.form["Monthly_Business_Expenses"]
        Monthly_Business_Profit = request.form["Monthly_Business_Profit"]
        Existing_Business_EMI = request.form["Existing_Business_EMI"]
        Loan_Amount = request.form["Loan_Amount"]
        Loan_Tenure = request.form["Loan_Tenure"]
        Number_of_Employees = request.form["Number_of_Employees"]
        Business_Registration = request.form["Business_Registration"]
        GST_Registration = request.form["GST_Registration"]
        Annual_Turnover = request.form["Annual_Turnover"]
        Business_Location_Type = request.form["Business_Location_Type"]
        Loan_Purpose = request.form["Loan_Purpose"]
        Collateral_Available = request.form["Collateral_Available"]

        try:

            cursor = db.cursor()

            # --------------------------------
            # 1. CREATE LOAN APPLICATION
            # --------------------------------

            application_query = """
                INSERT INTO loan_applications
                (
                    user_id,
                    loan_type,
                    application_status
                )
                VALUES (%s, %s, %s)
            """

            cursor.execute(
                application_query,
                (
                    user_id,
                    "Business Loan",
                    "Pending"
                )
            )

            # Get application ID
            application_id = cursor.lastrowid

            # --------------------------------
            # 2. SAVE BUSINESS LOAN FEATURES
            # --------------------------------

            loan_query = """
                INSERT INTO business_loans
                (
                    user_id,
                    Applicant_Age,
                    Business_Type,
                    Business_Age,
                    Monthly_Business_Revenue,
                    Monthly_Business_Expenses,
                    Monthly_Business_Profit,
                    Existing_Business_EMI,
                    Loan_Amount,
                    Loan_Tenure,
                    Number_of_Employees,
                    Business_Registration,
                    GST_Registration,
                    Annual_Turnover,
                    Business_Location_Type,
                    Loan_Purpose,
                    Collateral_Available,
                    application_id
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
            """

            cursor.execute(
                loan_query,
                (
                    user_id,
                    Applicant_Age,
                    Business_Type,
                    Business_Age,
                    Monthly_Business_Revenue,
                    Monthly_Business_Expenses,
                    Monthly_Business_Profit,
                    Existing_Business_EMI,
                    Loan_Amount,
                    Loan_Tenure,
                    Number_of_Employees,
                    Business_Registration,
                    GST_Registration,
                    Annual_Turnover,
                    Business_Location_Type,
                    Loan_Purpose,
                    Collateral_Available,
                    application_id
                )
            )

            # --------------------------------
            # 3. SAVE APPLICATION
            # --------------------------------

            db.commit()

            cursor.close()

            return "Business Loan Application Submitted Successfully"

        except mysql.connector.Error as error:

            db.rollback()

            return "Database Error: " + str(error)

    return render_template("business_loan.html")

# ================= EDUCATION LOAN =================

@app.route("/education-loan", methods=["GET", "POST"])
def education_loan():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        user_id = session["user_id"]

        # Get form data
        Age = request.form["Age"]
        Education_Level = request.form["Education_Level"]
        Course_Type = request.form["Course_Type"]
        Course_Duration = request.form["Course_Duration"]
        Institution_Type = request.form["Institution_Type"]
        Institution_Location = request.form["Institution_Location"]
        Admission_Status = request.form["Admission_Status"]
        Annual_Course_Fee = request.form["Annual_Course_Fee"]
        Total_Education_Cost = request.form["Total_Education_Cost"]
        Loan_Amount = request.form["Loan_Amount"]
        Family_Monthly_Income = request.form["Family_Monthly_Income"]
        Family_Existing_EMI = request.form["Family_Existing_EMI"]
        Number_of_Dependents = request.form["Number_of_Dependents"]
        Previous_Academic_Performance = request.form["Previous_Academic_Performance"]
        Co_Applicant_Occupation = request.form["Co_Applicant_Occupation"]
        Co_Applicant_Monthly_Income = request.form["Co_Applicant_Monthly_Income"]

        try:

            cursor = db.cursor()

            # --------------------------------
            # 1. CREATE LOAN APPLICATION
            # --------------------------------

            application_query = """
                INSERT INTO loan_applications
                (
                    user_id,
                    loan_type,
                    application_status
                )
                VALUES (%s, %s, %s)
            """

            cursor.execute(
                application_query,
                (
                    user_id,
                    "Education Loan",
                    "Pending"
                )
            )

            application_id = cursor.lastrowid

            # --------------------------------
            # 2. SAVE EDUCATION LOAN FEATURES
            # --------------------------------

            loan_query = """
                INSERT INTO education_loans
                (
                    application_id,
                    Age,
                    Education_Level,
                    Course_Type,
                    Course_Duration,
                    Institution_Type,
                    Institution_Location,
                    Admission_Status,
                    Annual_Course_Fee,
                    Total_Education_Cost,
                    Loan_Amount,
                    Family_Monthly_Income,
                    Family_Existing_EMI,
                    Number_of_Dependents,
                    Previous_Academic_Performance,
                    Co_Applicant_Occupation,
                    Co_Applicant_Monthly_Income
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
            """

            cursor.execute(
                loan_query,
                (
                    application_id,
                    Age,
                    Education_Level,
                    Course_Type,
                    Course_Duration,
                    Institution_Type,
                    Institution_Location,
                    Admission_Status,
                    Annual_Course_Fee,
                    Total_Education_Cost,
                    Loan_Amount,
                    Family_Monthly_Income,
                    Family_Existing_EMI,
                    Number_of_Dependents,
                    Previous_Academic_Performance,
                    Co_Applicant_Occupation,
                    Co_Applicant_Monthly_Income
                )
            )

            # --------------------------------
            # 3. SAVE
            # --------------------------------

            db.commit()

            cursor.close()

            return "Education Loan Application Submitted Successfully"

        except mysql.connector.Error as error:

            db.rollback()

            return "Database Error: " + str(error)

    return render_template("education_loan.html")

# ================= HOME LOAN =================

@app.route("/home-loan", methods=["GET", "POST"])
def home_loan():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        user_id = session["user_id"]

        # Get Home Loan form data
        Age = request.form["Age"]
        Occupation = request.form["Occupation"]
        Employment_Type = request.form["Employment_Type"]
        Monthly_Income = request.form["Monthly_Income"]
        Employment_Business_Duration = request.form["Employment_Business_Duration"]
        Existing_Monthly_EMI = request.form["Existing_Monthly_EMI"]
        Loan_Amount = request.form["Loan_Amount"]
        Loan_Tenure = request.form["Loan_Tenure"]
        Property_Value = request.form["Property_Value"]
        Down_Payment = request.form["Down_Payment"]
        Property_Type = request.form["Property_Type"]
        Property_Location_Type = request.form["Property_Location_Type"]
        Number_of_Dependents = request.form["Number_of_Dependents"]

        try:

            cursor = db.cursor()

            # --------------------------------
            # 1. CREATE LOAN APPLICATION
            # --------------------------------

            cursor.execute("""
                INSERT INTO loan_applications
                (
                    user_id,
                    loan_type,
                    application_status
                )
                VALUES (%s, %s, %s)
            """, (
                user_id,
                "Home Loan",
                "Pending"
            ))

            application_id = cursor.lastrowid

            # --------------------------------
            # 2. SAVE HOME LOAN FEATURES
            # --------------------------------

            cursor.execute("""
                INSERT INTO home_loans
                (
                    application_id,
                    Age,
                    Occupation,
                    Employment_Type,
                    Monthly_Income,
                    Employment_Business_Duration,
                    Existing_Monthly_EMI,
                    Loan_Amount,
                    Loan_Tenure,
                    Property_Value,
                    Down_Payment,
                    Property_Type,
                    Property_Location_Type,
                    Number_of_Dependents
                )
                VALUES
                (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
            """, (
                application_id,
                Age,
                Occupation,
                Employment_Type,
                Monthly_Income,
                Employment_Business_Duration,
                Existing_Monthly_EMI,
                Loan_Amount,
                Loan_Tenure,
                Property_Value,
                Down_Payment,
                Property_Type,
                Property_Location_Type,
                Number_of_Dependents
            ))

            # --------------------------------
            # 3. SAVE APPLICATION
            # --------------------------------

            db.commit()

            cursor.close()

            return "Home Loan Application Submitted Successfully"

        except mysql.connector.Error as error:

            db.rollback()

            return "Database Error: " + str(error)

    return render_template("home_loan.html")

# ================= PERSONAL LOAN =================

@app.route("/personal-loan", methods=["GET", "POST"])
def personal_loan():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        user_id = session["user_id"]

        # Get Personal Loan form data
        Age = request.form["Age"]
        Occupation = request.form["Occupation"]
        Employment_Type = request.form["Employment_Type"]
        Monthly_Income = request.form["Monthly_Income"]
        Employment_Business_Duration = request.form["Employment_Business_Duration"]
        Existing_Monthly_EMI = request.form["Existing_Monthly_EMI"]
        Loan_Amount = request.form["Loan_Amount"]
        Loan_Tenure = request.form["Loan_Tenure"]
        Loan_Purpose = request.form["Loan_Purpose"]
        Number_of_Dependents = request.form["Number_of_Dependents"]
        Monthly_Household_Expenses = request.form["Monthly_Household_Expenses"]
        Monthly_Savings_Surplus = request.form["Monthly_Savings_Surplus"]
        Residence_Type = request.form["Residence_Type"]
        Employment_Business_Stability = request.form["Employment_Business_Stability"]

        try:

            cursor = db.cursor()

            # --------------------------------
            # 1. CREATE LOAN APPLICATION
            # --------------------------------

            cursor.execute("""
                INSERT INTO loan_applications
                (
                    user_id,
                    loan_type,
                    application_status
                )
                VALUES (%s, %s, %s)
            """, (
                user_id,
                "Personal Loan",
                "Pending"
            ))

            application_id = cursor.lastrowid

            # --------------------------------
            # 2. SAVE PERSONAL LOAN FEATURES
            # --------------------------------

            cursor.execute("""
                INSERT INTO personal_loans
                (
                    application_id,
                    Age,
                    Occupation,
                    Employment_Type,
                    Monthly_Income,
                    Employment_Business_Duration,
                    Existing_Monthly_EMI,
                    Loan_Amount,
                    Loan_Tenure,
                    Loan_Purpose,
                    Number_of_Dependents,
                    Monthly_Household_Expenses,
                    Monthly_Savings_Surplus,
                    Residence_Type,
                    Employment_Business_Stability
                )
                VALUES
                (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
            """, (
                application_id,
                Age,
                Occupation,
                Employment_Type,
                Monthly_Income,
                Employment_Business_Duration,
                Existing_Monthly_EMI,
                Loan_Amount,
                Loan_Tenure,
                Loan_Purpose,
                Number_of_Dependents,
                Monthly_Household_Expenses,
                Monthly_Savings_Surplus,
                Residence_Type,
                Employment_Business_Stability
            ))

            # --------------------------------
            # 3. SAVE APPLICATION
            # --------------------------------

            db.commit()

            cursor.close()

            return "Personal Loan Application Submitted Successfully"

        except mysql.connector.Error as error:

            db.rollback()

            return "Database Error: " + str(error)

    return render_template("personal_loan.html")

# ================= VEHICLE LOAN =================

@app.route("/vehicle-loan", methods=["GET", "POST"])
def vehicle_loan():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        user_id = session["user_id"]

        # Get Vehicle Loan form data
        Age = request.form["Age"]
        Occupation = request.form["Occupation"]
        Employment_Type = request.form["Employment_Type"]
        Monthly_Income = request.form["Monthly_Income"]
        Employment_Business_Duration = request.form["Employment_Business_Duration"]
        Existing_Monthly_EMI = request.form["Existing_Monthly_EMI"]
        Vehicle_Type = request.form["Vehicle_Type"]
        Vehicle_Condition = request.form["Vehicle_Condition"]
        Vehicle_Price = request.form["Vehicle_Price"]
        Down_Payment = request.form["Down_Payment"]
        Loan_Amount = request.form["Loan_Amount"]
        Loan_Tenure = request.form["Loan_Tenure"]
        Vehicle_Usage = request.form["Vehicle_Usage"]
        Number_of_Dependents = request.form["Number_of_Dependents"]

        try:

            cursor = db.cursor()

            # --------------------------------
            # 1. CREATE LOAN APPLICATION
            # --------------------------------

            cursor.execute("""
                INSERT INTO loan_applications
                (
                    user_id,
                    loan_type,
                    application_status
                )
                VALUES (%s, %s, %s)
            """, (
                user_id,
                "Vehicle Loan",
                "Pending"
            ))

            application_id = cursor.lastrowid

            # --------------------------------
            # 2. SAVE VEHICLE LOAN FEATURES
            # --------------------------------

            cursor.execute("""
                INSERT INTO vehicle_loans
                (
                    application_id,
                    Age,
                    Occupation,
                    Employment_Type,
                    Monthly_Income,
                    Employment_Business_Duration,
                    Existing_Monthly_EMI,
                    Vehicle_Type,
                    Vehicle_Condition,
                    Vehicle_Price,
                    Down_Payment,
                    Loan_Amount,
                    Loan_Tenure,
                    Vehicle_Usage,
                    Number_of_Dependents
                )
                VALUES
                (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
            """, (
                application_id,
                Age,
                Occupation,
                Employment_Type,
                Monthly_Income,
                Employment_Business_Duration,
                Existing_Monthly_EMI,
                Vehicle_Type,
                Vehicle_Condition,
                Vehicle_Price,
                Down_Payment,
                Loan_Amount,
                Loan_Tenure,
                Vehicle_Usage,
                Number_of_Dependents
            ))

            # --------------------------------
            # 3. SAVE APPLICATION
            # --------------------------------

            db.commit()

            cursor.close()

            return "Vehicle Loan Application Submitted Successfully"

        except mysql.connector.Error as error:

            db.rollback()

            return "Database Error: " + str(error)

    return render_template("vehicle_loan.html")
# ================= MANAGER DASHBOARD =================

# ================= MANAGER HOME =================

@app.route("/manager")
def manager_home():
    return render_template("manager_home.html")


# ================= MANAGER REGISTER =================

@app.route("/manager-register", methods=["GET", "POST"])
def manager_register():

    if request.method == "POST":

        full_name = request.form["full_name"]
        email = request.form["email"]
        password = request.form["password"]

        password_hash = generate_password_hash(password)

        try:

            cursor = db.cursor()

            cursor.execute("""
                INSERT INTO managers
                (
                    full_name,
                    email,
                    password_hash
                )
                VALUES (%s, %s, %s)
            """, (
                full_name,
                email,
                password_hash
            ))

            db.commit()
            cursor.close()

            return redirect(url_for("manager_login"))

        except mysql.connector.Error as error:

            db.rollback()

            return "Database Error: " + str(error)

    return render_template("manager_register.html")
    
# ================= CREATE MANAGER =================

# ================= MANAGER LOGIN =================

@app.route("/manager-login", methods=["GET", "POST"])
def manager_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM managers
            WHERE email = %s
        """, (email,))

        manager = cursor.fetchone()

        cursor.close()

        if manager:

            if check_password_hash(
                manager["password_hash"],
                password
            ):

                session["manager_id"] = manager["id"]
                session["manager_name"] = manager["full_name"]

                return redirect(url_for("manager_dashboard"))

        return "Invalid manager email or password"

    return render_template("manager_login.html")

# ================= MANAGER DASHBOARD =================

@app.route("/manager-dashboard")
def manager_dashboard():

    if "manager_id" not in session:
        return redirect(url_for("manager_login"))

    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            id,
            user_id,
            loan_type,
            application_status,
            ai_prediction,
            manager_decision,
            rejection_reason,
            applied_at
        FROM loan_applications
        ORDER BY applied_at DESC
    """)

    applications = cursor.fetchall()

    cursor.close()

    return render_template(
        "manager_dashboard.html",
        applications=applications,
        manager_name=session["manager_name"]
    )
    
# ================= MANAGER APPLICATION DETAILS =================

@app.route("/manager-application/<int:application_id>")
def manager_application(application_id):

    if "manager_id" not in session:
        return redirect(url_for("manager_login"))

    try:
        cursor = db.cursor(dictionary=True)

        # Get main application
        cursor.execute("""
            SELECT *
            FROM loan_applications
            WHERE id = %s
        """, (application_id,))

        application = cursor.fetchone()

        if not application:
            cursor.close()
            return "Application not found"

        loan_type = application["loan_type"]

        # ==========================================
        # BUSINESS LOAN
        # ==========================================

        if loan_type == "Business Loan":

            cursor.execute("""
                SELECT *
                FROM business_loans
                WHERE application_id = %s
            """, (application_id,))

            loan_details = cursor.fetchone()

            if not loan_details:
                cursor.close()
                return "Business loan details not found"

            if application["ai_prediction"] is None:

                features = {
                    "Applicant_Age": loan_details["Applicant_Age"],
                    "Business_Type": loan_details["Business_Type"],
                    "Business_Age": loan_details["Business_Age"],
                    "Monthly_Business_Revenue": loan_details["Monthly_Business_Revenue"],
                    "Monthly_Business_Expenses": loan_details["Monthly_Business_Expenses"],
                    "Monthly_Business_Profit": loan_details["Monthly_Business_Profit"],
                    "Existing_Business_EMI": loan_details["Existing_Business_EMI"],
                    "Loan_Amount": loan_details["Loan_Amount"],
                    "Loan_Tenure": loan_details["Loan_Tenure"],
                    "Number_of_Employees": loan_details["Number_of_Employees"],
                    "Business_Registration": loan_details["Business_Registration"],
                    "GST_Registration": loan_details["GST_Registration"],
                    "Annual_Turnover": loan_details["Annual_Turnover"],
                    "Business_Location_Type": loan_details["Business_Location_Type"],
                    "Loan_Purpose": loan_details["Loan_Purpose"],
                    "Collateral_Available": loan_details["Collateral_Available"]
                }

                input_data = pd.DataFrame([features])

                prediction = business_loan_model.predict(input_data)

                ai_prediction = int(prediction[0])

                cursor.execute("""
                    UPDATE loan_applications
                    SET ai_prediction = %s
                    WHERE id = %s
                """, (ai_prediction, application_id))

                db.commit()

                application["ai_prediction"] = ai_prediction


        # ==========================================
        # EDUCATION LOAN
        # ==========================================

        elif loan_type == "Education Loan":

            cursor.execute("""
                SELECT *
                FROM education_loans
                WHERE application_id = %s
            """, (application_id,))

            loan_details = cursor.fetchone()

            if not loan_details:
                cursor.close()
                return "Education loan details not found"

            if application["ai_prediction"] is None:

                features = {
                    "Age": loan_details["Age"],
                    "Education_Level": loan_details["Education_Level"],
                    "Course_Type": loan_details["Course_Type"],
                    "Course_Duration": loan_details["Course_Duration"],
                    "Institution_Type": loan_details["Institution_Type"],
                    "Institution_Location": loan_details["Institution_Location"],
                    "Admission_Status": loan_details["Admission_Status"],
                    "Annual_Course_Fee": loan_details["Annual_Course_Fee"],
                    "Total_Education_Cost": loan_details["Total_Education_Cost"],
                    "Loan_Amount": loan_details["Loan_Amount"],
                    "Family_Monthly_Income": loan_details["Family_Monthly_Income"],
                    "Family_Existing_EMI": loan_details["Family_Existing_EMI"],
                    "Number_of_Dependents": loan_details["Number_of_Dependents"],
                    "Previous_Academic_Performance": loan_details["Previous_Academic_Performance"],
                    "Co_Applicant_Occupation": loan_details["Co_Applicant_Occupation"],
                    "Co_Applicant_Monthly_Income": loan_details["Co_Applicant_Monthly_Income"]
                }

                input_data = pd.DataFrame([features])

                prediction = education_loan_model.predict(input_data)

                ai_prediction = int(prediction[0])

                cursor.execute("""
                    UPDATE loan_applications
                    SET ai_prediction = %s
                    WHERE id = %s
                """, (ai_prediction, application_id))

                db.commit()

                application["ai_prediction"] = ai_prediction


        # ==========================================
        # HOME LOAN
        # ==========================================

        elif loan_type == "Home Loan":

            cursor.execute("""
                SELECT *
                FROM home_loans
                WHERE application_id = %s
            """, (application_id,))

            loan_details = cursor.fetchone()

            if not loan_details:
                cursor.close()
                return "Home loan details not found"

            if application["ai_prediction"] is None:

                features = {
                    "Age": loan_details["Age"],
                    "Occupation": loan_details["Occupation"],
                    "Employment_Type": loan_details["Employment_Type"],
                    "Monthly_Income": loan_details["Monthly_Income"],
                    "Employment_Business_Duration": loan_details["Employment_Business_Duration"],
                    "Existing_Monthly_EMI": loan_details["Existing_Monthly_EMI"],
                    "Loan_Amount": loan_details["Loan_Amount"],
                    "Loan_Tenure": loan_details["Loan_Tenure"],
                    "Property_Value": loan_details["Property_Value"],
                    "Down_Payment": loan_details["Down_Payment"],
                    "Property_Type": loan_details["Property_Type"],
                    "Property_Location_Type": loan_details["Property_Location_Type"],
                    "Number_of_Dependents": loan_details["Number_of_Dependents"]
                }

                input_data = pd.DataFrame([features])

                prediction = home_loan_model.predict(input_data)

                ai_prediction = int(prediction[0])

                cursor.execute("""
                    UPDATE loan_applications
                    SET ai_prediction = %s
                    WHERE id = %s
                """, (ai_prediction, application_id))

                db.commit()

                application["ai_prediction"] = ai_prediction


        # ==========================================
        # PERSONAL LOAN
        # ==========================================

        elif loan_type == "Personal Loan":

            cursor.execute("""
                SELECT *
                FROM personal_loans
                WHERE application_id = %s
            """, (application_id,))

            loan_details = cursor.fetchone()

            if not loan_details:
                cursor.close()
                return "Personal loan details not found"

            if application["ai_prediction"] is None:

                features = {
                    "Age": loan_details["Age"],
                    "Occupation": loan_details["Occupation"],
                    "Employment_Type": loan_details["Employment_Type"],
                    "Monthly_Income": loan_details["Monthly_Income"],
                    "Employment_Business_Duration": loan_details["Employment_Business_Duration"],
                    "Existing_Monthly_EMI": loan_details["Existing_Monthly_EMI"],
                    "Loan_Amount": loan_details["Loan_Amount"],
                    "Loan_Tenure": loan_details["Loan_Tenure"],
                    "Loan_Purpose": loan_details["Loan_Purpose"],
                    "Number_of_Dependents": loan_details["Number_of_Dependents"],
                    "Monthly_Household_Expenses": loan_details["Monthly_Household_Expenses"],
                    "Monthly_Savings_Surplus": loan_details["Monthly_Savings_Surplus"],
                    "Residence_Type": loan_details["Residence_Type"],
                    "Employment_Business_Stability": loan_details["Employment_Business_Stability"]
                }

                input_data = pd.DataFrame([features])

                prediction = personal_loan_model.predict(input_data)

                ai_prediction = int(prediction[0])

                cursor.execute("""
                    UPDATE loan_applications
                    SET ai_prediction = %s
                    WHERE id = %s
                """, (ai_prediction, application_id))

                db.commit()

                application["ai_prediction"] = ai_prediction


        # ==========================================
        # VEHICLE LOAN
        # ==========================================

        elif loan_type == "Vehicle Loan":

            cursor.execute("""
                SELECT *
                FROM vehicle_loans
                WHERE application_id = %s
            """, (application_id,))

            loan_details = cursor.fetchone()

            if not loan_details:
                cursor.close()
                return "Vehicle loan details not found"

            if application["ai_prediction"] is None:

                features = {
                    "Age": loan_details["Age"],
                    "Occupation": loan_details["Occupation"],
                    "Employment_Type": loan_details["Employment_Type"],
                    "Monthly_Income": loan_details["Monthly_Income"],
                    "Employment_Business_Duration": loan_details["Employment_Business_Duration"],
                    "Existing_Monthly_EMI": loan_details["Existing_Monthly_EMI"],
                    "Vehicle_Type": loan_details["Vehicle_Type"],
                    "Vehicle_Condition": loan_details["Vehicle_Condition"],
                    "Vehicle_Price": loan_details["Vehicle_Price"],
                    "Down_Payment": loan_details["Down_Payment"],
                    "Loan_Amount": loan_details["Loan_Amount"],
                    "Loan_Tenure": loan_details["Loan_Tenure"],
                    "Vehicle_Usage": loan_details["Vehicle_Usage"],
                    "Number_of_Dependents": loan_details["Number_of_Dependents"]
                }

                input_data = pd.DataFrame([features])

                prediction = vehicle_loan_model.predict(input_data)

                ai_prediction = int(prediction[0])

                cursor.execute("""
                    UPDATE loan_applications
                    SET ai_prediction = %s
                    WHERE id = %s
                """, (ai_prediction, application_id))

                db.commit()

                application["ai_prediction"] = ai_prediction

        else:
            cursor.close()
            return "Invalid loan type"

        cursor.close()

        return render_template(
            "manager_application.html",
            application=application,
            loan_details=loan_details,
            manager_name=session["manager_name"]
        )

    except mysql.connector.Error as error:
        db.rollback()
        return "Database Error: " + str(error)

    except Exception as error:
        return "ML/Processing Error: " + str(error)
    
# ================= MANAGER LOGOUT =================

@app.route("/manager-logout")
def manager_logout():

    session.pop("manager_id", None)
    session.pop("manager_name", None)

    return redirect(url_for("manager_login"))




# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)