"""
Sample script to populate database with test data
"""

from src.database import DatabaseManager, Customer, Enrollment, Engagement, Feedback
from datetime import datetime, timedelta
import random

def create_sample_data():
    """Create sample data for testing"""
    db = DatabaseManager()
    db.init_db()
    
    session = db.get_session()
    
    # Sample customers
    customers_data = [
        {
            "name": "John Smith",
            "email": "john.smith@company1.com",
            "phone": "+1-555-0101",
            "company": "Tech Corp",
            "industry": "Technology"
        },
        {
            "name": "Sarah Johnson",
            "email": "sarah.johnson@company2.com",
            "phone": "+1-555-0102",
            "company": "Finance Inc",
            "industry": "Financial Services"
        },
        {
            "name": "Michael Chen",
            "email": "michael.chen@company3.com",
            "phone": "+1-555-0103",
            "company": "Healthcare Solutions",
            "industry": "Healthcare"
        },
    ]
    
    customers = []
    for data in customers_data:
        customer = Customer(
            name=data["name"],
            email=data["email"],
            phone=data["phone"],
            company=data["company"],
            industry=data["industry"],
            engagement_score=random.uniform(0.3, 0.9)
        )
        session.add(customer)
        customers.append(customer)
    
    session.commit()
    
    # Add enrollments
    products = ["Premium Suite", "Basic Plan", "Enterprise Package"]
    for customer in customers:
        for _ in range(random.randint(1, 3)):
            enrollment = Enrollment(
                customer_id=customer.id,
                product=random.choice(products),
                status=random.choice(["active", "inactive"]),
                tier=random.choice(["starter", "professional", "enterprise"])
            )
            session.add(enrollment)
    
    # Add engagements
    engagement_types = ["email_open", "feature_usage", "support_ticket", "webinar_attendance"]
    for customer in customers:
        for _ in range(random.randint(2, 5)):
            engagement = Engagement(
                customer_id=customer.id,
                engagement_type=random.choice(engagement_types),
                engagement_date=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
                value=random.uniform(10, 100)
            )
            session.add(engagement)
    
    # Add feedback
    sentiments = ["positive", "neutral", "negative"]
    categories = ["product_quality", "customer_service", "price", "features"]
    for customer in customers:
        for _ in range(random.randint(1, 3)):
            feedback = Feedback(
                customer_id=customer.id,
                feedback_text=f"Sample feedback from {customer.name}",
                sentiment=random.choice(sentiments),
                rating=random.randint(1, 5),
                category=random.choice(categories),
                feedback_date=datetime.utcnow() - timedelta(days=random.randint(0, 30))
            )
            session.add(feedback)
    
    session.commit()
    session.close()
    
    print("Sample data created successfully!")

if __name__ == "__main__":
    create_sample_data()
