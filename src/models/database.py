from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from src.config import get_settings

Base = declarative_base()


class RegulatorType(enum.Enum):
    SEC = "SEC"
    FINRA = "FINRA"
    FCA = "FCA"
    MAS = "MAS"
    ECB = "ECB"
    ESMA = "ESMA"
    CFTC = "CFTC"
    OCC = "OCC"
    OSFI = "OSFI"


class DocumentType(enum.Enum):
    RULE = "rule"
    GUIDANCE = "guidance"
    NOTICE = "notice"
    AMENDMENT = "amendment"
    INTERPRETATION = "interpretation"


class RiskLevel(enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Regulator(Base):
    __tablename__ = "regulators"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    jurisdiction = Column(String(50))
    regulator_type = Column(SqlEnum(RegulatorType))
    website_url = Column(String(500))
    rss_feed_url = Column(String(500))
    api_endpoint = Column(String(500))
    last_scraped = Column(DateTime)
    active = Column(Boolean, default=True)

    regulations = relationship("Regulation", back_populates="regulator")


class Regulation(Base):
    __tablename__ = "regulations"

    id = Column(Integer, primary_key=True)
    regulator_id = Column(Integer, ForeignKey("regulators.id"), nullable=True)

    regulation_number = Column(String(100))
    title = Column(Text, nullable=False)
    document_type = Column(SqlEnum(DocumentType), default=DocumentType.NOTICE)
    effective_date = Column(DateTime)
    publication_date = Column(DateTime)

    full_text = Column(Text)
    summary = Column(Text)
    source_url = Column(String(500), unique=True)
    pdf_url = Column(String(500))

    embedding_id = Column(String(100))

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    regulator = relationship("Regulator", back_populates="regulations")
    obligations = relationship("ComplianceObligation", back_populates="regulation")


class ComplianceObligation(Base):
    __tablename__ = "compliance_obligations"

    id = Column(Integer, primary_key=True)
    regulation_id = Column(Integer, ForeignKey("regulations.id"), nullable=False)

    obligation_text = Column(Text, nullable=False)
    obligation_type = Column(String(50), default="general")

    confidence_score = Column(Float)
    extracted_entities = Column(JSON)

    deadline_type = Column(String(50))
    deadline_date = Column(String(100))
    is_recurring = Column(Boolean, default=False)

    risk_level = Column(SqlEnum(RiskLevel), default=RiskLevel.MEDIUM)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    regulation = relationship("Regulation", back_populates="obligations")
    mappings = relationship("PolicyMapping", back_populates="obligation")


class InternalPolicy(Base):
    __tablename__ = "internal_policies"

    id = Column(Integer, primary_key=True)
    policy_id = Column(String(100), unique=True, nullable=False)

    title = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(100))

    owner = Column(String(100))
    last_reviewed = Column(DateTime)
    next_review_date = Column(DateTime)

    control_type = Column(String(50))
    automation_level = Column(String(50))

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    mappings = relationship("PolicyMapping", back_populates="policy")


class PolicyMapping(Base):
    __tablename__ = "policy_mappings"

    id = Column(Integer, primary_key=True)
    obligation_id = Column(Integer, ForeignKey("compliance_obligations.id"), nullable=False)
    policy_id = Column(Integer, ForeignKey("internal_policies.id"), nullable=False)

    mapping_confidence = Column(Float)
    mapping_rationale = Column(Text)

    coverage_status = Column(String(50))
    gap_description = Column(Text)

    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    obligation = relationship("ComplianceObligation", back_populates="mappings")
    policy = relationship("InternalPolicy", back_populates="mappings")


class ComplianceGap(Base):
    __tablename__ = "compliance_gaps"

    id = Column(Integer, primary_key=True)
    obligation_id = Column(Integer, ForeignKey("compliance_obligations.id"), nullable=False)

    gap_type = Column(String(50))
    severity = Column(SqlEnum(RiskLevel), default=RiskLevel.MEDIUM)

    description = Column(Text)
    recommended_action = Column(Text)

    status = Column(String(50), default="open")
    assigned_to = Column(String(100))
    due_date = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)

    event_type = Column(String(100))
    entity_type = Column(String(50))
    entity_id = Column(Integer)

    user = Column(String(100))
    action = Column(String(200))

    before_state = Column(JSON)
    after_state = Column(JSON)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


def _create_engine():
    settings = get_settings()
    db_url = settings.sqlalchemy_database_url
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    return create_engine(db_url, pool_pre_ping=True, future=True, connect_args=connect_args)


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
