from src.nlp.model_loader import ComplianceNLPModels
from src.nlp.obligation_extractor import ObligationExtractor


def test_extract_obligation_sentences():
    text = (
        "Firms must submit quarterly reports to the authority. "
        "They should maintain complete records for at least five years. "
        "This paragraph is descriptive only."
    )

    extractor = ObligationExtractor(ComplianceNLPModels())
    obligations = extractor.extract_obligations(text, regulation_id=1)

    assert len(obligations) >= 2
    assert any(o["obligation_type"] == "reporting" for o in obligations)
