from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import os

# Exemplo: ler URL do env (recomenda-se usar var de ambiente)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("SQLALCHEMY_DATABASE_URI", "postgresql://tafon_user:tafon123456@db:5432/tafon_central_db")
)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)

# Expor Base para uso em scripts que precisam criar tabelas (Base.metadata.create_all)
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    Dependência do FastAPI para obter sessão do SQLAlchemy.
    Esta versão garante rollback() automaticamente se uma exceção ocorrer
    durante a requisição, evitando que a mesma Session fique em estado
    'aborted' e cause erros subsequentes.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        db.close()