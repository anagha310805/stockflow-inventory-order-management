import re
from decimal import Decimal
import pytest
from werkzeug.security import check_password_hash

from backend import create_app
from backend.config import Config, database_url, engine_options
from backend.models import db, User, Product, Category, Supplier
from backend.seed_products import seed_sample_products
from backend.init_admin import init_admin


@pytest.fixture
def clean_app():
    test_app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-deployment-secret-key-64chars",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "CORS_ORIGINS": [
            "https://stockflow-inventory-order-managemen.vercel.app",
            "https://stockflow-inventory-order-management.vercel.app",
            "http://127.0.0.1:5177"
        ]
    })
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


def test_cors_preflight_and_deployed_origins(clean_app):
    client = clean_app.test_client()

    # 1. Exact user deployment without 't'
    r1 = client.get('/api/health', headers={'Origin': 'https://stockflow-inventory-order-managemen.vercel.app'})
    assert r1.status_code == 200
    assert r1.headers.get('Access-Control-Allow-Origin') == 'https://stockflow-inventory-order-managemen.vercel.app'

    # 2. Deployment with 't'
    r2 = client.get('/api/health', headers={'Origin': 'https://stockflow-inventory-order-management.vercel.app'})
    assert r2.status_code == 200
    assert r2.headers.get('Access-Control-Allow-Origin') == 'https://stockflow-inventory-order-management.vercel.app'

    # 3. Dynamic preview domain on vercel.app
    r3 = client.get('/api/health', headers={'Origin': 'https://stockflow-preview-pr-12.vercel.app'})
    assert r3.status_code == 200
    assert r3.headers.get('Access-Control-Allow-Origin') == 'https://stockflow-preview-pr-12.vercel.app'

    # 4. OPTIONS preflight
    opt = client.options('/api/products', headers={
        'Origin': 'https://stockflow-inventory-order-managemen.vercel.app',
        'Access-Control-Request-Method': 'GET'
    })
    assert opt.status_code == 200
    assert opt.headers.get('Access-Control-Allow-Origin') == 'https://stockflow-inventory-order-managemen.vercel.app'


def test_empty_catalog_and_products_route(clean_app):
    client = clean_app.test_client()
    resp = client.get('/api/products')
    assert resp.status_code == 200
    data = resp.get_json()
    assert "products" in data
    assert data["products"] == []


def test_seed_sample_products_and_idempotency(clean_app):
    with clean_app.app_context():
        # Clean state
        assert Product.query.count() == 0

        # Run seed
        added, existing, total = seed_sample_products(app=clean_app)
        assert added == 5
        assert existing == 0
        assert total == 5

        # Verify products in database
        products = Product.query.all()
        assert len(products) == 5
        skus = {p.sku for p in products}
        assert skus == {"LAP-204", "KEY-104", "MOU-208", "MON-327", "AUD-410"}

        # Verify categories & suppliers relationships
        laptop = Product.query.filter_by(sku="LAP-204").first()
        assert laptop.category.name == "Computing"
        assert laptop.supplier.name == "Northstar Electronics"
        assert laptop.price == Decimal("54999.00")

        # Second run must be completely idempotent (0 added, 5 existing)
        added2, existing2, total2 = seed_sample_products(app=clean_app)
        assert added2 == 0
        assert existing2 == 5
        assert total2 == 5
        assert Product.query.count() == 5


def test_init_admin_creation_and_idempotency(clean_app):
    with clean_app.app_context():
        admin_email = "prod_admin@stockflow.test"
        admin_pass = "SecureAdmin2026!Key"

        # 1. Create admin
        admin = init_admin(email=admin_email, password=admin_pass, name="Lead Administrator", app=clean_app)
        assert admin is not None
        assert admin.email == admin_email
        assert admin.role == "admin"
        assert admin.active is True
        assert check_password_hash(admin.password_hash, admin_pass)

        # 2. Verify login works via API
        client = clean_app.test_client()
        login_resp = client.post('/api/auth/login', json={
            "email": admin_email,
            "password": admin_pass
        })
        assert login_resp.status_code == 200
        login_data = login_resp.get_json()
        assert login_data["user"]["role"] == "admin"
        assert "token" in login_data

        # 3. Running init_admin again must not duplicate or alter account
        admin_second = init_admin(email=admin_email, password="DifferentPassword!234", app=clean_app)
        assert admin_second.id == admin.id
        # Password remains the original password
        current_admin = db.session.get(User, admin.id)
        assert check_password_hash(current_admin.password_hash, admin_pass)
        assert not check_password_hash(current_admin.password_hash, "DifferentPassword!234")


def test_auth_failure_modes(clean_app):
    client = clean_app.test_client()

    # Wrong password
    resp1 = client.post('/api/auth/login', json={
        "email": "nonexistent@stockflow.test",
        "password": "AnyPassword123!"
    })
    assert resp1.status_code == 401
    assert "incorrect" in resp1.get_json()["error"].lower()

    # Incomplete payload
    resp2 = client.post('/api/auth/login', json={})
    assert resp2.status_code == 401


def test_database_engine_options():
    opts = engine_options()
    assert opts["pool_recycle"] == 280
    assert opts["pool_pre_ping"] is True
