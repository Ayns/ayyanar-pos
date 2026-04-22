/**
 * AYY-34 — IndexedDB layer for POS terminal.
 *
 * Stores: pending-bills queue, catalogue-cache, z-reports, settings.
 * Used for offline-first operation (FR: Section 11.3).
 */

const DB_NAME = "ayy-pos-db";
const DB_VERSION = 1;

// Store names
const STORE_PENDING_BILLS = "pending-bills";
const STORE_CATALOGUE = "catalogue-cache";
const STORE_ZREPORTS = "z-reports";
const STORE_SETTINGS = "settings";

let _db = null;

function openDB() {
  if (_db) return Promise.resolve(_db);
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_PENDING_BILLS)) {
        const store = db.createObjectStore(STORE_PENDING_BILLS, { keyPath: "id" });
        store.createIndex("store_id", "store_id", { unique: false });
        store.createIndex("created_at", "created_at", { unique: false });
      }
      if (!db.objectStoreNames.contains(STORE_CATALOGUE)) {
        db.createObjectStore(STORE_CATALOGUE, { keyPath: "key" });
      }
      if (!db.objectStoreNames.contains(STORE_ZREPORTS)) {
        const store = db.createObjectStore(STORE_ZREPORTS, { keyPath: "id" });
        store.createIndex("date", "date", { unique: false });
      }
      if (!db.objectStoreNames.contains(STORE_SETTINGS)) {
        db.createObjectStore(STORE_SETTINGS, { keyPath: "key" });
      }
    };
    req.onsuccess = (e) => { _db = e.target.result; resolve(_db); };
    req.onerror = (e) => reject(e.target.error);
  });
}

async function addPendingBill(bill) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_PENDING_BILLS, "readwrite");
    tx.objectStore(STORE_PENDING_BILLS).put(bill);
    tx.oncomplete = () => resolve();
    tx.onerror = (e) => reject(e.target.error);
  });
}

async function getPendingBills() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_PENDING_BILLS, "readonly");
    const store = tx.objectStore(STORE_PENDING_BILLS);
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = (e) => reject(e.target.error);
  });
}

async function syncPendingBills(bills) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_PENDING_BILLS, "readwrite");
    const store = tx.objectStore(STORE_PENDING_BILLS);
    for (const bill of bills) {
      store.delete(bill.id);
    }
    tx.oncomplete = () => resolve();
    tx.onerror = (e) => reject(e.target.error);
  });
}

async function saveCatalogue(products) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CATALOGUE, "readwrite");
    tx.objectStore(STORE_CATALOGUE).put({ key: "catalogue", products, saved_at: new Date().toISOString() });
    tx.oncomplete = () => resolve();
    tx.onerror = (e) => reject(e.target.error);
  });
}

async function loadCatalogue() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CATALOGUE, "readonly");
    const req = tx.objectStore(STORE_CATALOGUE).get("catalogue");
    req.onsuccess = () => resolve(req.result?.products || null);
    req.onerror = (e) => reject(e.target.error);
  });
}

async function saveZReport(report) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_ZREPORTS, "readwrite");
    tx.objectStore(STORE_ZREPORTS).put(report);
    tx.oncomplete = () => resolve();
    tx.onerror = (e) => reject(e.target.error);
  });
}

async function getZReports() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_ZREPORTS, "readonly");
    const req = tx.objectStore(STORE_ZREPORTS).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = (e) => reject(e.target.error);
  });
}

export {
  addPendingBill,
  getPendingBills,
  syncPendingBills,
  saveCatalogue,
  loadCatalogue,
  saveZReport,
  getZReports,
  openDB,
};
