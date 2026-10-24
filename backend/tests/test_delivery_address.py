from decimal import Decimal
import pytest
from werkzeug.security import generate_password_hash

from backend import create_app
from backend.models import CartItem, Category, Order, Product, User, db
from backend.services import BusinessError, place_order, validate_indian_delivery_address


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "CORS_ORIGINS": ["*"]
    })
    with app.app_context():
        db.create_all()
        admin = User(name="Store Admin", email="admin@test.local", phone="9876543210",
                     password_hash=generate_password_hash("admin-pass"), role="admin")
        staff = User(name="Warehouse Staff", email="staff@test.local", phone="9876543211",
                     password_hash=generate_password_hash("staff-pass"), role="staff")
        cust1 = User(name="Rajesh Kumar", email="rajesh@test.local", phone="9876543212",
                     password_hash=generate_password_hash("cust-pass"), role="customer")
        cust2 = User(name="Priya Sharma", email="priya@test.local", phone="9876543213",
                     password_hash=generate_password_hash("cust-pass"), role="customer")
        cat = Category(name="Electronics")
        db.session.add_all([admin, staff, cust1, cust2, cat])
        db.session.flush()

        prod1 = Product(sku="ELEC-01", name="Smart Watch", price=Decimal("2499.00"),
                        stock=10, category_id=cat.id)
        prod2 = Product(sku="ELEC-02", name="Bluetooth Speaker", price=Decimal("1299.00"),
                        stock=5, category_id=cat.id)
        db.session.add_all([prod1, prod2])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


SAMPLE_ADDRESS = {
    "fullName": "Rajesh Kumar",
    "mobileNumber": "9876543210",
    "alternatePhone": "9123456789",
    "houseNumber": "Flat 402, Lotus Tower",
    "buildingName": "Lotus Greens",
    "floorNumber": "4th Floor",
    "streetName": "MG Road",
    "area": "Indiranagar",
    "landmark": "Near Metro Station",
    "city": "Bengaluru",
    "postOffice": "Indiranagar PO",
    "district": "Bengaluru Urban",
    "state": "Karnataka",
    "pinCode": "560038",
    "deliveryInstructions": "Please ring bell and leave with security if unavailable"
}


def test_validate_indian_delivery_address_success():
    clean = validate_indian_delivery_address(SAMPLE_ADDRESS)
    assert clean["fullName"] == "Rajesh Kumar"
    assert clean["mobileNumber"] == "9876543210"
    assert clean["pinCode"] == "560038"
    assert clean["state"] == "Karnataka"


def test_validate_indian_delivery_address_missing_required():
    with pytest.raises(BusinessError, match="Full Name"):
        bad = SAMPLE_ADDRESS.copy()
        bad["fullName"] = " "
        validate_indian_delivery_address(bad)

    with pytest.raises(BusinessError, match="10-digit Indian mobile number"):
        bad = SAMPLE_ADDRESS.copy()
        bad["mobileNumber"] = "12345"
        validate_indian_delivery_address(bad)

    with pytest.raises(BusinessError, match="House/Flat Number"):
        bad = SAMPLE_ADDRESS.copy()
        bad["houseNumber"] = ""
        validate_indian_delivery_address(bad)

    with pytest.raises(BusinessError, match="Street Name/Road"):
        bad = SAMPLE_ADDRESS.copy()
        bad["streetName"] = ""
        validate_indian_delivery_address(bad)

    with pytest.raises(BusinessError, match="Area/Locality"):
        bad = SAMPLE_ADDRESS.copy()
        bad["area"] = ""
        validate_indian_delivery_address(bad)

    with pytest.raises(BusinessError, match="Village/Town/City"):
        bad = SAMPLE_ADDRESS.copy()
        bad["city"] = ""
        validate_indian_delivery_address(bad)

    with pytest.raises(BusinessError, match="District"):
        bad = SAMPLE_ADDRESS.copy()
        bad["district"] = ""
        validate_indian_delivery_address(bad)

    with pytest.raises(BusinessError, match="State"):
        bad = SAMPLE_ADDRESS.copy()
        bad["state"] = ""
        validate_indian_delivery_address(bad)

    with pytest.raises(BusinessError, match="6-digit Indian PIN code"):
        bad = SAMPLE_ADDRESS.copy()
        bad["pinCode"] = "056003"  # starts with 0
        validate_indian_delivery_address(bad)


def test_order_creation_with_address_snapshot(app):
    client = app.test_client()
    login = client.post("/api/auth/login", json={"email": "rajesh@test.local", "password": "cust-pass"})
    token = login.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Add item to cart
    res = client.post("/api/cart", headers=headers, json={"productId": 1, "quantity": 1})
    assert res.status_code == 200

    # Place order with complete Indian address
    res = client.post("/api/orders", headers=headers, json={"deliveryAddress": SAMPLE_ADDRESS})
    assert res.status_code == 201
    order_data = res.get_json()["order"]
    assert order_data["status"] == "pending"
    assert order_data["deliveryAddress"] is not None
    assert order_data["deliveryAddress"]["pinCode"] == "560038"
    assert order_data["deliveryAddress"]["district"] == "Bengaluru Urban"

    # Profile change should NOT change past order snapshot
    client.patch("/api/profile", headers=headers, json={"name": "Rajesh K", "phone": "9999999999"})
    res2 = client.get(f"/api/orders/{order_data['id']}", headers=headers)
    assert res2.status_code == 200
    retrieved_order = res2.get_json()["order"]
    assert retrieved_order["deliveryAddress"]["fullName"] == "Rajesh Kumar"
    assert retrieved_order["deliveryAddress"]["mobileNumber"] == "9876543210"


def test_order_authorization_and_cross_customer_isolation(app):
    client = app.test_client()
    # Cust 1 places order
    login1 = client.post("/api/auth/login", json={"email": "rajesh@test.local", "password": "cust-pass"})
    headers1 = {"Authorization": f"Bearer {login1.get_json()['token']}"}
    client.post("/api/cart", headers=headers1, json={"productId": 1, "quantity": 1})
    order_id = client.post("/api/orders", headers=headers1, json={"deliveryAddress": SAMPLE_ADDRESS}).get_json()["order"]["id"]

    # Cust 2 cannot view Cust 1's order details
    login2 = client.post("/api/auth/login", json={"email": "priya@test.local", "password": "cust-pass"})
    headers2 = {"Authorization": f"Bearer {login2.get_json()['token']}"}
    unauthorized = client.get(f"/api/orders/{order_id}", headers=headers2)
    assert unauthorized.status_code == 403

    # Staff CAN view Cust 1's order including delivery address
    staff_login = client.post("/api/auth/login", json={"email": "staff@test.local", "password": "staff-pass"})
    staff_headers = {"Authorization": f"Bearer {staff_login.get_json()['token']}"}
    staff_view = client.get(f"/api/orders/{order_id}", headers=staff_headers)
    assert staff_view.status_code == 200
    assert staff_view.get_json()["order"]["deliveryAddress"]["streetName"] == "MG Road"

    # Admin CAN view Cust 1's order including delivery address
    admin_login = client.post("/api/auth/login", json={"email": "admin@test.local", "password": "admin-pass"})
    admin_headers = {"Authorization": f"Bearer {admin_login.get_json()['token']}"}
    admin_view = client.get(f"/api/orders/{order_id}", headers=admin_headers)
    assert admin_view.status_code == 200
    assert admin_view.get_json()["order"]["deliveryAddress"]["city"] == "Bengaluru"
