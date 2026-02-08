from app.infrastructure.http_client.http_client import HttpClient
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface


def get_http_client() -> HttpClientInterface:
    return HttpClient.get_instance()
