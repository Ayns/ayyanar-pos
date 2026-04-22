"""
Injectable IRP target for production use.

Behaviourally interchangeable with the real IRP sandbox. In production,
a real HTTP implementation would implement this same IrpTarget Protocol.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class IrpResponse:
    http_status: int
    error_code: str  # "" when success
    body: dict
    retry_after_s: float | None = None
    request_id: str = ""


class IrpTarget(Protocol):
    def submit(self, tenant_id: str, payload: dict) -> IrpResponse: ...


@dataclass
class SimulatorConfig:
    latency_mu_ms: float = 5.0
    latency_sigma: float = 0.45
    throttle_rate: float = 0.02
    transient_5xx_rate: float = 0.015
    outage_duration_s: float = 60.0
    outage_start_prob: float = 0.002
    seed: int = 1337
    now_fn: "callable[[], float]" = field(default=time.monotonic)


class IrpSimulator:
    """Simulator for local testing. Replace with real HTTP client in production."""

    def __init__(self, config: SimulatorConfig | None = None) -> None:
        self.config = config or SimulatorConfig()
        self._rng = random.Random(self.config.seed)
        self._registered: dict[str, dict] = {}
        self._outage_until: dict[str, float] = {}

    def force_outage(self, tenant_id: str, duration_s: float) -> None:
        self._outage_until[tenant_id] = self.config.now_fn() + duration_s

    def submit(self, tenant_id: str, payload: dict) -> IrpResponse:
        self._sleep_latency()

        if self._is_in_outage(tenant_id):
            return IrpResponse(
                http_status=503, error_code="HTTP_503",
                body={"error": "service unavailable"}, request_id=self._rid(),
            )

        if self._rng.random() < self.config.outage_start_prob:
            self.force_outage(tenant_id, self.config.outage_duration_s)
            return IrpResponse(
                http_status=503, error_code="HTTP_503",
                body={"error": "service unavailable"}, request_id=self._rid(),
            )

        code = self._classify_payload(payload)
        if code is not None:
            if code == "DUPLICATE":
                key = self._idempotency_key(tenant_id, payload)
                ack = self._registered.get(key) or self._fresh_ack(payload)
                return IrpResponse(
                    http_status=200, error_code="2150",
                    body={"ErrorDetails": [{"ErrorCode": "2150"}], **ack},
                    request_id=self._rid(),
                )
            return IrpResponse(
                http_status=400, error_code=code,
                body={"ErrorDetails": [{"ErrorCode": code}]},
                request_id=self._rid(),
            )

        if self._rng.random() < self.config.throttle_rate:
            return IrpResponse(
                http_status=429, error_code="2244",
                body={"error": "rate limit"},
                retry_after_s=self._rng.choice([5.0, 10.0, 30.0]),
                request_id=self._rid(),
            )
        if self._rng.random() < self.config.transient_5xx_rate:
            code = self._rng.choice(["HTTP_500", "HTTP_502", "HTTP_504"])
            return IrpResponse(
                http_status=int(code.split("_")[1]), error_code=code,
                body={"error": "transient"}, request_id=self._rid(),
            )

        key = self._idempotency_key(tenant_id, payload)
        if key in self._registered:
            ack = self._registered[key]
            return IrpResponse(
                http_status=200, error_code="2150",
                body={"ErrorDetails": [{"ErrorCode": "2150"}], **ack},
                request_id=self._rid(),
            )
        ack = self._fresh_ack(payload)
        self._registered[key] = ack
        return IrpResponse(http_status=200, error_code="", body=ack, request_id=self._rid())

    def _sleep_latency(self) -> None:
        self._rng.lognormvariate(self.config.latency_mu_ms, self.config.latency_sigma)

    def _is_in_outage(self, tenant_id: str) -> bool:
        until = self._outage_until.get(tenant_id)
        return until is not None and self.config.now_fn() < until

    def _classify_payload(self, payload: dict) -> str | None:
        if "DocDtls" not in payload:
            return "2100"
        val = payload.get("ValDtls")
        if isinstance(val, list):
            return "2119"
        if payload.get("SellerDtls", {}).get("Gstin", "") == "00CANCELLED0000":
            return "2211"
        if payload.get("BuyerDtls", {}).get("Gstin", "") == "00CANCELLED0000":
            return "2212"
        tot_inv = payload.get("ValDtls", {}).get("TotInvVal", None)
        ass = payload.get("ValDtls", {}).get("AssVal", 0)
        cgst = payload.get("ValDtls", {}).get("CgstVal", 0)
        sgst = payload.get("ValDtls", {}).get("SgstVal", 0)
        igst = payload.get("ValDtls", {}).get("IgstVal", 0)
        expected = ass + cgst + sgst + igst
        if tot_inv is not None and not math.isclose(tot_inv, expected, rel_tol=1e-3):
            return "2189"
        if payload.get("DocDtls", {}).get("Dt", "") == "01/01/2000":
            return "2194"
        if any(it.get("HsnCd") == "0000" for it in payload.get("ItemList", [])):
            return "2233"
        if payload.get("BuyerDtls", {}).get("Pos") == "ZZ":
            return "2265"
        return None

    @staticmethod
    def _idempotency_key(tenant_id: str, payload: dict) -> str:
        docno = payload.get("DocDtls", {}).get("No", "")
        return f"{tenant_id}|{docno}"

    def _fresh_ack(self, payload: dict) -> dict:
        docno = payload.get("DocDtls", {}).get("No", "unknown")
        irn = f"IRN{abs(hash(docno)) % 10**16:016d}"
        return {
            "Irn": irn,
            "AckNo": str(self._rng.randint(100000000000, 999999999999)),
            "AckDt": "2026-04-20 12:00:00",
            "SignedQRCode": "STUB_QR",
        }

    def _rid(self) -> str:
        return f"sim-{self._rng.randint(10**9, 10**10 - 1)}"
