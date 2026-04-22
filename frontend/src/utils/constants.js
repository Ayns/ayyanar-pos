/**
 * AYY-34 — Frontend constants.
 */

// GST rates (slab percentages)
export const GST_SLABS = [0, 5, 12, 18, 28];

// Default tender types for split payments
export const DEFAULT_TENDERS = ["cash", "upi", "card"];

// Return window in days
export const RETURN_WINDOW_DAYS = 15;

// Store credit validity in days
export const STORE_CREDIT_VALIDITY_DAYS = 90;

// Discount override requires manager PIN
export const MAX_DISCOUNT_PCT = 25;
export const DISCOUNT_OVERRIDE_PIN_LENGTH = 4;

// Barcode format
export const BARCODE_FORMAT = "ean13";

// Price in paise
export const PAISE_PER_RUPEE = 100;
