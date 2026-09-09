FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/
COPY validate_submission.py .

# Data is mounted at runtime (see docker-compose.yml) -- never baked into the
# image. The brief is explicit that the data folder is not ours to ship.
ENV DATA_DIR=/app/data
ENV OUT_FILE=/app/predictions.csv

CMD ["sh", "-c", "python -m src.predict --data \"$DATA_DIR\" --out \"$OUT_FILE\" && python validate_submission.py \"$OUT_FILE\""]
