# backend/app/core/config.py
# Configurações carregadas a partir de variáveis de ambiente.
# Compatível com Pydantic v1 e v2 (usa pydantic-settings se necessário).

from typing import Optional

# Compatibilidade Pydantic v1 / v2 (BaseSettings foi movido para pydantic-settings)
try:
    from pydantic import BaseSettings
except Exception:
    try:
        from pydantic_settings import BaseSettings
    except Exception as e:
        raise ImportError(
            "Não foi possível importar BaseSettings. "
            "Se estiver usando pydantic v2, instale 'pydantic-settings'. "
            "Ou fixe pydantic<2 no requirements.txt. Erro original: " + str(e)
        )

class Settings(BaseSettings):
    # Segurança / JWT
    SECRET_KEY: str = "change-me-in-production"   # sobrescrever com variável de ambiente
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_ALGORITHM: str = "HS256"

    # Banco de dados (exemplo)
    DB_USER: str = "taf_user"
    DB_PASSWORD: str = "senha_segura"
    DB_NAME: str = "taf_db"
    DB_HOST: str = "db"
    DB_PORT: int = 5432

    # URL do frontend (dev)
    VITE_API_URL: str = "http://localhost:8000"

    # Opções extras (se necessário)
    BACKEND_CORS_ORIGINS: Optional[str] = None  # pode ser JSON string ou CSV de origens

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Instância global que os módulos importam
settings = Settings()