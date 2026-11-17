"""Database access for the MyTickets web app.

The app never connects as the owner. It uses one of two limited MySQL accounts:
  customer_app -> main database
  admin_app    -> admin database
MySQL itself decides what each account may do (see database/myv_myTickets_admin/grant/),
so a bug in this app cannot read or change more than the account is allowed to.

Inside a web request a connection is opened once per account and reused until the
request ends (one page used to open up to ten connections, which is slow over TLS).
Outside a request (create_admin.py) every call opens and closes its own connection.
"""
import os

import mysql.connector
from dotenv import load_dotenv
from flask import g, has_app_context

load_dotenv()

MAIN_DB = os.environ.get("MAIN_DB", "myv_myTickets")
ADMIN_DB = os.environ.get("ADMIN_DB", "myv_myTickets_admin")

# role -> (MySQL user, env variable holding its password, default database)
_ACCOUNTS = {
    "customer": ("customer_app", "CUSTOMER_APP_PASSWORD", MAIN_DB),
    "admin": ("admin_app", "ADMIN_APP_PASSWORD", ADMIN_DB),
    "owner": (None, "OWNER_PASSWORD", ADMIN_DB),  # only create_admin.py uses this one
}

# MySQL error numbers the app cares about
ER_DUP_ENTRY = 1062
ER_SIGNAL = 1644             # raised by SIGNAL in a trigger or procedure: the message is safe to show
ER_NO_SUCH_ROUTINE = 1305    # FUNCTION/PROCEDURE does not exist
ER_ROUTINE_DENIED = 1370     # no EXECUTE right on the routine


def _connect(role, database=None):
    user, password_var, default_db = _ACCOUNTS[role]
    if role == "owner":
        user = os.environ.get("OWNER_USER", "avnadmin")
    config = {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": user,
        "password": os.environ.get(password_var, ""),
        "database": database or default_db,
        "autocommit": True,
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        "connection_timeout": 10,
    }
    ssl_ca = os.environ.get("DB_SSL_CA", "").strip()
    if ssl_ca:
        config["ssl_ca"] = ssl_ca
        config["ssl_verify_cert"] = True
    return mysql.connector.connect(**config)


class _Session:
    """`with _Session(role, db) as conn:` gives a connection and cleans up afterwards.

    In a request the connection is kept in flask.g for the next query. If the query failed,
    the connection is thrown away instead, so a half-finished state can never leak into the next one.
    """

    def __init__(self, role, database=None):
        self.key = (role, database)
        self.shared = has_app_context()

    def __enter__(self):
        if self.shared:
            pool = g.setdefault("_db", {})
            conn = pool.get(self.key)
            if conn is None:
                conn = pool[self.key] = _connect(*self.key)
            self.conn = conn
        else:
            self.conn = _connect(*self.key)
        return self.conn

    def __exit__(self, exc_type, _exc, _tb):
        if not self.shared or exc_type is not None:
            if self.shared:
                g.get("_db", {}).pop(self.key, None)
            try:
                self.conn.close()
            except mysql.connector.Error:
                pass
        return False


def close_all(_exc=None):
    """Close the connections of this request. Registered with app.teardown_appcontext."""
    for conn in g.pop("_db", {}).values():
        try:
            conn.close()
        except mysql.connector.Error:
            pass


def fetch_all(role, sql, params=(), db=None):
    """Run a SELECT and return a list of dicts."""
    with _Session(role, db) as conn:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()


def fetch_one(role, sql, params=(), db=None):
    """Run a SELECT and return the first row as a dict, or None."""
    rows = fetch_all(role, sql, params, db)
    return rows[0] if rows else None


def execute(role, sql, params=(), db=None):
    """Run an INSERT/UPDATE/DELETE."""
    with _Session(role, db) as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
        finally:
            cur.close()


def call(role, proc, args=(), db=None):
    """Call a stored procedure.

    Returns (args_after_call, result_sets). OUT parameters are in args_after_call;
    every result set is a list of dicts.
    """
    with _Session(role, db) as conn:
        cur = conn.cursor()
        try:
            result_args = cur.callproc(proc, list(args))
            sets = []
            for result in cur.stored_results():
                columns = result.column_names
                sets.append([dict(zip(columns, row)) for row in result.fetchall()])
            return result_args, sets
        finally:
            cur.close()


def call_rows(role, proc, args=(), db=None):
    """Call a procedure that has only IN parameters and return its first result set (list of dicts).

    One network round trip instead of the three that callproc() needs, which adds up
    when a page calls the same procedure once per event.
    """
    with _Session(role, db) as conn:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute("CALL %s(%s)" % (proc, ", ".join(["%s"] * len(args))), tuple(args))
            rows = cur.fetchall() if cur.with_rows else []
            while cur.nextset():  # skip the status packet that ends every CALL
                pass
            return rows
        finally:
            cur.close()
