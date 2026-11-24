"""
OpenAlex Institutions & ROR (Research Organization Registry) Connector.
Source License: CC0 1.0 Universal Public Domain Dedication.
Endpoint: https://api.openalex.org/institutions
"""

from typing import List, Optional, Dict, Any
import httpx
from app.ingestion.base import BaseInstitutionConnector, NormalizedInstitution


class OpenAlexRorConnector(BaseInstitutionConnector):
    source_name = "OpenAlex Institutions / ROR Registry"
    source_type = "openalex_ror"
    license_type = "CC0-1.0"

    BASE_URL = "https://api.openalex.org/institutions"

    def __init__(self, polite_email: str = "engineering@uniglobe.edu", timeout: float = 20.0):
        self.polite_email = polite_email
        self.timeout = timeout

    @staticmethod
    def parse_openalex_record(raw: Dict[str, Any]) -> Optional[NormalizedInstitution]:
        """Normalizes a single OpenAlex institution JSON object into a NormalizedInstitution DTO."""
        name = (raw.get("display_name") or "").strip()
        if not name:
            return None

        geo = raw.get("geo") or {}
        country_code = (raw.get("country_code") or geo.get("country_code") or "").strip().upper()
        if not country_code or len(country_code) != 2:
            return None

        ror_url = raw.get("ror")
        ror_id = ror_url.rstrip("/").split("/")[-1] if ror_url else None

        openalex_url = raw.get("id")
        openalex_id = openalex_url.rstrip("/").split("/")[-1] if openalex_url else None

        ids_obj = raw.get("ids") or {}
        external_ids: Dict[str, Any] = {}
        if ids_obj.get("wikidata"):
            external_ids["wikidata"] = ids_obj["wikidata"]
        if ids_obj.get("grid"):
            external_ids["grid"] = ids_obj["grid"]
        if ids_obj.get("wikipedia"):
            external_ids["wikipedia"] = ids_obj["wikipedia"]

        acronyms = raw.get("display_name_acronyms") or []
        alts = list(raw.get("display_name_alternatives") or [])
        # Include internationalized names if present
        intl_names = raw.get("international", {}).get("display_name") or {}
        for _, local_val in intl_names.items():
            if local_val and local_val != name:
                alts.append(local_val)
        alts = [a for a in dict.fromkeys(alts) if a and a != name][:20]

        abbreviation = acronyms[0][:50] if acronyms else None

        # Detect parent institution from associated_institutions
        parent_ror_id = None
        is_main_campus = True
        for assoc in raw.get("associated_institutions") or []:
            if assoc.get("relationship") == "parent" and assoc.get("ror"):
                parent_ror_id = assoc["ror"].rstrip("/").split("/")[-1]
                is_main_campus = False
                break

        # Determine institution_type conservatively
        lower_name = name.lower()
        if "community college" in lower_name:
            inst_type = "community_college"
        elif "technical" in lower_name or "polytechnic" in lower_name or "technologie" in lower_name:
            inst_type = "technical_college"
        elif not is_main_campus:
            inst_type = "branch_campus"
        else:
            inst_type = "university"

        return NormalizedInstitution(
            official_name=name[:500],
            alternative_names=alts,
            abbreviation=abbreviation,
            country_code=country_code,
            country_name=geo.get("country"),
            state_province=geo.get("region"),
            city=geo.get("city"),
            latitude=geo.get("latitude"),
            longitude=geo.get("longitude"),
            institution_type=inst_type,
            official_website=raw.get("homepage_url"),
            ror_id=ror_id,
            openalex_id=openalex_id,
            external_ids=external_ids,
            parent_ror_id=parent_ror_id,
            is_main_campus=is_main_campus,
            accepts_transfer=True,
            accepts_first_year=True,
            accepts_international=True,
            source_type="openalex_ror",
            source_name="OpenAlex Institutions / ROR Registry",
            source_url=openalex_url or ror_url or self.BASE_URL,
            collection_method="api",
            confidence_level="verified",
        )

    def fetch_institutions(
        self,
        country_codes: Optional[List[str]] = None,
        per_country: int = 10,
        global_limit: Optional[int] = None,
    ) -> List[NormalizedInstitution]:
        """
        Queries the OpenAlex CC0 Institutions API (`type:education`).
        If `country_codes` is specified, fetches top `per_country` institutions by scholarly/record presence per country.
        """
        results: List[NormalizedInstitution] = []
        headers = {
            "User-Agent": f"UniGlobeAdmissionsPlatform/0.4 (mailto:{self.polite_email})"
        }

        with httpx.Client(timeout=self.timeout, headers=headers) as client:
            if country_codes:
                for cc in country_codes:
                    cc_clean = cc.strip().upper()
                    resp = client.get(
                        self.BASE_URL,
                        params={
                            "filter": f"type:education,country_code:{cc_clean}",
                            "sort": "works_count:desc",
                            "per-page": min(per_country, 200),
                            "mailto": self.polite_email,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    for raw in data.get("results", []):
                        parsed = self.parse_openalex_record(raw)
                        if parsed:
                            results.append(parsed)
            else:
                limit = global_limit or 50
                resp = client.get(
                    self.BASE_URL,
                    params={
                        "filter": "type:education",
                        "sort": "works_count:desc",
                        "per-page": min(limit, 200),
                        "mailto": self.polite_email,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                for raw in data.get("results", []):
                    parsed = self.parse_openalex_record(raw)
                    if parsed:
                        results.append(parsed)

        return results
