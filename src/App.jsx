import { useEffect, useState } from 'react'
import {
  ArrowDown, ArrowLeft, ArrowRight, ArrowUp, BadgeCheck, Box, Check, ChevronDown,
  CircleAlert, ClipboardList, Edit, LayoutDashboard, LogIn, LogOut, MapPin, Menu,
  Package, Plus, Search, ShieldCheck, ShoppingBag, ShoppingCart, SlidersHorizontal,
  Users, X,
} from 'lucide-react'
import { api, money } from './api.js'
import StaffPages from './StaffPages.jsx'

const sampleImages = {
  Laptop: 'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=800&q=80',
  Keyboard: 'https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=800&q=80',
  Mouse: 'https://images.unsplash.com/photo-1527814050087-3793815479db?auto=format&fit=crop&w=800&q=80',
  Monitor: 'https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=800&q=80',
  Headphones: 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=800&q=80',
  Smartphone: 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=800&q=80',
  Printer: 'https://images.unsplash.com/photo-1612815154858-60aa4c59eaa6?auto=format&fit=crop&w=800&q=80',
  Cable: 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=800&q=80',
}

const INDIAN_STATES = [
  'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
  'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
  'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
  'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
  'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
  'Andaman and Nicobar Islands', 'Chandigarh', 'Dadra and Nagar Haveli and Daman and Diu',
  'Delhi', 'Jammu and Kashmir', 'Ladakh', 'Lakshadweep', 'Puducherry',
]

const stockLabel = (item) => item.stock === 0 ? 'Out of stock' : item.stock <= item.threshold ? 'Low stock' : 'In stock'
const PAGE_IDS = new Set([
  'catalog', 'login', 'cart', 'orders', 'profile', 'operations', 'admin',
  'dashboard', 'products', 'inventory', 'orders-manage', 'customers-manage',
  'catalog-data', 'reports', 'settings',
])

function resolvePage(candidate, userRole) {
  if (!candidate || !PAGE_IDS.has(candidate)) {
    return userRole === 'admin' ? 'admin' : userRole === 'staff' ? 'dashboard' : 'catalog'
  }
  if (!userRole) {
    if (['login', 'catalog'].includes(candidate)) return candidate
    return 'login'
  }
  if (userRole === 'admin') {
    if (candidate === 'cart') return 'admin'
    if (candidate === 'login') return 'admin'
    return candidate
  }
  if (userRole === 'staff') {
    if (['admin', 'operations', 'cart'].includes(candidate)) return 'dashboard'
    if (candidate === 'login') return 'dashboard'
    return candidate
  }
  if (userRole === 'customer') {
    const allowed = ['catalog', 'cart', 'orders', 'profile', 'settings']
    if (allowed.includes(candidate)) return candidate
    return 'catalog'
  }
  return 'catalog'
}

function initialPage() {
  const candidate = window.location.hash.slice(1)
  const savedUser = JSON.parse(localStorage.getItem('stockflow-user') || 'null')
  return resolvePage(candidate, savedUser?.role)
}

function validateAddress(form) {
  const errors = {}
  if (!form.fullName || form.fullName.trim().length < 2) {
    errors.fullName = 'Full Name is required (minimum 2 characters)'
  }
  const cleanMobile = (form.mobileNumber || '').replace(/\D/g, '')
  const mobile10 = cleanMobile.length === 12 && cleanMobile.startsWith('91') ? cleanMobile.slice(2)
    : cleanMobile.length === 11 && cleanMobile.startsWith('0') ? cleanMobile.slice(1) : cleanMobile
  if (!mobile10 || !/^[6-9]\d{9}$/.test(mobile10)) {
    errors.mobileNumber = 'Enter a valid 10-digit Indian mobile number (e.g., 9876543210)'
  }
  if (form.alternatePhone && form.alternatePhone.trim()) {
    const cleanAlt = form.alternatePhone.replace(/\D/g, '')
    const alt10 = cleanAlt.length === 12 && cleanAlt.startsWith('91') ? cleanAlt.slice(2)
      : cleanAlt.length === 11 && cleanAlt.startsWith('0') ? cleanAlt.slice(1) : cleanAlt
    if (!/^[6-9]\d{9}$/.test(alt10)) {
      errors.alternatePhone = 'Alternate phone must be a valid 10-digit Indian mobile number'
    }
  }
  if (!form.houseNumber || !form.houseNumber.trim()) {
    errors.houseNumber = 'House/Flat Number is required'
  }
  if (!form.streetName || !form.streetName.trim()) {
    errors.streetName = 'Street Name/Road is required'
  }
  if (!form.area || !form.area.trim()) {
    errors.area = 'Area/Locality is required'
  }
  if (!form.city || !form.city.trim()) {
    errors.city = 'Village/Town/City is required'
  }
  if (!form.district || !form.district.trim()) {
    errors.district = 'District is required'
  }
  if (!form.state || !form.state.trim()) {
    errors.state = 'State is required'
  }
  const cleanPin = (form.pinCode || '').replace(/\D/g, '')
  if (!cleanPin || !/^[1-9]\d{5}$/.test(cleanPin)) {
    errors.pinCode = 'Enter a valid 6-digit Indian PIN code (e.g., 560001)'
  }
  return errors
}

function App() {
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem('stockflow-user') || 'null'))
  const [page, setPage] = useState(initialPage)
  const [pageHistory, setPageHistory] = useState([])
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState([])
  const [suppliers, setSuppliers] = useState([])
  const [supplierDetails, setSupplierDetails] = useState([])
  const [cart, setCart] = useState([])
  const [orders, setOrders] = useState([])
  const [customers, setCustomers] = useState([])
  const [overview, setOverview] = useState(null)
  const [users, setUsers] = useState([])
  const [adminAccountForm, setAdminAccountForm] = useState(null)
  const [movements, setMovements] = useState([])
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [available, setAvailable] = useState(false)
  const [supplier, setSupplier] = useState('')
  const [minimum, setMinimum] = useState('')
  const [maximum, setMaximum] = useState('')
  const [statusFilter, setStatusFilter] = useState('active')
  const [detailProduct, setDetailProduct] = useState(null)
  const [editingProduct, setEditingProduct] = useState(null)
  const [authMode, setAuthMode] = useState('login')
  const [loginRole, setLoginRole] = useState('customer')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [mobileMenu, setMobileMenu] = useState(false)

  // Checkout address & review state
  const [checkoutStep, setCheckoutStep] = useState('cart') // 'cart' | 'address' | 'review'
  const [addressForm, setAddressForm] = useState({
    fullName: user?.name || '',
    mobileNumber: user?.phone || '',
    alternatePhone: '',
    houseNumber: '',
    buildingName: '',
    floorNumber: '',
    streetName: '',
    area: '',
    landmark: '',
    city: '',
    postOffice: '',
    district: '',
    state: '',
    pinCode: '',
    deliveryInstructions: '',
  })
  const [addressErrors, setAddressErrors] = useState({})
  const [submittingOrder, setSubmittingOrder] = useState(false)

  const isStaff = user && ['staff', 'admin'].includes(user.role)
  const isAdmin = user?.role === 'admin'

  useEffect(() => {
    if (user) {
      setAddressForm((prev) => ({
        ...prev,
        fullName: prev.fullName || user.name || '',
        mobileNumber: prev.mobileNumber || user.phone || '',
      }))
    }
  }, [user])

  useEffect(() => {
    const onUnauthorized = () => {
      localStorage.removeItem('stockflow-token')
      localStorage.removeItem('stockflow-user')
      setUser(null)
      setCart([])
      setOrders([])
      setAuthMode('login')
      setPage('login')
      window.location.hash = 'login'
      setError('Your session expired. Please sign in again.')
    }
    window.addEventListener('stockflow:unauthorized', onUnauthorized)
    return () => window.removeEventListener('stockflow:unauthorized', onUnauthorized)
  }, [])

  // Browser hash change listener for Back / Forward buttons
  useEffect(() => {
    const onHashChange = () => {
      const raw = window.location.hash.slice(1)
      const valid = resolvePage(raw, user?.role)
      setPage(valid)
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [user])

  // Synchronize hash with active page
  useEffect(() => {
    const targetHash = `#${page}`
    if (window.location.hash !== targetHash) {
      window.history.replaceState(null, '', targetHash)
    }
  }, [page])

  // Guard routing on state / user role changes
  useEffect(() => {
    const valid = resolvePage(page, user?.role)
    if (valid !== page) {
      setPage(valid)
    }
  }, [page, user])

  const navigateTo = (target) => {
    const destination = resolvePage(target, user?.role)
    if (destination === page) return
    setPageHistory((prev) => [...prev, page])
    setPage(destination)
    window.location.hash = destination
  }

  const handleBack = () => {
    const home = user?.role === 'admin' ? 'admin' : user?.role === 'staff' ? 'dashboard' : 'catalog'
    if (pageHistory.length > 0) {
      const historyCopy = [...pageHistory]
      let prev = historyCopy.pop()
      while (prev && (prev === page || resolvePage(prev, user?.role) !== prev)) {
        prev = historyCopy.pop()
      }
      setPageHistory(historyCopy)
      if (prev) {
        setPage(prev)
        window.location.hash = prev
        return
      }
    }
    setPage(home)
    window.location.hash = home
  }

  const refreshCatalog = async () => {
    const params = new URLSearchParams()
    if (query) params.set('q', query)
    if (category) params.set('category', category)
    if (supplier) params.set('supplier', supplier)
    if (minimum !== '') params.set('min', minimum)
    if (maximum !== '') params.set('max', maximum)
    if (available) params.set('available', 'true')
    if (statusFilter && statusFilter !== 'active') params.set('status', statusFilter)
    const [items, categoryResult, supplierResult] = await Promise.all([
      api(`/products?${params}`), api('/categories'), api('/suppliers'),
    ])
    setProducts(items.products)
    setCategories(categoryResult.categories)
    setSuppliers(supplierResult.suppliers)
  }

  const refreshCart = async () => {
    if (!user || user.role !== 'customer') return setCart([])
    const result = await api('/cart')
    setCart(result.items)
  }

  const refreshOrders = async () => {
    if (!user) return setOrders([])
    const result = await api('/orders')
    setOrders(result.orders)
  }

  const refreshStaff = async () => {
    if (!isStaff) return
    const results = await Promise.all([
      api('/inventory/movements'), api('/orders'), api('/customers'), api('/suppliers/manage'),
    ])
    setMovements(results[0].movements)
    setOrders(results[1].orders)
    setCustomers(results[2].customers)
    setSupplierDetails(results[3].suppliers)
    if (isAdmin) {
      const [stats, accountList] = await Promise.all([api('/admin/overview'), api('/admin/users')])
      setOverview(stats)
      setUsers(accountList.users)
    }
  }

  const reload = async () => {
    setBusy(true)
    setError('')
    try {
      await Promise.all([refreshCatalog(), refreshCart(), refreshOrders(), refreshStaff()])
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { reload() }, [user, page])
  useEffect(() => {
    const timeout = setTimeout(() => refreshCatalog().catch((err) => setError(err.message)), 180)
    return () => clearTimeout(timeout)
  }, [query, category, supplier, minimum, maximum, available, statusFilter])

  const announce = (message) => {
    setNotice(message)
    setError('')
    window.setTimeout(() => setNotice(''), 3200)
  }

  const doAuth = async (event) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const payload = Object.fromEntries(form.entries())
    setBusy(true)
    setError('')
    try {
      const result = await api(authMode === 'register' ? '/auth/register' : '/auth/login', {
        method: 'POST', body: JSON.stringify(payload),
      })
      if (authMode === 'login' && result.user.role !== loginRole) {
        const actualRole = result.user.role === 'admin' ? 'Admin' : result.user.role === 'staff' ? 'Staff' : 'Customer'
        throw new Error(`This account uses the ${actualRole} login option.`)
      }
      localStorage.setItem('stockflow-token', result.token)
      localStorage.setItem('stockflow-user', JSON.stringify(result.user))
      setUser(result.user)
      setAuthMode('login')
      const landing = authMode === 'register' ? 'catalog'
        : result.user.role === 'admin' ? 'admin'
          : result.user.role === 'staff' ? 'dashboard' : 'catalog'
      setPage(landing)
      window.location.hash = landing
      announce(`Welcome, ${result.user.name.split(' ')[0]}.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const signOut = () => {
    localStorage.removeItem('stockflow-token')
    localStorage.removeItem('stockflow-user')
    setUser(null)
    setAuthMode('login')
    setPage('login')
    window.location.hash = 'login'
    announce('You have signed out.')
  }

  const addToCart = async (product) => {
    if (!user) {
      setAuthMode('login')
      setPage('login')
      window.location.hash = 'login'
      return
    }
    try {
      await api('/cart', { method: 'POST', body: JSON.stringify({ productId: product.id, quantity: 1 }) })
      await refreshCart()
      announce(`${product.name} added to your bag.`)
    } catch (err) {
      setError(err.message)
    }
  }

  const changeCart = async (productId, quantity) => {
    try {
      if (quantity < 1) await api(`/cart?productId=${productId}`, { method: 'DELETE' })
      else await api('/cart', { method: 'PATCH', body: JSON.stringify({ productId, quantity }) })
      await refreshCart()
    } catch (err) {
      setError(err.message)
    }
  }

  // Handle Address Step & Review
  const handleProceedToReview = (event) => {
    if (event) event.preventDefault()
    const errs = validateAddress(addressForm)
    setAddressErrors(errs)
    if (Object.keys(errs).length > 0) {
      setError('Please check the required fields in the delivery address.')
      return
    }
    setError('')
    setCheckoutStep('review')
  }

  const confirmOrder = async () => {
    if (submittingOrder) return
    const errs = validateAddress(addressForm)
    if (Object.keys(errs).length > 0) {
      setAddressErrors(errs)
      setCheckoutStep('address')
      setError('Please provide a complete and valid delivery address.')
      return
    }
    setSubmittingOrder(true)
    setError('')
    try {
      const result = await api('/orders', {
        method: 'POST',
        body: JSON.stringify({ deliveryAddress: addressForm }),
      })
      await reload()
      setCheckoutStep('cart')
      navigateTo('orders')
      announce(`Order ${result.order.number} placed successfully! Dispatch within 24h.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmittingOrder(false)
    }
  }

  const cancelOrder = async (orderId) => {
    try {
      await api(`/orders/${orderId}/status`, { method: 'PATCH', body: JSON.stringify({ status: 'cancelled' }) })
      await reload()
      announce('Order cancelled. Inventory has been restored.')
    } catch (err) {
      setError(err.message)
    }
  }

  const updateStatus = async (orderId, status) => {
    try {
      await api(`/orders/${orderId}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })
      await reload()
      announce(`Order status updated to ${status}.`)
    } catch (err) {
      setError(err.message)
    }
  }

  const changeInventory = async (event, product) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const action = form.get('action')
    const quantity = Number(form.get('quantity'))
    try {
      await api(`/inventory/${product.id}`, { method: 'POST', body: JSON.stringify({ action, quantity, note: form.get('note') }) })
      event.currentTarget.reset()
      await reload()
      announce('Inventory updated and movement recorded.')
    } catch (err) {
      setError(err.message)
    }
  }

  const createProduct = async (event) => {
    event.preventDefault()
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries())
    payload.price = Number(payload.price)
    payload.stock = Number(payload.stock || 0)
    payload.threshold = Number(payload.threshold || 5)
    payload.categoryId = payload.categoryId ? Number(payload.categoryId) : null
    payload.supplierId = payload.supplierId ? Number(payload.supplierId) : null
    try {
      await api('/products/manage', { method: 'POST', body: JSON.stringify(payload) })
      event.currentTarget.reset()
      await reload()
      announce('Product created.')
    } catch (err) {
      setError(err.message)
    }
  }

  const saveProduct = async (event) => {
    event.preventDefault()
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries())
    payload.id = editingProduct.id
    payload.price = Number(payload.price)
    payload.threshold = Number(payload.threshold)
    payload.categoryId = payload.categoryId ? Number(payload.categoryId) : null
    payload.supplierId = payload.supplierId ? Number(payload.supplierId) : null
    try {
      await api('/products/manage', { method: 'PATCH', body: JSON.stringify(payload) })
      setEditingProduct(null)
      await reload()
      announce('Product details updated.')
    } catch (err) {
      setError(err.message)
    }
  }

  const archiveProduct = async (product) => {
    if (!window.confirm(`Archive ${product.name}? It will no longer appear in the catalog.`)) return
    try {
      await api(`/products/manage?id=${product.id}`, { method: 'DELETE' })
      await reload()
      announce(`${product.name} archived.`)
    } catch (err) {
      setError(err.message)
    }
  }

  const updateProfile = async (event) => {
    event.preventDefault()
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries())
    try {
      const result = await api('/profile', { method: 'PATCH', body: JSON.stringify(payload) })
      setUser(result.user)
      localStorage.setItem('stockflow-user', JSON.stringify(result.user))
      announce('Profile updated.')
    } catch (err) {
      setError(err.message)
    }
  }

  const changeCustomerPassword = async (event) => {
    event.preventDefault()
    const form = event.currentTarget
    const payload = Object.fromEntries(new FormData(form).entries())
    if (payload.newPassword !== payload.confirmPassword) {
      return setError('New passwords do not match.')
    }
    try {
      await api('/profile/password', { method: 'PATCH', body: JSON.stringify(payload) })
      form.reset()
      announce('Password updated successfully.')
    } catch (err) {
      setError(err.message)
    }
  }

  const manageSimpleRecord = async (event, path) => {
    event.preventDefault()
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries())
    try {
      await api(path, { method: 'POST', body: JSON.stringify(payload) })
      event.currentTarget.reset()
      await reload()
      announce('Record added.')
    } catch (err) {
      setError(err.message)
    }
  }

  const openProductDetails = async (item) => {
    try {
      const result = await api(`/products/${item.id}`)
      setDetailProduct(result.product)
    } catch (err) {
      setError(err.message)
    }
  }

  const changeAccount = async (account, field, value) => {
    try {
      await api(`/admin/users/${account.id}`, { method: 'PATCH', body: JSON.stringify({ [field]: value }) })
      await refreshStaff()
      announce('Account updated.')
    } catch (err) {
      setError(err.message)
    }
  }

  const saveAdminAccount = async (event) => {
    event.preventDefault()
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries())
    const editing = Boolean(adminAccountForm?.id)
    if (!payload.password) delete payload.password
    if (payload.active) payload.active = payload.active === 'true'
    if (!editing) payload.role = 'staff'
    try {
      await api(editing ? `/admin/users/${adminAccountForm.id}` : '/admin/users', {
        method: editing ? 'PATCH' : 'POST', body: JSON.stringify(payload),
      })
      setAdminAccountForm(null)
      await refreshStaff()
      announce(editing ? 'Staff account updated.' : 'Staff account created.')
    } catch (err) {
      setError(err.message)
    }
  }

  const cartCount = cart.reduce((sum, row) => sum + row.quantity, 0)
  const cartSubtotal = cart.reduce((sum, row) => sum + row.lineTotal, 0)
  const cartDiscount = cartSubtotal >= 5000 ? Math.round(cartSubtotal * 0.05 * 100) / 100 : cartSubtotal >= 3500 ? 200 : 0

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#catalog" onClick={(e) => { e.preventDefault(); navigateTo('catalog') }}>
          <span className="brand-mark"><Box size={19} strokeWidth={2.2} /></span>
          <span>stock<span>flow</span></span>
        </a>
        <button className="mobile-toggle icon-button" aria-label="Toggle navigation" onClick={() => setMobileMenu(!mobileMenu)}>
          <Menu size={20} />
        </button>

        <nav className={mobileMenu ? 'main-nav open' : 'main-nav'}>
          <button className={page === 'catalog' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('catalog')}>Shop</button>

          {!user && (
            <button
              className={page === 'login' ? 'nav-link active' : 'nav-link'}
              onClick={() => { setAuthMode('login'); navigateTo('login') }}
            >
              Login
            </button>
          )}

          {user?.role === 'customer' && (
            <button className={page === 'orders' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('orders')}>
              My orders
            </button>
          )}

          {/* Dedicated Admin Navigation Menu */}
          {isAdmin && (
            <>
              <button className={page === 'admin' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('admin')}>Overview</button>
              <button className={page === 'products' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('products')}>Products</button>
              <button className={page === 'inventory' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('inventory')}>Inventory</button>
              <button className={page === 'orders-manage' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('orders-manage')}>Orders</button>
              <button className={page === 'customers-manage' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('customers-manage')}>Customers</button>
              <button className={page === 'catalog-data' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('catalog-data')}>Categories & suppliers</button>
              <button className={page === 'reports' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('reports')}>Reports</button>
              <button className={page === 'operations' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('operations')}>Operations</button>
            </>
          )}

          {/* Dedicated Staff Navigation Menu (Admin pages like Overview/Admin excluded) */}
          {isStaff && !isAdmin && (
            <>
              <button className={page === 'dashboard' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('dashboard')}>Dashboard</button>
              <button className={page === 'products' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('products')}>Products</button>
              <button className={page === 'inventory' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('inventory')}>Inventory</button>
              <button className={page === 'orders-manage' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('orders-manage')}>Orders</button>
              <button className={page === 'customers-manage' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('customers-manage')}>Customers</button>
              <button className={page === 'catalog-data' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('catalog-data')}>Categories & suppliers</button>
              <button className={page === 'reports' ? 'nav-link active' : 'nav-link'} onClick={() => navigateTo('reports')}>Reports</button>
            </>
          )}

          {user && (
            <button
              className={page === 'settings' || page === 'profile' ? 'nav-link active' : 'nav-link'}
              onClick={() => navigateTo('settings')}
            >
              Settings
            </button>
          )}
        </nav>

        <div className="top-actions">
          {user?.role === 'customer' && (
            <button className="bag-button" aria-label={`Shopping bag, ${cartCount} items`} onClick={() => navigateTo('cart')}>
              <ShoppingBag size={18} />
              <span>Bag</span>
              <b>{cartCount}</b>
            </button>
          )}
          {user ? (
            <div className="account-control">
              <button className="profile-link" onClick={() => navigateTo(isStaff ? 'settings' : 'profile')}>
                <span className="avatar">{user.name.slice(0, 1).toUpperCase()}</span>
                <span className="account-name">{user.name.split(' ')[0]}</span>
              </button>
              <button className="icon-button signout" aria-label="Sign out" title="Sign out" onClick={signOut}>
                <LogOut size={17} />
              </button>
            </div>
          ) : (
            <button className="login-button" onClick={() => { setAuthMode('login'); navigateTo('login') }}>
              <LogIn size={16} /> Sign in
            </button>
          )}
        </div>
      </header>

      <main>
        {notice && (
          <div className="toast success-toast">
            <BadgeCheck size={17} />{notice}
            <button className="icon-button" aria-label="Dismiss" onClick={() => setNotice('')}><X size={15} /></button>
          </div>
        )}
        {error && page !== 'login' && (
          <div className="toast error-toast">
            <CircleAlert size={17} />{error}
            <button className="icon-button" aria-label="Dismiss" onClick={() => setError('')}><X size={15} /></button>
          </div>
        )}
        {busy && <div className="loading-line" />}

        {/* Staff & Admin Pages Component */}
        {((isStaff && ['dashboard', 'products', 'inventory', 'orders-manage', 'customers-manage', 'catalog-data', 'reports'].includes(page)) || (user && page === 'settings')) && (
          <StaffPages
            page={page}
            user={user}
            onNavigate={navigateTo}
            onBack={handleBack}
            onUserUpdate={(updatedUser) => {
              setUser(updatedUser)
              localStorage.setItem('stockflow-user', JSON.stringify(updatedUser))
            }}
            onNotice={announce}
            onError={setError}
          />
        )}

        {/* Login Page */}
        {page === 'login' && !user && (
          <section className="login-page">
            <div className="login-aside">
              <span className="login-kicker">STOCKFLOW · WORKSPACE</span>
              <div className="login-aside-mark"><Box size={25} /></div>
              <h1>Inventory,<br /><em>in good order.</em></h1>
              <p>One clear place for products, stock, and orders.</p>
              <div className="login-aside-rule" />
              <span className="login-aside-foot">SECURE ACCESS · ROLE BASED</span>
            </div>
            <div className="login-form-panel">
              <div className="login-form-heading">
                <span className="section-kicker">{authMode === 'register' ? 'CUSTOMER REGISTRATION' : 'ACCOUNT ACCESS'}</span>
                <h2>{authMode === 'register' ? 'Create your account' : 'Welcome back'}</h2>
                <p>{authMode === 'register' ? 'Create a customer account to shop and follow your orders.' : 'Sign in to continue to your StockFlow workspace.'}</p>
              </div>
              {authMode === 'login' && (
                <fieldset className="login-role-fieldset">
                  <legend>Sign in as</legend>
                  <div className="login-role-options">
                    {[['customer', 'Customer'], ['staff', 'Staff'], ['admin', 'Admin']].map(([role, label]) => (
                      <button
                        key={role}
                        type="button"
                        aria-pressed={loginRole === role}
                        className={loginRole === role ? 'login-role-option selected' : 'login-role-option'}
                        onClick={() => { setLoginRole(role); setError('') }}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </fieldset>
              )}
              <form className="stack-form login-form" onSubmit={doAuth}>
                {authMode === 'register' && (
                  <>
                    <label>Full name<input name="name" required minLength="2" autoComplete="name" placeholder="Your name" /></label>
                    <label>Phone number<input name="phone" required autoComplete="tel" placeholder="+91 98765 43210" /></label>
                  </>
                )}
                <label>Email address<input name="email" required type="email" autoComplete="email" placeholder="you@example.com" /></label>
                <label>Password<input name="password" required type="password" minLength="8" autoComplete={authMode === 'register' ? 'new-password' : 'current-password'} placeholder="At least 8 characters" /></label>
                <button className="primary-button full-button" disabled={busy}>
                  {authMode === 'register' ? 'Create account' : `Sign in as ${loginRole === 'admin' ? 'Admin' : loginRole === 'staff' ? 'Staff' : 'Customer'}`} <ArrowRight size={16} />
                </button>
              </form>
              {authMode === 'register' ? (
                <div className="login-switch">Already registered? <button onClick={() => { setAuthMode('login'); setLoginRole('customer'); setError('') }}>Sign in</button></div>
              ) : loginRole === 'customer' ? (
                <div className="login-switch">New customer? <button onClick={() => { setAuthMode('register'); setLoginRole('customer'); setError('') }}>Create an account</button></div>
              ) : loginRole === 'staff' ? (
                <div className="login-access-note"><span>Staff accounts are created by the Administrator.</span><button onClick={() => { setLoginRole('staff'); setError('') }}>Return to Staff Login</button></div>
              ) : (
                <div className="login-access-note"><span>Administrator access must be configured securely.</span><button onClick={() => { setLoginRole('admin'); setError('') }}>Return to Admin Login</button></div>
              )}
              {error && <div className="inline-error login-error">{error}</div>}
            </div>
          </section>
        )}

        {/* Catalog / Shop */}
        {page === 'catalog' && (
          <>
            <section className="catalog-intro">
              <div className="eyebrow"><span className="live-dot" /> STOCKFLOW SUPPLY</div>
              <h1>Good tools.<br /><em>Ready when you are.</em></h1>
              <p>Thoughtful equipment for people who make things work.</p>
              <div className="catalog-stats"><span><strong>{products.length.toString().padStart(2, '0')}</strong> products</span><i /><span>Dispatch in <strong>24h</strong></span></div>
            </section>
            <section className="catalog-section">
              <div className="catalog-heading">
                <div><span className="section-kicker">THE COLLECTION</span><h2>Shop equipment</h2></div>
                <span className="results-count">{products.length} items</span>
              </div>
              <div className="filter-row">
                <label className="search-field"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search products or SKU" /></label>
                <label className="select-wrap"><SlidersHorizontal size={16} /><select value={category} onChange={(event) => setCategory(event.target.value)}><option value="">All categories</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><ChevronDown size={14} /></label>
                <label className="select-wrap supplier-select"><select value={supplier} onChange={(event) => setSupplier(event.target.value)}><option value="">All suppliers</option>{suppliers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><ChevronDown size={14} /></label>
                <label className="select-wrap status-select"><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="active">Active products</option><option value="all">All statuses</option><option value="inactive">Archived / Inactive</option></select><ChevronDown size={14} /></label>
                <label className="price-filter"><span>₹</span><input aria-label="Minimum price" type="number" min="0" placeholder="Min" value={minimum} onChange={(event) => setMinimum(event.target.value)} /><i /> <input aria-label="Maximum price" type="number" min="0" placeholder="Max" value={maximum} onChange={(event) => setMaximum(event.target.value)} /></label>
                <label className="availability-toggle"><input type="checkbox" checked={available} onChange={(event) => setAvailable(event.target.checked)} /><span className="toggle-track" /><span>In stock only</span></label>
              </div>
              {products.length ? (
                <div className="product-grid">
                  {products.map((item) => (
                    <article className="product-card" key={item.id}>
                      <div className="product-visual">
                        <img src={item.imageUrl || sampleImages[item.name.split(' ')[0]] || sampleImages.Cable} alt={item.name} loading="lazy" />
                        <span className={`availability-badge ${item.status !== 'active' ? 'none' : item.stock === 0 ? 'none' : item.stock <= item.threshold ? 'low' : ''}`}><i />{item.status !== 'active' ? 'Archived' : stockLabel(item)}</span>
                        <span className="product-sku">{item.sku}</span>
                      </div>
                      <div className="product-meta"><span>{item.category}</span><span>{item.status !== 'active' ? 'Archived' : `${item.stock} units`}</span></div>
                      <div className="product-title-row">
                        <h3>{item.name}</h3>
                        <button className="add-button" aria-label={`Add ${item.name} to bag`} disabled={!item.stock || item.status !== 'active'} onClick={() => addToCart(item)}><Plus size={17} /></button>
                      </div>
                      <div className="product-bottom">
                        <strong>{money(item.price)}</strong>
                        <button className="detail-link" onClick={() => openProductDetails(item)}>Details <ArrowRight size={13} /></button>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-state"><Package size={28} /><h3>No products found</h3><p>Try another search or category.</p></div>
              )}
            </section>
          </>
        )}

        {/* Customer Cart & Indian Delivery Address Checkout Flow */}
        {page === 'cart' && (
          <section className="workspace-page">
            {checkoutStep === 'cart' && (
              <>
                <PageTitle
                  eyebrow="YOUR SELECTION"
                  title="Shopping bag"
                  subtitle={`${cartCount} item${cartCount === 1 ? '' : 's'} ready for checkout`}
                  onBack={() => navigateTo('catalog')}
                />
                {!cart.length ? (
                  <div className="empty-state">
                    <ShoppingCart size={30} />
                    <h3>Your bag is empty</h3>
                    <p>Find something useful in the collection.</p>
                    <button className="primary-button" onClick={() => navigateTo('catalog')}>
                      Browse products <ArrowRight size={16} />
                    </button>
                  </div>
                ) : (
                  <div className="cart-layout">
                    <div className="cart-lines">
                      {cart.map((row) => (
                        <div className="cart-line" key={row.product.id}>
                          <img src={row.product.imageUrl || sampleImages[row.product.name.split(' ')[0]] || sampleImages.Cable} alt="" />
                          <div className="cart-product">
                            <span>{row.product.category} · {row.product.sku}</span>
                            <h3>{row.product.name}</h3>
                            <b>{money(row.product.price)}</b>
                          </div>
                          <div className="quantity-control">
                            <button aria-label="Decrease quantity" onClick={() => changeCart(row.product.id, row.quantity - 1)}>−</button>
                            <span>{row.quantity}</span>
                            <button aria-label="Increase quantity" disabled={row.quantity >= row.product.stock} onClick={() => changeCart(row.product.id, row.quantity + 1)}>+</button>
                          </div>
                          <strong className="line-total">{money(row.lineTotal)}</strong>
                        </div>
                      ))}
                    </div>
                    <aside className="summary-panel">
                      <span className="section-kicker">ORDER SUMMARY</span>
                      <div className="summary-row"><span>Subtotal</span><b>{money(cartSubtotal)}</b></div>
                      <div className="summary-row"><span>Volume discount</span><b className="discount">− {money(cartDiscount)}</b></div>
                      <div className="summary-total"><span>Total</span><strong>{money(cartSubtotal - cartDiscount)}</strong></div>
                      <button className="primary-button full-button" disabled={busy} onClick={() => setCheckoutStep('address')}>
                        Proceed to Delivery Address <ArrowRight size={16} />
                      </button>
                      <p className="secure-note"><ShieldCheck size={14} /> Free delivery across India</p>
                    </aside>
                  </div>
                )}
              </>
            )}

            {checkoutStep === 'address' && (
              <div className="checkout-container">
                <PageTitle
                  eyebrow="CHECKOUT · STEP 1 OF 2"
                  title="Delivery Address"
                  subtitle="Please provide your shipping and contact details within India."
                  onBack={() => setCheckoutStep('cart')}
                />
                <div className="checkout-steps-nav">
                  <span className="checkout-step-pill completed"><Check size={12} /> 1. Bag</span>
                  <span>→</span>
                  <span className="checkout-step-pill active">2. Delivery Address</span>
                  <span>→</span>
                  <span className="checkout-step-pill">3. Order Review</span>
                </div>

                <form className="checkout-form-container" onSubmit={handleProceedToReview}>
                  {/* Section 1: Contact Details */}
                  <div className="checkout-card">
                    <div className="checkout-card-heading">
                      <span className="section-kicker">CONTACT DETAILS</span>
                      <h3>Recipient Information</h3>
                    </div>
                    <div className="form-grid-2">
                      <div className={`field-group ${addressErrors.fullName ? 'has-error' : ''}`}>
                        <label>Full Name <span className="required-star">*</span></label>
                        <input
                          type="text"
                          required
                          value={addressForm.fullName}
                          placeholder="e.g. Rajesh Kumar"
                          onChange={(e) => {
                            setAddressForm({ ...addressForm, fullName: e.target.value })
                            if (addressErrors.fullName) setAddressErrors({ ...addressErrors, fullName: '' })
                          }}
                        />
                        {addressErrors.fullName && <span className="field-error-text">{addressErrors.fullName}</span>}
                      </div>

                      <div className={`field-group ${addressErrors.mobileNumber ? 'has-error' : ''}`}>
                        <label>Mobile Number <span className="required-star">*</span></label>
                        <input
                          type="tel"
                          required
                          maxLength="15"
                          value={addressForm.mobileNumber}
                          placeholder="10-digit number (e.g. 9876543210)"
                          onChange={(e) => {
                            setAddressForm({ ...addressForm, mobileNumber: e.target.value })
                            if (addressErrors.mobileNumber) setAddressErrors({ ...addressErrors, mobileNumber: '' })
                          }}
                        />
                        {addressErrors.mobileNumber && <span className="field-error-text">{addressErrors.mobileNumber}</span>}
                      </div>

                      <div className={`field-group ${addressErrors.alternatePhone ? 'has-error' : ''}`}>
                        <label>Alternate Mobile Number <span className="optional-tag">(Optional)</span></label>
                        <input
                          type="tel"
                          maxLength="15"
                          value={addressForm.alternatePhone}
                          placeholder="Alternate 10-digit number"
                          onChange={(e) => {
                            setAddressForm({ ...addressForm, alternatePhone: e.target.value })
                            if (addressErrors.alternatePhone) setAddressErrors({ ...addressErrors, alternatePhone: '' })
                          }}
                        />
                        {addressErrors.alternatePhone && <span className="field-error-text">{addressErrors.alternatePhone}</span>}
                      </div>
                    </div>
                  </div>

                  {/* Section 2: Delivery Address */}
                  <div className="checkout-card">
                    <div className="checkout-card-heading">
                      <span className="section-kicker">SHIPPING LOCATION</span>
                      <h3>Delivery Address</h3>
                    </div>
                    <div className="form-grid-3">
                      <div className={`field-group ${addressErrors.houseNumber ? 'has-error' : ''}`}>
                        <label>House / Flat No. <span className="required-star">*</span></label>
                        <input
                          type="text"
                          required
                          value={addressForm.houseNumber}
                          placeholder="e.g. Flat 402, Door 12"
                          onChange={(e) => {
                            setAddressForm({ ...addressForm, houseNumber: e.target.value })
                            if (addressErrors.houseNumber) setAddressErrors({ ...addressErrors, houseNumber: '' })
                          }}
                        />
                        {addressErrors.houseNumber && <span className="field-error-text">{addressErrors.houseNumber}</span>}
                      </div>

                      <div className="field-group">
                        <label>Building / Apartment Name <span className="optional-tag">(Optional)</span></label>
                        <input
                          type="text"
                          value={addressForm.buildingName}
                          placeholder="e.g. Lotus Greens"
                          onChange={(e) => setAddressForm({ ...addressForm, buildingName: e.target.value })}
                        />
                      </div>

                      <div className="field-group">
                        <label>Floor Number <span className="optional-tag">(Optional)</span></label>
                        <input
                          type="text"
                          value={addressForm.floorNumber}
                          placeholder="e.g. 4th Floor"
                          onChange={(e) => setAddressForm({ ...addressForm, floorNumber: e.target.value })}
                        />
                      </div>
                    </div>

                    <div className="form-grid-2" style={{ marginTop: 16 }}>
                      <div className={`field-group ${addressErrors.streetName ? 'has-error' : ''}`}>
                        <label>Street Name / Road <span className="required-star">*</span></label>
                        <input
                          type="text"
                          required
                          value={addressForm.streetName}
                          placeholder="e.g. 100ft Road, MG Road"
                          onChange={(e) => {
                            setAddressForm({ ...addressForm, streetName: e.target.value })
                            if (addressErrors.streetName) setAddressErrors({ ...addressErrors, streetName: '' })
                          }}
                        />
                        {addressErrors.streetName && <span className="field-error-text">{addressErrors.streetName}</span>}
                      </div>

                      <div className={`field-group ${addressErrors.area ? 'has-error' : ''}`}>
                        <label>Area / Locality <span className="required-star">*</span></label>
                        <input
                          type="text"
                          required
                          value={addressForm.area}
                          placeholder="e.g. Indiranagar, Sector 14"
                          onChange={(e) => {
                            setAddressForm({ ...addressForm, area: e.target.value })
                            if (addressErrors.area) setAddressErrors({ ...addressErrors, area: '' })
                          }}
                        />
                        {addressErrors.area && <span className="field-error-text">{addressErrors.area}</span>}
                      </div>
                    </div>

                    <div className="form-grid-3" style={{ marginTop: 16 }}>
                      <div className="field-group">
                        <label>Landmark <span className="optional-tag">(Optional)</span></label>
                        <input
                          type="text"
                          value={addressForm.landmark}
                          placeholder="e.g. Near Metro Station"
                          onChange={(e) => setAddressForm({ ...addressForm, landmark: e.target.value })}
                        />
                      </div>

                      <div className={`field-group ${addressErrors.city ? 'has-error' : ''}`}>
                        <label>Village / Town / City <span className="required-star">*</span></label>
                        <input
                          type="text"
                          required
                          value={addressForm.city}
                          placeholder="e.g. Bengaluru"
                          onChange={(e) => {
                            setAddressForm({ ...addressForm, city: e.target.value })
                            if (addressErrors.city) setAddressErrors({ ...addressErrors, city: '' })
                          }}
                        />
                        {addressErrors.city && <span className="field-error-text">{addressErrors.city}</span>}
                      </div>

                      <div className="field-group">
                        <label>Post Office <span className="optional-tag">(Optional)</span></label>
                        <input
                          type="text"
                          value={addressForm.postOffice}
                          placeholder="e.g. Indiranagar PO"
                          onChange={(e) => setAddressForm({ ...addressForm, postOffice: e.target.value })}
                        />
                      </div>
                    </div>

                    <div className="form-grid-3" style={{ marginTop: 16 }}>
                      <div className={`field-group ${addressErrors.district ? 'has-error' : ''}`}>
                        <label>District <span className="required-star">*</span></label>
                        <input
                          type="text"
                          required
                          value={addressForm.district}
                          placeholder="e.g. Bengaluru Urban"
                          onChange={(e) => {
                            setAddressForm({ ...addressForm, district: e.target.value })
                            if (addressErrors.district) setAddressErrors({ ...addressErrors, district: '' })
                          }}
                        />
                        {addressErrors.district && <span className="field-error-text">{addressErrors.district}</span>}
                      </div>

                      <div className={`field-group ${addressErrors.state ? 'has-error' : ''}`}>
                        <label>State <span className="required-star">*</span></label>
                        <select
                          required
                          value={addressForm.state}
                          onChange={(e) => {
                            setAddressForm({ ...addressForm, state: e.target.value })
                            if (addressErrors.state) setAddressErrors({ ...addressErrors, state: '' })
                          }}
                        >
                          <option value="">Select Indian State / UT</option>
                          {INDIAN_STATES.map((st) => (
                            <option key={st} value={st}>{st}</option>
                          ))}
                        </select>
                        {addressErrors.state && <span className="field-error-text">{addressErrors.state}</span>}
                      </div>

                      <div className={`field-group ${addressErrors.pinCode ? 'has-error' : ''}`}>
                        <label>PIN Code <span className="required-star">*</span></label>
                        <input
                          type="text"
                          required
                          maxLength="6"
                          value={addressForm.pinCode}
                          placeholder="6 digits (e.g. 560038)"
                          onChange={(e) => {
                            setAddressForm({ ...addressForm, pinCode: e.target.value })
                            if (addressErrors.pinCode) setAddressErrors({ ...addressErrors, pinCode: '' })
                          }}
                        />
                        {addressErrors.pinCode && <span className="field-error-text">{addressErrors.pinCode}</span>}
                      </div>
                    </div>
                  </div>

                  {/* Section 3: Additional Information */}
                  <div className="checkout-card">
                    <div className="checkout-card-heading">
                      <span className="section-kicker">ADDITIONAL DETAILS</span>
                      <h3>Delivery Instructions</h3>
                    </div>
                    <div className="field-group">
                      <label>Instructions for Delivery Partner <span className="optional-tag">(Optional)</span></label>
                      <textarea
                        rows="2"
                        value={addressForm.deliveryInstructions}
                        placeholder="e.g. Leave with security guard, call before arrival, ring doorbell twice"
                        onChange={(e) => setAddressForm({ ...addressForm, deliveryInstructions: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="checkout-actions-row">
                    <button type="button" className="text-button" onClick={() => setCheckoutStep('cart')}>
                      ← Back to Shopping Bag
                    </button>
                    <button type="submit" className="primary-button">
                      Review Order <ArrowRight size={16} />
                    </button>
                  </div>
                </form>
              </div>
            )}

            {checkoutStep === 'review' && (
              <div className="checkout-container">
                <PageTitle
                  eyebrow="CHECKOUT · STEP 2 OF 2"
                  title="Review & Confirm Order"
                  subtitle="Verify your shipping address and items before final submission."
                  onBack={() => setCheckoutStep('address')}
                />
                <div className="checkout-steps-nav">
                  <span className="checkout-step-pill completed"><Check size={12} /> 1. Bag</span>
                  <span>→</span>
                  <span className="checkout-step-pill completed"><Check size={12} /> 2. Delivery Address</span>
                  <span>→</span>
                  <span className="checkout-step-pill active">3. Order Review</span>
                </div>

                <div className="cart-layout">
                  <div>
                    {/* Delivery Address Card with Edit button */}
                    <div className="order-review-box">
                      <div className="review-header-row">
                        <h4><MapPin size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Delivery Address</h4>
                        <button type="button" className="text-button" onClick={() => setCheckoutStep('address')}>
                          <Edit size={14} /> Edit Address
                        </button>
                      </div>
                      <div className="review-address-details">
                        <div className="review-recipient-name">{addressForm.fullName}</div>
                        <div className="review-phone">
                          Mobile: {addressForm.mobileNumber}
                          {addressForm.alternatePhone && ` | Alt: ${addressForm.alternatePhone}`}
                        </div>
                        <div style={{ marginTop: 6 }}>
                          {[addressForm.houseNumber, addressForm.floorNumber, addressForm.buildingName, addressForm.streetName].filter(Boolean).join(', ')}
                        </div>
                        <div>
                          {addressForm.area}{addressForm.landmark ? ` (Landmark: ${addressForm.landmark})` : ''}
                        </div>
                        <div>
                          {addressForm.city}{addressForm.postOffice ? `, PO: ${addressForm.postOffice}` : ''}, {addressForm.district}, {addressForm.state} - <strong>{addressForm.pinCode}</strong>
                        </div>
                        {addressForm.deliveryInstructions && (
                          <div style={{ marginTop: 8, fontStyle: 'italic', color: '#66746a' }}>
                            Note: {addressForm.deliveryInstructions}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Order Items Preview */}
                    <div className="order-review-box">
                      <div className="review-header-row">
                        <h4>Items in Order ({cartCount})</h4>
                      </div>
                      <div className="cart-lines">
                        {cart.map((row) => (
                          <div className="cart-line" key={row.product.id} style={{ borderBottom: '1px solid var(--line)', paddingBottom: 12 }}>
                            <img src={row.product.imageUrl || sampleImages[row.product.name.split(' ')[0]] || sampleImages.Cable} alt="" style={{ width: 50, height: 50, objectFit: 'cover', borderRadius: 4 }} />
                            <div className="cart-product">
                              <span>{row.product.category} · {row.product.sku}</span>
                              <h3>{row.product.name}</h3>
                              <b>{money(row.product.price)} × {row.quantity}</b>
                            </div>
                            <strong className="line-total">{money(row.lineTotal)}</strong>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <aside className="summary-panel">
                    <span className="section-kicker">FINAL CONFIRMATION</span>
                    <div className="summary-row"><span>Subtotal</span><b>{money(cartSubtotal)}</b></div>
                    <div className="summary-row"><span>Volume discount</span><b className="discount">− {money(cartDiscount)}</b></div>
                    <div className="summary-total"><span>Total</span><strong>{money(cartSubtotal - cartDiscount)}</strong></div>

                    <button
                      className="primary-button full-button"
                      disabled={submittingOrder}
                      onClick={confirmOrder}
                    >
                      {submittingOrder ? 'Placing Order…' : 'Confirm & Place Order'} <ArrowRight size={16} />
                    </button>

                    <button
                      type="button"
                      className="text-button"
                      style={{ marginTop: 12, width: '100%', justifyContent: 'center' }}
                      onClick={() => setCheckoutStep('address')}
                    >
                      ← Modify Delivery Address
                    </button>

                    <p className="secure-note"><ShieldCheck size={14} /> Inventory reserved upon confirmation</p>
                  </aside>
                </div>
              </div>
            )}
          </section>
        )}

        {/* Customer Orders */}
        {page === 'orders' && (
          <section className="workspace-page">
            <PageTitle
              eyebrow="ACCOUNT"
              title="Your orders"
              subtitle="Track orders and revisit past purchases."
              onBack={handleBack}
            />
            {orders.length ? (
              <div className="order-list">
                {orders.map((order) => (
                  <OrderCard key={order.id} order={order} customer onCancel={() => cancelOrder(order.id)} />
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <ClipboardList size={30} />
                <h3>No orders yet</h3>
                <p>Your placed orders will appear here.</p>
                <button className="primary-button" onClick={() => navigateTo('catalog')}>
                  Explore products <ArrowRight size={16} />
                </button>
              </div>
            )}
          </section>
        )}

        {/* Customer Profile */}
        {page === 'profile' && user && (
          <section className="workspace-page profile-page">
            <PageTitle
              eyebrow="ACCOUNT SETTINGS"
              title="Your profile"
              subtitle="Keep your contact details and security credentials up to date."
              onBack={handleBack}
            />
            <div className="staff-two-column">
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <span className="section-kicker">PERSONAL DETAILS</span>
                    <h2>Contact info</h2>
                  </div>
                </div>
                <form className="profile-form stack-form" onSubmit={updateProfile}>
                  <label>Full name<input name="name" defaultValue={user.name} required minLength="2" /></label>
                  <label>Email address<input value={user.email} readOnly /></label>
                  <label>Phone number<input name="phone" defaultValue={user.phone} required /></label>
                  <label>Account type<input value={user.role} readOnly /></label>
                  <button className="primary-button">Save profile <ArrowRight size={15} /></button>
                </form>
              </section>

              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <span className="section-kicker">SECURITY</span>
                    <h2>Change password</h2>
                  </div>
                </div>
                <form className="profile-form stack-form" onSubmit={changeCustomerPassword}>
                  <label>Current password<input name="currentPassword" type="password" required autoComplete="current-password" /></label>
                  <label>New password<input name="newPassword" type="password" minLength="8" required autoComplete="new-password" /></label>
                  <label>Confirm new password<input name="confirmPassword" type="password" minLength="8" required autoComplete="new-password" /></label>
                  <button className="primary-button">Update password <ArrowRight size={15} /></button>
                </form>
              </section>
            </div>
          </section>
        )}

        {/* Operations Page (Staff / Admin) */}
        {page === 'operations' && isStaff && (
          <section className="workspace-page">
            <PageTitle
              eyebrow="STOCKFLOW OPERATIONS"
              title="Inventory & orders"
              subtitle="Keep stock accurate and orders moving."
              onBack={handleBack}
            />
            <div className="operations-grid">
              <section className="panel inventory-panel">
                <div className="panel-heading">
                  <div><span className="section-kicker">LIVE INVENTORY</span><h2>Stock control</h2></div>
                  <span className="live-indicator">● LIVE</span>
                </div>
                <div className="inventory-table">
                  <div className="table-head"><span>Product</span><span>On hand</span><span>Movement</span></div>
                  {products.map((item) => (
                    <div className="inventory-row" key={item.id}>
                      <div className="inventory-name">
                        <span className="mini-product"><Package size={16} /></span>
                        <span><b>{item.name}</b><small>{item.sku} · {stockLabel(item)}</small></span>
                      </div>
                      <strong className={item.stock <= item.threshold ? 'stock-warning' : ''}>{item.stock}</strong>
                      <form className="stock-form" onSubmit={(event) => changeInventory(event, item)}>
                        <select name="action" aria-label="Movement type">
                          <option value="addition">Add</option>
                          <option value="reduction">Reduce</option>
                        </select>
                        <input name="quantity" aria-label="Quantity" type="number" min="1" required placeholder="Qty" />
                        <button aria-label={`Update ${item.name} stock`}><ArrowUp size={15} /></button>
                      </form>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel add-product-panel">
                <div className="panel-heading">
                  <div><span className="section-kicker">CATALOG CONTROL</span><h2>Add a product</h2></div>
                  <Package size={19} />
                </div>
                <form className="stack-form" onSubmit={createProduct}>
                  <label>Product name<input name="name" minLength="2" required placeholder="Wireless keyboard" /></label>
                  <div className="form-pair">
                    <label>SKU<input name="sku" required placeholder="KEY-104" /></label>
                    <label>Price (₹)<input name="price" type="number" min="0" step="0.01" required placeholder="1499" /></label>
                  </div>
                  <div className="form-pair">
                    <label>Initial units<input name="stock" type="number" min="0" defaultValue="0" /></label>
                    <label>Alert below<input name="threshold" type="number" min="0" defaultValue="5" /></label>
                  </div>
                  <label>Category<select name="categoryId"><option value="">Uncategorized</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
                  <label>Supplier<select name="supplierId"><option value="">Unassigned</option>{suppliers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
                  <label>Description<textarea name="description" rows="2" placeholder="What makes this useful?" /></label>
                  <button className="primary-button" type="submit"><Plus size={16} /> Add to catalog</button>
                </form>
              </section>
            </div>

            <section className="panel inventory-manage-panel">
              <div className="panel-heading">
                <div><span className="section-kicker">CATALOG MAINTENANCE</span><h2>Products</h2></div>
                <span className="results-count">{products.length} active</span>
              </div>
              <div className="manage-list">
                {products.map((item) => (
                  <div className="manage-row" key={item.id}>
                    <span><b>{item.name}</b><small>{item.sku} · {item.category} · {money(item.price)}</small></span>
                    <button className="text-button" onClick={() => setEditingProduct(item)}>Edit</button>
                    <button className="cancel-order" onClick={() => archiveProduct(item)}>Archive</button>
                  </div>
                ))}
              </div>
            </section>

            <div className="operations-grid compact-management">
              <section className="panel">
                <div className="panel-heading"><div><span className="section-kicker">TAXONOMY</span><h2>Categories</h2></div></div>
                <form className="inline-add-form" onSubmit={(event) => manageSimpleRecord(event, '/categories/manage')}>
                  <input name="name" required placeholder="New category" />
                  <button className="icon-button" aria-label="Add category"><Plus size={17} /></button>
                </form>
                <div className="manage-list">
                  {categories.map((item) => (
                    <div className="manage-row" key={item.id}>
                      <span><b>{item.name}</b></span>
                      <button className="cancel-order" onClick={async () => {
                        try {
                          await api(`/categories/manage?id=${item.id}`, { method: 'DELETE' })
                          await reload()
                          announce('Category removed.')
                        } catch (err) { setError(err.message) }
                      }}>Remove</button>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel">
                <div className="panel-heading"><div><span className="section-kicker">PARTNERS</span><h2>Suppliers</h2></div></div>
                <form className="inline-add-form" onSubmit={(event) => manageSimpleRecord(event, '/suppliers/manage')}>
                  <input name="name" required placeholder="Supplier name" />
                  <button className="icon-button" aria-label="Add supplier"><Plus size={17} /></button>
                </form>
                <div className="manage-list">
                  {suppliers.map((item) => (
                    <div className="manage-row" key={item.id}>
                      <span><b>{item.name}</b></span>
                      <small>Active</small>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            <section className="panel orders-panel">
              <div className="panel-heading">
                <div><span className="section-kicker">FULFILMENT QUEUE</span><h2>Orders to process</h2></div>
                <span className="results-count">{orders.length} orders</span>
              </div>
              {orders.length ? (
                <div className="order-list">
                  {orders.map((order) => (
                    <OrderCard key={order.id} order={order} onStatus={updateStatus} />
                  ))}
                </div>
              ) : (
                <div className="compact-empty">No customer orders are waiting.</div>
              )}
            </section>

            <section className="panel movements-panel">
              <div className="panel-heading">
                <div><span className="section-kicker">AUDIT TRAIL</span><h2>Recent stock movements</h2></div>
                <span className="results-count">Latest 250</span>
              </div>
              <div className="movement-list">
                {movements.slice(0, 8).map((move) => (
                  <div className="movement-row" key={move.id}>
                    <span className={`movement-icon ${move.quantity > 0 ? 'positive' : 'negative'}`}>
                      {move.quantity > 0 ? <ArrowDown size={15} /> : <ArrowUp size={15} />}
                    </span>
                    <span><b>{move.product}</b><small>{move.note || move.action} · {move.user || 'System'} · {new Date(move.createdAt).toLocaleString()}</small></span>
                    <strong className={move.quantity > 0 ? 'positive-text' : ''}>{move.quantity > 0 ? '+' : ''}{move.quantity}</strong>
                  </div>
                ))}
              </div>
            </section>
          </section>
        )}

        {/* Dedicated Admin Overview Dashboard */}
        {page === 'admin' && isAdmin && (
          <section className="workspace-page">
            <PageTitle
              eyebrow="CONTROL ROOM"
              title="Platform overview"
              subtitle="Executive summary and administration of the StockFlow platform."
            />
            {overview && (
              <div className="metric-grid">
                {[
                  ['Products', overview.products, Package, 'products'],
                  ['Customers', overview.customers, Users, 'customers-manage'],
                  ['Staff', overview.staff, Users, null],
                  ['Categories', overview.categories, Box, 'catalog-data'],
                  ['Suppliers', overview.suppliers, Box, 'catalog-data'],
                  ['Orders', overview.orders, ClipboardList, 'orders-manage'],
                  ['Inventory units', overview.inventoryUnits, Package, 'inventory'],
                  ['Inventory value', money(overview.inventoryValue), ArrowUp, 'inventory'],
                  ['Completed sales', money(overview.salesTotal), ArrowRight, 'reports'],
                  ['Pending', overview.pending, CircleAlert, 'orders-manage'],
                  ['Completed', overview.completed, BadgeCheck, 'orders-manage'],
                  ['Cancelled', overview.cancelled, X, 'orders-manage'],
                  ['Low stock', overview.lowStock, ArrowDown, 'inventory'],
                  ['Out of stock', overview.outOfStock, CircleAlert, 'inventory'],
                ].map(([label, value, Icon, route]) => (
                  <button
                    key={label}
                    type="button"
                    className="metric-card clickable"
                    onClick={() => {
                      if (route) navigateTo(route)
                      else {
                        const el = document.getElementById('admin-staff-section')
                        if (el) el.scrollIntoView({ behavior: 'smooth' })
                      }
                    }}
                    title={route ? `View ${label}` : `Manage ${label}`}
                  >
                    <div className="metric-icon"><Icon size={17} /></div>
                    <span>{label}</span>
                    <strong>{value}</strong>
                  </button>
                ))}
              </div>
            )}

            {/* Quick Admin Shortcut Links */}
            <div className="admin-shortcut-links">
              <button type="button" className="shortcut-chip" onClick={() => navigateTo('products')}><Package size={14} /> Products</button>
              <button type="button" className="shortcut-chip" onClick={() => navigateTo('inventory')}><ArrowUp size={14} /> Inventory</button>
              <button type="button" className="shortcut-chip" onClick={() => navigateTo('orders-manage')}><ClipboardList size={14} /> Orders</button>
              <button type="button" className="shortcut-chip" onClick={() => navigateTo('customers-manage')}><Users size={14} /> Customers</button>
              <button type="button" className="shortcut-chip" onClick={() => navigateTo('catalog-data')}><Box size={14} /> Categories & Suppliers</button>
              <button type="button" className="shortcut-chip" onClick={() => navigateTo('reports')}><ArrowRight size={14} /> Reports</button>
            </div>

            {/* Admin Staff Accounts Management */}
            <section className="panel accounts-panel" id="admin-staff-section" style={{ marginTop: 28 }}>
              <div className="panel-heading">
                <div><span className="section-kicker">ACCESS CONTROL</span><h2>Staff accounts & permissions</h2></div>
                <button className="primary-button" onClick={() => setAdminAccountForm({})}>
                  <Plus size={15} /> Add staff
                </button>
              </div>
              <div className="account-table">
                <div className="table-head"><span>Account</span><span>Role</span><span>Access</span><span>Manage</span></div>
                {users.map((account) => (
                  <div className="account-row" key={account.id}>
                    <div><b>{account.name}</b><small>{account.email} · {account.phone}</small></div>
                    <select
                      aria-label={`Role for ${account.name}`}
                      value={account.role}
                      disabled={account.id === user.id}
                      onChange={(event) => changeAccount(account, 'role', event.target.value)}
                    >
                      <option value="customer">Customer</option>
                      <option value="staff">Staff</option>
                      <option value="admin">Admin</option>
                    </select>
                    <button
                      className={account.active ? 'status-toggle enabled' : 'status-toggle'}
                      disabled={account.id === user.id}
                      onClick={() => changeAccount(account, 'active', !account.active)}
                    >
                      {account.active ? 'Active' : 'Inactive'}
                    </button>
                    {account.role === 'staff' ? (
                      <button className="text-button" onClick={() => setAdminAccountForm(account)}>Edit</button>
                    ) : (
                      <span />
                    )}
                  </div>
                ))}
              </div>
            </section>
          </section>
        )}

        {/* Fallback for unknown / unavailable routes */}
        {!PAGE_IDS.has(page) && (
          <div className="empty-state">
            <CircleAlert size={28} />
            <h3>Page unavailable</h3>
            <button className="primary-button" onClick={() => navigateTo('catalog')}>Return to shop</button>
          </div>
        )}
      </main>

      <footer className="site-footer">
        <a className="brand footer-brand" href="#catalog" onClick={(e) => { e.preventDefault(); navigateTo('catalog') }}>
          <span className="brand-mark"><Box size={16} /></span>
          <span>stock<span>flow</span></span>
        </a>
        <span>Inventory, in better order.</span>
        <span>© 2026 STOCKFLOW</span>
      </footer>

      {/* Product Details Modal */}
      {detailProduct && (
        <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setDetailProduct(null) }}>
          <section className="detail-modal">
            <button className="modal-close icon-button" aria-label="Close details" onClick={() => setDetailProduct(null)}>
              <X size={19} />
            </button>
            <img src={detailProduct.imageUrl || sampleImages[detailProduct.name.split(' ')[0]] || sampleImages.Cable} alt={detailProduct.name} />
            <div className="detail-content">
              <span className="section-kicker">{detailProduct.category} · {detailProduct.sku}</span>
              <h2>{detailProduct.name}</h2>
              <p>{detailProduct.description || 'A dependable addition to your everyday setup.'}</p>
              <strong>{money(detailProduct.price)}</strong>
              <span className="detail-stock">{detailProduct.status !== 'active' ? 'Archived / Inactive (Not available for order)' : `${stockLabel(detailProduct)} · ${detailProduct.stock} units available`}</span>
              <button className="primary-button" disabled={!detailProduct.stock || detailProduct.status !== 'active'} onClick={() => { addToCart(detailProduct); setDetailProduct(null) }}>
                <ShoppingBag size={16} /> Add to bag
              </button>
            </div>
          </section>
        </div>
      )}

      {/* Edit Product Modal */}
      {editingProduct && (
        <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setEditingProduct(null) }}>
          <section className="auth-modal">
            <button className="modal-close icon-button" aria-label="Close edit form" onClick={() => setEditingProduct(null)}>
              <X size={19} />
            </button>
            <span className="section-kicker">CATALOG CONTROL</span>
            <h2>Edit product</h2>
            <form className="stack-form" onSubmit={saveProduct}>
              <label>Product name<input name="name" defaultValue={editingProduct.name} required /></label>
              <label>SKU<input name="sku" defaultValue={editingProduct.sku} required /></label>
              <label>Price<input name="price" type="number" min="0" step="0.01" defaultValue={editingProduct.price} required /></label>
              <label>Low-stock alert<input name="threshold" type="number" min="0" defaultValue={editingProduct.threshold} required /></label>
              <label>Category<select name="categoryId" defaultValue={editingProduct.categoryId || ''}><option value="">Uncategorized</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
              <label>Supplier<select name="supplierId" defaultValue={editingProduct.supplierId || ''}><option value="">Unassigned</option>{suppliers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
              <label>Description<textarea name="description" defaultValue={editingProduct.description} rows="3" /></label>
              <button className="primary-button">Save product</button>
            </form>
          </section>
        </div>
      )}

      {/* Admin Add/Edit Staff Modal */}
      {adminAccountForm && (
        <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setAdminAccountForm(null) }}>
          <section className="auth-modal">
            <button className="modal-close icon-button" aria-label="Close staff account form" onClick={() => setAdminAccountForm(null)}>
              <X size={19} />
            </button>
            <span className="section-kicker">STAFF ACCESS</span>
            <h2>{adminAccountForm.id ? 'Edit staff account' : 'Create staff account'}</h2>
            <form className="stack-form" onSubmit={saveAdminAccount}>
              <label>Name<input name="name" required minLength="2" defaultValue={adminAccountForm.name || ''} /></label>
              <label>Email<input name="email" required type="email" defaultValue={adminAccountForm.email || ''} /></label>
              <label>Phone<input name="phone" required defaultValue={adminAccountForm.phone || ''} /></label>
              <label>{adminAccountForm.id ? 'Reset password (optional)' : 'Temporary password'}<input name="password" type="password" minLength="8" required={!adminAccountForm.id} autoComplete="new-password" /></label>
              <label>Account status<select name="active" defaultValue={adminAccountForm.active === false ? 'false' : 'true'}><option value="true">Active</option><option value="false">Inactive</option></select></label>
              <button className="primary-button">{adminAccountForm.id ? 'Save staff account' : 'Create staff account'}</button>
            </form>
          </section>
        </div>
      )}
    </div>
  )
}

function PageTitle({ eyebrow, title, subtitle, onBack }) {
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
      </div>
    </div>
  )
}

function OrderCard({ order, customer = false, onCancel, onStatus }) {
  const next = {
    pending: 'confirmed',
    confirmed: 'processing',
    processing: 'ready',
    ready: 'completed',
    shipped: 'delivered',
    delivered: 'completed'
  }[order.status]
  const canCancel = ['pending', 'confirmed'].includes(order.status)
  const addr = order.deliveryAddress
  const subtotal = Number(order.subtotal || 0)
  const discount = Number(order.discount || 0)
  const total = Number(order.total || 0)

  return (
    <article className="order-card">
      <div className="order-main">
        <div className="order-id">
          <span>{order.number}</span>
          <small>{new Date(order.createdAt).toLocaleDateString()}</small>
        </div>
        <div className="order-detail">
          <div className="order-items-list">
            {order.items.map((item) => (
              <div className="order-item-line" key={`${order.id}-${item.productId}`}>
                <span>{item.name} <b>×{item.quantity}</b></span>
                <span className="order-item-price">
                  {money(item.unitPrice)} each = {money(item.unitPrice * item.quantity)}
                </span>
              </div>
            ))}
          </div>

          <div className="order-financials">
            <span>Subtotal: <strong>{money(subtotal)}</strong></span>
            {discount > 0 && (
              <span className="financial-discount">Discount: -{money(discount)}</span>
            )}
            <span className="financial-total">Order Total: <strong>{money(total)}</strong></span>
          </div>

          <small>{customer ? 'Customer order' : (order.customer?.name || 'Customer')}</small>
          {addr && (
            <div className="order-delivery-address-badge">
              <div>
                <strong>Deliver to: {addr.fullName}</strong> ({addr.mobileNumber}
                {addr.alternatePhone ? `, Alt: ${addr.alternatePhone}` : ''})
              </div>
              <div>
                {[addr.houseNumber, addr.floorNumber, addr.buildingName, addr.streetName].filter(Boolean).join(', ')}, {addr.area}
                {addr.landmark ? ` (Near ${addr.landmark})` : ''}, {addr.city}, {addr.district}, {addr.state} - <strong>{addr.pinCode}</strong>
              </div>
              {addr.deliveryInstructions && (
                <div className="instruction-note">Note: {addr.deliveryInstructions}</div>
              )}
            </div>
          )}
        </div>
        <span className={`order-status ${order.status}`}>{order.status}</span>
        <strong className="order-amount">{money(total)}</strong>
      </div>
      <div className="order-actions">
        {customer && canCancel && (
          <button className="cancel-order" onClick={onCancel}>
            Cancel order
          </button>
        )}
        {!customer && next && (
          <button className="text-button" onClick={() => onStatus(order.id, next)}>
            Mark {next} <ArrowRight size={14} />
          </button>
        )}
      </div>
    </article>
  )
}

export default App
