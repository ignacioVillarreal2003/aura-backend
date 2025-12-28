from dataclasses import dataclass


@dataclass(frozen=True)
class SentimentConfig:
    system_prompt: str = (
        "Eres un experto clasificador de sentimientos. "
        "Tu tarea es analizar el mensaje del usuario y clasificar su sentimiento emocional. "
        "Debes responder ÚNICAMENTE con una de estas tres palabras: positive, negative, neutral. "
        "No incluyas explicaciones, puntuación adicional ni texto extra."
    )

    user_prompt_template: str = (
        "Analiza el siguiente mensaje y clasifica su sentimiento:\n\n"
        '"{message}"'
    )