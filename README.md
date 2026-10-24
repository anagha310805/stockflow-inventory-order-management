# StockFlow — Inventory & Order Management Platform

StockFlow is a production-grade, full-stack inventory and order management platform built with React, Vite, Flask, SQLAlchemy, and MySQL. It empowers businesses to centrally manage products, inventory, suppliers, customers, and fulfillment workflows with role-based access control, atomic concurrency safety, and audit logging.

---

## 1. Core Architecture & User Roles

StockFlow provides distinct interfaces and capabilities for three primary user roles:

1. **Customer**:
   - Self-registration with validation (name, email, phone, password).
   - Profile management with contact details update and secure password change.
   - Live product catalog browsing with multi-criteria search and filtering:
     - Search by product name or SKU.
     - Filter by category, supplier, price range (Min/Max in INR), stock availability ("In stock only"), and product status (Active / Archived).
   - Product details modal with high-resolution imagery, SKU, category, stock indicators, and instant cart actions.
   - Shopping cart with quantity increments/decrements, removals, and real-time tiered discount calculation.
   - Comprehensive multi-step checkout with full Indian delivery address capture (Flat/House/Floor, Street/Area, Landmark, City/Town, District, State, and 6-digit PIN code validation).
   - Order history with detailed line-item breakdown (unit price, item quantity, line total), financial summary (subtotal, discount, total), order status, and frozen delivery address snapshots.
   - Instant order cancellation for eligible orders (`PENDING`, `CONFIRMED`) with transactional inventory restoration.

2. **Staff**:
   - Secure staff authentication with role verification and route protection.
   - Product catalog management: create, update, and archive products with category and supplier links.
   - Category and supplier management with cascade deletion protection (cannot delete categories or suppliers with associated products).
   - Supplier directory displaying supplier contact information, product count badges, and lists of supplied products.
   - Live inventory management: adjust stock (add/reduce with validation), view low-stock alerts, and toggle product status.
   - Complete inventory movement audit log tracking every stock adjustment, customer order deduction, and cancellation restoration with timestamps and reference IDs.
   - Order fulfillment workflow: view customer orders, delivery address details, and transition orders through:
     $$\text{PENDING} \longrightarrow \text{CONFIRMED} \longrightarrow \text{PROCESSING} \longrightarrow \text{READY} \longrightarrow \text{COMPLETED}$$
   - Customer directory lookup for order coordination.
   - Financial report generation and CSV export with date range and text filtering.

3. **Administrator**:
   - Full access to all Staff capabilities.
   - Platform overview and real-time dashboard statistics: total products, customers, suppliers, orders, pending, completed, cancelled, low stock, and out of stock counts.
   - Staff account management: create new staff accounts, update details, reset passwords, and toggle active/inactive status.
   - Self-lockout protection: administrators cannot deactivate or modify their own active status.
   - Customer account management and monitoring.

---

## 2. Business Logic & Tiered Discount Rule

Discounts are calculated authoritatively on the backend (`backend/services.py`) and synchronized with the frontend:

- **Tier 1 (Standard)**: Subtotals below ₹3,500 receive **₹0** discount.
- **Tier 2 (Assessment Baseline)**: Subtotals from **₹3,500 up to ₹4,999.99** receive a flat **₹200** discount.
  - *Example from Assessment Page 4*:
    - 2 × Wireless Keyboard (@ ₹1,499) = ₹2,998
    - 1 × Wireless Mouse (@ ₹799) = ₹799
    - **Subtotal**: ₹3,797
    - **Discount**: ₹200
    - **Final Order Total**: **₹3,597**
- **Tier 3 (Volume Threshold)**: Subtotals of **₹5,000 or greater** receive a **5% volume discount** (e.g., ₹5,000 subtotal yields ₹250 discount, total ₹4,750).

---

## 3. Concurrency Safety & Inventory Consistency

StockFlow protects against race conditions and negative inventory (e.g., two customers simultaneously purchasing the last items in stock):
- MySQL InnoDB transactions with row-level locks.
- Atomic conditional update pattern:
  ```sql
  UPDATE products
  SET stock = stock - :qty
  WHERE id = :prod_id AND stock >= :qty;
  ```
- If any line in a multi-item cart cannot be fulfilled, the entire database transaction rolls back, and an error response is returned without partial deductions.
- Cancellation verifies the order's state within the transaction and restores inventory only once, preventing double-cancellation attacks.

---

## 4. Project Structure

```text
stock-flow/
├── backend/
│   ├── __init__.py        # Flask application factory, CORS, and REST API endpoints
│   ├── config.py          # Environment-driven configuration
│   ├── models.py          # Relational SQLAlchemy schema (User, Product, Order, etc.)
│   ├── services.py        # Order transactions, discount engine, address validation
│   ├── run.py             # Development server entry point (port 5000)
│   ├── seed.py            # Repeatable database seed script
│   └── tests/
│       ├── test_delivery_address.py # Address validation & customer isolation tests
│       └── test_orders.py           # Concurrency, workflow, discounts, RBAC tests
├── src/
│   ├── App.jsx            # Customer checkout, catalog, profile, and admin controls
│   ├── StaffPages.jsx     # Staff dashboards, inventory, suppliers, orders, reports
│   ├── api.js             # Fetch API client with Bearer auth and error parsing
│   └── styles.css         # Modern, responsive styles with CSS variables
├── index.html             # Vite entry HTML
├── vite.config.js         # Frontend config and development /api reverse proxy
├── Procfile               # Production WSGI process definition (Gunicorn)
├── requirements.txt       # Python dependencies
├── package.json           # Node.js dependencies and build scripts
└── README.md              # Project documentation and video demonstration script
```

---

## 5. Local Setup & Installation

### Prerequisites
- Python 3.11 or later
- Node.js 20 or later
- MySQL 8.0 or later running locally

### Backend Setup

1. Open PowerShell and navigate to the project directory:
   ```powershell
   cd "c:\Users\AKSHAY R\OneDrive\Desktop\stock flow"
   ```

2. Create and activate a Python virtual environment:
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install required Python packages:
   ```powershell
   pip install -r requirements.txt
   ```

4. Configure environment variables in `.env`:
   ```ini
   SECRET_KEY=your-secure-random-secret-key
   MYSQL_HOST=127.0.0.1
   MYSQL_PORT=3306
   MYSQL_DATABASE=stockflow
   MYSQL_USER=your-mysql-user
   MYSQL_PASSWORD=your-mysql-password
   INITIAL_ADMIN_PASSWORD=choose-a-strong-admin-password
   INITIAL_STAFF_PASSWORD=choose-a-strong-staff-password
   DEMO_PASSWORD=choose-a-strong-demo-password
   ```

5. Seed the database with sample products, categories, suppliers, and initial users:
   ```powershell
   python -m backend.seed
   ```

6. Start the Flask API server:
   ```powershell
   python -m backend.run
   ```
   *The backend will listen on `http://127.0.0.1:5000`.*

### Frontend Setup

1. Open a second PowerShell terminal in the project directory:
   ```powershell
   npm install
   npm run dev
   ```
   *The Vite frontend will open at `http://localhost:5173` (or configured dev port).*

---

## 6. Testing & Quality Assurance

Run the automated test suite covering authentication, permissions, discount rules, concurrency, order transitions, and address validation:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -v
```
*(All 25 tests should pass with 100% success rate).*

Verify the production frontend build:

```powershell
npm run build
```

---

## 7. Production Deployment Guide

### Option A: Backend on Render / Railway / Fly.io

1. **Database**: Provision a managed MySQL instance (e.g., PlanetScale, Aiven, or Railway MySQL).
2. **Environment Variables**: Configure the following in your hosting provider's dashboard:
   - `SECRET_KEY`: High-entropy 64-character secret.
   - `DATABASE_URL`: `mysql+pymysql://<user>:<password>@<host>:<port>/<database>`
   - `CORS_ORIGINS`: Your production frontend URL (e.g., `https://stockflow-app.vercel.app`).
   - `FLASK_ENV`: `production`
3. **Build & Start Commands**:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn -w 4 -b 0.0.0.0:$PORT "backend:create_app()"` (or refer to `Procfile`).

### Option B: Frontend on Vercel / Netlify

1. Link your Git repository to Vercel or Netlify.
2. **Build Settings**:
   - Framework Preset: `Vite`
   - Build Command: `npm run build`
   - Output Directory: `dist`
3. **Environment Variables**:
   - `VITE_API_BASE`: `https://your-backend-service.onrender.com`
4. Deploy and test live connectivity.

---

## 8. Minute-by-Minute Video Recording Script (5–10 Minutes)

This script provides an exact schedule and speaking points for your 5–10 minute technical demonstration video:

| Time Interval | Section | Actions & Demonstration Flow | Key Talking Points |
| :--- | :--- | :--- | :--- |
| **0:00 – 1:00** | **Introduction & Role-Based Auth** | • Introduce StockFlow as a full-stack inventory and order platform.<br>• Demonstrate login as **Administrator**, **Staff**, and **Customer**.<br>• Show distinct navigation bars for each role. | *"StockFlow enforces server-side role isolation. Customers only see store routes; staff see operational tools; admins oversee the entire platform."* |
| **1:00 – 2:30** | **Product Catalog & Filtering** | • Log in as Customer.<br>• Demonstrate instant search by keyword ("Keyboard") and SKU.<br>• Filter by Category ("Accessories") and Supplier.<br>• Adjust price range sliders/inputs (Min/Max INR).<br>• Toggle "In stock only" and Product Status (Active vs Archived).<br>• Open Product Details modal. | *"Products display live stock quantities, low-stock threshold tags, and INR pricing. Inactive or archived items cannot be added to cart."* |
| **2:30 – 4:00** | **Cart, Tiered Discount & Checkout** | • Add 2 × Wireless Keyboard (₹1,499) and 1 × Wireless Mouse (₹799).<br>• Open Cart: highlight Subtotal = ₹3,797.<br>• Point out the automatic flat **₹200 discount** applied, bringing the Total to **₹3,597** (exact assessment example).<br>• Click "Proceed to checkout".<br>• Fill in the Indian delivery address form with House/Street/City/State and a valid 6-digit PIN code (e.g., 560001).<br>• Review summary and place order. | *"The discount engine authoritatively recalculates totals on the server. The complete Indian delivery address is snapshotted to the order permanently."* |
| **4:00 – 5:15** | **Customer Order History & Cancellation** | • Navigate to Customer Orders page.<br>• Inspect the newly placed order card: point out unit prices, subtotal, discount, total, and delivery address.<br>• Demonstrate order cancellation: click "Cancel Order".<br>• Show that order status updates to `cancelled` and stock is immediately restored.<br>• Try cancelling again to demonstrate single-restoration idempotency. | *"Eligible orders can be cancelled while pending or confirmed. Cancellation restores inventory in an atomic database transaction."* |
| **5:15 – 6:45** | **Staff Operations & Order Fulfillment** | • Switch account to Staff (`staff@stockflow.local`).<br>• Open Staff Orders view.<br>• Select an order and advance status: `PENDING → CONFIRMED → PROCESSING → READY → COMPLETED`.<br>• Open Inventory tab: demonstrate stock adjustment (add +10 units to a product).<br>• Open Inventory Movement history: show logged entries for orders, cancellations, and manual adjustments. | *"Staff advance orders through the strict workflow ending in COMPLETED. Every stock delta creates an immutable audit movement record."* |
| **6:45 – 8:00** | **Supplier & Category Management** | • Open Suppliers tab.<br>• Inspect supplier records: name, contact person, email, phone, and address.<br>• Show the **Product Count** badge and expandable list of products supplied by each supplier.<br>• Demonstrate category/supplier modification and explain deletion protection when products are linked. | *"Staff manage supplier contact info and monitor supplier product portfolios directly from the directory."* |
| **8:00 – 9:15** | **Admin Dashboard & Account Lifecycle** | • Switch account to Administrator (`admin@stockflow.local`).<br>• Show Platform Statistics cards: Products, Customers, Suppliers, Orders, Pending, Completed, Low Stock, Out of Stock.<br>• Open Staff Accounts: create a new staff account, edit credentials, and toggle status (Active/Inactive).<br>• Demonstrate self-lockout protection (deactivate button disabled for the logged-in admin). | *"Administrators have full operational visibility and manage staff credentials with built-in self-lockout safeguards."* |
| **9:15 – 10:00** | **Technical Architecture & Concurrency** | • Display terminal and run `pytest backend/tests -v` (showing all 25 tests passing).<br>• Run `npm run build` (showing clean Vite compilation).<br>• Briefly highlight the atomic `UPDATE ... WHERE stock >= qty` query in `backend/services.py`.<br>• Conclude the presentation. | *"StockFlow guarantees 100% data integrity, preventing negative stock scenarios under high concurrency while delivering a seamless user experience."* |

---

## 9. Security & Compliance Checklist

- [x] Passwords hashed using Werkzeug (`generate_password_hash` with scrypt/pbkdf2).
- [x] Expiring HMAC tokens with user role and ID claims.
- [x] Strict backend authorization decorators on every protected endpoint.
- [x] Input validation for email format, phone numbers, and Indian PIN codes.
- [x] Atomic transactions preventing race conditions and partial stock updates.
- [x] Zero hardcoded secrets: `.env` strictly excluded via `.gitignore`.
- [x] Clean, responsive UI with Back navigation and breadcrumb support.
