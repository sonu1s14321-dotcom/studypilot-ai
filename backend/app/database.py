from collections.abc import Generator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

class Settings(BaseSettings):
    database_url: str = "sqlite:///./studyplanner.db"
    jwt_secret: str = "development-only-change-me"
    jwt_expire_minutes: int = 10080
    frontend_origins: str = "http://localhost:5173"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.7-flash"
    openalex_api_key: str = ""
    open_library_contact_email: str = ""
    app_user_agent: str = "StudyPilotAI/1.0"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

def normalized_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url

database_url = normalized_database_url(settings.database_url)
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)

class Base(DeclarativeBase):
    pass

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
