import os

os.environ.setdefault("AUTHENTICATION_PROVIDER_AUTHENTICATION_URL", "http://auth.test")
os.environ.setdefault("DOCUMENT_CONTEXT_PROVIDER_QUESTION_CONTEXT_FRAGMENTS_URL", "http://docs.test/by-question")
os.environ.setdefault("DOCUMENT_CONTEXT_PROVIDER_DOCUMENT_CONTEXT_FRAGMENTS_URL", "http://docs.test/by-document")
