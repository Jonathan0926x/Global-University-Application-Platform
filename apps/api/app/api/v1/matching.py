from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.institution import Institution
from app.models.matching import MatchingPreference, UniversityRecommendation
from app.models.profile import StudentProfile
from app.models.user import User
from app.schemas.matching import (
    CompareInstitutionsRequest,
    MatchingPreferenceResponse,
    MatchingPreferenceUpdate,
    MatchingRunRequest,
    MatchingRunResponse,
    UniversityMatchRecommendationSchema,
)
from app.services.matching_engine import (
    evaluate_single_institution_match,
    run_matching_discovery,
)

router = APIRouter()


def _get_or_init_profile(db: Session, user: User) -> StudentProfile:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if not profile:
        profile = StudentProfile(
            user_id=user.id,
            first_name=user.email.split("@")[0].capitalize() if user.email else "Student",
            last_name="",
            applicant_type="undecided",
        )
        db.add(profile)
        db.flush()
    return profile


def _get_or_init_pref(db: Session, profile: StudentProfile) -> MatchingPreference:
    pref = db.query(MatchingPreference).filter(MatchingPreference.profile_id == profile.id).first()
    if not pref:
        pref = MatchingPreference(profile_id=profile.id)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


@router.get("/matching/preferences", response_model=MatchingPreferenceResponse, tags=["University Matching"])
def get_matching_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_or_init_profile(db, current_user)
    pref = _get_or_init_pref(db, profile)
    return pref


@router.put("/matching/preferences", response_model=MatchingPreferenceResponse, tags=["University Matching"])
def update_matching_preferences(
    payload: MatchingPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_or_init_profile(db, current_user)
    pref = _get_or_init_pref(db, profile)

    for field, val in payload.model_dump().items():
        if field == "preferred_countries":
            val = [str(c).strip().upper()[:2] for c in (val or []) if c]
        setattr(pref, field, val)

    db.commit()
    db.refresh(pref)
    return pref


@router.post("/matching/run", response_model=MatchingRunResponse, tags=["University Matching"])
def run_matching_engine(
    payload: MatchingRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_or_init_profile(db, current_user)
    pref = _get_or_init_pref(db, profile)

    weights_override = None
    if any(
        v is not None
        for v in (
            payload.weight_academic,
            payload.weight_financial,
            payload.weight_readiness,
            payload.weight_transfer,
        )
    ):
        weights_override = {
            "academic": payload.weight_academic if payload.weight_academic is not None else float(pref.weight_academic),
            "financial": payload.weight_financial if payload.weight_financial is not None else float(pref.weight_financial),
            "readiness": payload.weight_readiness if payload.weight_readiness is not None else float(pref.weight_readiness),
            "transfer": payload.weight_transfer if payload.weight_transfer is not None else float(pref.weight_transfer),
        }

    return run_matching_discovery(
        db=db,
        profile=profile,
        pref=pref,
        applicant_type=payload.applicant_type,
        intended_major=payload.intended_major,
        countries=payload.countries,
        states=payload.states,
        institution_types=payload.institution_types,
        budget_override=payload.max_annual_budget,
        weights_override=weights_override,
        limit=payload.limit,
        persist=payload.persist,
    )


@router.post(
    "/matching/evaluate/{institution_id}",
    response_model=UniversityMatchRecommendationSchema,
    tags=["University Matching"],
)
def evaluate_specific_institution(
    institution_id: UUID,
    applicant_type: Optional[str] = Query(None),
    intended_major: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

    profile = _get_or_init_profile(db, current_user)
    pref = _get_or_init_pref(db, profile)
    pathway = (applicant_type or profile.applicant_type or "first_year").lower()
    if pathway in ("undecided", "both"):
        pathway = "first_year"
    major = intended_major or profile.intended_major

    result = evaluate_single_institution_match(
        db=db,
        inst=inst,
        profile=profile,
        pref=pref,
        pathway=pathway,
        intended_major=major,
        persist=True,
    )
    db.commit()
    return result


@router.post("/matching/recommendations/{institution_id}/save", tags=["University Matching"])
def toggle_shortlist_institution(
    institution_id: UUID,
    saved: bool = Query(True, description="True to save to shortlist, False to remove"),
    applicant_type: Optional[str] = Query(None),
    intended_major: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

    profile = _get_or_init_profile(db, current_user)
    pref = _get_or_init_pref(db, profile)

    rec = (
        db.query(UniversityRecommendation)
        .filter(
            UniversityRecommendation.profile_id == profile.id,
            UniversityRecommendation.institution_id == institution_id,
        )
        .first()
    )
    if not rec:
        pathway = (applicant_type or profile.applicant_type or "first_year").lower()
        if pathway in ("undecided", "both"):
            pathway = "first_year"
        evaluate_single_institution_match(
            db=db,
            inst=inst,
            profile=profile,
            pref=pref,
            pathway=pathway,
            intended_major=intended_major or profile.intended_major,
            persist=True,
        )
        rec = (
            db.query(UniversityRecommendation)
            .filter(
                UniversityRecommendation.profile_id == profile.id,
                UniversityRecommendation.institution_id == institution_id,
            )
            .first()
        )

    rec.is_saved_by_student = saved
    db.commit()
    return {"institution_id": str(institution_id), "is_saved_by_student": rec.is_saved_by_student}


@router.get(
    "/matching/shortlist",
    response_model=List[UniversityMatchRecommendationSchema],
    tags=["University Matching"],
)
def list_shortlisted_universities(
    applicant_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        return []
    pref = db.query(MatchingPreference).filter(MatchingPreference.profile_id == profile.id).first()

    saved_rows = (
        db.query(UniversityRecommendation)
        .filter(
            UniversityRecommendation.profile_id == profile.id,
            UniversityRecommendation.is_saved_by_student == True,
        )
        .order_by(UniversityRecommendation.composite_score.desc())
        .all()
    )
    out: List[UniversityMatchRecommendationSchema] = []
    for row in saved_rows:
        pathway = (applicant_type or row.applicant_type or "first_year").lower()
        if pathway in ("undecided", "both"):
            pathway = "first_year"
        res = evaluate_single_institution_match(
            db=db,
            inst=row.institution,
            profile=profile,
            pref=pref,
            pathway=pathway,
            intended_major=row.intended_major or profile.intended_major,
            persist=False,
        )
        res.is_saved_by_student = True
        out.append(res)
    return out


@router.post(
    "/matching/compare",
    response_model=List[UniversityMatchRecommendationSchema],
    tags=["University Matching"],
)
def compare_institutions_side_by_side(
    payload: CompareInstitutionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_or_init_profile(db, current_user)
    pref = _get_or_init_pref(db, profile)
    pathway = (payload.applicant_type or profile.applicant_type or "first_year").lower()
    if pathway in ("undecided", "both"):
        pathway = "first_year"
    major = payload.intended_major or profile.intended_major

    results: List[UniversityMatchRecommendationSchema] = []
    for inst_id in payload.institution_ids:
        inst = db.query(Institution).filter(Institution.id == inst_id).first()
        if not inst:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Institution {inst_id} not found.",
            )
        rec_saved = (
            db.query(UniversityRecommendation.is_saved_by_student)
            .filter(
                UniversityRecommendation.profile_id == profile.id,
                UniversityRecommendation.institution_id == inst.id,
            )
            .scalar()
        )
        ev = evaluate_single_institution_match(
            db=db,
            inst=inst,
            profile=profile,
            pref=pref,
            pathway=pathway,
            intended_major=major,
            persist=False,
        )
        ev.is_saved_by_student = bool(rec_saved)
        results.append(ev)
    return results
