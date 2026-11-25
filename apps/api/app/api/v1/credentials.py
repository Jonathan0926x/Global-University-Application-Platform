from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_profile, get_db
from app.models.credentials import CredentialRecognitionRule
from app.models.profile import StudentProfile
from app.schemas.phase4 import (
    CredentialEvaluateRequest,
    CredentialEvaluationResponse,
    CredentialRecognitionRuleSchema,
    GradingSystemOptionSchema,
    ProfileCredentialEvaluationResponse,
)
from app.services.credential_engine import (
    ensure_credentials_seeded,
    evaluate_credential,
    evaluate_profile_credentials,
    list_grading_systems,
)

router = APIRouter()


@router.get(
    "/credentials/profile-evaluate",
    response_model=ProfileCredentialEvaluationResponse,
    tags=["International Credentials"],
)
def evaluate_authenticated_profile_credentials(
    destination_country: str = Query("US"),
    profile: Optional[StudentProfile] = Depends(get_current_profile),
    db: Session = Depends(get_db),
):
    res = evaluate_profile_credentials(db, profile, destination_country_code=destination_country)
    return ProfileCredentialEvaluationResponse(**res)


@router.get(
    "/credentials/systems",
    response_model=List[GradingSystemOptionSchema],
    tags=["International Credentials"],
)
def get_grading_systems(db: Session = Depends(get_db)):
    return [GradingSystemOptionSchema(**s) for s in list_grading_systems(db)]


@router.get(
    "/credentials/recognition-rules",
    response_model=List[CredentialRecognitionRuleSchema],
    tags=["International Credentials"],
)
def get_recognition_rules(
    source_country: Optional[str] = Query(None),
    destination_country: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    ensure_credentials_seeded(db)
    qry = db.query(CredentialRecognitionRule)
    if source_country:
        qry = qry.filter(CredentialRecognitionRule.source_country_code == source_country.strip().upper()[:2])
    if destination_country:
        qry = qry.filter(CredentialRecognitionRule.destination_country_code == destination_country.strip().upper()[:2])
    return qry.order_by(
        CredentialRecognitionRule.source_country_code.asc(),
        CredentialRecognitionRule.destination_country_code.asc(),
    ).all()


@router.post(
    "/credentials/evaluate",
    response_model=CredentialEvaluationResponse,
    tags=["International Credentials"],
)
def evaluate_international_credential(
    payload: CredentialEvaluateRequest,
    db: Session = Depends(get_db),
):
    res = evaluate_credential(
        db=db,
        source_country_code=payload.source_country_code,
        grading_system_key=payload.grading_system_key,
        raw_grade=payload.raw_grade,
        destination_country_code=payload.destination_country_code,
        academic_level=payload.academic_level,
    )
    return CredentialEvaluationResponse(**res)
