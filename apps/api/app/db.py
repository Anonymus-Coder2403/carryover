from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
Base = declarative_base()


def init_db():
    from . import models  # noqa: F401  ensure models are registered before create_all
    Base.metadata.create_all(engine)
