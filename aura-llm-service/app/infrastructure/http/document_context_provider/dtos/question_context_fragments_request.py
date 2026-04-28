from typing import Optional
from pydantic import BaseModel, Field, model_validator


class QuestionContextFragmentsRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=16_000)
    question_max_fragments: int = Field(..., ge=1, le=50)
    use_keywords: Optional[bool] = Field(default=None)
    keywords: Optional[str] = Field(default=None, max_length=16_000)
    keywords_max_fragments: Optional[int] = Field(default=None, ge=1, le=50)
    use_rerank: Optional[bool] = Field(default=None)
    rerank_max_fragments: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_request(self) -> "QuestionContextFragmentsRequest":
        question = self.question.strip()
        if not question:
            raise ValueError("question must not be empty.")
        self.question = question

        if self.keywords is not None:
            keywords = self.keywords.strip()
            self.keywords = keywords or None

        if self.use_keywords:
            if not self.keywords:
                raise ValueError("keywords must be provided when use_keywords is true.")
            if self.keywords_max_fragments is None:
                raise ValueError("keywords_max_fragments must be provided when use_keywords is true.")

        if self.use_rerank:
            if self.rerank_max_fragments is None:
                raise ValueError("rerank_max_fragments must be provided when use_rerank is true.")
            max_rerank_fragments = self.question_max_fragments
            if self.use_keywords:
                max_rerank_fragments += self.keywords_max_fragments
            if self.rerank_max_fragments > max_rerank_fragments:
                raise ValueError("rerank_max_fragments must not exceed total question+keywords fragments.")

        return self
