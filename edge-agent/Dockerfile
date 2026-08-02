FROM python:3.11-slim

WORKDIR /app

ARG INSTALL_YOLO=false
ARG INSTALL_LLM=false

COPY requirements.txt .
RUN pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

COPY requirements-yolo.txt .
RUN if [ "$INSTALL_YOLO" = "true" ]; then \
      pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ -r requirements-yolo.txt; \
    fi

COPY requirements-llm.txt .
RUN if [ "$INSTALL_LLM" = "true" ]; then \
      pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ -r requirements-llm.txt; \
    fi

COPY src/ ./src/

RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1

WORKDIR /app/src

CMD ["python", "main.py"]
