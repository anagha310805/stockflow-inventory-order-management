import os
from decimal import Decimal

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

from backend import create_app
from backend.models import Category, InventoryMovement, Product, Supplier, User, db

app = create_app()


def seed():
    with app.app_context():
        db.create_all()
        category_names = ["Computing", "Accessories", "Audio", "Mobile", "Office"]
        categories = {}
        for name in category_names:
            category = Category.query.filter_by(name=name).first()
            if category is None:
                category = Category(name=name)
                db.session.add(category)
            categories[name] = category
        supplier_names = ["Northstar Electronics", "Fieldwork Supply", "Paper & Circuit"]
        suppliers = {}
        for name in supplier_names:
            supplier = Supplier.query.filter_by(name=name).first()
            if supplier is None:
                supplier = Supplier(name=name, contact_person="StockFlow Supply Desk",
                                    email="supply@example.test", phone="+91 80000 10000")
                db.session.add(supplier)
            suppliers[name] = supplier
        db.session.flush()
        products = [
            ("LAP-204", "Laptop", "A reliable 14-inch work laptop with all-day battery life.", "54999", 18, "Computing", 0),
            ("KEY-104", "Keyboard", "A quiet, comfortable wireless keyboard for focused work.", "1499", 24, "Accessories", 1),
            ("MOU-208", "Mouse", "A precise ergonomic wireless mouse with adjustable tracking.", "799", 42, "Accessories", 1),
            ("MON-327", "Monitor", "A crisp 27-inch QHD display with an adjustable stand.", "18999", 3, "Computing", 0),
            ("AUD-410", "Headphones", "Over-ear headphones with clear calls and rich sound.", "4999", 16, "Audio", 0),
            ("PHN-112", "Smartphone", "A fast, dependable phone with a vivid OLED display.", "32999", 12, "Mobile", 1),
            ("PRN-550", "Printer", "A compact wireless all-in-one for everyday office printing.", "8999", 0, "Office", 2),
            ("CAB-018", "USB Cable", "A durable 2-meter USB-C cable with fast charging support.", "399", 67, "Accessories", 2),
        ]
        for sku, name, description, price, stock, category_name, supplier_index in products:
            product = Product.query.filter_by(sku=sku).first()
            if product is None:
                product = Product(sku=sku, name=name, description=description, price=Decimal(price),
                                  stock=stock, low_stock_threshold=5,
                                  category=categories[category_name],
                                  supplier=suppliers[supplier_names[supplier_index]])
                db.session.add(product)
                db.session.flush()
                if stock:
                    db.session.add(InventoryMovement(product_id=product.id, action="addition",
                                                     quantity=stock, note="Seed inventory"))
        demo_password = os.getenv("DEMO_PASSWORD")
        demo_accounts = [
            (os.getenv("DEMO_ADMIN_EMAIL", "admin@stockflow.local"), "StockFlow Admin", "admin",
             os.getenv("INITIAL_ADMIN_PASSWORD") or demo_password),
            (os.getenv("DEMO_STAFF_EMAIL", "staff@stockflow.local"), "StockFlow Staff", "staff",
             os.getenv("INITIAL_STAFF_PASSWORD") or demo_password),
            (os.getenv("DEMO_CUSTOMER_EMAIL", "customer@stockflow.local"), "StockFlow Customer", "customer",
             demo_password),
        ]
        account_results = []
        for email, name, role, password in demo_accounts:
            existing = User.query.filter_by(email=email).first()
            if existing:
                account_results.append(f"Existing {role} account {email} (stored role: {existing.role}); unchanged.")
            elif password:
                db.session.add(User(name=name, email=email, phone="+91 90000 00000",
                                    role=role, password_hash=generate_password_hash(password)))
                account_results.append(f"Created {role} account {email}.")
            else:
                password_variable = {
                    "admin": "INITIAL_ADMIN_PASSWORD",
                    "staff": "INITIAL_STAFF_PASSWORD",
                    "customer": "DEMO_PASSWORD",
                }[role]
                account_results.append(f"Skipped {role} account {email}; set {password_variable} to create it.")
        db.session.commit()
        print("StockFlow sample catalog and inventory are ready.")
        for result in account_results:
            print(result)


if __name__ == "__main__":
    seed()