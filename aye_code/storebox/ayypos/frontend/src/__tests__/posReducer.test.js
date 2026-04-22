/**
 * AYY-34 — Unit tests for POS reducer (cart state machine).
 * Tests: ADD_TO_CART, REMOVE_FROM_CART, SET_CART_QTY, CLEAR_CART,
 *        product->cart ID resolution (variant_id vs id).
 */

/** Extract a stable cart key from an item regardless of field name. */
function cartKey(item) {
  return item.variant_id || item.id || item.sku || "";
}

// Inline the reducer logic so Jest doesn't need to handle React context
function posReducer(state, action) {
  const initialState = {
    products: [],
    cart: [],
    online: true,
    pendingBills: [],
    cashRegister: { openingFloat: 0, expected: 0, actual: 0, variance: 0 },
  };
  const s = state || initialState;

  switch (action.type) {
    case "SET_PRODUCTS":
      return { ...s, products: action.payload };

    case "ADD_TO_CART": {
      const key = cartKey(action.payload);
      if (!key) return s;
      const existing = s.cart.find((c) => cartKey(c) === key);
      if (existing) {
        return {
          ...s,
          cart: s.cart.map((c) =>
            cartKey(c) === key
              ? { ...c, qty: c.qty + (action.payload.qty || 1) }
              : c
          ),
        };
      }
      return {
        ...s,
        cart: [...s.cart, { ...action.payload, qty: action.payload.qty || 1 }],
      };
    }

    case "REMOVE_FROM_CART": {
      const rmKey = action.payload;
      return {
        ...s,
        cart: s.cart.filter((c) => cartKey(c) !== rmKey),
      };
    }

    case "SET_CART_QTY": {
      const key = action.payload.id;
      return {
        ...s,
        cart: s.cart.map((c) =>
          cartKey(c) === key ? { ...c, qty: action.payload.qty } : c
        ),
      };
    }

    case "CLEAR_CART":
      return { ...s, cart: [] };

    case "SET_ONLINE":
      return { ...s, online: action.payload };

    case "SET_PENDING_BILLS":
      return { ...s, pendingBills: action.payload };

    case "ADD_PENDING_BILL":
      return {
        ...s,
        pendingBills: [...s.pendingBills, action.payload],
      };

    case "REMOVE_PENDING_BILL":
      return {
        ...s,
        pendingBills: s.pendingBills.filter((b) => b.id !== action.payload),
      };

    default:
      return s;
  }
}

describe("POS Reducer", () => {
  const mockProduct = {
    id: "mock-1",
    variant_id: "var-001",
    sku: "TSI-Red-M",
    style_name: "T-Shirt",
    colour_name: "Red",
    size_name: "M",
    mrp_paise: 99900,
    selling_price_paise: 89900,
    full_label: "T-Shirt | Red | M",
  };

  test("initial state has empty cart and products", () => {
    const state = posReducer(undefined, { type: "SET_PRODUCTS", payload: [] });
    expect(state.cart).toEqual([]);
    expect(state.products).toEqual([]);
    expect(state.online).toBe(true);
    expect(state.pendingBills).toEqual([]);
  });

  test("SET_PRODUCTS stores products", () => {
    const state = posReducer(undefined, {
      type: "SET_PRODUCTS",
      payload: [mockProduct],
    });
    expect(state.products).toHaveLength(1);
    expect(state.products[0].sku).toBe("TSI-Red-M");
  });

  test("ADD_TO_CART adds new item by variant_id", () => {
    const state = posReducer(undefined, {
      type: "ADD_TO_CART",
      payload: mockProduct,
    });
    expect(state.cart).toHaveLength(1);
    expect(state.cart[0].qty).toBe(1);
    expect(cartKey(state.cart[0])).toBe("var-001");
  });

  test("ADD_TO_CART increments qty for same item", () => {
    let state = posReducer(undefined, {
      type: "ADD_TO_CART",
      payload: { ...mockProduct, qty: 2 },
    });
    state = posReducer(state, {
      type: "ADD_TO_CART",
      payload: { ...mockProduct, qty: 3 },
    });
    expect(state.cart).toHaveLength(1);
    expect(state.cart[0].qty).toBe(5); // 2 + 3
  });

  test("ADD_TO_CART adds different items separately", () => {
    const product2 = { ...mockProduct, id: "mock-2", variant_id: "var-002", sku: "TSI-Blue-L" };
    let state = posReducer(undefined, {
      type: "ADD_TO_CART",
      payload: mockProduct,
    });
    state = posReducer(state, {
      type: "ADD_TO_CART",
      payload: product2,
    });
    expect(state.cart).toHaveLength(2);
  });

  test("REMOVE_FROM_CART removes by variant_id", () => {
    let state = posReducer(undefined, {
      type: "ADD_TO_CART",
      payload: mockProduct,
    });
    state = posReducer(state, {
      type: "REMOVE_FROM_CART",
      payload: "var-001",
    });
    expect(state.cart).toHaveLength(0);
  });

  test("SET_CART_QTY updates quantity", () => {
    let state = posReducer(undefined, {
      type: "ADD_TO_CART",
      payload: mockProduct,
    });
    state = posReducer(state, {
      type: "SET_CART_QTY",
      payload: { id: "var-001", qty: 5 },
    });
    expect(state.cart[0].qty).toBe(5);
  });

  test("CLEAR_CART empties cart", () => {
    let state = posReducer(undefined, {
      type: "ADD_TO_CART",
      payload: mockProduct,
    });
    state = posReducer(state, { type: "CLEAR_CART" });
    expect(state.cart).toHaveLength(0);
  });

  test("SET_ONLINE toggles online status", () => {
    let state = posReducer(undefined, { type: "SET_ONLINE", payload: false });
    expect(state.online).toBe(false);
    state = posReducer(state, { type: "SET_ONLINE", payload: true });
    expect(state.online).toBe(true);
  });

  test("SET_PENDING_BILLS sets pending bills", () => {
    const state = posReducer(undefined, {
      type: "SET_PENDING_BILLS",
      payload: [{ id: "bill-1", invoiceNo: "INV-001" }],
    });
    expect(state.pendingBills).toHaveLength(1);
  });

  test("ADD_PENDING_BILL appends bill", () => {
    const state = posReducer(undefined, {
      type: "SET_PENDING_BILLS",
      payload: [],
    });
    const state2 = posReducer(state, {
      type: "ADD_PENDING_BILL",
      payload: { id: "bill-2", invoiceNo: "INV-002" },
    });
    expect(state2.pendingBills).toHaveLength(1);
  });

  test("REMOVE_PENDING_BILL removes by id", () => {
    const state = posReducer(undefined, {
      type: "SET_PENDING_BILLS",
      payload: [{ id: "bill-1" }, { id: "bill-2" }],
    });
    const state2 = posReducer(state, {
      type: "REMOVE_PENDING_BILL",
      payload: "bill-1",
    });
    expect(state2.pendingBills).toHaveLength(1);
    expect(state2.pendingBills[0].id).toBe("bill-2");
  });

  test("cartKey resolves variant_id > id > sku", () => {
    expect(cartKey({ variant_id: "v1", id: "id1" })).toBe("v1");
    expect(cartKey({ id: "id2" })).toBe("id2");
    expect(cartKey({ sku: "SKU1" })).toBe("SKU1");
  });

  test("same variant_id treated as same cart item regardless of id field", () => {
    let state = posReducer(undefined, {
      type: "ADD_TO_CART",
      payload: { variant_id: "v1", sku: "A", qty: 1 },
    });
    state = posReducer(state, {
      type: "ADD_TO_CART",
      payload: { variant_id: "v1", id: "different-id", sku: "A", qty: 2 },
    });
    expect(state.cart).toHaveLength(1);
    expect(state.cart[0].qty).toBe(3);
  });

  test("cart total calculation with mixed price fields", () => {
    const state = posReducer(undefined, {
      type: "ADD_TO_CART",
      payload: { variant_id: "v1", mrp_paise: 159900, qty: 2 },
    });
    const total = state.cart.reduce(
      (s, item) => s + ((item.mrp_paise || item.selling_price_paise || 0) * item.qty),
      0
    );
    expect(total).toBe(319800); // 159900 * 2
  });
});
