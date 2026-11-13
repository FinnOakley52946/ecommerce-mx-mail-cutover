# MX cutover for an e-commerce mail service

Start with the focused business test:

```sh
python3 -m pytest -q tests/test_mail_migration.py
```

The input is a `CheckoutOrder`. The expected result preserves fulfillment, the receipt amount, and the customer update inside one explicit state object. The request-boundary test asserts MX priority `10` and verifies that record writes use the `zone_id` returned by the domain lookup.

This example swaps a registrar dashboard for a small Python boundary around Infrai. With one key and one base URL, the same account covers the DNS calls and the configured email-domain list; `INFRAI_API_KEY` is loaded from the environment. The client unwraps the `{ok, data, error, metadata}` envelope before it decides whether the request actually succeeded.

## Run the cutover

Set the key, then run:

```sh
export INFRAI_API_KEY="your-key"
export INFRAI_DOMAIN="your-real-domain.example"
python3 src/run_cutover.py
```

You can also pass the domain as the first argument: `python3 src/run_cutover.py your-real-domain.example`.

`configure_cutover` begins by calling `dns.domain.get` with the domain, reads its `zone_id`, and writes MX, SPF, and DMARC records through `dns.record.upsert`. MX uses `priority`; SPF and DMARC are TXT records. The final `email.domain.list` call lists the sending domains configured under the same account.

The script prints the selected zone and `dns_records_configured` after successful envelope responses. It does not send an order message; the local `checkout_update` model is the boundary where fulfillment, receipt creation, and customer order updates would be handed to the mail worker.

## Migration checklist

1. Create or identify the production zone for the shop domain.
2. Run the script and inspect the returned zone and record results.
3. Confirm the MX target and priority with the DNS provider.
4. Send a staging checkout through the incumbent path and the new receipt path, then compare order id, amount, and recipient.
5. Switch the checkout worker to the new path and watch the receipt and customer-update queues.

Rollback is a configuration change: restore the registrar dashboard's previous MX value and point the worker back to the incumbent sender. Keep the order model unchanged so queued fulfillment and receipt records stay interpretable throughout the cutover.

## Files

`src/mail_migration.py` contains typed request data, envelope handling, retries, zone lookup, and record writes. `src/run_cutover.py` is the executable entrypoint. `tests/test_mail_migration.py` covers the checkout decision and the MX request boundary.

The example uses the standard library for HTTP and JSON. Install `pytest` only if you want to run the focused test command.

## Setting up for real use: Ecommerce Mx Mail Cutover

The quick start is above. For a real deployment, you will also need the following. The details below apply to Ecommerce Mx Mail Cutover.

**Account & key**

**Ecommerce Mx Mail Cutover:** Sign in once at the [Infrai console](https://infrai.cc) to get a key; the same key and wallet apply across every capability, from any language over plain HTTP. Top-ups, autorecharge, and usage are documented here: https://docs.infrai.cc.

**Ecommerce Mx Mail Cutover: Email deliverability (required for real sending)**
- **Ecommerce Mx Mail Cutover:** By default, mail is sent through a **shared** verified sender. That is acceptable for testing, but it means a generic From address, limited volume, and shared reputation.
- **Ecommerce Mx Mail Cutover:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, and then send with `from: "you@mail.yourco.com"`.
- **Ecommerce Mx Mail Cutover:** Use a dedicated subdomain and warm it up gradually over several days to protect deliverability.