import React, { useState, useMemo, useCallback } from 'react';
import { usePOS } from './POSContext';

const SIZE_LABELS = ['XS', 'S', 'M', 'L', 'XL', 'XXL'];
const COLORS = ['Red', 'Blue', 'Black', 'White', 'Navy', 'Green', 'Grey', 'Maroon'];

function ProductCard({ product, onAdd }) {
  const [selectedSize, setSelectedSize] = useState(SIZE_LABELS[0] || SIZE_LABELS[0]);
  const [selectedColor, setSelectedColor] = useState(COLORS[0]);
  const [qty, setQty] = useState(1);

  const key = `${product.style}-${selectedColor}-${selectedSize}`;

  return (
    <div style={styles.card} onClick={() => {
      onAdd({ ...product, variant_id: key, size: selectedSize, color: selectedColor, mrp_paise: product.mrp_paise });
    }}>
      <div style={styles.cardHeader}>
        <span style={styles.cardStyle}>{product.style}</span>
        <span style={styles.cardMRP}>&#8377;{(product.mrp_paise / 100).toFixed(2)}</span>
      </div>
      <div style={styles.colorRow}>
        <div style={{ ...styles.colorDot, backgroundColor: selectedColor.toLowerCase() }} />
        <span>{selectedColor}</span>
      </div>
      <div style={styles.sizeRow}>
        {SIZE_LABELS.slice(0, 4).map((s) => (
          <button
            key={s}
            onClick={(e) => { e.stopPropagation(); setSelectedSize(s); }}
            style={{ ...styles.sizeBtn, ...(selectedSize === s ? styles.sizeBtnActive : {}) }}
          >
            {s}
          </button>
        ))}
      </div>
      <input
        type="number"
        min="1"
        max="99"
        value={qty}
        onChange={(e) => setQty(Math.max(1, parseInt(e.target.value) || 1))}
        onClick={(e) => e.stopPropagation()}
        style={styles.qtyInput}
      />
    </div>
  );
}

export default function CatalogueView({ products, onAddToCart }) {
  const [search, setSearch] = useState('');
  const [filterCategory, setFilterCategory] = useState('');

  const filtered = useMemo(() => {
    return products.filter((p) => {
      const matchSearch = !search ||
        p.style.toLowerCase().includes(search.toLowerCase()) ||
        p.variant_id.toLowerCase().includes(search.toLowerCase());
      const matchCat = !filterCategory || p.style === filterCategory;
      return matchSearch && matchCat;
    });
  }, [products, search, filterCategory]);

  const categories = useMemo(() => [...new Set(products.map((p) => p.style))], [products]);

  return (
    <div style={styles.container}>
      <div style={styles.searchBar}>
        <input
          placeholder="Search by name or SKU..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={styles.searchInput}
          autoFocus
        />
      </div>
      {categories.length > 1 && (
        <div style={styles.filterRow}>
          <button
            onClick={() => setFilterCategory('')}
            style={{ ...styles.filterBtn, ...( !filterCategory ? styles.filterBtnActive : {}) }}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setFilterCategory(cat)}
              style={{ ...styles.filterBtn, ...(filterCategory === cat ? styles.filterBtnActive : {}) }}
            >
              {cat}
            </button>
          ))}
        </div>
      )}
      <div style={styles.grid}>
        {filtered.map((p) => (
          <ProductCard key={p.variant_id} product={p} onAdd={onAddToCart} />
        ))}
      </div>
    </div>
  );
}

const styles = {
  container: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  searchBar: { padding: '8px 12px', background: '#16213e' },
  searchInput: {
    width: '100%', padding: '10px 14px', borderRadius: 8, border: 'none',
    fontSize: 16, background: '#0f3460', color: '#e0e0e0', outline: 'none',
  },
  filterRow: { display: 'flex', gap: 6, padding: '6px 12px', overflowX: 'auto' },
  filterBtn: {
    padding: '4px 12px', borderRadius: 12, border: '1px solid #0f3460',
    background: '#16213e', color: '#aaa', fontSize: 12, cursor: 'pointer', whiteSpace: 'nowrap',
  },
  filterBtnActive: { background: '#0f3460', color: '#fff' },
  grid: {
    flex: 1, overflowY: 'auto', padding: 12,
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 10,
  },
  card: {
    background: '#16213e', borderRadius: 10, padding: 10, cursor: 'pointer',
    border: '1px solid #0f3460', transition: 'border-color 0.15s',
  },
  cardHeader: { display: 'flex', justifyContent: 'space-between', marginBottom: 4 },
  cardStyle: { fontSize: 13, fontWeight: 600, color: '#e0e0e0' },
  cardMRP: { fontSize: 14, fontWeight: 700, color: '#e94560' },
  colorRow: { display: 'flex', alignItems: 'center', gap: 6, margin: '4px 0', fontSize: 11, color: '#aaa' },
  colorDot: { width: 10, height: 10, borderRadius: '50%' },
  sizeRow: { display: 'flex', gap: 4 },
  sizeBtn: {
    flex: 1, padding: '3px 0', borderRadius: 4, border: '1px solid #0f3460',
    background: '#0f3460', color: '#aaa', fontSize: 10, cursor: 'pointer',
  },
  sizeBtnActive: { background: '#e94560', color: '#fff', borderColor: '#e94560' },
  qtyInput: {
    width: 40, padding: '2px 4px', borderRadius: 4, border: '1px solid #0f3460',
    background: '#0f3460', color: '#e0e0e0', fontSize: 12, textAlign: 'center', marginTop: 4,
  },
};
