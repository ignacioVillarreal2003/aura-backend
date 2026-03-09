FROM ollama/ollama:latest

RUN ollama serve & sleep 5 && \
    ollama pull gemma3:1b && \
    ollama pull nomic-embed-text:v1.5 && \
    pkill ollama

CMD ["serve"]
