import React from 'react';
import { usePOS } from './POSContext';

export default function OfflineIndicator() {
  const { state } = usePOS();

  if (state.online) return null;

  return (
    <div style={styles.banner}>
      <span style={styles.dot} />
      <span style={styles.text}>Offline — bills saved locally, will sync when connection restored</span>
    </div>
  );
}

const styles = {
  banner: {
    background: '#ff9800', color: '#000', padding: '6px 12px', fontSize: 12,
    fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8,
  },
  dot: {
    width: 8, height: 8, borderRadius: '50%', background: '#000',
    animation: 'pulse 1.5s infinite',
  },
  text: 'Offline mode',
};

// Inject pulse animation
const styleEl = document.createElement('style');
styleEl.textContent = '@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}';
if (typeof document !== 'undefined') document.head.appendChild(styleEl);
