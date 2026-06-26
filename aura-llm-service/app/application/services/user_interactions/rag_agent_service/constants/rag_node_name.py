from enum import Enum


class RagNodeName(str, Enum):
    query_analyzer = "query_analyzer"
    graph_context_retriever = "graph_context_retriever"
    context_retriever = "context_retriever"
    document_fetcher = "document_fetcher"
    context_grader = "context_grader"
    query_refiner = "query_refiner"
    answer_synthesizer = "answer_synthesizer"
    guardrails = "guardrails"
    fallback = "fallback"
