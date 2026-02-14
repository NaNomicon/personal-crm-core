FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y wget gzip && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir -p /var/lib/cozo

RUN wget https://github.com/cozodb/cozo/releases/download/v0.7.6/cozo-0.7.6-x86_64-unknown-linux-gnu.gz \
    && gunzip cozo-0.7.6-x86_64-unknown-linux-gnu.gz \
    && mv cozo-0.7.6-x86_64-unknown-linux-gnu cozo \
    && chmod +x cozo

EXPOSE 9070

ENTRYPOINT ["./cozo"]
CMD ["server", "--engine=sqlite", "--bind=0.0.0.0", "--port=9070", "--path=/var/lib/cozo/storage"]
