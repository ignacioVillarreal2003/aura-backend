from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.application.services.generation_shared.state.generation_state import GenerationState
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.fragment.fragment_response import FragmentResponse

_NO_CONTEXT_PLACEHOLDER = (
    "(Sin contexto documental disponible. Trabajá únicamente con la información "
    "que aportó el usuario.)"
)


def _format_fragment_locator(fragment: FragmentResponse) -> str:
    parts: list[str] = []
    if fragment.page_number is not None:
        parts.append(f"pág. {fragment.page_number}")
    section = fragment.heading or fragment.section_path
    if section:
        parts.append(section)
    return " · ".join(parts)


def _render_fragments(
        parts: list[str],
        fragments: list[FragmentResponse],
        budget: int,
        *,
        use_contextualized: bool = True,
) -> int:
    used = 0
    for i, frag in enumerate(fragments, 1):
        locator = _format_fragment_locator(frag)
        header = f"[FRAGMENTO {i} — {frag.document.name}" + (f" · {locator}" if locator else "") + "]"
        body = frag.effective_content if use_contextualized else frag.content
        entry = f"\n{header}\n{body}"
        if used + len(entry) > budget:
            break
        parts.append(entry)
        used += len(entry)
    return used


def _build_section_context_block(state: GenerationState, max_context_chars: int) -> str:
    primaries = state.fragments
    secondary = [
        fragment
        for group in (state.section_groups or [])
        for fragment in group.section_fragments
    ]
    if not primaries and not secondary and not state.section_summary:
        return _NO_CONTEXT_PLACEHOLDER

    parts: list[str] = []
    used = 0

    if primaries:
        header = "=== CONTEXTO PRINCIPAL ==="
        parts.append(header)
        used += len(header)
        used += _render_fragments(parts, primaries, max_context_chars - used)

    if state.section_summary:
        header = "=== CONTEXTO DE SECCIÓN (complementario, resumido) ==="
        remaining = max_context_chars - used - len(header) - 1
        if remaining > 0:
            entry = f"{header}\n{state.section_summary[:remaining]}"
            parts.append(entry)
            used += len(entry)
    elif secondary:
        header = "=== CONTEXTO DE SECCIÓN (complementario) ==="
        if max_context_chars - used > len(header):
            parts.append(header)
            used += len(header)
            _render_fragments(parts, secondary, max_context_chars - used)

    parts.append("=== FIN DE CONTEXTO ===")
    return "\n".join(parts)


def build_context_block(
        state: GenerationState,
        max_context_chars: int,
        attached_reserve_ratio: float = 0.6,
) -> str:
    if state.section_groups:
        return _build_section_context_block(state, max_context_chars)

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
        used += _render_fragments(parts, attached, reserve, use_contextualized=False)

    if rag:
        parts.append("=== CONTEXTO DOCUMENTAL RECUPERADO (COMPLEMENTARIO) ===")
        _render_fragments(parts, rag, max_context_chars - used)

    parts.append("=== FIN DE CONTEXTO ===")
    return "\n".join(parts)


def _fit_history_within_budget(messages: list, max_history_chars: int) -> list:
    if max_history_chars <= 0 or not messages:
        return messages
    kept: list = []
    used = 0
    for msg in reversed(messages):
        if kept and used + len(msg.content) > max_history_chars:
            break
        kept.append(msg)
        used += len(msg.content)
    kept.reverse()
    return kept


def build_generation_messages(
        system_prompt: str,
        human_prompt_template: str,
        state: GenerationState,
        history_messages_window: int,
        context_block: str,
        max_history_chars: int = 0,
) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

    if state.history_summary:
        messages.append(
            HumanMessage(content=f"(Resumen de la conversación previa)\n{state.history_summary}")
        )
    else:
        tail = (
            state.history_messages[-history_messages_window:]
            if history_messages_window > 0
            else []
        )
        for msg in _fit_history_within_budget(tail, max_history_chars):
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
