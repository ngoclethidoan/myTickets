"""Database access for the MyTickets web app.

The app never connects as the owner. It uses one of two limited MySQL accounts:
  customer_app -> main database
  admin_app    -> admin database
MySQL itself decides what each account may do (see security/01_accounts_and_grants.sql),
so a bug in this app cannot read or change more than the account is allowed to.
"""
import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

MAIN_DB = os.environ.get("MAIN_DB", "myv_myTickets")
ADMIN_DB = os.environ.get("ADMIN_DB", "myv_myTickets_admin")

# role -> (MySQL user, env variable holding its password, default database)
_ACCOUNTS = {
    "customer": ("customer_app", "CUSTOMER_APP_PASSWORD", MAIN_DB),
    "admin": ("admin_app", "ADMIN_APP_PASSWORD", ADMIN_DB),
    "owner": (None, "OWNER_PASSWORD", ADMIN_DB),  # only create_admin.py uses this one
}


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
    }
    ssl_ca = os.environ.get("DB_SSL_CA", "").strip()
    if ssl_ca:
        config["ssl_ca"] = ssl_ca
        config["ssl_verify_cert"] = True
    return mysql.connector.connect(**config)


def fetch_all(role, sql, params=(), db=None):
    """Run a SELECT and return a list of dicts."""
    conn = _connect(role, db)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def execute(role, sql, params=(), db=None):
    """Run an INSERT/UPDATE/DELETE."""
    conn = _connect(role, db)
    try:
        conn.cursor().execute(sql, params)
    finally:
        conn.close()


def call(role, proc, args=(), db=None):
    """Call a stored procedure.

    Returns (args_after_call, result_sets). OUT parameters are in args_after_call;
    every result set is a list of dicts.
    """
    conn = _connect(role, db)
    try:
        cur = conn.cursor()
        result_args = cur.callproc(proc, list(args))
        sets = []
        for result in cur.stored_results():
            columns = result.column_names
            sets.append([dict(zip(columns, row)) for row in result.fetchall()])
        return result_args, sets
    finally:
        conn.close()
