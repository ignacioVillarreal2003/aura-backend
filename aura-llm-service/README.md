# Aura llm service

## Variables de Entorno

El servicio utiliza dos variables de entorno:

```env
OLLAMA_URL="..."
MODEL_NAME="..."
```

### Uso según el entorno

#### Entorno local

Crear un archivo `.env` en la raíz del proyecto:

```env
OLLAMA_URL="http://localhost:11434"
MODEL_NAME="gemma3:1b"
```

#### Entorno Docker

Crear un archivo `.env.docker`:

```env
OLLAMA_URL="http://llm:11434"
MODEL_NAME="gemma3:1b"
```