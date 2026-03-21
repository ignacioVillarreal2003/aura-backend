import httpx
client = httpx.Client()
request = client.build_request("POST", "http://localhost:8000/api/document-query/retrieve-context-fragments-by-question", headers={"Authorization": "Bearer user_token_123"})
print(request.headers)
