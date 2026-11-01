"""
CSV export engine for AccessReaper v2.
Generates RFC 4180 compliant CSVs with UTF-8 BOM encoding for Excel compatibility
and strict formula injection protection (sanitizing =, +, -, @, \t, \r).
"""

import csv
from io import StringIO
from typing import Any

from app.core.time import KARACHI_TZ
from app.db.models import AuditLog


def sanitize_csv_cell(val: Any) -> str:
    """
    Prevents CSV formula injection by prepending a single quote
    if the value starts with dangerous spreadsheet formula characters.
    """
    if val is None:
        return ""
    text = str(val)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{text}"
    return text


def export_findings_csv(findings: list[dict[str, Any]]) -> bytes:
    """
    Exports a frozen audit run's findings snapshot to CSV with UTF-8 BOM.
    """
    output = StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    headers = [
        "Finding ID",
        "Person",
        "Email",
        "Role",
        "Team",
        "Resource",
        "Source",
        "Access Level",
        "Risk Level",
        "Primary Reason",
        "Action Target",
        "Status",
        "Detected At",
    ]
    writer.writerow(headers)

    for f in findings:
        fid = sanitize_csv_cell(f.get("id"))
        person = sanitize_csv_cell(f.get("person") or f.get("name"))
        email = sanitize_csv_cell(f.get("email"))
        role = sanitize_csv_cell(f.get("role"))
        team = sanitize_csv_cell(f.get("team"))
        repo = sanitize_csv_cell(f.get("repo"))
        source = sanitize_csv_cell(f.get("source"))
        access = sanitize_csv_cell(f.get("access"))
        risk = sanitize_csv_cell(f.get("risk"))
        reason = sanitize_csv_cell(f.get("reason"))
        target = sanitize_csv_cell(f.get("target") or f.get("action"))
        status = sanitize_csv_cell(
            f.get("status") or (f.get("finding", {}).get("status") if isinstance(f.get("finding"), dict) else "Open")
        )
        detected = sanitize_csv_cell(f.get("detectedAt"))

        writer.writerow(
            [
                fid,
                person,
                email,
                role,
                team,
                repo,
                source,
                access,
                risk,
                reason,
                target,
                status,
                detected,
            ]
        )

    return output.getvalue().encode("utf-8-sig")


def export_history_csv(events: list[AuditLog]) -> bytes:
    """
    Exports audit ledger events to CSV with formula injection sanitization and UTF-8 BOM.
    """
    output = StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    headers = [
        "Event ID",
        "Date & Time (PKT)",
        "Tag",
        "Title",
        "Actor",
        "Before",
        "After",
        "Assignment ID",
        "Request ID",
        "Audit ID",
        "Note",
        "Mode",
    ]
    writer.writerow(headers)

    for e in events:
        local_dt = e.occurred_at.astimezone(KARACHI_TZ) if e.occurred_at else None
        dt_str = local_dt.strftime("%Y-%m-%d %H:%M:%S PKT") if local_dt else ""

        writer.writerow(
            [
                sanitize_csv_cell(e.id),
                sanitize_csv_cell(dt_str),
                sanitize_csv_cell(e.tag),
                sanitize_csv_cell(e.title),
                sanitize_csv_cell(e.actor),
                sanitize_csv_cell(e.before),
                sanitize_csv_cell(e.after),
                sanitize_csv_cell(e.assignment_id),
                sanitize_csv_cell(e.request_id),
                sanitize_csv_cell(e.audit_id),
                sanitize_csv_cell(e.note),
                sanitize_csv_cell(e.mode),
            ]
        )

    return output.getvalue().encode("utf-8-sig")
