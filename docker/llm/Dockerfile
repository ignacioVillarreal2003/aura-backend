FROM ollama/ollama:0.30.0-rc23

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
COPY healthcheck.sh /healthcheck.sh
RUN sed -i 's/\r$//' /entrypoint.sh /healthcheck.sh && chmod +x /entrypoint.sh /healthcheck.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]
