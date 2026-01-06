from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from mattersim_dt.core import SimConfig

# Base class for models
Base = declarative_base()

class DatabaseManager:
    _instance = None
    _engine = None
    _session_factory = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def init_db(self):
        """Initialize database connection and tables"""
        if not SimConfig.DB_URL:
             print("⚠️ DB_URL not set in config. Skipping DB initialization.")
             return

        if self._engine is None:
            try:
                self._engine = create_engine(SimConfig.DB_URL, echo=False)
                Base.metadata.create_all(self._engine)
                self._session_factory = scoped_session(sessionmaker(bind=self._engine))
                print("✅ Database connected and initialized.")
            except Exception as e:
                print(f"❌ Database connection failed: {e}")

    def get_session(self):
        """Get a new session"""
        if self._session_factory:
            return self._session_factory()
        return None

    def close(self):
        if self._engine:
            self._engine.dispose()

db_manager = DatabaseManager()
