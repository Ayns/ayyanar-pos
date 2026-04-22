/**
 * AYY-26 — Hardware Abstraction Layer (HAL) stubs.
 *
 * v0.1: Mock implementations for prototype.
 * Phase 1: Real drivers for Epson ESC/POS, Honeywell scanner, PSE terminals.
 */

// ── Printer Interface ──

class PrinterHAL {
  /**
   * Print a receipt.
   * @param {Object} receipt - { invoiceNo, lines[], payments[], total, discount, customerName }
   */
  async printReceipt(receipt) {
    console.log('[HAL:MockPrinter] Printing receipt:', receipt);
    // Mock: print to stdout (in prototype, no real printer connected)
    console.log(`--- ${receipt.invoiceNo} ---`);
    for (const line of receipt.lines) {
      console.log(`  ${line.variant_id} x${line.qty}  ₹${(line.mrp_paise * line.qty / 100).toFixed(2)}`);
    }
    console.log(`Total: ₹${(receipt.total_paise / 100).toFixed(2)}`);
    console.log(`Paid: ${receipt.payments.map(p => `${p.method} ₹${(p.amount_paise / 100).toFixed(2)}`).join(', ')}`);
    return { success: true, jobId: `receipt-${Date.now()}` };
  }

  async printZReport(report) {
    console.log('[HAL:MockPrinter] Z-Report:', report);
    console.log(`  Total sales: ${report.totalTransactions} transactions, ₹${(report.totalRevenue / 100).toFixed(2)}`);
    return { success: true };
  }
}

// ── Barcode Scanner Interface ──

class ScannerHAL {
  constructor(onScan) {
    this.onScan = onScan;
    this._listeners = [];
    // In prototype: listen for keyboard input (scanner acts as USB keyboard wedge)
    if (typeof window !== 'undefined') {
      window.addEventListener('keydown', this._handleKey.bind(this));
    }
  }

  _handleKey(event) {
    // Barcode scanners inject strings ending with Enter (key code 13)
    if (event.key === 'Enter') {
      const value = this._buffer?.trim();
      if (value && value.length > 3) {
        this.onScan?.(value);
      }
      this._buffer = '';
    } else {
      this._buffer = (this._buffer || '') + event.key;
      // Reset buffer after 2s of inactivity
      clearTimeout(this._bufferTimeout);
      this._bufferTimeout = setTimeout(() => { this._buffer = ''; }, 2000);
    }
  }

  /** Programmatically feed a scan (for testing) */
  feed(variantId) {
    this.onScan?.(variantId);
  }
}

// ── Payment Terminal Interface ──

class PaymentTerminalHAL {
  /**
   * Process a payment.
   * @param {string} method - CASH | UPI | CARD
   * @param {number} amountPaise
   * @returns {Promise<{success: boolean, txnRef: string}>}
   */
  async processPayment(method, amountPaise) {
    console.log(`[HAL:MockTerminal] Processing ${method} payment: ₹${(amountPaise / 100).toFixed(2)}`);

    // Mock: 95% success rate
    const success = Math.random() > 0.05;
    if (!success) {
      return { success: false, error: 'DECLINED', txnRef: null };
    }

    const txnRef = `TXN-${Date.now()}-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
    console.log(`[HAL:MockTerminal] Success: ${txnRef}`);
    return { success: true, txnRef };
  }
}

// ── Cash Drawer Interface ──

class CashDrawerHAL {
  async open() {
    console.log('[HAL:MockDrawer] Opened');
    return { success: true };
  }
}

// ── Customer Display Interface ──

class CustomerDisplayHAL {
  async show(line1, line2) {
    console.log(`[HAL:MockDisplay] "${line1}" | "${line2 || ''}"`);
    return { success: true };
  }
}

// ── Factory — creates all HALs ──

class HALFactory {
  static create() {
    return {
      printer: new PrinterHAL(),
      scanner: new ScannerHAL(),
      terminal: new PaymentTerminalHAL(),
      drawer: new CashDrawerHAL(),
      display: new CustomerDisplayHAL(),
    };
  }
}

export { PrinterHAL, ScannerHAL, PaymentTerminalHAL, CashDrawerHAL, CustomerDisplayHAL, HALFactory };
