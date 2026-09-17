FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BN_CACHE_DIR=/data/rules BN_SESSION_DIR=/data/sessions BN_CASE_DIR=/data/cases
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data && python -m pytest -q -x tests/test_rules_parser.py tests/test_schema_and_api.py
EXPOSE 8000
VOLUME ["/data"]
CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
