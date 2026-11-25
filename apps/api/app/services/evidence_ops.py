"""
Confirmation Evidence Verification Operations Service (Phase 3 Milestone 7.1).

Establishes strict reviewer RBAC enforcement, standardized rejection reason taxonomies,
Document Vault integrity checks, and immutable EvidenceReviewAudit logging.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth_provider import UserClaims
from app.models.application import Application
from app.models.routing import ApplicationSubmissionEvidence, EvidenceReviewAudit
from app.models.user import User
from app.schemas.routing import EvidenceReviewAuditSchema, SubmissionEvidenceSchema
from app.services.routing_engine import record_status_transition


EVIDENCE_REJECTION_REASONS: List[Dict[str, str]] = [
    {
        "code": "illegible_screenshot",
        "label": "Illegible Screenshot / Blurry Scan",
        "description": "Uploaded confirmation file is cropped, low resolution, or unreadable.",
    },
    {
        "code": "missing_confirmation_id",
        "label": "Missing Confirmation ID or Timestamp",
        "description": "Proof does not clearly display an official submission reference or date.",
    },
    {
        "code": "wrong_institution_or_pathway",
        "label": "Wrong Institution or Applicant Pathway",
        "description": "Confirmation artifact belongs to a different school or pathway.",
    },
    {
        "code": "wrong_term_or_expired",
        "label": "Wrong Academic Term or Expired Receipt",
        "description": "Submission receipt is from a prior or mismatched admissions cycle.",
    },
    {
        "code": "unverifiable_sender_or_url",
        "label": "Unverifiable Sender or Portal Header",
        "description": "Email header or portal screenshot lacks recognizable institutional domain.",
    },
    {
        "code": "incomplete_proof",
        "label": "Incomplete Submission Proof (Draft Screen)",
        "description": "Shows in-progress portal draft rather than final submitted confirmation.",
    },
    {
        "code": "other",
        "label": "Other Issue (See Reviewer Notes)",
        "description": "Detailed remediation instructions provided in reviewer notes.",
    },
]
EVIDENCE_REJECTION_CODES = {r["code"]: r for r in EVIDENCE_REJECTION_REASONS}


def rejection_label(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    entry = EVIDENCE_REJECTION_CODES.get(code)
    return entry["label"] if entry else code


def record_evidence_audit(
    db: Session,
    ev: ApplicationSubmissionEvidence,
    action: str,
    from_review_status: Optional[str],
    to_review_status: str,
    actor_user_id: Optional[UUID],
    actor_role: str,
    actor_email: Optional[str] = None,
    rejection_reason_code: Optional[str] = None,
    notes: Optional[str] = None,
) -> EvidenceReviewAudit:
    audit = EvidenceReviewAudit(
        evidence_id=ev.id,
        application_id=ev.application_id,
        from_review_status=from_review_status,
        to_review_status=to_review_status,
        action=action,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        actor_email=actor_email,
        rejection_reason_code=rejection_reason_code,
        notes=notes,
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    return audit


def serialize_evidence(
    ev: ApplicationSubmissionEvidence,
    include_actor_email: bool = False,
) -> SubmissionEvidenceSchema:
    out = SubmissionEvidenceSchema.model_validate(ev)
    if ev.document:
        out.original_filename = ev.document.original_filename
        out.document_sha256 = ev.document.file_sha256
    out.rejection_reason_label = rejection_label(ev.rejection_reason_code)

    audits_out: List[EvidenceReviewAuditSchema] = []
    for a in (ev.audits or []):
        item = EvidenceReviewAuditSchema.model_validate(a)
        item.rejection_reason_label = rejection_label(a.rejection_reason_code)
        if not include_actor_email:
            item.actor_email = None
        audits_out.append(item)
    out.audit_history = audits_out
    return out


def execute_evidence_review(
    db: Session,
    ev: ApplicationSubmissionEvidence,
    decision: str,
    claims: UserClaims,
    rejection_reason_code: Optional[str] = None,
    reviewer_notes: Optional[str] = None,
) -> ApplicationSubmissionEvidence:
    norm_decision = (decision or "").strip().lower()
    if norm_decision not in ("accepted", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be 'accepted' or 'rejected'.",
        )

    if norm_decision == "accepted":
        if not ev.document_id or not ev.document or not ev.document.file_sha256:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot confirm submission without an attached SHA-256 Document Vault confirmation artifact.",
            )
    else:
        code = (rejection_reason_code or "").strip()
        if code not in EVIDENCE_REJECTION_CODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rejecting evidence requires a valid rejection_reason_code: {sorted(EVIDENCE_REJECTION_CODES)}.",
            )
        if not (reviewer_notes or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejecting evidence requires actionable reviewer notes explaining what the student must re-upload.",
            )

    prev_review_status = ev.review_status
    now = datetime.now(timezone.utc)
    ev.review_status = norm_decision
    ev.rejection_reason_code = rejection_reason_code.strip() if norm_decision == "rejected" else None
    ev.reviewer_notes = (reviewer_notes or "").strip() or None
    ev.reviewed_at = now

    reviewer = db.query(User).filter(User.external_auth_id == claims.user_id).first()
    if reviewer:
        ev.reviewer_user_id = reviewer.id

    record_evidence_audit(
        db=db,
        ev=ev,
        action=norm_decision,
        from_review_status=prev_review_status,
        to_review_status=norm_decision,
        actor_user_id=reviewer.id if reviewer else None,
        actor_role=claims.role,
        actor_email=claims.email,
        rejection_reason_code=ev.rejection_reason_code,
        notes=ev.reviewer_notes,
    )

    app = db.query(Application).filter(Application.id == ev.application_id).first()
    if app:
        if norm_decision == "accepted":
            app.submission_confirmed_at = now
            app.submitted_at = app.student_reported_submitted_at or now
            record_status_transition(
                db=db,
                app=app,
                to_status="submission_confirmed",
                actor_user_id=reviewer.id if reviewer else None,
                actor_role=claims.role,
                reason=ev.reviewer_notes or "Confirmation evidence verified and accepted.",
                metadata={"evidence_id": str(ev.id), "document_id": str(ev.document_id)},
            )
        else:
            app.submission_confirmed_at = None
            reason_lbl = rejection_label(ev.rejection_reason_code) or "Rejected"
            record_status_transition(
                db=db,
                app=app,
                to_status="student_reported_submitted",
                actor_user_id=reviewer.id if reviewer else None,
                actor_role=claims.role,
                reason=f"[{reason_lbl}] {ev.reviewer_notes}",
                metadata={
                    "evidence_id": str(ev.id),
                    "review_decision": "rejected",
                    "rejection_reason_code": ev.rejection_reason_code,
                },
            )

    db.commit()
    db.refresh(ev)
    return ev
