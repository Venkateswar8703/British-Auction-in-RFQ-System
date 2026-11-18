import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

logger = logging.getLogger("meridian.database")

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    warning_msg = (
        "⚠️  [DATABASE WARNING] Running on SQLite fallback (%s).\n"
        "Row-level locking (SELECT ... FOR UPDATE) is NOT enforced by SQLite.\n"
        "For production-grade ACID concurrency and row-level locking, use PostgreSQL 16 via DATABASE_URL."
        % settings.DATABASE_URL
    )
    print("\n" + "!" * 80 + "\n" + warning_msg + "\n" + "!" * 80 + "\n", flush=True)
    logger.warning(warning_msg)
    connect_args = {"check_same_thread": False, "timeout": 30}
else:
    logger.info("Connected to PostgreSQL database: %s", settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "configured")

engine_kwargs = {"echo": settings.ECHO_SQL, "pool_pre_ping": True}
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update({"pool_size": 30, "max_overflow": 20})

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs,
)

# Enable Foreign Key enforcement in SQLite
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

