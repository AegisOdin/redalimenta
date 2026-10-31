# syntax=docker/dockerfile:1
FROM python:3.13-slim AS build
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-slim
ARG APP_VERSION=0.0.0
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_VERSION=${APP_VERSION}
RUN groupadd -g 10001 app && useradd -u 10001 -g app -s /usr/sbin/nologin -M app \
 && apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
COPY --from=build /install /usr/local
# pip/setuptools no se usan en ejecución: se eliminan (tratamiento de hallazgos Trivy en paquetes vendorizados)
RUN python -m pip uninstall -y pip setuptools wheel >/dev/null 2>&1 || true; \
    rm -rf /usr/local/lib/python3.13/site-packages/pip* /usr/local/lib/python3.13/site-packages/setuptools* /usr/local/bin/pip*
WORKDIR /app
COPY --chown=root:root alembic.ini ./
COPY --chown=root:root migrations ./migrations
COPY --chown=root:root app ./app
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
