from __future__ import annotations

from neo4j import GraphDatabase

from src.config import get_settings


class ComplianceGraphInitializer:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def create_constraints(self) -> None:
        with self.driver.session() as session:
            session.run(
                """
                CREATE CONSTRAINT regulation_id IF NOT EXISTS
                FOR (r:Regulation) REQUIRE r.regulation_id IS UNIQUE
                """
            )
            session.run(
                """
                CREATE CONSTRAINT obligation_id IF NOT EXISTS
                FOR (o:Obligation) REQUIRE o.obligation_id IS UNIQUE
                """
            )
            session.run(
                """
                CREATE CONSTRAINT policy_id IF NOT EXISTS
                FOR (p:Policy) REQUIRE p.policy_id IS UNIQUE
                """
            )
            session.run(
                """
                CREATE CONSTRAINT regulator_name IF NOT EXISTS
                FOR (r:Regulator) REQUIRE r.name IS UNIQUE
                """
            )

    def create_indexes(self) -> None:
        with self.driver.session() as session:
            session.run(
                """
                CREATE INDEX regulation_effective_date IF NOT EXISTS
                FOR (r:Regulation) ON (r.effective_date)
                """
            )
            session.run(
                """
                CREATE FULLTEXT INDEX obligation_text IF NOT EXISTS
                FOR (o:Obligation) ON EACH [o.text]
                """
            )

    def close(self) -> None:
        self.driver.close()


if __name__ == "__main__":
    settings = get_settings()
    initializer = ComplianceGraphInitializer(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    initializer.create_constraints()
    initializer.create_indexes()
    initializer.close()
    print("Neo4j schema initialized successfully")
