"""
Audit execution, inspection, and export endpoints for AccessReaper v2.
Re-evaluates assignments, generates immutable audit reports, snapshots, and audit log events.
Serves server-side PDF and CSV reports generated from frozen audit run snapshots.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import UserClaims, require_role
from app.db.models import AIExplanation, AuditRun
from app.db.session import get_db
from app.engine.audit_service import execute_audit_run
from app.engine.csv_export import export_findings_csv
from app.engine.pdf_report import generate_audit_pdf
from app.schemas.iam import AuditRunSchema
from app.schemas.serializers import serialize_audit_run

logger = logging.getLogger("accessreaper.audits")

router = APIRouter()


@router.post("/audits/run", response_model=AuditRunSchema)
def run_access_audit(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Executes an IAM audit run. Allowed only when ENV=dev and ALLOW_MANUAL_AUDIT=true.
    Otherwise, AccessReaper runs automatic audits every 24 hours.
    """
    if not (settings.ENV == "dev" and settings.ALLOW_MANUAL_AUDIT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MANUAL_AUDIT_DISABLED",
                    "message": "Manual audit runs are disabled. AccessReaper runs automatic audits every 24 hours.",
                }
            },
        )
    audit_run = execute_audit_run(db=db, actor=user.name, trigger="manual")
    return serialize_audit_run(audit_run)


@router.get("/audits", response_model=list[AuditRunSchema])
def list_audits(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    runs = db.query(AuditRun).order_by(AuditRun.completed_at.desc()).all()
    summaries = {
        exp.run_id: exp
        for exp in db.query(AIExplanation).filter(AIExplanation.finding_id.is_(None)).all()
    }
    return [serialize_audit_run(r, summaries.get(r.id)) for r in runs]


@router.get("/audits/{id}", response_model=AuditRunSchema)
def get_audit_by_id(
    id: str,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    run = db.query(AuditRun).filter(AuditRun.id == id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Audit report not found."}},
        )
    ai_summary = (
        db.query(AIExplanation)
        .filter(AIExplanation.run_id == id, AIExplanation.finding_id.is_(None))
        .first()
    )
    return serialize_audit_run(run, ai_summary)


@router.get("/audits/{id}/report.pdf")
def download_audit_pdf_report(
    id: str,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Generates and downloads a clean, branded PDF report from the frozen audit run snapshot.
    Uses ReportLab with page numbering, Acme, Inc. metadata, risk totals, and finding list.
    """
    run = db.query(AuditRun).filter(AuditRun.id == id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Audit report not found."}},
        )

    run_dict = {
        "id": run.id,
        "completed_at": run.completed_at,
        "actor": run.actor,
        "mode": run.mode,
        "rule_version": getattr(run, "rule_version", 1),
        "trigger": getattr(run, "trigger", "manual"),
        "identities": run.identities,
        "assignments": run.assignments,
        "high": run.high,
        "medium": run.medium,
        "healthy": run.healthy,
        "resolved": run.resolved,
        "sources": run.sources,
    }

    findings_list = run.findings_snapshot or []
    pdf_bytes = generate_audit_pdf(run_dict, findings_list)

    logger.info("Audit PDF report generated: run_id=%s, actor=%s, size=%d bytes", id, user.name, len(pdf_bytes))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="audit-{id}-report.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


@router.get("/audits/{id}/findings.csv")
def download_audit_findings_csv(
    id: str,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """
    Exports the frozen findings snapshot of the specified audit run to CSV.
    Guaranteed UTF-8 BOM encoding and formula injection sanitization.
    """
    run = db.query(AuditRun).filter(AuditRun.id == id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Audit report not found."}},
        )

    findings_list = run.findings_snapshot or []
    csv_bytes = export_findings_csv(findings_list)

    logger.info("Audit findings CSV exported: run_id=%s, actor=%s, size=%d bytes", id, user.name, len(csv_bytes))
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="audit-{id}-findings.csv"',
            "Content-Length": str(len(csv_bytes)),
        },
    )
