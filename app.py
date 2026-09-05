from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector, random, pandas as pd, pickle
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "banking_system_secret_key"

db = mysql.connector.connect(host="localhost", user="root", password="akash2005", database="banking")

MODELS = {name: pickle.load(open(f"{name}_loan_model.pkl", "rb"))
          for name in ["business", "education", "home", "personal", "vehicle"]}

# loan_key -> (label, table, [ordered feature/column names])
LOAN_CONFIG = {
    "business": ("Business Loan", "business_loans", [
        "Applicant_Age", "Business_Type", "Business_Age", "Monthly_Business_Revenue",
        "Monthly_Business_Expenses", "Monthly_Business_Profit", "Existing_Business_EMI",
        "Loan_Amount", "Loan_Tenure", "Number_of_Employees", "Business_Registration",
        "GST_Registration", "Annual_Turnover", "Business_Location_Type", "Loan_Purpose",
        "Collateral_Available"]),
    "education": ("Education Loan", "education_loans", [
        "Age", "Education_Level", "Course_Type", "Course_Duration", "Institution_Type",
        "Institution_Location", "Admission_Status", "Annual_Course_Fee", "Total_Education_Cost",
        "Loan_Amount", "Family_Monthly_Income", "Family_Existing_EMI", "Number_of_Dependents",
        "Previous_Academic_Performance", "Co_Applicant_Occupation", "Co_Applicant_Monthly_Income"]),
    "home": ("Home Loan", "home_loans", [
        "Age", "Occupation", "Employment_Type", "Monthly_Income", "Employment_Business_Duration",
        "Existing_Monthly_EMI", "Loan_Amount", "Loan_Tenure", "Property_Value", "Down_Payment",
        "Property_Type", "Property_Location_Type", "Number_of_Dependents"]),
    "personal": ("Personal Loan", "personal_loans", [
        "Age", "Occupation", "Employment_Type", "Monthly_Income", "Employment_Business_Duration",
        "Existing_Monthly_EMI", "Loan_Amount", "Loan_Tenure", "Loan_Purpose", "Number_of_Dependents",
        "Monthly_Household_Expenses", "Monthly_Savings_Surplus", "Residence_Type",
        "Employment_Business_Stability"]),
    "vehicle": ("Vehicle Loan", "vehicle_loans", [
        "Age", "Occupation", "Employment_Type", "Monthly_Income", "Employment_Business_Duration",
        "Existing_Monthly_EMI", "Vehicle_Type", "Vehicle_Condition", "Vehicle_Price", "Down_Payment",
        "Loan_Amount", "Loan_Tenure", "Vehicle_Usage", "Number_of_Dependents"]),
}
# business_loans also stores user_id + application_id (kept for schema compatibility)
BUSINESS_EXTRA_COLS = ["user_id"]


def login_required(kind="user"):
    return (kind + "_id") not in session


def get_account(user_id, fields="*"):
    cur = db.cursor(dictionary=True)
    cur.execute(f"SELECT {fields} FROM accounts WHERE user_id=%s LIMIT 1", (user_id,))
    row = cur.fetchone()
    cur.close()
    return row


# ================= HOME =================

@app.route("/")
def home():
    return render_template("home.html")


# ================= REGISTER / LOGIN / LOGOUT (USER) =================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        try:
            cur = db.cursor()
            cur.execute("INSERT INTO users (full_name,email,phone,password_hash) VALUES (%s,%s,%s,%s)",
                        (f["full_name"], f["email"], f["phone"], generate_password_hash(f["password"])))
            db.commit(); cur.close()
            return redirect(url_for("login"))
        except mysql.connector.Error as e:
            return "Database Error: " + str(e)
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (request.form["email"],))
        user = cur.fetchone(); cur.close()
        if user and check_password_hash(user["password_hash"], request.form["password"]):
            session["user_id"], session["user_name"] = user["id"], user["full_name"]
            return redirect(url_for("dashboard"))
        return "Invalid email or password"
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():
    if login_required():
        return redirect(url_for("login"))
    return render_template("dashboard.html", name=session["user_name"],
                            account=get_account(session["user_id"]))


# ================= CREATE ACCOUNT =================

@app.route("/create-account", methods=["GET", "POST"])
def create_account():
    if login_required():
        return redirect(url_for("login"))
    user_id = session["user_id"]
    if get_account(user_id, "id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        f = request.form
        deposit = float(f["initial_deposit"])
        acc_no = str(random.randint(1000000000, 9999999999))
        try:
            cur = db.cursor()
            cur.execute("""INSERT INTO profiles
                (user_id,date_of_birth,gender,address,city,state,pincode,occupation)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (user_id, f["date_of_birth"], f["gender"], f["address"], f["city"],
                 f["state"], f["pincode"], f["occupation"]))
            cur.execute("""INSERT INTO accounts (user_id,account_number,account_type,balance)
                VALUES (%s,%s,%s,%s)""", (user_id, acc_no, f["account_type"], deposit))
            account_id = cur.lastrowid
            if deposit > 0:
                cur.execute("""INSERT INTO transactions (account_id,transaction_type,amount,description)
                    VALUES (%s,%s,%s,%s)""", (account_id, "Deposit", deposit, "Initial account deposit"))
            db.commit(); cur.close()
            return redirect(url_for("dashboard"))
        except mysql.connector.Error as e:
            db.rollback(); return "Database Error: " + str(e)
    return render_template("create_account.html")


# ================= DEPOSIT / WITHDRAW (shared helper) =================

def deposit_or_withdraw(kind, template):
    if login_required():
        return redirect(url_for("login"))
    account = get_account(session["user_id"], "id,balance")
    if not account:
        return redirect(url_for("create_account"))

    if request.method == "POST":
        amount = float(request.form["amount"])
        if amount <= 0:
            return f"Invalid {kind.lower()} amount"
        if kind == "Withdrawal" and amount > float(account["balance"]):
            return "Insufficient balance"
        sign = "+" if kind == "Deposit" else "-"
        desc = "Money deposited" if kind == "Deposit" else "Money withdrawn"
        try:
            cur = db.cursor()
            cur.execute(f"UPDATE accounts SET balance=balance{sign}%s WHERE id=%s", (amount, account["id"]))
            cur.execute("""INSERT INTO transactions (account_id,transaction_type,amount,description)
                VALUES (%s,%s,%s,%s)""", (account["id"], kind, amount, desc))
            db.commit(); cur.close()
            return redirect(url_for("dashboard"))
        except mysql.connector.Error as e:
            db.rollback(); return "Database Error: " + str(e)
    return render_template(template, balance=account["balance"])


@app.route("/deposite", methods=["GET", "POST"])
def deposite():
    return deposit_or_withdraw("Deposit", "deposite.html")


@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():
    return deposit_or_withdraw("Withdrawal", "withdraw.html")


# ================= TRANSFER MONEY =================

@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    if login_required():
        return redirect(url_for("login"))
    sender = get_account(session["user_id"], "id,account_number,balance")
    if not sender:
        return redirect(url_for("create_account"))

    if request.method == "POST":
        recv_no = request.form["receiver_account_number"]
        amount = float(request.form["amount"])
        if amount <= 0:
            return "Invalid transfer amount"
        if recv_no == sender["account_number"]:
            return "You cannot transfer money to your own account"
        if amount > float(sender["balance"]):
            return "Insufficient balance"
        try:
            cur = db.cursor(dictionary=True)
            cur.execute("SELECT id,account_number FROM accounts WHERE account_number=%s LIMIT 1", (recv_no,))
            receiver = cur.fetchone()
            if not receiver:
                cur.close(); return "Receiver account not found"
            cur.execute("UPDATE accounts SET balance=balance-%s WHERE id=%s", (amount, sender["id"]))
            cur.execute("UPDATE accounts SET balance=balance+%s WHERE id=%s", (amount, receiver["id"]))
            cur.execute("""INSERT INTO transactions (account_id,transaction_type,amount,description)
                VALUES (%s,%s,%s,%s)""",
                (sender["id"], "Transfer", amount, "Money transferred to account " + recv_no))
            cur.execute("""INSERT INTO transactions (account_id,transaction_type,amount,description)
                VALUES (%s,%s,%s,%s)""",
                (receiver["id"], "Transfer", amount, "Money received from account " + sender["account_number"]))
            db.commit(); cur.close()
            return redirect(url_for("dashboard"))
        except mysql.connector.Error as e:
            db.rollback(); return "Database Error: " + str(e)
    return render_template("transfer.html", balance=sender["balance"], account_number=sender["account_number"])


# ================= TRANSACTION HISTORY =================

@app.route("/transactions")
def transactions():
    if login_required():
        return redirect(url_for("login"))
    cur = db.cursor(dictionary=True)
    cur.execute("""SELECT t.transaction_type, t.amount, t.description, t.transaction_date
        FROM transactions t JOIN accounts a ON t.account_id=a.id
        WHERE a.user_id=%s ORDER BY t.transaction_date DESC""", (session["user_id"],))
    rows = cur.fetchall(); cur.close()
    return render_template("transactions.html", transactions=rows)


# ================= ACCOUNT DETAILS =================

@app.route("/account-details")
def account_details():
    if login_required():
        return redirect(url_for("login"))
    cur = db.cursor(dictionary=True)
    cur.execute("""SELECT u.full_name,u.email,u.phone,
            p.date_of_birth,p.gender,p.address,p.city,p.state,p.pincode,p.occupation,
            a.account_number,a.account_type,a.balance,a.created_at
        FROM users u JOIN profiles p ON u.id=p.user_id JOIN accounts a ON u.id=a.user_id
        WHERE u.id=%s LIMIT 1""", (session["user_id"],))
    account = cur.fetchone(); cur.close()
    if not account:
        return redirect(url_for("create_account"))
    return render_template("account_details.html", account=account)


# ================= LOAN APPLICATION (shared for all 5 types) =================

@app.route("/apply-loan")
def apply_loan():
    return render_template("apply_loan.html")


def submit_loan(loan_key):
    if login_required():
        return redirect(url_for("login"))
    label, table, fields = LOAN_CONFIG[loan_key]
    if request.method == "POST":
        user_id = session["user_id"]
        f = request.form
        values = [f[name] for name in fields]
        try:
            cur = db.cursor()
            cur.execute("""INSERT INTO loan_applications (user_id,loan_type,application_status)
                VALUES (%s,%s,%s)""", (user_id, label, "Pending"))
            application_id = cur.lastrowid

            if loan_key == "business":
                # business_loans also stores user_id and application_id
                cols = fields + BUSINESS_EXTRA_COLS + ["application_id"]
                vals = values + [user_id, application_id]
            else:
                cols = ["application_id"] + fields
                vals = [application_id] + values

            placeholders = ",".join(["%s"] * len(vals))
            cur.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})", vals)
            db.commit(); cur.close()
            return f"{label} Application Submitted Successfully"
        except mysql.connector.Error as e:
            db.rollback(); return "Database Error: " + str(e)
    return render_template(f"{loan_key}_loan.html")


@app.route("/business-loan", methods=["GET", "POST"])
def business_loan():
    return submit_loan("business")


@app.route("/education-loan", methods=["GET", "POST"])
def education_loan():
    return submit_loan("education")


@app.route("/home-loan", methods=["GET", "POST"])
def home_loan():
    return submit_loan("home")


@app.route("/personal-loan", methods=["GET", "POST"])
def personal_loan():
    return submit_loan("personal")


@app.route("/vehicle-loan", methods=["GET", "POST"])
def vehicle_loan():
    return submit_loan("vehicle")


# ================= MANAGER: HOME / REGISTER / LOGIN / LOGOUT =================

@app.route("/manager")
def manager_home():
    return render_template("manager_home.html")


@app.route("/manager-register", methods=["GET", "POST"])
def manager_register():
    if request.method == "POST":
        f = request.form
        try:
            cur = db.cursor()
            cur.execute("INSERT INTO managers (full_name,email,password_hash) VALUES (%s,%s,%s)",
                        (f["full_name"], f["email"], generate_password_hash(f["password"])))
            db.commit(); cur.close()
            return redirect(url_for("manager_login"))
        except mysql.connector.Error as e:
            db.rollback(); return "Database Error: " + str(e)
    return render_template("manager_register.html")


@app.route("/manager-login", methods=["GET", "POST"])
def manager_login():
    if request.method == "POST":
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM managers WHERE email=%s", (request.form["email"],))
        manager = cur.fetchone(); cur.close()
        if manager and check_password_hash(manager["password_hash"], request.form["password"]):
            session["manager_id"], session["manager_name"] = manager["id"], manager["full_name"]
            return redirect(url_for("manager_dashboard"))
        return "Invalid manager email or password"
    return render_template("manager_login.html")


@app.route("/manager-logout")
def manager_logout():
    session.pop("manager_id", None)
    session.pop("manager_name", None)
    return redirect(url_for("manager_login"))


# ================= MANAGER DASHBOARD =================

@app.route("/manager-dashboard")
def manager_dashboard():
    if login_required("manager"):
        return redirect(url_for("manager_login"))
    cur = db.cursor(dictionary=True)
    cur.execute("""SELECT id,user_id,loan_type,application_status,ai_prediction,
        manager_decision,rejection_reason,applied_at
        FROM loan_applications ORDER BY applied_at DESC""")
    applications = cur.fetchall(); cur.close()
    return render_template("manager_dashboard.html", applications=applications,
                            manager_name=session["manager_name"])


# ================= MANAGER APPLICATION DETAILS (+ AI PREDICTION) =================

LOAN_KEY_BY_LABEL = {label: key for key, (label, _, _) in LOAN_CONFIG.items()}

@app.route("/manager-application/<int:application_id>")
def manager_application(application_id):
    if login_required("manager"):
        return redirect(url_for("manager_login"))
    try:
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM loan_applications WHERE id=%s", (application_id,))
        application = cur.fetchone()
        if not application:
            cur.close(); return "Application not found"

        loan_key = LOAN_KEY_BY_LABEL.get(application["loan_type"])
        if loan_key is None:
            cur.close(); return "Invalid loan type"

        _, table, fields = LOAN_CONFIG[loan_key]
        cur.execute(f"SELECT * FROM {table} WHERE application_id=%s", (application_id,))
        loan_details = cur.fetchone()
        if not loan_details:
            cur.close(); return f"{loan_key.capitalize()} loan details not found"

        if application["ai_prediction"] is None:
            input_data = pd.DataFrame([{name: loan_details[name] for name in fields}])
            ai_prediction = int(MODELS[loan_key].predict(input_data)[0])
            cur.execute("UPDATE loan_applications SET ai_prediction=%s WHERE id=%s",
                        (ai_prediction, application_id))
            db.commit()
            application["ai_prediction"] = ai_prediction

        cur.close()
        return render_template("manager_application.html", application=application,
                                loan_details=loan_details, manager_name=session["manager_name"])
    except mysql.connector.Error as e:
        db.rollback(); return "Database Error: " + str(e)
    except Exception as e:
        return "ML/Processing Error: " + str(e)


# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)