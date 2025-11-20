# Aura LLM Service

## Variables de Entorno

### Entorno local

Crear un archivo `.env` en la raíz del proyecto con todas las variables:

```env
OLLAMA_URL=http://localhost:11434
MODEL_NAME=gemma3:1b
```

### Entorno Docker

Crear un archivo `.env.docker` con las variables adaptadas a los servicios de Docker:

```env
OLLAMA_URL=http://llm:11434
MODEL_NAME=gemma3:1b
```