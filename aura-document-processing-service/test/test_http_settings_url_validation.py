"""
Tests for URL validation in the document-collection-catalog and chat-membership
settings (scheme + host), mirroring the auth/llm provider settings.
"""
import pytest
from pydantic import ValidationError

from app.infrastructure.http.chat_membership.chat_membership_provider_settings import (
    ChatMembershipProviderSettings,
)
from app.infrastructure.http.document_collection_catalog.document_collection_catalog_settings import (
    DocumentCollectionCatalogSettings,
)


class TestCollectionCatalogSettingsUrl:
    def test_valid_url_is_accepted_and_trimmed(self):
        s = DocumentCollectionCatalogSettings(
            accessible_collections_url="http://collections.local/api/ "
        )
        assert s.accessible_collections_url == "http://collections.local/api"

    def test_missing_scheme_is_rejected(self):
        with pytest.raises(ValidationError):
            DocumentCollectionCatalogSettings(accessible_collections_url="collections.local/api")

    def test_missing_host_is_rejected(self):
        with pytest.raises(ValidationError):
            DocumentCollectionCatalogSettings(accessible_collections_url="http://")


class TestChatMembershipSettingsUrl:
    def test_none_is_allowed(self):
        s = ChatMembershipProviderSettings(membership_url=None)
        assert s.membership_url is None

    def test_empty_string_becomes_none(self):
        s = ChatMembershipProviderSettings(membership_url="   ")
        assert s.membership_url is None

    def test_valid_url_is_accepted(self):
        s = ChatMembershipProviderSettings(membership_url="https://chat.local/")
        assert s.membership_url == "https://chat.local"

    def test_missing_scheme_is_rejected(self):
        with pytest.raises(ValidationError):
            ChatMembershipProviderSettings(membership_url="chat.local")

    def test_missing_host_is_rejected(self):
        with pytest.raises(ValidationError):
            ChatMembershipProviderSettings(membership_url="https://")
