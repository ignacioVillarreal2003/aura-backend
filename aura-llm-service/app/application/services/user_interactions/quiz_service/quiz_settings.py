from dataclasses import dataclass


@dataclass(frozen=True)
class QuizSettings:
    max_title_chars: int = 100
    max_instructions_chars: int = 2_000
    max_question_chars: int = 1_000
    max_explanation_chars: int = 2_000
    max_option_chars: int = 500
    max_questions: int = 200
    max_options: int = 10
