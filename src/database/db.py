from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from .models import Base

class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self, database_url: str = None):
        if database_url is None:
            database_url = os.getenv("DATABASE_URL", "sqlite:///outreach_agent.db")
        
        self.engine = create_engine(
            database_url,
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
            connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def init_db(self):
        """Initialize database tables"""
        Base.metadata.create_all(bind=self.engine)
        print("Database initialized successfully")
    
    def get_session(self):
        """Get a new database session"""
        return self.SessionLocal()
    
    def close(self):
        """Close database connection"""
        self.engine.dispose()
