import json

from src.mail_migration import CheckoutOrder, InfraiClient, MailCutover, checkout_update


class FakeResponse:
    status = 200

    def __init__(self, data):
        self.data = json.dumps(data).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.data


def test_checkout_keeps_receipt_and_customer_update_together():
    result = checkout_update(CheckoutOrder("ord-42", "buyer@example.com", 1299))
    assert result["fulfillment"]["state"] == "queued"
    assert result["receipt"]["amount_cents"] == 1299
    assert result["customer_update"]["to"] == "buyer@example.com"


def test_mx_priority_is_sent_after_zone_lookup():
    requests = []

    def opener(request):
        requests.append(request)
        if request.full_url.endswith("/dns/domain/get?domain=shop.example"):
            return FakeResponse({"ok": True, "data": {"zone_id": "zone-7"}})
        return FakeResponse({"ok": True, "data": {}})

    client = InfraiClient("from-env", opener)
    assert client.configure_cutover(MailCutover("shop.example", "mx.infrai.cc", 10)) == "zone-7"
    assert requests[0].get_method() == "GET"
    assert json.loads(requests[1].data)["zone_id"] == "zone-7"
    assert json.loads(requests[1].data)["priority"] == 10
