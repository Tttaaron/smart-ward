FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

COPY src/ ./src/

RUN mkdir -p /app/data

WORKDIR /app/src

CMD ["python", "main.py"]
