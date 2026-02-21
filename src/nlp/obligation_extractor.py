from __future__ import annotations

import re
from typing import Any

from loguru import logger

from src.models.database import RiskLevel


class ObligationExtractor:
    OBLIGATION_KEYWORDS = {
        "must",
        "shall",
        "required",
        "mandatory",
        "obligation",
        "duty",
        "prohibited",
        "forbidden",
        "comply",
        "ensure",
        "report",
        "disclose",
        "maintain",
        "establish",
        "implement",
        "provide",
        "submit",
    }

    def __init__(self, nlp_models):
        self.nlp_models = nlp_models
        self.spacy_nlp = self._load_spacy()
        logger.info("ObligationExtractor initialized")

    @staticmethod
    def _load_spacy():
        try:
            import spacy

            try:
                return spacy.load("en_core_web_lg")
            except Exception:
                nlp = spacy.blank("en")
                if "sentencizer" not in nlp.pipe_names:
                    nlp.add_pipe("sentencizer")
                return nlp
        except Exception:
            return None

    def extract_obligations(self, regulation_text: str, regulation_id: int) -> list[dict[str, Any]]:
        sentences = self._sentence_split(regulation_text)
        obligations: list[dict[str, Any]] = []

        for idx, sentence in enumerate(sentences):
            if not self._is_obligation_sentence(sentence):
                continue
            obligations.append(self._parse_obligation(sentence, regulation_id, idx))

        logger.info("Extracted {} obligations for regulation_id={}", len(obligations), regulation_id)
        return obligations

    def _sentence_split(self, text: str) -> list[str]:
        if not text:
            return []

        if self.spacy_nlp:
            doc = self.spacy_nlp(text)
            sents = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
            if sents:
                return sents

        return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

    def _is_obligation_sentence(self, sentence: str) -> bool:
        s = sentence.lower()
        if any(word in s for word in self.OBLIGATION_KEYWORDS):
            return True
        return bool(re.search(r"\b(no later than|within \d+|not later than|at least|by)\b", s))

    def _parse_obligation(self, sentence: str, regulation_id: int, sentence_idx: int) -> dict[str, Any]:
        obligation_type = self._classify_obligation_type(sentence)
        entities = self._extract_entities(sentence)
        temporal = self._extract_temporal_info(sentence)
        confidence = self._calculate_confidence(sentence)
        risk = self._assess_risk_level(sentence, obligation_type)

        return {
            "regulation_id": regulation_id,
            "obligation_text": sentence,
            "obligation_type": obligation_type,
            "confidence_score": confidence,
            "extracted_entities": entities,
            "deadline_type": temporal["deadline_type"],
            "deadline_date": temporal["deadline_date"],
            "is_recurring": temporal["is_recurring"],
            "risk_level": risk.value,
            "sentence_index": sentence_idx,
        }

    @staticmethod
    def _classify_obligation_type(sentence: str) -> str:
        s = sentence.lower()
        if any(w in s for w in ["report", "submit", "file", "disclose"]):
            return "reporting"
        if any(w in s for w in ["control", "procedure", "system", "process"]):
            return "control"
        if any(w in s for w in ["maintain", "retain", "preserve", "record"]):
            return "recordkeeping"
        if any(w in s for w in ["prohibit", "forbidden", "ban", "restrict"]):
            return "prohibition"
        if any(w in s for w in ["train", "educate", "inform"]):
            return "training"
        return "general"

    def _extract_entities(self, sentence: str) -> dict[str, list[str]]:
        entities = {"dates": [], "amounts": [], "organizations": [], "persons": []}

        if not self.spacy_nlp:
            return entities

        doc = self.spacy_nlp(sentence)
        for ent in getattr(doc, "ents", []):
            if ent.label_ == "DATE":
                entities["dates"].append(ent.text)
            elif ent.label_ in {"MONEY", "QUANTITY", "PERCENT"}:
                entities["amounts"].append(ent.text)
            elif ent.label_ == "ORG":
                entities["organizations"].append(ent.text)
            elif ent.label_ == "PERSON":
                entities["persons"].append(ent.text)
        return entities

    @staticmethod
    def _extract_temporal_info(sentence: str) -> dict[str, Any]:
        s = sentence.lower()
        temporal = {"deadline_type": None, "deadline_date": None, "is_recurring": False}

        if "annual" in s or "annually" in s:
            temporal["deadline_type"] = "annual"
            temporal["is_recurring"] = True
        elif "quarterly" in s:
            temporal["deadline_type"] = "quarterly"
            temporal["is_recurring"] = True
        elif "monthly" in s:
            temporal["deadline_type"] = "monthly"
            temporal["is_recurring"] = True

        match = re.search(r"within\s+(\d+)\s+(day|week|month|year)s?", s)
        if match:
            temporal["deadline_type"] = "specific"
            temporal["deadline_date"] = f"{match.group(1)} {match.group(2)}(s)"

        if any(w in s for w in ["by ", "before ", "no later than"]):
            temporal["deadline_type"] = temporal["deadline_type"] or "specific"

        return temporal

    @staticmethod
    def _calculate_confidence(sentence: str) -> float:
        score = 0.5
        s = sentence.lower()

        if any(w in s for w in ["must", "shall", "required"]):
            score += 0.3
        if any(w in s for w in ["should", "may", "recommend"]):
            score += 0.1
        if re.search(r"\d+\.\d+|\([a-z]\)|\(i{1,3}\)", sentence):
            score += 0.1

        wc = len(sentence.split())
        if 8 <= wc <= 60:
            score += 0.05

        return min(score, 1.0)

    @staticmethod
    def _assess_risk_level(sentence: str, obligation_type: str) -> RiskLevel:
        s = sentence.lower()
        if any(w in s for w in ["fraud", "laundering", "criminal", "penalty", "fine"]):
            return RiskLevel.CRITICAL
        if obligation_type in {"reporting", "prohibition"}:
            return RiskLevel.HIGH
        if obligation_type in {"control", "recordkeeping"}:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
