FROM ollama/ollama:latest

RUN ollama serve & sleep 5 && \
    ollama pull gemma3:1b && \
    pkill ollama

CMD ["serve"]
