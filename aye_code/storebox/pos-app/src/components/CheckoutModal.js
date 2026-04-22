import React, { useState } from 'react';

const PAYMENT_METHODS = [
  { value: 'CASH', label: 'Cash', icon: '&#128179;' },
  { value: 'UPI', label: 'UPI', icon: '&#128241;' },
  { value: 'CARD', label: 'Card', icon: '&#128179;' },
  { value: 'CREDIT', label: 'Credit', icon: '&#128179;' },
];

export default function CheckoutModal({ cart, totalPaise, onClose, onConfirm }) {
  const [step, setStep] = useState('payment'); // payment | confirm | receipt
  const [payments, setPayments] = useState([]);
  const [discountPaise, setDiscountPaise] = useState(0);
  const [customerName, setCustomerName] = useState('');
  const [customerGSTIN, setCustomerGSTIN] = useState('');
  const [result, setResult] = useState(null);

  const remaining = totalPaise - payments.reduce((s, p) => s + p.amount_paise, 0);

  const handleAmountAdd = (method) => {
    const maxForMethod = Math.max(0, remaining - payments.filter((p) => p.method !== method).reduce((s, p) => s + p.amount_paise, 0));
    if (maxForMethod <= 0) return;

    const existing = payments.find((p) => p.method === method);
    const amount = remaining;
    if (existing) {
      setPayments(payments.map((p) => p.method === method ? { ...p, amount_paise: amount } : p));
    } else {
      setPayments([...payments, { method, amount_paise: amount, txn_ref: null }]);
    }
  };

  const handleCheckout = async () => {
    if (remaining > 0) return;
    setStep('confirm');

    try {
      const billResult = await onConfirm({ payments: payments.map((p) => ({ method: p.method, amount_paise: p.amount_paise })), discountPaise, customerName, customerGSTIN });
      setResult(billResult);
      setStep('receipt');
    } catch (err) {
      alert('Checkout failed: ' + err.message);
    }
  };

  if (step === 'receipt' && result) {
    return (
      <div style={styles.modal}>
        <div style={styles.modalContent}>
          <h2 style={{ color: '#4caf50', marginBottom: 12 }}>&#10004; Sale Complete</h2>
          <div style={styles.receipt}>
            <p style={{ textAlign: 'center', fontWeight: 700, fontSize: 18 }}>AYY POS Terminal</p>
            <p style={{ textAlign: 'center', fontSize: 11, color: '#888' }}>Store: store-0001</p>
            <hr style={{ border: 'none', borderTop: '1px dashed #444', margin: '8px 0' }} />
            <p>Invoice: <strong>{result.invoice_no}</strong></p>
            {result.customer_name && <p>Customer: {result.customer_name}</p>}
            <hr style={{ border: 'none', borderTop: '1px dashed #444', margin: '8px 0' }} />
            {cart.map((item) => (
              <div key={item.variant_id} style={styles.receiptLine}>
                <span>{item.style} ({item.size}) x{item.qty}</span>
                <span>&#8377;{(item.mrp_paise * item.qty / 100).toFixed(2)}</span>
              </div>
            ))}
            <hr style={{ border: 'none', borderTop: '1px dashed #444', margin: '8px 0' }} />
            <div style={styles.receiptTotal}>
              <span>Total Paid</span>
              <span>&#8377;{(totalPaise / 100).toFixed(2)}</span>
            </div>
            <hr style={{ border: 'none', borderTop: '1px dashed #444', margin: '8px 0' }} />
            {result.gst_lines?.map((gst, i) => (
              <div key={i} style={{ fontSize: 11, color: '#888' }}>
                GST: Base &#8377;{gst.base_paise / 100} | {gst.cgst_paise > 0 && `CGST &#8377;${gst.cgst_paise / 100} `}{gst.igst_paise > 0 && `IGST &#8377;${gst.igst_paise / 100}`}
              </div>
            ))}
            <p style={{ textAlign: 'center', marginTop: 12, fontSize: 11, color: '#888' }}>Thank you for shopping!</p>
          </div>
          <button style={styles.closeBtn} onClick={onClose}>Close / New Sale</button>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.modal}>
      <div style={styles.modalContent}>
        {step === 'confirm' ? (
          <div>
            <h2 style={{ marginBottom: 16 }}>Confirm Payment</h2>
            {payments.map((p, i) => (
              <div key={i} style={styles.paymentRow}>
                <span>{p.method}</span>
                <span>&#8377;{(p.amount_paise / 100).toFixed(2)}</span>
              </div>
            ))}
            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <button style={styles.cancelBtn} onClick={() => setStep('payment')}>Back</button>
              <button style={styles.confirmBtn} onClick={handleCheckout}>Confirm</button>
            </div>
          </div>
        ) : (
          <div>
            <h2 style={{ marginBottom: 12 }}>Payment Split</h2>

            <div style={{ marginBottom: 8 }}>
              <label style={styles.label}>Customer Name (optional)</label>
              <input
                style={styles.textInput}
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="Walk-in customer"
              />
            </div>
            <div style={{ marginBottom: 8 }}>
              <label style={styles.label}>GSTIN (optional, for B2B)</label>
              <input
                style={styles.textInput}
                value={customerGSTIN}
                onChange={(e) => setCustomerGSTIN(e.target.value)}
                placeholder="22AAAAA0000A1Z5"
                maxLength={15}
              />
            </div>

            <div style={styles.paymentGrid}>
              {PAYMENT_METHODS.map((m) => (
                <button
                  key={m.value}
                  onClick={() => handleAmountAdd(m.value)}
                  style={{
                    ...styles.methodBtn,
                    ...(remaining > 0 && payments.find((p) => p.method === m.value)?.amount_paise >= remaining ? styles.methodBtnFull : {}),
                  }}
                >
                  <span dangerouslySetInnerHTML={{ __html: m.icon }} />
                  <span>{m.label}</span>
                  {payments.find((p) => p.method === m.value) && (
                    <span style={styles.methodAmount}>&#8377;{(payments.find((p) => p.method === m.value).amount_paise / 100).toFixed(2)}</span>
                  )}
                </button>
              ))}
            </div>

            {remaining > 0 && (
              <div style={{ color: '#ff9800', fontSize: 13, marginTop: 8 }}>
                Remaining: &#8377;{(remaining / 100).toFixed(2)}
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <button style={styles.cancelBtn} onClick={onClose}>Cancel</button>
              <button
                style={styles.confirmBtn}
                disabled={remaining > 0}
                onClick={() => setStep('confirm')}
              >
                Proceed ({payments.length} method{payments.length !== 1 ? 's' : ''})
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  modal: {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  },
  modalContent: {
    background: '#1a1a2e', borderRadius: 12, padding: 20, width: '90%', maxWidth: 450,
    maxHeight: '85vh', overflowY: 'auto', border: '1px solid #0f3460',
  },
  receipt: { textAlign: 'left', fontSize: 13, color: '#e0e0e0' },
  receiptLine: { display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: 12 },
  receiptTotal: { display: 'flex', justifyContent: 'space-between', fontWeight: 700, fontSize: 15, marginTop: 4 },
  closeBtn: {
    width: '100%', padding: '12px 0', borderRadius: 8, border: 'none',
    background: '#4caf50', color: '#fff', fontSize: 15, fontWeight: 700, cursor: 'pointer', marginTop: 12,
  },
  paymentGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, margin: '8px 0' },
  methodBtn: {
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
    padding: 12, borderRadius: 8, border: '1px solid #0f3460',
    background: '#16213e', color: '#e0e0e0', cursor: 'pointer', fontSize: 12,
  },
  methodBtnFull: { background: '#0f3460', borderColor: '#4caf50' },
  methodAmount: { fontSize: 13, fontWeight: 700, color: '#4caf50' },
  paymentRow: { display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 13, color: '#e0e0e0' },
  textInput: {
    width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #0f3460',
    background: '#0f3460', color: '#e0e0e0', fontSize: 13, outline: 'none',
  },
  label: { display: 'block', fontSize: 11, color: '#888', marginBottom: 4 },
  cancelBtn: {
    flex: 1, padding: '10px 0', borderRadius: 8, border: '1px solid #0f3460',
    background: 'none', color: '#aaa', fontSize: 14, cursor: 'pointer',
  },
  confirmBtn: {
    flex: 1, padding: '10px 0', borderRadius: 8, border: 'none',
    background: '#4caf50', color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer',
    opacity: 0.5,
  },
};
