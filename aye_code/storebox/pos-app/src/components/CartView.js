import React from 'react';

export default function CartView({ cart, onRemove, onUpdateQty, onClear, onCheckout }) {
  const totalPaise = cart.reduce((sum, item) => sum + item.mrp_paise * item.qty, 0);
  const totalItems = cart.reduce((sum, item) => sum + item.qty, 0);

  if (cart.length === 0) {
    return (
      <div style={styles.empty}>
        <div style={styles.emptyIcon}>&#9881;&#65039;</div>
        <p>Cart is empty</p>
        <p style={{ fontSize: 12, color: '#666' }}>Tap products on the left to add items</p>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.cartTitle}>Cart ({totalItems} {totalItems === 1 ? 'item' : 'items'})</span>
        <button onClick={onClear} style={styles.clearBtn}>Clear</button>
      </div>

      <div style={styles.items}>
        {cart.map((item) => (
          <div key={item.variant_id} style={styles.itemRow}>
            <div style={styles.itemInfo}>
              <div style={styles.itemName}>{item.style} — {item.color}</div>
              <div style={styles.itemVariant}>Size: {item.size} | &#8377;{(item.mrp_paise / 100).toFixed(2)} each</div>
            </div>
            <div style={styles.itemActions}>
              <button onClick={() => onUpdateQty(item.variant_id, item.qty - 1)} style={styles.qtyBtn}>-</button>
              <span style={styles.qtyText}>{item.qty}</span>
              <button onClick={() => onUpdateQty(item.variant_id, item.qty + 1)} style={styles.qtyBtn}>+</button>
              <button onClick={() => onRemove(item.variant_id)} style={styles.removeBtn} title="Remove">&#10005;</button>
            </div>
            <div style={styles.itemTotal}>&#8377;{(item.mrp_paise * item.qty / 100).toFixed(2)}</div>
          </div>
        ))}
      </div>

      <div style={styles.footer}>
        <div style={styles.totalRow}>
          <span>Total</span>
          <span style={styles.totalValue}>&#8377;{(totalPaise / 100).toFixed(2)}</span>
        </div>
        <button
          onClick={onCheckout}
          style={styles.checkoutBtn}
          disabled={cart.length === 0}
        >
          &#128196; Checkout
        </button>
      </div>
    </div>
  );
}

const styles = {
  container: { display: 'flex', flexDirection: 'column', height: '100%' },
  empty: {
    flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', color: '#666', gap: 8,
  },
  emptyIcon: { fontSize: 48 },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '10px 12px', borderBottom: '1px solid #0f3460',
  },
  cartTitle: { fontWeight: 600, fontSize: 14, color: '#e0e0e0' },
  clearBtn: { background: 'none', border: 'none', color: '#e94560', cursor: 'pointer', fontSize: 12 },
  items: { flex: 1, overflowY: 'auto', padding: '8px 0' },
  itemRow: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px',
    borderBottom: '1px solid #0f346033',
  },
  itemInfo: { flex: 1 },
  itemName: { fontSize: 13, fontWeight: 500, color: '#e0e0e0' },
  itemVariant: { fontSize: 11, color: '#888' },
  itemActions: { display: 'flex', alignItems: 'center', gap: 4 },
  qtyBtn: {
    width: 24, height: 24, borderRadius: 4, border: '1px solid #0f3460',
    background: '#16213e', color: '#e0e0e0', cursor: 'pointer', fontSize: 14,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  qtyText: { fontSize: 13, color: '#e0e0e0', minWidth: 20, textAlign: 'center' },
  removeBtn: {
    width: 22, height: 22, borderRadius: 4, border: 'none',
    background: '#e9456033', color: '#e94560', cursor: 'pointer', fontSize: 12,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  itemTotal: { fontSize: 13, fontWeight: 600, color: '#e94560', minWidth: 60, textAlign: 'right' },
  footer: { padding: '10px 12px', borderTop: '1px solid #0f3460' },
  totalRow: {
    display: 'flex', justifyContent: 'space-between', marginBottom: 8,
    fontSize: 16, fontWeight: 600, color: '#e0e0e0',
  },
  totalValue: { color: '#e94560' },
  checkoutBtn: {
    width: '100%', padding: '12px 0', borderRadius: 8, border: 'none',
    background: '#e94560', color: '#fff', fontSize: 16, fontWeight: 700,
    cursor: 'pointer', letterSpacing: 0.5,
  },
};
