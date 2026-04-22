"""
Cloud → store catalogue change-feed pull. Monotonic cursor per store.

Only applies to Product rows (catalogue). Stock is intentionally NOT
replayed back from cloud to store — each store's StockEvent log is
authoritative for its own stock. Cloud's projection is a read model for
HO reporting, not the source of truth.
"""
from __future__ import annotations

from django.db import transaction

from .models import CatalogUpdate, ChangeFeedCursor, Product


@transaction.atomic
def pull_catalog_changes(store_id: str, batch_size: int = 500) -> int:
    cursor_row, _ = ChangeFeedCursor.objects.get_or_create(store_id=store_id)
    updates = list(
        CatalogUpdate.objects.filter(feed_cursor__gt=cursor_row.cursor).order_by(
            "feed_cursor"
        )[:batch_size]
    )
    if not updates:
        return 0
    for upd in updates:
        _apply_update_locally(upd)
        if upd.feed_cursor > cursor_row.cursor:
            cursor_row.cursor = upd.feed_cursor
    cursor_row.save()
    return len(updates)


def _apply_update_locally(upd: CatalogUpdate) -> None:
    product, created = Product.objects.get_or_create(
        variant_id=upd.variant_id,
        defaults={
            "style": "",
            "size": "",
            "color": "",
            "mrp_paise": 0,
            "season_tag": "",
            "catalogue_version": 0,
        },
    )
    if upd.field in {"style", "size", "color", "season_tag"}:
        setattr(product, upd.field, str(upd.new_value))
    elif upd.field == "mrp_paise":
        product.mrp_paise = int(upd.new_value)
    elif upd.field == "catalogue_version":
        product.catalogue_version = int(upd.new_value)
    else:
        product.catalogue_version += 1
    if not created:
        product.catalogue_version += 1
    product.save()
