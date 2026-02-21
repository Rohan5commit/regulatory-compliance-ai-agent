from __future__ import annotations

from src.models.database import Base, InternalPolicy, Regulator, RegulatorType, SessionLocal, engine

Base.metadata.create_all(bind=engine)


def upsert_regulator(db, **kwargs):
    existing = db.query(Regulator).filter(Regulator.name == kwargs["name"]).first()
    if existing:
        return existing
    row = Regulator(**kwargs)
    db.add(row)
    return row


def upsert_policy(db, **kwargs):
    existing = db.query(InternalPolicy).filter(InternalPolicy.policy_id == kwargs["policy_id"]).first()
    if existing:
        return existing
    row = InternalPolicy(**kwargs)
    db.add(row)
    return row


def main() -> None:
    db = SessionLocal()
    try:
        upsert_regulator(
            db,
            name="Securities and Exchange Commission",
            jurisdiction="US",
            regulator_type=RegulatorType.SEC,
            website_url="https://www.sec.gov",
            rss_feed_url="https://www.sec.gov/news/pressreleases.rss",
            active=True,
        )
        upsert_regulator(
            db,
            name="Financial Industry Regulatory Authority",
            jurisdiction="US",
            regulator_type=RegulatorType.FINRA,
            website_url="https://www.finra.org",
            active=True,
        )
        upsert_regulator(
            db,
            name="Monetary Authority of Singapore",
            jurisdiction="SG",
            regulator_type=RegulatorType.MAS,
            website_url="https://www.mas.gov.sg",
            active=True,
        )

        upsert_policy(
            db,
            policy_id="KYC-001",
            title="Customer Due Diligence Procedures",
            description="Procedures for verifying customer identity and assessing risk.",
            category="KYC/AML",
            owner="Compliance Department",
            control_type="preventive",
            automation_level="semi-automated",
        )
        upsert_policy(
            db,
            policy_id="RPT-001",
            title="Quarterly Regulatory Reporting",
            description="Process for preparing and submitting quarterly reports.",
            category="Reporting",
            owner="Finance Department",
            control_type="detective",
            automation_level="manual",
        )

        db.commit()
        print("Seeded regulators and policies")
    finally:
        db.close()


if __name__ == "__main__":
    main()
