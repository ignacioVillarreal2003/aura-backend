from enum import Enum


class Sentiment(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"