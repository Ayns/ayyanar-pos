import React, { useState, useEffect } from 'react';
import { usePOS } from './POSContext';
import { fetchProducts, addToCart, removeFromCart, checkout as apiCheckout, getPendingBills } from './api';
import { addPendingBill } from './db';
import { HALFactory } from './hal';
import CatalogueView from './components/CatalogueView';
import CartView from './components/CartView';
import CheckoutModal from './components/CheckoutModal';
import ZReport from './components/ZReport';
import OfflineIndicator from './components/OfflineIndicator';

export default function App() {
  const { state, dispatch } = usePOS();
  const [view, setView] = useState('catalogue'); // catalogue | zreport
  const [showCheckout, setShowCheckout] = useState(false);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadProducts();
    loadPendingBills();
  }, []);

  async function loadProducts() {
    try {
      setLoading(true);
      // Try API first; fall back to mock data if backend unavailable
      let data;
      try {
        data = await fetchProducts();
      } catch {
        // Mock catalogue for when backend is not running
        data = generateMockCatalogue();
      }
      setProducts(data);
      dispatch({ type: 'SET_PRODUCTS', payload: data });

      // Cache in IndexedDB
      try {
        const { saveCatalogue } = await import('./db');
        await saveCatalogue(data);
      } catch {}
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadPendingBills() {
    try {
      const pending = await getPendingBills();
      dispatch({ type: 'SET_PENDING_BILLS', payload: pending });
    } catch {}
  }

  function handleAddToCart(item) {
    dispatch({ type: 'ADD_TO_CART', payload: item });
  }

  function handleRemoveFromCart(variantId) {
    dispatch({ type: 'REMOVE_FROM_CART', payload: variantId });
  }

  function handleUpdateQty(variantId, newQty) {
    if (newQty <= 0) {
      dispatch({ type: 'REMOVE_FROM_CART', payload: variantId });
    } else {
      dispatch({
        type: 'ADD_TO_CART',
        payload: { ...state.cart.find((c) => c.variant_id === variantId), qty: newQty - state.cart.find((c) => c.variant_id === variantId).qty },
      });
    }
  }

  function handleClearCart() {
    dispatch({ type: 'CLEAR_CART' });
  }

  async function handleConfirmCheckout(paymentData) {
    const { payments, discountPaise, customerName, customerGSTIN } = paymentData;
    const totalPaise = state.cart.reduce((s, item) => s + item.mrp_paise * item.qty, 0);
    const isOnline = state.online;

    try {
      const result = await apiCheckout(state.cart, payments, discountPaise, customerName, customerGSTIN);

      if (!isOnline) {
        // Also save to IndexedDB
        await addPendingBill({
          id: `bill-${Date.now()}`,
          invoiceNo: result.invoice_no,
          total: result.total_paid_paise,
          items: state.cart,
          payments,
          created_at: new Date().toISOString(),
        });
      }

      return result;
    } catch (err) {
      // If API fails, save bill to pending queue for later sync
      const bill = {
        id: `bill-${Date.now()}`,
        invoiceNo: `PENDING-${Date.now()}`,
        total: totalPaise,
        items: [...state.cart],
        payments,
        discountPaise,
        customerName,
        customerGSTIN,
        created_at: new Date().toISOString(),
      };
      await addPendingBill(bill);

      // Try to sync pending bills in background
      try {
        const { PrinterHAL } = await import('./hal');
        const hal = HALFactory.create();
        await hal.printer.printReceipt({
          invoiceNo: bill.invoiceNo,
          lines: bill.items,
          payments,
          total_paise: totalPaise,
        });
      } catch {}

      dispatch({ type: 'ADD_PENDING_BILL', payload: bill });

      return { invoice_no: bill.invoiceNo, total_paid_paise: totalPaise, payments, gst_lines: [] };
    }
  }

  if (loading) {
    return (
      <div style={styles.loading}>
        <div style={styles.spinner} />
        <p>Loading catalogue...</p>
      </div>
    );
  }

  if (error && !products.length) {
    return (
      <div style={styles.loading}>
        <p style={{ color: '#e94560' }}>Error: {error}</p>
        <p style={{ fontSize: 12, color: '#888' }}>Using mock catalogue for prototype demo.</p>
      </div>
    );
  }

  const totalPaise = state.cart.reduce((s, item) => s + item.mrp_paise * item.qty, 0);
  const totalItems = state.cart.reduce((s, item) => s + item.qty, 0);

  return (
    <div style={styles.app}>
      <OfflineIndicator />

      {/* Header */}
      <header style={styles.header}>
        <div style={styles.brand}>
          <span style={styles.brandIcon}>&#9881;</span>
          <span>AYY POS</span>
        </div>
        <div style={styles.nav}>
          <button
            onClick={() => setView('catalogue')}
            style={{ ...styles.navBtn, ...(view === 'catalogue' ? styles.navBtnActive : {}) }}
          >
            &#128723; Catalogue
          </button>
          <button
            onClick={() => setView('zreport')}
            style={{ ...styles.navBtn, ...(view === 'zreport' ? styles.navBtnActive : {}) }}
          >
            &#128202; Z-Report
          </button>
        </div>
        <div style={styles.headerRight}>
          <span style={state.online ? styles.online : styles.offline}>
            {state.online ? '&#128994; Online' : '&#128274; Offline'}
          </span>
          {state.pendingBills.length > 0 && (
            <span style={styles.pendingBadge}>{state.pendingBills.length} pending</span>
          )}
        </div>
      </header>

      {/* Main content */}
      {view === 'catalogue' ? (
        <div style={styles.main}>
          <div style={styles.leftPanel}>
            <CatalogueView products={products} onAddToCart={handleAddToCart} />
          </div>
          <div style={styles.rightPanel}>
            <CartView
              cart={state.cart}
              onRemove={handleRemoveFromCart}
              onUpdateQty={handleUpdateQty}
              onClear={handleClearCart}
              onCheckout={() => setShowCheckout(true)}
            />
          </div>
        </div>
      ) : (
        <ZReport
          cart={state.cart}
          pendingBills={state.pendingBills}
          online={state.online}
        />
      )}

      {/* Checkout Modal */}
      {showCheckout && (
        <CheckoutModal
          cart={state.cart}
          totalPaise={totalPaise}
          onClose={() => setShowCheckout(false)}
          onConfirm={handleConfirmCheckout}
        />
      )}
    </div>
  );
}

function generateMockCatalogue() {
  const styles = ['T-Shirt', 'Jeans', 'Kurta', 'Saree'];
  const colors = ['Red', 'Blue', 'Black', 'White', 'Navy'];
  const sizes = ['S', 'M', 'L', 'XL', 'XXL'];
  const items = [];
  let counter = 1;

  for (const style of styles) {
    for (const color of colors) {
      for (const size of sizes) {
        items.push({
          variant_id: `${style}-${color}-${size}-${counter.toString().padStart(3, '0')}`,
          style,
          color,
          size,
          mrp_paise: Math.floor(Math.random() * 1500 + 499) * 100, // 499-1999
          hsn_code: '6109',
        });
        counter++;
      }
    }
  }
  return items;
}

const styles = {
  app: { height: '100vh', display: 'flex', flexDirection: 'column', background: '#0d1117', color: '#e0e0e0' },
  loading: { flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 },
  spinner: { width: 32, height: 32, border: '3px solid #0f3460', borderTop: '3px solid #e94560', borderRadius: '50%', animation: 'spin 1s linear infinite' },
  header: {
    display: 'flex', alignItems: 'center', padding: '0 16px', height: 48,
    background: '#16213e', borderBottom: '1px solid #0f3460', gap: 16, flexShrink: 0,
  },
  brand: { display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: 16, color: '#e94560' },
  brandIcon: { fontSize: 18 },
  nav: { display: 'flex', gap: 4, marginLeft: 16 },
  navBtn: {
    padding: '4px 12px', borderRadius: 6, border: 'none', background: 'transparent',
    color: '#888', fontSize: 13, cursor: 'pointer',
  },
  navBtnActive: { background: '#0f3460', color: '#fff' },
  headerRight: { marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 },
  online: { fontSize: 12, color: '#4caf50' },
  offline: { fontSize: 12, color: '#ff9800' },
  pendingBadge: {
    background: '#ff9800', color: '#000', fontSize: 10, fontWeight: 700,
    padding: '2px 8px', borderRadius: 10,
  },
  main: { flex: 1, display: 'flex', overflow: 'hidden' },
  leftPanel: { flex: 3, minWidth: 0, borderRight: '1px solid #0f3460' },
  rightPanel: { flex: 2, minWidth: 280, display: 'flex', flexDirection: 'column' },
};

// Inject spin animation
const styleEl = document.createElement('style');
styleEl.textContent = '@keyframes spin{to{transform:rotate(360deg)}}';
if (typeof document !== 'undefined' && !document.getElementById('pos-style')) {
  styleEl.id = 'pos-style';
  document.head.appendChild(styleEl);
}
