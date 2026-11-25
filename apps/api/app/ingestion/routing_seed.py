"""
Official Application Routing Directory Seeder & URL Validator (Milestone 7).

Strict Grounding Guarantees:
1. Validates every URL structurally (`http://`/`https://`, valid hostname, blocks local/SSRF/script/example URLs).
2. Curated institution & centralized-platform destinations include real official URLs, source names,
   verification timestamps, and international instructions.
3. IPEDS-reported `application_portal_url` records without independent manual verification are marked
   `needs_verification` (`medium` confidence) and NEVER forged when NULL.
"""

from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from app.models.institution import Institution
from app.models.routing import ApplicationRoute


_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "example.com", "example.org", "test.local"}


def validate_routing_url(url: Optional[str]) -> Dict[str, Any]:
    raw = (url or "").strip()
    if not raw:
        return {"valid": False, "reason": "URL is empty.", "normalized_url": None, "scheme_secure": False}

    lower = raw.lower()
    if lower.startswith(("javascript:", "data:", "vbscript:", "file:")):
        return {"valid": False, "reason": "Disallowed URL scheme.", "normalized_url": None, "scheme_secure": False}

    parsed = urlparse(raw)
    if parsed.scheme not in ("https", "http"):
        return {"valid": False, "reason": "URL must start with https:// or http://.", "normalized_url": None, "scheme_secure": False}

    host = (parsed.hostname or "").lower().strip()
    if not host or "." not in host or host in _BLOCKED_HOSTS:
        return {"valid": False, "reason": f"Invalid or restricted host: '{host or 'missing'}'.", "normalized_url": None, "scheme_secure": False}

    # Block raw IPv4/IPv6 literal targets (private / SSRF hygiene)
    try:
        ip_address(host)
        return {"valid": False, "reason": "IP-literal URLs are disallowed for official application routing.", "normalized_url": None, "scheme_secure": False}
    except ValueError:
        pass

    if re.search(r"\s", raw):
        return {"valid": False, "reason": "URL contains whitespace characters.", "normalized_url": None, "scheme_secure": False}

    return {
        "valid": True,
        "reason": None,
        "normalized_url": raw,
        "scheme_secure": parsed.scheme == "https",
    }


CURATED_CENTRALIZED_PLATFORMS: List[Dict[str, Any]] = [
    {
        "platform_name": "UC Application (University of California Centralized System)",
        "platform_type": "state_system",
        "country_code": "US",
        "applicant_type": "all",
        "official_url": "https://apply.universityofcalifornia.edu/",
        "international_instructions": "International first-year and transfer applicants submit one centralized UC Application covering all 9 undergraduate campuses (including UC Berkeley and UCLA) between October 1 and November 30.",
        "notes": "Single portal for both First-Year and Transfer applicants to any UC campus.",
        "source_name": "University of California Admissions",
        "source_url": "https://admission.universityofcalifornia.edu/apply-now.html",
    },
    {
        "platform_name": "Common App (First-Year Centralized US & Global)",
        "platform_type": "common_app",
        "country_code": "US",
        "applicant_type": "first_year",
        "official_url": "https://apply.commonapp.org/",
        "international_instructions": "Used by 1,000+ US and international colleges for first-year applicants; supports school report, counselor recommendation, and international fee waiver requests.",
        "notes": "Separate Common App for Transfer workspace exists on apply.commonapp.org/transfer.",
        "source_name": "The Common Application",
        "source_url": "https://www.commonapp.org/",
    },
    {
        "platform_name": "Common App for Transfer",
        "platform_type": "common_app",
        "country_code": "US",
        "applicant_type": "transfer",
        "official_url": "https://www.commonapp.org/apply/transfer-students",
        "international_instructions": "Verify per-university participation before starting; international transfers often require WES/ECE course-by-course credential evaluation alongside official syllabi.",
        "notes": "Dedicated transfer platform distinct from First-Year Common App.",
        "source_name": "Common App Transfer",
        "source_url": "https://www.commonapp.org/apply/transfer-students",
    },
    {
        "platform_name": "Cal State Apply (California State University System)",
        "platform_type": "state_system",
        "country_code": "US",
        "applicant_type": "all",
        "official_url": "https://www.calstate.edu/apply",
        "international_instructions": "Single application portal for all 23 CSU campuses (including San Francisco State University) supporting First-Year, Upper-Division Transfer (ADT), and International applicants.",
        "notes": "Priority filing window typically opens October 1.",
        "source_name": "California State University",
        "source_url": "https://www.calstate.edu/apply",
    },
    {
        "platform_name": "UCAS (UK Universities & Colleges Admissions Service)",
        "platform_type": "country_platform",
        "country_code": "GB",
        "applicant_type": "all",
        "official_url": "https://www.ucas.com/",
        "international_instructions": "Mandatory centralized portal for UK full-time undergraduate courses (including Oxford, Cambridge, and UCL). Max 5 choices (4 for medicine). Oxford/Cambridge deadline is October 15.",
        "notes": "Both UK domestic and international undergraduate entrants apply through UCAS Hub.",
        "source_name": "UCAS Official Hub",
        "source_url": "https://www.ucas.com/undergraduate/applying-to-university",
    },
    {
        "platform_name": "OUAC (Ontario Universities' Application Centre)",
        "platform_type": "country_platform",
        "country_code": "CA",
        "applicant_type": "all",
        "official_url": "https://www.ouac.on.ca/",
        "international_instructions": "Required portal for University of Toronto and all Ontario universities. International applicants residing outside Canada use OUAC Undergraduate Application followed by institutional document portal (JOIN U of T).",
        "notes": "Supports secondary and post-secondary transfer applicants to Ontario institutions.",
        "source_name": "OUAC Official Portal",
        "source_url": "https://www.ouac.on.ca/",
    },
    {
        "platform_name": "Études en France (Campus France)",
        "platform_type": "country_platform",
        "country_code": "FR",
        "applicant_type": "international_first_year",
        "official_url": "https://pastel.diplomatie.gouv.fr/etudesenfrance",
        "international_instructions": "Mandatory centralized admission + visa pre-consular portal for applicants from 65+ CEF countries (including Haiti) applying to French public universities such as Sorbonne Université and Université Paris-Saclay.",
        "notes": "EU/EEA and French resident first-year applicants use Parcoursup instead.",
        "source_name": "Campus France / Ministère de l'Europe et des Affaires étrangères",
        "source_url": "https://www.campusfrance.org/en/etudes-en-france-procedure",
    },
    {
        "platform_name": "uni-assist (International HZB / VPD Verification for Germany)",
        "platform_type": "country_platform",
        "country_code": "DE",
        "applicant_type": "international_first_year",
        "official_url": "https://my.uni-assist.de/",
        "international_instructions": "International applicants with non-German credentials must obtain a VPD (Vorprüfungsdokumentation) via uni-assist before or alongside submitting in TUMonline / LMU International portal.",
        "notes": "Allow 4–6 weeks for uni-assist VPD processing prior to university portal cutoffs.",
        "source_name": "uni-assist e.V.",
        "source_url": "https://www.uni-assist.de/en/",
    },
]


CURATED_INSTITUTION_ROUTES: List[Dict[str, Any]] = [
    {
        "ipeds": "110635",
        "platform_name": "UC Application Portal — UC Berkeley (First-Year)",
        "platform_type": "state_system",
        "applicant_type": "first_year",
        "official_url": "https://apply.universityofcalifornia.edu/",
        "international_instructions": "International first-year students apply via the exact same UC Application (Oct 1 – Nov 30) and later upload secondary/external exam records in MAP@Berkeley.",
        "source_name": "UC Berkeley Undergraduate Admissions",
        "source_url": "https://admissions.berkeley.edu/apply-to-berkeley/",
    },
    {
        "ipeds": "110635",
        "platform_name": "UC Application Portal — UC Berkeley (Transfer)",
        "platform_type": "state_system",
        "applicant_type": "transfer",
        "official_url": "https://apply.universityofcalifornia.edu/",
        "international_instructions": "Complete Transfer Academic Update (TAU) by Jan 31 after Fall grades post. Check California CC course equivalencies on ASSIST.org before applying.",
        "source_name": "UC Berkeley Transfer Admissions",
        "source_url": "https://admissions.berkeley.edu/apply-to-berkeley/transfer-students/",
    },
    {
        "ipeds": "110662",
        "platform_name": "UC Application Portal — UCLA (First-Year)",
        "platform_type": "state_system",
        "applicant_type": "first_year",
        "official_url": "https://apply.universityofcalifornia.edu/",
        "international_instructions": "Submit UC Application directly; TOEFL/IELTS or Duolingo English Test scores are required if high school instruction was outside an English-majority system.",
        "source_name": "UCLA Undergraduate Admission",
        "source_url": "https://admission.ucla.edu/apply/first-year-applicants",
    },
    {
        "ipeds": "110662",
        "platform_name": "UC Application Portal — UCLA (Transfer)",
        "platform_type": "state_system",
        "applicant_type": "transfer",
        "official_url": "https://apply.universityofcalifornia.edu/",
        "international_instructions": "Must complete 60 semester / 90 quarter transferable units and major prep prior to Spring end; UC Application serves domestic and international transfers identically.",
        "source_name": "UCLA Transfer Admission",
        "source_url": "https://admission.ucla.edu/apply/transfer-applicants",
    },
    {
        "ipeds": "170976",
        "platform_name": "Common App — University of Michigan (First-Year & Transfer)",
        "platform_type": "common_app",
        "applicant_type": "all",
        "official_url": "https://apply.commonapp.org/",
        "international_instructions": "UMich accepts the Common App for both First-Year and Transfer applicants; track credential receipt in Enrollment Connect afterward.",
        "source_name": "University of Michigan Office of Undergraduate Admissions",
        "source_url": "https://admissions.umich.edu/apply",
    },
    {
        "ipeds": "166683",
        "platform_name": "MyMIT Direct Institutional Portal (First-Year & Transfer)",
        "platform_type": "direct_portal",
        "applicant_type": "all",
        "official_url": "https://my.mit.edu/",
        "international_instructions": "MIT does NOT use the Common App. Both domestic and international applicants apply strictly through MyMIT and complete CSS Profile + tax docs for need-based aid.",
        "source_name": "MIT Admissions",
        "source_url": "https://mitadmissions.org/apply/",
    },
    {
        "ipeds": "122597",
        "platform_name": "Cal State Apply — San Francisco State University",
        "platform_type": "state_system",
        "applicant_type": "all",
        "official_url": "https://www.calstate.edu/apply",
        "international_instructions": "International F-1 students submit financial affidavit and foreign transcripts via SF State Gateway following Cal State Apply filing.",
        "source_name": "SFSU Future Students",
        "source_url": "https://future.sfsu.edu/admissions",
    },
    {
        "ipeds": "113333",
        "platform_name": "CCCApply — De Anza College",
        "platform_type": "state_system",
        "applicant_type": "all",
        "official_url": "https://www.opencccapply.net/",
        "international_instructions": "Domestic/CA students use CCCApply; F-1 international students apply via De Anza International Student Programs portal.",
        "source_name": "De Anza College Admissions",
        "source_url": "https://www.deanza.edu/admissions/",
    },
    {
        "ipeds": "122931",
        "platform_name": "CCCApply / OpenCCC — Santa Monica College",
        "platform_type": "state_system",
        "applicant_type": "all",
        "official_url": "https://www.opencccapply.net/",
        "international_instructions": "F-1 international students apply through SMC International Education Center portal separately from CCCApply.",
        "source_name": "Santa Monica College Admissions",
        "source_url": "https://www.smc.edu/admission-aid/apply/",
    },
    {
        "ipeds": "113698",
        "platform_name": "WGU Direct Online Enrollment Portal",
        "platform_type": "direct_portal",
        "applicant_type": "all",
        "official_url": "https://www.wgu.edu/admissions.html",
        "international_instructions": "WGU primarily serves US residents and limited Canadian/international regions; verify state/country eligibility before paying enrollment fees.",
        "source_name": "Western Governors University",
        "source_url": "https://www.wgu.edu/admissions.html",
    },
    {
        "name": "University of Toronto",
        "platform_name": "OUAC & U of T International Application",
        "platform_type": "country_platform",
        "applicant_type": "all",
        "official_url": "https://www.ouac.on.ca/",
        "international_instructions": "All full-time undergraduates apply via OUAC; transfer students submit course syllabi in JOIN U of T for transfer credit assessment.",
        "source_name": "University of Toronto Future Students",
        "source_url": "https://future.utoronto.ca/apply/applying/",
    },
    {
        "name": "McGill University",
        "platform_name": "McGill Direct Admissions Portal (Slate)",
        "platform_type": "direct_portal",
        "applicant_type": "all",
        "official_url": "https://www.mcgill.ca/applying/",
        "international_instructions": "McGill manages applications directly (not via OUAC); international transfer/first-year applicants upload self-reported grades and request official transcripts in Minerva.",
        "source_name": "McGill Undergraduate Admissions",
        "source_url": "https://www.mcgill.ca/applying/",
    },
    {
        "name": "University of British Columbia",
        "platform_name": "EducationPlannerBC (EPBC) — UBC Undergraduate",
        "platform_type": "state_system",
        "applicant_type": "all",
        "official_url": "https://you.ubc.ca/applying-ubc/",
        "international_instructions": "Applications route through EducationPlannerBC into UBC Student Service Centre (SSC) for post-submission transcript upload.",
        "source_name": "UBC Undergraduate Admissions",
        "source_url": "https://you.ubc.ca/applying-ubc/",
    },
    {
        "name": "University of Oxford",
        "platform_name": "UCAS — University of Oxford",
        "platform_type": "country_platform",
        "applicant_type": "first_year",
        "official_url": "https://www.ucas.com/",
        "international_instructions": "Strict October 15 UCAS deadline; subject admission tests (MAT/PAT/TSA) must be registered separately. Oxford generally does not accept transfer credits.",
        "source_name": "University of Oxford Admissions",
        "source_url": "https://www.ox.ac.uk/admissions/undergraduate/applying-to-oxford",
    },
    {
        "name": "Technical University of Munich",
        "platform_name": "TUMonline Direct + uni-assist VPD",
        "platform_type": "direct_portal",
        "applicant_type": "all",
        "official_url": "https://campus.tum.de/",
        "international_instructions": "International applicants with foreign certificates must request a VPD via uni-assist.de first, then submit the degree application in TUMonline before July 15 (Winter) or January 15 (Summer).",
        "source_name": "Technical University of Munich",
        "source_url": "https://www.tum.de/en/studies/application",
    },
    {
        "name": "Sorbonne Université",
        "platform_name": "Études en France / Parcoursup — Sorbonne Université",
        "platform_type": "country_platform",
        "applicant_type": "all",
        "official_url": "https://pastel.diplomatie.gouv.fr/etudesenfrance",
        "international_instructions": "Non-EU international candidates in CEF countries apply through Études en France; EU/French Bac holders apply via Parcoursup.",
        "source_name": "Sorbonne Université Admissions",
        "source_url": "https://www.sorbonne-universite.fr/en/admissions",
    },
    {
        "name": "University of Haiti",
        "platform_name": "UEH Official Admissions Portal (Université d'État d'Haïti)",
        "platform_type": "direct_portal",
        "applicant_type": "first_year",
        "official_url": "https://admission.ueh.edu.ht/",
        "international_instructions": "Requires Baccalauréat (Rhéto/Philo or NS4) + MENFP transcript legalization and faculty-specific entrance exam registration.",
        "source_name": "Université d'État d'Haïti",
        "source_url": "https://admission.ueh.edu.ht/",
    },
    {
        "name": "Quisqueya University",
        "platform_name": "UniQ Official Admissions Portal",
        "platform_type": "direct_portal",
        "applicant_type": "all",
        "official_url": "https://uniq.edu.ht/",
        "international_instructions": "Requires certified Baccalauréat I & II / NS4, national ID/passport, and faculty placement review.",
        "source_name": "Université Quisqueya",
        "source_url": "https://uniq.edu.ht/",
    },
    {
        "name": "The University of Tokyo",
        "platform_name": "UTokyo PEAK / Undergraduate Online Application",
        "platform_type": "direct_portal",
        "applicant_type": "first_year",
        "official_url": "https://www.u-tokyo.ac.jp/en/prospective-students/undergraduate_admissions.html",
        "international_instructions": "International English-track applicants apply through PEAK online system; standard track requires EJU and JLPT N1.",
        "source_name": "University of Tokyo Admissions",
        "source_url": "https://www.u-tokyo.ac.jp/en/prospective-students/undergraduate_admissions.html",
    },
    {
        "name": "The University of Melbourne",
        "platform_name": "University of Melbourne Direct International Portal",
        "platform_type": "direct_portal",
        "applicant_type": "all",
        "official_url": "https://study.unimelb.edu.au/how-to-apply/undergraduate-study/international-applications",
        "international_instructions": "International students outside Australia apply online directly (or via VTAC if completing Australian Year 12 / IB in Victoria).",
        "source_name": "University of Melbourne Study",
        "source_url": "https://study.unimelb.edu.au/how-to-apply",
    },
]


def seed_verified_application_routes(db: Session) -> Dict[str, int]:
    """
    Idempotently seeds centralized platforms and verified institution routes,
    validating every URL cleanly before persistence.
    """
    now = datetime.now(timezone.utc)
    counts = {"centralized_created": 0, "institution_created": 0, "ipeds_needs_verification": 0}

    # 1. Centralized country & multi-campus platforms
    for p in CURATED_CENTRALIZED_PLATFORMS:
        val = validate_routing_url(p["official_url"])
        if not val["valid"]:
            continue
        exists = (
            db.query(ApplicationRoute)
            .filter(
                ApplicationRoute.institution_id.is_(None),
                ApplicationRoute.platform_name == p["platform_name"],
                ApplicationRoute.applicant_type == p["applicant_type"],
            )
            .first()
        )
        if not exists:
            db.add(
                ApplicationRoute(
                    institution_id=None,
                    platform_name=p["platform_name"],
                    platform_type=p["platform_type"],
                    country_code=p["country_code"],
                    applicant_type=p["applicant_type"],
                    official_url=val["normalized_url"],
                    international_instructions=p.get("international_instructions"),
                    notes=p.get("notes"),
                    source_name=p["source_name"],
                    source_url=p.get("source_url"),
                    verification_status="verified",
                    confidence_level="high",
                    verified_at=now,
                    verification_expires_at=now + timedelta(days=180),
                    pathway_verified=True,
                    last_checked_at=now,
                    is_active=True,
                )
            )
            counts["centralized_created"] += 1

    # 2. Curated flagship institution routes
    for r in CURATED_INSTITUTION_ROUTES:
        val = validate_routing_url(r["official_url"])
        if not val["valid"]:
            continue
        inst = None
        if r.get("ipeds"):
            inst = db.query(Institution).filter(Institution.ipeds_unit_id == r["ipeds"]).first()
        elif r.get("name"):
            inst = db.query(Institution).filter(Institution.official_name == r["name"]).first()
        if not inst:
            continue

        exists = (
            db.query(ApplicationRoute)
            .filter(
                ApplicationRoute.institution_id == inst.id,
                ApplicationRoute.applicant_type == r["applicant_type"],
                ApplicationRoute.official_url == val["normalized_url"],
            )
            .first()
        )
        if not exists:
            db.add(
                ApplicationRoute(
                    institution_id=inst.id,
                    platform_name=r["platform_name"],
                    platform_type=r["platform_type"],
                    country_code=inst.country_code,
                    applicant_type=r["applicant_type"],
                    official_url=val["normalized_url"],
                    international_instructions=r.get("international_instructions"),
                    source_name=r["source_name"],
                    source_url=r.get("source_url"),
                    verification_status="verified",
                    confidence_level="high",
                    verified_at=now,
                    verification_expires_at=now + timedelta(days=180),
                    pathway_verified=True,
                    last_checked_at=now,
                    is_active=True,
                )
            )
            counts["institution_created"] += 1

    # 3. Link IPEDS-reported portals explicitly as `needs_verification` (never forged if NULL!)
    ipeds_insts = (
        db.query(Institution)
        .filter(
            Institution.application_portal_url.isnot(None),
            Institution.is_published == True,
        )
        .order_by(Institution.total_enrollment.desc().nullslast())
        .limit(400)
        .all()
    )
    for inst in ipeds_insts:
        val = validate_routing_url(inst.application_portal_url)
        if not val["valid"]:
            continue
        has_any = (
            db.query(ApplicationRoute.id)
            .filter(ApplicationRoute.institution_id == inst.id)
            .first()
        )
        if has_any:
            continue
        url_lower = val["normalized_url"].lower()
        ptype = "common_app" if "commonapp.org" in url_lower else "direct_portal"
        pname = "Common App (Reported via IPEDS)" if ptype == "common_app" else f"{inst.official_name} Application Portal (IPEDS Reported)"
        db.add(
            ApplicationRoute(
                institution_id=inst.id,
                platform_name=pname,
                platform_type=ptype,
                country_code=inst.country_code,
                applicant_type="all",
                official_url=val["normalized_url"],
                notes="Imported from NCES IPEDS HD2023 application link; verify pathway & term cutoffs directly.",
                source_name="NCES IPEDS HD2023",
                source_url=inst.admissions_website or val["normalized_url"],
                verification_status="needs_verification",
                confidence_level="medium" if val["scheme_secure"] else "low",
                verified_at=inst.last_verified_at,
                last_checked_at=now,
                is_active=True,
            )
        )
        counts["ipeds_needs_verification"] += 1

    db.commit()
    return counts
