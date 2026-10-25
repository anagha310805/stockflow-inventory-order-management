import math
import re
import csv
import io
from datetime import datetime, time, timedelta, timezone

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import or_, update
from werkzeug.security import check_password_hash, generate_password_hash

from .config import Config
from .models import CartItem, Category, InventoryMovement, Order, Product, Supplier, User, db
from .services import BusinessError, create_order, place_order, transition_order


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Set SECRET_KEY in the environment before starting StockFlow.")
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("Set DATABASE_URL or MYSQL_USER and MYSQL_PASSWORD before starting StockFlow.")
    db.init_app(app)
    raw_origins = app.config["CORS_ORIGINS"]
    configured_origins = raw_origins if isinstance(raw_origins, list) else [raw_origins]
    vercel_pattern = re.compile(r"^https://[a-zA-Z0-9\-_]+\.vercel\.app$")
    cors_origins = [vercel_pattern] + [o for o in configured_origins if isinstance(o, str)]
    CORS(app, origins=cors_origins, supports_credentials=True)
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="stockflow-auth")

    def error(message, status=400):
        return jsonify({"error": message}), status

    def token_user(roles=None):
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if not token:
            return None, error("Authentication required.", 401)
        try:
            user_id = serializer.loads(token, max_age=app.config["TOKEN_MAX_AGE"])
        except (BadSignature, SignatureExpired):
            return None, error("Your session is invalid or expired.", 401)
        user = db.session.get(User, user_id)
        if user is None or not user.active:
            return None, error("This account is unavailable.", 401)
        if roles and user.role not in roles:
            return None, error("You are not authorized to perform this action.", 403)
        return user, None

    def payload():
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    def user_json(user):
        return {"id": user.id, "name": user.name, "email": user.email, "phone": user.phone,
                "role": user.role, "active": user.active}

    def product_json(product):
        return {"id": product.id, "sku": product.sku, "name": product.name,
                "description": product.description, "price": float(product.price),
                "stock": product.stock, "threshold": product.low_stock_threshold,
                "imageUrl": product.image_url, "status": product.status,
                "category": product.category.name if product.category else "Uncategorized",
                "categoryId": product.category_id,
                "supplier": product.supplier.name if product.supplier else "Unassigned",
                "supplierId": product.supplier_id}

    def order_json(order):
        return {"id": order.id, "number": order.number, "status": order.status,
                "subtotal": float(order.subtotal), "discount": float(order.discount),
                "total": float(order.total), "createdAt": order.created_at.isoformat(),
                "customer": user_json(order.user),
                "deliveryAddress": getattr(order, "delivery_address", None),
                "items": [{"productId": row.product_id, "name": row.product_name,
                           "sku": row.sku, "unitPrice": float(row.unit_price),
                           "quantity": row.quantity} for row in order.items]}

    @app.get("/")
    def root():
        return jsonify({"status": "ok", "service": "StockFlow API", "version": "1.0.0"})

    @app.get("/health")
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "StockFlow API"})

    @app.post("/api/auth/register")
    def register():
        data = payload()
        name, email, phone, password = (str(data.get(key, "")).strip() for key in ("name", "email", "phone", "password"))
        if (len(name) < 2 or len(name) > 120 or len(email) > 255
            or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is None):
            return error("Enter a valid name and email.")
        if (re.fullmatch(r"[+()0-9.\s-]{7,30}", phone) is None
            or sum(character.isdigit() for character in phone) < 7
            or not password or len(password) < 8):
            return error("Enter a valid phone number and a password of at least 8 characters.")
        email = email.lower()
        if User.query.filter_by(email=email).first():
            return error("An account with that email already exists.", 409)
        user = User(name=name, email=email, phone=phone, role="customer",
                    password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return jsonify({"token": serializer.dumps(user.id), "user": user_json(user)}), 201

    @app.post("/api/auth/login")
    def login():
        data = payload()
        user = User.query.filter_by(email=str(data.get("email", "")).strip().lower()).first()
        if user is None or not user.active or not check_password_hash(user.password_hash, str(data.get("password", ""))):
            return error("Email or password is incorrect.", 401)
        return jsonify({"token": serializer.dumps(user.id), "user": user_json(user)})

    @app.get("/api/auth/me")
    def me():
        user, failure = token_user()
        return failure or jsonify({"user": user_json(user)})

    @app.patch("/api/profile")
    def profile():
        user, failure = token_user()
        if failure:
            return failure
        data = payload()
        name = str(data.get("name", user.name)).strip()
        phone = str(data.get("phone", user.phone)).strip()
        if (len(name) < 2 or re.fullmatch(r"[+()0-9.\s-]{7,30}", phone) is None
            or sum(character.isdigit() for character in phone) < 7):
            return error("Enter a valid name and phone number.")
        user.name, user.phone = name, phone
        db.session.commit()
        return jsonify({"user": user_json(user)})

    @app.get("/api/products")
    def products():
        status = request.args.get("status")
        if status and status != "all":
            query = Product.query.filter_by(status=status)
        elif status == "all":
            query = Product.query
        else:
            query = Product.query.filter_by(status="active")
        search = request.args.get("q", "").strip()
        if search:
            query = query.filter(Product.name.ilike(f"%{search}%") | Product.sku.ilike(f"%{search}%"))
        category = request.args.get("category", type=int)
        supplier = request.args.get("supplier", type=int)
        minimum = request.args.get("min", type=float)
        maximum = request.args.get("max", type=float)
        if category:
            query = query.filter_by(category_id=category)
        if supplier:
            query = query.filter_by(supplier_id=supplier)
        if minimum is not None:
            query = query.filter(Product.price >= minimum)
        if maximum is not None:
            query = query.filter(Product.price <= maximum)
        if request.args.get("available") == "true":
            query = query.filter(Product.stock > 0)
        return jsonify({"products": [product_json(row) for row in query.order_by(Product.name).all()]})

    @app.get("/api/categories")
    def categories():
        query = Category.query
        search = request.args.get("q", "").strip()
        if search:
            query = query.filter(Category.name.ilike(f"%{search}%"))
        return jsonify({"categories": [{"id": row.id, "name": row.name}
                                        for row in query.order_by(Category.name).all()]})

    @app.get("/api/suppliers")
    def suppliers():
        query = Supplier.query.filter_by(active=True)
        search = request.args.get("q", "").strip()
        if search:
            query = query.filter(Supplier.name.ilike(f"%{search}%"))
        return jsonify({"suppliers": [{"id": row.id, "name": row.name, "productCount": len(row.products)}
                                       for row in query.order_by(Supplier.name).all()]})

    @app.get("/api/products/<int:product_id>")
    def product_detail(product_id):
        product = Product.query.filter_by(id=product_id, status="active").first()
        if product is None:
            return error("Product not found.", 404)
        return jsonify({"product": product_json(product)})

    @app.route("/api/customers", methods=["GET", "POST"])
    def customers():
        user, failure = token_user({"staff", "admin"})
        if failure:
            return failure
        if request.method == "POST":
            if user.role != "admin":
                return error("Only administrators can create customer accounts.", 403)
            data = payload()
            name, email = str(data.get("name", "")).strip(), str(data.get("email", "")).strip().lower()
            phone, password = str(data.get("phone", "")).strip(), str(data.get("password", ""))
            if len(name) < 2 or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is None:
                return error("Enter a valid customer name and email.")
            if User.query.filter_by(email=email).first():
                return error("An account with that email already exists.", 409)
            if len(password) < 8 or re.fullmatch(r"[+()0-9.\s-]{7,30}", phone) is None:
                return error("Provide a valid phone number and password of at least 8 characters.")
            customer = User(name=name, email=email, phone=phone, role="customer",
                            password_hash=generate_password_hash(password))
            db.session.add(customer)
            db.session.commit()
            return jsonify({"customer": user_json(customer)}), 201
        query = User.query.filter_by(role="customer")
        search = request.args.get("q", "").strip()
        if search:
            pattern = f"%{search}%"
            query = query.filter(or_(User.name.ilike(pattern), User.email.ilike(pattern), User.phone.ilike(pattern)))
        return jsonify({"customers": [user_json(row) for row in query.order_by(User.name).all()]})

    @app.patch("/api/customers/<int:customer_id>")
    def update_customer(customer_id):
        user, failure = token_user({"admin"})
        if failure:
            return failure
        customer = db.session.get(User, customer_id)
        if customer is None or customer.role != "customer":
            return error("Customer not found.", 404)
        data = payload()
        name = str(data.get("name", customer.name)).strip()
        email = str(data.get("email", customer.email)).strip().lower()
        phone = str(data.get("phone", customer.phone)).strip()
        duplicate = User.query.filter(User.email == email, User.id != customer.id).first()
        if len(name) < 2 or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is None:
            return error("Enter a valid customer name and email.")
        if duplicate:
            return error("An account with that email already exists.", 409)
        if re.fullmatch(r"[+()0-9.\s-]{7,30}", phone) is None:
            return error("Enter a valid phone number.")
        customer.name, customer.email, customer.phone = name, email, phone
        if "active" in data and type(data["active"]) is bool:
            customer.active = data["active"]
        db.session.commit()
        return jsonify({"customer": user_json(customer)})

    @app.delete("/api/customers/<int:customer_id>")
    def delete_customer(customer_id):
        user, failure = token_user({"admin"})
        if failure:
            return failure
        customer = db.session.get(User, customer_id)
        if customer is None or customer.role != "customer":
            return error("Customer not found.", 404)
        if Order.query.filter_by(user_id=customer.id).first():
            return error("This customer has order history; deactivate the account instead.", 409)
        CartItem.query.filter_by(user_id=customer.id).delete(synchronize_session=False)
        db.session.delete(customer)
        db.session.commit()
        return jsonify({"deleted": True})

    @app.patch("/api/profile/password")
    def change_password():
        user, failure = token_user()
        if failure:
            return failure
        data = payload()
        current, replacement = str(data.get("currentPassword", "")), str(data.get("newPassword", ""))
        if not check_password_hash(user.password_hash, current):
            return error("Current password is incorrect.", 401)
        if len(replacement) < 8:
            return error("New password must be at least 8 characters.")
        user.password_hash = generate_password_hash(replacement)
        db.session.commit()
        return jsonify({"updated": True})

    @app.route("/api/categories/manage", methods=["POST", "PATCH", "DELETE"])
    def manage_categories():
        user, failure = token_user({"staff", "admin"})
        if failure:
            return failure
        data = payload()
        category_id = data.get("id") or request.args.get("id", type=int)
        category = db.session.get(Category, category_id) if category_id else None
        if request.method == "POST":
            name = str(data.get("name", "")).strip()
            if not name or len(name) > 100:
                return error("Category name is required.")
            if Category.query.filter(Category.name.ilike(name)).first():
                return error("A category with that name already exists.", 409)
            category = Category(name=name, description=str(data.get("description", ""))[:300])
            db.session.add(category)
        elif category is None:
            return error("Category not found.", 404)
        elif request.method == "DELETE":
            if Product.query.filter_by(category_id=category.id).first():
                return error("Move the category's products before removing it.", 409)
            db.session.delete(category)
        else:
            name = str(data.get("name", category.name)).strip()
            if not name or len(name) > 100:
                return error("Category name is required.")
            if Category.query.filter(Category.name.ilike(name), Category.id != category.id).first():
                return error("A category with that name already exists.", 409)
            category.name = name
            category.description = str(data.get("description", category.description))[:300]
        deleted = request.method == "DELETE"
        db.session.commit()
        return jsonify({"category": None if deleted else {"id": category.id, "name": category.name}})

    @app.route("/api/suppliers/manage", methods=["GET", "POST", "PATCH", "DELETE"])
    def manage_suppliers():
        user, failure = token_user({"staff", "admin"})
        if failure:
            return failure
        data = payload()
        if request.method == "GET":
            query = Supplier.query
            search = request.args.get("q", "").strip()
            if search:
                pattern = f"%{search}%"
                query = query.filter(or_(Supplier.name.ilike(pattern), Supplier.contact_person.ilike(pattern),
                                         Supplier.email.ilike(pattern), Supplier.phone.ilike(pattern)))
            return jsonify({"suppliers": [{"id": row.id, "name": row.name,
                                           "contactPerson": row.contact_person, "email": row.email,
                                           "phone": row.phone, "address": row.address, "active": row.active,
                                           "productCount": len(row.products),
                                           "products": [{"id": p.id, "name": p.name, "sku": p.sku, "status": p.status} for p in row.products]}
                                          for row in query.order_by(Supplier.name).all()]})
        supplier_id = data.get("id") or request.args.get("id", type=int)
        supplier = db.session.get(Supplier, supplier_id) if supplier_id else None
        if request.method == "POST":
            name = str(data.get("name", "")).strip()
            if not name:
                return error("Supplier name is required.")
            supplier = Supplier(name=name)
            db.session.add(supplier)
        elif supplier is None:
            return error("Supplier not found.", 404)
        elif request.method == "DELETE":
            if Product.query.filter_by(supplier_id=supplier.id).first():
                return error("Reassign the supplier's products before removing it.", 409)
            db.session.delete(supplier)
            db.session.commit()
            return jsonify({"supplier": None})
        supplier.name = str(data.get("name", supplier.name)).strip()
        supplier.contact_person = str(data.get("contactPerson", supplier.contact_person))[:120]
        supplier.email = str(data.get("email", supplier.email))[:255]
        supplier.phone = str(data.get("phone", supplier.phone))[:30]
        supplier.address = str(data.get("address", supplier.address))[:300]
        db.session.commit()
        return jsonify({"supplier": {"id": supplier.id, "name": supplier.name,
                                     "contactPerson": supplier.contact_person,
                                     "email": supplier.email, "phone": supplier.phone,
                                     "address": supplier.address, "active": supplier.active}})

    @app.route("/api/cart", methods=["GET", "POST", "PATCH", "DELETE"])
    def cart():
        user, failure = token_user({"customer"})
        if failure:
            return failure
        data = payload()
        if request.method == "POST":
            product = db.session.get(Product, data.get("productId"))
            quantity = data.get("quantity", 1)
            if product is None or product.status != "active" or type(quantity) is not int or quantity < 1:
                return error("Choose an available product and a valid quantity.")
            row = CartItem.query.filter_by(user_id=user.id, product_id=product.id).first()
            new_quantity = quantity + (row.quantity if row else 0)
            if new_quantity > product.stock:
                return error("Requested quantity exceeds available stock.", 409)
            if row:
                row.quantity = new_quantity
            else:
                db.session.add(CartItem(user_id=user.id, product_id=product.id, quantity=quantity))
            db.session.commit()
        elif request.method == "PATCH":
            row = CartItem.query.filter_by(user_id=user.id, product_id=data.get("productId")).first()
            quantity = data.get("quantity")
            if row is None or type(quantity) is not int or quantity < 1 or quantity > row.product.stock:
                return error("Choose a valid quantity within available stock.")
            row.quantity = quantity
            db.session.commit()
        elif request.method == "DELETE":
            CartItem.query.filter_by(user_id=user.id, product_id=request.args.get("productId", type=int)).delete()
            db.session.commit()
        rows = CartItem.query.filter_by(user_id=user.id).all()
        return jsonify({"items": [{"product": product_json(row.product), "quantity": row.quantity,
                                    "lineTotal": round(float(row.product.price) * row.quantity, 2)} for row in rows]})

    @app.route("/api/orders", methods=["GET", "POST"])
    def orders():
        user, failure = token_user()
        if failure:
            return failure
        if request.method == "POST":
            data = payload()
            delivery_addr = data.get("deliveryAddress") or data.get("delivery_address")
            try:
                if user.role == "customer":
                    order = place_order(user.id, delivery_address=delivery_addr)
                elif user.role in {"staff", "admin"}:
                    customer = db.session.get(User, data.get("customerId"))
                    if customer is None or customer.role != "customer" or not customer.active:
                        return error("Choose an active customer account.")
                    items = data.get("items", [])
                    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
                        return error("Order items must be a list.")
                    order = create_order(customer.id, [
                        (item.get("productId"), item.get("quantity"))
                        for item in items
                    ], actor_id=user.id, delivery_address=delivery_addr)
                else:
                    return error("You are not authorized to place orders.", 403)
            except BusinessError as exc:
                return error(str(exc), 409)
            return jsonify({"order": order_json(order)}), 201
        query = Order.query.order_by(Order.created_at.desc())
        if user.role == "customer":
            query = query.filter_by(user_id=user.id)
        elif user.role not in {"staff", "admin"}:
            return error("You are not authorized to view orders.", 403)
        return jsonify({"orders": [order_json(row) for row in query.all()]})

    @app.get("/api/orders/<int:order_id>")
    def get_order(order_id):
        user, failure = token_user()
        if failure:
            return failure
        order = db.session.get(Order, order_id)
        if order is None:
            return error("Order not found.", 404)
        if user.role == "customer" and order.user_id != user.id:
            return error("You are not authorized to view this order.", 403)
        if user.role not in {"customer", "staff", "admin"}:
            return error("You are not authorized to view this order.", 403)
        return jsonify({"order": order_json(order)})

    @app.patch("/api/orders/<int:order_id>/status")
    def order_status(order_id):
        user, failure = token_user()
        if failure:
            return failure
        order = db.session.get(Order, order_id)
        if order is None:
            return error("Order not found.", 404)
        status = payload().get("status")
        if user.role == "customer":
            if order.user_id != user.id or status != "cancelled":
                return error("You can only cancel your own eligible orders.", 403)
        elif user.role not in {"staff", "admin"}:
            return error("You are not authorized to update orders.", 403)
        try:
            transition_order(order, status, user.id)
        except BusinessError as exc:
            db.session.rollback()
            return error(str(exc), 409)
        return jsonify({"order": order_json(order)})

    @app.route("/api/products/manage", methods=["GET", "POST", "PATCH", "DELETE"])
    def manage_products():
        user, failure = token_user({"staff", "admin"})
        if failure:
            return failure
        if request.method == "GET":
            query = Product.query
            status = request.args.get("status", "active")
            if status != "all":
                query = query.filter_by(status=status)
            search = request.args.get("q", "").strip()
            if search:
                query = query.filter(Product.name.ilike(f"%{search}%") | Product.sku.ilike(f"%{search}%"))
            category_id = request.args.get("category", type=int)
            supplier_id = request.args.get("supplier", type=int)
            if category_id:
                query = query.filter_by(category_id=category_id)
            if supplier_id:
                query = query.filter_by(supplier_id=supplier_id)
            return jsonify({"products": [product_json(item) for item in query.order_by(Product.name).all()]})
        data = payload()
        product_id = data.get("id") or request.args.get("id", type=int)
        product = db.session.get(Product, product_id) if product_id else None
        if request.method != "POST" and product is None:
            return error("Product not found.", 404)
        sku_value = str(data.get("sku", product.sku if product else "")).strip()
        duplicate_sku = Product.query.filter(Product.sku == sku_value)
        if product is not None:
            duplicate_sku = duplicate_sku.filter(Product.id != product.id)
        if sku_value and duplicate_sku.first():
            return error("That SKU is already in use.", 409)
        if request.method == "DELETE":
            product.status = "inactive"
        else:
            if request.method == "POST" and any(key not in data for key in ("sku", "name", "price")):
                return error("SKU, name, and price are required.")
            try:
                raw_price = data.get("price", product.price if product else 0)
                raw_threshold = data.get("threshold", product.low_stock_threshold if product else 5)
                raw_stock = data.get("stock", 0) if product is None else product.stock
                if (isinstance(raw_price, bool) or not isinstance(raw_price, (int, float))
                        or type(raw_threshold) is not int or type(raw_stock) is not int):
                    raise ValueError
                price = float(raw_price)
                threshold = raw_threshold
                initial_stock = raw_stock
                if not math.isfinite(price) or price < 0 or price >= 100000000 or initial_stock < 0 or threshold < 0:
                    raise ValueError
            except (TypeError, ValueError):
                return error("Price and inventory values must be non-negative numbers.")
            name = str(data.get("name", product.name if product else "")).strip()
            sku = str(data.get("sku", product.sku if product else "")).strip()
            if not name or len(name) > 180 or not sku or len(sku) > 50:
                return error("Product name and SKU are required and must fit their field limits.")
            category_id = data.get("categoryId", product.category_id if product else None)
            supplier_id = data.get("supplierId", product.supplier_id if product else None)
            if category_id is not None and (type(category_id) is not int or db.session.get(Category, category_id) is None):
                return error("Choose an existing category.")
            if supplier_id is not None and (type(supplier_id) is not int or db.session.get(Supplier, supplier_id) is None):
                return error("Choose an existing supplier.")
            if product is None:
                product = Product(sku=sku, name=name,
                                  price=price, stock=initial_stock)
                db.session.add(product)
                if initial_stock:
                    db.session.flush()
                    db.session.add(InventoryMovement(product_id=product.id, user_id=user.id,
                                                     action="addition", quantity=initial_stock,
                                                     note="Initial inventory"))
            else:
                product.sku = sku
                product.name = name
                product.price = price
            product.description = str(data.get("description", product.description if product.id else ""))
            product.low_stock_threshold = threshold
            product.image_url = str(data.get("imageUrl", product.image_url if product.id else ""))
            product.category_id = category_id
            product.supplier_id = supplier_id
            product.status = "active"
        db.session.commit()
        return jsonify({"product": product_json(product)})

    @app.post("/api/inventory/<int:product_id>")
    def adjust_inventory(product_id):
        user, failure = token_user({"staff", "admin"})
        if failure:
            return failure
        data = payload()
        quantity, action = data.get("quantity"), data.get("action")
        product = db.session.get(Product, product_id)
        if product is None:
            return error("Product not found.", 404)
        if type(quantity) is not int or quantity < 1 or action not in {"addition", "reduction"}:
            return error("Choose an addition or reduction and a positive whole quantity.")
        delta = quantity if action == "addition" else -quantity
        changed = db.session.execute(
            update(Product).where(Product.id == product_id, Product.stock + delta >= 0)
            .values(stock=Product.stock + delta).execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            db.session.rollback()
            return error("Inventory cannot be reduced below zero.", 409)
        db.session.add(InventoryMovement(product_id=product_id, user_id=user.id,
                                         action=action, quantity=delta,
                                         note=str(data.get("note", ""))[:300]))
        db.session.commit()
        db.session.refresh(product)
        return jsonify({"product": product_json(product)})

    @app.get("/api/inventory/movements")
    def inventory_history():
        user, failure = token_user({"staff", "admin"})
        if failure:
            return failure
        rows = InventoryMovement.query.order_by(InventoryMovement.created_at.desc()).limit(250).all()
        return jsonify({"movements": [{"id": row.id, "product": row.product.name,
                                        "sku": row.product.sku, "action": row.action,
                                        "quantity": row.quantity, "note": row.note,
                                        "user": row.user.name if row.user else "System",
                                        "createdAt": row.created_at.isoformat()} for row in rows]})

    @app.get("/api/admin/overview")
    def admin_overview():
        user, failure = token_user({"admin"})
        if failure:
            return failure
        products = Product.query.filter_by(status="active").all()
        inventory_value = sum((row.price * row.stock for row in products), start=0)
        completed_sales = sum((row.total for row in Order.query.filter(
            Order.status.in_(["completed", "delivered"])).all()), start=0)
        return jsonify({"products": len(products), "customers": User.query.filter_by(role="customer").count(),
                        "staff": User.query.filter_by(role="staff").count(), "suppliers": Supplier.query.count(),
                        "categories": Category.query.count(),
                        "inventoryUnits": sum(row.stock for row in products),
                        "inventoryValue": float(inventory_value), "salesTotal": float(completed_sales),
                        "orders": Order.query.count(), "pending": Order.query.filter_by(status="pending").count(),
                        "completed": Order.query.filter_by(status="completed").count(),
                        "cancelled": Order.query.filter_by(status="cancelled").count(),
                        "lowStock": sum(1 for row in products if 0 < row.stock <= row.low_stock_threshold),
                        "outOfStock": sum(1 for row in products if row.stock == 0)})

    @app.get("/api/dashboard")
    def dashboard():
        user, failure = token_user({"staff", "admin"})
        if failure:
            return failure
        product_query = Product.query.filter_by(status="active")
        products = product_query.all()
        recent_orders = Order.query.order_by(Order.created_at.desc()).limit(8).all()
        low_stock = [row for row in products if row.stock <= row.low_stock_threshold]
        inventory_value = sum((row.price * row.stock for row in products), start=0)
        completed_sales = sum((row.total for row in Order.query.filter(Order.status.in_(["completed", "delivered"])).all()), start=0)
        return jsonify({
            "products": len(products), "customers": User.query.filter_by(role="customer").count(),
            "staff": User.query.filter_by(role="staff").count(),
            "suppliers": Supplier.query.count(), "categories": Category.query.count(),
            "orders": Order.query.count(), "inventoryUnits": sum(row.stock for row in products),
            "inventoryValue": float(inventory_value),
            "salesTotal": float(completed_sales), "pending": Order.query.filter_by(status="pending").count(),
            "lowStock": [product_json(row) for row in low_stock],
            "recentOrders": [order_json(row) for row in recent_orders],
        })

    def filtered_orders():
        query = Order.query.join(User, Order.user_id == User.id)
        start_date = request.args.get("from")
        end_date = request.args.get("to")
        search = request.args.get("q", "").strip()
        try:
            if start_date:
                start = datetime.combine(datetime.fromisoformat(start_date).date(), time.min, tzinfo=timezone.utc)
                query = query.filter(Order.created_at >= start)
            if end_date:
                end = datetime.combine(datetime.fromisoformat(end_date).date() + timedelta(days=1), time.min, tzinfo=timezone.utc)
                query = query.filter(Order.created_at < end)
        except ValueError:
            raise BusinessError("Dates must use YYYY-MM-DD format.")
        if search:
            query = query.filter(Order.number.ilike(f"%{search}%") | User.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%"))
        return query.order_by(Order.created_at.desc())

    @app.get("/api/reports")
    def reports():
        user, failure = token_user({"staff", "admin"})
        if failure:
            return failure
        try:
            report_orders = filtered_orders().all()
        except BusinessError as exc:
            return error(str(exc))
        movements_query = InventoryMovement.query.order_by(InventoryMovement.created_at.desc())
        try:
            if request.args.get("from"):
                start = datetime.combine(datetime.fromisoformat(request.args["from"]).date(), time.min, tzinfo=timezone.utc)
                movements_query = movements_query.filter(InventoryMovement.created_at >= start)
            if request.args.get("to"):
                end = datetime.combine(datetime.fromisoformat(request.args["to"]).date() + timedelta(days=1), time.min, tzinfo=timezone.utc)
                movements_query = movements_query.filter(InventoryMovement.created_at < end)
        except ValueError:
            return error("Dates must use YYYY-MM-DD format.")
        sales = sum((row.total for row in report_orders if row.status in {"completed", "delivered"}), start=0)
        return jsonify({"orders": [order_json(row) for row in report_orders],
                        "orderCount": len(report_orders), "salesTotal": float(sales),
                        "movements": [{"product": row.product.name, "sku": row.product.sku,
                                       "action": row.action, "quantity": row.quantity,
                                       "user": row.user.name if row.user else "System",
                                       "createdAt": row.created_at.isoformat()}
                                      for row in movements_query.limit(500).all()]})

    @app.get("/api/reports/orders.csv")
    def export_orders_csv():
        user, failure = token_user({"staff", "admin"})
        if failure:
            return failure
        try:
            report_orders = filtered_orders().all()
        except BusinessError as exc:
            return error(str(exc))
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Order", "Customer", "Email", "Status", "Subtotal", "Discount", "Total", "Created"])
        for row in report_orders:
            writer.writerow([row.number, row.user.name, row.user.email, row.status,
                             row.subtotal, row.discount, row.total, row.created_at.isoformat()])
        return Response(output.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=stockflow-orders.csv"})

    @app.route("/api/admin/users", methods=["GET", "POST"])
    def admin_users():
        user, failure = token_user({"admin"})
        if failure:
            return failure
        if request.method == "POST":
            data = payload()
            name = str(data.get("name", "")).strip()
            email = str(data.get("email", "")).strip().lower()
            phone = str(data.get("phone", "")).strip()
            password = str(data.get("password", ""))
            role = data.get("role", "staff")
            active = data.get("active", True)
            if len(name) < 2 or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is None:
                return error("Enter a valid name and email.")
            if User.query.filter_by(email=email).first():
                return error("An account with that email already exists.", 409)
            if (re.fullmatch(r"[+()0-9.\s-]{7,30}", phone) is None
                    or len(password) < 8 or role not in {"staff", "admin", "customer"}
                    or type(active) is not bool):
                return error("Provide a valid phone, password of at least 8 characters, and role.")
            account = User(name=name, email=email, phone=phone, role=role,
                           password_hash=generate_password_hash(password), active=active)
            db.session.add(account)
            db.session.commit()
            return jsonify({"user": user_json(account)}), 201
        return jsonify({"users": [user_json(row) for row in User.query.order_by(User.name).all()]})

    @app.patch("/api/admin/users/<int:user_id>")
    def admin_update_user(user_id):
        user, failure = token_user({"admin"})
        if failure:
            return failure
        target = db.session.get(User, user_id)
        if target is None or target.id == user.id:
            return error("User not found or cannot be changed.", 404)
        data = payload()
        name = str(data.get("name", target.name)).strip()
        email = str(data.get("email", target.email)).strip().lower()
        phone = str(data.get("phone", target.phone)).strip()
        if len(name) < 2 or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is None:
            return error("Enter a valid name and email.")
        if User.query.filter(User.email == email, User.id != target.id).first():
            return error("An account with that email already exists.", 409)
        if re.fullmatch(r"[+()0-9.\s-]{7,30}", phone) is None:
            return error("Enter a valid phone number.")
        if "password" in data:
            password = str(data["password"])
            if len(password) < 8:
                return error("Password must be at least 8 characters.")
            target.password_hash = generate_password_hash(password)
        target.name, target.email, target.phone = name, email, phone
        if "active" in data and type(data["active"]) is bool:
            target.active = data["active"]
        if data.get("role") in {"customer", "staff", "admin"}:
            target.role = data["role"]
        db.session.commit()
        return jsonify({"user": user_json(target)})

    @app.errorhandler(BusinessError)
    def business_error(exc):
        db.session.rollback()
        return error(str(exc), 409)

    return app