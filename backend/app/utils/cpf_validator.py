# -*- coding: utf-8 -*-
# backend/app/utils/cpf_validator.py

import re
import unicodedata
from typing import Optional


def normalize_cpf(raw: Optional[str]) -> str:
    """
    Normaliza um CPF bruto:
    - aplica Unicode NFKC para normalizar dígitos fullwidth e similares
    - remove todos os caracteres não-dígitos
    - retorna string com apenas dígitos
    """
    if raw is None:
        return ""
    # força str
    s = str(raw).strip()
    if not s:
        return ""
    try:
        s = unicodedata.normalize("NFKC", s)
    except Exception:
        # fallback se normalize falhar por algum motivo
        s = s
    # remove tudo que não for dígito
    s = re.sub(r"\D", "", s)
    return s


def clean_cpf(cpf: Optional[str]) -> str:
    """
    Alias para normalize_cpf (mantém compatibilidade).
    """
    return normalize_cpf(cpf)


def validate_cpf(raw: Optional[str]) -> bool:
    """
    Valida um CPF brasileiro usando o algoritmo dos dígitos verificadores.
    Aceita entrada em vários formatos (com pontos/traço, com espaços, fullwidth digits, etc).
    Retorna True se válido, False caso contrário.
    """
    cpf = normalize_cpf(raw)

    # Deve ter 11 dígitos
    if len(cpf) != 11:
        return False

    # Rejeita sequências iguais (11111111111, etc.)
    if cpf == cpf[0] * 11:
        return False

    # cálculo dos dígitos verificadores
    def _calc_digit(sequence: str, factor_start: int) -> int:
        total = 0
        factor = factor_start
        for ch in sequence:
            total += int(ch) * factor
            factor -= 1
        mod = total % 11
        digit = 0 if mod < 2 else 11 - mod
        return digit

    try:
        d1 = _calc_digit(cpf[:9], 10)
        d2 = _calc_digit(cpf[:9] + str(d1), 11)
    except Exception:
        return False

    return cpf[-2:] == f"{d1}{d2}"


def format_cpf(raw: Optional[str]) -> str:
    """
    Formata CPF para XXX.XXX.XXX-XX se possível; se não houver 11 dígitos, retorna a string limpa.
    """
    cpf = normalize_cpf(raw)
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


# Testes rápidos para debug
if __name__ == "__main__":
    examples = [
        "52998224725",            # already digits
        "529.982.247-25",         # formatted
        "529 982 247 25",         # spaces
        "５２９９８２２４７２５",    # fullwidth digits (Japanese fullwidth)
        "111.111.111-11",         # repeated digits -> invalid
        "12345678909",            # invalid check digits example
        None,
        ""
    ]

    print("\n" + "="*70)
    print("DEBUG CPF VALIDATION")
    print("="*70)
    for raw in examples:
        norm = normalize_cpf(raw)
        valid = validate_cpf(raw)
        formatted = format_cpf(raw)
        print(f"RAW: {repr(raw):20} | NORM: {norm:11} | VALID: {valid} | FORMATTED: {formatted}")
    print("="*70 + "\n")