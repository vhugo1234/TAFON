-- Script SQL para adicionar coluna batch_number em todas as tabelas candidates dos schemas tenants
-- Execute este script manualmente no PostgreSQL

-- Para o schema padrao (ajustar nome conforme necessario)
DO $$
DECLARE
    schema_rec RECORD;
BEGIN
    -- Loop em todos os schemas que contem tabela candidates
    FOR schema_rec IN 
        SELECT DISTINCT table_schema 
        FROM information_schema.tables 
        WHERE table_name = 'candidates' 
        AND table_schema NOT IN ('pg_catalog', 'information_schema')
    LOOP
        -- Verifica se a coluna ja existe
        IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_schema = schema_rec.table_schema 
            AND table_name = 'candidates' 
            AND column_name = 'batch_number'
        ) THEN
            -- Adiciona a coluna
            EXECUTE format('ALTER TABLE %I.candidates ADD COLUMN batch_number INTEGER', schema_rec.table_schema);
            RAISE NOTICE 'Coluna batch_number adicionada em %.candidates', schema_rec.table_schema;
        ELSE
            RAISE NOTICE 'Coluna batch_number ja existe em %.candidates', schema_rec.table_schema;
        END IF;
    END LOOP;
END$$;
