"""Fills the company database with realistic Turkish sample data.

Creates 200 customers, 50 products, 20 suppliers and 400 orders with
Faker("tr_TR"). A fixed random seed is used, so every run produces exactly
the same data on Windows, Linux and macOS (with the same Faker version),
which is handy for SQL accuracy tests with expected answers.
Running it again replaces the old sample data; the users table is not touched.

Run with:
    python db/seed.py
"""

import os
import random
import re
import sys
from datetime import date, timedelta

# Lets "python db/seed.py" find config.py in the project root (also on Windows/OneDrive)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faker import Faker

import config
from db.database import get_connection, init_db

SEED = 42
NUM_CUSTOMERS = 200
NUM_PRODUCTS = 50
NUM_SUPPLIERS = 20
NUM_ORDERS = 400

# Faker's tr_TR city names are not real cities, so we pick from this list (with weights)
CITIES = {
    "İstanbul": 25, "Ankara": 12, "İzmir": 10, "Bursa": 6, "Antalya": 5,
    "Kocaeli": 4, "Konya": 4, "Adana": 4, "Gaziantep": 3, "Mersin": 3,
    "Kayseri": 3, "Eskişehir": 3, "Samsun": 3, "Trabzon": 2, "Denizli": 2,
    "Diyarbakır": 2, "Sakarya": 2, "Tekirdağ": 2, "Muğla": 2, "Malatya": 2,
}

MOBILE_PREFIXES = ["501", "505", "506", "507", "530", "532", "533", "535", "536", "538",
                   "539", "541", "542", "543", "544", "545", "546", "548", "549", "551",
                   "552", "553", "554", "555", "559"]

# (category, product name, min price TL, max price TL) -> exactly 50 products
CATALOG = [
    ("Elektronik", "Kablosuz Kulaklık", 800, 4000),
    ("Elektronik", "Akıllı Saat", 1500, 9000),
    ("Elektronik", "Dizüstü Bilgisayar", 18000, 55000),
    ("Elektronik", "Tablet", 6000, 25000),
    ("Elektronik", "Bluetooth Hoparlör", 700, 4500),
    ("Elektronik", "Powerbank", 400, 1500),
    ("Elektronik", "Oyuncu Faresi", 500, 2500),
    ("Elektronik", "Mekanik Klavye", 1200, 5000),
    ("Elektronik", "27 İnç Monitör", 5000, 15000),
    ("Elektronik", "Web Kamerası", 600, 3000),
    ("Ev & Yaşam", "Kahve Makinesi", 2500, 12000),
    ("Ev & Yaşam", "Elektrikli Süpürge", 3000, 18000),
    ("Ev & Yaşam", "Tost Makinesi", 900, 3500),
    ("Ev & Yaşam", "Çaydanlık Seti", 600, 2500),
    ("Ev & Yaşam", "Nevresim Takımı", 700, 3000),
    ("Ev & Yaşam", "Masa Lambası", 300, 1500),
    ("Ev & Yaşam", "Hava Temizleyici", 3500, 12000),
    ("Ev & Yaşam", "Blender", 1000, 4000),
    ("Ev & Yaşam", "Yemek Takımı", 1500, 7000),
    ("Ev & Yaşam", "Buharlı Ütü", 1000, 4000),
    ("Giyim", "Kot Pantolon", 600, 2500),
    ("Giyim", "Pamuklu Tişört", 200, 800),
    ("Giyim", "Kapüşonlu Sweatshirt", 500, 1800),
    ("Giyim", "Kışlık Mont", 1500, 7000),
    ("Giyim", "Spor Ayakkabı", 1200, 5500),
    ("Giyim", "Deri Kemer", 300, 1200),
    ("Giyim", "Yün Atkı", 250, 900),
    ("Giyim", "Oxford Gömlek", 450, 1500),
    ("Giyim", "Triko Kazak", 500, 1800),
    ("Giyim", "Sırt Çantası", 600, 2500),
    ("Kırtasiye", "Defter Seti", 100, 400),
    ("Kırtasiye", "Tükenmez Kalem Seti", 60, 250),
    ("Kırtasiye", "Ajanda", 150, 600),
    ("Kırtasiye", "Dosya Klasörü", 40, 200),
    ("Kırtasiye", "Masaüstü Organizer", 150, 700),
    ("Kırtasiye", "A4 Fotokopi Kağıdı", 150, 400),
    ("Kırtasiye", "Bilimsel Hesap Makinesi", 400, 1500),
    ("Kırtasiye", "Boya Kalemi Seti", 120, 600),
    ("Kırtasiye", "Yapışkanlı Not Kağıdı", 30, 150),
    ("Kırtasiye", "Zımba Makinesi", 80, 350),
    ("Spor & Outdoor", "Yoga Matı", 300, 1200),
    ("Spor & Outdoor", "Dambıl Seti", 800, 3500),
    ("Spor & Outdoor", "Koşu Bandı", 12000, 40000),
    ("Spor & Outdoor", "Kamp Çadırı", 1500, 8000),
    ("Spor & Outdoor", "Uyku Tulumu", 800, 3500),
    ("Spor & Outdoor", "Çelik Termos", 300, 1200),
    ("Spor & Outdoor", "Bisiklet Kaskı", 600, 2500),
    ("Spor & Outdoor", "Pilates Topu", 200, 700),
    ("Spor & Outdoor", "Atlama İpi", 80, 400),
    ("Spor & Outdoor", "Trekking Batonu", 400, 1800),
]

SUPPLIER_SECTORS = ["Ticaret", "Dağıtım", "Toptan Satış", "Lojistik", "Sanayi", "İthalat"]
SUPPLIER_SUFFIXES = ["A.Ş.", "Ltd. Şti."]

# Order statuses with their probability weights
ORDER_STATUSES = {"delivered": 60, "shipped": 15, "pending": 15, "cancelled": 10}
ORDER_QUANTITIES = {1: 50, 2: 25, 3: 12, 4: 8, 5: 5}

# Fixed date ranges keep the data the same no matter which day the script runs
CUSTOMER_SINCE = (date(2023, 1, 1), date(2025, 10, 31))
BIRTH_DATES = (date(1955, 1, 1), date(2006, 12, 31))
ORDER_DATES = (date(2025, 11, 1), date(2026, 10, 31))

_TR_TO_ASCII = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")

INSERT_CUSTOMER = """
    INSERT INTO customers (id, first_name, last_name, email, phone, tc_no, iban, birth_date, city, created_at)
    VALUES (:id, :first_name, :last_name, :email, :phone, :tc_no, :iban, :birth_date, :city, :created_at)
"""
INSERT_SUPPLIER = """
    INSERT INTO suppliers (id, name, contact_name, email, phone, city)
    VALUES (:id, :name, :contact_name, :email, :phone, :city)
"""
INSERT_PRODUCT = """
    INSERT INTO products (id, name, category, price, stock, supplier_id)
    VALUES (:id, :name, :category, :price, :stock, :supplier_id)
"""
INSERT_ORDER = """
    INSERT INTO orders (id, customer_id, product_id, quantity, unit_price, total_price, status, order_date)
    VALUES (:id, :customer_id, :product_id, :quantity, :unit_price, :total_price, :status, :order_date)
"""
# Children first, so foreign keys are never broken while deleting
CLEAR_SAMPLE_DATA = ["DELETE FROM orders", "DELETE FROM products", "DELETE FROM suppliers", "DELETE FROM customers"]
COUNT_QUERIES = {
    "customers": "SELECT COUNT(*) FROM customers",
    "products": "SELECT COUNT(*) FROM products",
    "suppliers": "SELECT COUNT(*) FROM suppliers",
    "orders": "SELECT COUNT(*) FROM orders",
    "users": "SELECT COUNT(*) FROM users",
}


def slugify(text):
    """'Şükrü Öztürk' -> 'sukruozturk' (ASCII only, for e-mail addresses)."""
    return re.sub(r"[^a-z0-9]", "", text.translate(_TR_TO_ASCII).lower())


def mobile_phone(rng):
    """Turkish mobile number in one fixed format: '0532 123 45 67'."""
    return f"0{rng.choice(MOBILE_PREFIXES)} {rng.randint(0, 999):03d} {rng.randint(0, 99):02d} {rng.randint(0, 99):02d}"


def random_date(rng, start, end):
    """Random date between start and end (inclusive) as 'YYYY-MM-DD'.

    Faker's date functions are not used on purpose: they draw random numbers
    differently on Windows and Linux/macOS, so the same seed gave different data.
    """
    return (start + timedelta(days=rng.randint(0, (end - start).days))).isoformat()


def pick_city(rng):
    return rng.choices(list(CITIES), weights=list(CITIES.values()))[0]


def make_customers(fake, rng, count=NUM_CUSTOMERS):
    customers, used_emails = [], set()
    for customer_id in range(1, count + 1):
        first, last = fake.first_name(), fake.last_name()
        base = f"{slugify(first)}.{slugify(last)}"
        email, n = base, 1
        while email in used_emails:
            n += 1
            email = f"{base}{n}"
        used_emails.add(email)
        customers.append({
            "id": customer_id,
            "first_name": first,
            "last_name": last,
            "email": f"{email}@{rng.choice(['example.com', 'example.net', 'example.org'])}",
            "phone": mobile_phone(rng),
            "tc_no": fake.ssn(),  # valid 11-digit TC kimlik no (passes the checksum)
            "iban": fake.iban(),
            "birth_date": random_date(rng, *BIRTH_DATES),
            "city": pick_city(rng),
            "created_at": random_date(rng, *CUSTOMER_SINCE),
        })
    return customers


def make_suppliers(fake, rng, count=NUM_SUPPLIERS):
    suppliers, used_names = [], set()
    while len(suppliers) < count:
        last, sector = fake.last_name(), rng.choice(SUPPLIER_SECTORS)
        name = f"{last} {sector} {rng.choice(SUPPLIER_SUFFIXES)}"
        if name in used_names:
            continue
        used_names.add(name)
        suppliers.append({
            "id": len(suppliers) + 1,
            "name": name,
            "contact_name": fake.name(),
            "email": f"satis@{slugify(last + sector)}.example.com",
            "phone": mobile_phone(rng),
            "city": pick_city(rng),
        })
    return suppliers


def make_products(rng, supplier_ids, count=NUM_PRODUCTS):
    products = []
    for product_id, (category, name, low, high) in enumerate(CATALOG[:count], start=1):
        price = round(rng.uniform(low, high) / 10) * 10 - 0.10  # e.g. 1249.90
        products.append({
            "id": product_id,
            "name": name,
            "category": category,
            "price": round(price, 2),
            "stock": rng.randint(0, 300),
            "supplier_id": rng.choice(supplier_ids),
        })
    return products


def make_orders(fake, rng, customer_ids, products, count=NUM_ORDERS):
    # Uneven weights: a few loyal customers order a lot, some never order
    customer_weights = [rng.paretovariate(3.0) for _ in customer_ids]
    orders = []
    for order_id in range(1, count + 1):
        product = rng.choice(products)
        quantity = rng.choices(list(ORDER_QUANTITIES), weights=list(ORDER_QUANTITIES.values()))[0]
        orders.append({
            "id": order_id,
            "customer_id": rng.choices(customer_ids, weights=customer_weights)[0],
            "product_id": product["id"],
            "quantity": quantity,
            "unit_price": product["price"],
            "total_price": round(product["price"] * quantity, 2),
            "status": rng.choices(list(ORDER_STATUSES), weights=list(ORDER_STATUSES.values()))[0],
            "order_date": random_date(rng, *ORDER_DATES),
        })
    return orders


def seed_database(db_path=None, seed=SEED):
    """Create the tables and fill them with sample data. Returns row counts per table."""
    fake = Faker("tr_TR")
    fake.seed_instance(seed)
    rng = random.Random(seed)

    customers = make_customers(fake, rng)
    suppliers = make_suppliers(fake, rng)
    products = make_products(rng, [s["id"] for s in suppliers])
    orders = make_orders(fake, rng, [c["id"] for c in customers], products)

    init_db(db_path)
    conn = get_connection(db_path)
    try:
        with conn:  # one transaction: all or nothing
            for statement in CLEAR_SAMPLE_DATA:
                conn.execute(statement)
            conn.executemany(INSERT_CUSTOMER, customers)
            conn.executemany(INSERT_SUPPLIER, suppliers)
            conn.executemany(INSERT_PRODUCT, products)
            conn.executemany(INSERT_ORDER, orders)
        return {table: conn.execute(sql).fetchone()[0] for table, sql in COUNT_QUERIES.items()}
    finally:
        conn.close()


def main():
    counts = seed_database()
    print(f"Company database ready: {config.DB_PATH}")
    for table, count in counts.items():
        print(f"  {table:<10} {count}")


if __name__ == "__main__":
    main()
