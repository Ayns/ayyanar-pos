"""
Daily Tally XML export — Celery task.

Runs via Celery beat at 23:59 IST each day. Generates one Tally XML voucher
per invoice submitted that day, bundles them into a daily export file,
and records the log.
"""
from __future__ import annotations

import hashlib
import os
from datetime import date
from decimal import Decimal

from celery import shared_task
from django.conf import settings

from .models import DailyVoucherLog
from .xml_generator import generate, to_xml_bytes
from .scenarios import (
    LineItem, Scenario, Tender, TenderKind, VoucherKind,
)
from sync_core.models import StockEvent, StockEventKind


@shared_task(bind=True, max_retries=3, acks_late=True)
def export_daily_tally_vouchers(self, store_id: str, export_date: str) -> dict:
    """
    Generate Tally XML for all sale events from export_date.
    Returns {"vouchers_exported": N, "date": "YYYYMMDD", "error": null}.
    """
    try:
        day = date.fromisoformat(export_date)
    except (ValueError, TypeError):
        return {"vouchers_exported": 0, "error": f"invalid date: {export_date}"}

    events = StockEvent.objects.filter(
        store_id=store_id,
        kind=StockEventKind.SALE,
        occurred_at_wall__date=day,
    ).order_by("outbox_id")

    if not events.exists():
        return {"vouchers_exported": 0, "date": export_date, "error": None}

    # Group events by invoice (consecutive SALE events share an invoice)
    vouchers = _group_events_into_vouchers(events)
    xml_bytes = _build_daily_envelope(vouchers, day, store_id)

    # Persist XML to store directory
    xml_dir = f"/tmp/tally_exports/{store_id}"
    os.makedirs(xml_dir, exist_ok=True)
    filename = f"vouchers_{day.isoformat()}.xml"
    xml_path = os.path.join(xml_dir, filename)
    with open(xml_path, "wb") as f:
        f.write(xml_bytes)

    # Record the export
    sha = hashlib.sha256(xml_bytes).hexdigest()
    DailyVoucherLog.objects.get_or_create(
        store_id=store_id, date=day,
        defaults={"xml_path": xml_path, "xml_sha256": sha},
    )

    return {"vouchers_exported": len(vouchers), "date": export_date, "xml_path": xml_path, "error": None}


def _group_events_into_vouchers(events) -> list[Scenario]:
    """
    Group consecutive SALE events into voucher scenarios.
    v0.1 heuristic: every 5-20 events is one invoice line.
    Production should use the invoice_no stored on events.
    """
    vouchers = []
    batch = []
    for event in events:
        batch.append(event)
        if len(batch) >= 5:  # TODO: use proper invoice grouping
            vouchers.append(_event_to_voucher(batch))
            batch = []
    if batch:
        vouchers.append(_event_to_voucher(batch))
    return vouchers


def _event_to_voucher(events) -> Scenario:
    """Convert a batch of StockEvents into a Tally Scenario."""
    lines = []
    for e in events:
        payload = e.payload or {}
        lines.append(LineItem(
            sku=e.variant_id,
            description=f"Item {e.variant_id}",
            hsn=payload.get("hsn_code", ""),
            quantity=abs(e.delta),
            mrp=Decimal(payload.get("mrp_paise", 0)) / 100,
            unit_price_incl_gst=Decimal(payload.get("mrp_paise", 0)) / 100,
            gst_rate_bps=int(payload.get("gst_rate_bps", 1200)),
        ))
    return Scenario(
        scenario_id=f"auto-{events[0].outbox_id}",
        voucher_kind=VoucherKind.SALE,
        voucher_number=str(events[0].outbox_id),
        voucher_date=events[0].occurred_at_wall.strftime("%Y%m%d"),
        party_name="Walk-in Customer",
        party_gstin="",
        state_of_supply="Karnataka",
        narration=f"Auto-export, {len(events)} line(s)",
        lines=tuple(lines),
        tenders=(Tender(kind=TenderKind.CASH, amount=Decimal("0")),),
    )


def _build_daily_envelope(vouchers: list[Scenario], day: date, store_id: str) -> bytes:
    """Build the Tally XML envelope for a daily batch. v0.1: one voucher per version."""
    from .version_matrix import TallyVersion
    envelopes = []
    for v in vouchers:
        xml = generate(v, TallyVersion.PRIME, target_company=store_id)
        envelopes.append(xml)
    return "\n".join(envelopes).encode("utf-8")
