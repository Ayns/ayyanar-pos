/**
 * AYY-34 — POS React Context + Reducer.
 *
 * Manages cart state, catalogue, online status, pending bills.
 */

import { useReducer, useEffect, createContext, useContext } from "react";

const POSContext = createContext(null);

const initialState = {
  products: [],
  cart: [],
  online: typeof navigator !== "undefined" && navigator.onLine,
  pendingBills: [],
  cashRegister: {
    openingFloat: 0,
    expected: 0,
    actual: 0,
    variance: 0,
  },
};

/** Extract a stable cart key from an item regardless of field name. */
function cartKey(item) {
  return item.variant_id || item.id || item.sku || "";
}

function posReducer(state, action) {
  switch (action.type) {
    case "SET_PRODUCTS":
      return { ...state, products: action.payload };

    case "ADD_TO_CART": {
      const key = cartKey(action.payload);
      if (!key) return state;
      const existing = state.cart.find((c) => cartKey(c) === key);
      let newCart;
      if (existing) {
        newCart = state.cart.map((c) =>
          cartKey(c) === key
            ? { ...c, qty: c.qty + (action.payload.qty || 1) }
            : c
        );
      } else {
        newCart = [
          ...state.cart,
          { ...action.payload, qty: action.payload.qty || 1 },
        ];
      }
      return { ...state, cart: newCart };
    }

    case "REMOVE_FROM_CART": {
      const rmKey = action.payload;
      return {
        ...state,
        cart: state.cart.filter((c) => cartKey(c) !== rmKey),
      };
    }

    case "SET_CART_QTY": {
      const key = action.payload.id;
      return {
        ...state,
        cart: state.cart.map((c) =>
          cartKey(c) === key ? { ...c, qty: action.payload.qty } : c
        ),
      };
    }

    case "CLEAR_CART":
      return { ...state, cart: [] };

    case "SET_ONLINE":
      return { ...state, online: action.payload };

    case "SET_PENDING_BILLS":
      return { ...state, pendingBills: action.payload };

    case "ADD_PENDING_BILL":
      return {
        ...state,
        pendingBills: [...state.pendingBills, action.payload],
      };

    case "REMOVE_PENDING_BILL":
      return {
        ...state,
        pendingBills: state.pendingBills.filter((b) => b.id !== action.payload),
      };

    case "SET_CASH_REGISTER":
      return { ...state, cashRegister: action.payload };

    default:
      return state;
  }
}

export function POSProvider({ children }) {
  const [state, dispatch] = useReducer(posReducer, initialState);

  // Online/offline detection
  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleOnline = () => dispatch({ type: "SET_ONLINE", payload: true });
    const handleOffline = () => dispatch({ type: "SET_ONLINE", payload: false });
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return (
    <POSContext.Provider value={{ state, dispatch }}>
      {children}
    </POSContext.Provider>
  );
}

export function usePOS() {
  const ctx = useContext(POSContext);
  if (!ctx) throw new Error("usePOS must be used within POSProvider");
  return ctx;
}
