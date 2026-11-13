-- Company database schema (SQLite).
--
-- Personal fields in customers (email, phone, tc_no, iban, birth_date) are
-- masked/encrypted by the security layer in Week 3.
-- The users table is filled by the login module in Week 3 (bcrypt hashes)
-- and must stay out of the Text-to-SQL table whitelist.

CREATE TABLE IF NOT EXISTS customers (
    id           INTEGER PRIMARY KEY,
    first_name   TEXT NOT NULL,
    last_name    TEXT NOT NULL,
    email        TEXT NOT NULL UNIQUE,
    phone        TEXT NOT NULL,
    tc_no        TEXT NOT NULL,
    iban         TEXT,
    birth_date   TEXT,               -- YYYY-MM-DD
    city         TEXT NOT NULL,
    created_at   TEXT NOT NULL       -- YYYY-MM-DD
);

CREATE TABLE IF NOT EXISTS suppliers (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    contact_name  TEXT NOT NULL,
    email         TEXT NOT NULL,
    phone         TEXT NOT NULL,
    city          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    category     TEXT NOT NULL,
    price        REAL NOT NULL CHECK (price >= 0),   -- TL
    stock        INTEGER NOT NULL CHECK (stock >= 0),
    supplier_id  INTEGER NOT NULL REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(id),
    product_id   INTEGER NOT NULL REFERENCES products(id),
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    unit_price   REAL NOT NULL,      -- TL, price at order time
    total_price  REAL NOT NULL,      -- quantity * unit_price
    status       TEXT NOT NULL CHECK (status IN ('pending', 'shipped', 'delivered', 'cancelled')),
    order_date   TEXT NOT NULL       -- YYYY-MM-DD
);

CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY,
    username       TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    role           TEXT NOT NULL CHECK (role IN ('admin', 'employee', 'guest')),
    created_at     TEXT NOT NULL DEFAULT (date('now'))
);

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_product ON orders(product_id);
CREATE INDEX IF NOT EXISTS idx_products_supplier ON products(supplier_id);
