# ---------- 阶段1: Node 编译 Vue ----------
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# ---------- 阶段2: Python 运行 ----------
FROM python:3.11-slim
RUN pip install --no-cache-dir --index-url https://mirrors.aliyun.com/pypi/simple/ aiohttp
WORKDIR /app
COPY --from=builder /app/dist/ /app/dist/
COPY proxy.py /app/proxy.py
EXPOSE 80
CMD ["python", "/app/proxy.py"]
