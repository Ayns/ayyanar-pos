/**
 * AYY-34 — Cart view component.
 */

import React from "react";

export default function CartView({ cart, totalPaise, totalItems, onRemove, onUpdateQty, onClear, onCheckout }) {
  const totalRupees = (totalPaise / 100).toFixed(2);
  const isEmpty = cart.length === 0;

  return (
    <div style={styles.container}>
      {/* Cart header */}
      <div style={styles.header}>
        <span style={styles.title}>Cart ({totalItems})</span>
        {!isEmpty && (
          <button onClick={onClear} style={styles.clearBtn}>Clear All</button>
        )}
      </div>

      {/* Cart lines */}
      <div style={styles.lines}>
        {cart.map((item) => {
          const key = item.variant_id || item.id || item.sku;
          return (
          <div key={key} style={styles.line}>
            <div style={styles.lineInfo}>
              <div style={styles.lineName}>{item.full_label || `${item.style_name || ""} ${item.colour_name || ""} ${item.size_name || ""}`}</div>
              <div style={styles.lineSku}>{item.sku}</div>
              <div style={styles.linePrice}>Rs {((item.mrp_paise || item.selling_price_paise) / 100).toFixed(0)} x {item.qty}</div>
            </div>
            <div style={styles.lineControls}>
              <button onClick={() => onUpdateQty(item.id, item.qty - 1)} style={styles.qtyBtn}>-</button>
              <span style={styles.qty}>{item.qty}</span>
              <button onClick={() => onUpdateQty(item.id, item.qty + 1)} style={styles.qtyBtn}>+</button>
              <button onClick={() => onRemove(item.id)} style={styles.removeBtn}>&times;</button>
            </div>
            <div style={styles.lineTotal}>
              Rs {(((((item.mrp_paise || item.selling_price_paise) || 0) * item.qty)) / 100).toFixed(2)}
            </div>
          </div>
        );
        })}
      </div>

      {/* Total */}
      <div style={styles.total}>
        <span style={styles.totalLabel}>Total</span>
        <span style={styles.totalValue}>Rs {totalRupees}</span>
      </div>

      {/* Checkout button */}
      <button
        onClick={onCheckout}
        disabled={isEmpty}
        style={{
          ...styles.checkoutBtn,
          opacity: isEmpty ? 0.5 : 1,
          cursor: isEmpty ? "not-allowed" : "pointer",
        }}
      >
        &#128179; Checkout — Rs {totalRupees}
      </button>
    </div>
  );
}

const styles = {
  container: { display: "flex", flexDirection: "column", height: "100%", background: "#0f1923" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", borderBottom: "1px solid #0f3460" },
  title: { fontWeight: 700, fontSize: 14 },
  clearBtn: { background: "transparent", border: "none", color: "#e94560", cursor: "pointer", fontSize: 12 },
  lines: { flex: 1, overflowY: "auto", padding: 4 },
  line: { display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", borderBottom: "1px solid #0a1520" },
  lineInfo: { flex: 1, minWidth: 0 },
  lineName: { fontSize: 12, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  lineSku: { fontSize: 10, color: "#666", fontFamily: "monospace" },
  linePrice: { fontSize: 11, color: "#aaa" },
  lineControls: { display: "flex", alignItems: "center", gap: 2 },
  qtyBtn: { width: 24, height: 24, borderRadius: 4, border: "1px solid #0f3460", background: "#16213e", color: "#e0e0e0", cursor: "pointer", fontSize: 14 },
  qty: { width: 20, textAlign: "center", fontSize: 13 },
  removeBtn: { width: 24, height: 24, borderRadius: 4, border: "1px solid #333", background: "transparent", color: "#e94560", cursor: "pointer", fontSize: 14 },
  lineTotal: { fontWeight: 700, fontSize: 12, minWidth: 60, textAlign: "right" },
  total: { display: "flex", justifyContent: "space-between", padding: "12px 12px", borderTop: "2px solid #0f3460", fontSize: 16 },
  totalLabel: { fontWeight: 600 },
  totalValue: { fontWeight: 700, color: "#e94560", fontSize: 20 },
  checkoutBtn: { width: "100%", padding: "14px 0", background: "#e94560", border: "none", borderRadius: 8, color: "#fff", fontWeight: 700, fontSize: 16, marginTop: 8 },
};
