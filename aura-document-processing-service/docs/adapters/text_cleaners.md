# Text Cleaners

Normalizan el texto crudo extraído por los readers antes del chunking. Se seleccionan por
`TEXT_CLEANER_ACTIVE_TYPE` (default `simple`) vía `TextCleanerFactory`.

## SimpleTextCleaner (`simple`)

Único cleaner activo. Pipeline determinístico, **stateless y thread-safe** (se ejecuta en
`asyncio.to_thread`, no bloquea el event loop):

1. Normaliza fin de línea (`\r\n`/`\r` → `\n`) y tabs → espacio.
2. Normalización Unicode **NFKC**.
3. Elimina **caracteres de control** y **emojis**.
4. **Strip de Markdown**: imágenes, bloques/inline de código, links (preserva el texto),
   bold/italic, headings, blockquotes.
5. Elimina **URLs**.
6. Elimina **líneas de ruido** (separadores `---`, `===`, etc.).
7. **De-hyphenation**: une palabras cortadas por guion al final de línea (artefacto de PDF).
8. **Une líneas fragmentadas** (artefactos de layout de PDF) con heurísticas (fragmentos cortos,
   inicio en minúscula, section labels, join sin espacio en casos tipo hyphenation).
9. Normaliza whitespace (espacios múltiples, saltos triples → dobles).

| Variable | Default | Descripción |
| --- | --- | --- |
| `TEXT_CLEANER_ACTIVE_TYPE` | `simple` | Tipo de cleaner activo. |
| `TEXT_CLEANER_MAX_TEXT_LENGTH` | `10000000` | Máximo de caracteres; sobre el límite → excepción. |

> Decisión de diseño: la remoción de URLs/emojis/markdown es **lossy a propósito** (optimiza el
> texto para retrieval RAG). Un input vacío/no-str devuelve `""`.
