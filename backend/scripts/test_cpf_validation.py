# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
Script para testar validação de CPFs específicos
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.cpf_validator import validate_cpf

# CPFs do usuário
cpfs = [
    ("52998224725", "Joao Silva"),
    ("39833144820", "Maria Souza"),
    ("11144477735", "Carlos Pereira"),
    ("05987701895", "Ana Costa"),
    ("71728172740", "Pedro Santos"),
    ("13822685830", "Julia Lima"),
]

print("="*70)
print("TESTANDO VALIDACAO DE CPFs")
print("="*70)
print()

valid = 0
invalid = 0

for cpf, nome in cpfs:
    ok = validate_cpf(cpf)
    status = "VALIDO" if ok else "INVALIDO"
    symbol = "OK" if ok else "ERRO"
    
    print(f"[{symbol}] {cpf} - {nome} - {status}")
    
    if ok:
        valid += 1
    else:
        invalid += 1

print()
print("="*70)
print(f"RESULTADO: {valid} validos | {invalid} invalidos")
print("="*70)
