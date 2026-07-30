"""Populate the database with realistic sample data.

Run directly (``python scripts/seed_data.py``) or through the CLI
(``python main.py seed --reset``).
"""

import argparse
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Allow running this file directly from the scripts/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import (  # noqa: E402
    Customer,
    DatabaseManager,
    Engagement,
    Enrollment,
    Feedback,
)

SAMPLE_CUSTOMERS = [
    ("John Smith", "john.smith@techcorp.example", "+15550100", "Tech Corp", "Technology"),
    ("Sarah Johnson", "sarah.johnson@financeinc.example", "+15550101", "Finance Inc", "Financial Services"),
    ("Michael Chen", "michael.chen@healthsol.example", "+15550102", "Healthcare Solutions", "Healthcare"),
    ("Priya Nair", "priya.nair@retailhub.example", "+15550103", "Retail Hub", "Retail"),
    ("David Okafor", "david.okafor@buildwell.example", "+15550104", "BuildWell", "Construction"),
    ("Elena Rossi", "elena.rossi@edulearn.example", "+15550105", "EduLearn", "Education"),
    ("Tom Weber", "tom.weber@logipro.example", "+15550106", "LogiPro", "Logistics"),
    ("Aisha Khan", "aisha.khan@medtrack.example", "+15550107", "MedTrack", "Healthcare"),
]

PRODUCTS = ["Premium Suite", "Basic Plan", "Enterprise Package", "Analytics Add-on"]
ENGAGEMENT_TYPES = ["email_open", "feature_usage", "support_ticket", "webinar_attendance"]
FEEDBACK_BY_SENTIMENT = {
    "positive": [
        "The onboarding was smooth and the team is already seeing value.",
        "Support has been responsive and the reporting is excellent.",
    ],
    "neutral": [
        "The product works as expected, nothing to flag right now.",
        "Still evaluating how much of the suite we will use.",
    ],
    "negative": [
        "Pricing feels high compared to what we currently use.",
        "Integration took longer than we planned and slowed the rollout.",
    ],
}


def create_sample_data(reset: bool = False, customers: int = 5, seed: int = 42) -> int:
    """Create sample customers with enrollments, engagements and feedback.

    Existing customers are matched by email and left untouched, so the script
    is safe to run repeatedly. Returns the number of customers created.
    """
    random.seed(seed)

    db = DatabaseManager()
    if reset:
        db.drop_all()
    db.init_db()

    requested = SAMPLE_CUSTOMERS[: max(1, min(customers, len(SAMPLE_CUSTOMERS)))]
    created = 0

    with db.session_scope() as session:
        existing_emails = {email for (email,) in session.query(Customer.email).all()}

        for name, email, phone, company, industry in requested:
            if email in existing_emails:
                continue

            customer = Customer(
                name=name,
                email=email,
                phone=phone,
                company=company,
                industry=industry,
                engagement_score=round(random.uniform(0.3, 0.95), 2),
            )
            session.add(customer)
            session.flush()  # assign customer.id before adding related rows
            created += 1

            for product in random.sample(PRODUCTS, random.randint(1, 3)):
                session.add(
                    Enrollment(
                        customer_id=customer.id,
                        product=product,
                        enrollment_date=datetime.utcnow() - timedelta(days=random.randint(30, 400)),
                        status=random.choice(["active", "active", "inactive"]),
                        tier=random.choice(["starter", "professional", "enterprise"]),
                    )
                )

            for _ in range(random.randint(2, 6)):
                session.add(
                    Engagement(
                        customer_id=customer.id,
                        engagement_type=random.choice(ENGAGEMENT_TYPES),
                        engagement_date=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
                        value=round(random.uniform(10, 100), 2),
                    )
                )

            for _ in range(random.randint(1, 3)):
                sentiment = random.choice(list(FEEDBACK_BY_SENTIMENT))
                session.add(
                    Feedback(
                        customer_id=customer.id,
                        feedback_text=random.choice(FEEDBACK_BY_SENTIMENT[sentiment]),
                        sentiment=sentiment,
                        rating={"positive": 5, "neutral": 3, "negative": 2}[sentiment],
                        category=random.choice(
                            ["product_quality", "customer_service", "price", "features"]
                        ),
                        feedback_date=datetime.utcnow() - timedelta(days=random.randint(0, 60)),
                    )
                )

    total = created if created else 0
    print(f"Sample data ready: {total} customer(s) created, database at {db.database_url}")
    db.close()
    return total


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Seed the outreach database with sample data")
    parser.add_argument("--reset", action="store_true", help="drop existing tables first")
    parser.add_argument("--customers", type=int, default=5, help="number of sample customers")
    args = parser.parse_args(argv)

    create_sample_data(reset=args.reset, customers=args.customers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
