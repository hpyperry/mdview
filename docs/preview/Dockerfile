# 中文注释：Dockerfile
FROM python:3.12-slim AS builder
ENV LANG=C.UTF-8
WORKDIR /app
COPY mdview.py ./
RUN echo "中文构建步骤"
EXPOSE 8000
CMD ["python3", "mdview.py"]
