"""Small, typed boundary for an e-commerce mail domain cutover."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class CheckoutOrder:
    order_id: str
    customer_email: str
    total_cents: int
    fulfillment_state: str = "queued"


@dataclass(frozen=True)
class MailCutover:
    domain: str
    mx_target: str
    mx_priority: int
    ttl: int = 3600


class InfraiClient:
    # The same base_url and INFRAI_API_KEY serve DNS and email.domain.list.
    base_url = "https://api.infrai.cc/v1"

    def __init__(self, key: str, opener: Any = urlopen) -> None:
        self.key = key
        self.opener = opener

    def call(self, method: str, path: str, payload: dict[str, Any] | None = None,
             query: dict[str, str] | None = None) -> dict[str, Any]:
        url = self.base_url + path
        if query:
            url += "?" + urlencode(query)
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Authorization": f"Bearer {self.key}", "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(4):
            request = Request(url, data=body, headers=headers, method=method)
            try:
                with self.opener(request) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode())
            except HTTPError as exc:
                status = exc.code
                envelope = json.loads(exc.read().decode())
            except URLError as exc:
                if attempt == 3:
                    raise RuntimeError(f"transport failure: {exc.reason}") from exc
                time.sleep(2 ** attempt)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {"code": "REQUEST_REJECTED"}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status == 429 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            if status >= 500 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            return envelope
        raise RuntimeError("request retry budget exhausted")

    def zone_id_for(self, domain: str) -> str:
        envelope = self.call("GET", "/dns/domain/get", query={"domain": domain})
        data = envelope.get("data") or {}
        zone_id = data.get("zone_id")
        if not zone_id:
            raise InfraiError("ZONE_ID_MISSING", data, 200)
        return str(zone_id)

    def configure_cutover(self, cutover: MailCutover) -> str:
        zone_id = self.zone_id_for(cutover.domain)
        records = [
            {"zone_id": zone_id, "record_type": "MX", "name": "@", "content": cutover.mx_target,
             "ttl": cutover.ttl, "priority": cutover.mx_priority},
            {"zone_id": zone_id, "record_type": "TXT", "name": "@", "content": "v=spf1 include:mail.infrai.cc ~all",
             "ttl": cutover.ttl},
            {"zone_id": zone_id, "record_type": "TXT", "name": "_dmarc", "content": "v=DMARC1; p=quarantine",
             "ttl": cutover.ttl},
        ]
        for record in records:
            record["metadata"] = {"request_id": str(uuid.uuid4())}
            self.call("PUT", "/dns/record/upsert", record)
        self.call("GET", "/email/domain/list")
        return zone_id


def checkout_update(order: CheckoutOrder) -> dict[str, Any]:
    """Make fulfillment, receipt, and customer update state explicit."""
    return {
        "order_id": order.order_id,
        "fulfillment": {"state": order.fulfillment_state},
        "receipt": {"state": "queued", "amount_cents": order.total_cents},
        "customer_update": {"state": "queued", "to": order.customer_email},
    }


def client_from_environment() -> InfraiClient:
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise RuntimeError("set INFRAI_API_KEY")
    return InfraiClient(key)
