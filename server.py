"""COMS W4111 Project 1, Part 3: restaurant reservation web app (Flask).

This file contains the web layer only: routes, form validation, sessions and
error pages. There is deliberately NO SQL here. Every database operation is a
function in queries.py, which you and your teammate write.

Run locally with Python 3.14:  python server.py
Cloud Run uses the Gunicorn command in Procfile instead of Flask's dev server.
"""

import datetime
import os
from functools import lru_cache, wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

import queries

app = Flask(__name__)
# The secret key only signs the cookie that remembers which user is selected
# (this app has no passwords). Override it with the SECRET_KEY environment
# variable on Cloud Run if you like.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-not-a-secret")

PAYMENT_METHODS = ["Credit Card", "Debit Card", "Apple Pay", "Cash"]
NYC_ZIP_RANGE = (10001, 11697)  # same range as the CHECK in the schema


# ---------------------------------------------------------------------------
# Database connection (from the course starter, unchanged in behaviour)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_engine():
    """Configure the connection pool without opening a connection at import."""
    database_url = URL.create(
        "postgresql+psycopg2",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "5454")),
        database=os.environ.get("DB_NAME", "proj1part2"),
    )
    return create_engine(
        database_url,
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
        pool_timeout=5,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=5000"},
    )


@app.before_request
def before_request():
    """Make a connection available as g.conn for every page except static files."""
    g.conn = None
    g.database_error = None
    g.database_configured = bool(os.environ.get("DB_USER") and os.environ.get("DB_PASSWORD"))
    if request.endpoint in (None, "static"):
        return
    if not g.database_configured:
        g.database_error = "Database credentials are not configured yet. Follow the Cloud Run setup guide."
        return
    try:
        g.conn = get_engine().connect()
        schema = os.environ.get("DB_SCHEMA")
        if schema:
            # Bind the schema value and quote it as one identifier, not raw SQL.
            g.conn.execute(
                text("SELECT set_config('search_path', quote_ident(:schema), false)"),
                {"schema": schema},
            )
            g.conn.commit()
    except (SQLAlchemyError, ValueError, KeyError) as exc:
        # Driver exception messages can contain credentials or connection details.
        app.logger.warning("Database connection failed (%s)", type(exc).__name__)
        if g.conn is not None:
            g.conn.close()
            g.conn = None
        g.database_error = "The database is unavailable. Check the proxy, secrets, and application logs."


@app.teardown_request
def teardown_request(exception):
    """Return the connection to the pool, rolling back unfinished work."""
    conn = g.pop("conn", None)
    if conn is not None:
        conn.close()


def require_connection():
    if g.get("conn") is None:
        abort(503)
    return g.conn


# ---------------------------------------------------------------------------
# Input validation helpers (all user input is checked before it reaches SQL)
# ---------------------------------------------------------------------------

class InputError(Exception):
    """The user typed something we cannot accept; str(error) says what to fix."""


def parse_int(value, label, minimum=None, maximum=None, required=True):
    value = (value or "").strip()
    if not value:
        if required:
            raise InputError(f"{label} is required.")
        return None
    try:
        number = int(value)
    except ValueError:
        raise InputError(f"{label} must be a whole number.")
    if minimum is not None and number < minimum:
        raise InputError(f"{label} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise InputError(f"{label} must be at most {maximum}.")
    return number


def parse_date(value, label="Date"):
    try:
        return datetime.date.fromisoformat((value or "").strip())
    except ValueError:
        raise InputError(f"{label} must be a valid date (YYYY-MM-DD).")


def parse_time(value, label="Time"):
    try:
        return datetime.time.fromisoformat((value or "").strip())
    except ValueError:
        raise InputError(f"{label} must be a valid time (HH:MM).")


def parse_text(value, label, maximum, required=False):
    value = (value or "").strip()
    if required and not value:
        raise InputError(f"{label} is required.")
    if len(value) > maximum:
        raise InputError(f"{label} must be at most {maximum} characters.")
    return value or None


def current_user_id():
    return session.get("user_id")


def login_required(view):
    """Pages that need a selected user send you to the home page to pick one."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user_id() is None:
            flash("Pick who you are first.", "warn")
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped


def safe_next(default_endpoint="index"):
    """Return to a local page after a form; never redirect to another site."""
    target = request.form.get("next", "")
    if target.startswith("/") and not target.startswith("//"):
        return target
    return url_for(default_endpoint)


def optional(call, default):
    """Run a queries.* call but fall back if that function is not written yet,
    so one missing function does not blank an entire page."""
    try:
        return call()
    except NotImplementedError as exc:
        flash(f"Not written yet: {exc}", "warn")
        return default


# ---------------------------------------------------------------------------
# Error pages
# ---------------------------------------------------------------------------

def error_page(message, status):
    return render_template("error.html", message=message, status=status), status


@app.errorhandler(InputError)
def handle_input_error(error):
    return error_page(str(error), 400)


@app.errorhandler(queries.BookingError)
def handle_booking_error(error):
    flash(str(error), "warn")
    return redirect(request.referrer or url_for("index"))


@app.errorhandler(NotImplementedError)
def handle_not_implemented(error):
    return error_page(f"This page needs a database function that has not been written yet: {error}", 501)


@app.errorhandler(SQLAlchemyError)
def handle_database_error(error):
    conn = g.get("conn")
    if conn is not None:
        conn.rollback()
    app.logger.warning("Database operation failed (%s)", type(error).__name__)
    if request.endpoint == "database_check":
        return jsonify(database="unavailable"), 503
    return error_page("The database operation could not be completed. Check the application logs.", 503)


@app.errorhandler(503)
def unavailable(error):
    if request.endpoint == "database_check":
        return jsonify(database="unavailable"), 503
    return error_page(g.get("database_error") or "The database is unavailable.", 503)


@app.errorhandler(400)
def bad_request(error):
    return error_page(getattr(error, "description", None) or "That request could not be understood.", 400)


@app.errorhandler(404)
def not_found(error):
    return error_page("That page or item does not exist.", 404)


@app.errorhandler(405)
def method_not_allowed(error):
    return error_page("That page cannot be used that way.", 405)


@app.errorhandler(500)
def server_error(error):
    return error_page("Something went wrong. The error has been logged.", 500)


# ---------------------------------------------------------------------------
# Home: choose who you are
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    users = []
    if g.conn is not None:
        users = optional(lambda: queries.list_users(g.conn), [])
    elif g.database_error:
        flash(g.database_error, "warn")
    return render_template("index.html", users=users, user_id=current_user_id())


@app.route("/choose-user", methods=["POST"])
def choose_user():
    user_id = parse_int(request.form.get("user_id"), "User", minimum=1)
    user = queries.get_user(require_connection(), user_id)
    if user is None:
        flash("There is no user with that id.", "warn")
        return redirect(url_for("index"))
    session["user_id"] = user["user_id"]
    session["user_name"] = user["name"]
    flash(f"Welcome, {user['name']}.", "ok")
    return redirect(url_for("index"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Feature 1: search restaurants
# ---------------------------------------------------------------------------

@app.route("/restaurants")
def restaurants():
    """Find restaurants, and (optionally) see which tables are free, on ONE page.

    Date, time and party size are optional, but all three are needed to check availability.
    """
    conn = require_connection()
    name = parse_text(request.args.get("name"), "Restaurant name", 100)
    cuisine = parse_text(request.args.get("cuisine"), "Cuisine", 50)
    max_price = parse_int(request.args.get("max_price"), "Maximum price",
                          minimum=0, maximum=100000, required=False)
    zip_min = parse_int(request.args.get("zip_min"), "Lowest zip code",
                        minimum=NYC_ZIP_RANGE[0], maximum=NYC_ZIP_RANGE[1], required=False)
    zip_max = parse_int(request.args.get("zip_max"), "Highest zip code",
                        minimum=NYC_ZIP_RANGE[0], maximum=NYC_ZIP_RANGE[1], required=False)
    if zip_min is not None and zip_max is not None and zip_min > zip_max:
        raise InputError("The lowest zip code cannot be higher than the highest zip code.")
    open_now = request.args.get("open_now") == "on"

    # Availability: all three fields or none.
    raw = {k: (request.args.get(k) or "").strip() for k in ("date", "time", "party_size")}
    check = any(raw.values())
    res_date = res_time = party_size = None
    if check:
        res_date = parse_date(raw["date"])
        res_time = parse_time(raw["time"])
        party_size = parse_int(raw["party_size"], "Party size", minimum=1, maximum=50)
        if res_date < datetime.date.today():
            raise InputError("The date cannot be in the past.")

    cuisines = optional(lambda: queries.list_cuisines(conn), [])
    results = optional(lambda: queries.search_restaurants(
        conn, name=name, cuisine=cuisine, max_price=max_price,
        zip_min=zip_min, zip_max=zip_max, open_now=open_now), [])

    if check and results:
        free = optional(lambda: queries.find_available_tables(
            conn, res_date, res_time, party_size,
            restaurant_ids=[r["restaurant_id"] for r in results]), None)
        by_restaurant = {}
        for t in free or []:
            by_restaurant.setdefault(t["restaurant_id"], []).append(t)
        results = [dict(r, free_tables=by_restaurant.get(r["restaurant_id"], []),
                        deposit=queries.deposit_amount(r["min_price"], party_size)) for r in results]
        if free is None:           # find_available_tables not written: do not claim "fully booked"
            check = False

    form = {"name": name or "", "cuisine": cuisine or "", "max_price": max_price,
            "zip_min": zip_min, "zip_max": zip_max, "open_now": open_now,
            "date": res_date.isoformat() if res_date else "",
            "time": res_time.strftime("%H:%M") if res_time else "",
            "party_size": party_size if party_size is not None else ""}
    return render_template("restaurants.html", results=results, cuisines=cuisines, form=form,
                           check=check, buffer_minutes=queries.BOOKING_BUFFER_MINUTES)


@app.route("/restaurant/<int:restaurant_id>")
def restaurant(restaurant_id):
    conn = require_connection()
    info = queries.get_restaurant(conn, restaurant_id)
    if info is None:
        abort(404)
    tables = optional(lambda: queries.list_tables(conn, restaurant_id), [])
    reviews = optional(lambda: queries.list_reviews(conn, restaurant_id), [])
    is_favorite = False
    if current_user_id() is not None:
        favorites = optional(lambda: queries.list_favorites(conn, current_user_id()), [])
        is_favorite = any(f["restaurant_id"] == restaurant_id for f in favorites)
    prefill = {key: request.args.get(key, "") for key in ("table_no", "date", "time", "party_size")}
    return render_template("restaurant.html", r=info, tables=tables, reviews=reviews,
                           is_favorite=is_favorite, prefill=prefill, payment_methods=PAYMENT_METHODS,
                           deposit_per_person=queries.deposit_amount(info["min_price"], 1),
                           buffer_minutes=queries.BOOKING_BUFFER_MINUTES,
                           user_id=current_user_id())


# ---------------------------------------------------------------------------
# Book a table and pay the (fixed) deposit
# ---------------------------------------------------------------------------

@app.route("/book", methods=["POST"])
@login_required
def book():
    f = request.form
    restaurant_id = parse_int(f.get("restaurant_id"), "Restaurant", minimum=1)
    table_no = parse_int(f.get("table_no"), "Table", minimum=1)
    res_date = parse_date(f.get("date"))
    res_time = parse_time(f.get("time"))
    party_size = parse_int(f.get("party_size"), "Party size", minimum=1, maximum=50)
    requests_text = parse_text(f.get("special_requests"), "Special requests", 500)
    method = f.get("payment_method", "")
    if method not in PAYMENT_METHODS:
        raise InputError("Choose a payment method from the list.")
    if res_date < datetime.date.today():
        raise InputError("The reservation date cannot be in the past.")
    reservation_id = queries.create_reservation(
        require_connection(), current_user_id(), restaurant_id, table_no, res_date, res_time,
        party_size, requests_text, method)
    flash(f"Reservation #{reservation_id} booked.", "ok")
    return redirect(url_for("reservations"))


# ---------------------------------------------------------------------------
# View and cancel reservations
# ---------------------------------------------------------------------------

@app.route("/reservations")
@login_required
def reservations():
    rows = queries.list_reservations(require_connection(), current_user_id())
    return render_template("reservations.html", rows=rows)


@app.route("/reservations/<int:reservation_id>/cancel", methods=["POST"])
@login_required
def cancel(reservation_id):
    if queries.cancel_reservation(require_connection(), current_user_id(), reservation_id):
        flash(f"Reservation #{reservation_id} cancelled.", "ok")
    else:
        flash("That reservation could not be cancelled (it may already have started, "
              "been cancelled, or belong to someone else).", "warn")
    return redirect(url_for("reservations"))


# ---------------------------------------------------------------------------
# Feature 4: reviews
# ---------------------------------------------------------------------------

@app.route("/review", methods=["POST"])
@login_required
def review():
    restaurant_id = parse_int(request.form.get("restaurant_id"), "Restaurant", minimum=1)
    rating = parse_int(request.form.get("rating"), "Rating", minimum=1, maximum=5)
    review_text = parse_text(request.form.get("rating_text"), "Review", 500)
    queries.add_review(require_connection(), current_user_id(), restaurant_id, rating, review_text or "")
    flash("Thanks, your review was added.", "ok")
    return redirect(url_for("restaurant", restaurant_id=restaurant_id))


# ---------------------------------------------------------------------------
# Feature 5: favorites
# ---------------------------------------------------------------------------

@app.route("/favorites")
@login_required
def favorites():
    rows = queries.list_favorites(require_connection(), current_user_id())
    return render_template("favorites.html", rows=rows)


@app.route("/favorites/add", methods=["POST"])
@login_required
def favorites_add():
    restaurant_id = parse_int(request.form.get("restaurant_id"), "Restaurant", minimum=1)
    queries.add_favorite(require_connection(), current_user_id(), restaurant_id)
    flash("Added to your favorites.", "ok")
    return redirect(safe_next("favorites"))


@app.route("/favorites/remove", methods=["POST"])
@login_required
def favorites_remove():
    restaurant_id = parse_int(request.form.get("restaurant_id"), "Restaurant", minimum=1)
    queries.remove_favorite(require_connection(), current_user_id(), restaurant_id)
    flash("Removed from your favorites.", "ok")
    return redirect(safe_next("favorites"))


# ---------------------------------------------------------------------------
# Feature 6: recommendations
# ---------------------------------------------------------------------------

@app.route("/recommendations")
@login_required
def recommendations():
    rows = queries.recommend_restaurants(require_connection(), current_user_id())
    return render_template("recommendations.html", rows=rows)


# ---------------------------------------------------------------------------
# Used by the Cloud Run setup guide to check the database connection
# ---------------------------------------------------------------------------

@app.route("/db-check")
def database_check():
    conn = require_connection()
    value = conn.execute(text("SELECT :value"), {"value": 1}).scalar_one()
    schema_accessible = conn.execute(text("""
        SELECT current_schema() IS NOT NULL
            AND has_schema_privilege(current_schema(), 'USAGE')
    """)).scalar_one()
    return jsonify(
        database="ok",
        select_1=value,
        current_schema_accessible=bool(schema_accessible),
        revision=os.environ.get("K_REVISION", "local"),
    )


if __name__ == "__main__":
    # This is only for local development; Cloud Run runs Gunicorn via Procfile.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8111")))
