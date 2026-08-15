from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify
)

import psycopg2
from psycopg2 import Error
from psycopg2.extras import RealDictCursor

from werkzeug.security import generate_password_hash, check_password_hash

from functools import wraps
from datetime import datetime, timedelta

import uuid
import os


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")


# =========================================================
# DATABASE CONFIGURATION
# =========================================================
#
# Render PostgreSQL:
# - Render provides DATABASE_URL for a linked PostgreSQL database.
# - For local development, PG_* variables can be used.
#
DATABASE_URL = os.environ.get("DATABASE_URL")

DB_CONFIG = {
    "host": os.environ.get("PGHOST", "localhost"),
    "port": int(os.environ.get("PGPORT", "5432")),
    "user": os.environ.get("PGUSER", "postgres"),
    "password": os.environ.get("PGPASSWORD", ""),
    "dbname": os.environ.get("PGDATABASE", "eventora")
}


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)

    return psycopg2.connect(**DB_CONFIG)


# =========================================================
# TIME FILTER
# =========================================================
#
# IMPORTANT:
# MySQL TIME values are returned by PostgreSQL driver
# as datetime.timedelta objects.
#
# Therefore we MUST NOT use:
#

#
# in Jinja.
#
# Instead use:
#
# {{ event.event_time|time12 }}
# =========================================================

@app.template_filter("time12")
def time12(value):

    if value is None:
        return ""

    # MySQL TIME -> datetime.timedelta
    if isinstance(value, timedelta):

        total_seconds = int(
            value.total_seconds()
        )

        hours = (
            total_seconds // 3600
        ) % 24

        minutes = (
            total_seconds % 3600
        ) // 60

        suffix = "AM" if hours < 12 else "PM"

        hour = hours % 12

        if hour == 0:
            hour = 12

        return f"{hour:02d}:{minutes:02d} {suffix}"

    # datetime.time / datetime.datetime
    if hasattr(value, "strftime"):

        return value.strftime(
            "%I:%M %p"
        )

    return str(value)


# =========================================================
# LOGIN REQUIRED
# =========================================================

def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please log in to continue.",
                "warning"
            )

            return redirect(
                url_for("login")
            )

        return view(*args, **kwargs)

    return wrapped


# =========================================================
# ADMIN REQUIRED
# =========================================================

def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if session.get("role") != "admin":

            flash(
                "Admin access is required.",
                "danger"
            )

            return redirect(
                url_for("home")
            )

        return view(*args, **kwargs)

    return wrapped


# =========================================================
# GLOBAL TEMPLATE VARIABLES
# =========================================================

@app.context_processor
def inject_globals():

    return {
        "current_year": datetime.now().year,
        "logged_in": "user_id" in session,
        "session_user": session.get("user_name"),
        "session_role": session.get("role")
    }


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    db = get_db_connection()

    cursor = db.cursor(
        cursor_factory=RealDictCursor
    )

    try:

        cursor.execute("""
            SELECT
                e.*,

                COALESCE(
                    SUM(
                        CASE
                            WHEN r.status = 'confirmed'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS registered_count

            FROM events e

            LEFT JOIN registrations r
                ON e.id = r.event_id

            WHERE
                e.status = 'published'
                AND e.event_date >= CURRENT_DATE

            GROUP BY e.id

            ORDER BY
                e.event_date,
                e.event_time

            LIMIT 9
        """)

        events = cursor.fetchall()

        return render_template(
            "index.html",
            events=events
        )

    finally:

        cursor.close()
        db.close()


# =========================================================
# EXPLORE EVENTS
# =========================================================

@app.route("/events")
def events():

    q = request.args.get(
        "q",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    ).strip()

    price = request.args.get(
        "price",
        ""
    ).strip()


    db = get_db_connection()

    cursor = db.cursor(
        cursor_factory=RealDictCursor
    )


    try:

        query = """
            SELECT
                e.*,

                COALESCE(
                    SUM(
                        CASE
                            WHEN r.status = 'confirmed'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS registered_count

            FROM events e

            LEFT JOIN registrations r
                ON e.id = r.event_id

            WHERE
                e.status = 'published'
                AND e.event_date >= CURRENT_DATE
        """

        params = []


        if q:

            query += """
                AND (
                    e.title LIKE %s
                    OR e.description LIKE %s
                    OR e.venue LIKE %s
                    OR e.category LIKE %s
                )
            """

            search = f"%{q}%"

            params.extend([
                search,
                search,
                search,
                search
            ])


        if category:

            query += """
                AND e.category = %s
            """

            params.append(
                category
            )


        if price == "free":

            query += """
                AND e.price = 0
            """


        elif price == "paid":

            query += """
                AND e.price > 0
            """


        query += """
            GROUP BY e.id

            ORDER BY
                e.event_date,
                e.event_time
        """


        cursor.execute(
            query,
            params
        )

        event_list = cursor.fetchall()


        cursor.execute("""
            SELECT
                id,
                name

            FROM categories

            ORDER BY name
        """)

        categories = cursor.fetchall()


        return render_template(
            "events.html",
            events=event_list,
            categories=categories,
            q=q,
            selected_category=category,
            selected_price=price
        )


    finally:

        cursor.close()
        db.close()


# =========================================================
# EVENT DETAILS
# =========================================================

@app.route(
    "/event/<int:event_id>"
)
def event_detail(event_id):

    db = get_db_connection()

    cursor = db.cursor(
        cursor_factory=RealDictCursor
    )


    try:

        cursor.execute(
            """
            SELECT *
            FROM events
            WHERE id = %s
            """,
            (event_id,)
        )

        event = cursor.fetchone()


        if not event:

            flash(
                "Event not found.",
                "danger"
            )

            return redirect(
                url_for("events")
            )


        cursor.execute(
            """
            SELECT
                COUNT(*) AS registered_count

            FROM registrations

            WHERE
                event_id = %s
                AND status = 'confirmed'
            """,
            (event_id,)
        )

        result = cursor.fetchone()


        registered_count = (
            result["registered_count"]
            or 0
        )


        event["registered_count"] = (
            registered_count
        )


        event["seats_left"] = max(
            0,
            event["total_seats"]
            - registered_count
        )


        cursor.execute(
            """
            SELECT
                AVG(rating) AS avg_rating,
                COUNT(*) AS review_count

            FROM feedback

            WHERE event_id = %s
            """,
            (event_id,)
        )

        rating = cursor.fetchone()


        already_registered = False


        if session.get("user_id"):

            cursor.execute(
                """
                SELECT id

                FROM registrations

                WHERE
                    user_id = %s
                    AND event_id = %s
                    AND status = 'confirmed'
                """,
                (
                    session["user_id"],
                    event_id
                )
            )

            already_registered = (
                cursor.fetchone()
                is not None
            )


        return render_template(
            "event_detail.html",
            event=event,
            rating=rating,
            already_registered=already_registered
        )


    finally:

        cursor.close()
        db.close()


# =========================================================
# REGISTER ACCOUNT
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )


        if not name:

            flash(
                "Please enter your full name.",
                "warning"
            )

            return redirect(
                url_for("register")
            )


        if not email:

            flash(
                "Please enter your email.",
                "warning"
            )

            return redirect(
                url_for("register")
            )


        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "warning"
            )

            return redirect(
                url_for("register")
            )


        db = get_db_connection()

        cursor = db.cursor()


        try:

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            if cursor.fetchone():

                flash(
                    "An account with this email already exists.",
                    "warning"
                )

                return redirect(
                    url_for("login")
                )


            password_hash = (
                generate_password_hash(
                    password
                )
            )


            cursor.execute(
                """
                INSERT INTO users
                (
                    name,
                    email,
                    phone,
                    password_hash,
                    role,
                    is_verified
                )

                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    'user',
                    TRUE
                )
                """,
                (
                    name,
                    email,
                    phone,
                    password_hash
                )
            )


            db.commit()


            flash(
                "Account created successfully. Please log in.",
                "success"
            )


            return redirect(
                url_for("login")
            )


        except Error as exc:

            db.rollback()

            flash(
                f"Registration failed: {exc}",
                "danger"
            )


        finally:

            cursor.close()
            db.close()


    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )


        db = get_db_connection()

        cursor = db.cursor(
            cursor_factory=RealDictCursor
        )


        try:

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            user = cursor.fetchone()

        finally:

            cursor.close()
            db.close()


        valid = False


        if user:

            stored_password = (
                user.get("password_hash")
            )


            if stored_password:

                try:

                    valid = (
                        check_password_hash(
                            stored_password,
                            password
                        )
                    )

                except ValueError:

                    valid = (
                        stored_password
                        == password
                    )


        if valid:

            session["user_id"] = user["id"]

            session["user_name"] = user["name"]

            session["role"] = user["role"]


            flash(
                f"Welcome back, {user['name']}!",
                "success"
            )


            if user["role"] == "admin":

                return redirect(
                    url_for("admin")
                )


            return redirect(
                url_for("dashboard")
            )


        flash(
            "Invalid email or password.",
            "danger"
        )


    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("home")
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    db = get_db_connection()

    cursor = db.cursor(
        cursor_factory=RealDictCursor
    )


    try:

        cursor.execute(
            """
            SELECT
                r.*,

                e.title,
                e.description,
                e.category,
                e.event_date,
                e.event_time,
                e.venue,
                e.banner_image,
                e.price

            FROM registrations r

            JOIN events e
                ON e.id = r.event_id

            WHERE
                r.user_id = %s
                AND r.status = 'confirmed'

            ORDER BY
                e.event_date,
                e.event_time
            """,
            (session["user_id"],)
        )

        registrations = cursor.fetchall()


        return render_template(
            "dashboard.html",
            registrations=registrations
        )


    finally:

        cursor.close()
        db.close()


# =========================================================
# REGISTER FOR EVENT
# =========================================================

@app.route(
    "/event/<int:event_id>/register",
    methods=["POST"]
)
@login_required
def register_event(event_id):

    db = get_db_connection()

    cursor = db.cursor(
        cursor_factory=RealDictCursor
    )


    try:

        cursor.execute(
            """
            SELECT *
            FROM events
            WHERE id = %s
            FOR UPDATE
            """,
            (event_id,)
        )

        event = cursor.fetchone()


        if not event:

            flash(
                "Event not found.",
                "danger"
            )

            return redirect(
                url_for("events")
            )


        if event["status"] != "published":

            flash(
                "This event is not available.",
                "warning"
            )

            return redirect(
                url_for(
                    "event_detail",
                    event_id=event_id
                )
            )


        if event["event_date"] < datetime.now().date():

            flash(
                "Registration for this event has closed.",
                "warning"
            )

            return redirect(
                url_for(
                    "event_detail",
                    event_id=event_id
                )
            )


        deadline = event.get(
            "registration_deadline"
        )


        if deadline:

            if datetime.now().date() > deadline:

                flash(
                    "The registration deadline has passed.",
                    "warning"
                )

                return redirect(
                    url_for(
                        "event_detail",
                        event_id=event_id
                    )
                )


        cursor.execute(
            """
            SELECT
                COUNT(*) AS count

            FROM registrations

            WHERE
                event_id = %s
                AND status = 'confirmed'
            """,
            (event_id,)
        )

        booked = cursor.fetchone()["count"]


        if booked >= event["total_seats"]:

            flash(
                "Sorry, this event is sold out.",
                "warning"
            )

            return redirect(
                url_for(
                    "event_detail",
                    event_id=event_id
                )
            )


        cursor.execute(
            """
            SELECT id

            FROM registrations

            WHERE
                user_id = %s
                AND event_id = %s
                AND status = 'confirmed'
            """,
            (
                session["user_id"],
                event_id
            )
        )


        if cursor.fetchone():

            flash(
                "You are already registered for this event.",
                "warning"
            )

            return redirect(
                url_for("dashboard")
            )


        ticket_id = (
            "TKT-"
            + uuid.uuid4().hex[:10].upper()
        )


        cursor.execute(
            """
            INSERT INTO registrations
            (
                user_id,
                event_id,
                registration_date,
                ticket_id,
                attendance_status,
                status
            )

            VALUES
            (
                %s,
                %s,
                NOW(),
                %s,
                'absent',
                'confirmed'
            )
            RETURNING id
            """,
            (
                session["user_id"],
                event_id,
                ticket_id
            )
        )


        registration_row = cursor.fetchone()
        registration_id = registration_row['id']


        amount = float(
            event["price"] or 0
        )


        if amount == 0:

            payment_status = "success"

            transaction_id = (
                "FREE-" + ticket_id
            )

            payment_method = "Free"


        else:

            payment_status = "pending"

            transaction_id = None

            payment_method = "Demo"


        cursor.execute(
            """
            INSERT INTO payments
            (
                registration_id,
                amount,
                payment_status,
                transaction_id,
                payment_method
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                registration_id,
                amount,
                payment_status,
                transaction_id,
                payment_method
            )
        )


        new_seats = max(
            0,
            event["total_seats"] - booked - 1
        )


        cursor.execute(
            """
            UPDATE events

            SET seats_available = %s

            WHERE id = %s
            """,
            (
                new_seats,
                event_id
            )
        )


        cursor.execute(
            """
            INSERT INTO notifications
            (
                user_id,
                message,
                type
            )

            VALUES
            (
                %s,
                %s,
                'registration'
            )
            """,
            (
                session["user_id"],
                f"Your registration for '{event['title']}' is confirmed. Ticket ID: {ticket_id}"
            )
        )


        db.commit()


        flash(
            "Registration confirmed! Your ticket is ready.",
            "success"
        )


        return redirect(
            url_for("dashboard")
        )


    except Error as exc:

        db.rollback()

        flash(
            f"Registration failed: {exc}",
            "danger"
        )

        return redirect(
            url_for(
                "event_detail",
                event_id=event_id
            )
        )


    finally:

        cursor.close()
        db.close()


# =========================================================
# ADMIN
# =========================================================

@app.route("/admin")
@admin_required
def admin():

    db = get_db_connection()

    cursor = db.cursor(
        cursor_factory=RealDictCursor
    )


    try:

        cursor.execute(
            "SELECT COUNT(*) AS c FROM users"
        )

        total_users = cursor.fetchone()["c"]


        cursor.execute(
            "SELECT COUNT(*) AS c FROM events"
        )

        total_events = cursor.fetchone()["c"]


        cursor.execute(
            """
            SELECT COUNT(*) AS c
            FROM registrations
            WHERE status = 'confirmed'
            """
        )

        total_registrations = (
            cursor.fetchone()["c"]
        )


        cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(amount),
                    0
                ) AS total

            FROM payments

            WHERE payment_status = 'success'
            """
        )

        revenue = cursor.fetchone()["total"]


        cursor.execute(
            """
            SELECT
                e.*,

                COALESCE(
                    SUM(
                        CASE
                            WHEN r.status = 'confirmed'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS registered_count

            FROM events e

            LEFT JOIN registrations r
                ON e.id = r.event_id

            GROUP BY e.id

            ORDER BY e.event_date DESC
            """
        )

        events_list = cursor.fetchall()


        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                phone,
                role,
                created_at

            FROM users

            ORDER BY created_at DESC

            LIMIT 20
            """
        )

        users = cursor.fetchall()


        return render_template(
            "admin.html",
            total_users=total_users,
            total_events=total_events,
            total_registrations=total_registrations,
            revenue=revenue,
            events=events_list,
            users=users
        )


    finally:

        cursor.close()
        db.close()


# =========================================================
# CREATE EVENT
# =========================================================

@app.route(
    "/admin/events/new",
    methods=["GET", "POST"]
)
@admin_required
def create_event():

    if request.method == "POST":

        data = request.form


        try:

            total_seats = int(
                data["total_seats"]
            )

            if total_seats <= 0:
                raise ValueError

        except (ValueError, KeyError):

            flash(
                "Please enter a valid number of seats.",
                "warning"
            )

            return render_template(
                "event_form.html"
            )


        try:

            price = float(
                data.get("price") or 0
            )

            if price < 0:
                raise ValueError

        except ValueError:

            flash(
                "Please enter a valid price.",
                "warning"
            )

            return render_template(
                "event_form.html"
            )


        db = get_db_connection()

        cursor = db.cursor()


        try:

            cursor.execute(
                """
                INSERT INTO events
                (
                    title,
                    description,
                    category,
                    venue,
                    event_date,
                    event_time,
                    registration_deadline,
                    total_seats,
                    seats_available,
                    price,
                    banner_image,
                    status,
                    organizer_id
                )

                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'published',
                    %s
                )
                """,
                (
                    data["title"].strip(),
                    data["description"].strip(),
                    data["category"].strip(),
                    data["venue"].strip(),
                    data["event_date"],
                    data["event_time"],
                    data.get(
                        "registration_deadline"
                    ) or None,
                    total_seats,
                    total_seats,
                    price,
                    data.get(
                        "banner_image"
                    ) or "event-tech.svg",
                    session["user_id"]
                )
            )


            db.commit()


            flash(
                "Event published successfully.",
                "success"
            )


            return redirect(
                url_for("admin")
            )


        except Error as exc:

            db.rollback()

            flash(
                f"Could not create event: {exc}",
                "danger"
            )


        finally:

            cursor.close()
            db.close()


    return render_template(
        "event_form.html"
    )


# =========================================================
# CANCEL EVENT
# =========================================================

@app.route(
    "/admin/events/<int:event_id>/delete",
    methods=["POST"]
)
@admin_required
def delete_event(event_id):

    db = get_db_connection()

    cursor = db.cursor()


    try:

        cursor.execute(
            """
            UPDATE events

            SET status = 'cancelled'

            WHERE id = %s
            """,
            (event_id,)
        )


        db.commit()


        flash(
            "Event cancelled.",
            "success"
        )


    except Error as exc:

        db.rollback()

        flash(
            str(exc),
            "danger"
        )


    finally:

        cursor.close()
        db.close()


    return redirect(
        url_for("admin")
    )


# =========================================================
# ADMIN CHART DATA
# =========================================================

@app.route(
    "/api/admin/chart-data"
)
@admin_required
def chart_data():

    db = get_db_connection()

    cursor = db.cursor(
        cursor_factory=RealDictCursor
    )


    try:

        cursor.execute(
            """
            SELECT
                category,
                COUNT(*) AS total

            FROM events

            GROUP BY category

            ORDER BY total DESC
            """
        )

        categories = cursor.fetchall()


        cursor.execute(
            """
            SELECT
                TO_CHAR(
                    e.event_date,
                    'Mon'
                ) AS month,

                COUNT(*) AS total

            FROM registrations r

            JOIN events e
                ON e.id = r.event_id

            WHERE
                r.status = 'confirmed'

            GROUP BY
                YEAR(e.event_date),
                MONTH(e.event_date)

            ORDER BY
                YEAR(e.event_date),
                MONTH(e.event_date)
            """
        )

        monthly = cursor.fetchall()


        return jsonify(
            {
                "categories": categories,
                "monthly": monthly
            }
        )


    finally:

        cursor.close()
        db.close()


# =========================================================
# FEEDBACK
# =========================================================

@app.route(
    "/feedback/<int:event_id>",
    methods=["POST"]
)
@login_required
def feedback(event_id):

    try:

        rating = int(
            request.form["rating"]
        )

    except (ValueError, KeyError):

        flash(
            "Please select a valid rating.",
            "warning"
        )

        return redirect(
            url_for(
                "event_detail",
                event_id=event_id
            )
        )


    comment = request.form.get(
        "comment",
        ""
    ).strip()


    if rating < 1 or rating > 5:

        flash(
            "Rating must be between 1 and 5.",
            "warning"
        )

        return redirect(
            url_for(
                "event_detail",
                event_id=event_id
            )
        )


    db = get_db_connection()

    cursor = db.cursor()


    try:

        cursor.execute(
            """
            SELECT id

            FROM registrations

            WHERE
                user_id = %s
                AND event_id = %s
                AND status = 'confirmed'
            """,
            (
                session["user_id"],
                event_id
            )
        )


        if not cursor.fetchone():

            flash(
                "You can leave feedback only for events you registered for.",
                "warning"
            )

            return redirect(
                url_for(
                    "event_detail",
                    event_id=event_id
                )
            )


        cursor.execute(
            """
            INSERT INTO feedback
            (
                event_id,
                user_id,
                rating,
                comment
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                event_id,
                session["user_id"],
                rating,
                comment
            )
        )


        db.commit()


        flash(
            "Thank you for your feedback!",
            "success"
        )


    except Error as exc:

        db.rollback()

        flash(
            str(exc),
            "danger"
        )


    finally:

        cursor.close()
        db.close()


    return redirect(
        url_for(
            "event_detail",
            event_id=event_id
        )
    )


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", "5000"))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
