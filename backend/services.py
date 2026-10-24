import re
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import update

from .models import CartItem, InventoryMovement, Order, OrderItem, Product, db

CENT = Decimal("0.01")
STATUS_NEXT = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"processing", "cancelled"},
    "processing": {"ready", "shipped"},
    "ready": {"completed", "shipped"},
    "shipped": {"delivered", "completed"},
    "delivered": {"completed"},
    "completed": set(),
    "cancelled": set(),
}


class BusinessError(ValueError):
    pass


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_discount(subtotal):
    sub = Decimal(str(subtotal))
    if sub >= Decimal("5000.00"):
        return money(sub * Decimal("0.05"))
    elif sub >= Decimal("3500.00"):
        return Decimal("200.00")
    return Decimal("0.00")


def validate_indian_delivery_address(data):
    if not isinstance(data, dict):
        raise BusinessError("A valid delivery address is required.")

    def get_val(*keys):
        for k in keys:
            if k in data and data[k] is not None:
                val = str(data[k]).strip()
                if val:
                    return val
        return ""

    full_name = get_val("fullName", "full_name", "name")
    mobile = get_val("mobileNumber", "mobile_number", "phone", "mobile")
    alternate_phone = get_val("alternatePhone", "alternate_phone", "altPhone", "alt_phone")

    house_number = get_val("houseNumber", "house_number", "flatNumber", "flat_number", "flatNo")
    building_name = get_val("buildingName", "building_name", "apartmentName", "apartment_name")
    floor_number = get_val("floorNumber", "floor_number", "floor")
    street_name = get_val("streetName", "street_name", "road", "street")
    area = get_val("area", "locality", "areaLocality")
    landmark = get_val("landmark")
    city = get_val("city", "town", "village", "townCity")
    post_office = get_val("postOffice", "post_office")
    district = get_val("district")
    state = get_val("state")
    pin_code = get_val("pinCode", "pincode", "postalCode", "zip")
    delivery_instructions = get_val("deliveryInstructions", "delivery_instructions", "instructions")

    if len(full_name) < 2:
        raise BusinessError("Full Name is required (minimum 2 characters).")

    mobile_digits = re.sub(r"\D", "", mobile)
    if len(mobile_digits) == 12 and mobile_digits.startswith("91"):
        mobile_digits = mobile_digits[2:]
    if len(mobile_digits) == 11 and mobile_digits.startswith("0"):
        mobile_digits = mobile_digits[1:]
    if not (len(mobile_digits) == 10 and mobile_digits[0] in "6789"):
        raise BusinessError("Please provide a valid 10-digit Indian mobile number.")

    alt_phone_clean = ""
    if alternate_phone:
        alt_digits = re.sub(r"\D", "", alternate_phone)
        if len(alt_digits) == 12 and alt_digits.startswith("91"):
            alt_digits = alt_digits[2:]
        if len(alt_digits) == 11 and alt_digits.startswith("0"):
            alt_digits = alt_digits[1:]
        if not (len(alt_digits) == 10 and alt_digits[0] in "6789"):
            raise BusinessError("Alternate mobile number must be a valid 10-digit Indian mobile number.")
        alt_phone_clean = alt_digits

    if not house_number:
        raise BusinessError("House/Flat Number is required.")
    if not street_name:
        raise BusinessError("Street Name/Road is required.")
    if not area:
        raise BusinessError("Area/Locality is required.")
    if not city:
        raise BusinessError("Village/Town/City is required.")
    if not district:
        raise BusinessError("District is required.")
    if not state:
        raise BusinessError("State is required.")

    pin_digits = re.sub(r"\D", "", pin_code)
    if not (len(pin_digits) == 6 and pin_digits[0] != "0"):
        raise BusinessError("Please provide a valid 6-digit Indian PIN code.")

    return {
        "fullName": full_name,
        "mobileNumber": mobile_digits,
        "alternatePhone": alt_phone_clean,
        "houseNumber": house_number,
        "buildingName": building_name,
        "floorNumber": floor_number,
        "streetName": street_name,
        "area": area,
        "landmark": landmark,
        "city": city,
        "postOffice": post_office,
        "district": district,
        "state": state,
        "pinCode": pin_digits,
        "deliveryInstructions": delivery_instructions,
    }


def place_order(user_id, delivery_address=None):
    cart = CartItem.query.filter_by(user_id=user_id).all()
    if not cart:
        raise BusinessError("Your cart is empty.")
    return create_order(user_id, [(row.product_id, row.quantity) for row in cart],
                        clear_cart=True, delivery_address=delivery_address)


def create_order(user_id, requested_items, clear_cart=False, actor_id=None, delivery_address=None):
    if not isinstance(requested_items, list) or not requested_items:
        raise BusinessError("Add at least one product to the order.")
    address_snapshot = None
    if delivery_address:
        address_snapshot = validate_indian_delivery_address(delivery_address)
    quantities = {}
    for product_id, quantity in requested_items:
        if type(product_id) is not int or type(quantity) is not int or quantity < 1:
            raise BusinessError("Each order item needs a valid product and positive whole quantity.")
        quantities[product_id] = quantities.get(product_id, 0) + quantity
    try:
        subtotal = Decimal("0.00")
        order = Order(number=f"SF-{uuid4().hex[:10].upper()}", user_id=user_id,
                      status="pending", subtotal=Decimal("0.00"),
                      discount=Decimal("0.00"), total=Decimal("0.00"),
                      delivery_address=address_snapshot)
        db.session.add(order)
        db.session.flush()
        for product_id, quantity in sorted(quantities.items()):
            product = db.session.get(Product, product_id)
            if product is None or product.status != "active":
                raise BusinessError("A product in your cart is no longer available.")
            changed = db.session.execute(
                update(Product).where(Product.id == product.id, Product.status == "active",
                                      Product.stock >= quantity)
                .values(stock=Product.stock - quantity)
                .execution_options(synchronize_session=False)
            )
            if changed.rowcount != 1:
                raise BusinessError(f"Not enough stock for {product.name}.")
            subtotal += money(product.price) * quantity
            order.items.append(OrderItem(product_id=product.id, product_name=product.name,
                                         sku=product.sku, unit_price=money(product.price),
                                         quantity=quantity))
            db.session.add(InventoryMovement(product_id=product.id, user_id=actor_id or user_id,
                                             order_id=order.id, action="order",
                                             quantity=-quantity, note=f"Order {order.number}"))
        discount = calculate_discount(subtotal)
        order.subtotal, order.discount, order.total = money(subtotal), discount, money(subtotal - discount)
        if clear_cart:
            CartItem.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        db.session.commit()
        return order
    except Exception:
        db.session.rollback()
        raise


def transition_order(order, next_status, actor_id):
    if not isinstance(next_status, str):
        raise BusinessError("Choose a valid order status.")
    if next_status not in STATUS_NEXT.get(order.status, set()):
        raise BusinessError(f"Cannot move an order from {order.status} to {next_status}.")
    previous_status = order.status
    changed = db.session.execute(
        update(Order).where(Order.id == order.id, Order.status == previous_status)
        .values(status=next_status).execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.session.rollback()
        raise BusinessError("This order has already changed. Refresh and try again.")
    if next_status == "cancelled":
        if order.status not in {"pending", "confirmed"}:
            raise BusinessError("Only pending or confirmed orders can be cancelled.")
        for item in order.items:
            changed = db.session.execute(
                update(Product).where(Product.id == item.product_id)
                .values(stock=Product.stock + item.quantity)
                .execution_options(synchronize_session=False)
            )
            if changed.rowcount != 1:
                raise BusinessError("A product in this order no longer exists.")
            db.session.add(InventoryMovement(product_id=item.product_id, user_id=actor_id,
                                             order_id=order.id, action="restoration",
                                             quantity=item.quantity, note=f"Cancelled {order.number}"))
    order.status = next_status
    db.session.commit()
    return order
