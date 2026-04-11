FROM ollama/ollama:latest

RUN ollama serve & sleep 5 && \
    ollama pull gemma3:1b && \
    ollama pull qwen3-embedding:0.6b && \
    pkill ollama

CMD ["serve"]