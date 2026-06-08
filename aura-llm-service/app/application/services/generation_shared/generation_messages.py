from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.application.services.generation_shared.generation_state import GenerationState
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.fragment.fragment_response import FragmentResponse

_NO_CONTEXT_PLACEHOLDER = (
    "(Sin contexto documental disponible. Trabajá únicamente con la información "
    "que aportó el usuario.)"
)


def _render_fragments(parts: list[str], fragments: list[FragmentResponse], budget: int) -> int:
    used = 0
    for i, frag in enumerate(fragments, 1):
        entry = f"\n[FRAGMENTO {i} — {frag.document.name}]\n{frag.content}"
        if used + len(entry) > budget:
            break
        parts.append(entry)
        used += len(entry)
    return used


def build_context_block(
        state: GenerationState,
        max_context_chars: int,
        attached_reserve_ratio: float = 0.6,
) -> str:
    if state.reduced_context:
        return (
            "=== SÍNTESIS DE CONTEXTO DOCUMENTAL (extraída en varias pasadas) ===\n"
            f"{state.reduced_context}\n"
            "=== FIN DE CONTEXTO ==="
        )

    attached = state.attached_fragments
    rag = state.rag_only_fragments
    if not attached and not rag:
        return _NO_CONTEXT_PLACEHOLDER

    parts: list[str] = []
    used = 0
    if attached:
        reserve = max_context_chars if not rag else int(max_context_chars * attached_reserve_ratio)
        parts.append("=== DOCUMENTOS ADJUNTOS (FUENTE PRIORITARIA) ===")
        used += _render_fragments(parts, attached, reserve)

    if rag:
        parts.append("=== CONTEXTO DOCUMENTAL RECUPERADO (COMPLEMENTARIO) ===")
        _render_fragments(parts, rag, max_context_chars - used)

    parts.append("=== FIN DE CONTEXTO ===")
    return "\n".join(parts)


def build_generation_messages(
        system_prompt: str,
        human_prompt_template: str,
        state: GenerationState,
        history_messages_window: int,
        context_block: str,
) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

    tail = (
        state.history_messages[-history_messages_window:]
        if history_messages_window > 0
        else []
    )
    for msg in tail:
        if msg.role == MessageRole.human:
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == MessageRole.assistant:
            messages.append(AIMessage(content=msg.content))

    messages.append(
        HumanMessage(
            content=human_prompt_template.format(
                context=context_block,
                input=state.current_message.content,
            )
        )
    )
    return messages
