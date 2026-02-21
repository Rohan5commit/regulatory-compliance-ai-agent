from __future__ import annotations

import asyncio
from datetime import datetime
from functools import lru_cache

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from src.agents.mapping_agent import PolicyMappingAgent
from src.config import get_settings
from src.knowledge_graph.graph_manager import ComplianceKnowledgeGraph
from src.knowledge_graph.vector_store import ComplianceVectorStore
from src.models.database import (
    Base,
    ComplianceObligation,
    InternalPolicy,
    PolicyMapping,
    Regulation,
    RiskLevel,
    SessionLocal,
    engine,
)
from src.nlp.model_loader import ComplianceNLPModels
from src.schemas.api import MappingRequest, RegulationResponse, SearchRequest
from src.tasks.worker import process_new_regulations, scan_all_regulators

settings = get_settings()

app = FastAPI(
    title="Regulatory Compliance AI Agent",
    version="1.0.0",
    description="Autonomous system for financial regulatory compliance monitoring",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@lru_cache(maxsize=1)
def get_nlp_models() -> ComplianceNLPModels:
    return ComplianceNLPModels()


@lru_cache(maxsize=1)
def get_vector_store() -> ComplianceVectorStore | None:
    if not settings.enable_vector_search:
        return None
    try:
        return ComplianceVectorStore(settings.qdrant_host, int(settings.qdrant_port), get_nlp_models())
    except Exception as exc:
        logger.warning("Vector store unavailable: {}", exc)
        return None


@lru_cache(maxsize=1)
def get_knowledge_graph() -> ComplianceKnowledgeGraph | None:
    if not settings.enable_graph_search:
        return None
    try:
        return ComplianceKnowledgeGraph(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    except Exception as exc:
        logger.warning("Knowledge graph unavailable: {}", exc)
        return None


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/v1/admin/trigger-scan")
async def trigger_scan():
    task = scan_all_regulators.delay()
    return {"status": "queued", "task_id": task.id}


@app.post("/api/v1/admin/trigger-processing")
async def trigger_processing():
    task = process_new_regulations.delay()
    return {"status": "queued", "task_id": task.id}


@app.get("/api/v1/regulations", response_model=list[RegulationResponse])
async def list_regulations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    rows = (
        db.query(Regulation, func.count(ComplianceObligation.id).label("obligation_count"))
        .outerjoin(ComplianceObligation, ComplianceObligation.regulation_id == Regulation.id)
        .group_by(Regulation.id)
        .order_by(Regulation.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        RegulationResponse(
            id=reg.id,
            title=reg.title,
            regulator=reg.regulator.name if reg.regulator else "Unknown",
            effective_date=reg.effective_date,
            obligation_count=count,
        )
        for reg, count in rows
    ]


@app.get("/api/v1/obligations/unmapped")
async def get_unmapped_obligations(risk_level: str | None = None, db: Session = Depends(get_db)):
    query = db.query(ComplianceObligation).filter(~ComplianceObligation.mappings.any())

    if risk_level:
        try:
            query = query.filter(ComplianceObligation.risk_level == RiskLevel(risk_level.lower()))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid risk_level")

    obligations = query.order_by(ComplianceObligation.id.desc()).all()
    payload = [
        {
            "id": ob.id,
            "text": ob.obligation_text,
            "type": ob.obligation_type,
            "risk": ob.risk_level.value if ob.risk_level else "unknown",
        }
        for ob in obligations
    ]

    return {"unmapped_obligations": payload, "count": len(payload)}


@app.post("/api/v1/search/regulations")
async def search_regulations(request: SearchRequest):
    store = get_vector_store()
    if not store:
        raise HTTPException(status_code=503, detail="Vector search unavailable")

    return {"results": store.semantic_search(request.query, request.limit)}


@app.post("/api/v1/mapping/run")
async def run_policy_mapping(request: MappingRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    obligations = db.query(ComplianceObligation).filter(ComplianceObligation.id.in_(request.obligation_ids)).all()
    if not obligations:
        raise HTTPException(status_code=400, detail="No obligations found for requested IDs")

    if request.policy_ids:
        policies = db.query(InternalPolicy).filter(InternalPolicy.policy_id.in_(request.policy_ids)).all()
    else:
        policies = db.query(InternalPolicy).all()

    if not policies:
        raise HTTPException(status_code=400, detail="No internal policies available")

    background_tasks.add_task(_execute_mapping_job, [o.id for o in obligations], [p.id for p in policies])

    return {
        "status": "started",
        "obligation_count": len(obligations),
        "policy_count": len(policies),
    }


def _execute_mapping_job(obligation_ids: list[int], policy_db_ids: list[int]) -> None:
    db = SessionLocal()
    try:
        obligations = db.query(ComplianceObligation).filter(ComplianceObligation.id.in_(obligation_ids)).all()
        policies = db.query(InternalPolicy).filter(InternalPolicy.id.in_(policy_db_ids)).all()

        obligation_payload = [
            {
                "id": o.id,
                "obligation_text": o.obligation_text,
                "obligation_type": o.obligation_type,
                "risk_level": o.risk_level.value if o.risk_level else "medium",
            }
            for o in obligations
        ]

        policy_payload = [
            {
                "id": p.id,
                "policy_id": p.policy_id,
                "title": p.title,
                "description": p.description,
                "control_type": p.control_type,
            }
            for p in policies
        ]

        api_key = settings.anthropic_api_key if settings.mapping_provider == "anthropic" else settings.openai_api_key

        agent = PolicyMappingAgent(api_key=api_key, provider=settings.mapping_provider, model=settings.mapping_model)
        mappings = asyncio.run(agent.batch_map_obligations(obligation_payload, policy_payload))

        graph = get_knowledge_graph()
        for mapping in mappings:
            if mapping["coverage_status"] == "none":
                continue

            exists = (
                db.query(PolicyMapping)
                .filter(
                    PolicyMapping.obligation_id == mapping["obligation_id"],
                    PolicyMapping.policy_id == mapping["policy_db_id"],
                )
                .first()
            )
            if exists:
                continue

            row = PolicyMapping(
                obligation_id=mapping["obligation_id"],
                policy_id=mapping["policy_db_id"],
                mapping_confidence=mapping["mapping_confidence"],
                mapping_rationale=mapping["mapping_rationale"],
                coverage_status=mapping["coverage_status"],
                gap_description="; ".join(mapping.get("identified_gaps", [])) or None,
            )
            db.add(row)

            if graph:
                try:
                    graph.create_policy_mapping(
                        mapping["obligation_id"],
                        mapping["policy_ref"],
                        float(mapping["mapping_confidence"]),
                        mapping["mapping_rationale"],
                    )
                except Exception as exc:
                    logger.warning("Failed to mirror mapping to graph: {}", exc)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@app.get("/api/v1/dashboard/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    total_regulations = db.query(func.count(Regulation.id)).scalar() or 0
    total_obligations = db.query(func.count(ComplianceObligation.id)).scalar() or 0
    mapped_obligations = db.query(func.count(PolicyMapping.id)).scalar() or 0

    high_risk_unmapped = (
        db.query(func.count(ComplianceObligation.id))
        .filter(
            and_(
                ComplianceObligation.risk_level == RiskLevel.HIGH,
                ~ComplianceObligation.mappings.any(),
            )
        )
        .scalar()
        or 0
    )

    coverage = round((mapped_obligations / total_obligations) * 100, 2) if total_obligations else 0.0

    return {
        "total_regulations": total_regulations,
        "total_obligations": total_obligations,
        "mapped_obligations": mapped_obligations,
        "mapping_coverage": coverage,
        "high_risk_unmapped": high_risk_unmapped,
    }
