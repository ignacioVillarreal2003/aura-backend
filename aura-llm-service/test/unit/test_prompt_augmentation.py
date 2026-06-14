from app.application.services.generation_shared.prompts.prompt_augmentation import augment_system_prompt

BASE = "Prompt base."


class TestAugmentSystemPrompt:
    def test_base_unchanged_without_extras(self):
        assert augment_system_prompt(BASE, None, None) == BASE

    def test_blank_extras_are_ignored(self):
        assert augment_system_prompt(BASE, "   ", "  ") == BASE

    def test_operator_prompt_is_appended_with_precedence_note(self):
        result = augment_system_prompt(BASE, "Sé breve.", None)
        assert result.startswith(BASE)
        assert "CONTEXTO DEL OPERADOR" in result
        assert "Sé breve." in result
        assert "prevalecen siempre las reglas anteriores" in result

    def test_response_style_is_appended(self):
        result = augment_system_prompt(BASE, None, "Tono formal.")
        assert "ESTILO DE RESPUESTA" in result
        assert "Tono formal." in result

    def test_operator_section_comes_before_style(self):
        result = augment_system_prompt(BASE, "Operador.", "Estilo.")
        assert result.index("CONTEXTO DEL OPERADOR") < result.index("ESTILO DE RESPUESTA")
