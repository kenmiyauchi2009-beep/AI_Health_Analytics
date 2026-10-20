from __future__ import annotations

import streamlit as st

from assistant.ai_query import AIQuery
from assistant.ai_result_assistant import AIResultAssistant
from assistant.conversation_manager import ConversationManager
from assistant.doctor_analysis_context import DoctorAnalysisContext
from assistant.doctor_prompt_builder import DoctorPromptBuilder
from assistant.doctor_safety_guard import DoctorSafetyGuard
from assistant.llm_client import LLMClient
from assistant.patient_analysis_context import PatientAnalysisContext
from assistant.prompt_builder import PromptBuilder
from assistant.safety_guard import SafetyGuard


def _get_groq_api_key() -> str | None:
    try:
        key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        return None
    if key is None:
        return None
    return str(key).strip() or None


def _get_groq_model() -> str:
    try:
        model = st.secrets.get("GROQ_MODEL")
    except Exception:
        model = None
    if model is None or not str(model).strip():
        return LLMClient.DEFAULT_MODEL
    return str(model).strip()


def _get_conversation() -> ConversationManager:
    if "ai_conversation" not in st.session_state:
        st.session_state.ai_conversation = ConversationManager()
    return st.session_state.ai_conversation


def build_context_from_session() -> PatientAnalysisContext:
    return PatientAnalysisContext(
        selected_symptoms=list(st.session_state.get("selected_symptoms", [])),
        prediction=st.session_state.get("latest_prediction"),
        cluster_assignment=st.session_state.get("latest_cluster_assignment"),
    )


def render_assistant_panel() -> None:
    st.subheader("Ask AI about your results")
    st.caption(
        "This assistant explains your selected symptoms, disease prediction, and cluster match. "
        "It will not diagnose outside the app’s ML results."
    )

    context = build_context_from_session()
    if not context.has_analysis():
        st.info(
            "First run **Predict Disease** and/or **Find Closest Cluster**, "
            "then ask questions here."
        )
        return

    with st.expander("Analysis context sent to the assistant", expanded=False):
        st.json(context.to_prompt_dict())

    _render_chat(
        context,
        conversation=_get_conversation(),
        safety_guard=SafetyGuard(),
        prompt_builder=PromptBuilder(),
        key_prefix="ai",
        placeholder="Ask a question about your results",
    )


def render_doctor_assistant_panel(context: DoctorAnalysisContext, conversation_key: str) -> None:
    """Doctor-facing assistant for one saved analysis; history is kept per analysis."""
    st.subheader("AI Assistant")
    st.caption(
        "Ask about this analysis, the model's uncertainty, the patient subgroup, or how it compares "
        "with the patient's earlier analyses. Answers are grounded in the ML output only."
    )

    with st.expander("Analysis context sent to the assistant", expanded=False):
        st.json(context.to_prompt_dict())

    if conversation_key not in st.session_state:
        st.session_state[conversation_key] = ConversationManager()

    _render_chat(
        context,
        conversation=st.session_state[conversation_key],
        safety_guard=DoctorSafetyGuard(),
        prompt_builder=DoctorPromptBuilder(),
        key_prefix=conversation_key,
        placeholder="Ask the assistant about this analysis",
    )


def _render_chat(
    context: PatientAnalysisContext,
    *,
    conversation: ConversationManager,
    safety_guard: SafetyGuard,
    prompt_builder: PromptBuilder,
    key_prefix: str,
    placeholder: str,
) -> None:
    api_key = _get_groq_api_key()
    if not api_key:
        st.warning(
            "Add your Groq API key to `.streamlit/secrets.toml` as "
            '`GROQ_API_KEY = "your_key_here"`, then reboot the app.'
        )
        return

    for message in conversation.messages:
        with st.chat_message(message.role):
            st.write(message.content)

    pending_key = f"{key_prefix}_pending_question"
    st.markdown("**Suggested questions**")
    cols = st.columns(2)
    for index, suggestion in enumerate(safety_guard.SUGGESTED_QUESTIONS):
        if cols[index % 2].button(suggestion, key=f"{key_prefix}_suggestion_{index}"):
            st.session_state[pending_key] = suggestion

    prompt = st.chat_input(placeholder, key=f"{key_prefix}_chat_input")
    question = st.session_state.pop(pending_key, None) or prompt
    if not question:
        return

    try:
        assistant = AIResultAssistant(
            llm_client=LLMClient(api_key=api_key, model=_get_groq_model()),
            prompt_builder=prompt_builder,
            safety_guard=safety_guard,
            conversation=conversation,
        )
        response = assistant.ask(AIQuery(text=question), context)
    except Exception as error:
        st.error(f"Assistant error: {error}")
        return

    if response.refused:
        conversation.add_user(question)
        conversation.add_assistant(response.answer)

    st.rerun()
