"""Tally version matrix — production version of AYY-15 spike.

Single source of truth for version-specific differences. Everything downstream
(XML generator, simulator, golden files) is keyed off TallyVersion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TallyVersion(str, Enum):
    ERP_9 = "tally_erp_9"
    PRIME = "tally_prime"
    PRIME_SERVER = "tally_prime_server"


@dataclass(frozen=True)
class VersionQuirk:
    key: str
    description: str
    versions: tuple[TallyVersion, ...]
    known_from: str = "docs"


@dataclass(frozen=True)
class VersionCapabilities:
    version: TallyVersion
    voucher_numbering: str
    gst_requires_hsn: bool
    requires_target_company: bool
    requires_gst_reg_type: bool
    strict_udf_namespace: bool
    credit_note_requires_isinvoice: bool
    strict_tender_sum_check: bool
    date_format: str = "YYYYMMDD"
    extra: tuple[VersionQuirk, ...] = field(default_factory=tuple)


_CAPABILITIES: dict[TallyVersion, VersionCapabilities] = {
    TallyVersion.ERP_9: VersionCapabilities(
        version=TallyVersion.ERP_9, voucher_numbering="manual",
        gst_requires_hsn=False, requires_target_company=False,
        requires_gst_reg_type=False, strict_udf_namespace=False,
        credit_note_requires_isinvoice=False, strict_tender_sum_check=False,
    ),
    TallyVersion.PRIME: VersionCapabilities(
        version=TallyVersion.PRIME, voucher_numbering="manual",
        gst_requires_hsn=True, requires_target_company=False,
        requires_gst_reg_type=True, strict_udf_namespace=True,
        credit_note_requires_isinvoice=True, strict_tender_sum_check=False,
    ),
    TallyVersion.PRIME_SERVER: VersionCapabilities(
        version=TallyVersion.PRIME_SERVER, voucher_numbering="manual",
        gst_requires_hsn=True, requires_target_company=True,
        requires_gst_reg_type=True, strict_udf_namespace=True,
        credit_note_requires_isinvoice=True, strict_tender_sum_check=True,
    ),
}


def capabilities(version: TallyVersion) -> VersionCapabilities:
    return _CAPABILITIES[version]


def all_versions() -> tuple[TallyVersion, ...]:
    return tuple(_CAPABILITIES.keys())
