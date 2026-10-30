"""Create an admin account. Run it yourself; the web app cannot create admins.

    python create_admin.py boss --level super_admin

The password is typed here (hidden), hashed, and only the hash is stored.
Uses the owner account from .env because admin_app is not allowed to insert admins.
"""
import argparse
import getpass

import mysql.connector
from werkzeug.security import generate_password_hash

import db


def main():
    parser = argparse.ArgumentParser(description="Create a MyTickets admin account")
    parser.add_argument("username")
    parser.add_argument("--level", choices=["staff", "super_admin"], default="staff")
    args = parser.parse_args()

    password = getpass.getpass("Password (at least 8 characters): ")
    if len(password) < 8:
        raise SystemExit("Password is too short.")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match.")

    try:
        db.execute(
            "owner",
            "INSERT INTO admin (admin_id, username, password, `level`) VALUES (NULL, %s, %s, %s)",
            (args.username, generate_password_hash(password), args.level),
        )
        row = db.fetch_all("owner", "SELECT admin_id FROM admin WHERE username = %s", (args.username,))[0]
    except mysql.connector.Error as e:
        raise SystemExit("Could not create the admin: " + e.msg)
    print("Created %s (%s) as %s" % (row["admin_id"], args.username, args.level))


if __name__ == "__main__":
    main()
