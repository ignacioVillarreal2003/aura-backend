from app.application.processors.text_cleaners.interfaces.text_cleaner_interface import TextCleanerInterface


class BasicTextCleaner(TextCleanerInterface):
    def clean_text(self, text: str) -> str:
        return " ".join(text.split())