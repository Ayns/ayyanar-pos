/**
 * AYY-34 — POS App root.
 * End-to-end: catalogue -> cart -> checkout -> receipt.
 */

import React, { useState, useEffect, useCallback } from "react";
import { POSProvider, usePOS } from "./POSContext";
import { fetchCatalogue, searchCatalogue, checkout as apiCheckout } from "./services/api";
import { addPendingBill, getPendingBills as loadPendingBillsFromDB, saveCatalogue } from "./db";
import CatalogueView from "./components/CatalogueView";
import CartView from "./components/CartView";
import CheckoutModal from "./components/CheckoutModal";
import ZReport from "./components/ZReport";
import OfflineIndicator from "./components/OfflineIndicator";

function AppContent() {
  const { state, dispatch } = usePOS();
  const [view, setView] = useState("catalogue");
  const [showCheckout, setShowCheckout] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // Local product list for search filtering (mirrors state.products)
  const [localProducts, setLocalProducts] = useState([]);

  useEffect(() => {
    loadInitialData();
    loadPendingFromDB();
  }, []);

  // Keep localProducts in sync with POS context
  useEffect(() => {
    if (state.products.length > 0) {
      setLocalProducts(state.products);
    }
  }, [state.products]);

  async function loadInitialData() {
    try {
      setLoading(true);
      let products;
      // Try cache first (offline support)
      const cached = await loadCatalogue();
      if (cached && cached.length > 0) {
        products = cached;
      }
      // Fetch from API
      try {
        const data = await fetchCatalogue();
        products = data;
        await saveCatalogue(data);
      } catch {
        // Use cached or mock data
        if (!products || products.length === 0) {
          products = generateMockCatalogue();
        }
      }
      setLocalProducts(products);
      dispatch({ type: "SET_PRODUCTS", payload: products });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadPendingFromDB() {
    try {
      const pending = await loadPendingBillsFromDB();
      dispatch({ type: "SET_PENDING_BILLS", payload: pending });
    } catch {}
  }

  const handleSearch = useCallback(async (query) => {
    setSearchQuery(query);
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }
    try {
      const results = await searchCatalogue(query);
      setSearchResults(results);
    } catch {
      // Filter locally
      const results = localProducts.filter((p) =>
        (p.sku || "").toLowerCase().includes(query.toLowerCase()) ||
        (p.style_name || p.style_code || "").toLowerCase().includes(query.toLowerCase()) ||
        String(p.barcode || "").includes(query)
      );
      setSearchResults(results.slice(0, 50));
    }
  }, [localProducts]);

  function handleAddToCart(item) {
    // Ensure each cart item has a stable ID
    const cartItem = {
      id: item.variant_id || item.id,
      variant_id: item.variant_id || item.id,
      qty: 1,
      ...item,
    };
    dispatch({ type: "ADD_TO_CART", payload: cartItem });
    setSearchQuery("");
    setSearchResults([]);
  }

  function handleRemoveFromCart(variantId) {
    dispatch({ type: "REMOVE_FROM_CART", payload: variantId });
  }

  function handleUpdateQty(variantId, newQty) {
    if (newQty <= 0) {
      dispatch({ type: "REMOVE_FROM_CART", payload: variantId });
    } else {
      dispatch({ type: "SET_CART_QTY", payload: { id: variantId, qty: newQty } });
    }
  }

  function handleClearCart() {
    dispatch({ type: "CLEAR_CART" });
  }

  async function handleConfirmCheckout(paymentData) {
    const { payments, discountPaise, customerName, customerGSTIN } = paymentData;
    const isOnline = state.online;

    try {
      const result = await apiCheckout(state.cart, payments, discountPaise, customerName, customerGSTIN);

      if (!isOnline) {
        await addPendingBill({
          id: `bill-${Date.now()}`,
          invoiceNo: result.invoice_no,
          total: result.total_paid_paise,
          items: [...state.cart],
          payments,
          created_at: new Date().toISOString(),
        });
      }

      dispatch({ type: "CLEAR_CART" });
      setShowCheckout(false);
      return result;
    } catch (err) {
      // Save to pending queue on failure
      const totalPaise = state.cart.reduce((s, item) => s + ((item.mrp_paise || item.selling_price_paise || 0) * item.qty), 0);
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
      dispatch({ type: "ADD_PENDING_BILL", payload: bill });
      dispatch({ type: "CLEAR_CART" });
      setShowCheckout(false);
      return { invoice_no: bill.invoiceNo, total_paid_paise: totalPaise, payments };
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

  const totalPaise = state.cart.reduce((s, item) => s + ((item.mrp_paise || item.selling_price_paise || 0) * item.qty), 0);
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
          <button onClick={() => setView("catalogue")}
            style={{ ...styles.navBtn, ...(view === "catalogue" ? styles.navBtnActive : {}) }}>
            Catalogue
          </button>
          <button onClick={() => setView("zreport")}
            style={{ ...styles.navBtn, ...(view === "zreport" ? styles.navBtnActive : {}) }}>
            Z-Report
          </button>
        </div>
        <div style={styles.headerRight}>
          <span style={state.online ? styles.online : styles.offline}>
            {state.online ? "Online" : "Offline"}
          </span>
          {state.pendingBills.length > 0 && (
            <span style={styles.pendingBadge}>{state.pendingBills.length} pending</span>
          )}
        </div>
      </header>

      {/* Main */}
      {view === "catalogue" ? (
        <div style={styles.main}>
          <div style={styles.leftPanel}>
            <CatalogueView
              products={localProducts}
              searchQuery={searchQuery}
              searchResults={searchResults}
              onSearch={handleSearch}
              onAddToCart={handleAddToCart}
            />
          </div>
          <div style={styles.rightPanel}>
            <CartView
              cart={state.cart}
              totalPaise={totalPaise}
              totalItems={totalItems}
              onRemove={handleRemoveFromCart}
              onUpdateQty={handleUpdateQty}
              onClear={handleClearCart}
              onCheckout={() => setShowCheckout(true)}
            />
          </div>
        </div>
      ) : (
        <ZReport
          pendingBills={state.pendingBills}
          online={state.online}
          onSyncPending={loadPendingFromDB}
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
  const styles = ["T-Shirt", "Jeans", "Kurta", "Saree", "Shirt"];
  const colors = ["Red", "Blue", "Black", "White", "Navy", "Green"];
  const sizes = ["S", "M", "L", "XL", "XXL"];
  const items = [];
  let counter = 1;
  for (const style of styles) {
    for (const color of colors) {
      for (const size of sizes) {
        items.push({
          id: `mock-${counter}`,
          variant_id: `mock-${counter}`,
          sku: `${style}-${color}-${size}`,
          style_name: style,
          style_code: style.substring(0, 3).toUpperCase(),
          colour_name: color,
          colour: color,
          size_name: size,
          size: size,
          mrp_paise: Math.floor(Math.random() * 1500 + 499) * 100,
          selling_price_paise: Math.floor(Math.random() * 1200 + 399) * 100,
          hsn_code: "6109",
          gst_slab: 12,
          barcode: `890${String(counter).padStart(9, "0")}`,
          full_label: `${style} | ${color} | ${size}`,
        });
        counter++;
      }
    }
  }
  return items;
}

const styles = {
  app: { height: "100vh", display: "flex", flexDirection: "column", background: "#0d1117", color: "#e0e0e0" },
  loading: { flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12 },
  spinner: { width: 32, height: 32, border: "3px solid #0f3460", borderTop: "3px solid #e94560", borderRadius: "50%" },
  header: { display: "flex", alignItems: "center", padding: "0 16px", height: 48, background: "#16213e", borderBottom: "1px solid #0f3460", gap: 16, flexShrink: 0 },
  brand: { display: "flex", alignItems: "center", gap: 8, fontWeight: 700, fontSize: 16, color: "#e94560" },
  brandIcon: { fontSize: 18 },
  nav: { display: "flex", gap: 4, marginLeft: 16 },
  navBtn: { padding: "4px 12px", borderRadius: 6, border: "none", background: "transparent", color: "#888", fontSize: 13, cursor: "pointer" },
  navBtnActive: { background: "#0f3460", color: "#fff" },
  headerRight: { marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 },
  online: { fontSize: 12, color: "#4caf50" },
  offline: { fontSize: 12, color: "#ff9800" },
  pendingBadge: { background: "#ff9800", color: "#000", fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 10 },
  main: { flex: 1, display: "flex", overflow: "hidden" },
  leftPanel: { flex: 3, minWidth: 0, borderRight: "1px solid #0f3460" },
  rightPanel: { flex: 2, minWidth: 280, display: "flex", flexDirection: "column" },
};

export default function App() {
  return (
    <POSProvider>
      <AppContent />
    </POSProvider>
  );
}
