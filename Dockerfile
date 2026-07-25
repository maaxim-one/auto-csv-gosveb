FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY routes ./routes
COPY templates ./templates
COPY static ./static
COPY wsgi.py .

RUN useradd --create-home appuser
RUN mkdir -p /app/storage && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

ENV FLASK_DEBUG=0
ENV SECRET_KEY=change-me-in-production

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "wsgi:app"]
