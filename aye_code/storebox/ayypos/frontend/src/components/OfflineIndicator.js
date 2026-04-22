/**
 * AYY-34 — Offline indicator.
 * Shows connection status to the backend.
 */

import React from "react";
import { usePOS } from "../POSContext";

export default function OfflineIndicator() {
  const { state } = usePOS();

  if (state.online) return null;

  return (
    <div style={styles.banner}>
      <span style={styles.icon}>&#9888;</span>
      <span>Offline — connecting to {process.env.REACT_APP_API_URL || "localhost:8000"}</span>
    </div>
  );
}

const styles = {
  banner: {
    background: "#ff9800",
    color: "#000",
    padding: "6px 16px",
    fontSize: 12,
    fontWeight: 600,
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  icon: { fontSize: 14 },
};
