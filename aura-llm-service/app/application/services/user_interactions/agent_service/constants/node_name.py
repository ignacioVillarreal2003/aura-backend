from enum import Enum


class NodeName(str, Enum):
    input_normalizer = "input_normalizer"
    context_resolver = "context_resolver"
    intent_classifier = "intent_classifier"
    keyword_extractor = "keyword_extractor"
    retriever = "retriever"
    document_fetcher = "document_fetcher"
    context_builder = "context_builder"
    answer_generator = "answer_generator"
    guardrails = "guardrails"
    fallback = "fallback"
