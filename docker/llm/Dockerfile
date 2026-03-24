FROM ollama/ollama:latest

RUN ollama serve & sleep 5 && \
    ollama pull llama3.1:8b && \
    pkill ollama

CMD ["serve"]
