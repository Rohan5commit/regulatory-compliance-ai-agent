from __future__ import annotations

import hashlib

import numpy as np
from loguru import logger


class ComplianceNLPModels:
    """Lazy model manager with free fallback embeddings when model downloads are unavailable."""

    VECTOR_SIZE = 384

    def __init__(self):
        self.device = "cpu"
        self.legal_tokenizer = None
        self.legal_model = None
        self.fin_tokenizer = None
        self.fin_model = None
        self.sentence_model = None

        try:
            import torch

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            self.device = "cpu"

        logger.info("NLP model manager initialized on device={}", self.device)

    def _load_sentence_model(self) -> None:
        if self.sentence_model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer

            self.sentence_model = SentenceTransformer("all-MiniLM-L6-v2", device=self.device)
            logger.info("Loaded sentence-transformer all-MiniLM-L6-v2")
        except Exception as exc:
            logger.warning("Sentence model unavailable, using deterministic fallback embeddings: {}", exc)
            self.sentence_model = False

    def _load_transformers(self) -> None:
        if self.legal_model is not None and self.fin_model is not None:
            return

        try:
            from transformers import AutoModel, AutoTokenizer

            self.legal_tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
            self.legal_model = AutoModel.from_pretrained("nlpaueb/legal-bert-base-uncased")

            self.fin_tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
            self.fin_model = AutoModel.from_pretrained("ProsusAI/finbert")

            if self.device == "cuda":
                self.legal_model = self.legal_model.to("cuda")
                self.fin_model = self.fin_model.to("cuda")

            logger.info("Loaded Legal-BERT and FinBERT")
        except Exception as exc:
            logger.warning("Transformer models unavailable: {}", exc)
            self.legal_model = False
            self.fin_model = False

    def get_sentence_embedding(self, text: str) -> list[float]:
        self._load_sentence_model()
        if self.sentence_model:
            embedding = self.sentence_model.encode(text or "", convert_to_tensor=False)
            return embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)

        digest = hashlib.sha256((text or "").encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big")
        rng = np.random.default_rng(seed)
        vector = rng.standard_normal(self.VECTOR_SIZE)
        norm = np.linalg.norm(vector) or 1.0
        return (vector / norm).astype(float).tolist()

    def encode_text(self, text: str, model_type: str = "legal") -> np.ndarray:
        self._load_transformers()
        if model_type not in {"legal", "financial"}:
            raise ValueError(f"Unknown model_type={model_type}")

        tokenizer = self.legal_tokenizer if model_type == "legal" else self.fin_tokenizer
        model = self.legal_model if model_type == "legal" else self.fin_model

        if not tokenizer or not model:
            return np.array(self.get_sentence_embedding(text), dtype=float)

        import torch

        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
        if self.device == "cuda":
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)
            embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()[0]
        return embedding
