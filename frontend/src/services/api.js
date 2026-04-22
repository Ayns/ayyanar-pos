/**
 * AYY-34 — Backend API client.
 *
 * Connects to the Django backend at /api/ and /till/ endpoints.
 */

const BASE_URL = "/api";

async function fetchCatalogue() {
  const resp = await fetch(`${BASE_URL}/till/`);
  if (!resp.ok) throw new Error("Failed to fetch catalogue");
  return resp.json();
}

async function searchCatalogue(query) {
  if (!query) return [];
  const resp = await fetch(`${BASE_URL}/catalogue/search/?q=${encodeURIComponent(query)}`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.variants || [];
}

async function checkout(lines, payments, discountPaise = 0, customerName = "Walk-in", customerGSTIN = "") {
  const resp = await fetch(`${BASE_URL}/till/checkout/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      lines,
      payments,
      discount_paise: discountPaise,
      customer_name: customerName,
      customer_gstin: customerGSTIN,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || "Checkout failed");
  }
  return resp.json();
}

async function createReturn(billNumber, lines, reason = "Customer choice", refundMode = "original_tender") {
  const resp = await fetch(`${BASE_URL}/till/returns/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      bill_number: billNumber,
      reason,
      refund_mode: refundMode,
      lines,
    }),
  });
  if (!resp.ok) throw new Error("Return failed");
  return resp.json();
}

async function getDailySales(date) {
  const resp = await fetch(`${BASE_URL}/reporting/daily-sales/?date=${date}`);
  if (!resp.ok) throw new Error("Failed to fetch daily sales");
  return resp.json();
}

async function getZReport(date) {
  const resp = await fetch(`${BASE_URL}/reporting/z-report/?date=${date}`);
  if (!resp.ok) throw new Error("Failed to fetch Z report");
  return resp.json();
}

async function getPendingBills() {
  const resp = await fetch(`${BASE_URL}/sync/outbox/?status=pending`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.items || [];
}

async function drainOutbox(storeId) {
  const resp = await fetch(`${BASE_URL}/sync/drain/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ store_id: storeId }),
  });
  if (!resp.ok) throw new Error("Drain failed");
  return resp.json();
}

export {
  fetchCatalogue,
  searchCatalogue,
  checkout,
  createReturn,
  getDailySales,
  getZReport,
  getPendingBills,
  drainOutbox,
};
