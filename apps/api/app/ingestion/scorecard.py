"""
U.S. Department of Education College Scorecard Connector.
Supports:
  1. Official Bulk Institutional Cohort CSV (Most-Recent-Cohorts-Institution)
  2. Live Department of Education REST API (api.data.gov/ed/collegescorecard/v1/schools with DEMO_KEY)
License: Public Domain (U.S. Department of Education)
"""

import csv
import io
import os
import zipfile
from typing import Any, Dict, List, Optional
import httpx

from app.ingestion.base import (
    BaseInstitutionConnector,
    NormalizedInstitution,
    NormalizedProgram,
)

DEFAULT_RAW_DIR = os.path.expanduser(
    "~/.gemini/antigravity/scratch/Global-University-Application-Platform/data/raw/us"
)
SCORECARD_ZIP_NAME = "Most-Recent-Cohorts-Institution_11022026.zip"
SCORECARD_ZIP_URL = f"https://ed-public-download.scorecard.network/downloads/{SCORECARD_ZIP_NAME}"
SCORECARD_API_URL = "https://api.data.gov/ed/collegescorecard/v1/schools"

# Official NCES 2-digit CIP 2020 classifications for program mapping (PCIP01..PCIP54)
CIP_2DIGIT_NAMES: Dict[str, str] = {
    "01": "Agricultural / Animal / Plant / Veterinary Science",
    "03": "Natural Resources and Conservation",
    "04": "Architecture and Related Services",
    "05": "Area, Ethnic, Cultural, Gender, and Group Studies",
    "09": "Communication, Journalism, and Related Programs",
    "11": "Computer and Information Sciences and Support Services",
    "13": "Education",
    "14": "Engineering",
    "15": "Engineering / Engineering-Related Technologies",
    "16": "Foreign Languages, Literatures, and Linguistics",
    "19": "Family and Consumer Sciences / Human Sciences",
    "22": "Legal Professions and Studies",
    "23": "English Language and Literature / Letters",
    "24": "Liberal Arts and Sciences, General Studies and Humanities",
    "26": "Biological and Biomedical Sciences",
    "27": "Mathematics and Statistics",
    "30": "Multi / Interdisciplinary Studies",
    "31": "Parks, Recreation, Leisure, Fitness, and Kinesiology",
    "38": "Philosophy and Religious Studies",
    "40": "Physical Sciences",
    "42": "Psychology",
    "43": "Homeland Security, Law Enforcement, Firefighting",
    "44": "Public Administration and Social Service Professions",
    "45": "Social Sciences",
    "50": "Visual and Performing Arts",
    "51": "Health Professions and Related Programs",
    "52": "Business, Management, Marketing, and Related Support Services",
    "54": "History",
}


def _clean_sc_str(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s in ("NULL", "PrivacySuppressed", "PS", "NA", "N/A", "."):
        return None
    return s


def _clean_sc_url(val: Any) -> Optional[str]:
    s = _clean_sc_str(val)
    if not s:
        return None
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return f"https://{s}"


def _clean_sc_float(val: Any) -> Optional[float]:
    s = _clean_sc_str(val)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _clean_sc_int(val: Any) -> Optional[int]:
    f = _clean_sc_float(val)
    return int(round(f)) if f is not None else None


def _clean_sc_pct(val: Any) -> Optional[float]:
    f = _clean_sc_float(val)
    if f is None:
        return None
    return round(f * 100.0, 2) if f <= 1.0 else round(f, 2)


class CollegeScorecardConnector(BaseInstitutionConnector):
    source_name = "U.S. Dept. of Education College Scorecard"
    source_type = "college_scorecard"
    license_type = "Public Domain (U.S. Department of Education)"

    def __init__(self, raw_dir: str = DEFAULT_RAW_DIR, api_key: Optional[str] = None):
        self.raw_dir = raw_dir
        self.api_key = api_key or os.getenv("COLLEGE_SCORECARD_API_KEY", "DEMO_KEY")

    def _ensure_bulk_zip(self) -> str:
        os.makedirs(self.raw_dir, exist_ok=True)
        path = os.path.join(self.raw_dir, SCORECARD_ZIP_NAME)
        if not os.path.exists(path):
            with httpx.stream("GET", SCORECARD_ZIP_URL, follow_redirects=True, timeout=180.0) as r:
                r.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=1024 * 256):
                        f.write(chunk)
        return path

    @staticmethod
    def _parse_row(row: Dict[str, Any], source_url: str) -> Optional[NormalizedInstitution]:
        unitid = _clean_sc_str(row.get("UNITID") or row.get("id"))
        name = _clean_sc_str(row.get("INSTNM") or row.get("school.name"))
        if not name or not unitid:
            return None

        ope_id = _clean_sc_str(row.get("OPEID") or row.get("ope8_id"))
        ope6_id = _clean_sc_str(row.get("OPEID6") or row.get("ope6_id"))

        main_flag = _clean_sc_int(row.get("MAIN") if "MAIN" in row else row.get("school.main_campus"))
        is_main = True if main_flag is None or main_flag == 1 else False

        ctrl_num = _clean_sc_int(row.get("CONTROL") if "CONTROL" in row else row.get("school.ownership"))
        control_type = {1: "public", 2: "private_nonprofit", 3: "private_forprofit"}.get(ctrl_num)

        pred_deg = _clean_sc_int(row.get("PREDDEG") if "PREDDEG" in row else row.get("school.degrees_awarded.predominant"))
        if pred_deg == 2:
            inst_type = "community_college" if control_type == "public" else "technical_college"
        elif pred_deg == 3:
            inst_type = "university"
        elif pred_deg == 1:
            inst_type = "vocational"
        elif not is_main:
            inst_type = "branch_campus"
        else:
            inst_type = "other"

        npt_pub = _clean_sc_float(row.get("NPT4_PUB"))
        npt_priv = _clean_sc_float(row.get("NPT4_PRIV"))
        avg_net_price = npt_pub if npt_pub is not None else npt_priv

        comp_4yr = _clean_sc_pct(row.get("C150_4"))
        comp_l4 = _clean_sc_pct(row.get("C150_L4"))
        ret_4 = _clean_sc_pct(row.get("RET_FT4"))
        ret_l4 = _clean_sc_pct(row.get("RET_FTL4"))
        retention = ret_4 if ret_4 is not None else ret_l4

        # Aggregated student demographics (only stored when published)
        demographics: Dict[str, Any] = {}
        for col, label in [
            ("UGDS_WHITE", "white_pct"),
            ("UGDS_BLACK", "black_pct"),
            ("UGDS_HISP", "hispanic_pct"),
            ("UGDS_ASIAN", "asian_pct"),
            ("UGDS_AIAN", "aian_pct"),
            ("UGDS_NHPI", "nhpi_pct"),
            ("UGDS_2MOR", "two_or_more_pct"),
            ("UGDS_NRA", "international_pct"),
            ("UGDS_MEN", "men_pct"),
            ("UGDS_WOMEN", "women_pct"),
        ]:
            pct = _clean_sc_pct(row.get(col))
            if pct is not None:
                demographics[label] = pct

        # Extract dominant academic programs from PCIP01..PCIP54 (>= 3% share)
        degree_level = "associate" if pred_deg == 2 else ("certificate" if pred_deg == 1 else "bachelors")
        programs: List[NormalizedProgram] = []
        for cip2, cip_title in CIP_2DIGIT_NAMES.items():
            share = _clean_sc_float(row.get(f"PCIP{cip2}"))
            if share is not None and share >= 0.03:
                programs.append(NormalizedProgram(
                    program_name=cip_title,
                    degree_level=degree_level,
                    cip_code=cip2,
                    academic_year="2023-2024",
                    source_url=source_url,
                    verification_status="verified",
                ))

        accred = _clean_sc_str(row.get("ACCREDAGENCY") or row.get("school.accreditor"))

        return NormalizedInstitution(
            official_name=name[:500],
            country_code="US",
            country_name="United States",
            state_province=_clean_sc_str(row.get("STABBR") or row.get("school.state")),
            city=_clean_sc_str(row.get("CITY") or row.get("school.city")),
            postal_code=_clean_sc_str(row.get("ZIP") or row.get("school.zip")),
            latitude=_clean_sc_float(row.get("LATITUDE") or row.get("location.lat")),
            longitude=_clean_sc_float(row.get("LONGITUDE") or row.get("location.lon")),
            institution_type=inst_type,
            control_type=control_type,
            official_website=_clean_sc_url(row.get("INSTURL") or row.get("school.school_url")),
            net_price_calculator_url=_clean_sc_url(row.get("NPCURL") or row.get("school.price_calculator_url")),
            accreditation_status="accredited" if accred else None,
            accrediting_body=accred,
            undergraduate_enrollment=_clean_sc_int(row.get("UGDS")),
            total_enrollment=_clean_sc_int(row.get("UGDS")),
            acceptance_rate=_clean_sc_pct(row.get("ADM_RATE")),
            sat_math_25=_clean_sc_int(row.get("SATMT25")),
            sat_math_75=_clean_sc_int(row.get("SATMT75")),
            sat_ebrw_25=_clean_sc_int(row.get("SATVR25")),
            sat_ebrw_75=_clean_sc_int(row.get("SATVR75")),
            act_composite_25=_clean_sc_int(row.get("ACTCM25")),
            act_composite_75=_clean_sc_int(row.get("ACTCM75")),
            completion_rate_4yr=comp_4yr,
            completion_rate_less_4yr=comp_l4,
            retention_rate=retention,
            median_earnings_10yr=_clean_sc_float(row.get("MD_EARN_WNE_P10")),
            median_debt=_clean_sc_float(row.get("GRAD_DEBT_MDN")),
            pct_international=_clean_sc_pct(row.get("UGDS_NRA")),
            pct_pell=_clean_sc_pct(row.get("PCTPELL")),
            student_demographics=demographics,
            tuition_in_state=_clean_sc_float(row.get("TUITIONFEE_IN")),
            tuition_out_of_state=_clean_sc_float(row.get("TUITIONFEE_OUT")),
            avg_net_price=avg_net_price,
            cost_of_attendance=_clean_sc_float(row.get("COSTT4_A")),
            currency="USD",
            ipeds_unit_id=unitid,
            ope_id=ope_id,
            ope6_id=ope6_id,
            parent_ope6_id=ope6_id if not is_main else None,
            is_main_campus=is_main,
            programs=programs,
            source_type="college_scorecard",
            source_name="U.S. Dept. of Education College Scorecard",
            source_url=source_url,
            collection_method="bulk_csv" if source_url == SCORECARD_ZIP_URL else "api",
            confidence_level="verified",
            academic_year="2023-2024",
        )

    def fetch_from_live_api(self, state: Optional[str] = None, per_page: int = 20) -> List[NormalizedInstitution]:
        """Queries the live College Scorecard REST API (uses DEMO_KEY by default, $0 cost)."""
        fields = ",".join([
            "id", "ope6_id", "ope8_id", "school.name", "school.city", "school.state",
            "school.zip", "school.school_url", "school.price_calculator_url",
            "school.main_campus", "school.ownership", "school.degrees_awarded.predominant",
            "school.accreditor", "location.lat", "location.lon",
            "latest.admissions.admission_rate.overall",
            "latest.cost.tuition.in_state", "latest.cost.tuition.out_of_state",
            "latest.cost.attendance.academic_year",
            "latest.student.size", "latest.completion.completion_rate_4yr_150nt",
        ])
        params: Dict[str, Any] = {
            "api_key": self.api_key,
            "per_page": min(per_page, 100),
            "fields": fields,
        }
        if state:
            params["school.state"] = state.strip().upper()

        with httpx.Client(timeout=20.0) as client:
            resp = client.get(SCORECARD_API_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()

        results: List[NormalizedInstitution] = []
        for row in payload.get("results", []):
            mapped_row = {
                "UNITID": row.get("id"),
                "OPEID": row.get("ope8_id"),
                "OPEID6": row.get("ope6_id"),
                "INSTNM": row.get("school.name"),
                "CITY": row.get("school.city"),
                "STABBR": row.get("school.state"),
                "ZIP": row.get("school.zip"),
                "INSTURL": row.get("school.school_url"),
                "NPCURL": row.get("school.price_calculator_url"),
                "MAIN": row.get("school.main_campus"),
                "CONTROL": row.get("school.ownership"),
                "PREDDEG": row.get("school.degrees_awarded.predominant"),
                "ACCREDAGENCY": row.get("school.accreditor"),
                "LATITUDE": row.get("location.lat"),
                "LONGITUDE": row.get("location.lon"),
                "ADM_RATE": row.get("latest.admissions.admission_rate.overall"),
                "TUITIONFEE_IN": row.get("latest.cost.tuition.in_state"),
                "TUITIONFEE_OUT": row.get("latest.cost.tuition.out_of_state"),
                "COSTT4_A": row.get("latest.cost.attendance.academic_year"),
                "UGDS": row.get("latest.student.size"),
                "C150_4": row.get("latest.completion.completion_rate_4yr_150nt"),
            }
            parsed = self._parse_row(mapped_row, SCORECARD_API_URL)
            if parsed:
                results.append(parsed)
        return results

    def fetch_institutions(
        self,
        limit: Optional[int] = None,
        states: Optional[List[str]] = None,
        mode: str = "bulk",
    ) -> List[NormalizedInstitution]:
        if mode == "api":
            st = states[0] if states else None
            return self.fetch_from_live_api(state=st, per_page=limit or 20)

        zip_path = self._ensure_bulk_zip()
        state_filter = {s.strip().upper() for s in states} if states else None
        results: List[NormalizedInstitution] = []

        with zipfile.ZipFile(zip_path) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            with zf.open(csv_names[0]) as cf:
                reader = csv.DictReader(io.TextIOWrapper(cf, encoding="utf-8-sig", errors="replace"))
                for row in reader:
                    stabbr = (_clean_sc_str(row.get("STABBR")) or "").upper()
                    if state_filter and stabbr not in state_filter:
                        continue
                    parsed = self._parse_row(row, SCORECARD_ZIP_URL)
                    if parsed:
                        results.append(parsed)
                        if limit and len(results) >= limit:
                            break
        return results
