FROM ollama/ollama:latest

RUN ollama serve & sleep 5 && \
    ollama pull gemma3:1b && \
    ollama pull nomic-embed-text:v1.5 && \
    pkill ollama

CMD ["serve"]ø

'''
ollama pull gemma3:1b
ollama pull gemma3:4b
ollama pull qwen3:4b
ollama pull cogito:3b
ollama pull llama3.2:3b
ollama pull mistral:7b

ollama pull nomic-embed-text:v1.5
ollama pull qwen3-embedding:4b
ollama pull embeddinggemma:300m
ollama pull nomic-embed-text-v2-moe
ollama pull mxbai-embed-large:335m
'''