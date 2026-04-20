from typing import Optional

from pydantic import BaseModel, Field, model_validator

MAX_QUESTION_CHARS = 16_000
MAX_KEYWORDS_CHARS = 16_000
MAX_FRAGMENTS = 50
MAX_RERANK_FRAGMENTS = 100
MAX_CHAT_ID = 2_147_483_647


class QuestionContextFragmentsRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_CHARS)
    question_max_fragments: int = Field(..., ge=1, le=MAX_FRAGMENTS)
    chat_id: Optional[int] = Field(default=None, gt=0, le=MAX_CHAT_ID)
    use_keywords: Optional[bool] = Field(default=None)
    keywords: Optional[str] = Field(default=None, min_length=1, max_length=MAX_KEYWORDS_CHARS)
    keywords_max_fragments: Optional[int] = Field(default=None, ge=1, le=MAX_FRAGMENTS)
    use_rerank: Optional[bool] = Field(default=None)
    rerank_max_fragments: Optional[int] = Field(default=None, ge=1, le=MAX_RERANK_FRAGMENTS)

    @model_validator(mode="after")
    def validate_request(self) -> "QuestionContextFragmentsRequest":
        question = self.question.strip()
        if not question:
            raise ValueError("question must not be blank.")
        self.question = question

        if self.keywords is not None:
            keywords = self.keywords.strip()
            self.keywords = keywords or None

        if self.use_keywords:
            if not self.keywords:
                raise ValueError("keywords must be provided when use_keywords is true.")
            if self.keywords_max_fragments is None:
                raise ValueError("keywords_max_fragments must be provided when use_keywords is true.")

        if not self.use_rerank and self.rerank_max_fragments is not None:
            raise ValueError("rerank_max_fragments may only be set when use_rerank is true.")

        if self.use_rerank:
            if self.rerank_max_fragments is None:
                raise ValueError("rerank_max_fragments must be provided when use_rerank is true.")
            max_rerank = self.question_max_fragments
            if self.use_keywords and self.keywords_max_fragments:
                max_rerank += self.keywords_max_fragments
            if self.rerank_max_fragments > max_rerank:
                raise ValueError(
                    "rerank_max_fragments must not exceed the total of question_max_fragments and keywords_max_fragments."
                )

        return self
