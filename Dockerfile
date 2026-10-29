FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm config set registry https://registry.npmmirror.com && npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r backend/requirements.txt
COPY backend/ ./backend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
