from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from loguru import logger


class PolicyMappingAgent:
    MAPPING_PROMPT = """You are a regulatory compliance expert.

Evaluate whether the internal policy covers the compliance obligation.

Compliance Obligation:
{obligation_text}

Obligation Type: {obligation_type}
Risk Level: {risk_level}

Internal Policy:
Title: {policy_title}
Description: {policy_description}
Control Type: {control_type}

Respond with strict JSON:
{{
  "coverage_status": "full|partial|none",
  "confidence": 0.0,
  "rationale": "short explanation",
  "gaps": ["..."]
}}
"""

    def __init__(
        self,
        api_key: str | None = None,
        provider: str = "nvidia_nim",
        model: str | None = None,
        nim_base_url: str = "https://integrate.api.nvidia.com/v1",
    ):
        self.provider = provider
        self.api_key = api_key
        self.model = model

        self.openai_client = None
        self.anthropic_client = None

        if not api_key:
            logger.info("No API key provided. Mapping agent will use heuristic mode.")
            return

        if provider == "openai":
            from openai import AsyncOpenAI

            self.openai_client = AsyncOpenAI(api_key=api_key)
            self.model = model or "gpt-4o-mini"
        elif provider == "nvidia_nim":
            from openai import AsyncOpenAI

            self.openai_client = AsyncOpenAI(api_key=api_key, base_url=nim_base_url.rstrip("/"))
            self.model = model or "meta/llama-3.1-8b-instruct"
        elif provider == "anthropic":
            from anthropic import AsyncAnthropic

            self.anthropic_client = AsyncAnthropic(api_key=api_key)
            self.model = model or "claude-3-5-sonnet-20241022"
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    async def map_obligation_to_policy(self, obligation: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            return self._heuristic_map(obligation, policy)

        prompt = self.MAPPING_PROMPT.format(
            obligation_text=obligation["obligation_text"],
            obligation_type=obligation.get("obligation_type", "general"),
            risk_level=obligation.get("risk_level", "medium"),
            policy_title=policy["title"],
            policy_description=policy.get("description", "N/A"),
            control_type=policy.get("control_type", "N/A"),
        )

        try:
            content = await self._call_llm(prompt)
            parsed = self._extract_json(content)
            return {
                "obligation_id": obligation["id"],
                "policy_db_id": policy["id"],
                "policy_ref": policy["policy_id"],
                "coverage_status": parsed.get("coverage_status", "none"),
                "mapping_confidence": float(parsed.get("confidence", 0.0)),
                "mapping_rationale": parsed.get("rationale", "No rationale returned"),
                "identified_gaps": parsed.get("gaps", []),
            }
        except Exception as exc:
            logger.warning("LLM mapping failed, falling back to heuristic mode: {}", exc)
            return self._heuristic_map(obligation, policy)

    async def batch_map_obligations(
        self,
        obligations: list[dict[str, Any]],
        policies: list[dict[str, Any]],
        concurrency: int = 6,
    ) -> list[dict[str, Any]]:
        semaphore = asyncio.Semaphore(max(1, concurrency))

        async def run_single(obligation: dict[str, Any], policy: dict[str, Any]):
            async with semaphore:
                return await self.map_obligation_to_policy(obligation, policy)

        tasks = [run_single(obligation, policy) for obligation in obligations for policy in policies]
        results = await asyncio.gather(*tasks)

        filtered = [
            result
            for result in results
            if result["coverage_status"] in {"full", "partial"} or result["mapping_confidence"] >= 0.5
        ]
        return filtered

    async def _call_llm(self, prompt: str) -> str:
        if self.provider in {"openai", "nvidia_nim"} and self.openai_client:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=700,
            )
            return response.choices[0].message.content or "{}"

        if self.provider == "anthropic" and self.anthropic_client:
            response = await self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=700,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text

        raise RuntimeError("No valid LLM client initialized")

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        content = content.strip()
        try:
            return json.loads(content)
        except Exception:
            pass

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return {}

        try:
            return json.loads(match.group(0))
        except Exception:
            return {}

    @staticmethod
    def _heuristic_map(obligation: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
        obligation_terms = {
            token.lower()
            for token in re.findall(r"[a-zA-Z]{4,}", obligation.get("obligation_text", ""))
            if token.lower() not in {"shall", "must", "with", "from", "that", "this", "than"}
        }
        policy_terms = {
            token.lower()
            for token in re.findall(
                r"[a-zA-Z]{4,}", f"{policy.get('title', '')} {policy.get('description', '')}"
            )
        }

        overlap = obligation_terms & policy_terms
        denom = max(len(obligation_terms), 1)
        ratio = len(overlap) / denom

        if ratio >= 0.45:
            status = "full"
        elif ratio >= 0.2:
            status = "partial"
        else:
            status = "none"

        confidence = min(0.95, 0.25 + ratio)

        gaps = []
        if status != "full":
            missing = sorted(list(obligation_terms - policy_terms))[:5]
            if missing:
                gaps.append(f"Missing obligation concepts: {', '.join(missing)}")

        return {
            "obligation_id": obligation["id"],
            "policy_db_id": policy["id"],
            "policy_ref": policy["policy_id"],
            "coverage_status": status,
            "mapping_confidence": round(confidence, 3),
            "mapping_rationale": f"Heuristic keyword overlap ratio={ratio:.2f} ({len(overlap)} matches).",
            "identified_gaps": gaps,
        }
