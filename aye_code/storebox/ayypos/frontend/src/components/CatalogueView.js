/**
 * AYY-34 — Catalogue view component.
 * FR-POS-001, FR-POS-002: Fast search and grid display.
 */

import React, { useState, useMemo } from "react";

export default function CatalogueView({ products, searchQuery, searchResults, onSearch, onAddToCart }) {
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [selectedStyle, setSelectedStyle] = useState(null);

  const displayedProducts = searchQuery
    ? (searchResults.length > 0 ? searchResults : products)
    : products;

  const groupedByStyle = useMemo(() => {
    const groups = {};
    for (const p of displayedProducts) {
      const key = p.style_code || p.style_name;
      if (!groups[key]) groups[key] = { code: key, name: p.style_name || p.style_code, variants: [] };
      groups[key].variants.push(p);
    }
    return Object.values(groups);
  }, [displayedProducts]);

  return (
    <div style={styles.container}>
      {/* Search bar */}
      <div style={styles.searchBar}>
        <input
          type="text"
          placeholder="Search by barcode, SKU, or style name..."
          value={searchQuery}
          onChange={(e) => onSearch(e.target.value)}
          style={styles.searchInput}
        />
        {searchQuery && (
          <button onClick={() => onSearch("")} style={styles.clearBtn}>&times;</button>
        )}
      </div>

      {/* Category pills */}
      <div style={styles.filterBar}>
        <button
          onClick={() => setCategoryFilter("all")}
          style={{ ...styles.filterBtn, ...(categoryFilter === "all" ? styles.filterBtnActive : {}) }}
        >
          All
        </button>
        {groupedByStyle.slice(0, 8).map((g) => (
          <button
            key={g.code}
            onClick={() => setCategoryFilter(g.code)}
            style={{
              ...styles.filterBtn,
              ...(categoryFilter === g.code ? styles.filterBtnActive : {}),
            }}
          >
            {g.name}
          </button>
        ))}
      </div>

      {/* Product grid */}
      <div style={styles.grid}>
        {displayedProducts.map((product) => (
          <button
            key={product.id}
            onClick={() => onAddToCart(product)}
            style={styles.card}
          >
            <div style={styles.cardStyle}>{product.style_name || product.style_code}</div>
            <div style={styles.cardDetails}>
              <span>{product.colour_name || product.colour}</span>
              <span>{product.size_name || product.size}</span>
            </div>
            <div style={styles.cardPrice}>
              Rs {((product.mrp_paise || product.selling_price_paise) / 100).toFixed(0)}
            </div>
            <div style={styles.cardBarcode}>
              {product.barcode || product.sku}
            </div>
          </button>
        ))}
      </div>

      {displayedProducts.length === 0 && (
        <div style={styles.empty}>No products found. Import a catalogue to get started.</div>
      )}
    </div>
  );
}

const styles = {
  container: { display: "flex", flexDirection: "column", height: "100%", padding: 8 },
  searchBar: { display: "flex", alignItems: "center", gap: 8, marginBottom: 8 },
  searchInput: { flex: 1, padding: "8px 12px", borderRadius: 8, border: "1px solid #0f3460", background: "#16213e", color: "#e0e0e0", fontSize: 14 },
  clearBtn: { padding: "4px 10px", background: "transparent", border: "1px solid #555", color: "#aaa", borderRadius: 6, cursor: "pointer" },
  filterBar: { display: "flex", gap: 4, overflowX: "auto", padding: "4px 0 8px", marginBottom: 4 },
  filterBtn: { padding: "4px 10px", borderRadius: 12, border: "1px solid #0f3460", background: "transparent", color: "#888", fontSize: 11, cursor: "pointer", whiteSpace: "nowrap" },
  filterBtnActive: { background: "#e94560", color: "#fff", borderColor: "#e94560" },
  grid: { flex: 1, overflowY: "auto", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 6, padding: "0 2px" },
  card: { padding: 8, borderRadius: 8, border: "1px solid #0f3460", background: "#16213e", color: "#e0e0e0", cursor: "pointer", textAlign: "left", display: "flex", flexDirection: "column", gap: 2 },
  cardStyle: { fontWeight: 600, fontSize: 12, color: "#e94560" },
  cardDetails: { fontSize: 11, color: "#888" },
  cardPrice: { fontWeight: 700, fontSize: 14, marginTop: "auto" },
  cardBarcode: { fontSize: 9, color: "#666", fontFamily: "monospace" },
  empty: { flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#666" },
};
