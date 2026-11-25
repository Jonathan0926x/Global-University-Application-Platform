from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin_claims
from app.core.auth_provider import UserClaims
from app.database import get_db
from app.ingestion.countries_seed import ensure_country_exists
from app.ingestion.routing_seed import validate_routing_url
from app.models.application import Application, ApplicationRequirementStatus
from app.models.document import Document, DocumentExtraction
from app.models.institution import Institution
from app.models.profile import StudentProfile
from app.models.routing import ApplicationRoute, ApplicationSubmissionEvidence
from app.models.user import User
from app.schemas.application import (
    ApplicationCreate,
    ApplicationResponse,
    InstitutionSummarySchema,
)
from app.schemas.routing import (
    ApplicationRedirectRequest,
    ApplicationReportSubmissionRequest,
    ApplicationRouteSchema,
    ApplicationStatusUpdateRequest,
    EvidenceReviewRequest,
    SubmissionEvidenceSchema,
)
from app.services.document_vault import DocumentVaultService
from app.services.requirements_engine import evaluate_dynamic_checklist
from app.services.routing_engine import (
    STUDENT_PREP_STATES,
    compute_deadline_countdowns,
    normalize_legacy_status,
    record_status_transition,
    resolve_institution_routing,
)

router = APIRouter()


def seed_sample_institutions_if_empty(db: Session):
    count = db.query(Institution).count()
    if count == 0:
        ensure_country_exists(db, "US", "United States")
        samples = [
            Institution(
                official_name="University of California, Berkeley",
                alternative_names=["UC Berkeley", "Cal"],
                abbreviation="UCB",
                country_code="US",
                state_province="CA",
                city="Berkeley",
                institution_type="university",
                control_type="public",
                official_website="https://www.berkeley.edu",
                admissions_website="https://admissions.berkeley.edu",
                tuition_in_state=14226.0,
                tuition_out_of_state=44008.0,
                accepts_transfer=True,
                accepts_first_year=True,
            ),
            Institution(
                official_name="University of California, Los Angeles",
                alternative_names=["UCLA"],
                abbreviation="UCLA",
                country_code="US",
                state_province="CA",
                city="Los Angeles",
                institution_type="university",
                control_type="public",
                official_website="https://www.ucla.edu",
                admissions_website="https://admission.ucla.edu",
                tuition_in_state=13746.0,
                tuition_out_of_state=43528.0,
                accepts_transfer=True,
                accepts_first_year=True,
            ),
            Institution(
                official_name="San Francisco State University",
                alternative_names=["SFSU", "San Francisco State"],
                abbreviation="SFSU",
                country_code="US",
                state_province="CA",
                city="San Francisco",
                institution_type="university",
                control_type="public",
                official_website="https://www.sfsu.edu",
                admissions_website="https://future.sfsu.edu",
                tuition_in_state=7484.0,
                tuition_out_of_state=19364.0,
                accepts_transfer=True,
                accepts_first_year=True,
            ),
            Institution(
                official_name="De Anza College",
                alternative_names=["De Anza"],
                abbreviation="DAC",
                country_code="US",
                state_province="CA",
                city="Cupertino",
                institution_type="community_college",
                control_type="public",
                official_website="https://www.deanza.edu",
                tuition_in_state=1560.0,
                tuition_out_of_state=9120.0,
                accepts_transfer=False,
                accepts_first_year=True,
            ),
        ]
        db.add_all(samples)
        db.commit()


def _serialize_application(db: Session, app: Application) -> ApplicationResponse:
    inst = app.institution
    resolved = resolve_institution_routing(db, inst, applicant_type=app.applicant_type) if inst else None

    def _to_route_schema(items: List[ApplicationRoute]) -> List[ApplicationRouteSchema]:
        res = []
        for r in items:
            s = ApplicationRouteSchema.model_validate(r)
            s.institution_name = inst.official_name if inst else None
            res.append(s)
        return res

    ev_items: List[SubmissionEvidenceSchema] = []
    for ev in (app.submission_evidence or []):
        item = SubmissionEvidenceSchema.model_validate(ev)
        if ev.document:
            item.original_filename = ev.document.original_filename
        ev_items.append(item)

    deadlines = compute_deadline_countdowns(db, app.institution_id, app.applicant_type) if app.institution_id else []

    return ApplicationResponse(
        id=app.id,
        profile_id=app.profile_id,
        institution_id=app.institution_id,
        applicant_type=app.applicant_type,
        status=normalize_legacy_status(app.status),
        intended_major=app.intended_major,
        intended_term=app.intended_term,
        academic_year=app.academic_year,
        readiness_pct=app.readiness_pct,
        notes=app.notes,
        selected_route_id=app.selected_route_id,
        external_portal_url=app.external_portal_url,
        external_platform_name=app.external_platform_name,
        redirected_at=app.redirected_at,
        student_reported_submitted_at=app.student_reported_submitted_at,
        submission_confirmed_at=app.submission_confirmed_at,
        external_confirmation_number=app.external_confirmation_number,
        submitted_via=app.submitted_via,
        created_at=app.created_at,
        updated_at=app.updated_at,
        institution=app.institution,
        requirements_status=app.requirements_status or [],
        status_history=app.status_history or [],
        submission_evidence=ev_items,
        verified_routes=_to_route_schema(resolved["verified_routes"]) if resolved else [],
        needs_verification_routes=_to_route_schema(resolved["needs_verification_routes"]) if resolved else [],
        routing_notice=resolved["notice"] if resolved else None,
        deadlines=deadlines,
    )


def _get_owned_application(db: Session, current_user: User, application_id: UUID) -> tuple[StudentProfile, Application]:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")
    app = (
        db.query(Application)
        .filter(Application.id == application_id, Application.profile_id == profile.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application workspace not found.")
    return profile, app


@router.get("/institutions", response_model=List[InstitutionSummarySchema], tags=["Institutions"])
def list_institutions(
    type: Optional[str] = None,
    accepts_transfer: Optional[bool] = None,
    accepts_first_year: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    seed_sample_institutions_if_empty(db)
    query = db.query(Institution).filter(Institution.is_published == True)
    if type:
        query = query.filter(Institution.institution_type == type)
    if accepts_transfer is not None:
        query = query.filter(Institution.accepts_transfer == accepts_transfer)
    if accepts_first_year is not None:
        query = query.filter(Institution.accepts_first_year == accepts_first_year)
    priority_order = case(
        (Institution.ipeds_unit_id.in_(["110635", "110662", "122597", "170976", "166683", "113333"]), 0),
        else_=1,
    )
    return (
        query.order_by(priority_order.asc(), Institution.total_enrollment.desc().nullslast(), Institution.official_name.asc())
        .limit(limit)
        .all()
    )


@router.get("/applications", response_model=List[ApplicationResponse], tags=["Applications"])
def list_applications(
    applicant_type: Optional[str] = Query(None, description="Filter by 'first_year' or 'transfer'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        return []

    query = db.query(Application).filter(Application.profile_id == profile.id)
    if applicant_type:
        query = query.filter(Application.applicant_type == applicant_type)
    apps = query.order_by(Application.updated_at.desc(), Application.created_at.desc()).all()
    return [_serialize_application(db, a) for a in apps]


@router.post("/applications", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED, tags=["Applications"])
def create_application_workspace(
    app_in: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile required to create an application workspace.",
        )

    institution = db.query(Institution).filter(Institution.id == app_in.institution_id).first()
    if not institution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target institution not found.",
        )

    if app_in.applicant_type == "transfer" and not institution.accepts_transfer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{institution.official_name} does not currently accept transfer applications.",
        )
    if app_in.applicant_type == "first_year" and not institution.accepts_first_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{institution.official_name} does not accept first-year applications.",
        )

    resolved = resolve_institution_routing(db, institution, applicant_type=app_in.applicant_type)
    chosen_route: Optional[ApplicationRoute] = None
    if app_in.route_id:
        chosen_route = (
            db.query(ApplicationRoute)
            .filter(ApplicationRoute.id == app_in.route_id, ApplicationRoute.is_active == True)
            .first()
        )
    if not chosen_route and resolved["verified_routes"]:
        chosen_route = resolved["verified_routes"][0]

    application = Application(
        profile_id=profile.id,
        institution_id=institution.id,
        applicant_type=app_in.applicant_type,
        status="not_started",
        intended_major=app_in.intended_major or profile.intended_major,
        intended_term=app_in.intended_term or profile.intended_enrollment_term or "Fall 2027",
        academic_year=app_in.academic_year or "2026-2027",
        readiness_pct=0,
        selected_route_id=chosen_route.id if chosen_route else None,
        external_portal_url=chosen_route.official_url if chosen_route else None,
        external_platform_name=chosen_route.platform_name if chosen_route else None,
    )
    db.add(application)
    db.flush()

    checklist = evaluate_dynamic_checklist(
        db=db,
        institution=institution,
        profile=profile,
        applicant_type=app_in.applicant_type,
        intended_major=application.intended_major,
    )

    checklist_items = []
    if checklist.has_verified_requirements:
        all_evals = (
            checklist.completed_requirements
            + checklist.missing_documents
            + checklist.outstanding_prerequisites
            + checklist.other_requirements
            + checklist.not_applicable_requirements
        )
        for ev in all_evals:
            checklist_items.append(
                ApplicationRequirementStatus(
                    application_id=application.id,
                    institution_requirement_id=ev.requirement_id,
                    title=ev.title,
                    category=ev.category,
                    importance=ev.effective_importance,
                    status=ev.status,
                    notes=ev.explanation,
                    satisfied_by_document_id=ev.satisfied_by_document_id,
                    satisfied_by_profile_field=ev.satisfied_by_profile_field,
                    auto_matched=ev.auto_matched,
                    verification_status=ev.verification_status,
                    source_url=ev.source_url,
                )
            )
        application.readiness_pct = checklist.readiness_pct
        if checklist.readiness_pct > 0:
            application.status = "preparing"
    elif app_in.applicant_type == "transfer":
        checklist_items = [
            ApplicationRequirementStatus(application_id=application.id, title="Official College Transcript(s)", category="document", importance="required", status="pending", verification_status="general_guideline"),
            ApplicationRequirementStatus(application_id=application.id, title="Transfer Personal Statement / Statement of Purpose", category="document", importance="required", status="pending", verification_status="general_guideline"),
            ApplicationRequirementStatus(application_id=application.id, title="Major Prerequisites Audit (60 transferable units minimum)", category="academic", importance="required", status="pending", verification_status="general_guideline"),
            ApplicationRequirementStatus(application_id=application.id, title="Professor Recommendation Letter", category="document", importance="optional", status="pending", verification_status="general_guideline"),
            ApplicationRequirementStatus(application_id=application.id, title="Application Fee or Approved Fee Waiver", category="administrative", importance="required", status="pending", verification_status="general_guideline"),
        ]
    else:
        checklist_items = [
            ApplicationRequirementStatus(application_id=application.id, title="Official High School Secondary Transcript", category="document", importance="required", status="pending", verification_status="general_guideline"),
            ApplicationRequirementStatus(application_id=application.id, title="Personal Essay / Statement", category="document", importance="required", status="pending", verification_status="general_guideline"),
            ApplicationRequirementStatus(application_id=application.id, title="Standardized Exam Scores (SAT/ACT or International Bac)", category="academic", importance="recommended", status="pending", verification_status="general_guideline"),
            ApplicationRequirementStatus(application_id=application.id, title="High School Counselor Recommendation", category="document", importance="required", status="pending", verification_status="general_guideline"),
            ApplicationRequirementStatus(application_id=application.id, title="Application Fee or Fee Waiver Code", category="administrative", importance="required", status="pending", verification_status="general_guideline"),
        ]

    db.add_all(checklist_items)
    record_status_transition(
        db=db,
        app=application,
        to_status=application.status,
        actor_user_id=current_user.id,
        actor_role="student",
        reason="Application workspace initialized.",
    )
    db.commit()
    db.refresh(application)
    return _serialize_application(db, application)


@router.post("/applications/{application_id}/refresh-checklist", response_model=ApplicationResponse, tags=["Applications"])
def refresh_application_checklist(
    application_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile, app = _get_owned_application(db, current_user, application_id)
    institution = db.query(Institution).filter(Institution.id == app.institution_id).first()
    checklist = evaluate_dynamic_checklist(
        db=db,
        institution=institution,
        profile=profile,
        applicant_type=app.applicant_type,
        intended_major=app.intended_major,
    )
    if checklist.has_verified_requirements:
        db.query(ApplicationRequirementStatus).filter(
            ApplicationRequirementStatus.application_id == app.id
        ).delete()
        all_evals = (
            checklist.completed_requirements
            + checklist.missing_documents
            + checklist.outstanding_prerequisites
            + checklist.other_requirements
            + checklist.not_applicable_requirements
        )
        for ev in all_evals:
            db.add(
                ApplicationRequirementStatus(
                    application_id=app.id,
                    institution_requirement_id=ev.requirement_id,
                    title=ev.title,
                    category=ev.category,
                    importance=ev.effective_importance,
                    status=ev.status,
                    notes=ev.explanation,
                    satisfied_by_document_id=ev.satisfied_by_document_id,
                    satisfied_by_profile_field=ev.satisfied_by_profile_field,
                    auto_matched=ev.auto_matched,
                    verification_status=ev.verification_status,
                    source_url=ev.source_url,
                )
            )
        app.readiness_pct = checklist.readiness_pct
        if normalize_legacy_status(app.status) == "not_started" and checklist.readiness_pct > 0:
            record_status_transition(db, app, "preparing", current_user.id, "student", "Checklist refreshed with completed items.")
        db.commit()
        db.refresh(app)
    return _serialize_application(db, app)


@router.post("/applications/{application_id}/requirements/{requirement_status_id}", response_model=ApplicationResponse, tags=["Applications"])
def update_requirement_item_status(
    application_id: UUID,
    requirement_status_id: UUID,
    item_status: str = Query(..., description="pending | in_progress | completed"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if item_status not in ("pending", "in_progress", "completed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid requirement status.")
    _, app = _get_owned_application(db, current_user, application_id)
    req_row = (
        db.query(ApplicationRequirementStatus)
        .filter(
            ApplicationRequirementStatus.id == requirement_status_id,
            ApplicationRequirementStatus.application_id == app.id,
        )
        .first()
    )
    if not req_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist item not found.")

    req_row.status = item_status
    req_row.updated_at = datetime.now(timezone.utc)
    db.flush()

    all_items = db.query(ApplicationRequirementStatus).filter(ApplicationRequirementStatus.application_id == app.id).all()
    if all_items:
        done = sum(1 for r in all_items if r.status == "completed")
        app.readiness_pct = round((done / len(all_items)) * 100)
    if normalize_legacy_status(app.status) == "not_started" and item_status in ("in_progress", "completed"):
        record_status_transition(db, app, "preparing", current_user.id, "student", f"Updated checklist item '{req_row.title}' to {item_status}.")
    db.commit()
    db.refresh(app)
    return _serialize_application(db, app)


@router.post("/applications/{application_id}/status", response_model=ApplicationResponse, tags=["Applications"])
def update_application_preparation_status(
    application_id: UUID,
    payload: ApplicationStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _, app = _get_owned_application(db, current_user, application_id)
    target = (payload.status or "").strip().lower()

    if target == "submission_confirmed":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Submission confirmation cannot be self-certified; upload evidence for verifier approval.",
        )
    if target not in STUDENT_PREP_STATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Direct status endpoint supports preparation states {STUDENT_PREP_STATES}. Use /redirect or /report-submission for external steps.",
        )
    record_status_transition(
        db=db,
        app=app,
        to_status=target,
        actor_user_id=current_user.id,
        actor_role="student",
        reason=payload.reason or f"Student moved workspace status to {target}.",
    )
    db.commit()
    db.refresh(app)
    return _serialize_application(db, app)


@router.post("/applications/{application_id}/redirect", tags=["Applications"])
def record_external_portal_redirect(
    application_id: UUID,
    payload: ApplicationRedirectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Records an external portal redirect honestly.
    IMPORTANT: Clicking an external link ONLY transitions to `redirected_to_external_portal`
    and NEVER marks an application as submitted.
    """
    _, app = _get_owned_application(db, current_user, application_id)
    inst = app.institution
    resolved = resolve_institution_routing(db, inst, applicant_type=app.applicant_type)

    chosen_url: Optional[str] = None
    chosen_platform: Optional[str] = None
    chosen_route_id: Optional[UUID] = None
    is_verified = False

    if payload.route_id:
        r = db.query(ApplicationRoute).filter(ApplicationRoute.id == payload.route_id, ApplicationRoute.is_active == True).first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Selected application route not found.")
        chosen_url = r.official_url
        chosen_platform = r.platform_name
        chosen_route_id = r.id
        is_verified = r.verification_status == "verified"
    elif payload.target_url:
        chk = validate_routing_url(payload.target_url)
        if not chk["valid"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid destination URL: {chk['reason']}")
        # Verify whether this URL belongs to verified routes for this school
        match_v = next((r for r in resolved["verified_routes"] if r.official_url == chk["normalized_url"]), None)
        if match_v:
            chosen_url, chosen_platform, chosen_route_id, is_verified = match_v.official_url, match_v.platform_name, match_v.id, True
        else:
            if not payload.acknowledge_unverified:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Target URL is not a verified destination route; pass acknowledge_unverified=true only after manual verification.",
                )
            chosen_url, chosen_platform = chk["normalized_url"], "External Unverified Link"
    elif resolved["verified_routes"]:
        r0 = resolved["verified_routes"][0]
        chosen_url, chosen_platform, chosen_route_id, is_verified = r0.official_url, r0.platform_name, r0.id, True
    elif resolved["needs_verification_routes"] and payload.acknowledge_unverified:
        r0 = resolved["needs_verification_routes"][0]
        chosen_url, chosen_platform = r0.official_url, r0.platform_name
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No verified application portal URL exists for this institution; acknowledge unverified registry link or check university admissions.",
        )

    url_chk = validate_routing_url(chosen_url)
    if not url_chk["valid"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=url_chk["reason"])

    app.selected_route_id = chosen_route_id
    app.external_portal_url = url_chk["normalized_url"]
    app.external_platform_name = chosen_platform
    app.redirected_at = datetime.now(timezone.utc)

    record_status_transition(
        db=db,
        app=app,
        to_status="redirected_to_external_portal",
        actor_user_id=current_user.id,
        actor_role="student",
        reason=f"Redirected to external portal ({chosen_platform}); submission not confirmed.",
        metadata={"redirect_url": app.external_portal_url, "verified_route": is_verified},
    )
    db.commit()
    db.refresh(app)
    return {
        "application": _serialize_application(db, app),
        "redirect_url": app.external_portal_url,
        "verified_route": is_verified,
        "notice": "External redirect recorded. UniGlobe never submits on external portals and has NOT marked your application submitted.",
    }


@router.post("/applications/{application_id}/report-submission", response_model=ApplicationResponse, tags=["Applications"])
def student_report_external_submission(
    application_id: UUID,
    payload: ApplicationReportSubmissionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Allows the student to record self-reported external submission + optional confirmation reference.
    Moves strictly to `student_reported_submitted` (unverified) — NOT `submission_confirmed`.
    """
    _, app = _get_owned_application(db, current_user, application_id)
    now = datetime.now(timezone.utc)
    app.student_reported_submitted_at = now
    if payload.external_confirmation_number:
        app.external_confirmation_number = payload.external_confirmation_number.strip()[:120]
    if payload.submitted_via:
        app.submitted_via = payload.submitted_via.strip()[:100]

    record_status_transition(
        db=db,
        app=app,
        to_status="student_reported_submitted",
        actor_user_id=current_user.id,
        actor_role="student",
        reason=payload.note or "Student reported external submission (awaiting confirmation evidence review).",
        metadata={"external_confirmation_number": app.external_confirmation_number},
    )
    db.commit()
    db.refresh(app)
    return _serialize_application(db, app)


@router.post("/applications/{application_id}/evidence", response_model=SubmissionEvidenceSchema, status_code=status.HTTP_201_CREATED, tags=["Applications"])
async def upload_or_attach_submission_evidence(
    application_id: UUID,
    evidence_type: str = Form("portal_screenshot"),
    external_confirmation_number: Optional[str] = Form(None),
    submitted_note: Optional[str] = Form(None),
    document_id: Optional[UUID] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Uploads confirmation screenshots/emails to the private Document Vault (or attaches an existing
    owned document) and creates a `pending` `ApplicationSubmissionEvidence` record for verification.
    """
    profile, app = _get_owned_application(db, current_user, application_id)
    attached_doc: Optional[Document] = None

    if file is not None:
        storage_path, sha256_hash, file_size, file_ext = await DocumentVaultService.store_original_file(
            str(profile.id), file
        )
        content_bytes = await file.read()
        extraction_data = DocumentVaultService.extract_document_intelligence(
            file.filename or "submission_confirmation",
            content_bytes,
            file_ext,
        )
        attached_doc = Document(
            profile_id=profile.id,
            original_filename=file.filename or "submission_confirmation",
            file_type=file_ext,
            file_size_bytes=file_size,
            file_sha256=sha256_hash,
            storage_path=storage_path,
            detected_language=extraction_data["detected_language"],
            document_category="submission_confirmation",
        )
        db.add(attached_doc)
        db.flush()
        db.add(
            DocumentExtraction(
                document_id=attached_doc.id,
                extracted_text=extraction_data["extracted_text"],
                detected_institution=extraction_data.get("detected_institution") or (app.institution.official_name if app.institution else None),
                detected_qualification="Submission Confirmation Evidence",
                detected_grading_scale=None,
                extracted_data_json=extraction_data.get("extracted_data") or {},
                extraction_confidence=extraction_data["extraction_confidence"],
                extraction_warnings=extraction_data["extraction_warnings"],
            )
        )
    elif document_id is not None:
        attached_doc = (
            db.query(Document)
            .filter(Document.id == document_id, Document.profile_id == profile.id)
            .first()
        )
        if not attached_doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced Document Vault file not found.")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either an uploaded confirmation file or an owned document_id.",
        )

    ev = ApplicationSubmissionEvidence(
        application_id=app.id,
        profile_id=profile.id,
        document_id=attached_doc.id,
        evidence_type=evidence_type,
        external_confirmation_number=external_confirmation_number.strip()[:120] if external_confirmation_number else app.external_confirmation_number,
        submitted_note=submitted_note,
        review_status="pending",
    )
    db.add(ev)

    if external_confirmation_number:
        app.external_confirmation_number = external_confirmation_number.strip()[:120]
    if normalize_legacy_status(app.status) in ("not_started", "preparing", "ready_to_apply", "redirected_to_external_portal"):
        app.student_reported_submitted_at = datetime.now(timezone.utc)
        record_status_transition(
            db=db,
            app=app,
            to_status="student_reported_submitted",
            actor_user_id=current_user.id,
            actor_role="student",
            reason="Uploaded submission confirmation evidence for verification review.",
            metadata={"evidence_type": evidence_type, "document_id": str(attached_doc.id)},
        )

    db.commit()
    db.refresh(ev)
    out = SubmissionEvidenceSchema.model_validate(ev)
    out.original_filename = attached_doc.original_filename
    return out


@router.get("/applications/{application_id}/evidence", response_model=List[SubmissionEvidenceSchema], tags=["Applications"])
def list_application_evidence(
    application_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _, app = _get_owned_application(db, current_user, application_id)
    out = []
    for ev in (app.submission_evidence or []):
        item = SubmissionEvidenceSchema.model_validate(ev)
        if ev.document:
            item.original_filename = ev.document.original_filename
        out.append(item)
    return out


@router.post("/applications/evidence/{evidence_id}/review", response_model=SubmissionEvidenceSchema, tags=["Applications"])
def review_submission_evidence(
    evidence_id: UUID,
    payload: EvidenceReviewRequest,
    claims: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    """
    RBAC-restricted verifier/admin decision on student confirmation evidence.
    Only `accepted` review with linked supporting evidence promotes the application
    to `submission_confirmed`.
    """
    decision = (payload.decision or "").strip().lower()
    if decision not in ("accepted", "rejected"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Decision must be 'accepted' or 'rejected'.")

    ev = db.query(ApplicationSubmissionEvidence).filter(ApplicationSubmissionEvidence.id == evidence_id).first()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission evidence not found.")

    if decision == "accepted" and not ev.document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot confirm submission without an attached Document Vault confirmation artifact.",
        )

    now = datetime.now(timezone.utc)
    ev.review_status = decision
    ev.reviewer_notes = payload.reviewer_notes
    ev.reviewed_at = now

    reviewer = db.query(User).filter(User.external_auth_id == claims.user_id).first()
    if reviewer:
        ev.reviewer_user_id = reviewer.id

    app = db.query(Application).filter(Application.id == ev.application_id).first()
    if app:
        if decision == "accepted":
            app.submission_confirmed_at = now
            app.submitted_at = app.student_reported_submitted_at or now
            record_status_transition(
                db=db,
                app=app,
                to_status="submission_confirmed",
                actor_user_id=reviewer.id if reviewer else None,
                actor_role=claims.role,
                reason=payload.reviewer_notes or "Confirmation evidence verified and accepted.",
                metadata={"evidence_id": str(ev.id), "document_id": str(ev.document_id)},
            )
        else:
            record_status_transition(
                db=db,
                app=app,
                to_status="student_reported_submitted",
                actor_user_id=reviewer.id if reviewer else None,
                actor_role=claims.role,
                reason=payload.reviewer_notes or "Confirmation evidence rejected; please re-upload valid confirmation proof.",
                metadata={"evidence_id": str(ev.id), "review_decision": "rejected"},
            )

    db.commit()
    db.refresh(ev)
    out = SubmissionEvidenceSchema.model_validate(ev)
    if ev.document:
        out.original_filename = ev.document.original_filename
    return out


@router.get("/applications/{application_id}", response_model=ApplicationResponse, tags=["Applications"])
def get_application(
    application_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _, app = _get_owned_application(db, current_user, application_id)
    return _serialize_application(db, app)


@router.delete("/applications/{application_id}", tags=["Applications"])
def delete_application(
    application_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _, app = _get_owned_application(db, current_user, application_id)
    db.delete(app)
    db.commit()
    return {"deleted": True, "application_id": str(application_id)}
