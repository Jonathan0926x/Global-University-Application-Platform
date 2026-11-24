"""
ASSIST.org Official Statewide Articulation API Connector (EULA-Compliant).

Requires an authorized ASSIST API key (`ASSIST_API_KEY` environment variable issued via help@assist.org).
Refuses to scrape restricted web endpoints when unconfigured.
"""

import os
from typing import Any, Dict, List, Optional
import urllib.request
import json


class AssistOrgConnector:
    BASE_URL = "https://assist.org/api"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ASSIST_API_KEY")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def fetch_agreements(self, sending_institution_id: int, receiving_institution_id: int, academic_year_id: int) -> List[Dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError(
                "ASSIST_API_KEY is not configured. Official programmatic ASSIST access requires an approved "
                "API-Key from help@assist.org under the ASSIST End User License Agreement (EULA)."
            )

        url = (
            f"{self.BASE_URL}/articulation/Agreements"
            f"?Key={academic_year_id}/{sending_institution_id}/to/{receiving_institution_id}/AllMajors"
        )
        req = urllib.request.Request(
            url,
            headers={
                "API-Key": self.api_key,
                "ASSIST-Common-Response": "true",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if not payload.get("isSuccessful", True):
            raise RuntimeError(f"ASSIST API error: {payload.get('validationFailure')}")
        return payload.get("result") or []
