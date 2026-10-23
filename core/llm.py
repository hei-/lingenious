"""Thin OpenAI-compatible chat wrapper (default: DeepSeek). Provider/model come from config."""
from __future__ import annotations

import json
import os
import re
from typing import Optional, Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLM:
    def __init__(self, cfg: dict):
        c = cfg["llm"]
        key = os.environ.get(c.get("api_key_env", "DEEPSEEK_API_KEY"))
        if not key:
            raise RuntimeError(f"environment variable {c.get('api_key_env')} is not set")
        self.client = OpenAI(api_key=key, base_url=c["base_url"])
        self.model = c["model"]
        self.temperature = c.get("temperature", 0.2)
        self.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}

    def chat(self, messages: list[dict], json_mode: bool = False) -> str:
        kwargs: dict = {"response_format": {"type": "json_object"}} if json_mode else {}
        r = self.client.chat.completions.create(
            model=self.model, messages=messages,  # type: ignore[arg-type]
            temperature=self.temperature, **kwargs
        )
        self.usage["calls"] += 1
        if r.usage:
            self.usage["prompt_tokens"] += r.usage.prompt_tokens
            self.usage["completion_tokens"] += r.usage.completion_tokens
        return r.choices[0].message.content or ""

    def structured(self, messages: list[dict], model: Type[T], retries: int = 1) -> T:
        """JSON-mode call validated by pydantic; on failure feed the error back once."""
        msgs = list(messages)
        err: Optional[str] = None
        for _ in range(retries + 1):
            if err:
                msgs = msgs + [{"role": "user", "content": f"上一次输出不符合 schema:{err}\n请只输出修正后的 JSON。"}]
            text = self.chat(msgs, json_mode=True)
            try:
                return model.model_validate(json.loads(text))
            except (json.JSONDecodeError, ValidationError) as e:
                err = str(e)[:800]
                msgs = msgs + [{"role": "assistant", "content": text}]
        raise ValueError(f"structured output failed: {err}")


def extract_code(text: str) -> str:
    """Return the first python code block, or the raw text if none."""
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()
