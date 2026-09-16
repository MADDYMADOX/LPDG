# Matches the interpreter this was developed and tested on, so the pinned
# requirements resolve to the same wheels here as they do locally.
FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/
COPY run.py validate_submission.py ./

# Data is mounted at runtime (see docker-compose.yml) -- never baked into the
# image. The brief is explicit that the data folder is not ours to ship.
ENV DATA_DIR=/app/data
ENV OUT_FILE=/app/predictions.csv

# Same entry point as the local path, so there is one code path to reason
# about. run.py predicts and then runs the official validator; a non-zero exit
# means the file would not be accepted.
CMD ["sh", "-c", "python run.py --no-venv --data \"$DATA_DIR\" --out \"$OUT_FILE\""]
