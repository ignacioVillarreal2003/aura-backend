# Modelos para Ollama

Para poder utilizarlos en entorno local o Docker, primero hay que descargarlos usando el comando:

```bash
ollama pull <nombre_del_modelo>
```

| Nombre                | Tamaño  | Parámetros | Contexto | Notas                                                                                  |
| --------------------- | ------- | ---------- | -------- | -------------------------------------------------------------------------------------- |
| deepseek-r1:8b        | 5.2 GB  | 8B         | 128K     | Razonamiento sólido, bueno para tareas complejas.                                      |
| deepseek-r1:1.5b      | 1.1 GB  | 1.5B       | 128K     | Liviano, rápido, útil para pruebas y tareas simples.                                   |
| gemma3:4b             | 3.3 GB  | 4B         | 128K     | Multimodal (texto + imagen), rápido y eficiente.                                       |
| gemma3:12b            | 8.1 GB  | 12B        | 128K     | Potente, ideal para proyectos más exigentes; puede necesitar cuantización en 8GB VRAM. |
| qwen3:4b              | 2.5 GB  | 4B         | 256K     | Muy bueno para reasoning y código, bajo consumo de memoria.                            |
| qwen3:8b              | 5.2 GB  | 8B         | 40K      | Excelente para código, matemáticas y tareas complejas.                                 |
| llama3.1:8b           | 4.9 GB  | 8B         | 128K     | Estable y equilibrado, buena opción general.                                           |
| mistral:7b            | 4.4 GB  | 7B         | 32K      | Liviano y rápido, competitivo con modelos mayores en inglés.                           |
| deepseek-r1:8b-q4_K_M | ~4.5 GB | 8B         | 128K     | Mantiene buena calidad con VRAM limitada; razonamiento sólido.                         |
| qwen3:7b-q4_K_M       | ~3.8 GB | 7B         | 40K      | Muy rápido y eficiente; excelente para código y tareas complejas.                      |
| gemma3:12b-q4_K_M     | ~5.2 GB | 12B        | 128K     | Corre en 8GB VRAM sin problemas; multimodal texto + imagen.                            |
