from __future__ import annotations

import streamlit as st

from assistant.ai_query import AIQuery
from assistant.ai_result_assistant import AIResultAssistant
from assistant.conversation_manager import ConversationManager
from assistant.llm_client import LLMClient
from assistant.patient_analysis_context import PatientAnalysisContext
from assistant.safety_guard import SafetyGuard


def _get_groq_api_key() -> str | None:
    try:
        key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        return None
    if key is None:
        return None
    return str(key).strip() or None


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

    api_key = _get_groq_api_key()
    if not api_key:
        st.warning(
            "Add your Groq API key to `.streamlit/secrets.toml` as "
            '`GROQ_API_KEY = "your_key_here"`, then reboot the app.'
        )
        return

    conversation = _get_conversation()
    for message in conversation.messages:
        with st.chat_message(message.role):
            st.write(message.content)

    st.markdown("**Suggested questions**")
    cols = st.columns(2)
    for index, suggestion in enumerate(SafetyGuard.SUGGESTED_QUESTIONS):
        if cols[index % 2].button(suggestion, key=f"ai_suggestion_{index}"):
            st.session_state.ai_pending_question = suggestion

    prompt = st.chat_input("Ask a question about your results")
    question = st.session_state.pop("ai_pending_question", None) or prompt
    if not question:
        return

    try:
        assistant = AIResultAssistant(
            llm_client=LLMClient(api_key=api_key),
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
