from enum import Enum


class RagNodeName(str, Enum):
    query_analyzer = "query_analyzer"
    context_retriever = "context_retriever"
    context_evaluator = "context_evaluator"
    reasoning = "reasoning"
    answer_synthesizer = "answer_synthesizer"
    fallback = "fallback"
