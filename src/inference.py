"""
Inference and Cost Accounting Module
Supports live Groq API inference for candidate models:
  - openai/gpt-oss-20b
  - openai/gpt-oss-120b
Includes token cost calculation and offline MockInferenceRunner for testing.
"""

import json
import os
import re
import time
import winreg
from typing import Any, Dict, List, Optional
from openai import OpenAI

# Published token rates per 1M tokens (from llm-routing-study)
RATES = {
    "openai/gpt-oss-20b": {"prompt": 0.075 / 1e6, "completion": 0.300 / 1e6},
    "openai_gpt-oss-20b": {"prompt": 0.075 / 1e6, "completion": 0.300 / 1e6},
    "openai/gpt-oss-120b": {"prompt": 0.150 / 1e6, "completion": 0.600 / 1e6},
    "openai_gpt-oss-120b": {"prompt": 0.150 / 1e6, "completion": 0.600 / 1e6},
}


def get_groq_client(timeout: float = 60.0) -> OpenAI:
    """Retrieves GROQ_API_KEY from environment or Windows registry."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
            api_key, _ = winreg.QueryValueEx(k, "GROQ_API_KEY")
        except Exception:
            pass
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not found in environment or Windows registry.")
    return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1", timeout=timeout)


def compute_token_cost(prompt_tokens: int, completion_tokens: int, model_id: str) -> float:
    """Calculates published accounting cost in USD based on exact token usage."""
    rate = RATES.get(model_id, {"prompt": 0.150 / 1e6, "completion": 0.600 / 1e6})
    return (prompt_tokens * rate["prompt"]) + (completion_tokens * rate["completion"])


def is_tpd_exhaustion(error_str: str) -> bool:
    lower = error_str.lower()
    return "tokens per day" in lower or "limit 200000" in lower or "tpd" in lower


def call_groq_inference(
    client: OpenAI,
    model_id: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    max_retries: int = 3,
    initial_backoff: float = 2.0
) -> Dict[str, Any]:
    """
    Executes chat completion with retry, token tracking, and latency measurement.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    backoff = initial_backoff
    retries = 0
    t0 = time.time()

    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
            latency_ms = int((time.time() - t0) * 1000)
            choice = resp.choices[0]
            usage = resp.usage

            p_tok = usage.prompt_tokens if usage else 0
            c_tok = usage.completion_tokens if usage else 0
            tot_tok = usage.total_tokens if usage else (p_tok + c_tok)
            cost_usd = compute_token_cost(p_tok, c_tok, model_id)

            return {
                "status": "success",
                "raw_text": choice.message.content or "",
                "finish_reason": choice.finish_reason,
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "total_tokens": tot_tok,
                "latency_ms": latency_ms,
                "cost_usd": cost_usd,
                "retries": retries,
                "error": None
            }
        except Exception as e:
            err_str = str(e)
            if is_tpd_exhaustion(err_str):
                return {
                    "status": "quota_exhausted",
                    "raw_text": "",
                    "finish_reason": "quota_exhausted",
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "cost_usd": 0.0,
                    "retries": retries,
                    "error": err_str
                }
            retries += 1
            if attempt == max_retries - 1:
                return {
                    "status": "error",
                    "raw_text": "",
                    "finish_reason": "error",
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "cost_usd": 0.0,
                    "retries": retries,
                    "error": err_str
                }
            time.sleep(backoff)
            backoff *= 2.0


class MockInferenceRunner:
    """Mock runner for offline testing and reproducible tests without API access."""
    def __init__(self, responses_by_kpi: Optional[Dict[str, Dict]] = None):
        self.responses_by_kpi = responses_by_kpi or {}

    def call_mock(self, model_id: str, kpi_name: str, gold_record: Optional[Dict] = None) -> Dict[str, Any]:
        if kpi_name in self.responses_by_kpi:
            data = self.responses_by_kpi[kpi_name]
        elif gold_record:
            # Deterministic mock from gold record
            data = {
                "kpi_name": kpi_name,
                "raw_value": gold_record.get("raw_value"),
                "raw_unit": gold_record.get("raw_unit"),
                "disclosure_status": "disclosed",
                "reporting_boundary": gold_record.get("reporting_boundary"),
                "pdf_page_index": gold_record.get("pdf_page_index"),
                "evidence_text": gold_record.get("evidence_text"),
                "confidence": 0.95
            }
        else:
            data = {
                "kpi_name": kpi_name,
                "raw_value": None,
                "raw_unit": None,
                "disclosure_status": "not_disclosed",
                "reporting_boundary": None,
                "pdf_page_index": None,
                "evidence_text": None,
                "confidence": 0.0
            }

        p_tok = 850
        c_tok = 95
        cost = compute_token_cost(p_tok, c_tok, model_id)

        return {
            "status": "success",
            "raw_text": json.dumps(data),
            "finish_reason": "stop",
            "prompt_tokens": p_tok,
            "completion_tokens": c_tok,
            "total_tokens": p_tok + c_tok,
            "latency_ms": 350,
            "cost_usd": cost,
            "retries": 0,
            "error": None
        }
