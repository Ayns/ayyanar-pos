/**
 * AYY-34 — Checkout modal.
 * Handles payment split, customer details, discount.
 */

import React, { useState, useMemo } from "react";

const TENDER_TYPES = [
  { value: "cash", label: "Cash", icon: "\u20B9" },
  { value: "upi", label: "UPI", icon: "\u2714;" },
  { value: "card", label: "Card", icon: "\u26A1" },
  { value: "wallet", label: "Wallet", icon: "\u{1F4F1}" },
  { value: "store_credit", label: "Store Credit", icon: "\u2728" },
];

export default function CheckoutModal({ cart, totalPaise, onClose, onConfirm }) {
  const [customerName, setCustomerName] = useState("");
  const [customerGSTIN, setCustomerGSTIN] = useState("");
  const [discountPaise, setDiscountPaise] = useState(0);
  const [payments, setPayments] = useState([{ type: "cash", amount_paise: totalPaise }]);
  const [error, setError] = useState("");

  const totalRupees = (totalPaise / 100).toFixed(2);
  const paidPaise = useMemo(
    () => payments.reduce((s, p) => s + (p.amount_paise || 0), 0),
    [payments]
  );
  const remainingPaise = Math.max(0, totalPaise - paidPaise);
  const isOverpaid = paidPaise > totalPaise;

  function handleAddPayment() {
    setPayments([
      ...payments,
      { type: "cash", amount_paise: remainingPaise },
    ]);
  }

  function handleUpdatePayment(index, field, value) {
    const updated = [...payments];
    updated[index] = { ...updated[index], [field]: value };
    // If removing the only payment or changing type, reset amount to remaining
    setPayments(updated);
  }

  function handleRemovePayment(index) {
    if (payments.length <= 1) return;
    const remaining = payments[index].amount_paise || 0;
    const updated = payments.filter((_, i) => i !== index);
    // Distribute the removed amount to the first remaining payment
    if (updated.length > 0) {
      updated[0].amount_paise = (updated[0].amount_paise || 0) + remaining;
    }
    setPayments(updated);
  }

  async function handleConfirm() {
    const paid = payments.reduce((s, p) => s + (p.amount_paise || 0), 0);
    if (paid < totalPaise) {
      setError(`Payment total Rs ${(paid / 100).toFixed(2)} is less than bill total Rs ${totalRupees}`);
      return;
    }

    try {
      setError("");
      await onConfirm({ payments, discountPaise, customerName, customerGSTIN });
    } catch (err) {
      setError(err.message || "Checkout failed");
    }
  }

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={styles.header}>
          <h2 style={styles.modalTitle}>Checkout</h2>
          <button onClick={onClose} style={styles.closeBtn}>&times;</button>
        </div>

        {/* Cart summary */}
        <div style={styles.cartSummary}>
          {cart.map((item, i) => (
            <div key={i} style={styles.cartItem}>
              <span>{item.full_label || item.sku}</span>
              <span>x{item.qty}</span>
              <span>Rs {(((item.mrp_paise || item.selling_price_paise || 0) * item.qty) / 100).toFixed(2)}</span>
            </div>
          ))}
        </div>

        {/* Customer info */}
        <div style={styles.section}>
          <label style={styles.label}>Customer Name</label>
          <input style={styles.input} value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Walk-in" />
          <label style={styles.label}>GSTIN (optional)</label>
          <input style={styles.input} value={customerGSTIN} onChange={(e) => setCustomerGSTIN(e.target.value.toUpperCase())} placeholder="22AAAAA0000A1Z5" maxLength={15} />
        </div>

        {/* Discount */}
        <div style={styles.section}>
          <label style={styles.label}>Discount (Rs)</label>
          <input
            type="number"
            style={styles.input}
            value={(discountPaise / 100).toFixed(2)}
            onChange={(e) => setDiscountPaise(Math.max(0, parseFloat(e.target.value) * 100 || 0))}
            min="0"
            step="0.01"
          />
        </div>

        {/* Payment split */}
        <div style={styles.section}>
          <label style={styles.label}>Payment Split</label>
          {payments.map((pay, i) => (
            <div key={i} style={styles.paymentRow}>
              <select
                value={pay.type}
                onChange={(e) => handleUpdatePayment(i, "type", e.target.value)}
                style={styles.select}
              >
                {TENDER_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
              <input
                type="number"
                style={{ ...styles.input, flex: 1 }}
                value={(pay.amount_paise / 100).toFixed(2)}
                onChange={(e) => handleUpdatePayment(i, "amount_paise", Math.max(0, parseFloat(e.target.value) * 100 || 0))}
                step="0.01"
                min="0"
              />
              {payments.length > 1 && (
                <button onClick={() => handleRemovePayment(i)} style={styles.removePayBtn}>&times;</button>
              )}
            </div>
          ))}
          <button onClick={handleAddPayment} style={styles.addPaymentBtn}>+ Add Payment</button>
        </div>

        {/* Summary */}
        <div style={styles.summary}>
          <div>Total: <strong>Rs {totalRupees}</strong></div>
          <div>Paid: <strong style={{ color: isOverpaid ? "#ff9800" : "#4caf50" }}>Rs {(paidPaise / 100).toFixed(2)}</strong></div>
          {isOverpaid && (
            <div style={{ color: "#ff9800", fontSize: 12 }}>Change: Rs {((paidPaise - totalPaise) / 100).toFixed(2)}</div>
          )}
          {error && <div style={{ color: "#e94560", fontSize: 12, marginTop: 4 }}>{error}</div>}
        </div>

        {/* Confirm */}
        <button onClick={handleConfirm} style={styles.confirmBtn}>
          Confirm Payment — Rs {totalRupees}
        </button>
      </div>
    </div>
  );
}

const styles = {
  overlay: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 },
  modal: { background: "#16213e", borderRadius: 12, width: "min(500px, 90vw)", maxHeight: "90vh", overflowY: "auto", padding: 20 },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  modalTitle: { margin: 0, fontSize: 18, color: "#e0e0e0" },
  closeBtn: { background: "transparent", border: "none", color: "#888", fontSize: 24, cursor: "pointer" },
  cartSummary: { background: "#0d1117", borderRadius: 8, padding: 8, marginBottom: 12, fontSize: 12 },
  cartItem: { display: "flex", justifyContent: "space-between", padding: "3px 0", color: "#aaa" },
  section: { marginBottom: 12 },
  label: { display: "block", fontSize: 12, color: "#888", marginBottom: 4 },
  input: { width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #0f3460", background: "#0d1117", color: "#e0e0e0", fontSize: 14, boxSizing: "border-box" },
  select: { padding: "8px 10px", borderRadius: 6, border: "1px solid #0f3460", background: "#0d1117", color: "#e0e0e0", fontSize: 13 },
  paymentRow: { display: "flex", gap: 8, alignItems: "center", marginBottom: 4 },
  removePayBtn: { padding: "4px 8px", background: "transparent", border: "1px solid #555", color: "#e94560", borderRadius: 4, cursor: "pointer" },
  addPaymentBtn: { background: "transparent", border: "1px dashed #0f3460", color: "#888", padding: "6px 12px", borderRadius: 6, cursor: "pointer", fontSize: 12 },
  summary: { background: "#0d1117", borderRadius: 8, padding: 12, marginBottom: 12, fontSize: 14 },
  confirmBtn: { width: "100%", padding: "14px 0", background: "#4caf50", border: "none", borderRadius: 8, color: "#fff", fontWeight: 700, fontSize: 16, cursor: "pointer" },
};
