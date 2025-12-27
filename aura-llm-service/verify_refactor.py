import asyncio
import logging
import sys
from unittest.mock import MagicMock, AsyncMock

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Mock dependencies before imports to avoid side effects if needed
# But for now we import real classes and mock their internals

from app.application.llm_configurator.ollama_llm_configurator import OllamaConfigurator
from app.application.agent_workflow.agent_workflow import create_agent_workflow
from app.application.tools.document_question_tool import DocumentQuestionTool
from app.infrastructure.providers.context_provider import ContextProvider
from app.domain.agent_state.agent_state import AgentState
from langchain_core.messages import HumanMessage, AIMessage

async def run_verification():
    print("Starting verification...")

    # 1. Mock ContextProvider for Tool
    mock_http_client = MagicMock()
    context_provider = ContextProvider(mock_http_client, "http://mock", "http://mock")
    context_provider.retrieve_fragments_by_question = AsyncMock(return_value=["fragment 1", "fragment 2"])

    # 2. Define Tool Factory
    def tool_factory():
        return DocumentQuestionTool(context_provider=context_provider)

    # 3. Create OllamaConfigurator
    # We mock ChatOllama inside it or just let it fail connecting if it tries?
    # OllamaConfigurator tries to create ChatOllama in initialization.
    # We should mock ChatOllama to avoid needing a real server.
    
    with (
        # Patching ChatOllama in llm_configurator module
        # We need to find where it is imported. 
         # app.application.llm_configurator.llm_configurator.ChatOllama
        import.mock.patch("app.application.llm_configurator.llm_configurator.ChatOllama") as MockChatOllama
    ):
        # Setup Mock LLM
        mock_llm_instance = MagicMock()
        mock_llm_instance.bind_tools.return_value = mock_llm_instance
        mock_llm_instance.ainvoke = AsyncMock(return_value=AIMessage(content="Hello!"))
        
        MockChatOllama.return_value = mock_llm_instance

        configurator = OllamaConfigurator(
            ollama_model_name="mock-model",
            ollama_base_url="http://localhost:11434",
            ollama_temperature=0.5,
            tool_factories=[tool_factory]
        )

        # Initialize to setup LLM and Tools
        configurator.initialize()
        
        print("Configurator initialized.")
        print(f"Tools count: {len(configurator.tools)}")

        # 4. Create Workflow
        workflow = create_agent_workflow(configurator)
        print("Workflow created.")

        # 5. Run Workflow
        state = {"messages": [HumanMessage(content="Hola")]}
        print("Running workflow...")
        
        # Since we mocked the LLM to return "Hello!", it should run AgentNode and finish.
        result = await workflow.ainvoke(state)
        
        print("Workflow execution finished.")
        print(f"Result messages: {len(result['messages'])}")
        print(f"Last message: {result['messages'][-1].content}")

        assert len(result['messages']) >= 2 # Input + Output
        assert result['messages'][-1].content == "Hello!"

if __name__ == "__main__":
    # Need to import mock properly
    import unittest.mock
    sys.modules['unittest.mock'] = unittest.mock
    
    asyncio.run(run_verification())
