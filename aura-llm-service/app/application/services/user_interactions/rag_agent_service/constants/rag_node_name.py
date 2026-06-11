from enum import Enum


class RagNodeName(str, Enum):
    query_analyzer = "query_analyzer"
    graph_context_retriever = "graph_context_retriever"
    context_retriever = "context_retriever"
    answer_synthesizer = "answer_synthesizer"
    fallback = "fallback"
