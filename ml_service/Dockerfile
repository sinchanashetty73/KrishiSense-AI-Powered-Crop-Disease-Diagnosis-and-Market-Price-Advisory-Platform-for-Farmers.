FROM python:3.11-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MODELS_DIR=/models
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8001
# Models are NOT baked into the image: they are mounted at /models (see docker-compose.yml)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
