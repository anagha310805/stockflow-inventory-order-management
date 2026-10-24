from decimal import Decimal

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from backend import create_app
from backend.models import CartItem, Category, InventoryMovement, Order, Product, Supplier, User, db
from backend.services import BusinessError, place_order, transition_order


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret",
                      "SQLALCHEMY_DATABASE_URI": "sqlite://", "CORS_ORIGINS": ["*"]})
    with app.app_context():
        db.create_all()
        user = User(name="Customer One", email="customer@example.test", phone="5550100",
                    password_hash="hash", role="customer")
        category = Category(name="Accessories")
        db.session.add_all([user, category])
        db.session.flush()
        product = Product(sku="KB-01", name="Keyboard", price=Decimal("1499.00"),
                          stock=5, category_id=category.id)
        db.session.add(product)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


def test_order_deducts_stock_and_cancel_restores_once(app):
    with app.app_context():
        user, product = User.query.one(), Product.query.one()
        db.session.add(CartItem(user_id=user.id, product_id=product.id, quantity=3))
        db.session.commit()
        order = place_order(user.id)
        db.session.refresh(product)
        assert product.stock == 2
        assert order.subtotal == Decimal("4497.00")
        assert order.discount == Decimal("200.00")
        assert order.total == Decimal("4297.00")
        assert InventoryMovement.query.count() == 1
        transition_order(order, "cancelled", user.id)
        db.session.refresh(product)
        assert product.stock == 5
        assert InventoryMovement.query.count() == 2
        with pytest.raises(BusinessError, match="Cannot move"):
            transition_order(order, "cancelled", user.id)
        db.session.refresh(product)
        assert product.stock == 5
        assert InventoryMovement.query.count() == 2


def test_order_rejects_short_stock_without_partial_changes(app):
    with app.app_context():
        user, product = User.query.one(), Product.query.one()
        db.session.add(CartItem(user_id=user.id, product_id=product.id, quantity=6))
        db.session.commit()
        with pytest.raises(BusinessError, match="Not enough stock"):
            place_order(user.id)
        db.session.refresh(product)
        assert product.stock == 5
        assert Order.query.count() == 0
        assert InventoryMovement.query.count() == 0


def test_discount_applies_at_five_thousand_subtotal(app):
    with app.app_context():
        user, product = User.query.one(), Product.query.one()
        product.price = Decimal("5000.00")
        db.session.add(CartItem(user_id=user.id, product_id=product.id, quantity=1))
        db.session.commit()

        order = place_order(user.id)
        assert order.subtotal == Decimal("5000.00")
        assert order.discount == Decimal("250.00")
        assert order.total == Decimal("4750.00")


def test_registration_is_customer_only_and_customer_cannot_adjust_stock(app):
    with app.app_context():
        client = app.test_client()
        registered = client.post("/api/auth/register", json={
            "name": "New Customer", "email": "new@example.test",
            "phone": "555 0101", "password": "valid-pass-123",
        })
        assert registered.status_code == 201
        data = registered.get_json()
        assert data["user"]["role"] == "customer"
        headers = {"Authorization": f"Bearer {data['token']}"}
        duplicate = client.post("/api/auth/register", json={
            "name": "New Customer", "email": "NEW@example.test",
            "phone": "555 0101", "password": "valid-pass-123",
        })
        assert duplicate.status_code == 409
        product_id = Product.query.one().id
        denied = client.post(f"/api/inventory/{product_id}", headers=headers,
                             json={"action": "addition", "quantity": 4})
        assert denied.status_code == 403


def test_login_hashing_and_role_boundaries(app):
    with app.app_context():
        staff = User(name="Store Staff", email="staff@example.test", phone="5550200",
                     password_hash=generate_password_hash("staff-password-123"), role="staff")
        admin = User(name="Store Admin", email="admin@example.test", phone="5550300",
                     password_hash=generate_password_hash("admin-password-123"), role="admin")
        db.session.add_all([staff, admin])
        db.session.commit()
        assert check_password_hash(staff.password_hash, "staff-password-123")

    client = app.test_client()
    staff_login = client.post("/api/auth/login", json={
        "email": "staff@example.test", "password": "staff-password-123",
    })
    assert staff_login.status_code == 200
    assert staff_login.get_json()["user"]["role"] == "staff"
    staff_headers = {"Authorization": f"Bearer {staff_login.get_json()['token']}"}
    assert client.get("/api/inventory/movements", headers=staff_headers).status_code == 200
    assert client.get("/api/admin/overview", headers=staff_headers).status_code == 403
    assert client.post("/api/auth/login", json={
        "email": "staff@example.test", "password": "wrong-password",
    }).status_code == 401

    admin_login = client.post("/api/auth/login", json={
        "email": "admin@example.test", "password": "admin-password-123",
    })
    admin_headers = {"Authorization": f"Bearer {admin_login.get_json()['token']}"}
    assert client.get("/api/admin/overview", headers=admin_headers).status_code == 200


def test_admin_staff_customer_api_permission_matrix(app):
    with app.app_context():
        staff = User(name="Permission Staff", email="permission-staff@example.test", phone="5550801",
                     password_hash=generate_password_hash("permission-password-123"), role="staff")
        admin = User(name="Permission Admin", email="permission-admin@example.test", phone="5550802",
                     password_hash=generate_password_hash("permission-password-123"), role="admin")
        db.session.add_all([staff, admin])
        db.session.commit()
    client = app.test_client()

    def headers_for(email):
        response = client.post("/api/auth/login", json={
            "email": email, "password": "permission-password-123",
        })
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.get_json()['token']}"}

    customer_login = client.post("/api/auth/register", json={
        "name": "Permission Customer", "email": "permission-customer@example.test",
        "phone": "555 0803", "password": "permission-password-123",
    })
    customer_headers = {"Authorization": f"Bearer {customer_login.get_json()['token']}"}
    staff_headers = headers_for("permission-staff@example.test")
    admin_headers = headers_for("permission-admin@example.test")

    staff_routes = ["/api/dashboard", "/api/products/manage", "/api/customers",
                    "/api/inventory/movements", "/api/reports"]
    admin_routes = ["/api/admin/overview", "/api/admin/users"]
    for route in staff_routes:
        assert client.get(route, headers=customer_headers).status_code == 403, route
        assert client.get(route, headers=staff_headers).status_code == 200, route
        assert client.get(route, headers=admin_headers).status_code == 200, route
    assert client.get("/api/orders", headers=customer_headers).status_code == 200
    assert client.get("/api/orders", headers=staff_headers).status_code == 200
    assert client.get("/api/orders", headers=admin_headers).status_code == 200
    for route in admin_routes:
        assert client.get(route, headers=customer_headers).status_code == 403, route
        assert client.get(route, headers=staff_headers).status_code == 403, route
        assert client.get(route, headers=admin_headers).status_code == 200, route
    assert client.get("/api/orders", headers={"Authorization": "Bearer invalid-token"}).status_code == 401
    customer_id = customer_login.get_json()["user"]["id"]
    assert client.get("/api/customers", headers=staff_headers).status_code == 200
    assert client.post("/api/customers", headers=staff_headers, json={}).status_code == 403
    assert client.patch(f"/api/customers/{customer_id}", headers=staff_headers,
                        json={"name": "Attempted Update"}).status_code == 403
    assert client.delete(f"/api/customers/{customer_id}", headers=staff_headers).status_code == 403
    app.config["TOKEN_MAX_AGE"] = -1
    assert client.get("/api/orders", headers=customer_headers).status_code == 401


def test_inactive_accounts_cannot_login_and_checkout_uses_database_price(app):
    client = app.test_client()
    registered = client.post("/api/auth/register", json={
        "name": "Checkout Customer", "email": "checkout@example.test",
        "phone": "555 0102", "password": "checkout-pass-123",
    })
    token = registered.get_json()["token"]
    user_id = registered.get_json()["user"]["id"]
    with app.app_context():
        product = Product.query.one()
        db.session.add(CartItem(user_id=user_id, product_id=product.id, quantity=2))
        account = db.session.get(User, user_id)
        account.active = False
        db.session.commit()
        assert check_password_hash(account.password_hash, "checkout-pass-123")

    assert client.post("/api/auth/login", json={
        "email": "checkout@example.test", "password": "checkout-pass-123",
    }).status_code == 401

    with app.app_context():
        account = db.session.get(User, user_id)
        account.active = True
        db.session.commit()
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/orders", headers=headers,
                           json={"price": 0, "quantity": 999, "total": 0})
    assert response.status_code == 201
    result = response.get_json()["order"]
    assert result["items"][0]["quantity"] == 2
    assert result["items"][0]["unitPrice"] == 1499.0
    assert result["total"] == 2998.0


def test_invalid_status_transition_does_not_change_stock_or_order(app):
    with app.app_context():
        user, product = User.query.one(), Product.query.one()
        db.session.add(CartItem(user_id=user.id, product_id=product.id, quantity=1))
        db.session.commit()
        order = place_order(user.id)
        with pytest.raises(BusinessError, match="Cannot move"):
            transition_order(order, "completed", user.id)
        db.session.refresh(product)
        db.session.refresh(order)
        assert product.stock == 4
        assert order.status == "pending"


def test_staff_can_create_customer_order_with_multiple_products(app):
    with app.app_context():
        staff = User(name="Store Staff", email="ops@example.test", phone="5550200",
                     password_hash=generate_password_hash("staff-password-123"), role="staff")
        second = Product(sku="MS-02", name="Mouse", price=Decimal("799.00"), stock=4)
        db.session.add_all([staff, second])
        db.session.commit()

    client = app.test_client()
    login = client.post("/api/auth/login", json={"email": "ops@example.test", "password": "staff-password-123"})
    headers = {"Authorization": f"Bearer {login.get_json()['token']}"}
    customer_id = User.query.filter_by(email="customer@example.test").first().id
    response = client.post("/api/orders", headers=headers, json={
        "customerId": customer_id,
        "items": [{"productId": 1, "quantity": 2}, {"productId": 2, "quantity": 1}],
    })
    assert response.status_code == 201
    result = response.get_json()["order"]
    assert result["customer"]["id"] == customer_id
    assert result["subtotal"] == 3797.0
    assert len(result["items"]) == 2
    with app.app_context():
        assert Product.query.filter_by(sku="KB-01").one().stock == 3
        assert Product.query.filter_by(sku="MS-02").one().stock == 3
        movement = InventoryMovement.query.order_by(InventoryMovement.id).first()
        assert movement.user_id == User.query.filter_by(email="ops@example.test").one().id


def test_dashboard_reports_and_csv_use_database_records(app):
    with app.app_context():
        admin = User(name="Store Admin", email="report-admin@example.test", phone="5550300",
                     password_hash=generate_password_hash("admin-password-123"), role="admin")
        db.session.add(admin)
        user, product = User.query.filter_by(role="customer").one(), Product.query.one()
        db.session.add(CartItem(user_id=user.id, product_id=product.id, quantity=2))
        db.session.commit()

    client = app.test_client()
    login = client.post("/api/auth/login", json={"email": "report-admin@example.test", "password": "admin-password-123"})
    headers = {"Authorization": f"Bearer {login.get_json()['token']}"}
    dashboard = client.get("/api/dashboard", headers=headers).get_json()
    assert dashboard["products"] == 1
    assert dashboard["customers"] == 1
    assert dashboard["staff"] == 0
    assert dashboard["categories"] == 1
    assert dashboard["inventoryUnits"] == 5
    assert dashboard["inventoryValue"] == 7495.0
    assert len(dashboard["recentOrders"]) == 0

    with app.app_context():
        user = User.query.filter_by(role="customer").one()
        user.password_hash = generate_password_hash("customer-password-123")
        db.session.commit()
    customer_login = client.post("/api/auth/login", json={"email": "customer@example.test", "password": "customer-password-123"})
    assert customer_login.status_code == 200, customer_login.get_json()
    customer_headers = {"Authorization": f"Bearer {customer_login.get_json()['token']}"}
    order = client.post("/api/orders", headers=customer_headers, json={}).get_json()["order"]
    with app.app_context():
        db.session.get(Order, order["id"]).status = "completed"
        db.session.commit()
    reports = client.get("/api/reports?from=2020-01-01&to=2099-12-31&q=customer@example.test", headers=headers)
    assert reports.status_code == 200
    assert reports.get_json()["orderCount"] == 1
    assert reports.get_json()["salesTotal"] == 2998.0
    exported = client.get("/api/reports/orders.csv?from=2020-01-01", headers=headers)
    assert exported.status_code == 200
    assert "text/csv" in exported.content_type
    assert order["number"] in exported.text


def test_customer_crud_and_secure_password_change(app):
    with app.app_context():
        admin = User(name="Customer Desk", email="desk@example.test", phone="5550400",
                     password_hash=generate_password_hash("desk-password-123"), role="admin")
        db.session.add(admin)
        db.session.commit()
    client = app.test_client()
    staff_login = client.post("/api/auth/login", json={"email": "desk@example.test", "password": "desk-password-123"})
    staff_headers = {"Authorization": f"Bearer {staff_login.get_json()['token']}"}
    created = client.post("/api/customers", headers=staff_headers, json={
        "name": "Managed Customer", "email": "managed@example.test",
        "phone": "555 0401", "password": "temporary-password-123",
    })
    assert created.status_code == 201
    customer_id = created.get_json()["customer"]["id"]
    assert client.get("/api/customers", headers=staff_headers).status_code == 200
    updated = client.patch(f"/api/customers/{customer_id}", headers=staff_headers, json={
        "name": "Updated Customer", "phone": "555 0402",
    })
    assert updated.get_json()["customer"]["name"] == "Updated Customer"
    searched = client.get("/api/customers?q=Updated", headers=staff_headers).get_json()["customers"]
    assert [row["id"] for row in searched] == [customer_id]

    customer_login = client.post("/api/auth/login", json={
        "email": "managed@example.test", "password": "temporary-password-123",
    })
    assert customer_login.status_code == 200
    customer_headers = {"Authorization": f"Bearer {customer_login.get_json()['token']}"}
    changed = client.patch("/api/profile/password", headers=customer_headers, json={
        "currentPassword": "temporary-password-123", "newPassword": "changed-password-123",
    })
    assert changed.status_code == 200
    assert client.post("/api/auth/login", json={
        "email": "managed@example.test", "password": "temporary-password-123",
    }).status_code == 401
    assert client.post("/api/auth/login", json={
        "email": "managed@example.test", "password": "changed-password-123",
    }).status_code == 200
    assert client.delete(f"/api/customers/{customer_id}", headers=staff_headers).status_code == 200


def test_product_filters_and_invalid_quantities(app):
    with app.app_context():
        category = Category.query.one()
        supplier = Supplier(name="Filter Supplier")
        db.session.add(supplier)
        db.session.flush()
        target = Product.query.one()
        target.supplier_id = supplier.id
        db.session.commit()
        category_id, supplier_id = category.id, supplier.id
        staff = User(name="Catalog Staff", email="catalog@example.test", phone="5550500",
                     password_hash=generate_password_hash("catalog-password-123"), role="staff")
        db.session.add(staff)
        db.session.commit()
    client = app.test_client()
    filtered = client.get(f"/api/products?category={category_id}&supplier={supplier_id}&min=1000&max=2000")
    assert filtered.status_code == 200
    assert [row["sku"] for row in filtered.get_json()["products"]] == ["KB-01"]
    login = client.post("/api/auth/login", json={"email": "catalog@example.test", "password": "catalog-password-123"})
    headers = {"Authorization": f"Bearer {login.get_json()['token']}"}
    invalid = client.post("/api/products/manage", headers=headers, json={
        "name": "Bad Quantity", "sku": "BAD-01", "price": 10, "stock": 1.5,
    })
    assert invalid.status_code == 400
    assert client.get("/api/products/manage?status=all", headers=headers).status_code == 200


def test_product_crud_and_inventory_movements(app):
    with app.app_context():
        staff = User(name="Inventory Staff", email="inventory@example.test", phone="5550600",
                     password_hash=generate_password_hash("inventory-password-123"), role="staff")
        category_id = Category.query.one().id
        supplier = Supplier(name="Inventory Supplier")
        db.session.add_all([staff, supplier])
        db.session.commit()
        supplier_id = supplier.id
    client = app.test_client()
    login = client.post("/api/auth/login", json={"email": "inventory@example.test", "password": "inventory-password-123"})
    headers = {"Authorization": f"Bearer {login.get_json()['token']}"}
    created = client.post("/api/products/manage", headers=headers, json={
        "name": "Docking Station", "sku": "DOC-01", "price": 12500,
        "stock": 4, "threshold": 2, "categoryId": category_id, "supplierId": supplier_id,
    })
    assert created.status_code == 200
    product = created.get_json()["product"]
    assert product["stock"] == 4
    product_id = product["id"]
    updated = client.patch("/api/products/manage", headers=headers, json={
        "id": product_id, "name": "USB-C Dock", "sku": "DOC-01", "price": 12999,
        "threshold": 3, "categoryId": category_id, "supplierId": supplier_id,
    })
    assert updated.get_json()["product"]["name"] == "USB-C Dock"
    assert updated.get_json()["product"]["stock"] == 4

    added = client.post(f"/api/inventory/{product_id}", headers=headers,
                        json={"action": "addition", "quantity": 3})
    assert added.get_json()["product"]["stock"] == 7
    history = client.get("/api/inventory/movements", headers=headers).get_json()["movements"]
    assert history[0]["quantity"] == 3
    assert history[0]["user"] == "Inventory Staff"
    reduced = client.post(f"/api/inventory/{product_id}", headers=headers,
                          json={"action": "reduction", "quantity": 2})
    assert reduced.get_json()["product"]["stock"] == 5
    rejected = client.post(f"/api/inventory/{product_id}", headers=headers,
                           json={"action": "reduction", "quantity": 6})
    assert rejected.status_code == 409
    assert client.delete(f"/api/products/manage?id={product_id}", headers=headers).status_code == 200
    archived = client.get("/api/products/manage?status=all&q=DOC-01", headers=headers).get_json()["products"]
    assert archived[0]["status"] == "inactive"
    with app.app_context():
        product = db.session.get(Product, product_id)
        assert product.stock == 5
        assert InventoryMovement.query.filter_by(product_id=product_id).count() == 3


def test_customer_cart_checkout_order_isolation_and_cancellation(app):
    client = app.test_client()
    credentials = [
        {"name": "Shopper One", "email": "shopper-one@example.test", "phone": "555 0701", "password": "shopper-password-123"},
        {"name": "Shopper Two", "email": "shopper-two@example.test", "phone": "555 0702", "password": "shopper-password-123"},
    ]
    tokens = []
    ids = []
    for data in credentials:
        response = client.post("/api/auth/register", json=data)
        assert response.status_code == 201
        tokens.append(response.get_json()["token"])
        ids.append(response.get_json()["user"]["id"])
    first_headers = {"Authorization": f"Bearer {tokens[0]}"}
    second_headers = {"Authorization": f"Bearer {tokens[1]}"}
    profile = client.patch("/api/profile", headers=first_headers, json={
        "name": "Shopper One Updated", "phone": "555 0711",
    })
    assert profile.status_code == 200
    assert profile.get_json()["user"]["name"] == "Shopper One Updated"
    with app.app_context():
        assert db.session.get(User, ids[0]).phone == "555 0711"

    detail = client.get("/api/products/1")
    assert detail.status_code == 200
    assert detail.get_json()["product"]["sku"] == "KB-01"
    assert client.post("/api/cart", headers=first_headers, json={"productId": 1, "quantity": 2}).status_code == 200
    assert client.get("/api/cart", headers=second_headers).get_json()["items"] == []
    assert client.get("/api/cart", headers=first_headers).get_json()["items"][0]["quantity"] == 2
    assert client.patch("/api/cart", headers=first_headers, json={"productId": 1, "quantity": 3}).status_code == 200
    assert client.patch("/api/cart", headers=first_headers, json={"productId": 1, "quantity": 6}).status_code == 400
    assert client.delete("/api/cart?productId=1", headers=first_headers).status_code == 200
    assert client.get("/api/cart", headers=first_headers).get_json()["items"] == []
    assert client.post("/api/cart", headers=first_headers, json={"productId": 1, "quantity": 2}).status_code == 200

    with app.app_context():
        product = db.session.get(Product, 1)
        product.stock = 1
        db.session.commit()
    failed_order = client.post("/api/orders", headers=first_headers, json={})
    assert failed_order.status_code == 409
    assert len(client.get("/api/cart", headers=first_headers).get_json()["items"]) == 1
    with app.app_context():
        product = db.session.get(Product, 1)
        assert product.stock == 1
        product.stock = 5
        db.session.commit()

    placed = client.post("/api/orders", headers=first_headers,
                         json={"price": 0, "quantity": 999, "total": 0})
    assert placed.status_code == 201
    order = placed.get_json()["order"]
    assert order["items"][0]["quantity"] == 2
    assert order["items"][0]["unitPrice"] == 1499.0
    assert client.get("/api/cart", headers=first_headers).get_json()["items"] == []
    assert len(client.get("/api/orders", headers=first_headers).get_json()["orders"]) == 1
    assert client.get("/api/orders", headers=second_headers).get_json()["orders"] == []
    assert client.patch(f"/api/orders/{order['id']}/status", headers=second_headers,
                        json={"status": "cancelled"}).status_code == 403
    cancelled = client.patch(f"/api/orders/{order['id']}/status", headers=first_headers,
                             json={"status": "cancelled"})
    assert cancelled.status_code == 200
    assert cancelled.get_json()["order"]["status"] == "cancelled"
    assert client.patch(f"/api/orders/{order['id']}/status", headers=first_headers,
                        json={"status": "cancelled"}).status_code == 409
    with app.app_context():
        assert db.session.get(Product, 1).stock == 5

    with app.app_context():
        db.session.get(Order, order["id"]).status = "shipped"
        db.session.commit()
    shipped_cancel = client.patch(f"/api/orders/{order['id']}/status", headers=first_headers,
                                  json={"status": "cancelled"})
    assert shipped_cancel.status_code == 409
    with app.app_context():
        assert db.session.get(Product, 1).stock == 5
        account = db.session.get(User, ids[0])
        assert check_password_hash(account.password_hash, credentials[0]["password"])


def test_admin_staff_account_lifecycle_and_self_lockout_protection(app):
    with app.app_context():
        admin = User(name="Account Admin", email="account-admin@example.test", phone="5550901",
                     password_hash=generate_password_hash("admin-password-123"), role="admin")
        staff = User(name="Existing Staff", email="existing-staff@example.test", phone="5550902",
                     password_hash=generate_password_hash("staff-password-123"), role="staff")
        db.session.add_all([admin, staff])
        db.session.commit()
        admin_id, staff_id = admin.id, staff.id
    client = app.test_client()
    admin_login = client.post("/api/auth/login", json={
        "email": "account-admin@example.test", "password": "admin-password-123",
    })
    admin_headers = {"Authorization": f"Bearer {admin_login.get_json()['token']}"}
    staff_login = client.post("/api/auth/login", json={
        "email": "existing-staff@example.test", "password": "staff-password-123",
    })
    staff_headers = {"Authorization": f"Bearer {staff_login.get_json()['token']}"}

    denied = client.post("/api/admin/users", headers=staff_headers, json={
        "name": "New Staff", "email": "new-staff@example.test", "phone": "555 0903",
        "password": "new-staff-password", "role": "staff",
    })
    assert denied.status_code == 403
    created = client.post("/api/admin/users", headers=admin_headers, json={
        "name": "New Staff", "email": "new-staff@example.test", "phone": "555 0903",
        "password": "new-staff-password", "role": "staff", "active": False,
    })
    assert created.status_code == 201
    new_id = created.get_json()["user"]["id"]
    assert created.get_json()["user"]["role"] == "staff"
    assert created.get_json()["user"]["active"] is False
    assert client.post("/api/auth/login", json={
        "email": "new-staff@example.test", "password": "new-staff-password",
    }).status_code == 401

    self_deactivate = client.patch(f"/api/admin/users/{admin_id}", headers=admin_headers,
                                   json={"active": False})
    assert self_deactivate.status_code == 404
    updated = client.patch(f"/api/admin/users/{new_id}", headers=admin_headers, json={
        "name": "Updated Staff", "active": False, "password": "updated-staff-password",
    })
    assert updated.status_code == 200
    assert updated.get_json()["user"]["name"] == "Updated Staff"
    assert updated.get_json()["user"]["active"] is False
    assert client.post("/api/auth/login", json={
        "email": "new-staff@example.test", "password": "updated-staff-password",
    }).status_code == 401
    assert client.patch(f"/api/admin/users/{new_id}", headers=admin_headers,
                        json={"active": True}).status_code == 200
    reactivated = client.post("/api/auth/login", json={
        "email": "new-staff@example.test", "password": "updated-staff-password",
    })
    assert reactivated.status_code == 200
    with app.app_context():
        account = db.session.get(User, new_id)
        assert check_password_hash(account.password_hash, "updated-staff-password")
        assert account.role == "staff"
        assert db.session.get(User, staff_id).active is True


def test_category_supplier_crud_preserves_product_relationships(app):
    with app.app_context():
        staff = User(name="Catalog Admin", email="catalog-admin@example.test", phone="5551001",
                     password_hash=generate_password_hash("catalog-password-123"), role="admin")
        db.session.add(staff)
        db.session.commit()
    client = app.test_client()
    login = client.post("/api/auth/login", json={
        "email": "catalog-admin@example.test", "password": "catalog-password-123",
    })
    headers = {"Authorization": f"Bearer {login.get_json()['token']}"}

    category = client.post("/api/categories/manage", headers=headers,
                           json={"name": "Peripherals", "description": "Input devices"})
    assert category.status_code == 200
    category_id = category.get_json()["category"]["id"]
    supplier = client.post("/api/suppliers/manage", headers=headers, json={
        "name": "Circuit House", "contactPerson": "Sam Lee",
        "email": "sam@example.test", "phone": "555 1002", "address": "Unit 4",
    })
    assert supplier.status_code == 200
    supplier_id = supplier.get_json()["supplier"]["id"]
    assert len(client.get("/api/categories?q=Periph").get_json()["categories"]) == 1
    assert len(client.get("/api/suppliers/manage?q=Sam", headers=headers).get_json()["suppliers"]) == 1

    product = client.post("/api/products/manage", headers=headers, json={
        "name": "Trackball", "sku": "TRK-01", "price": 2500,
        "stock": 4, "threshold": 1, "categoryId": category_id, "supplierId": supplier_id,
    })
    assert product.status_code == 200
    product_id = product.get_json()["product"]["id"]
    assert client.delete(f"/api/categories/manage?id={category_id}", headers=headers).status_code == 409
    assert client.delete(f"/api/suppliers/manage?id={supplier_id}", headers=headers).status_code == 409

    assert client.patch("/api/categories/manage", headers=headers,
                        json={"id": category_id, "name": "Pointing Devices"}).status_code == 200
    updated_supplier = client.patch("/api/suppliers/manage", headers=headers, json={
        "id": supplier_id, "name": "Circuit House West", "contactPerson": "Alex Kim",
        "email": "alex@example.test", "phone": "555 1003", "address": "Unit 8",
    })
    assert updated_supplier.status_code == 200
    detail = client.get(f"/api/products/{product_id}").get_json()["product"]
    assert detail["category"] == "Pointing Devices"
    assert detail["supplier"] == "Circuit House West"

def test_exact_pdf_assessment_discount_example(app):
    with app.app_context():
        user = User.query.first()
        category = Category.query.first()
        keyboard = Product.query.filter_by(sku='KB-01').first()
        mouse = Product(sku='MS-01', name='Wireless Mouse', price=Decimal('799.00'),
                        stock=10, category_id=category.id)
        db.session.add(mouse)
        db.session.commit()

        db.session.add_all([
            CartItem(user_id=user.id, product_id=keyboard.id, quantity=2),
            CartItem(user_id=user.id, product_id=mouse.id, quantity=1),
        ])
        db.session.commit()

        order = place_order(user.id)
        assert order.subtotal == Decimal('3797.00')
        assert order.discount == Decimal('200.00')
        assert order.total == Decimal('3597.00')


def test_discount_boundary_values(app):
    from backend.services import calculate_discount
    assert calculate_discount(Decimal('0.00')) == Decimal('0.00')
    assert calculate_discount(Decimal('3499.99')) == Decimal('0.00')
    assert calculate_discount(Decimal('3500.00')) == Decimal('200.00')
    assert calculate_discount(Decimal('3797.00')) == Decimal('200.00')
    assert calculate_discount(Decimal('4999.99')) == Decimal('200.00')
    assert calculate_discount(Decimal('5000.00')) == Decimal('250.00')
    assert calculate_discount(Decimal('10000.00')) == Decimal('500.00')


def test_order_workflow_to_completed_terminal_state(app):
    with app.app_context():
        user, product = User.query.one(), Product.query.filter_by(sku='KB-01').one()
        db.session.add(CartItem(user_id=user.id, product_id=product.id, quantity=1))
        db.session.commit()
        order = place_order(user.id)
        assert order.status == 'pending'

        transition_order(order, 'confirmed', user.id)
        assert order.status == 'confirmed'

        transition_order(order, 'processing', user.id)
        assert order.status == 'processing'

        transition_order(order, 'ready', user.id)
        assert order.status == 'ready'

        transition_order(order, 'completed', user.id)
        assert order.status == 'completed'

        with pytest.raises(BusinessError, match='Cannot move'):
            transition_order(order, 'cancelled', user.id)


def test_product_status_filter_catalog(app):
    with app.app_context():
        category = Category.query.first()
        archived_prod = Product(sku='OLD-01', name='Old Archived Cable', price=Decimal('199.00'),
                                stock=10, category_id=category.id, status='inactive')
        db.session.add(archived_prod)
        db.session.commit()

    client = app.test_client()
    res = client.get('/api/products')
    assert res.status_code == 200
    skus = [p['sku'] for p in res.get_json()['products']]
    assert 'KB-01' in skus
    assert 'OLD-01' not in skus

    res_inactive = client.get('/api/products?status=inactive')
    skus_inactive = [p['sku'] for p in res_inactive.get_json()['products']]
    assert 'OLD-01' in skus_inactive
    assert 'KB-01' not in skus_inactive

    res_all = client.get('/api/products?status=all')
    skus_all = [p['sku'] for p in res_all.get_json()['products']]
    assert 'KB-01' in skus_all
    assert 'OLD-01' in skus_all


def test_supplier_supplied_products_count_and_list(app):
    with app.app_context():
        admin = User(name='Supply Admin', email='supply-admin@example.test', phone='5550888',
                     password_hash=generate_password_hash('supply-pass-123'), role='admin')
        category = Category.query.first()
        supplier = Supplier(name='Prime Logistics', contact_person='Dana Vance',
                            email='dana@prime.test', phone='5550999', address='Tech Park 1')
        db.session.add_all([admin, supplier])
        db.session.flush()
        p1 = Product(sku='PR-01', name='Product One', price=Decimal('500.00'),
                     stock=10, category_id=category.id, supplier_id=supplier.id)
        p2 = Product(sku='PR-02', name='Product Two', price=Decimal('750.00'),
                     stock=15, category_id=category.id, supplier_id=supplier.id)
        db.session.add_all([p1, p2])
        db.session.commit()

    client = app.test_client()
    login = client.post('/api/auth/login', json={
        'email': 'supply-admin@example.test', 'password': 'supply-pass-123'
    })
    headers = {'Authorization': f"Bearer {login.get_json()['token']}"}

    res = client.get('/api/suppliers/manage', headers=headers)
    assert res.status_code == 200
    supp_list = res.get_json()['suppliers']
    prime = next(s for s in supp_list if s['name'] == 'Prime Logistics')
    assert prime['productCount'] == 2
    assert len(prime['products']) == 2
    assert {p['sku'] for p in prime['products']} == {'PR-01', 'PR-02'}
