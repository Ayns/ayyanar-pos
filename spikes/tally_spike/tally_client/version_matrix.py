"""Tally version matrix for the XML voucher import surface.

This is the single place where we encode the version-specific differences we
have to handle when generating vouchers and parsing Tally's import response.
Everything downstream (XML generator, simulator, golden files, tests) is
keyed off a `TallyVersion` enum value.

The values come from the public Tally XML integration documentation. The
empirical confirmation / contradiction on real VMs is what Phase 1 must do
before we claim version parity in a release note; the `known_from` field on
each quirk flags whether our current understanding is docs-only or
empirical.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TallyVersion(str, Enum):
    ERP_9 = "tally_erp_9"           # Tally ERP 9 Release 6.x (last: 6.6.3)
    PRIME = "tally_prime"           # Tally Prime 2.x / 3.x single-user
    PRIME_SERVER = "tally_prime_server"  # Tally Prime Server 4.x multi-user host


@dataclass(frozen=True)
class VersionQuirk:
    """One known divergence between versions that affects our client."""
    key: str
    description: str
    versions: tuple[TallyVersion, ...]
    # "docs" = known only from published docs; "empirical" = confirmed on a VM
    known_from: str = "docs"


@dataclass(frozen=True)
class VersionCapabilities:
    version: TallyVersion
    # Voucher number handling: "auto" means Tally assigns; "manual" means we send
    voucher_numbering: str
    # Whether GST classification on ledger entries requires HSN explicitly
    gst_requires_hsn: bool
    # Whether the envelope must include <TARGETCOMPANY> to route the import
    requires_target_company: bool
    # Whether a <GSTREGISTRATIONTYPE> child is required on party ledgers
    requires_gst_reg_type: bool
    # Whether UDF tags use the legacy `<UDF:NAME.LIST TYPE="...">` form
    # (Prime tightened this; ERP 9 accepts the looser form)
    strict_udf_namespace: bool
    # Credit notes require ISINVOICE=Yes to get into GSTR-1 on Prime; ERP 9
    # accepts either but the GSTR report is only built from ISINVOICE=Yes.
    credit_note_requires_isinvoice: bool
    # Whether the server rejects mixed-tender sales that don't sum to the
    # invoice total by more than 1 paisa (real Tally rounds to the nearest
    # paisa, but Prime Server enforces it strictly).
    strict_tender_sum_check: bool
    # Date format the server prefers. All three accept YYYYMMDD; Prime Server
    # additionally accepts <DATE.LIST> but we don't use that form.
    date_format: str = "YYYYMMDD"
    # Extra quirks that don't fit a flag but the generator / simulator must
    # know about.
    extra: tuple[VersionQuirk, ...] = field(default_factory=tuple)


_ERP_9_QUIRKS: tuple[VersionQuirk, ...] = (
    VersionQuirk(
        key="party_name_legacy",
        description=(
            "ERP 9 accepts <PARTYNAME> as the party identifier; Prime deprecated "
            "this in favour of <PARTYLEDGERNAME> but still accepts the legacy tag."
        ),
        versions=(TallyVersion.ERP_9,),
    ),
    VersionQuirk(
        key="udf_loose_namespace",
        description=(
            "ERP 9 accepts <UDF:Apparel_Season> without an explicit TYPE; Prime "
            "requires the full `TYPE=\"String\"` attribute."
        ),
        versions=(TallyVersion.ERP_9,),
    ),
)

_PRIME_QUIRKS: tuple[VersionQuirk, ...] = (
    VersionQuirk(
        key="stricter_gstin_validation",
        description=(
            "Prime rejects malformed GSTINs with import error 6401 at parse "
            "time; ERP 9 warns but imports the voucher with a blank GSTIN."
        ),
        versions=(TallyVersion.PRIME, TallyVersion.PRIME_SERVER),
    ),
    VersionQuirk(
        key="isinvoice_required_for_gstr",
        description=(
            "Credit notes must have <ISINVOICE>Yes</ISINVOICE> to appear in "
            "GSTR-1. Prime enforces this at import; ERP 9 accepts the voucher "
            "but it silently drops from GSTR."
        ),
        versions=(TallyVersion.PRIME, TallyVersion.PRIME_SERVER),
    ),
)

_PRIME_SERVER_QUIRKS: tuple[VersionQuirk, ...] = (
    VersionQuirk(
        key="target_company_required",
        description=(
            "Prime Server hosts multiple companies; imports must declare "
            "<TARGETCOMPANY>Apparel HQ</TARGETCOMPANY> in the header or the "
            "server responds 7102 (Target company mismatch)."
        ),
        versions=(TallyVersion.PRIME_SERVER,),
    ),
    VersionQuirk(
        key="strict_tender_sum",
        description=(
            "Mixed-tender sales must balance to ±0.01 INR across all tender "
            "ledgers; Prime Server rejects with 6212 otherwise."
        ),
        versions=(TallyVersion.PRIME_SERVER,),
    ),
)


CAPABILITIES: dict[TallyVersion, VersionCapabilities] = {
    TallyVersion.ERP_9: VersionCapabilities(
        version=TallyVersion.ERP_9,
        voucher_numbering="manual",
        gst_requires_hsn=False,
        requires_target_company=False,
        requires_gst_reg_type=False,
        strict_udf_namespace=False,
        credit_note_requires_isinvoice=False,
        strict_tender_sum_check=False,
        extra=_ERP_9_QUIRKS,
    ),
    TallyVersion.PRIME: VersionCapabilities(
        version=TallyVersion.PRIME,
        voucher_numbering="manual",
        gst_requires_hsn=True,
        requires_target_company=False,
        requires_gst_reg_type=True,
        strict_udf_namespace=True,
        credit_note_requires_isinvoice=True,
        strict_tender_sum_check=False,
        extra=_PRIME_QUIRKS,
    ),
    TallyVersion.PRIME_SERVER: VersionCapabilities(
        version=TallyVersion.PRIME_SERVER,
        voucher_numbering="manual",
        gst_requires_hsn=True,
        requires_target_company=True,
        requires_gst_reg_type=True,
        strict_udf_namespace=True,
        credit_note_requires_isinvoice=True,
        strict_tender_sum_check=True,
        extra=_PRIME_SERVER_QUIRKS,
    ),
}


def capabilities(version: TallyVersion) -> VersionCapabilities:
    return CAPABILITIES[version]


def all_versions() -> tuple[TallyVersion, ...]:
    return tuple(CAPABILITIES.keys())


def all_quirks() -> tuple[VersionQuirk, ...]:
    seen: dict[str, VersionQuirk] = {}
    for cap in CAPABILITIES.values():
        for q in cap.extra:
            seen.setdefault(q.key, q)
    return tuple(seen.values())
