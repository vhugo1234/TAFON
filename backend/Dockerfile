# ----------------------------------------------------
# STAGE 1: BUILD (Instalação de dependências)
# ----------------------------------------------------
FROM python:3.11-slim AS builder
WORKDIR /app

# Instala ferramentas de build e libpq-dev para compilar pacotes nativos
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e instala dependências em /install (prefix),
# assim evitamos copiar /usr/local/bin do builder diretamente.
COPY requirements.txt .
RUN python -m pip install --upgrade pip
RUN python -m pip install --no-cache-dir --prefix=/install -r requirements.txt

# ----------------------------------------------------
# STAGE 2: RUNTIME (imagem final mais limpa)
# ----------------------------------------------------
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala apenas pacotes runtime necessários
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

# Copia as dependências instaladas pelo builder para /usr/local
COPY --from=builder /install /usr/local

# Cria um usuário não-root para rodar a aplicação e os diretórios esperados
RUN useradd --create-home appuser \
    && mkdir -p /app/uploads /app/static /app/static/imagens /app/static/logos /app/logs \
    && chown -R appuser:appuser /app /app/uploads /app/static /app/logs

# Copia o código da aplicação definindo propriedade para appuser
COPY --chown=appuser:appuser . /app

USER appuser

# TEMPORARY FIX: Create static directories and set ownership to avoid permission issues
RUN mkdir -p /app/static/imagens /app/static/logos /app/uploads \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Comando padrão — docker-compose pode sobrescrever para rodar migrações antes
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]