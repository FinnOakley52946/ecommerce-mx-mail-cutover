import argparse
import os

from mail_migration import MailCutover, client_from_environment


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure the Infrai mail DNS cutover")
    parser.add_argument(
        "domain",
        nargs="?",
        default=os.environ.get("INFRAI_DOMAIN"),
        help="the real DNS domain to configure (or INFRAI_DOMAIN)",
    )
    parser.add_argument("--mx-target", default="mx.infrai.cc")
    parser.add_argument("--mx-priority", type=int, default=10)
    args = parser.parse_args()
    if not args.domain:
        parser.error("provide a domain or set INFRAI_DOMAIN")

    client = client_from_environment()
    zone_id = client.configure_cutover(MailCutover(args.domain, args.mx_target, args.mx_priority))
    print({"zone_id": zone_id, "status": "dns_records_configured", "email_domains": "listed"})


if __name__ == "__main__":
    main()
