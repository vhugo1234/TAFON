# backend/Dockerfile

# ----------------------------------------------------
# STAGE 1: BUILD (Instalação de dependências e compilação)
# ----------------------------------------------------
FROM python:3.11-slim as builder
WORKDIR /app

# Instala ferramentas de build e libpq-dev para compilar o driver de banco de dados
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------
# STAGE 2: FINAL (Imagem de produção mais limpa e menor)
# ----------------------------------------------------
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala apenas as bibliotecas de runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

# COPIA AS DEPENDÊNCIAS INSTALADAS (INCLUINDO ALEMBIC)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copia o restante do código da aplicação
COPY . /app 

# TEMPORARY FIX: Create static directories and set ownership to avoid permission issues
RUN mkdir -p /app/static/imagens /app/static/logos /app/uploads \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# O comando será executado pelo docker-compose.yml (com `python -m alembic`)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]