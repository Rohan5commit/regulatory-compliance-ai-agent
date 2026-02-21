from __future__ import annotations

import asyncio

from celery import Celery
from celery.schedules import crontab

from src.config import get_settings
from src.models.database import (
    ComplianceObligation,
    DocumentType,
    Regulation,
    Regulator,
    RegulatorType,
    RiskLevel,
    SessionLocal,
)
from src.nlp.model_loader import ComplianceNLPModels
from src.nlp.obligation_extractor import ObligationExtractor
from src.scrapers.regulator_scanner import MultiRegulatorScanner

settings = get_settings()

celery_app = Celery("compliance_tasks", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "scan-regulators": {
        "task": "src.tasks.worker.scan_all_regulators",
        "schedule": crontab(minute=0, hour=f"*/{max(1, settings.scraping_interval_hours)}"),
    },
    "process-new-regulations": {
        "task": "src.tasks.worker.process_new_regulations",
        "schedule": crontab(minute=0, hour=2),
    },
}


def _get_or_create_regulator(db, code: str) -> Regulator:
    existing = db.query(Regulator).filter(Regulator.regulator_type == RegulatorType[code]).first()
    if existing:
        return existing

    names = {
        "SEC": "Securities and Exchange Commission",
        "FINRA": "Financial Industry Regulatory Authority",
        "MAS": "Monetary Authority of Singapore",
        "FCA": "Financial Conduct Authority",
        "ECB": "European Central Bank",
    }

    reg = Regulator(
        name=names.get(code, code),
        jurisdiction={"SEC": "US", "FINRA": "US", "MAS": "SG", "FCA": "UK", "ECB": "EU"}.get(code, "Unknown"),
        regulator_type=RegulatorType[code],
        active=True,
    )
    db.add(reg)
    db.flush()
    return reg


@celery_app.task(name="src.tasks.worker.scan_all_regulators")
def scan_all_regulators() -> dict[str, int]:
    scanner = MultiRegulatorScanner({"SEC_EDGAR_USER_AGENT": settings.sec_edgar_user_agent})
    results = asyncio.run(scanner.scan_all_regulators(days_back=7))

    db = SessionLocal()
    new_count = 0
    try:
        for regulator_code, items in results.items():
            regulator = _get_or_create_regulator(db, regulator_code)

            for item in items:
                existing = db.query(Regulation).filter(Regulation.source_url == item.get("link")).first()
                if existing:
                    continue

                doc_type_value = str(item.get("document_type", "notice")).lower()
                if doc_type_value not in {"rule", "guidance", "notice", "amendment", "interpretation"}:
                    doc_type_value = "notice"

                regulation = Regulation(
                    regulator_id=regulator.id,
                    title=item.get("title") or "Untitled",
                    source_url=item.get("link"),
                    summary=item.get("summary"),
                    publication_date=item.get("published"),
                    document_type=DocumentType(doc_type_value),
                )
                db.add(regulation)
                new_count += 1

        db.commit()
        return {"new_regulations": new_count}
    finally:
        db.close()


@celery_app.task(name="src.tasks.worker.process_new_regulations")
def process_new_regulations(batch_size: int = 10) -> dict[str, int]:
    db = SessionLocal()
    extracted_count = 0

    try:
        unprocessed = (
            db.query(Regulation)
            .filter(~Regulation.obligations.any())
            .order_by(Regulation.id.asc())
            .limit(batch_size)
            .all()
        )

        if not unprocessed:
            return {"processed_regulations": 0, "extracted_obligations": 0}

        nlp_models = ComplianceNLPModels()
        extractor = ObligationExtractor(nlp_models)

        for regulation in unprocessed:
            if not regulation.full_text:
                continue

            obligations = extractor.extract_obligations(regulation.full_text, regulation.id)
            for data in obligations:
                risk_level = data.get("risk_level", "medium").upper()
                obligation = ComplianceObligation(
                    regulation_id=regulation.id,
                    obligation_text=data["obligation_text"],
                    obligation_type=data.get("obligation_type", "general"),
                    confidence_score=data.get("confidence_score"),
                    extracted_entities=data.get("extracted_entities", {}),
                    deadline_type=data.get("deadline_type"),
                    deadline_date=data.get("deadline_date"),
                    is_recurring=bool(data.get("is_recurring")),
                    risk_level=RiskLevel[risk_level] if risk_level in RiskLevel.__members__ else RiskLevel.MEDIUM,
                )
                db.add(obligation)
                extracted_count += 1

        db.commit()
        return {"processed_regulations": len(unprocessed), "extracted_obligations": extracted_count}
    finally:
        db.close()
