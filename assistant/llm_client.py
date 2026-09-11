from __future__ import annotations

from typing import Any


class LLMClient:
    """Thin Groq Chat Completions client."""

    DEFAULT_MODEL = "llama-3.1-8b-instant"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        if not api_key or not api_key.strip():
            raise ValueError(
                "GROQ_API_KEY is missing. Add it to .streamlit/secrets.toml."
            )
        try:
            from groq import Groq
        except ImportError as error:
            raise ValueError(
                "The groq package is not installed. Run: pip install groq"
            ) from error

        self._client = Groq(api_key=api_key.strip())
        self.model = model

    def complete(self, messages: list[dict[str, str]]) -> str:
        response: Any = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            max_tokens=700,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("The LLM returned an empty response.")
        return content.strip()
