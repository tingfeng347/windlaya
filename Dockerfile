FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv==0.12.3

COPY pyproject.toml uv.lock README.md LICENSE NOTICE ./
COPY app ./app

RUN uv sync --frozen --no-dev --no-editable

ENV PATH="/app/.venv/bin:$PATH"
ENV WINDLAYA_MODEL_ROOT="/models"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
