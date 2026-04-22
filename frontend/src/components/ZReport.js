/**
 * AYY-34 — Z-Report component.
 * End-of-day summary with pending bills status.
 */

import React from "react";

export default function ZReport({ pendingBills, online, onSyncPending }) {
  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Z-Report</h2>

      {/* Connection status */}
      <div style={styles.statusRow}>
        <span style={{ color: online ? "#4caf50" : "#ff9800" }}>
          {online ? "Online" : "Offline"}
        </span>
        <span style={styles.pendingCount}>
          Pending: {pendingBills?.length || 0}
        </span>
      </div>

      {/* Pending bills */}
      {(pendingBills?.length || 0) > 0 && (
        <div style={styles.pendingSection}>
          <div style={styles.pendingHeader}>
            <span>Pending Bills to Sync</span>
            <button onClick={onSyncPending} style={styles.syncBtn}>Sync Now</button>
          </div>
          {pendingBills.map((bill) => (
            <div key={bill.id} style={styles.pendingItem}>
              <span>{bill.invoiceNo}</span>
              <span style={styles.pendingAmount}>Rs {((bill.total || 0) / 100).toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Today's summary */}
      <div style={styles.summarySection}>
        <div style={styles.summaryCard}>
          <div style={styles.summaryLabel}>Total Bills</div>
          <div style={styles.summaryValue}>0</div>
        </div>
        <div style={styles.summaryCard}>
          <div style={styles.summaryLabel}>Sales</div>
          <div style={styles.summaryValue}>Rs 0</div>
        </div>
        <div style={styles.summaryCard}>
          <div style={styles.summaryLabel}>Discounts</div>
          <div style={styles.summaryValue}>Rs 0</div>
        </div>
        <div style={styles.summaryCard}>
          <div style={styles.summaryLabel}>Tax</div>
          <div style={styles.summaryValue}>Rs 0</div>
        </div>
      </div>

      <div style={styles.emptyHint}>
        No Z-report data for today yet. Bills will appear here at end of day.
      </div>
    </div>
  );
}

const styles = {
  container: { padding: 16, overflowY: "auto", flex: 1 },
  title: { margin: "0 0 16px", fontSize: 18, color: "#e0e0e0" },
  statusRow: { display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid #0f3460" },
  pendingCount: { background: "#ff9800", color: "#000", padding: "2px 10px", borderRadius: 10, fontSize: 12, fontWeight: 700 },
  pendingSection: { margin: "16px 0" },
  pendingHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  syncBtn: { background: "#4caf50", border: "none", color: "#fff", padding: "6px 12px", borderRadius: 6, cursor: "pointer", fontSize: 12 },
  pendingItem: { display: "flex", justifyContent: "space-between", padding: "6px 8px", background: "#0f1923", borderRadius: 4, marginBottom: 4, fontSize: 13 },
  pendingAmount: { color: "#e94560", fontWeight: 600 },
  summarySection: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, margin: "16px 0" },
  summaryCard: { background: "#0f1923", borderRadius: 8, padding: 12, textAlign: "center" },
  summaryLabel: { fontSize: 11, color: "#888" },
  summaryValue: { fontSize: 18, fontWeight: 700, marginTop: 4 },
  emptyHint: { color: "#555", textAlign: "center", marginTop: 32, fontSize: 13 },
};
