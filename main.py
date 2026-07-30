"""Command line entry point for the AI Outreach Agent."""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import get_settings  # noqa: E402
from src.database import DatabaseManager, OutreachRepository  # noqa: E402
from src.orchestrator import OutreachOrchestrator  # noqa: E402
from src.utils import setup_logging  # noqa: E402

logger = logging.getLogger(__name__)


def _parse_customer_ids(raw: str) -> list:
    """Parse a comma separated list of customer ids."""
    if not raw:
        return []
    ids = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.append(int(chunk))
        except ValueError:
            raise SystemExit(f"Invalid customer id: {chunk!r}")
    return ids


def command_run(args) -> int:
    """Execute an outreach campaign."""
    orchestrator = OutreachOrchestrator()
    try:
        customer_ids = _parse_customer_ids(args.customers)
        if not customer_ids:
            customer_ids = orchestrator.repository.customer_ids(limit=args.limit)

        results = orchestrator.execute_outreach_workflow(customer_ids, campaign_name=args.campaign)
        if not results:
            print("No campaign was executed. Seed the database with: python main.py seed")
            return 1

        print("\nOutreach campaign completed")
        print(f"  Campaign:        {results['campaign_name']} (id {results['campaign_id']})")
        print(f"  Customers:       {results['total_customers']}")
        print(f"  Successful calls:{results['successful_calls']:>4}")
        print(f"  Failed calls:    {results['failed_calls']:>4}")
        print(f"  Emails sent:     {results['emails_sent']:>4}")

        for interaction in results["interactions"]:
            print(
                f"    - {interaction['customer_name']}: "
                f"score={interaction['success_score']} "
                f"sentiment={interaction['sentiment']} "
                f"next={interaction['next_action']}"
            )

        summary = orchestrator.get_performance_summary(days=args.days)
        if summary:
            print(f"\nPerformance summary (last {summary['period_days']} days)")
            print(f"  Overall success rate:  {summary['overall_success_rate']}%")
            print(f"  Avg satisfaction:      {summary['avg_customer_satisfaction']}/5.0")
        return 0
    finally:
        orchestrator.close()


def command_seed(args) -> int:
    """Populate the database with sample data."""
    from scripts.seed_data import create_sample_data

    create_sample_data(reset=args.reset, customers=args.customers)
    return 0


def command_init_db(args) -> int:
    """Create the database schema."""
    db = DatabaseManager()
    db.init_db()
    print(f"Database initialized at {db.database_url}")
    db.close()
    return 0


def command_customers(args) -> int:
    """List the customers currently stored."""
    db = DatabaseManager()
    db.init_db()
    try:
        rows = OutreachRepository(db).list_customers(limit=args.limit)
        if not rows:
            print("No customers found. Run: python main.py seed")
            return 1
        print(f"{'ID':>4}  {'NAME':<22} {'COMPANY':<22} {'SCORE':>6}  EMAIL")
        for row in rows:
            print(
                f"{row['id']:>4}  {(row['name'] or ''):<22.22} "
                f"{(row['company'] or ''):<22.22} {row['engagement_score']:>6.2f}  {row['email']}"
            )
        return 0
    finally:
        db.close()


def command_report(args) -> int:
    """Show campaign metrics or a rolling performance summary."""
    db = DatabaseManager()
    db.init_db()
    try:
        from src.utils import AnalyticsManager

        analytics = AnalyticsManager(db)
        if args.campaign:
            metrics = analytics.get_campaign_metrics(args.campaign)
            if not metrics:
                print(f"Campaign {args.campaign} not found")
                return 1
            for key, value in metrics.items():
                print(f"  {key}: {value}")
            return 0

        summary = analytics.get_performance_summary(days=args.days)
        if not summary:
            print(f"No metrics recorded in the last {args.days} days")
            return 1
        for key, value in summary.items():
            print(f"  {key}: {value}")
        return 0
    finally:
        db.close()


def command_authorize_gmail(args) -> int:
    """Run the Gmail OAuth consent flow once and cache the token."""
    from src.integrations import GmailIntegration

    settings = get_settings()
    if not settings.google_credentials_path:
        print("Set GOOGLE_APPLICATION_CREDENTIALS in .env first")
        return 1

    gmail = GmailIntegration(interactive=True)
    if gmail.live:
        print(f"Gmail authorized. Token stored at {settings.gmail_token_path}")
        return 0
    print("Gmail authorization failed. Check the logs for details.")
    return 1


def command_config(args) -> int:
    """Show the resolved configuration and which integrations are live."""
    settings = get_settings()
    print(f"  config file:   {settings.config_path}")
    print(f"  database:      {settings.database_url}")
    print(f"  log level:     {settings.log_level}")
    print(f"  dry run:       {settings.dry_run}")
    print(f"  openai model:  {settings.openai_model}")
    missing = settings.missing_credentials()
    print(f"  configured:    {', '.join(sorted({'openai','elevenlabs','twilio','gmail'} - set(missing))) or 'none'}")
    print(f"  simulated:     {', '.join(missing) or 'none'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py", description="AI Outreach Agent - multi-agent customer outreach"
    )
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="execute an outreach campaign")
    run.add_argument("--customers", help="comma separated customer ids (default: all active)")
    run.add_argument("--campaign", help="campaign name")
    run.add_argument("--limit", type=int, help="max customers to contact")
    run.add_argument("--days", type=int, default=30, help="performance summary window")
    run.set_defaults(func=command_run)

    seed = subparsers.add_parser("seed", help="populate the database with sample data")
    seed.add_argument("--reset", action="store_true", help="drop existing tables first")
    seed.add_argument("--customers", type=int, default=5, help="number of sample customers")
    seed.set_defaults(func=command_seed)

    init = subparsers.add_parser("init-db", help="create the database schema")
    init.set_defaults(func=command_init_db)

    customers = subparsers.add_parser("customers", help="list stored customers")
    customers.add_argument("--limit", type=int, help="max rows to show")
    customers.set_defaults(func=command_customers)

    report = subparsers.add_parser("report", help="show campaign or period metrics")
    report.add_argument("--campaign", type=int, help="campaign id")
    report.add_argument("--days", type=int, default=30, help="summary window in days")
    report.set_defaults(func=command_report)

    authorize = subparsers.add_parser("authorize-gmail", help="run the Gmail OAuth flow once")
    authorize.set_defaults(func=command_authorize_gmail)

    config = subparsers.add_parser("config", help="show the resolved configuration")
    config.set_defaults(func=command_config)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    setup_logging()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130
    except Exception as exc:
        logger.error("Command failed: %s", exc, exc_info=True)
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
