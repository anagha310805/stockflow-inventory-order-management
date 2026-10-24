import { useEffect, useState } from 'react'
import {
  ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Download, FileText, Package, Plus,
  Search, Users, X,
} from 'lucide-react'
import { api, money } from './api.js'

const empty = { products: [], categories: [], suppliers: [], customers: [], orders: [], movements: [] }

export default function StaffPages({ page, user, onNavigate, onBack, onUserUpdate, onNotice, onError }) {
  const isAdmin = user?.role === 'admin'
  const [data, setData] = useState(empty)
  const [dashboard, setDashboard] = useState(null)
  const [report, setReport] = useState(null)
  const [search, setSearch] = useState('')
  const [productCategory, setProductCategory] = useState('')
  const [productSupplier, setProductSupplier] = useState('')
  const [productStatus, setProductStatus] = useState('all')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [editProduct, setEditProduct] = useState(null)
  const [editCustomer, setEditCustomer] = useState(null)
  const [categoryRecords, setCategoryRecords] = useState([])
  const [supplierRecords, setSupplierRecords] = useState([])
  const [categorySearch, setCategorySearch] = useState('')
  const [supplierSearch, setSupplierSearch] = useState('')
  const [editCategory, setEditCategory] = useState(null)
  const [editSupplier, setEditSupplier] = useState(null)
  const [orderItems, setOrderItems] = useState([{ productId: '', quantity: 1 }])

  const load = async () => {
    setLoading(true)
    try {
      if (page === 'dashboard') {
        setDashboard(await api('/dashboard'))
      } else if (page === 'products') {
        const params = new URLSearchParams({ status: productStatus })
        if (search) params.set('q', search)
        if (productCategory) params.set('category', productCategory)
        if (productSupplier) params.set('supplier', productSupplier)
        const [products, categories, suppliers] = await Promise.all([
          api(`/products/manage?${params}`), api('/categories'), api('/suppliers'),
        ])
        setData((previous) => ({ ...previous, products: products.products, categories: categories.categories, suppliers: suppliers.suppliers }))
      } else if (page === 'inventory') {
        const [products, movements] = await Promise.all([api('/products/manage'), api('/inventory/movements')])
        setData((previous) => ({ ...previous, products: products.products, movements: movements.movements }))
      } else if (page === 'orders-manage') {
        const [orders, customers, products] = await Promise.all([api('/orders'), api('/customers'), api('/products/manage')])
        setData((previous) => ({ ...previous, orders: orders.orders, customers: customers.customers, products: products.products }))
      } else if (page === 'customers-manage') {
        const params = new URLSearchParams()
        if (search) params.set('q', search)
        const result = await api(`/customers?${params}`)
        setData((previous) => ({ ...previous, customers: result.customers }))
      } else if (page === 'catalog-data') {
        const [categories, suppliers] = await Promise.all([
          api(`/categories?q=${encodeURIComponent(categorySearch)}`),
          api(`/suppliers/manage?q=${encodeURIComponent(supplierSearch)}`),
        ])
        setCategoryRecords(categories.categories)
        setSupplierRecords(suppliers.suppliers)
      } else if (page === 'reports') {
        const params = new URLSearchParams()
        if (from) params.set('from', from)
        if (to) params.set('to', to)
        if (search) params.set('q', search)
        setReport(await api(`/reports?${params}`))
      }
    } catch (error) {
      onError(error.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [page, from, to, search, productCategory, productSupplier, productStatus, categorySearch, supplierSearch])

  const submit = async (event, request, message) => {
    event.preventDefault()
    try {
      await request()
      await load()
      onNotice(message)
      return true
    } catch (error) {
      onError(error.message)
      return false
    }
  }

  const saveProduct = async (event) => {
    const form = new FormData(event.currentTarget)
    const payload = Object.fromEntries(form.entries())
    const isEdit = Boolean(editProduct?.id)
    payload.price = Number(payload.price)
    payload.threshold = Number(payload.threshold)
    payload.categoryId = payload.categoryId ? Number(payload.categoryId) : null
    payload.supplierId = payload.supplierId ? Number(payload.supplierId) : null
    if (!isEdit) payload.stock = Number(payload.stock || 0)
    const completed = await submit(event, () => api('/products/manage', {
      method: isEdit ? 'PATCH' : 'POST',
      body: JSON.stringify(isEdit ? { ...payload, id: editProduct.id } : payload),
    }), isEdit ? 'Product updated.' : 'Product added.')
    if (completed) setEditProduct(null)
  }

  const adjustInventory = (event, product) => {
    const form = new FormData(event.currentTarget)
    return submit(event, () => api(`/inventory/${product.id}`, {
      method: 'POST', body: JSON.stringify({
        action: form.get('action'), quantity: Number(form.get('quantity')),
        note: String(form.get('note') || ''),
      }),
    }), 'Inventory movement saved.')
  }

  const saveCustomer = async (event) => {
    const form = new FormData(event.currentTarget)
    const payload = Object.fromEntries(form.entries())
    const endpoint = editCustomer ? `/customers/${editCustomer.id}` : '/customers'
    const completed = await submit(event, () => api(endpoint, {
      method: editCustomer ? 'PATCH' : 'POST', body: JSON.stringify(payload),
    }), editCustomer ? 'Customer updated.' : 'Customer created.')
    if (completed) setEditCustomer(null)
  }

  const saveCategory = async (event) => {
    const form = new FormData(event.currentTarget)
    const payload = Object.fromEntries(form.entries())
    const endpoint = editCategory ? '/categories/manage' : '/categories/manage'
    const completed = await submit(event, () => api(endpoint, {
      method: editCategory ? 'PATCH' : 'POST',
      body: JSON.stringify(editCategory ? { ...payload, id: editCategory.id } : payload),
    }), editCategory ? 'Category updated.' : 'Category created.')
    if (completed) setEditCategory(null)
  }

  const saveSupplier = async (event) => {
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries())
    const completed = await submit(event, () => api('/suppliers/manage', {
      method: editSupplier ? 'PATCH' : 'POST',
      body: JSON.stringify(editSupplier ? { ...payload, id: editSupplier.id } : payload),
    }), editSupplier ? 'Supplier updated.' : 'Supplier created.')
    if (completed) setEditSupplier(null)
  }

  const deleteRecord = async (kind, item) => {
    if (!window.confirm(`Delete ${item.name}?`)) return
    try {
      const endpoint = kind === 'category' ? `/categories/manage?id=${item.id}` : `/suppliers/manage?id=${item.id}`
      await api(endpoint, { method: 'DELETE' })
      await load()
      onNotice(`${kind === 'category' ? 'Category' : 'Supplier'} deleted.`)
    } catch (error) { onError(error.message) }
  }

  const createOrder = async (event) => {
    const form = new FormData(event.currentTarget)
    const items = orderItems.map((line) => ({ productId: Number(line.productId), quantity: Number(line.quantity) }))
    const completed = await submit(event, () => api('/orders', {
      method: 'POST', body: JSON.stringify({ customerId: Number(form.get('customerId')), items }),
    }), 'Order created and stock deducted.')
    if (completed) setOrderItems([{ productId: '', quantity: 1 }])
  }

  const updateOrder = async (order, status) => {
    try {
      await api(`/orders/${order.id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })
      await load()
      onNotice(`Order ${order.number} moved to ${status}.`)
    } catch (error) { onError(error.message) }
  }

  const estimatedSubtotal = orderItems.reduce((total, line) => {
    const product = data.products.find((item) => item.id === Number(line.productId))
    return total + (product ? product.price * Number(line.quantity || 0) : 0)
  }, 0)
  const estimatedDiscount = estimatedSubtotal >= 5000 ? Math.round(estimatedSubtotal * 0.05 * 100) / 100 : 0

  const exportCsv = async () => {
    try {
      const token = localStorage.getItem('stockflow-token')
      const params = new URLSearchParams()
      if (from) params.set('from', from)
      if (to) params.set('to', to)
      if (search) params.set('q', search)
      const response = await fetch(`/api/reports/orders.csv?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      if (!response.ok) throw new Error('CSV export failed.')
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'stockflow-orders.csv'
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (error) { onError(error.message) }
  }

  if (page === 'dashboard') return <section className="workspace-page">
    <PageTitle eyebrow="STOCKFLOW OVERVIEW" title="Dashboard" subtitle="Live inventory, order, and sales signals." loading={loading} onBack={isAdmin ? onBack : undefined} />
    {!dashboard ? <EmptyState title="Dashboard unavailable" /> : <>
      <div className="metric-grid dashboard-metrics">
        <button type="button" className="metric-card metric-button" onClick={() => onNavigate?.('products')} title="Manage products">
          <div className="metric-icon"><Package size={17} /></div>
          <span>Products</span>
          <strong>{dashboard.products}</strong>
        </button>
        <button type="button" className="metric-card metric-button" onClick={() => onNavigate?.('customers-manage')} title="Manage customers">
          <div className="metric-icon"><Users size={17} /></div>
          <span>Customers</span>
          <strong>{dashboard.customers}</strong>
        </button>
        <button type="button" className="metric-card metric-button" onClick={() => onNavigate?.('orders-manage')} title="Manage orders">
          <div className="metric-icon"><FileText size={17} /></div>
          <span>Orders</span>
          <strong>{dashboard.orders}</strong>
        </button>
        <button type="button" className="metric-card metric-button" onClick={() => onNavigate?.('inventory')} title="Manage inventory">
          <div className="metric-icon"><ArrowUp size={17} /></div>
          <span>Inventory value</span>
          <strong>{money(dashboard.inventoryValue)}</strong>
        </button>
        <button type="button" className="metric-card metric-button" onClick={() => onNavigate?.('reports')} title="View reports">
          <div className="metric-icon"><ArrowRight size={17} /></div>
          <span>Sales completed</span>
          <strong>{money(dashboard.salesTotal)}</strong>
        </button>
      </div>
      <div className="staff-two-column">
        <section className="panel">
          <div className="panel-heading">
            <div><span className="section-kicker">RECENT ACTIVITY</span><h2>Latest orders</h2></div>
            <button type="button" className="text-button" onClick={() => onNavigate?.('orders-manage')}>View all <ArrowRight size={13} /></button>
          </div>
          {dashboard.recentOrders.length ? <div className="staff-list">{dashboard.recentOrders.map((order) => <OrderRow key={order.id} order={order} />)}</div> : <EmptyState title="No orders recorded" />}
        </section>
        <section className="panel">
          <div className="panel-heading">
            <div><span className="section-kicker">REPLENISHMENT</span><h2>Low stock</h2></div>
            <button type="button" className="text-button" onClick={() => onNavigate?.('inventory')}>View stock <ArrowRight size={13} /></button>
          </div>
          {dashboard.lowStock.length ? <div className="staff-list">{dashboard.lowStock.map((item) => <div className="staff-list-row" key={item.id}><span><b>{item.name}</b><small>{item.sku} · threshold {item.threshold}</small></span><strong className="stock-warning">{item.stock} left</strong></div>)}</div> : <EmptyState title="Stock levels look good" />}
        </section>
      </div>
    </>}
  </section>

  if (page === 'products') return <section className="workspace-page">
    <PageTitle eyebrow="CATALOG CONTROL" title="Products" subtitle="Create, inspect, edit, and archive catalog items." loading={loading} onBack={onBack} />
    <div className="staff-toolbar"><label className="search-field"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name or SKU" /></label><select aria-label="Filter category" value={productCategory} onChange={(event) => setProductCategory(event.target.value)}><option value="">All categories</option>{data.categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select><select aria-label="Filter supplier" value={productSupplier} onChange={(event) => setProductSupplier(event.target.value)}><option value="">All suppliers</option>{data.suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}</select><select aria-label="Filter status" value={productStatus} onChange={(event) => setProductStatus(event.target.value)}><option value="all">All statuses</option><option value="active">Active</option><option value="inactive">Archived</option></select><button className="primary-button" onClick={() => setEditProduct({})}><Plus size={15} /> Add product</button></div>
    <section className="panel staff-table-panel"><div className="staff-table-scroll"><table className="staff-table"><thead><tr><th>Product</th><th>SKU</th><th>Category</th><th>Price</th><th>Quantity</th><th>Status</th><th>Actions</th></tr></thead><tbody>
      {data.products.map((item) => <tr key={item.id}><td><b>{item.name}</b></td><td>{item.sku}</td><td>{item.category}</td><td>{money(item.price)}</td><td>{item.stock}</td><td><span className={`table-status ${item.status}`}>{item.status}</span></td><td className="table-actions"><button className="text-button" onClick={() => setSelectedProduct(item)}>View</button><button className="text-button" onClick={() => setEditProduct(item)}>Edit</button>{item.status === 'active' && <button className="cancel-order" onClick={async () => { if (!window.confirm(`Archive ${item.name}?`)) return; try { await api(`/products/manage?id=${item.id}`, { method: 'DELETE' }); await load(); onNotice('Product archived.') } catch (error) { onError(error.message) } }}>Archive</button>}</td></tr>)}
      {!data.products.length && <tr><td colSpan="7"><EmptyState title="No products match this search" /></td></tr>}
    </tbody></table></div></section>
    {editProduct && <ProductDialog product={editProduct.id ? editProduct : null} categories={data.categories} suppliers={data.suppliers} onClose={() => setEditProduct(null)} onSubmit={saveProduct} />}
    {selectedProduct && <ProductView product={selectedProduct} onClose={() => setSelectedProduct(null)} />}
  </section>

  if (page === 'inventory') return <section className="workspace-page">
    <PageTitle eyebrow="STOCK CONTROL" title="Inventory" subtitle="Every adjustment is recorded in the movement history." loading={loading} onBack={onBack} />
    <section className="panel staff-table-panel"><div className="staff-table-scroll"><table className="staff-table"><thead><tr><th>Product</th><th>SKU</th><th>Available</th><th>Threshold</th><th>Level</th><th>Adjust stock</th></tr></thead><tbody>
      {data.products.map((item) => <tr key={item.id}><td><b>{item.name}</b></td><td>{item.sku}</td><td>{item.stock}</td><td>{item.threshold}</td><td><span className={`table-status ${item.stock === 0 ? 'inactive' : item.stock <= item.threshold ? 'warning' : 'active'}`}>{item.stock === 0 ? 'Out of stock' : item.stock <= item.threshold ? 'Low stock' : 'In stock'}</span></td><td><form className="inline-stock-form" onSubmit={(event) => adjustInventory(event, item)}><select name="action" aria-label="Stock movement"><option value="addition">Add</option><option value="reduction">Reduce</option></select><input name="quantity" type="number" min="1" required placeholder="Units" /><button className="icon-button" aria-label={`Save stock adjustment for ${item.name}`}><ArrowUp size={16} /></button></form></td></tr>)}
      {!data.products.length && <tr><td colSpan="6"><EmptyState title="No inventory found" /></td></tr>}
    </tbody></table></div></section>
    <section className="panel movement-panel"><PanelTitle eyebrow="AUDIT TRAIL" title="Recent movements" />{data.movements.slice(0, 15).map((move) => <div className="staff-list-row" key={move.id}><span><b>{move.product}</b><small>{move.note || move.action} · {move.user || 'System'} · {new Date(move.createdAt).toLocaleString()}</small></span><strong className={move.quantity > 0 ? 'positive-text' : 'stock-warning'}>{move.quantity > 0 ? '+' : ''}{move.quantity}</strong></div>)}</section>
  </section>

  if (page === 'orders-manage') return <section className="workspace-page">
    <PageTitle eyebrow="ORDER FULFILMENT" title="Orders" subtitle="Create customer orders and progress fulfilment." loading={loading} onBack={onBack} />
    <section className="panel create-order-panel"><PanelTitle eyebrow="NEW CUSTOMER ORDER" title="Build an order" />
      <form className="staff-order-form" onSubmit={createOrder}><label>Customer<select name="customerId" required defaultValue=""><option value="" disabled>Select customer</option>{data.customers.filter((customer) => customer.active).map((customer) => <option value={customer.id} key={customer.id}>{customer.name} · {customer.email}</option>)}</select></label>
        <div className="order-line-editor">{orderItems.map((line, index) => <div className="order-line-edit" key={index}><select aria-label="Product" value={line.productId} required onChange={(event) => setOrderItems((previous) => previous.map((row, rowIndex) => rowIndex === index ? { ...row, productId: event.target.value } : row))}><option value="" disabled>Select product</option>{data.products.map((product) => <option key={product.id} value={product.id} disabled={product.stock < 1}>{product.name} · {money(product.price)} · {product.stock} available</option>)}</select><input aria-label="Quantity" type="number" min="1" required value={line.quantity} onChange={(event) => setOrderItems((previous) => previous.map((row, rowIndex) => rowIndex === index ? { ...row, quantity: event.target.value } : row))} /><button type="button" className="icon-button remove-line" aria-label="Remove order line" disabled={orderItems.length === 1} onClick={() => setOrderItems((previous) => previous.filter((_, rowIndex) => rowIndex !== index))}><X size={16} /></button></div>)}</div>
        <div className="order-form-actions"><button type="button" className="text-button" onClick={() => setOrderItems((previous) => [...previous, { productId: '', quantity: 1 }])}><Plus size={15} /> Add another product</button><div className="order-estimate"><span>Subtotal {money(estimatedSubtotal)}</span><span>Discount −{money(estimatedDiscount)}</span><b>Total {money(estimatedSubtotal - estimatedDiscount)}</b></div><button className="primary-button">Create order <ArrowRight size={15} /></button></div>
      </form>
    </section>
    <section className="panel"><PanelTitle eyebrow="ALL CUSTOMERS" title="Order history" />{data.orders.length ? <div className="staff-list">{data.orders.map((order) => <OrderRow key={order.id} order={order} staff onStatus={updateOrder} />)}</div> : <EmptyState title="No orders yet" />}</section>
  </section>

  if (page === 'customers-manage') return <section className="workspace-page">
    <PageTitle eyebrow="CUSTOMER RECORDS" title="Customers" subtitle="Create, update, and maintain customer accounts." loading={loading} onBack={onBack} />
    <div className="staff-toolbar"><label className="search-field"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, email, or phone" /></label></div>
    {isAdmin && <section className="panel customer-create-panel"><PanelTitle eyebrow="NEW ACCOUNT" title="Add customer" /><CustomerForm onSubmit={saveCustomer} /></section>}
    <section className="panel staff-table-panel"><div className="staff-table-scroll"><table className="staff-table"><thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Access</th><th>Actions</th></tr></thead><tbody>
      {data.customers.map((customer) => <tr key={customer.id}><td><b>{customer.name}</b></td><td>{customer.email}</td><td>{customer.phone}</td><td><span className={`table-status ${customer.active ? 'active' : 'inactive'}`}>{customer.active ? 'Active' : 'Inactive'}</span></td><td className="table-actions">{isAdmin && <><button className="text-button" onClick={() => setEditCustomer(customer)}>Edit</button><button className="cancel-order" onClick={async () => { if (!window.confirm(`Delete ${customer.name}?`)) return; try { await api(`/customers/${customer.id}`, { method: 'DELETE' }); await load(); onNotice('Customer deleted.') } catch (error) { onError(error.message) } }}>Delete</button></>}</td></tr>)}
      {!data.customers.length && <tr><td colSpan="5"><EmptyState title="No customers found" /></td></tr>}
    </tbody></table></div></section>
    {editCustomer && <Modal title="Edit customer" onClose={() => setEditCustomer(null)}><CustomerForm customer={editCustomer} onSubmit={saveCustomer} /></Modal>}
  </section>

  if (page === 'catalog-data') return <section className="workspace-page">
    <PageTitle eyebrow="CATALOG STRUCTURE" title="Categories & suppliers" subtitle="Maintain product relationships without orphaning catalog records." loading={loading} onBack={onBack} />
    <div className="staff-two-column">
      <section className="panel"><PanelTitle eyebrow="PRODUCT GROUPING" title="Categories" />
        <form className="inline-add-form" onSubmit={saveCategory}><input name="name" required minLength="2" placeholder="New category name" /><button className="icon-button" aria-label="Add category"><Plus size={17} /></button></form>
        <label className="search-field directory-search"><Search size={15} /><input value={categorySearch} onChange={(event) => setCategorySearch(event.target.value)} placeholder="Search categories" /></label>
        <div className="staff-list">{categoryRecords.map((item) => <div className="staff-list-row" key={item.id}><span><b>{item.name}</b><small>Category #{item.id}</small></span><button className="text-button" onClick={() => setEditCategory(item)}>Edit</button><button className="cancel-order" onClick={() => deleteRecord('category', item)}>Delete</button></div>)}{!categoryRecords.length && <EmptyState title="No categories found" />}</div>
      </section>
      <section className="panel"><PanelTitle eyebrow="SUPPLY PARTNERS" title="Suppliers" />
        <form className="inline-add-form" onSubmit={saveSupplier}><input name="name" required minLength="2" placeholder="New supplier name" /><button className="icon-button" aria-label="Add supplier"><Plus size={17} /></button></form>
        <label className="search-field directory-search"><Search size={15} /><input value={supplierSearch} onChange={(event) => setSupplierSearch(event.target.value)} placeholder="Search supplier, contact, email" /></label>
        <div className="staff-list">
          {supplierRecords.map((item) => (
            <div className="staff-list-row supplier-staff-row" key={item.id}>
              <div style={{ flex: 1 }}>
                <div>
                  <b>{item.name}</b>
                  <span className={`table-status ${item.active ? 'active' : 'inactive'}`} style={{ marginLeft: 8 }}>
                    {item.active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <small style={{ display: 'block', color: 'var(--muted)', marginTop: 2 }}>
                  {item.contactPerson || 'Contact not set'} · {item.email || 'No email'} · {item.phone || 'No phone'}
                </small>
                <div className="supplier-products-box">
                  <strong>Supplied Products ({item.productCount || (item.products ? item.products.length : 0)}):</strong>{' '}
                  {item.products && item.products.length > 0 ? (
                    item.products.map((p) => (
                      <span key={p.id} className="product-chip">
                        {p.name} ({p.sku})
                      </span>
                    ))
                  ) : (
                    <em style={{ color: 'var(--muted)' }}>No products assigned</em>
                  )}
                </div>
              </div>
              <button className="text-button" onClick={() => setEditSupplier(item)}>Edit</button>
              <button className="cancel-order" onClick={() => deleteRecord('supplier', item)}>Delete</button>
            </div>
          ))}
          {!supplierRecords.length && <EmptyState title="No suppliers found" />}
        </div>
      </section>
    </div>
    {editCategory && <Modal title="Edit category" onClose={() => setEditCategory(null)}><form className="stack-form" onSubmit={saveCategory}><label>Name<input name="name" required minLength="2" defaultValue={editCategory.name} /></label><button className="primary-button">Save category</button></form></Modal>}
    {editSupplier && <Modal title="Edit supplier" onClose={() => setEditSupplier(null)}><form className="stack-form" onSubmit={saveSupplier}><label>Name<input name="name" required minLength="2" defaultValue={editSupplier.name} /></label><label>Contact person<input name="contactPerson" defaultValue={editSupplier.contactPerson} /></label><label>Email<input name="email" type="email" defaultValue={editSupplier.email} /></label><label>Phone<input name="phone" defaultValue={editSupplier.phone} /></label><label>Address<textarea name="address" rows="3" defaultValue={editSupplier.address} /></label><button className="primary-button">Save supplier</button></form></Modal>}
  </section>

  if (page === 'reports') return <section className="workspace-page">
    <PageTitle eyebrow="BUSINESS INTELLIGENCE" title="Reports" subtitle="Filter recorded sales, orders, and inventory movements." loading={loading} onBack={onBack} />
    <div className="report-filters"><label>From<input type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></label><label>To<input type="date" value={to} onChange={(event) => setTo(event.target.value)} /></label><label className="report-search"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Order, customer, email" /></label><button className="secondary-button" onClick={exportCsv}><Download size={15} /> Export CSV</button></div>
    {report && <><div className="metric-grid report-metrics"><Metric label="Matching orders" value={report.orderCount} icon={<FileText size={17} />} /><Metric label="Completed sales" value={money(report.salesTotal)} icon={<ArrowUp size={17} />} /><Metric label="Movements" value={report.movements.length} icon={<Package size={17} />} /></div>
      <section className="panel staff-table-panel"><PanelTitle eyebrow="SALES & ORDERS" title="Filtered order records" /><div className="staff-table-scroll"><table className="staff-table"><thead><tr><th>Order</th><th>Customer</th><th>Date</th><th>Status</th><th>Subtotal</th><th>Total</th></tr></thead><tbody>{report.orders.map((order) => <tr key={order.id}><td><b>{order.number}</b></td><td>{order.customer.name}</td><td>{new Date(order.createdAt).toLocaleDateString()}</td><td><span className={`table-status ${order.status}`}>{order.status}</span></td><td>{money(order.subtotal)}</td><td>{money(order.total)}</td></tr>)}{!report.orders.length && <tr><td colSpan="6"><EmptyState title="No orders match these filters" /></td></tr>}</tbody></table></div></section>
      <section className="panel movement-panel"><PanelTitle eyebrow="INVENTORY HISTORY" title="Matching stock movements" />{report.movements.map((item, index) => <div className="staff-list-row" key={`${item.sku}-${item.createdAt}-${index}`}><span><b>{item.product}</b><small>{item.action} · {item.user || 'System'} · {new Date(item.createdAt).toLocaleString()}</small></span><strong className={item.quantity > 0 ? 'positive-text' : 'stock-warning'}>{item.quantity > 0 ? '+' : ''}{item.quantity}</strong></div>)}{!report.movements.length && <EmptyState title="No movements in this date range" />}</section>
    </>}
  </section>

  if (page === 'settings') return <section className="workspace-page">
    <PageTitle eyebrow="ACCOUNT SETTINGS" title="Settings" subtitle="Update your profile and credentials." onBack={onBack} />
    <div className="staff-two-column"><section className="panel"><PanelTitle eyebrow="PERSONAL DETAILS" title="Profile" /><ProfileForm user={user} onUserUpdate={onUserUpdate} onNotice={onNotice} onError={onError} /></section><section className="panel"><PanelTitle eyebrow="SECURITY" title="Change password" /><PasswordForm onNotice={onNotice} onError={onError} /></section></div>
  </section>

  return null
}

function PageTitle({ eyebrow, title, subtitle, loading, onBack }) {
  return (
    <div className="page-header-group">
      {onBack && (
        <button
          type="button"
          className="page-back-button"
          onClick={onBack}
          aria-label="Go back"
          title="Go back"
        >
          <ArrowLeft size={16} strokeWidth={2.2} />
          <span>Back</span>
        </button>
      )}
      <div className="page-title">
        {eyebrow && <span className="section-kicker">{eyebrow}</span>}
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
        {loading && <span className="page-loading">Loading latest records…</span>}
      </div>
    </div>
  )
}

function PanelTitle({ eyebrow, title }) {
  return <div className="panel-heading"><div><span className="section-kicker">{eyebrow}</span><h2>{title}</h2></div></div>
}

function Metric({ label, value, icon }) {
  return <div className="metric-card"><div className="metric-icon">{icon}</div><span>{label}</span><strong>{value}</strong></div>
}

function EmptyState({ title }) {
  return <div className="empty-state small-empty"><Package size={23} /><h3>{title}</h3></div>
}

function OrderRow({ order, staff = false, onStatus }) {
  const next = { pending: 'confirmed', confirmed: 'processing', processing: 'ready', ready: 'completed', shipped: 'delivered', delivered: 'completed' }[order.status]
  const allowedNext = next && <button className="text-button" onClick={() => onStatus(order, next)}>Mark {next} <ArrowRight size={13} /></button>
  const addr = order.deliveryAddress
  return (
    <div className="staff-list-row order-staff-row">
      <div style={{ flex: 1 }}>
        <div>
          <b>{order.number} · {order.customer.name}</b>
          <small style={{ display: 'block', marginTop: 2, color: 'var(--muted)' }}>
            {order.items.map((item) => `${item.name} ×${item.quantity}`).join(', ')} · {new Date(order.createdAt).toLocaleDateString()}
          </small>
        </div>
        {addr && (
          <div className="order-delivery-address-badge">
            <div>
              <strong>Delivery: {addr.fullName}</strong> ({addr.mobileNumber}{addr.alternatePhone ? `, Alt: ${addr.alternatePhone}` : ''})
            </div>
            <div>
              {[addr.houseNumber, addr.floorNumber, addr.buildingName, addr.streetName].filter(Boolean).join(', ')}, {addr.area}{addr.landmark ? ` (Near ${addr.landmark})` : ''}, {addr.city}, {addr.district}, {addr.state} - <strong>{addr.pinCode}</strong>
            </div>
            {addr.deliveryInstructions && (
              <div className="instruction-note">Note: {addr.deliveryInstructions}</div>
            )}
          </div>
        )}
      </div>
      <span className={`table-status ${order.status}`}>{order.status}</span>
      <strong>{money(order.total)}</strong>
      {staff && (allowedNext || ['pending', 'confirmed'].includes(order.status) ? allowedNext : null)}
      {staff && ['pending', 'confirmed'].includes(order.status) && (
        <button className="cancel-order" onClick={() => onStatus(order, 'cancelled')}>Cancel</button>
      )}
    </div>
  )
}

function Modal({ title, onClose, children }) {
  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="auth-modal"><button className="modal-close icon-button" aria-label="Close" onClick={onClose}><X size={18} /></button><h2>{title}</h2>{children}</section></div>
}

function ProductDialog({ product, categories, suppliers, onClose, onSubmit }) {
  return <Modal title={product ? 'Edit product' : 'Add product'} onClose={onClose}><form className="stack-form" onSubmit={onSubmit}>
    <label>Name<input name="name" required minLength="2" defaultValue={product?.name || ''} /></label>
    <label>SKU<input name="sku" required defaultValue={product?.sku || ''} /></label>
    <label>Price<input name="price" type="number" min="0" step="0.01" required defaultValue={product?.price || ''} /></label>
    {!product && <label>Initial quantity<input name="stock" type="number" min="0" required defaultValue="0" /></label>}
    <label>Low-stock threshold<input name="threshold" type="number" min="0" required defaultValue={product?.threshold ?? 5} /></label>
    <label>Category<select name="categoryId" defaultValue={product?.categoryId || ''}><option value="">Uncategorized</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
    <label>Supplier<select name="supplierId" defaultValue={product?.supplierId || ''}><option value="">Unassigned</option>{suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}</select></label>
    <label>Description<textarea name="description" rows="3" defaultValue={product?.description || ''} /></label>
    <button className="primary-button">Save product</button>
  </form></Modal>
}

function ProductView({ product, onClose }) {
  return <Modal title="Product details" onClose={onClose}><dl className="detail-list"><dt>Name</dt><dd>{product.name}</dd><dt>SKU</dt><dd>{product.sku}</dd><dt>Category</dt><dd>{product.category}</dd><dt>Supplier</dt><dd>{product.supplier}</dd><dt>Price</dt><dd>{money(product.price)}</dd><dt>Quantity</dt><dd>{product.stock}</dd><dt>Status</dt><dd>{product.status}</dd><dt>Description</dt><dd>{product.description || 'No description'}</dd></dl></Modal>
}

function CustomerForm({ customer, onSubmit }) {
  return <form className="stack-form customer-form" onSubmit={onSubmit}>
    <label>Name<input name="name" required minLength="2" defaultValue={customer?.name || ''} /></label>
    <label>Email<input name="email" type="email" required defaultValue={customer?.email || ''} /></label>
    <label>Phone<input name="phone" required defaultValue={customer?.phone || ''} /></label>
    {!customer && <label>Temporary password<input name="password" type="password" minLength="8" required /></label>}
    <button className="primary-button">{customer ? 'Save changes' : 'Create customer'}</button>
  </form>
}

function ProfileForm({ user, onUserUpdate, onNotice, onError }) {
  return <form className="stack-form" onSubmit={async (event) => {
    event.preventDefault()
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries())
    try {
      const result = await api('/profile', { method: 'PATCH', body: JSON.stringify(payload) })
      onUserUpdate(result.user)
      onNotice('Profile saved.')
    } catch (error) { onError(error.message) }
  }}><label>Name<input name="name" required minLength="2" defaultValue={user.name} /></label><label>Email<input value={user.email} readOnly /></label><label>Phone<input name="phone" required defaultValue={user.phone} /></label><button className="primary-button">Save profile</button></form>
}

function PasswordForm({ onNotice, onError }) {
  return <form className="stack-form" onSubmit={async (event) => {
    event.preventDefault()
    const form = event.currentTarget
    const payload = Object.fromEntries(new FormData(form).entries())
    if (payload.newPassword !== payload.confirmPassword) return onError('New passwords do not match.')
    try { await api('/profile/password', { method: 'PATCH', body: JSON.stringify(payload) }); form.reset(); onNotice('Password changed.') } catch (error) { onError(error.message) }
  }}><label>Current password<input name="currentPassword" type="password" required autoComplete="current-password" /></label><label>New password<input name="newPassword" type="password" minLength="8" required autoComplete="new-password" /></label><label>Confirm new password<input name="confirmPassword" type="password" minLength="8" required autoComplete="new-password" /></label><button className="primary-button">Change password</button></form>
}
