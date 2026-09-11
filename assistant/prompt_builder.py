from __future__ import annotations

import json

from assistant.chat_message import ChatMessage
from assistant.patient_analysis_context import PatientAnalysisContext


class PromptBuilder:
    """Builds LLM prompts grounded in PatientAnalysisContext."""

    SYSTEM_PROMPT = (
        "You are an assistant inside a health analytics demo app. "
        "Explain the machine-learning outputs only: selected symptoms, disease prediction, "
        "and cluster assignment. "
        "Use plain language for non-experts. "
        "Do not give a medical diagnosis beyond the provided ML results. "
        "Do not invent diseases, probabilities, clusters, or symptoms that are not in the context. "
        "If information is missing, say what is missing. "
        "Remind the user this is not clinical advice."
    )

    def build_messages(
        self,
        context: PatientAnalysisContext,
        question: str,
        history: list[ChatMessage],
    ) -> list[dict[str, str]]:
        context_json = json.dumps(context.to_prompt_dict(), indent=2)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "system",
                "content": (
                    "Current ML analysis context (JSON). "
                    "Only discuss these values:\n"
                    f"{context_json}"
                ),
            },
        ]
        for message in history[-6:]:
            if message.role in {"user", "assistant"}:
                messages.append({"role": message.role, "content": message.content})
        messages.append({"role": "user", "content": question})
        return messages
