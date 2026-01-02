from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os

# Exemplo: ler URL do env (recomenda-se usar var de ambiente)
DATABASE_URL = os.getenv("DATABASE_URL", os.getenv("SQLALCHEMY_DATABASE_URI", "postgresql://tafon_user:tafon123456@db:5432/tafon_central_db"))

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)

def get_db() -> Generator[Session, None, None]:
    """
    Dependência do FastAPI para obter sessão do SQLAlchemy.
    Uso nos endpoints: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()