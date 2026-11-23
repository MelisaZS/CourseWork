"""User accounts: bcrypt password hashing, login check and roles.

Roles:
    admin     - everything (database, documents, web, PDF upload, admin panel)
    employee  - database, documents, web, PDF upload (personal data masked in answers)
    guest     - documents and web only; no database questions, no upload

Users live in the "users" table of the company database (db/schema.sql).
Passwords are never stored, only their bcrypt hash.

Create accounts from the terminal:
    python -m auth.users create <username> <role>     # asks for the password
    python -m auth.users demo                         # admin / employee / guest demo accounts
    python -m auth.users list
"""

import getpass
import sqlite3
import sys

import bcrypt

import config
from db.database import get_connection, init_db

ROLES = ("admin", "employee", "guest")
MIN_PASSWORD_LENGTH = 8

# Which answer sources each role may use (checked before the question is answered)
ROLE_ROUTES = {
    "admin": ("db", "doc", "web"),
    "employee": ("db", "doc", "web"),
    "guest": ("doc", "web"),
}
UPLOAD_ROLES = ("admin", "employee")

# Local demo accounts (change or delete them outside a demo)
DEMO_USERS = (
    ("admin", "Admin.2026!", "admin"),
    ("calisan", "Calisan.2026!", "employee"),
    ("misafir", "Misafir.2026!", "guest"),
)

# Used when the username does not exist, so a wrong username and a wrong
# password take the same time (does not reveal which usernames exist).
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)).decode()


def hash_password(password):
    salt = bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password, password_hash):
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_user(username, password, role, db_path=None):
    """Add a user and return its id. Raises ValueError for invalid input."""
    username = (username or "").strip()
    if not username:
        raise ValueError("Kullanıcı adı boş olamaz.")
    if role not in ROLES:
        raise ValueError(f"Geçersiz rol: {role!r}. Seçenekler: {', '.join(ROLES)}")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Şifre en az {MIN_PASSWORD_LENGTH} karakter olmalı.")

    init_db(db_path)
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hash_password(password), role),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"'{username}' kullanıcı adı zaten var.") from None
    finally:
        conn.close()


def check_login(username, password, db_path=None):
    """Return {"id", "username", "role"} if the credentials are correct, otherwise None."""
    username = (username or "").strip()
    password = password or ""
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        verify_password(password, _DUMMY_HASH)
        return None
    user_id, name, password_hash, role = row
    if not verify_password(password, password_hash):
        return None
    return {"id": user_id, "username": name, "role": role}


def list_users(db_path=None):
    """All users without password hashes: [{"id", "username", "role", "created_at"}]."""
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY id").fetchall()
    finally:
        conn.close()
    return [{"id": r[0], "username": r[1], "role": r[2], "created_at": r[3]} for r in rows]


def allowed_routes(role):
    return ROLE_ROUTES.get(role, ())


def can_upload(role):
    return role in UPLOAD_ROLES


def create_demo_users(db_path=None):
    """Create the demo accounts that do not exist yet. Returns the created usernames."""
    existing = {u["username"] for u in list_users(db_path)}
    created = []
    for username, password, role in DEMO_USERS:
        if username not in existing:
            create_user(username, password, role, db_path)
            created.append(username)
    return created


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["create"] and len(args) == 3:
        password = getpass.getpass("Şifre: ")
        if password != getpass.getpass("Şifre (tekrar): "):
            print("Şifreler eşleşmiyor.", file=sys.stderr)
            return 1
        try:
            create_user(args[1], password, args[2])
        except ValueError as error:
            print(error, file=sys.stderr)
            return 1
        print(f"Kullanıcı oluşturuldu: {args[1]} ({args[2]})")
        return 0
    if args == ["demo"]:
        created = create_demo_users()
        for username, password, role in DEMO_USERS:
            note = "oluşturuldu" if username in created else "zaten vardı"
            print(f"{username:<8} {password:<14} {role:<9} {note}")
        return 0
    if args == ["list"]:
        for user in list_users():
            print(f"{user['id']:>3}  {user['username']:<20} {user['role']:<9} {user['created_at']}")
        return 0
    print(__doc__.split("Create accounts from the terminal:")[1].strip())
    return 1


if __name__ == "__main__":
    sys.exit(main())
