"""
AYY-34 — Reporting views.

End-of-day summary, daily sales, tender-wise register.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Count, Q
from datetime import date, datetime

from ..billing.models import Bill, BillPayment, BillLine


class DailySalesView(APIView):
    """FR: Daily sales summary report."""

    def get(self, request):
        report_date = request.query_params.get("date", date.today().isoformat())
        store_id = request.query_params.get("store_id", "")

        try:
            target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)

        bills = Bill.objects.filter(
            store_id=store_id if store_id else "",
            created_at__date=target_date,
            status=Bill.STATUS_COMPLETED,
        )

        total_bills = bills.count()
        total_sales_paise = bills.aggregate(s=Sum("total_paise"))["s"] or 0
        total_discount_paise = bills.aggregate(s=Sum("discount_paise"))["s"] or 0
        total_tax_paise = (
            (bills.aggregate(s=Sum("cgst_paise"))["s"] or 0)
            + (bills.aggregate(s=Sum("sgst_paise"))["s"] or 0)
            + (bills.aggregate(s=Sum("igst_paise"))["s"] or 0)
        )

        # Tender-wise breakdown
        tender_totals = {}
        payments = BillPayment.objects.filter(
            bill__in=bills
        ).values("tender_type").annotate(
            total_paise=Sum("amount_paise"),
            count=Count("id"),
        )
        for p in payments:
            tender_totals[p["tender_type"]] = {
                "total_paise": p["total_paise"] or 0,
                "count": p["count"],
            }

        # HSN-wise tax breakdown
        hsn_tax = BillLine.objects.filter(
            bill__in=bills
        ).values("hsn_code").annotate(
            taxable_paise=Sum("taxable_value_paise"),
            cgst_paise=Sum("cgst_paise"),
            sgst_paise=Sum("sgst_paise"),
            igst_paise=Sum("igst_paise"),
        )

        return Response({
            "date": report_date,
            "store_id": store_id,
            "total_bills": total_bills,
            "total_sales_paise": total_sales_paise,
            "total_discount_paise": total_discount_paise,
            "taxable_value_paise": total_sales_paise - total_discount_paise,
            "total_tax_paise": total_tax_paise,
            "tender_wise": tender_totals,
            "hsn_wise_tax": [{
                "hsn": h["hsn_code"],
                "taxable_paise": h["taxable_paise"] or 0,
                "cgst_paise": h["cgst_paise"] or 0,
                "sgst_paise": h["sgst_paise"] or 0,
                "igst_paise": h["igst_paise"] or 0,
            } for h in hsn_tax],
        })


class ZReportView(APIView):
    """End-of-day Z report — complete register for the day."""

    def get(self, request):
        report_date = request.query_params.get("date", date.today().isoformat())
        store_id = request.query_params.get("store_id", "")

        bills = Bill.objects.filter(
            store_id=store_id if store_id else "",
            created_at__date=report_date.split("-")[0]+"-"+report_date.split("-")[1]+"-"+report_date.split("-")[2],
        ).select_related()

        return Response({
            "report_type": "Z",
            "date": report_date,
            "store_id": store_id,
            "total_bills": bills.count(),
            "total_cancelled": bills.filter(status=Bill.STATUS_CANCELLED).count(),
            "total_returns": bills.filter(status=Bill.STATUS_RETURNED).count(),
            "bills": [{
                "bill_number": b.bill_number,
                "time": b.created_at.strftime("%H:%M"),
                "cashier": b.cashier_id,
                "total_paise": b.total_paise,
                "lines": b.lines.count(),
            } for b in bills[:100]],
        })
