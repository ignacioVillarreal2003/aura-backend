from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.application.services.general.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.general.document_question_service.steps.generate_answer.generate_answer_prompt import (
    GENERATE_ANSWER_PROMPT,
    LEARNING_GUIDELINES,
)
from app.domain.constants.message_role import MessageRole


def build_generate_answer_llm_input(
        state: DocumentQuestionPipelineState,
        history_window: int,
) -> list[BaseMessage]:
    context_fragments = state.retrieved_fragments
    context = "\n\n---\n\n".join(f.content for f in context_fragments)

    history_tail = (
        state.history_messages[-history_window:]
        if history_window > 0
        else []
    )
    history_messages: list[BaseMessage] = []
    for msg in history_tail:
        if msg.role == MessageRole.human:
            history_messages.append(HumanMessage(content=msg.content))
        elif msg.role == MessageRole.assistant:
            history_messages.append(AIMessage(content=msg.content))

    return [
        SystemMessage(content=LEARNING_GUIDELINES),
        *history_messages,
        HumanMessage(
            content=GENERATE_ANSWER_PROMPT.format(
                query=state.current_message.content,
                context=context,
            )
        ),
    ]
