"""Re-export sync_core for backwards compatibility.
The canonical code now lives in storebox.sync_core — this file provides
backwards-compatibility imports for any code that still references pos_spike.
"""
from sync_core.models import (
    Product,
    StockEvent,
    StockEventKind,
    SyncOutbox,
    SyncOutboxStatus,
    CloudEvent,
    CloudStockProjection,
    CatalogUpdate,
    ChangeFeedCursor,
    PendingReconciliation,
)
from sync_core.store import Till, StoreClock, local_on_hand
from sync_core.drainer import drain
from sync_core.cloud import DrainSink
from sync_core.replayer import pull_catalog_changes
