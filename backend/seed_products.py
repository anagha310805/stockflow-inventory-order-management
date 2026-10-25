import os
import sys
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

from backend import create_app
from backend.models import db, Category, Supplier, Product, InventoryMovement


def seed_sample_products(app=None):
    """
    Explicitly runnable, idempotent seed script that populates exactly five realistic
    sample products and their required categories and suppliers.
    Safe to run repeatedly; skips existing records based on unique SKU and names.
    """
    target_app = app or create_app()
    with target_app.app_context():
        # Display safe, masked database connection info
        safe_url = db.engine.url.render_as_string(hide_password=True)
        is_cloud = "127.0.0.1" not in safe_url and "localhost" not in safe_url
        print(f"Connected to database: {safe_url}")
        if is_cloud:
            print(">> Target: Remote Cloud Production Database (TiDB Cloud)")
        else:
            print(">> Target: Local Database")

        # Test connection
        try:
            with db.engine.connect() as conn:
                pass
        except Exception as e:
            print(f"ERROR: Could not establish connection to the database: {e}")
            sys.exit(1)

        # Ensure schema tables exist safely
        db.create_all()

        # 1. Categories
        categories_data = [
            ("Computing", "Laptops, monitors, and core computing hardware"),
            ("Accessories", "Keyboards, mice, cables, and ergonomic workspace accessories"),
            ("Audio", "Headphones, headsets, and professional communication audio"),
        ]
        categories = {}
        for name, desc in categories_data:
            cat = Category.query.filter_by(name=name).first()
            if not cat:
                cat = Category(name=name, description=desc)
                db.session.add(cat)
                db.session.flush()
            categories[name] = cat

        # 2. Suppliers
        suppliers_data = [
            ("Northstar Electronics", "Supply Coordinator", "supply@northstar.example", "+91 80000 10001", "Bangalore, India"),
            ("Fieldwork Supply", "Logistics Lead", "orders@fieldwork.example", "+91 80000 10002", "Hyderabad, India"),
        ]
        suppliers = {}
        for name, contact, email, phone, addr in suppliers_data:
            sup = Supplier.query.filter_by(name=name).first()
            if not sup:
                sup = Supplier(name=name, contact_person=contact, email=email, phone=phone, address=addr, active=True)
                db.session.add(sup)
                db.session.flush()
            suppliers[name] = sup

        # 3. Exactly 5 Realistic Sample Products
        sample_products = [
            {
                "sku": "LAP-204",
                "name": "Work Laptop 14-inch",
                "description": "High-performance business laptop with 16GB RAM, 512GB SSD, and all-day battery life.",
                "price": Decimal("54999.00"),
                "stock": 18,
                "threshold": 5,
                "category": "Computing",
                "supplier": "Northstar Electronics",
                "image_url": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=800&q=80"
            },
            {
                "sku": "KEY-104",
                "name": "Wireless Keyboard",
                "description": "Quiet, comfortable ergonomic wireless keyboard with multi-device Bluetooth support.",
                "price": Decimal("1499.00"),
                "stock": 24,
                "threshold": 5,
                "category": "Accessories",
                "supplier": "Fieldwork Supply",
                "image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=800&q=80"
            },
            {
                "sku": "MOU-208",
                "name": "Wireless Mouse",
                "description": "Precise ergonomic optical mouse with adjustable DPI and silent click switches.",
                "price": Decimal("799.00"),
                "stock": 42,
                "threshold": 10,
                "category": "Accessories",
                "supplier": "Fieldwork Supply",
                "image_url": "https://images.unsplash.com/photo-1527814050087-3793815479db?auto=format&fit=crop&w=800&q=80"
            },
            {
                "sku": "MON-327",
                "name": "QHD Monitor 27-inch",
                "description": "Crisp 2560x1440 IPS display with USB-C hub connectivity and height-adjustable stand.",
                "price": Decimal("18999.00"),
                "stock": 8,
                "threshold": 3,
                "category": "Computing",
                "supplier": "Northstar Electronics",
                "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=800&q=80"
            },
            {
                "sku": "AUD-410",
                "name": "Over-Ear Headphones",
                "description": "Active noise-cancelling over-ear headphones with clear voice microphone for remote work.",
                "price": Decimal("4999.00"),
                "stock": 16,
                "threshold": 5,
                "category": "Audio",
                "supplier": "Northstar Electronics",
                "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=800&q=80"
            },
        ]

        added_count = 0
        existing_count = 0

        for p_data in sample_products:
            prod = Product.query.filter_by(sku=p_data["sku"]).first()
            if prod:
                existing_count += 1
            else:
                prod = Product(
                    sku=p_data["sku"],
                    name=p_data["name"],
                    description=p_data["description"],
                    price=p_data["price"],
                    stock=p_data["stock"],
                    low_stock_threshold=p_data["threshold"],
                    image_url=p_data["image_url"],
                    status="active",
                    category=categories[p_data["category"]],
                    supplier=suppliers[p_data["supplier"]]
                )
                db.session.add(prod)
                db.session.flush()
                # Record initial stock intake movement
                if prod.stock > 0:
                    db.session.add(InventoryMovement(
                        product_id=prod.id,
                        action="addition",
                        quantity=prod.stock,
                        note="Initial stock intake"
                    ))
                added_count += 1

        db.session.commit()
        total_products = Product.query.count()
        print(f"Products seed complete: {added_count} added, {existing_count} already existed. Total products in database: {total_products}")
        return added_count, existing_count, total_products


if __name__ == "__main__":
    seed_sample_products()
