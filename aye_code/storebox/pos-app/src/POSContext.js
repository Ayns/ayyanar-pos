import React, { createContext, useContext, useReducer } from 'react';

const POSContext = createContext();

function posReducer(state, action) {
  switch (action.type) {
    case 'SET_PRODUCTS':
      return { ...state, products: action.payload };
    case 'ADD_TO_CART': {
      const existing = state.cart.find((c) => c.variant_id === action.payload.variant_id);
      if (existing) {
        return {
          ...state,
          cart: state.cart.map((c) =>
            c.variant_id === action.payload.variant_id
              ? { ...c, qty: c.qty + action.payload.qty }
              : c
          ),
        };
      }
      return { ...state, cart: [...state.cart, { ...action.payload, qty: action.payload.qty || 1 }] };
    }
    case 'REMOVE_FROM_CART':
      return { ...state, cart: state.cart.filter((c) => c.variant_id !== action.payload) };
    case 'CLEAR_CART':
      return { ...state, cart: [] };
    case 'SET_OFFLINE':
      return { ...state, online: false };
    case 'SET_ONLINE':
      return { ...state, online: true };
    case 'SET_PENDING_BILLS':
      return { ...state, pendingBills: action.payload };
    case 'ADD_PENDING_BILL':
      return { ...state, pendingBills: [...state.pendingBills, action.payload] };
    case 'CLEAR_PENDING':
      return { ...state, pendingBills: [] };
    case 'SET_LAST_Z_REPORT':
      return { ...state, lastZReport: action.payload };
    default:
      return state;
  }
}

export function POSProvider({ children }) {
  const initialState = {
    products: [],
    cart: [],
    online: navigator.onLine,
    pendingBills: [],
    lastZReport: null,
  };

  const [state, dispatch] = useReducer(posReducer, initialState);

  // Listen for online/offline events
  React.useEffect(() => {
    const handleOnline = () => dispatch({ type: 'SET_ONLINE' });
    const handleOffline = () => dispatch({ type: 'SET_OFFLINE' });
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return (
    <POSContext.Provider value={{ state, dispatch }}>
      {children}
    </POSContext.Provider>
  );
}

export function usePOS() {
  return useContext(POSContext);
}
