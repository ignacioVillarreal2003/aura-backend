from app.application.graph.agent_state import AgentState
from app.application.ollama_configurator.ollama_configurator import ollama_configurator


async def sentiment_node(state: AgentState):
    llm = ollama_configurator.get_llm_base()
    last_message = state["messages"][-1]

    prompt = f"Clasifica el sentimiento: {last_message.content}. Responde solo: POSITIVO, NEGATIVO, NEUTRAL."

    response = await llm.ainvoke(prompt)
    sentiment = response.content.strip().upper()

    return {"sentiment": sentiment}