from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase


class ComplianceKnowledgeGraph:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def add_regulation(self, regulation_data: dict[str, Any]) -> None:
        with self.driver.session() as session:
            session.execute_write(self._create_regulation_node, regulation_data)

    @staticmethod
    def _create_regulation_node(tx, data: dict[str, Any]):
        tx.run(
            """
            MERGE (r:Regulation {regulation_id: $regulation_id})
            SET r.title = $title,
                r.effective_date = $effective_date,
                r.document_type = $document_type,
                r.source_url = $source_url
            MERGE (g:Regulator {name: $regulator_name})
            MERGE (g)-[:ISSUED]->(r)
            """,
            **data,
        )

    def add_obligation(self, obligation_data: dict[str, Any]) -> None:
        with self.driver.session() as session:
            session.execute_write(self._create_obligation_node, obligation_data)

    @staticmethod
    def _create_obligation_node(tx, data: dict[str, Any]):
        tx.run(
            """
            MATCH (r:Regulation {regulation_id: $regulation_id})
            MERGE (o:Obligation {obligation_id: $obligation_id})
            SET o.text = $text,
                o.type = $obligation_type,
                o.risk_level = $risk_level,
                o.deadline_type = $deadline_type
            MERGE (r)-[:CONTAINS]->(o)
            """,
            **data,
        )

    def create_policy_mapping(self, obligation_id: int, policy_id: str, confidence: float, rationale: str) -> None:
        with self.driver.session() as session:
            session.execute_write(self._create_mapping_relationship, obligation_id, policy_id, confidence, rationale)

    @staticmethod
    def _create_mapping_relationship(tx, obligation_id: int, policy_id: str, confidence: float, rationale: str):
        tx.run(
            """
            MATCH (o:Obligation {obligation_id: $obligation_id})
            MERGE (p:Policy {policy_id: $policy_id})
            MERGE (o)-[m:MAPPED_TO]->(p)
            SET m.confidence = $confidence,
                m.rationale = $rationale,
                m.created_at = datetime()
            """,
            obligation_id=obligation_id,
            policy_id=policy_id,
            confidence=confidence,
            rationale=rationale,
        )

    def find_related_obligations(self, obligation_id: int, limit: int = 10) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            return session.execute_read(self._query_related_obligations, obligation_id, limit)

    @staticmethod
    def _query_related_obligations(tx, obligation_id: int, limit: int):
        result = tx.run(
            """
            MATCH (o:Obligation {obligation_id: $obligation_id})<-[:CONTAINS]-(r:Regulation)
            MATCH (r)-[:CONTAINS]->(related:Obligation)
            WHERE related.obligation_id <> $obligation_id
            RETURN related.obligation_id AS id, related.text AS text, related.type AS type
            LIMIT $limit
            """,
            obligation_id=obligation_id,
            limit=limit,
        )
        return [{"id": row["id"], "text": row["text"], "type": row["type"]} for row in result]

    def get_unmapped_obligations(self, risk_level: str | None = None) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            return session.execute_read(self._query_unmapped_obligations, risk_level)

    @staticmethod
    def _query_unmapped_obligations(tx, risk_level: str | None):
        if risk_level:
            query = (
                "MATCH (o:Obligation) "
                "WHERE NOT (o)-[:MAPPED_TO]->(:Policy) AND o.risk_level = $risk_level "
                "RETURN o.obligation_id AS id, o.text AS text, o.type AS type, o.risk_level AS risk"
            )
            rows = tx.run(query, risk_level=risk_level)
        else:
            query = (
                "MATCH (o:Obligation) "
                "WHERE NOT (o)-[:MAPPED_TO]->(:Policy) "
                "RETURN o.obligation_id AS id, o.text AS text, o.type AS type, o.risk_level AS risk"
            )
            rows = tx.run(query)

        return [{"id": r["id"], "text": r["text"], "type": r["type"], "risk": r["risk"]} for r in rows]

    def close(self):
        self.driver.close()
