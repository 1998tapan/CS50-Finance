import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
# <class 'cs50.sql.SQL'>
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # get user_id
    user_id = int(session['user_id'])
    try:
        # get user's total shares company wise and stock symbol
        user_data = db.execute("SELECT company_symbol AS symbol, SUM(shares) AS shares FROM stocks_purchased WHERE id = :user_id GROUP BY company_symbol",
                               user_id=user_id)
        # fetch current price, company_name  of the stock from API via stock symbol
        # and add them to it's respective stock in user_data dict
        total_user_money = 0
        for row in user_data:
            stock_info = lookup(row['symbol'])
            row['name'] = stock_info['name']
            # price is converted to float by helper method lookup()
            row['price'] = usd(stock_info['price'])
            # shares is stored as an integer in database
            total_shares_cost = row['shares'] * stock_info['price']
            total_user_money += total_shares_cost
            row['total'] = usd(total_shares_cost)

        # [{'cash': 7296.79}]
        user = db.execute("SELECT username, cash FROM users WHERE id = :user_id",
                               user_id=user_id)
        user_cash = user[0]['cash']
        user_name = user[0]['username']
        total_user_money += user_cash

    except Exception as e:
        return apology(e, 500)

    return render_template("index.html", user_data=user_data, user_cash=usd(user_cash), total_user_money=usd(total_user_money))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == 'POST':
        """Buy shares of stock"""

        # take symbols and shares from user
        symbol = request.form['symbol']
        shares = int(request.form['shares'])

        # validate them
        if not symbol:
            return apology("Must provide a symbol", 403)

        if not shares:
            return apology("Must provide the number of shares", 403)

        if shares < 1:
            return apology("Invalid number of shares", 403)

        # get company_name and their current price
        stock_dict = lookup(symbol)
        # validate it
        if not stock_dict:
            return apology("Invalid stock symbol", 403)

        company_name = stock_dict['name']
        stock_price = float(stock_dict['price'])
        symbol = stock_dict['symbol']

        # take user_id to identify user
        user_id = int(session["user_id"])

        # total cost for purchasing shares -> this will be deducted from user's cash
        total_cost = float(shares * stock_price)

        # get user data from database
        # <class 'list'>
        # [{'id': 2, 'username': 'Tapan681', 'hash': 'pwd hash', 'cash': 10000}]
        user_data = db.execute('SELECT * FROM users WHERE id = :id',
                               id=user_id)
        user_cash = float(user_data[0]['cash'])
        # now we have all the data

        # check if user has enough cash to buy shares
        if user_cash < total_cost:
            return apology("Insufficient funds", 403)

        # add stocks purchase info to database
        # and if successful, deduct cash from user
        try:
            db.execute(
                'INSERT INTO stocks_purchased(id, company_name, company_symbol, shares, stock_price, total_cost) VALUES(:uid, :name, :sym, :share, :price, :total_cost)',
                uid=user_id,
                name=company_name,
                sym=symbol,
                share=shares,
                price=stock_price,
                total_cost=total_cost)

            db.execute('UPDATE users SET cash = :cash WHERE id=:id',
                       cash=(user_cash-total_cost),
                       id=user_id)

        except Exception as e:
            return apology(str(e), 403)
        flash("Purchase successful !!")
        return redirect("/")

    else:
        return render_template("buy.html")


"""
        if val > 0:
            db.execute('UPDATE')
            return apology("success !")
"""


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
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
    if request.method == 'POST':
        """Get stock quote."""
        symbol = request.form['symbol']
        stock_dict = lookup(symbol)
        if not stock_dict:
            return apology("Missing symbol", 403)

        else:
            return render_template("quoted.html", stock_dict=stock_dict)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user ---DONE!"""
    session.clear()
    if request.method == 'POST':
        username = request.form["username"]
        password = request.form['password']
        confirm_password = request.form['confirmation']

        if not username:
            return apology("must provide username", 403)

        elif not password:
            return apology("must provide password", 403)

        elif not confirm_password:
            return apology("must provide confirm password", 403)

        elif password != confirm_password:
            return apology("password and confirm-password must match", 403)

        row = db.execute('SELECT * FROM users WHERE username= :username',
                         username=username)
        if len(row) > 0:
            return apology("Username already taken", 403)

        else:
            db.execute("INSERT INTO users(username,hash) VALUES(:username, :hash)",
                       username=username,
                       hash=generate_password_hash(password))
        flash("Registration successful !!")
        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    return apology("TODO")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
