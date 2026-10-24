from datetime import datetime, timezone
from decimal import Decimal

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, Index, UniqueConstraint

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(30), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer", index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (CheckConstraint("role IN ('customer','staff','admin')"),)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(300), nullable=False, default="")


class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    contact_person = db.Column(db.String(120), nullable=False, default="")
    email = db.Column(db.String(255), nullable=False, default="")
    phone = db.Column(db.String(30), nullable=False, default="")
    address = db.Column(db.String(300), nullable=False, default="")
    active = db.Column(db.Boolean, nullable=False, default=True)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(180), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False, default="")
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    low_stock_threshold = db.Column(db.Integer, nullable=False, default=5)
    image_url = db.Column(db.String(500), nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="active")
    category_id = db.Column(db.Integer, db.ForeignKey("category.id", ondelete="SET NULL"))
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id", ondelete="SET NULL"))
    category = db.relationship(Category, backref=db.backref("products", lazy="selectin"))
    supplier = db.relationship(Supplier, backref=db.backref("products", lazy="selectin"))
    __table_args__ = (
        CheckConstraint("price >= 0"),
        CheckConstraint("stock >= 0"),
        CheckConstraint("low_stock_threshold >= 0"),
        Index("ix_product_category_supplier", "category_id", "supplier_id"),
    )


class InventoryMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    order_id = db.Column(db.Integer, db.ForeignKey("order.id", ondelete="SET NULL"))
    action = db.Column(db.String(30), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(300), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    product = db.relationship(Product)
    user = db.relationship(User)


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id", ondelete="CASCADE"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    product = db.relationship(Product)
    __table_args__ = (UniqueConstraint("user_id", "product_id"), CheckConstraint("quantity > 0"))


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(24), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    discount = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    total = db.Column(db.Numeric(10, 2), nullable=False)
    delivery_address = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    user = db.relationship(User)
    items = db.relationship("OrderItem", cascade="all, delete-orphan", lazy="selectin")
    __table_args__ = (
        CheckConstraint("subtotal >= 0 AND discount >= 0 AND total >= 0"),
        CheckConstraint("status IN ('pending','confirmed','processing','ready','shipped','delivered','completed','cancelled')"),
    )


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id", ondelete="CASCADE"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id", ondelete="RESTRICT"), nullable=False)
    product_name = db.Column(db.String(180), nullable=False)
    sku = db.Column(db.String(50), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    product = db.relationship(Product)
    __table_args__ = (CheckConstraint("unit_price >= 0 AND quantity > 0"),)