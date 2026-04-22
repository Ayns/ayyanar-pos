import React, { useState, useMemo } from 'react';

export default function ZReport({ dailySales, cart, pendingBills, online }) {
  const today = new Date().toISOString().split('T')[0];

  const totalRevenue = useMemo(
    () => cart.reduce((sum, item) => sum + item.mrp_paise * item.qty, 0),
    [cart]
  );

  const totalItems = useMemo(
    () => cart.reduce((sum, item) => sum + item.qty, 0),
    [cart]
  );

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Z-Report — {today}</h2>

      <div style={styles.card}>
        <div style={styles.metricRow}>
          <span className="label">Total Sales</span>
          <span style={styles.metricValue}>&#8377;{(totalRevenue / 100).toFixed(2)}</span>
        </div>
        <div style={styles.metricRow}>
          <span className="label">Transactions</span>
          <span style={styles.metricValue}>{totalItems > 0 ? '1' : '0'}</span>
        </div>
        <div style={styles.metricRow}>
          <span className="label">Items Sold</span>
          <span style={styles.metricValue}>{totalItems}</span>
        </div>
      </div>

      {pendingBills.length > 0 && (
        <div style={styles.pendingCard}>
          <h3 style={{ color: '#ff9800', margin: '0 0 8px 0', fontSize: 14 }}>
            Pending Sync ({pendingBills.length})
          </h3>
          {pendingBills.map((bill) => (
            <div key={bill.id} style={styles.pendingItem}>
              <span>Invoice #{bill.invoiceNo}</span>
              <span>&#8377;{(bill.total / 100).toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}

      {dailySales?.stores?.length > 0 && (
        <div style={styles.card}>
          <h3 style={{ margin: '0 0 8px 0', fontSize: 14 }}>Multi-store Summary</h3>
          {dailySales.stores.map((s) => (
            <div key={s.storeId} style={styles.metricRow}>
              <span>{s.storeId}</span>
              <span>&#8377;{(s.totalSales * 100).toFixed(2)} ({s.transactionCount})</span>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 16, fontSize: 12, color: '#666' }}>
        <p>Online: {online ? '&#10004;' : '&#10060;'} Offline</p>
        <p>Z-reports are stored locally in IndexedDB.</p>
      </div>
    </div>
  );
}

const styles = {
  container: { padding: 16, overflowY: 'auto' },
  title: { margin: '0 0 16px 0', fontSize: 18, color: '#e0e0e0' },
  card: { background: '#16213e', borderRadius: 10, padding: 12, marginBottom: 12 },
  pendingCard: { background: '#16213e', borderRadius: 10, padding: 12, marginBottom: 12, border: '1px solid #ff980044' },
  metricRow: { display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 14, color: '#e0e0e0' },
  metricValue: { fontWeight: 700, color: '#e94560' },
  pendingItem: { display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12, color: '#aaa' },
};
