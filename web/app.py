"""MyTickets web app (Flask).

Three tiers: browser (HTML) -> this Flask app -> MySQL.
All ticket rules live in the database (triggers + procedures). This app only
signs people in, picks the right MySQL account, calls the procedures and shows results.
"""
import hashlib
import hmac
import os
import re
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps

import mysql.connector
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from markupsafe import Markup
from PIL import Image
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

import db

try:  # QR codes on the tickets. The app still runs without it (tickets then show the code as text only).
    import segno
except ImportError:
    segno = None

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  MAX_CONTENT_LENGTH=6 * 1024 * 1024)  # uploads (posters) are limited to 6 MB
app.teardown_appcontext(db.close_all)

# The database has no price table, so prices live here (VND per ticket).
# Zone names must match seat.seat_zone in the database. STANDING is special (no seat numbers).
PRICES = {"SKYBOX": 2500000, "VIP": 1500000, "A": 800000, "BALCONY": 700000, "B": 500000, "STANDING": 450000}
ZONE_LABEL = {"SKYBOX": "Sky Box", "VIP": "VIP", "A": "Zone A", "BALCONY": "Balcony", "B": "Zone B",
              "STANDING": "Standing"}
# Which zones each venue has. A venue not listed here falls back to "every zone that has seats".
# The map for a venue is templates/maps/<venue-name-as-slug>.html (e.g. aurora-arena.html).
VENUE_ZONES = {
    "The Velvet Room": ["VIP", "A", "STANDING"],
    "Lantern Hall": ["VIP", "A", "B"],
    "Starlight Theatre": ["SKYBOX", "VIP", "A", "BALCONY"],
    "Aurora Arena": ["SKYBOX", "VIP", "A", "B", "STANDING"],
    "Skyline Dome": ["SKYBOX", "VIP", "A", "B", "STANDING"],
}
MAX_PER_EVENT = 2  # tickets one customer may hold for one event, all zones together
ORDER_HOLD_MINUTES = 15  # minutes to pay a pending order; keep equal to fn_order_hold_minutes() in the database
PAY_METHODS = ["Card", "Bank transfer", "E-wallet"]
LOW_STOCK = 10  # "Only N left" is shown from this number down
UPGRADE_HINT = "This needs the database update in database/upgrade_existing_db.sql."


# ---------------------------------------------------------------- helpers
@app.template_filter("vnd")
def vnd(value):
    return "{:,.0f} đ".format(value or 0)


@app.template_filter("when")
def when(value):
    return value.strftime("%a %d %b, %H:%M") if value else ""


@app.template_filter("stamp")
def stamp(value):
    return value.strftime("%d %b %Y, %H:%M") if value else ""


@app.template_filter("dt")
def dt(value, fmt):
    """Free strftime format, e.g. {{ ev.start_time|dt('%d') }}."""
    return value.strftime(fmt) if value else ""


@app.template_filter("local_input")
def local_input(value):
    """Value for <input type="datetime-local">."""
    return value.strftime("%Y-%m-%dT%H:%M") if value else ""


def poster_url(event_id):
    """Poster image is static/events/<event_id>.jpg. Returns None when the file is missing.
    The file time is added to the address, so a replaced poster shows up at once."""
    path = os.path.join(app.static_folder, "events", event_id + ".jpg")
    if not os.path.isfile(path):
        return None
    return url_for("static", filename="events/" + event_id + ".jpg", v=int(os.path.getmtime(path)))


def save_poster(event_id, upload):
    """Check an uploaded poster and store it as static/events/<event_id>.jpg.
    The file name comes from the event id, never from the uploaded name.
    Returns an error message, or None when saved (or when nothing was uploaded)."""
    if upload is None or not upload.filename:
        return None
    try:
        Image.open(upload.stream).verify()  # is it really an image?
        upload.stream.seek(0)
        img = Image.open(upload.stream).convert("RGB")
    except Exception:
        return "The poster is not a valid image. Use a JPG, PNG or WebP file."
    img.thumbnail((1200, 1600))
    os.makedirs(os.path.join(app.static_folder, "events"), exist_ok=True)
    img.save(os.path.join(app.static_folder, "events", event_id + ".jpg"), "JPEG", quality=88)
    return None


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token
app.jinja_env.globals["ZONE_LABEL"] = ZONE_LABEL
app.jinja_env.globals["HOLD_MINUTES"] = ORDER_HOLD_MINUTES


@app.context_processor
def inject_user():
    return {"user": session.get("user")}


@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        if not sent or not secrets.compare_digest(sent, session.get("_csrf", "")):
            abort(400)


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


def safe_next(target):
    """Only allow redirects to a path on this site."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return None


def friendly(e):
    """Message from a database rule (SIGNAL) is safe to show; anything else is not."""
    if e.errno == db.ER_SIGNAL:
        return e.msg
    if e.errno in (db.ER_NO_SUCH_ROUTINE, db.ER_ROUTINE_DENIED):
        return UPGRADE_HINT
    app.logger.error("Database error %s: %s", e.errno, e.msg)
    return "Something went wrong. Please try again."


def customer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        u = session.get("user")
        if not u:
            return redirect(url_for("signin", next=request.full_path.rstrip("?")))
        if u["role"] != "customer":
            return redirect(url_for("admin_dashboard"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        u = session.get("user")
        if not u:
            return redirect(url_for("signin", next=request.full_path.rstrip("?")))
        if u["role"] != "admin":
            return redirect(url_for("home"))
        return view(*args, **kwargs)

    return wrapped


def is_super():
    return (session.get("user") or {}).get("level") == "super_admin"


# Newer database objects (database/upgrade_existing_db.sql). The app asks once whether each one is
# there and switches the matching feature off when it is not, instead of failing.
# Each probe touches the routine with an id that cannot exist, so nothing is ever changed.
_FEATURES = {
    "standing_left": ("customer", "SELECT fn_standing_left(%s)"),
    "edit_profile": ("customer", "CALL pc_update_customer(%s, NULL, NULL, NULL, NULL)"),
    "edit_event": ("admin", "CALL pc_update_event(%s, NULL, NULL, NULL, NULL, NULL, NULL)"),
}
_feature_cache = {}  # name -> (available, time of the check)


def has_feature(name):
    hit = _feature_cache.get(name)
    if hit and (hit[0] or time.monotonic() - hit[1] < 60):  # "missing" is asked again after a minute
        return hit[0]
    role, sql = _FEATURES[name]
    try:
        db.fetch_all(role, sql, ("",))
        found = True
    except mysql.connector.Error as e:
        found = e.errno == db.ER_SIGNAL  # the routine answered "... not found": it exists
        if not found and e.errno not in (db.ER_NO_SUCH_ROUTINE, db.ER_ROUTINE_DENIED):
            app.logger.error("Feature check %s failed: %s %s", name, e.errno, e.msg)
    _feature_cache[name] = (found, time.monotonic())
    return found


app.jinja_env.globals["has_feature"] = has_feature


def sale_state(now, sale_time, start_time):
    """soon = sales not open yet, open = on sale, ended = the event has started."""
    if now < sale_time:
        return "soon"
    if now >= start_time:
        return "ended"
    return "open"


def venue_zone_keys(venue, standing_capacity):
    """Zones of a venue, most expensive first. STANDING only when the event has a standing area."""
    wanted = VENUE_ZONES.get(venue)
    keys = [k for k in PRICES if wanted is None or k in wanted]
    if not standing_capacity:
        keys = [k for k in keys if k != "STANDING"]
    return keys


def parse_local(value):
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------- errors
@app.errorhandler(413)
def too_large(_e):
    flash("That file is too big (6 MB at most).", "error")
    return redirect(url_for("admin_dashboard" if (session.get("user") or {}).get("role") == "admin" else "home"))


_ERROR_TEXT = {
    400: ("This form is out of date", "The page was open for too long, or it was sent twice. "
                                      "Go back, reload the page and try again."),
    404: ("Nothing is playing here", "This page does not exist. The event may have been removed, "
                                     "or the address is mistyped."),
    405: ("That does not work from here", "Use the buttons on the page instead of opening this address directly."),
    500: ("Something broke on our side", "The page could not be built. Reload it; if it keeps happening, "
                                         "the terminal that runs Flask shows the reason."),
}


@app.errorhandler(HTTPException)
def http_error(e):
    title, text = _ERROR_TEXT.get(e.code, (e.name, e.description))
    return render_template("error.html", code=e.code, title=title, text=text), e.code


@app.errorhandler(mysql.connector.Error)
def database_down(e):
    app.logger.error("Database error %s: %s", getattr(e, "errno", "?"), getattr(e, "msg", e))
    return render_template("error.html", code=500, title="The database did not play along",
                           text="The page needs the database and the request failed. Reload the page; if it keeps "
                                "happening, check that the database is running and that .env is right. "
                                "The terminal that runs Flask shows the exact error."), 500


# ---------------------------------------------------------------- home
def event_card(r):
    """One event of the home page list, ready for the template."""
    state = sale_state(r["now"], r["sale_time"], r["start_time"])
    zones = venue_zone_keys(r["venue"], r["standing_capacity"])
    seats_left = r["seats_left"] or 0
    standing_left = r["standing_left"] if r["standing_capacity"] else 0
    sold_out = state == "open" and seats_left == 0 and standing_left == 0
    left = seats_left + (standing_left or 0)
    return {
        "id": r["event_id"],
        "name": r["event_name"],
        "artist": r["artist"] or "",
        "venue": r["venue"],
        "start": r["start_time"],
        "sale": r["sale_time"],
        "state": "soldout" if sold_out else state,
        "low": state == "open" and not sold_out and standing_left is not None and left <= LOW_STOCK,
        "left": left,
        "days": (r["start_time"].date() - r["now"].date()).days,
        "price_from": min(PRICES[z] for z in zones) if zones else None,
        "img": poster_url(r["event_id"]),
        "tint": sum(map(ord, r["event_id"])) % 5,
        "href": url_for("event_page", event_id=r["event_id"]),
    }


@app.route("/")
def home():
    u = session.get("user")
    if u and u["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    q = request.args.get("q", "").strip()
    show = request.args.get("show", "all")
    if show not in ("open", "soon"):
        show = "all"
    like = "%" + q + "%"
    standing = "fn_standing_left(e.event_id)" if has_feature("standing_left") else "NULL"
    rows = db.fetch_all(
        "customer",
        "SELECT e.event_id, e.event_name, e.artist, e.sale_time, e.start_time, e.standing_capacity, "
        "v.address AS venue, NOW() AS now, fn_available_seats(e.event_id, NULL) AS seats_left, "
        + standing + " AS standing_left "
        "FROM event e JOIN venue v ON v.venue_id = e.venue_id "
        "WHERE e.start_time > NOW() AND (e.event_name LIKE %s OR e.artist LIKE %s OR v.address LIKE %s) "
        "ORDER BY e.start_time",
        (like, like, like),
    )
    cards = [event_card(r) for r in rows]
    counts = {"all": len(cards),
              "open": sum(1 for c in cards if c["state"] in ("open", "soldout")),
              "soon": sum(1 for c in cards if c["state"] == "soon")}
    # The big ticket on top: the next show you can actually buy, else the next show
    featured = None
    if not q and show == "all" and cards:
        featured = next((c for c in cards if c["state"] == "open"), cards[0])
    if show == "open":
        cards = [c for c in cards if c["state"] in ("open", "soldout")]
    elif show == "soon":
        cards = [c for c in cards if c["state"] == "soon"]
    return render_template("home.html", events=cards, featured=featured, q=q, show=show, counts=counts)


# ---------------------------------------------------------------- sign in / up / out
@app.route("/signin", methods=["GET", "POST"])
def signin():
    next_url = safe_next(request.values.get("next"))
    if session.get("user"):
        return redirect(next_url or url_for("home"))
    error = None
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        # One sign-in page for both: look for an admin first, then for a customer.
        admins = db.fetch_all(
            "admin",
            "SELECT admin_id, username, password, `level` FROM admin WHERE username = %s",
            (username,),
        )
        if admins and check_password_hash(admins[0]["password"], password):
            a = admins[0]
            session.clear()
            session["user"] = {"role": "admin", "id": a["admin_id"], "username": a["username"], "level": a["level"]}
            return redirect(url_for("admin_dashboard"))
        customers = db.fetch_all(
            "customer",
            "SELECT customer_id, username, password FROM customer WHERE username = %s",
            (username,),
        )
        if customers and check_password_hash(customers[0]["password"], password):
            c = customers[0]
            session.clear()
            session["user"] = {"role": "customer", "id": c["customer_id"], "username": c["username"]}
            return redirect(next_url or url_for("home"))
        error = "Wrong username or password."  # same message for every failure on purpose
    return render_template("signin.html", error=error, username=username, next_url=next_url)


def profile_errors(name, email, phone):
    """Checks shared by sign up and the account page (the lengths are the column sizes)."""
    errors = []
    if not name or len(name) > 100:
        errors.append("Full name is required (100 characters at most).")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 100:
        errors.append("Enter a valid email address.")
    if phone and not re.fullmatch(r"\+?[0-9 ().-]{6,20}", phone):
        errors.append("The phone number can only have digits, spaces and + ( ) . - (20 characters at most).")
    return errors


@app.route("/signup", methods=["GET", "POST"])
def signup():
    next_url = safe_next(request.values.get("next"))
    if session.get("user"):
        return redirect(url_for("home"))
    form = {k: request.form.get(k, "").strip() for k in ("username", "name", "email", "phone_num")}
    errors = []
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,50}", form["username"]):
            errors.append("Username: 3 to 50 letters, digits, dots, dashes or underscores.")
        if len(password) < 8 or len(password) > 128:
            errors.append("Password must be 8 to 128 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        errors += profile_errors(form["name"], form["email"], form["phone_num"])
        if not errors:
            try:
                db.execute(
                    "customer",
                    "INSERT INTO customer (customer_id, username, password, name, email, phone_num) "
                    "VALUES (NULL, %s, %s, %s, %s, %s)",
                    (form["username"], generate_password_hash(password), form["name"],
                     form["email"], form["phone_num"] or None),
                )
            except mysql.connector.Error as e:
                if e.errno == db.ER_DUP_ENTRY and "email" in e.msg:
                    errors.append("That email is already registered.")
                elif e.errno == db.ER_DUP_ENTRY or (e.errno == db.ER_SIGNAL and "already an admin" in e.msg):
                    errors.append("That username is taken.")  # same text for admin names: do not reveal them
                else:
                    errors.append(friendly(e))
            else:
                row = db.fetch_all("customer", "SELECT customer_id FROM customer WHERE username = %s",
                                   (form["username"],))[0]
                session.clear()
                session["user"] = {"role": "customer", "id": row["customer_id"], "username": form["username"]}
                flash("Welcome to myTickets, %s." % form["name"], "ok")
                return redirect(next_url or url_for("home"))
    return render_template("signup.html", form=form, errors=errors, next_url=next_url)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))


# ---------------------------------------------------------------- membership
def get_membership():
    """Rank, discount and progress of the signed-in customer (read from vw_customer_membership)."""
    rows = db.fetch_all("customer", "SELECT * FROM vw_customer_membership WHERE customer_id = %s",
                        (session["user"]["id"],))
    if not rows:
        return {"tier_name": "Bronze", "discount_percent": 0, "spent": 0, "next_tier": None,
                "next_min_spent": None, "missing": 0, "progress": 100}
    m = dict(rows[0])
    m["spent"] = m["spent"] or 0
    if m["next_tier"]:
        m["missing"] = max(m["next_min_spent"] - m["spent"], 0)
        # progress inside the current rank band: from this rank's own minimum to the next minimum
        base = db.fetch_all("customer", "SELECT min_spent FROM membership_tier WHERE tier_name = %s",
                            (m["tier_name"],))
        low = base[0]["min_spent"] if base else 0
        span = (m["next_min_spent"] - low) or 1
        m["progress"] = max(0, min(100, int((m["spent"] - low) * 100 / span)))
    else:
        m["missing"], m["progress"] = 0, 100
    return m


def net_price(price, discount_percent):
    """Same rounding as pc_book_tickets: ROUND(price * (100 - d) / 100, 0), half up."""
    return (int(price) * (100 - int(discount_percent)) + 50) // 100


# ---------------------------------------------------------------- event + booking
@app.route("/event/<event_id>")
def event_page(event_id):
    """Open to everyone. Guests see prices and what is left; booking needs a customer account."""
    u = session.get("user")
    if u and u["role"] == "admin":
        return redirect(url_for("admin_event", event_id=event_id))
    ev = db.fetch_one(
        "customer",
        "SELECT e.event_id, e.event_name, e.artist, e.sale_time, e.start_time, e.standing_capacity, "
        "v.address AS venue, NOW() AS now "
        "FROM event e JOIN venue v ON v.venue_id = e.venue_id WHERE e.event_id = %s",
        (event_id,),
    )
    if not ev:
        abort(404)
    sale = sale_state(ev["now"], ev["sale_time"], ev["start_time"])

    held, member = {}, None
    if u:
        held = {r["seat_zone"]: r["n"] for r in db.fetch_all(
            "customer",
            "SELECT seat_zone, COUNT(*) AS n FROM vw_order_history "
            "WHERE customer_id = %s AND event_id = %s AND order_status IN ('pending', 'paid') "
            "GROUP BY seat_zone",
            (u["id"], event_id),
        )}
        member = get_membership()
    held_total = sum(held.values())
    room = max(MAX_PER_EVENT - held_total, 0)  # tickets this customer may still add for this event
    discount = member["discount_percent"] if member else 0

    # Free numbered seats of every zone in one query; the zone names are our own constants
    wanted = VENUE_ZONES.get(ev["venue"])
    seat_zones = [k for k in PRICES if k != "STANDING" and (wanted is None or k in wanted)]
    left = {}
    if seat_zones:
        cols = ", ".join("fn_available_seats(%s, %s) AS `{}`".format(k) for k in seat_zones)
        params = [p for k in seat_zones for p in (event_id, k)]
        left = db.fetch_one("customer", "SELECT " + cols, params)
    has_standing = ev["standing_capacity"] > 0 and (wanted is None or "STANDING" in wanted)
    standing_left = None  # None = unknown (the database update has not been run)
    if has_standing and has_feature("standing_left"):
        standing_left = db.fetch_one("customer", "SELECT fn_standing_left(%s) AS n", (event_id,))["n"]

    zones = []
    for key, price in PRICES.items():
        if wanted is not None and key not in wanted:
            continue
        if key == "STANDING":
            if not has_standing:
                if wanted is None:
                    continue  # unknown venue: only show zones that exist
                n, note = 0, "Not open for this event"
            elif standing_left is None:
                n, note = ev["standing_capacity"], "Capacity %d" % ev["standing_capacity"]
            else:
                n = standing_left
                note = "Sold out" if n == 0 else ("Only %d left" % n if n <= LOW_STOCK else "%d left" % n)
        else:
            n = left.get(key) or 0
            if wanted is None and n == 0:
                continue  # unknown venue: only show zones that have seats
            note = "Sold out" if n == 0 else ("Only %d left" % n if n <= LOW_STOCK else "%d left" % n)
        zones.append({"key": key, "label": ZONE_LABEL[key], "price": price, "net": net_price(price, discount),
                      "note": note, "low": 0 < n <= LOW_STOCK and note.startswith("Only"), "sold_out": n == 0,
                      "held": held.get(key, 0),
                      "max_qty": min(room, n) if sale == "open" else 0})

    slug = re.sub(r"[^a-z0-9]+", "-", ev["venue"].lower()).strip("-")
    map_file = os.path.join(app.root_path, app.template_folder or "templates", "maps", slug + ".html")
    map_tpl = "maps/%s.html" % slug if os.path.isfile(map_file) else None
    if map_tpl is None:
        app.logger.warning("No map file for venue %r (looked for %s)", ev["venue"], map_file)
    return render_template(
        "event.html", ev=ev, zones=zones, sale=sale, max_per_event=MAX_PER_EVENT, held_total=held_total,
        room=room, member=member, poster=poster_url(ev["event_id"]), map_tpl=map_tpl,
        tint=sum(map(ord, ev["event_id"])) % 5,
        sold_out=sale == "open" and bool(zones) and all(z["note"] in ("Sold out", "Not open for this event") for z in zones),
        opens_in=max(int((ev["sale_time"] - ev["now"]).total_seconds()), 0),
        signin_url=url_for("signin", next=url_for("event_page", event_id=event_id)))


@app.route("/event/<event_id>/book", methods=["POST"])
@customer_required
def book(event_id):
    zone = request.form.get("zone", "")
    try:
        qty = int(request.form.get("qty", "0"))
    except ValueError:
        qty = 0
    if zone not in PRICES or qty not in (1, 2):
        flash("Choose a zone and 1 or 2 tickets.", "error")
        return redirect(url_for("event_page", event_id=event_id))
    try:
        out, _ = db.call("customer", "pc_book_tickets",
                         (session["user"]["id"], event_id, zone, qty, PRICES[zone], 0))
    except mysql.connector.Error as e:
        flash(friendly(e), "error")
        return redirect(url_for("event_page", event_id=event_id))
    flash("Order %s placed. Your seats are held for %d minutes. Pay to keep them." % (out[5], ORDER_HOLD_MINUTES),
          "ok")
    return redirect(url_for("orders", _anchor=out[5]))


# ---------------------------------------------------------------- orders
def own_order_status(order_id):
    rows = db.fetch_all(
        "customer",
        "SELECT order_status FROM vw_order_history WHERE order_id = %s AND customer_id = %s LIMIT 1",
        (order_id, session["user"]["id"]),
    )
    if not rows:
        abort(404)
    return rows[0]["order_status"]


def seat_text(r):
    if r["is_standing"]:
        return "no assigned seat"
    return "row %s, seat %s" % (r["seat_row"], r["seat_number"])


@app.route("/orders")
@customer_required
def orders():
    rows = db.fetch_all(
        "customer",
        "SELECT h.*, NOW() AS db_now FROM vw_order_history h WHERE h.customer_id = %s "
        "ORDER BY h.place_at DESC, h.order_id DESC, h.seat_id",
        (session["user"]["id"],),
    )
    grouped = {}
    for r in rows:
        o = grouped.get(r["order_id"])
        if o is None:
            expires = r["place_at"] + timedelta(minutes=ORDER_HOLD_MINUTES)
            o = grouped[r["order_id"]] = {
                "id": r["order_id"], "placed": r["place_at"], "status": r["order_status"],
                "event": r["event_name"], "event_id": r["event_id"], "artist": r["artist"],
                "venue": r["venue_address"], "start": r["start_time"], "zone": r["seat_zone"],
                "tickets": [], "total": 0, "pay_method": None, "pay_date": None, "expires": expires,
                # counted on the database clock, so the browser's clock and time zone do not matter
                "seconds_left": max(int((expires - r["db_now"]).total_seconds()), 0),
            }
        if r["seat_id"]:
            o["tickets"].append({"seat": seat_text(r), "price": r["ticket_price"]})
            o["total"] += r["ticket_price"]
            o["pay_method"] = r["pay_method"]
            o["pay_date"] = r["pay_date"]
    all_orders = list(grouped.values())
    status = request.args.get("status", "all")
    if status not in ("pending", "paid", "failed"):
        status = "all"
    counts = {"all": len(all_orders)}
    for s in ("pending", "paid", "failed"):
        counts[s] = sum(1 for o in all_orders if o["status"] == s)
    shown = [o for o in all_orders if status == "all" or o["status"] == status]
    return render_template("orders.html", orders=shown, counts=counts, status=status,
                           methods=PAY_METHODS, hold_minutes=ORDER_HOLD_MINUTES)


@app.route("/orders/<order_id>/pay", methods=["POST"])
@customer_required
def pay_order(order_id):
    method = request.form.get("method", "")
    if method not in PAY_METHODS:
        flash("Choose a payment method.", "error")
        return redirect(url_for("orders", _anchor=order_id))
    if own_order_status(order_id) != "pending":
        flash("Only a pending order can be paid.", "error")
        return redirect(url_for("orders"))
    try:
        db.call("customer", "pc_pay_order", (order_id, 1, method))
    except mysql.connector.Error as e:
        flash(friendly(e), "error")
        return redirect(url_for("orders"))
    flash("Order %s is paid. Your tickets are below." % order_id, "ok")
    return redirect(url_for("tickets", _anchor=order_id))


@app.route("/orders/<order_id>/cancel", methods=["POST"])
@customer_required
def cancel_order(order_id):
    if own_order_status(order_id) != "pending":
        flash("Only a pending order can be cancelled.", "error")
        return redirect(url_for("orders"))
    try:
        db.call("customer", "pc_cancel_order", (order_id,))
    except mysql.connector.Error as e:
        flash(friendly(e), "error")
    else:
        flash("Order %s was cancelled. Its seats are free again." % order_id, "ok")
    return redirect(url_for("orders"))


# ---------------------------------------------------------------- tickets
def ticket_code(event_id, seat_id, order_id):
    """Text behind the QR code: the ticket's key plus a signature made with SECRET_KEY.
    Nobody can make up a code that passes check_ticket_code() without knowing that key."""
    body = "%s.%s.%s" % (event_id, seat_id, order_id)
    sig = hmac.new(app.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()[:12].upper()
    return body + "." + sig


def check_ticket_code(code):
    """Returns (event_id, seat_id, order_id) when the signature is right, else None."""
    parts = code.strip().split(".")
    if len(parts) != 4:
        return None
    if not hmac.compare_digest(ticket_code(*parts[:3]), ".".join(parts[:3] + [parts[3].upper()])):
        return None
    return tuple(parts[:3])


def qr_svg(text):
    if segno is None:
        return None
    return Markup(segno.make(text, error="m").svg_inline(scale=4, border=0, dark="#17134A", omitsize=True))


@app.route("/tickets")
@customer_required
def tickets():
    """Tickets of paid orders. A ticket only exists here once its order is paid."""
    rows = db.fetch_all(
        "customer",
        "SELECT h.*, NOW() AS db_now FROM vw_order_history h "
        "WHERE h.customer_id = %s AND h.order_status = 'paid' AND h.seat_id IS NOT NULL "
        "ORDER BY h.start_time, h.order_id, h.seat_id",
        (session["user"]["id"],),
    )
    upcoming, past = [], []
    for r in rows:
        code = ticket_code(r["event_id"], r["seat_id"], r["order_id"])
        t = {
            "event": r["event_name"], "event_id": r["event_id"], "artist": r["artist"],
            "venue": r["venue_address"], "start": r["start_time"], "zone": r["seat_zone"],
            "zone_label": ZONE_LABEL.get(r["seat_zone"], r["seat_zone"]), "standing": r["is_standing"],
            "row": r["seat_row"], "number": r["seat_number"], "price": r["ticket_price"],
            "order": r["order_id"], "holder": r["customer_name"], "code": code, "qr": qr_svg(code),
        }
        # a show stays under "upcoming" until the morning after
        (past if r["start_time"] + timedelta(hours=12) < r["db_now"] else upcoming).append(t)
    past.reverse()
    return render_template("tickets.html", upcoming=upcoming, past=past)


# ---------------------------------------------------------------- account
@app.route("/account")
@customer_required
def account():
    uid = session["user"]["id"]
    profile = db.fetch_one("customer", "SELECT customer_id, username, name, email, phone_num FROM customer "
                                       "WHERE customer_id = %s", (uid,))
    if not profile:  # the account was removed while signed in
        session.clear()
        return redirect(url_for("signin"))
    tiers = db.fetch_all("customer", "SELECT tier_name, min_spent, discount_percent FROM membership_tier "
                                     "ORDER BY min_spent")
    totals = db.fetch_one(
        "customer",
        "SELECT COUNT(DISTINCT order_id) AS orders, COUNT(seat_id) AS tickets, COUNT(DISTINCT event_id) AS events "
        "FROM vw_order_history WHERE customer_id = %s AND order_status = 'paid'", (uid,))
    return render_template("account.html", profile=profile, member=get_membership(), tiers=tiers, totals=totals,
                           can_edit=has_feature("edit_profile"))


@app.route("/account/profile", methods=["POST"])
@customer_required
def account_profile():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone_num", "").strip()
    errors = profile_errors(name, email, phone)
    if errors:
        for msg in errors:
            flash(msg, "error")
        return redirect(url_for("account"))
    try:
        db.call("customer", "pc_update_customer", (session["user"]["id"], name, email, phone or None, None))
    except mysql.connector.Error as e:
        flash("That email is already registered." if e.errno == db.ER_DUP_ENTRY else friendly(e), "error")
    else:
        flash("Profile saved.", "ok")
    return redirect(url_for("account"))


@app.route("/account/password", methods=["POST"])
@customer_required
def account_password():
    uid = session["user"]["id"]
    current = request.form.get("current", "")
    new = request.form.get("password", "")
    row = db.fetch_one("customer", "SELECT name, email, phone_num, password FROM customer WHERE customer_id = %s",
                       (uid,))
    if not row or not check_password_hash(row["password"], current):
        flash("The current password is wrong.", "error")
    elif len(new) < 8 or len(new) > 128:
        flash("The new password must be 8 to 128 characters.", "error")
    elif new != request.form.get("confirm", ""):
        flash("The two new passwords do not match.", "error")
    else:
        try:
            db.call("customer", "pc_update_customer",
                    (uid, row["name"], row["email"], row["phone_num"], generate_password_hash(new)))
        except mysql.connector.Error as e:
            flash(friendly(e), "error")
        else:
            flash("Password changed.", "ok")
    return redirect(url_for("account"))


# ---------------------------------------------------------------- admin
def admin_events():
    return db.fetch_all(
        "admin",
        "SELECT e.event_id, e.event_name, e.artist, e.sale_time, e.start_time, e.standing_capacity, "
        "e.venue_id, v.address AS venue, NOW() AS now "
        "FROM " + db.MAIN_DB + ".event e JOIN " + db.MAIN_DB + ".venue v ON v.venue_id = e.venue_id "
        "ORDER BY e.start_time")


def event_stats(event_id, standing_capacity):
    """pc_event_stats plus the numbers the bars need."""
    rows = db.call_rows("admin", "pc_event_stats", (session["user"]["id"], event_id))
    s = dict(rows[0])
    s["revenue"] = s["revenue"] or 0
    sold = (s["tickets_paid"] or 0) + (s["tickets_pending"] or 0)
    standing_sold = standing_capacity - (s["standing_left"] or 0)
    s["capacity"] = (s["seats_left"] or 0) + (sold - standing_sold) + standing_capacity
    cap = s["capacity"] or 1
    s["paid_pct"] = round((s["tickets_paid"] or 0) * 100 / cap, 1)
    s["pending_pct"] = round((s["tickets_pending"] or 0) * 100 / cap, 1)
    s["free"] = (s["seats_left"] or 0) + (s["standing_left"] or 0)
    return s


@app.route("/admin")
@admin_required
def admin_dashboard():
    if request.args.get("event"):  # old address of the event view
        return redirect(url_for("admin_event", event_id=request.args["event"]))
    upcoming, past = [], []
    totals = {"revenue": 0, "paid": 0, "pending": 0, "open": 0, "upcoming": 0}
    for e in admin_events():
        e = dict(e)
        e["state"] = sale_state(e["now"], e["sale_time"], e["start_time"])
        e["stats"] = event_stats(e["event_id"], e["standing_capacity"])
        e["img"] = poster_url(e["event_id"])
        totals["revenue"] += e["stats"]["revenue"]
        totals["paid"] += e["stats"]["tickets_paid"] or 0
        totals["pending"] += e["stats"]["tickets_pending"] or 0
        if e["state"] == "ended":
            past.append(e)
        else:
            upcoming.append(e)
            totals["upcoming"] += 1
            totals["open"] += e["state"] == "open"
    past.reverse()
    venues = db.fetch_all("admin", "SELECT venue_id, address, capacity FROM " + db.MAIN_DB + ".venue "
                                   "ORDER BY venue_id")
    activity = db.fetch_all(
        "admin",
        "SELECT l.done_at, l.admin_id, a.username, l.action, l.target_id "
        "FROM audit_log l JOIN admin a ON a.admin_id = l.admin_id ORDER BY l.log_id DESC LIMIT 12",
    )
    return render_template("admin.html", upcoming=upcoming, past=past, totals=totals, venues=venues,
                           activity=activity, can_add=is_super(),
                           venue_zones={v: [ZONE_LABEL[z] for z in zs] for v, zs in VENUE_ZONES.items()})


@app.route("/admin/events/<event_id>")
@admin_required
def admin_event(event_id):
    ev = next((dict(e) for e in admin_events() if e["event_id"] == event_id), None)
    if not ev:
        abort(404)
    ev["state"] = sale_state(ev["now"], ev["sale_time"], ev["start_time"])
    stats = event_stats(event_id, ev["standing_capacity"])
    seats = db.call_rows("admin", "pc_available_seats", (event_id, None), db=db.MAIN_DB)
    free_by_zone = {}
    for s in seats:
        free_by_zone[s["seat_zone"]] = free_by_zone.get(s["seat_zone"], 0) + 1
    zone = request.args.get("zone", "")
    if zone not in free_by_zone:
        zone = ""
    listed = [s for s in seats if not zone or s["seat_zone"] == zone]
    # Delete button state (the database trigger enforces the same rules)
    delete_block = None
    if (stats["tickets_paid"] or 0) + (stats["tickets_pending"] or 0) > 0:
        delete_block = "This event has tickets, so it cannot be deleted."
    elif ev["state"] == "ended":
        delete_block = "This event has already started, so it cannot be deleted."
    return render_template(
        "admin_event.html", ev=ev, stats=stats, poster=poster_url(event_id), delete_block=delete_block,
        free_by_zone=[(k, ZONE_LABEL.get(k, k), free_by_zone[k]) for k in PRICES if k in free_by_zone],
        zone=zone, seats=listed[:60], seats_total=len(listed), can_add=is_super(),
        can_edit=is_super() and ev["state"] != "ended" and has_feature("edit_event"),
        edit_missing=is_super() and not has_feature("edit_event"))


@app.route("/admin/events", methods=["POST"])
@admin_required
def admin_add_event():
    me = session["user"]
    sale = parse_local(request.form.get("sale_time", ""))
    start = parse_local(request.form.get("start_time", ""))
    name = request.form.get("event_name", "").strip()
    artist = request.form.get("artist", "").strip()
    venue = request.form.get("venue_id", "")
    try:
        standing = int(request.form.get("standing_capacity", "0") or 0)
    except ValueError:
        standing = -1
    if not name or not sale or not start:
        flash("Event name, sale time and start time are required.", "error")
        return redirect(url_for("admin_dashboard", _anchor="add"))
    try:
        out, _ = db.call("admin", "pc_add_event",
                         (me["id"], venue, name, artist or None, sale, start, standing, 0))
    except mysql.connector.Error as e:
        flash(friendly(e), "error")
        return redirect(url_for("admin_dashboard", _anchor="add"))
    msg = save_poster(out[7], request.files.get("poster"))
    if msg:
        flash("Event %s created, but the poster was not saved. %s" % (out[7], msg), "error")
    else:
        flash("Event %s created." % out[7], "ok")
    return redirect(url_for("admin_event", event_id=out[7]))


@app.route("/admin/events/<event_id>/edit", methods=["POST"])
@admin_required
def admin_edit_event(event_id):
    me = session["user"]
    sale = parse_local(request.form.get("sale_time", ""))
    start = parse_local(request.form.get("start_time", ""))
    name = request.form.get("event_name", "").strip()
    artist = request.form.get("artist", "").strip()
    try:
        standing = int(request.form.get("standing_capacity", "0") or 0)
    except ValueError:
        standing = -1
    if not name or not sale or not start:
        flash("Event name, sale time and start time are required.", "error")
    else:
        try:
            db.call("admin", "pc_update_event", (me["id"], event_id, name, artist or None, sale, start, standing))
        except mysql.connector.Error as e:
            flash(friendly(e), "error")
        else:
            flash("Event %s saved." % event_id, "ok")
    return redirect(url_for("admin_event", event_id=event_id))


@app.route("/admin/events/<event_id>/delete", methods=["POST"])
@admin_required
def admin_delete_event(event_id):
    me = session["user"]
    if me["level"] != "super_admin":
        flash("Only a super admin can delete events.", "error")
        return redirect(url_for("admin_event", event_id=event_id))
    try:
        db.call("admin", "pc_delete_event", (me["id"], event_id))
    except mysql.connector.Error as e:
        flash(friendly(e), "error")
        return redirect(url_for("admin_event", event_id=event_id))
    # The event is gone: remove its poster file too
    if re.fullmatch(r"EV\d+", event_id):
        try:
            os.remove(os.path.join(app.static_folder, "events", event_id + ".jpg"))
        except OSError:
            pass
    flash("Event %s deleted." % event_id, "ok")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/events/<event_id>/poster", methods=["POST"])
@admin_required
def admin_set_poster(event_id):
    if session["user"]["level"] != "super_admin":
        flash("Only a super admin can change posters.", "error")
        return redirect(url_for("admin_event", event_id=event_id))
    known = [e["event_id"] for e in db.fetch_all("admin", "SELECT event_id FROM " + db.MAIN_DB + ".event")]
    if event_id not in known:
        abort(404)
    upload = request.files.get("poster")
    if upload is None or not upload.filename:
        flash("Choose an image first.", "error")
    else:
        msg = save_poster(event_id, upload)
        flash(msg or "Poster saved for %s." % event_id, "error" if msg else "ok")
    return redirect(url_for("admin_event", event_id=event_id))


@app.route("/admin/check")
@admin_required
def admin_check():
    """Door check: is this ticket code one of ours? Reads nothing secret, changes nothing."""
    code = request.args.get("code", "").strip()
    result = None
    if code:
        key = check_ticket_code(code)
        if key is None:
            result = {"ok": False}
        else:
            event_id, seat_id, order_id = key
            ev = db.fetch_one(
                "admin",
                "SELECT e.event_name, e.artist, e.start_time, v.address AS venue "
                "FROM " + db.MAIN_DB + ".event e JOIN " + db.MAIN_DB + ".venue v ON v.venue_id = e.venue_id "
                "WHERE e.event_id = %s", (event_id,))
            result = {"ok": True, "event_id": event_id, "seat_id": seat_id, "order_id": order_id, "ev": ev,
                      "standing": seat_id.startswith("STND-")}
    return render_template("admin_check.html", code=code, result=result)


if __name__ == "__main__":
    app.run(debug=True)
