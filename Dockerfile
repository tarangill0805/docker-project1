FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py sample_properties.json ./
COPY templates/ templates/
COPY static/ static/

RUN mkdir -p /app/instance \
    && useradd --system --uid 10001 --no-create-home app \
    && chown app:app /app/instance

USER app

VOLUME ["/app/instance"]
EXPOSE 5000

CMD ["waitress-serve", "--listen=0.0.0.0:5000", "--call", "app:create_app"]
