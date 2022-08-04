import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_stocks = db.execute("SELECT DISTINCT symbol FROM transactions WHERE user_id=?", session["user_id"])
    stock_list = [stock["symbol"] for stock in user_stocks]
    information_list = []
    cash = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])[0]["cash"]
    user_info = {
        "cash_balance": cash,
        "stock_total": 0
    }
    for stock in stock_list:

        temp_dict = dict()
        temp_dict["symbol"] = stock
        temp_dict["amount"] = db.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND symbol=?", session["user_id"], stock)[0]["SUM(amount)"]
        temp_dict["current_price"] = lookup(stock)["price"]
        temp_dict["current_price_usd"] = usd(temp_dict["current_price"])
        temp_dict["holdings"] = temp_dict["amount"] * temp_dict["current_price"]
        user_info["stock_total"] += temp_dict["holdings"]
        temp_dict["holdings_usd"] = usd(temp_dict["holdings"])
        information_list.append(temp_dict)
    user_info["grand_total"] = user_info["cash_balance"] + user_info["stock_total"]
    user_info["grand_total_usd"] = usd(user_info["grand_total"])
    user_info["cash_balance_usd"] = usd(user_info["cash_balance"])
    print(user_info)

    return render_template("index.html", information=information_list, user_info=user_info)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        transaction = {
        "symbol": request.form.get("symbol"),
        "shares": request.form.get("shares")
        }
        if transaction["symbol"] == None or transaction["shares"] == None:
            return apology("You must input a symbol and an amount of shares!")

        else:
            try:
                transaction["shares"] = int(transaction["shares"])
            except:
                return apology("You must input a valid number of shares!")
            quote = lookup(transaction["symbol"])

            if quote == None:
                return apology("You must enter a valid symbol!")
            if transaction["shares"] < 0 or transaction["shares"] % 1 != 0:
                return apology("You must only input whole numbers!")

            transaction["price"] = quote["price"]
            transaction["total_price"] = transaction["price"] * transaction["shares"]

            # TODO determine whether the user has enough money to complete the transaction
            print(f"Buying {transaction['shares']} shares of {transaction['symbol']} at {transaction['price']} per share, for a total of {transaction['total_price']}.\n")
            cash = db.execute("SELECT cash FROM users WHERE id=?;", session["user_id"])
            print(f"User currently has {usd(cash[0]['cash'])}")
            user_cash = cash[0]['cash']
            if user_cash - transaction["total_price"] >= 0:
                new_balance = user_cash - transaction["total_price"]
                db.execute("UPDATE users SET cash = ? WHERE id = ?;", new_balance, session["user_id"])
                db.execute("INSERT INTO transactions (user_id, buy, symbol, amount, price, date, time) VALUES (?, true, ?, ?, ?, DATE(), TIME());", session["user_id"], transaction["symbol"], transaction["shares"], transaction["price"])
                print("Transaction processed!")
                flash("Transaction processed!")
                return redirect("/")
            else:
                flash("Insufficient balance!")
                return render_template("buy.html")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT buy, symbol, amount, price, date, time FROM transactions WHERE user_id=?", session["user_id"])

    if transactions == None:
        render_template("history.html")

    for tx in transactions:
        if tx["buy"] == 1:
            tx["type"] = "Buy"
        else:
            tx["type"] = "Sell"
            tx["amount"] = tx["amount"] * -1

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash("Succesfully logged in!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # get quote
        symbol = request.form.get("symbol")
        if symbol == "":
            return apology("You must input a symbol!")

        quote = lookup(symbol)

        if quote:
            return render_template("quoted.html", quote=quote)
        else:
            return apology("That symbol does not exist!")

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("username")
        if name == "":
            return apology("You must input a username!")

        user_list = db.execute("SELECT username FROM users WHERE username = ?;", name)

        if len(user_list) != 0:
            return apology("Username already exists!")

        password = request.form.get("password")
        repeatpassword = request.form.get("confirmation")

        if password == "":
            return apology("You must input a password!")

        if password != repeatpassword:
            return apology("The passwords don't match!")

        # Register User
        db.execute('INSERT INTO users(username, hash, cash) VALUES(?, ?, 10000);', name, generate_password_hash(password))
        return redirect("/login")


    else:
        # Render Register page.
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if shares == None or symbol == None:
            return apology("Select a valid stock and share amount!")

        else:
            try:
                shares = int(shares)
            except:
                return apology("Select a valid share amount!")


            available_shares = db.execute("SELECT SUM(amount) FROM transactions WHERE user_id=? AND symbol=?", session["user_id"], symbol)
            if available_shares == None:
                return apology("You don't have any on these shares!")

            available_shares = available_shares[0]["SUM(amount)"]
            if available_shares - shares >= 0:
                # Sell successful
                price = lookup(symbol)["price"]
                sell_value = price * shares
                db.execute("INSERT INTO transactions (user_id, buy, symbol, amount, price, date, time) VALUES (?, false, ?, ?, ?, DATE(), TIME());", session["user_id"], symbol, shares*-1, price)
                db.execute("UPDATE users SET cash = cash + ? WHERE id = ?;", sell_value, session["user_id"])
                flash("Sell successful")
                return redirect("/")
            else:
                return apology("Not enough shares!")

    user_stocks = db.execute("SELECT DISTINCT symbol FROM transactions WHERE user_id=?", session["user_id"])
    stock_list = [stock["symbol"] for stock in user_stocks]

    return render_template("sell.html", stocks=stock_list)
