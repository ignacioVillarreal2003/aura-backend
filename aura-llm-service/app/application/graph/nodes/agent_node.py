from langchain_core.messages import SystemMessage

from app.application import ollama_configurator
from app.application.graph.agent_state import AgentState


async def agent_node(state: AgentState):
    llm_with_tools = ollama_configurator.get_llm_with_tools()
    messages = state["messages"]
    sentiment = state.get("sentiment", "NEUTRAL")

    system_prompt = (
        "Eres un asistente inteligente orquestador. "
        f"El sentimiento del usuario es: {sentiment}. "
        "Si el usuario está enojado (negativo), sé más empático y formal. "
        "Si el usuario está contento (positivo), usa emojis. "
        "Tienes acceso a herramientas para buscar información (RAG) o resumir textos. "
        "Si te preguntan algo que requiere contexto, USA la herramienta search_knowledge_base. "
        "Si te piden resumir, USA summarize_document."
    )

    full_messages = [SystemMessage(content=system_prompt)] + messages
    response = await llm_with_tools.ainvoke(full_messages)

    return {"messages": [response]}