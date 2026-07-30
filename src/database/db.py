"""Database engine and session management."""

import logging
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import get_settings

from .models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database connection and session management"""

    def __init__(self, database_url: str = None, echo: bool = None):
        settings = get_settings()

        self.database_url = database_url or settings.database_url
        is_sqlite = self.database_url.startswith("sqlite")

        engine_kwargs = {
            "echo": settings.db_echo if echo is None else echo,
            "future": True,
        }
        if is_sqlite:
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            database_cfg = settings.section("database")
            engine_kwargs["pool_size"] = int(database_cfg.get("pool_size", 5))
            engine_kwargs["max_overflow"] = int(database_cfg.get("max_overflow", 10))
            engine_kwargs["pool_pre_ping"] = True

        self.engine = create_engine(self.database_url, **engine_kwargs)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine, expire_on_commit=False
        )

    def init_db(self):
        """Create any tables that do not exist yet."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database initialized (%s)", self.database_url)
        return True

    def drop_all(self):
        """Drop every table. Used by `seed_data.py --reset` and by tests."""
        Base.metadata.drop_all(bind=self.engine)
        logger.info("All tables dropped (%s)", self.database_url)
        return True

    def get_session(self):
        """Get a new database session."""
        return self.SessionLocal()

    @contextmanager
    def session_scope(self):
        """Transactional scope: commits on success, rolls back on error."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self):
        """Dispose of the connection pool."""
        self.engine.dispose()
