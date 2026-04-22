"""
AYY-34 — Celery tasks for Tally XML export.

Scheduled daily at 23:59 IST (CELERY_BEAT_SCHEDULE in settings).
"""

from celery import shared_task
from datetime import date, timedelta

from .models import DailyVoucherLog
from .xml_generator import generate_daily_tally_xml
from ..billing.models import Bill


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def export_daily_tally_vouchers(self, store_id, export_date=None):
    """
    Celery task: Generate daily Tally XML vouchers.

    Run at 23:59 IST to export the previous day's bills.
    """
    if export_date is None:
        export_date = (date.today() - timedelta(days=1)).isoformat()

    try:
        bills = Bill.objects.filter(
            store_id=store_id,
            created_at__date=export_date,
            status=Bill.STATUS_COMPLETED,
        )

        if not bills.exists():
            return {"status": "no_bills", "store_id": store_id, "date": export_date}

        xml_content = generate_daily_tally_xml(store_id, bills, tally_version="erp_9")

        log, created = DailyVoucherLog.objects.get_or_create(
            store_id=store_id,
            date=export_date,
            defaults={
                "xml_content": xml_content,
                "total_bills": bills.count(),
                "total_sales_paise": bills.aggregate(s=models.Sum("total_paise"))["s"] or 0,
                "status": "generated",
            },
        )

        if not created:
            log.xml_content = xml_content
            log.total_bills = bills.count()
            log.status = "generated"
            log.save()

        return {
            "status": "generated",
            "store_id": store_id,
            "date": export_date,
            "total_bills": bills.count(),
            "total_sales_paise": log.total_sales_paise,
        }

    except Exception as exc:
        self.retry(exc=exc)
