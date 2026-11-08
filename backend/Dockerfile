FROM python:3.12-slim AS runtime

# FORWARDED_ALLOW_IPS: proxies de confianza para leer X-Forwarded-For (IP real del cliente en rate limits).
# Solo redes privadas: uvicorn recorre X-Forwarded-For desde la derecha y se queda con la primera IP no
# confiable, asi un cliente no puede falsear su IP anteponiendo valores. No usar "*" (seria falseable).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    FORWARDED_ALLOW_IPS="127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16" \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN python -m pip install --no-cache-dir --upgrade pip uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
