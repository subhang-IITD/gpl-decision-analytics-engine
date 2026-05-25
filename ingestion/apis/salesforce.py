"""Salesforce client for GPL historical sales (brief 3.2, 5.2).

READ-ONLY access to GPL's SFDC for historical project performance. Optionally
writes model outputs back as a custom object. Key-driven; without credentials,
the engine relies on CSV-uploaded historical data already in the warehouse.

SECURITY (brief 5.1): SFDC data is GPL-internal and must NEVER be forwarded to
any external LLM. This client only moves data between SFDC and GPL's warehouse.
"""
from __future__ import annotations

from config import get_settings


class SalesforceClient:
    def __init__(self) -> None:
        cfg = get_settings().keys
        self._token = cfg.salesforce_token
        self._instance = cfg.salesforce_instance_url

    @property
    def live(self) -> bool:
        return bool(self._token and self._instance)

    def query(self, soql: str) -> list[dict]:
        if not self.live:
            return []
        import requests

        resp = requests.get(
            f"{self._instance}/services/data/v60.0/query",
            headers={"Authorization": f"Bearer {self._token}"},
            params={"q": soql},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("records", [])

    def fetch_historical_sales(self) -> list[dict]:
        """Read GPL historical project performance (read-only)."""
        soql = (
            "SELECT Project_Name__c, Config_Type__c, Planned_Units__c, Sold_Units__c, "
            "Launch_Price_PSF__c, Realised_Price_PSF__c, Months_To_50pct__c, Phase__c "
            "FROM GPL_Project_Performance__c"
        )
        return self.query(soql)
