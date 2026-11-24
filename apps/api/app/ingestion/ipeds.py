"""
NCES IPEDS (Integrated Postsecondary Education Data System) Official Bulk CSV Connector.
Source: National Center for Education Statistics (U.S. Department of Education)
License: Public Domain
Datasets (2023-2024 Cycle):
  - HD2023.zip: Institutional Directory & Identifiers
  - IC2023.zip: Institutional Characteristics (Open Admissions, Calendar, App Fees)
  - IC2023_AY.zip: Academic Year Student Charges (Tuition, Mandatory Fees, Room/Board, Books)
  - ADM2023.zip: Admissions & Test Score Percentiles (SAT/ACT, Acceptance Rate)
  - DRVEF2023.zip: Fall Enrollment & Aggregated Demographics
"""

import csv
import io
import os
import zipfile
from typing import Any, Dict, List, Optional
import httpx

from app.ingestion.base import (
    BaseInstitutionConnector,
    NormalizedCost,
    NormalizedInstitution,
)

DEFAULT_RAW_DIR = os.path.expanduser(
    "~/.gemini/antigravity/scratch/Global-University-Application-Platform/data/raw/us"
)

IPEDS_FILES = {
    "HD2023.zip": "https://nces.ed.gov/ipeds/datacenter/data/HD2023.zip",
    "IC2023.zip": "https://nces.ed.gov/ipeds/datacenter/data/IC2023.zip",
    "IC2023_AY.zip": "https://nces.ed.gov/ipeds/datacenter/data/IC2023_AY.zip",
    "ADM2023.zip": "https://nces.ed.gov/ipeds/datacenter/data/ADM2023.zip",
    "DRVEF2023.zip": "https://nces.ed.gov/ipeds/datacenter/data/DRVEF2023.zip",
}

CARNEGIE_2021_LABELS = {
    "15": "Doctoral Universities: Very High Research Activity (R1)",
    "16": "Doctoral Universities: High Research Activity (R2)",
    "17": "Doctoral/Professional Universities",
    "18": "Master's Colleges & Universities: Larger Programs",
    "19": "Master's Colleges & Universities: Medium Programs",
    "20": "Master's Colleges & Universities: Small Programs",
    "21": "Baccalaureate Colleges: Arts & Sciences Focus",
    "22": "Baccalaureate Colleges: Diverse Fields",
    "23": "Baccalaureate/Associate's Colleges",
}

CALENDAR_MAP = {
    "1": "semester",
    "2": "quarter",
    "3": "trimester",
    "4": "four_one_four",
    "5": "other",
    "6": "continuous",
    "7": "other",
}


def _clean_str(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    s = val.strip()
    if not s or s in (".", "-1", "-2", "NULL", "PrivacySuppressed", "N/A"):
        return None
    return s


def _clean_url(val: Optional[str]) -> Optional[str]:
    s = _clean_str(val)
    if not s:
        return None
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return f"https://{s}"


def _clean_int(val: Optional[str]) -> Optional[int]:
    s = _clean_str(val)
    if not s:
        return None
    try:
        n = int(float(s))
        return n if n >= 0 else None
    except ValueError:
        return None


def _clean_float(val: Optional[str]) -> Optional[float]:
    s = _clean_str(val)
    if not s:
        return None
    try:
        n = float(s)
        return n if n >= 0 else None
    except ValueError:
        return None


class IPEDSConnector(BaseInstitutionConnector):
    source_name = "NCES IPEDS 2023 Bulk Data"
    source_type = "ipeds"
    license_type = "Public Domain (U.S. Department of Education)"

    def __init__(self, raw_dir: str = DEFAULT_RAW_DIR):
        self.raw_dir = raw_dir

    def _ensure_files(self):
        os.makedirs(self.raw_dir, exist_ok=True)
        missing = [(fn, url) for fn, url in IPEDS_FILES.items() if not os.path.exists(os.path.join(self.raw_dir, fn))]
        if not missing:
            return
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            for fn, url in missing:
                resp = client.get(url)
                resp.raise_for_status()
                with open(os.path.join(self.raw_dir, fn), "wb") as f:
                    f.write(resp.content)

    def _read_zip_by_unitid(self, filename: str) -> Dict[str, Dict[str, str]]:
        path = os.path.join(self.raw_dir, filename)
        by_id: Dict[str, Dict[str, str]] = {}
        with zipfile.ZipFile(path) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            with zf.open(csv_names[0]) as cf:
                reader = csv.DictReader(io.TextIOWrapper(cf, encoding="utf-8-sig", errors="replace"))
                for row in reader:
                    uid = _clean_str(row.get("UNITID"))
                    if uid:
                        by_id[uid] = row
        return by_id

    @staticmethod
    def _map_institution_type(sector: Optional[str], c21: Optional[str], instcat: Optional[str]) -> str:
        if c21 in ("21", "22"):
            return "liberal_arts_college"
        if sector in ("1", "2", "3"):
            return "university"
        if sector == "4":
            return "community_college"
        if sector == "5":
            return "community_college"
        if sector in ("6", "7", "8", "9"):
            return "technical_college"
        if instcat == "6":
            return "vocational"
        return "other"

    @staticmethod
    def _map_control(ctrl: Optional[str]) -> Optional[str]:
        return {"1": "public", "2": "private_nonprofit", "3": "private_forprofit"}.get(ctrl or "")

    def fetch_institutions(
        self,
        limit: Optional[int] = None,
        states: Optional[List[str]] = None,
        active_only: bool = True,
    ) -> List[NormalizedInstitution]:
        self._ensure_files()
        hd_rows = self._read_zip_by_unitid("HD2023.zip")
        ic_rows = self._read_zip_by_unitid("IC2023.zip")
        ay_rows = self._read_zip_by_unitid("IC2023_AY.zip")
        adm_rows = self._read_zip_by_unitid("ADM2023.zip")
        ef_rows = self._read_zip_by_unitid("DRVEF2023.zip")

        state_filter = {s.strip().upper() for s in states} if states else None
        results: List[NormalizedInstitution] = []

        for unitid, hd in hd_rows.items():
            if active_only and _clean_str(hd.get("CYACTIVE")) != "1":
                continue

            name = _clean_str(hd.get("INSTNM"))
            if not name:
                continue

            stabbr = (_clean_str(hd.get("STABBR")) or "").upper()
            if state_filter and stabbr not in state_filter:
                continue

            ic = ic_rows.get(unitid, {})
            ay = ay_rows.get(unitid, {})
            adm = adm_rows.get(unitid, {})
            ef = ef_rows.get(unitid, {})

            sector = _clean_str(hd.get("SECTOR"))
            c21 = _clean_str(hd.get("C21BASIC"))
            instcat = _clean_str(hd.get("INSTCAT"))
            inst_type = self._map_institution_type(sector, c21, instcat)
            control_type = self._map_control(_clean_str(hd.get("CONTROL")))
            carnegie_label = CARNEGIE_2021_LABELS.get(c21 or "")

            ope_raw = _clean_str(hd.get("OPEID"))
            ope6 = ope_raw[:6] if ope_raw and len(ope_raw) >= 6 else None

            # Alternative names from IALIAS
            alts = []
            ialias = _clean_str(hd.get("IALIAS"))
            if ialias:
                alts = [a.strip() for a in ialias.replace("|", ",").split(",") if a.strip() and a.strip() != name][:10]

            # Tuition & Cost components (AY 2023-2024)
            tuition_in = _clean_float(ay.get("TUITION2"))
            fee_in = _clean_float(ay.get("FEE2"))
            tuition_out = _clean_float(ay.get("TUITION3"))
            fee_out = _clean_float(ay.get("FEE3"))
            books = _clean_float(ay.get("CHG4AY3"))
            room_board = _clean_float(ay.get("CHG5AY3"))
            personal = _clean_float(ay.get("CHG6AY3"))

            in_state_total_tuition = (
                round(tuition_in + (fee_in or 0.0), 2) if tuition_in is not None else None
            )
            out_state_total_tuition = (
                round(tuition_out + (fee_out or 0.0), 2) if tuition_out is not None else None
            )

            costs: List[NormalizedCost] = []
            if tuition_in is not None:
                total_in = round(
                    tuition_in + (fee_in or 0.0) + (room_board or 0.0) + (books or 0.0) + (personal or 0.0),
                    2,
                )
                costs.append(NormalizedCost(
                    academic_year="2023-2024",
                    student_type="in_state",
                    degree_level="bachelors" if sector in ("1", "2", "3") else "associate",
                    tuition=tuition_in,
                    mandatory_fees=fee_in,
                    room_board=room_board,
                    books_supplies=books,
                    personal_expenses=personal,
                    total_estimated_cost=total_in,
                    currency="USD",
                    source_url=IPEDS_FILES["IC2023_AY.zip"],
                    verification_status="verified",
                ))
            if tuition_out is not None:
                total_out = round(
                    tuition_out + (fee_out or 0.0) + (room_board or 0.0) + (books or 0.0) + (personal or 0.0),
                    2,
                )
                costs.append(NormalizedCost(
                    academic_year="2023-2024",
                    student_type="out_of_state",
                    degree_level="bachelors" if sector in ("1", "2", "3") else "associate",
                    tuition=tuition_out,
                    mandatory_fees=fee_out,
                    room_board=room_board,
                    books_supplies=books,
                    personal_expenses=personal,
                    total_estimated_cost=total_out,
                    currency="USD",
                    source_url=IPEDS_FILES["IC2023_AY.zip"],
                    verification_status="verified",
                ))

            # Admissions & test scores
            applcn = _clean_float(adm.get("APPLCN"))
            admssn = _clean_float(adm.get("ADMSSN"))
            acceptance_rate = (
                round((admssn / applcn) * 100.0, 2)
                if applcn is not None and admssn is not None and applcn > 0
                else None
            )

            open_admp_code = _clean_str(ic.get("OPENADMP"))
            open_admissions = True if open_admp_code == "1" else (False if open_admp_code == "2" else None)
            calendar_system = CALENDAR_MAP.get(_clean_str(ic.get("CALSYS")) or "")
            app_fee = _clean_float(ic.get("APPLFEEU"))

            # Enrollment & demographics
            total_enr = _clean_int(ef.get("ENRTOT"))
            ug_enr = _clean_int(ef.get("EFUG"))
            grad_enr = _clean_int(ef.get("EFGRAD"))
            pct_intl = _clean_float(ef.get("PCTENRNR"))

            demographics: Dict[str, Any] = {}
            for col, label in [
                ("PCTENRWH", "white_pct"),
                ("PCTENRBK", "black_pct"),
                ("PCTENRHS", "hispanic_pct"),
                ("PCTENRAS", "asian_pct"),
                ("PCTENR2M", "two_or_more_pct"),
                ("PCTENRNR", "international_pct"),
            ]:
                v = _clean_float(ef.get(col))
                if v is not None:
                    demographics[label] = v

            results.append(NormalizedInstitution(
                official_name=name[:500],
                alternative_names=alts,
                country_code="US",
                country_name="United States",
                state_province=stabbr or None,
                city=_clean_str(hd.get("CITY")),
                postal_code=_clean_str(hd.get("ZIP")),
                latitude=_clean_float(hd.get("LATITUDE")),
                longitude=_clean_float(hd.get("LONGITUD")),
                institution_type=inst_type,
                control_type=control_type,
                carnegie_classification=carnegie_label,
                official_website=_clean_url(hd.get("WEBADDR")),
                admissions_website=_clean_url(hd.get("ADMINURL")),
                financial_aid_website=_clean_url(hd.get("FAIDURL")),
                application_portal_url=_clean_url(hd.get("APPLURL")),
                open_admissions=open_admissions,
                calendar_system=calendar_system,
                undergrad_application_fee=app_fee,
                total_enrollment=total_enr,
                undergraduate_enrollment=ug_enr,
                graduate_enrollment=grad_enr,
                acceptance_rate=acceptance_rate,
                sat_math_25=_clean_int(adm.get("SATMT25")),
                sat_math_75=_clean_int(adm.get("SATMT75")),
                sat_ebrw_25=_clean_int(adm.get("SATVR25")),
                sat_ebrw_75=_clean_int(adm.get("SATVR75")),
                act_composite_25=_clean_int(adm.get("ACTCM25")),
                act_composite_75=_clean_int(adm.get("ACTCM75")),
                pct_international=pct_intl,
                student_demographics=demographics,
                tuition_in_state=in_state_total_tuition,
                tuition_out_of_state=out_state_total_tuition,
                currency="USD",
                ipeds_unit_id=unitid,
                ope_id=ope_raw,
                ope6_id=ope6,
                external_ids={"ipeds_sector": sector, "ipeds_c21basic": c21} if sector else {},
                accepts_transfer=(inst_type != "community_college"),
                accepts_first_year=True,
                accepts_international=True,
                costs=costs,
                source_type="ipeds",
                source_name="NCES IPEDS 2023",
                source_url=IPEDS_FILES["HD2023.zip"],
                collection_method="bulk_csv",
                confidence_level="verified",
                academic_year="2023-2024",
            ))

            if limit and len(results) >= limit:
                break

        return results
