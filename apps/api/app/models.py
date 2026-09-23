from sqlalchemy import Column, DateTime, String, JSON, func

from .db import Base


class Capsule(Base):
    __tablename__ = "capsules"

    id = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)
    emb = Column(JSON, nullable=True)
    owner = Column(String, nullable=True, index=True)
    parent = Column(String, nullable=True)
    created = Column(DateTime(timezone=True), server_default=func.now())
