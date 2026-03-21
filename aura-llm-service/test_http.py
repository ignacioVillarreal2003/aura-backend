import asyncio
import httpx
from unittest.mock import AsyncMock, patch

from app.infrastructure.http_client.http_client import HttpClient
from app.infrastructure.document_context_provider.document_context_provider import DocumentContextProvider
from app.infrastructure.document_context_provider.document_context_provider_settings import DocumentContextProviderSettings

async def main():
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        # Mocking the response
        mock_response = httpx.Response(200, json={"context_fragments": [{"content": "foo"}]})
        mock_request.return_value = mock_response

        # Start client
        client = HttpClient()
        await client.start()

        provider = DocumentContextProvider(http_client=client)

        await provider.retrieve_context_fragments_by_question("Test?", 3)

        # Print the call arguments
        print("Calls to httpx:")
        for call_args in mock_request.call_args_list:
            args, kwargs = call_args
            print("Method and URL:", args)
            if "headers" in kwargs:
                print("Headers passed directly via kwargs:")
                for k, v in kwargs["headers"].items():
                    print(f"  {k}: {v}")
            else:
                print("No headers kwargs.")
        print()
        await client.stop()

if __name__ == "__main__":
    asyncio.run(main())
