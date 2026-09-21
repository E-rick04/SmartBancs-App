from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Account


@pytest.fixture
def api_environment():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory.begin() as db:
        db.add_all([
            Account(account_number="CUEN_001", currency="USD", balance=Decimal("1000.00")),
            Account(account_number="CUEN_002", currency="USD", balance=Decimal("500.00")),
        ])

    def test_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as client:
            yield client, session_factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
