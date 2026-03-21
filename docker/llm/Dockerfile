FROM ollama/ollama:latest

RUN ollama serve & sleep 5 && \
    ollama pull gemma3:1b && \
    ollama pull qwen3-embedding:4b && \
    pkill ollama

CMD ["serve"]
