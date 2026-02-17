# debug_cpf.py
# Executar: python3 debug_cpf.py caminho/para/modelo_candidatos.csv
import csv
import sys
import unicodedata
import re

def only_digits_nfkc(s):
    if s is None:
        return ""
    try:
        s_norm = unicodedata.normalize("NFKC", s)
    except Exception:
        s_norm = s
    return re.sub(r"\D", "", s_norm)

def validate_cpf(cpf: str) -> bool:
    cpf = ''.join(filter(str.isdigit, cpf or ""))
    if len(cpf) != 11:
        return False
    if cpf == cpf[0] * 11:
        return False
    def calc(t):
        s = 0
        for i in range(t - 1):
            s += int(cpf[i]) * (t - i)
        d = 11 - (s % 11)
        return 0 if d >= 10 else d
    d1 = calc(10)
    d2 = calc(11)
    try:
        return d1 == int(cpf[9]) and d2 == int(cpf[10])
    except Exception:
        return False

def show_codepoints(s):
    return " ".join(f"U+{ord(ch):04X}" for ch in s)

if len(sys.argv) < 2:
    print("Uso: python3 debug_cpf.py arquivo.csv")
    sys.exit(1)

path = sys.argv[1]
with open(path, "rb") as fh:
    raw = fh.read()
# try decodings
for enc in ("utf-8-sig", "utf-8", "latin-1"):
    try:
        text = raw.decode(enc)
        used_enc = enc
        break
    except Exception:
        text = None
if text is None:
    print("Não foi possível decodificar o arquivo. Tente salvar como UTF-8.")
    sys.exit(2)

print("Arquivo decodificado com:", used_enc)
reader = csv.reader(text.splitlines())
rows = list(reader)
if not rows:
    print("CSV vazio")
    sys.exit(0)

headers = [h.strip() for h in rows[0]]
print("Headers detectados:", headers)
# try to find CPF column
cpf_idx = None
for i,h in enumerate(headers):
    if h.lower() == "cpf" or "cpf" in h.lower():
        cpf_idx = i
        break
if cpf_idx is None:
    print("Não detectei coluna 'cpf' nos headers. Headers:", headers)
    sys.exit(1)

print("\nProcessando linhas (mostrando até 200 linhas):\n")
print(f"{'row':>4} | {'raw value (repr)':<40} | {'normalized':<15} | len | valid | codepoints (sample) ")
print("-"*120)
for i, row in enumerate(rows[1:], start=2):
    if len(row) <= cpf_idx:
        rawcpf = ""
    else:
        rawcpf = row[cpf_idx]
    rawrepr = repr(rawcpf)
    norm = only_digits_nfkc(rawcpf)
    valid = validate_cpf(norm)
    cps = show_codepoints(rawcpf)
    print(f"{i:4} | {rawrepr[:40]:<40} | {norm:<15} | {len(norm):>3} | {str(valid):>5} | {cps[:80]}")
    if i >= 201:
        break