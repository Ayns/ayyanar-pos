/**
 * AYY-26 — IndexedDB layer for offline bill persistence and pending queue.
 *
 * Stores:
 * - `pending-bills`: bills created while offline, queued for sync when back online
 * - `catalogue-cache`: last known product catalogue for offline search
 * - `settings`: local POS settings (store ID, etc.)
 */

const DB_NAME = 'ayy-pos';
const DB_VERSION = 1;

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;

      // Pending bills queue: stores bills to sync when back online
      if (!db.objectStoreNames.contains('pending-bills')) {
        const store = db.createObjectStore('pending-bills', { keyPath: 'id' });
        store.createIndex('status', 'status', { unique: false });
        store.createIndex('created_at', 'created_at', { unique: false });
      }

      // Catalogue cache: products pulled from API, used for offline search
      if (!db.objectStoreNames.contains('catalogue-cache')) {
        const store = db.createObjectStore('catalogue-cache', { keyPath: 'variant_id' });
        store.createIndex('style', 'style', { unique: false });
        store.createIndex('category', 'category', { unique: false });
      }

      // Settings store
      if (!db.objectStoreNames.contains('settings')) {
        db.createObjectStore('settings', { keyPath: 'key' });
      }

      // Daily Z-reports
      if (!db.objectStoreNames.contains('z-reports')) {
        const store = db.createObjectStore('z-reports', { keyPath: 'date' });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// ── Pending Bills ──

async function addPendingBill(bill) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('pending-bills', 'readwrite');
    const store = tx.objectStore('pending-bills');
    bill.status = 'pending';
    const request = store.put(bill);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getPendingBills() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('pending-bills', 'readonly');
    const store = tx.objectStore('pending-bills');
    const index = store.index('status');
    const request = index.getAll('pending');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function markBillSynced(billId) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('pending-bills', 'readwrite');
    const store = tx.objectStore('pending-bills');
    const request = store.get(billId);
    request.onsuccess = () => {
      const bill = request.result;
      if (bill) {
        bill.status = 'synced';
        store.put(bill);
      }
      resolve();
    };
    request.onerror = () => reject(request.error);
  });
}

async function clearPendingBills() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('pending-bills', 'readwrite');
    const store = tx.objectStore('pending-bills');
    const request = store.clear();
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

// ── Catalogue Cache ──

async function saveCatalogue(products) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('catalogue-cache', 'readwrite');
    const store = tx.objectStore('catalogue-cache');
    store.delete('all').catch(() => {}); // Clear existing
    products.forEach((p) => store.put(p));
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function getCachedCatalogue() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('catalogue-cache', 'readonly');
    const store = tx.objectStore('catalogue-cache');
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// ── Z-Reports ──

async function saveZReport(date, report) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('z-reports', 'readwrite');
    const store = tx.objectStore('z-reports');
    const request = store.put({ date, ...report });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getZReport(date) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('z-reports', 'readonly');
    const store = tx.objectStore('z-reports');
    const request = store.get(date);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// ── Settings ──

async function getSetting(key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('settings', 'readonly');
    const store = tx.objectStore('settings');
    const request = store.get(key);
    request.onsuccess = () => resolve(request.result ? request.result.value : null);
    request.onerror = () => reject(request.error);
  });
}

async function setSetting(key, value) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('settings', 'readwrite');
    const store = tx.objectStore('settings');
    const request = store.put({ key, value });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export {
  openDB,
  addPendingBill,
  getPendingBills,
  markBillSynced,
  clearPendingBills,
  saveCatalogue,
  getCachedCatalogue,
  saveZReport,
  getZReport,
  getSetting,
  setSetting,
};
