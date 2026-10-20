# 中文注释：Dockerfile
FROM rust:1.96-slim AS builder
ENV LANG=C.UTF-8
WORKDIR /app
COPY . .
RUN cargo build --release --locked

FROM debian:bookworm-slim
COPY --from=builder /app/target/release/mdview /usr/local/bin/mdview
EXPOSE 8000
CMD ["mdview", "--root", "/docs", "--host", "0.0.0.0"]
