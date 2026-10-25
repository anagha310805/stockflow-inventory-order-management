import os
import sys
from dotenv import load_dotenv

load_dotenv()

from backend import create_app
from backend.models import db, Category, Supplier, Product, User, Order


def verify_database():
    """
    Explicitly runnable database verification script.
    Inspects and displays counts and summaries for products, categories, suppliers,
    and users without exposing passwords or sensitive secrets.
    """
    app = create_app()
    with app.app_context():
        # Display safe, masked database connection info
        safe_url = db.engine.url.render_as_string(hide_password=True)
        is_cloud = "127.0.0.1" not in safe_url and "localhost" not in safe_url
        
        print("=" * 65)
        print("StockFlow Database Status & Verification Report")
        print("=" * 65)
        print(f"Target Database : {safe_url}")
        print(f"Environment     : {'Remote Cloud Production (TiDB Cloud)' if is_cloud else 'Local Database'}")
        print("-" * 65)

        # Test connection
        try:
            with db.engine.connect() as conn:
                pass
        except Exception as e:
            print(f"ERROR: Could not establish connection to the database.")
            print(f"Details: {e}")
            if not is_cloud:
                print("\nTip: To target your production TiDB Cloud database, set the DATABASE_URL:")
                print('  $env:DATABASE_URL = "mysql+pymysql://<USER>:<PASSWORD>@<HOST>:4000/stockflow?ssl_verify_cert=true"')
            sys.exit(1)

        # 1. Products
        products = Product.query.all()
        print(f"\n[Products] Total Count: {len(products)}")
        if products:
            for p in products:
                cat_name = p.category.name if p.category else "Uncategorized"
                sup_name = p.supplier.name if p.supplier else "None"
                print(f"  * [{p.sku}] {p.name:<24} | Price: ₹{p.price:>8.2f} | Stock: {p.stock:>3} | Cat: {cat_name:<12} | Sup: {sup_name:<20} | Status: {p.status}")
        else:
            print("  (No products found. Run 'python -m backend.seed_products' to seed sample catalog.)")

        # 2. Categories
        categories = Category.query.all()
        print(f"\n[Categories] Total Count: {len(categories)}")
        for c in categories:
            print(f"  * [ID {c.id}] {c.name}: {c.description}")

        # 3. Suppliers
        suppliers = Supplier.query.all()
        print(f"\n[Suppliers] Total Count: {len(suppliers)}")
        for s in suppliers:
            print(f"  * [ID {s.id}] {s.name} (Contact: {s.contact_person}, Email: {s.email}, Phone: {s.phone})")

        # 4. Users
        users = User.query.all()
        print(f"\n[Users] Total Count: {len(users)}")
        if users:
            for u in users:
                print(f"  * [ID {u.id}] {u.name:<25} | Email: {u.email:<30} | Role: {u.role:<10} | Active: {u.active}")
        else:
            print("  (No users found. Run 'python -m backend.init_admin' to initialize administrator account.)")

        # 5. Orders
        orders_count = Order.query.count()
        print(f"\n[Orders] Total Count: {orders_count}")

        print("\n" + "=" * 65)
        has_admin = any(u.role == "admin" for u in users)
        has_products = len(products) > 0

        if has_admin and has_products:
            print("STATUS: HEALTHY - Database is populated with products and administrator account.")
        else:
            issues = []
            if not has_products:
                issues.append("Missing sample products")
            if not has_admin:
                issues.append("Missing administrator account")
            print(f"STATUS: ACTION REQUIRED - {', '.join(issues)}.")
        print("=" * 65)
        return len(products), len(users), has_admin


if __name__ == "__main__":
    verify_database()
