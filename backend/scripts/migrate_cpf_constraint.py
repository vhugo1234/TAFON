#!/usr/bin/env python3
"""
Script de migração: Remove constraint UNIQUE global do CPF e adiciona constraint composta (cpf, event_id).
Isso permite que o mesmo CPF participe de múltiplos eventos TAF.

Execute: python backend/scripts/migrate_cpf_constraint.py
"""

import sys
import os
from pathlib import Path

# Adiciona o diretório backend ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from app.db.connection import engine, SessionLocal
from app.db.models.public import Tenant

def get_all_tenant_schemas():
    """Retorna lista de todos os schemas de tenants"""
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        return [t.schema_name for t in tenants]
    finally:
        db.close()

def migrate_schema(schema_name: str):
    """Migra um schema específico"""
    print(f"\n?? Migrando schema: {schema_name}")
    
    with engine.begin() as conn:
        # Define search_path
        conn.execute(text(f'SET search_path TO "{schema_name}"'))
        
        # Verifica se a tabela existe
        inspector = inspect(conn)
        if 'candidates' not in inspector.get_table_names(schema=schema_name):
            print(f"   ??  Tabela 'candidates' não existe - ignorando")
            return
        
        # 1. Remove constraint UNIQUE antiga se existir
        try:
            conn.execute(text("""
                ALTER TABLE candidates 
                DROP CONSTRAINT IF EXISTS ix_candidates_cpf
            """))
            print(f"   ? Constraint UNIQUE global removida")
        except Exception as e:
            print(f"   ??  Erro ao remover constraint (pode já estar removida): {e}")
        
        # 2. Remove índice único antigo se existir
        try:
            conn.execute(text("""
                DROP INDEX IF EXISTS ix_candidates_cpf
            """))
            print(f"   ? Índice único global removido")
        except Exception as e:
            print(f"   ??  Erro ao remover índice: {e}")
        
        # 3. Cria índice composto UNIQUE (cpf, event_id) se não existir
        try:
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS ix_candidates_cpf_event 
                ON candidates (cpf, event_id)
            """))
            print(f"   ? Índice composto (cpf, event_id) criado")
        except Exception as e:
            print(f"   ? Erro ao criar índice composto: {e}")
            raise
        
        # 4. Cria índice simples para busca por CPF (não-único)
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_candidates_cpf_search 
                ON candidates (cpf)
            """))
            print(f"   ? Índice de busca por CPF criado")
        except Exception as e:
            print(f"   ??  Erro ao criar índice de busca: {e}")

def main():
    print("=" * 70)
    print("?? MIGRAÇÃO: CPF Único por Evento")
    print("=" * 70)
    print("\nEsta migração:")
    print("  1. Remove constraint UNIQUE global do CPF")
    print("  2. Adiciona constraint UNIQUE composta (cpf, event_id)")
    print("  3. Permite que mesmo CPF participe de múltiplos eventos")
    print("\n" + "=" * 70)
    
    try:
        # Busca todos os schemas de tenants
        schemas = get_all_tenant_schemas()
        print(f"\n?? Encontrados {len(schemas)} schemas para migrar:")
        for schema in schemas:
            print(f"   - {schema}")
        
        confirm = input("\n??  Continuar com a migração? (s/N): ").strip().lower()
        if confirm != 's':
            print("\n? Migração cancelada pelo usuário")
            return
        
        # Migra cada schema
        success_count = 0
        for schema in schemas:
            try:
                migrate_schema(schema)
                success_count += 1
            except Exception as e:
                print(f"\n? ERRO ao migrar schema '{schema}': {e}")
                import traceback
                traceback.print_exc()
        
        print("\n" + "=" * 70)
        print(f"? Migração concluída!")
        print(f"   • Schemas migrados com sucesso: {success_count}/{len(schemas)}")
        print("=" * 70)
        
        if success_count < len(schemas):
            print("\n??  Alguns schemas falharam. Verifique os erros acima.")
            sys.exit(1)
        
    except Exception as e:
        print(f"\n? ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
