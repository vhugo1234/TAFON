# -*- coding: utf-8 -*-
"""
Script para verificar e adicionar encoding UTF-8 em todos os arquivos Python
"""
import os
from pathlib import Path

def check_encoding(file_path):
    """Verifica se arquivo tem declaracao de encoding UTF-8"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            second_line = f.readline()
            
            has_encoding = (
                'coding: utf-8' in first_line or
                'coding: utf-8' in second_line
            )
            return has_encoding
    except Exception as e:
        print(f"Erro ao ler {file_path}: {e}")
        return None

def scan_python_files(directory):
    """Escaneia todos os arquivos .py no diretorio"""
    results = []
    for root, dirs, files in os.walk(directory):
        # Ignorar diretorios comuns
        dirs[:] = [d for d in dirs if d not in ['.venv', 'venv', '__pycache__', '.git', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                has_encoding = check_encoding(file_path)
                results.append({
                    'path': file_path,
                    'has_encoding': has_encoding
                })
    
    return results

if __name__ == '__main__':
    print("="*70)
    print("VERIFICANDO ENCODING UTF-8 EM ARQUIVOS PYTHON")
    print("="*70)
    print()
    
    backend_dir = Path(__file__).parent.parent
    results = scan_python_files(backend_dir)
    
    without_encoding = [r for r in results if r['has_encoding'] == False]
    with_encoding = [r for r in results if r['has_encoding'] == True]
    errors = [r for r in results if r['has_encoding'] is None]
    
    print(f"Total de arquivos Python: {len(results)}")
    print(f"  Com encoding UTF-8: {len(with_encoding)}")
    print(f"  Sem encoding UTF-8: {len(without_encoding)}")
    print(f"  Erros de leitura: {len(errors)}")
    print()
    
    if without_encoding:
        print("Arquivos SEM encoding UTF-8:")
        for item in without_encoding:
            rel_path = os.path.relpath(item['path'], backend_dir)
            print(f"  - {rel_path}")
    
    if errors:
        print()
        print("Arquivos com ERRO:")
        for item in errors:
            rel_path = os.path.relpath(item['path'], backend_dir)
            print(f"  - {rel_path}")
    
    print()
    print("="*70)
    
    if without_encoding:
        print(f"ATENCAO: {len(without_encoding)} arquivos precisam de encoding UTF-8!")
    else:
        print("TUDO OK: Todos os arquivos tem encoding UTF-8!")
    
    print("="*70)
