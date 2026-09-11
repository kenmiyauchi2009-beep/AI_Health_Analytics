from __future__ import annotations

from assistant.ai_query import AIQuery
from assistant.ai_response import AIResponse
from assistant.conversation_manager import ConversationManager
from assistant.llm_client import LLMClient
from assistant.patient_analysis_context import PatientAnalysisContext
from assistant.prompt_builder import PromptBuilder
from assistant.safety_guard import SafetyGuard


class AIResultAssistant:
    """Orchestrates safety checks, prompting, LLM calls, and conversation state."""

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_builder: PromptBuilder | None = None,
        safety_guard: SafetyGuard | None = None,
        conversation: ConversationManager | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.safety_guard = safety_guard or SafetyGuard()
        self.conversation = conversation or ConversationManager()

    def ask(self, query: AIQuery, context: PatientAnalysisContext) -> AIResponse:
        if not context.has_analysis():
            return AIResponse(
                answer=(
                    "Run Predict and/or Find Closest Cluster first so I have ML results "
                    "to explain."
                ),
                refused=True,
                refusal_reason="missing_analysis",
                suggested_questions=SafetyGuard.SUGGESTED_QUESTIONS,
            )

        allowed, reason = self.safety_guard.check(query.text)
        if not allowed:
            return AIResponse(
                answer=reason or "I cannot answer that question.",
                refused=True,
                refusal_reason="safety",
                suggested_questions=SafetyGuard.SUGGESTED_QUESTIONS,
            )

        messages = self.prompt_builder.build_messages(
            context=context,
            question=query.text,
            history=self.conversation.messages,
        )
        answer = self.llm_client.complete(messages)
        self.conversation.add_user(query.text)
        self.conversation.add_assistant(answer)
        return AIResponse(
            answer=answer,
            refused=False,
            suggested_questions=SafetyGuard.SUGGESTED_QUESTIONS,
        )
