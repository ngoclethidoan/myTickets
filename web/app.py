"""MyTickets web app (Flask).

Three tiers: browser (HTML) -> this Flask app -> MySQL.
All ticket rules live in the database (triggers + procedures). This app only
signs people in, picks the right MySQL account, calls the procedures and shows results.
"""
import os
import re
import secrets
from datetime import datetime
from functools import wraps

import mysql.connector
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash

import db

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  MAX_CONTENT_LENGTH=6 * 1024 * 1024)  # uploads (posters) are limited to 6 MB

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
PAY_METHODS = ["Card", "Bank transfer", "E-wallet"]


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


def poster_url(event_id):
    """Poster image is static/events/<event_id>.jpg. Returns None when the file is missing."""
    path = os.path.join(app.static_folder, "events", event_id + ".jpg")
    return url_for("static", filename="events/" + event_id + ".jpg") if os.path.isfile(path) else None


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


@app.errorhandler(413)
def too_large(_e):
    flash("That file is too big (6 MB at most).", "error")
    return redirect(url_for("admin_dashboard" if (session.get("user") or {}).get("role") == "admin" else "home"))


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token
app.jinja_env.globals["ZONE_LABEL"] = ZONE_LABEL


@app.context_processor
def inject_user():
    return {"user": session.get("user")}


@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        if not sent or not secrets.compare_digest(sent, session.get("_csrf", "")):
            abort(400)


def safe_next(target):
    """Only allow redirects to a path on this site."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return None


def friendly(e):
    """Message from a database rule (SIGNAL) is safe to show; anything else is not."""
    if e.errno == 1644:
        return e.msg
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


# ---------------------------------------------------------------- home
@app.route("/")
def home():
    u = session.get("user")
    if u and u["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    q = request.args.get("q", "").strip()
    like = "%" + q + "%"
    rows = db.fetch_all(
        "customer",
        "SELECT e.event_id, e.event_name, e.artist, e.start_time, v.address AS venue "
        "FROM event e JOIN venue v ON v.venue_id = e.venue_id "
        "WHERE e.start_time > NOW() AND (e.event_name LIKE %s OR e.artist LIKE %s) "
        "ORDER BY e.start_time",
        (like, like),
    )
    events = []
    for r in rows:
        target = url_for("event_page", event_id=r["event_id"])
        events.append({
            "id": r["event_id"],
            "day": r["start_time"].strftime("%d"),
            "month": r["start_time"].strftime("%b"),
            "name": r["event_name"],
            "artist": r["artist"] or "",
            "venue": r["venue"],
            "img": poster_url(r["event_id"]),
            "href": target if u else url_for("signin", next=target),
        })
    return render_template("home.html", events=events, q=q)


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


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("user"):
        return redirect(url_for("home"))
    form = {k: request.form.get(k, "").strip() for k in ("username", "name", "email", "phone_num")}
    errors = []
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not form["username"] or len(form["username"]) > 50:
            errors.append("Username is required (50 characters at most).")
        if len(password) < 8 or len(password) > 128:
            errors.append("Password must be 8 to 128 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if not form["name"]:
            errors.append("Full name is required.")
        if "@" not in form["email"]:
            errors.append("Enter a valid email address.")
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
                if e.errno == 1062 and "email" in e.msg:
                    errors.append("That email is already registered.")
                elif e.errno == 1062 or (e.errno == 1644 and "already an admin" in e.msg):
                    errors.append("That username is taken.")  # same text for admin names: do not reveal them
                else:
                    errors.append(friendly(e))
            else:
                row = db.fetch_all("customer", "SELECT customer_id FROM customer WHERE username = %s",
                                   (form["username"],))[0]
                session.clear()
                session["user"] = {"role": "customer", "id": row["customer_id"], "username": form["username"]}
                flash("Welcome to myTickets!", "ok")
                return redirect(url_for("home"))
    return render_template("signup.html", form=form, errors=errors)


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
@customer_required
def event_page(event_id):
    rows = db.fetch_all(
        "customer",
        "SELECT e.event_id, e.event_name, e.artist, e.sale_time, e.start_time, e.standing_capacity, "
        "v.address AS venue, NOW() AS now "
        "FROM event e JOIN venue v ON v.venue_id = e.venue_id WHERE e.event_id = %s",
        (event_id,),
    )
    if not rows:
        abort(404)
    ev = rows[0]
    if ev["now"] < ev["sale_time"]:
        sale = "soon"
    elif ev["now"] >= ev["start_time"]:
        sale = "ended"
    else:
        sale = "open"

    held = {r["seat_zone"]: r["n"] for r in db.fetch_all(
        "customer",
        "SELECT seat_zone, COUNT(*) AS n FROM vw_order_history "
        "WHERE customer_id = %s AND event_id = %s AND order_status IN ('pending', 'paid') "
        "GROUP BY seat_zone",
        (session["user"]["id"], event_id),
    )}

    wanted = VENUE_ZONES.get(ev["venue"])
    held_total = sum(held.values())
    room = max(MAX_PER_EVENT - held_total, 0)  # tickets this customer may still add for this event
    member = get_membership()
    zones = []
    for key, price in PRICES.items():
        if wanted is not None and key not in wanted:
            continue
        h = held.get(key, 0)
        if key == "STANDING":
            exists = ev["standing_capacity"] > 0
            note = "Capacity %d" % ev["standing_capacity"] if exists else "Not open for this event"
            max_qty = room if exists else 0
        else:
            n = db.fetch_all("customer", "SELECT fn_available_seats(%s, %s) AS n", (event_id, key))[0]["n"] or 0
            exists = n > 0
            note = "%d left" % n if n else "Sold out"
            max_qty = min(room, n)
            if wanted is None and not exists:
                continue  # unknown venue: only show zones that have seats
        if wanted is None and key == "STANDING" and not exists:
            continue
        if sale != "open":
            max_qty = 0
        zones.append({"key": key, "label": ZONE_LABEL[key], "price": price,
                      "net": net_price(price, member["discount_percent"]), "note": note, "held": h,
                      "max_qty": max_qty})
    slug = re.sub(r"[^a-z0-9]+", "-", ev["venue"].lower()).strip("-")
    map_file = os.path.join(app.root_path, app.template_folder or "templates", "maps", slug + ".html")
    map_tpl = "maps/%s.html" % slug if os.path.isfile(map_file) else None
    if map_tpl is None:
        app.logger.warning("No map file for venue %r (looked for %s)", ev["venue"], map_file)
    return render_template("event.html", ev=ev, zones=zones, sale=sale, max_per_event=MAX_PER_EVENT, held_total=held_total, room=room,
                           member=member, poster=poster_url(ev["event_id"]), map_tpl=map_tpl)


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
    flash("Order %s placed. Pay for it to confirm your seats." % out[5], "ok")
    return redirect(url_for("orders"))


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


@app.route("/orders")
@customer_required
def orders():
    rows = db.fetch_all(
        "customer",
        "SELECT * FROM vw_order_history WHERE customer_id = %s "
        "ORDER BY place_at DESC, order_id DESC, seat_id",
        (session["user"]["id"],),
    )
    grouped = {}
    for r in rows:
        o = grouped.setdefault(r["order_id"], {
            "id": r["order_id"], "placed": r["place_at"], "status": r["order_status"],
            "event": r["event_name"], "venue": r["venue_address"], "start": r["start_time"],
            "tickets": [], "total": 0, "pay_method": None, "pay_date": None,
        })
        if r["seat_id"]:
            if r["is_standing"]:
                seat = "Standing · no assigned seat"
            else:
                seat = "%s · Row %s, Seat %s" % (ZONE_LABEL.get(r["seat_zone"], r["seat_zone"]),
                                                  r["seat_row"], r["seat_number"])
            o["tickets"].append({"seat": seat, "price": r["ticket_price"]})
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
                           pay_open=request.args.get("pay"), methods=PAY_METHODS, member=get_membership())


@app.route("/orders/<order_id>/pay", methods=["POST"])
@customer_required
def pay_order(order_id):
    method = request.form.get("method", "")
    if method not in PAY_METHODS:
        flash("Choose a payment method.", "error")
        return redirect(url_for("orders", pay=order_id))
    if own_order_status(order_id) != "pending":
        flash("Only a pending order can be paid.", "error")
        return redirect(url_for("orders"))
    try:
        db.call("customer", "pc_pay_order", (order_id, 1, method))
    except mysql.connector.Error as e:
        flash(friendly(e), "error")
    else:
        flash("Order %s is paid and locked." % order_id, "ok")
    return redirect(url_for("orders"))


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


# ---------------------------------------------------------------- admin
def parse_local(value):
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


@app.route("/admin")
@admin_required
def admin_dashboard():
    me = session["user"]
    events = db.fetch_all(
        "admin", "SELECT event_id, event_name, start_time FROM " + db.MAIN_DB + ".event ORDER BY start_time DESC")
    venues = db.fetch_all("admin", "SELECT venue_id, address FROM " + db.MAIN_DB + ".venue ORDER BY venue_id")
    chosen = request.args.get("event") or (events[0]["event_id"] if events else None)
    if chosen not in [e["event_id"] for e in events]:
        chosen = events[0]["event_id"] if events else None
    zone = request.args.get("zone", "")
    if zone not in PRICES or zone == "STANDING":
        zone = ""
    stats, seats = None, []
    if chosen:
        try:
            _, sets = db.call("admin", "pc_event_stats", (me["id"], chosen))
            stats = sets[0][0] if sets and sets[0] else None
            _, sets = db.call("admin", "pc_available_seats", (chosen, zone or None), db=db.MAIN_DB)
            seats = sets[0] if sets else []
        except mysql.connector.Error as e:
            flash(friendly(e), "error")
    activity = db.fetch_all(
        "admin",
        "SELECT l.done_at, l.admin_id, a.username, l.action, l.target_id "
        "FROM audit_log l JOIN admin a ON a.admin_id = l.admin_id ORDER BY l.log_id DESC LIMIT 10",
    )
    zone_options = [(k, v) for k, v in ZONE_LABEL.items() if k != "STANDING"]
    # Delete button state (the database trigger enforces the same rules)
    delete_block = None
    if stats:
        start = next((e["start_time"] for e in events if e["event_id"] == chosen), None)
        if (stats["tickets_paid"] or 0) + (stats["tickets_pending"] or 0) > 0:
            delete_block = "This event has tickets, so it cannot be deleted."
        elif start is not None and start <= datetime.now():
            delete_block = "This event has already started, so it cannot be deleted."
    return render_template("admin.html", delete_block=delete_block, poster=poster_url(chosen) if chosen else None, events=events, venues=venues, chosen=chosen, zone=zone,
                           zone_options=zone_options,
                           stats=stats, seats=seats[:10], seats_total=len(seats), activity=activity,
                           can_add=(me["level"] == "super_admin"))


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
        return redirect(url_for("admin_dashboard"))
    try:
        out, _ = db.call("admin", "pc_add_event",
                         (me["id"], venue, name, artist or None, sale, start, standing, 0))
    except mysql.connector.Error as e:
        flash(friendly(e), "error")
        return redirect(url_for("admin_dashboard"))
    msg = save_poster(out[7], request.files.get("poster"))
    if msg:
        flash("Event %s created, but the poster was not saved. %s" % (out[7], msg), "error")
    else:
        flash("Event %s created." % out[7], "ok")
    return redirect(url_for("admin_dashboard", event=out[7]))


@app.route("/admin/events/<event_id>/delete", methods=["POST"])
@admin_required
def admin_delete_event(event_id):
    me = session["user"]
    if me["level"] != "super_admin":
        flash("Only a super admin can delete events.", "error")
        return redirect(url_for("admin_dashboard", event=event_id))
    try:
        db.call("admin", "pc_delete_event", (me["id"], event_id))
    except mysql.connector.Error as e:
        flash(friendly(e), "error")
        return redirect(url_for("admin_dashboard", event=event_id))
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
        return redirect(url_for("admin_dashboard", event=event_id))
    known = [e["event_id"] for e in db.fetch_all("admin", "SELECT event_id FROM " + db.MAIN_DB + ".event")]
    if event_id not in known:
        abort(404)
    upload = request.files.get("poster")
    if upload is None or not upload.filename:
        flash("Choose an image first.", "error")
    else:
        msg = save_poster(event_id, upload)
        flash(msg or "Poster saved for %s." % event_id, "error" if msg else "ok")
    return redirect(url_for("admin_dashboard", event=event_id))


if __name__ == "__main__":
    app.run(debug=True)
