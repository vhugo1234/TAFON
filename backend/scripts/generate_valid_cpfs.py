# -*- coding: utf-8 -*-
"""
Gerador de CPFs válidos para testes
"""

import random

def generate_valid_cpf():
    """Gera um CPF válido aleatoriamente"""
    # Gera 9 primeiros dígitos
    cpf = [random.randint(0, 9) for _ in range(9)]
    
    # Calcula primeiro dígito verificador
    sum_first = sum((10 - i) * cpf[i] for i in range(9))
    remainder_first = sum_first % 11
    first_digit = 0 if remainder_first < 2 else 11 - remainder_first
    cpf.append(first_digit)
    
    # Calcula segundo dígito verificador
    sum_second = sum((11 - i) * cpf[i] for i in range(10))
    remainder_second = sum_second % 11
    second_digit = 0 if remainder_second < 2 else 11 - remainder_second
    cpf.append(second_digit)
    
    return ''.join(map(str, cpf))

# Gera 6 CPFs válidos
print("CPFs VALIDOS GERADOS:")
print("="*70)
print()

names = [
    "Joao Silva",
    "Maria Souza", 
    "Carlos Pereira",
    "Ana Costa",
    "Pedro Santos",
    "Julia Lima"
]

print("full_name,cpf,registration_number,gender")
for i, name in enumerate(names, 1):
    cpf = generate_valid_cpf()
    gender = 'M' if i % 2 == 1 else 'F'
    print(f"{name},{cpf},100{i},{gender}")

print()
print("="*70)
