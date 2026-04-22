/**
 * AYY-26 — API client for POS terminal.
 *
 * Connects to the Django backend at /till/ and /api/ endpoints.
 * All requests use relative URLs (nginx reverse proxy handles routing).
 */

const BASE = ''; // Relative — served via nginx on the same host

async function fetchProducts() {
  const resp = await fetch(`${BASE}/till/`);
  if (!resp.ok) throw new Error('Failed to fetch products');
  return resp.json();
}

async function addToCart(variantId, qty = 1) {
  const resp = await fetch(`${BASE}/till/cart/add/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ variant_id: variantId, qty }),
  });
  if (!resp.ok) throw new Error('Failed to add to cart');
  return resp.json();
}

async function removeFromCart(variantId) {
  const resp = await fetch(`${BASE}/till/cart/remove/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ variant_id: variantId }),
  });
  if (!resp.ok) throw new Error('Failed to remove from cart');
  return resp.json();
}

async function checkout(cart, payments, discountPaise = 0, customerName = 'Walk-in', customerGSTIN = '') {
  const lines = cart.map((item) => ({
    variant_id: item.variant_id,
    qty: item.qty,
    hsn_code: item.hsn_code || '',
  }));

  const resp = await fetch(`${BASE}/till/checkout/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      payments,
      discount_paise: discountPaise,
      customer_name: customerName,
      customer_gstin: customerGSTIN,
      lines,
    }),
  });
  if (!resp.ok) throw new Error('Checkout failed');
  return resp.json();
}

async function getReceipt(invoiceId) {
  const resp = await fetch(`${BASE}/till/receipt/${invoiceId}/`);
  if (!resp.ok) throw new Error('Receipt not found');
  return resp.json();
}

async function getDailySales(date) {
  const resp = await fetch(`${BASE}/api/hoc/daily-sales/?date=${date}`);
  if (!resp.ok) throw new Error('Failed to fetch daily sales');
  return resp.json();
}

export {
  fetchProducts,
  addToCart,
  removeFromCart,
  checkout,
  getReceipt,
  getDailySales,
};
