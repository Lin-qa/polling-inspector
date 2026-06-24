FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY inspector ./inspector

CMD ["python", "main.py", "run", "--config", "/app/config/巡检配置.xlsx", "--log-file", "/app/logs/inspection.log"]

