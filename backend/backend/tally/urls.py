"""
AYY-34 — Tally URL routes.
"""

from django.urls import path
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import DailyVoucherLog
from .tasks import export_daily_tally_vouchers


class TallyExportView(APIView):
    """Manual trigger for daily Tally export."""

    def post(self, request):
        store_id = request.data.get("store_id", "")
        export_date = request.data.get("date")

        result = export_daily_tally_vouchers.delay(store_id, export_date)
        return Response({"task_id": result.id, "status": "queued"})


class TallyVoucherLogViewSet:
    """Read-only access to voucher logs."""

    @staticmethod
    def list(request):
        logs = DailyVoucherLog.objects.all().order_by("-date")[:30]
        return Response([{
            "id": str(l.id),
            "store_id": l.store_id,
            "date": l.date.isoformat(),
            "status": l.status,
            "total_bills": l.total_bills,
            "total_sales_paise": l.total_sales_paise,
            "created_at": l.created_at.isoformat(),
        } for l in logs])
