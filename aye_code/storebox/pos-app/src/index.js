import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { POSProvider } from './POSContext';

// Register service worker for offline support
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then((reg) => console.log('SW registered:', reg.scope))
      .catch((err) => console.log('SW registration failed:', err));
  });
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <POSProvider>
      <App />
    </POSProvider>
  </React.StrictMode>
);
