# -*- coding: utf-8 -*-
# backend/app/utils/csv_parser.py
# Robust CSV parsing for candidate import:
# - auto-detect encoding & delimiter
# - handle header-in-single-cell cases produced by Excel
# - case-insensitive header matching with common synonyms (pt/en)
# - normalize names and CPF (digits-only)
# - DO NOT perform CPF check-digit validation (per request)

import csv
import io
import re
import unicodedata
from typing import Tuple, List, Dict, Any, Optional
from fastapi import UploadFile

# Small words to keep lowercase in title-cased names
SMALL_WORDS = {
    'da', 'de', 'do', 'das', 'dos', 'e', 'van', 'von', 'y', 'la', 'el', 'le', 'du', 'di'
}

# Header synonyms -> canonical key
HEADER_SYNONYMS = {
    'full_name': {'full_name', 'name', 'nome', 'nome_completo', 'full name', 'nome completo'},
    'cpf': {'cpf', 'c.p.f', 'document', 'documento'},
    'registration_number': {'registration_number', 'registration', 'inscription', 'inscricao', 'numero_inscricao', 'matricula'},
    'gender': {'gender', 'sexo', 'sex'},
    'batch_name': {'batch_name', 'batch', 'turma', 'group', 'grupo'}
}

EXPECTED_KEYS = ['full_name', 'cpf', 'registration_number', 'gender']  # batch_name is optional

def only_digits(s: Optional[str]) -> str:
    if not s:
        return ""
    try:
        s_norm = unicodedata.normalize('NFKC', str(s))
    except Exception:
        s_norm = str(s)
    return re.sub(r"\D", "", s_norm)

def normalize_whitespace(s: str) -> str:
    return re.sub(r'\s+', ' ', s.strip())

def normalize_name(raw: Optional[str]) -> str:
    if not raw:
        return ""
    try:
        s = unicodedata.normalize('NFKC', str(raw))
    except Exception:
        s = str(raw)
    s = normalize_whitespace(s)
    if s == "":
        return ""
    # If letters only are all uppercase, convert to title case with small-word handling.
    letters = re.sub(r'[^A-Za-z\u00C0-\u017F]', '', s)
    if letters and letters.upper() == letters:
        parts = s.lower().split(' ')
        parts = [p for p in parts if p != '']
        for i in range(len(parts)):
            if i != 0 and i != len(parts) - 1 and parts[i] in SMALL_WORDS:
                parts[i] = parts[i].lower()
            else:
                parts[i] = parts[i].capitalize()
        return ' '.join(parts)
    return s

def detect_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
        return dialect.delimiter
    except Exception:
        comma_count = sample.count(',')
        semicolon_count = sample.count(';')
        tab_count = sample.count('\t')
        if tab_count >= comma_count and tab_count >= semicolon_count:
            return '\t'
        if semicolon_count > comma_count:
            return ';'
        return ','

def map_headers_to_keys(headers: List[str]) -> Dict[str, str]:
    hdr_map: Dict[str, str] = {}
    low_headers = {h.strip().lower(): h for h in headers}
    for key, synonyms in HEADER_SYNONYMS.items():
        for candidate_lower, original in low_headers.items():
            cand = re.sub(r'[^a-z0-9]', '', candidate_lower)
            matched = False
            for syn in synonyms:
                syn_clean = re.sub(r'[^a-z0-9]', '', syn.lower())
                if cand == syn_clean:
                    hdr_map[key] = original
                    matched = True
                    break
            if matched:
                break
    return hdr_map

async def parse_candidates_csv(file: UploadFile) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    content = await file.read()

    # decode with fallbacks
    text = None
    for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            text = content.decode(enc)
            break
        except Exception:
            text = None
    if text is None:
        text = content.decode('latin-1', errors='replace')

    sample_lines = text.splitlines()[:20]
    sample = '\n'.join(sample_lines) if sample_lines else text[:1024]
    delimiter = detect_delimiter(sample)

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    raw_headers = list(reader.fieldnames or [])
    headers = [h.strip() for h in raw_headers]

    # Handle header-in-single-cell (Excel regional issue)
    if len(headers) == 1 and (',' in headers[0] or ';' in headers[0] or '\t' in headers[0]):
        raw_header = headers[0]
        guessed_sep = '\t' if '\t' in raw_header and raw_header.count('\t') >= max(raw_header.count(','), raw_header.count(';')) else \
                      (';' if raw_header.count(';') > raw_header.count(',') else ',')
        all_rows = list(csv.reader(io.StringIO(text), delimiter=guessed_sep))
        if not all_rows:
            return [], [{'row_number': 0, 'field': 'header', 'error': 'Unable to parse CSV header/rows.'}]
        parsed_headers = [h.strip() for h in all_rows[0]]
        data_rows = []
        for r in all_rows[1:]:
            if len(r) < len(parsed_headers):
                r = r + [''] * (len(parsed_headers) - len(r))
            row_dict = {parsed_headers[i]: r[i].strip() for i in range(min(len(parsed_headers), len(r)))}
            data_rows.append(row_dict)
    else:
        data_rows = [ {h: (row.get(h) if row is not None else '') for h in headers} for row in reader ]

    detected_headers = list(data_rows[0].keys()) if data_rows else headers
    header_map = map_headers_to_keys(detected_headers)

    missing_required = [k for k in EXPECTED_KEYS if k not in header_map]
    if missing_required:
        low_detected = {h.strip().lower(): h for h in detected_headers}
        for key in EXPECTED_KEYS:
            if key in header_map:
                continue
            for dh_lower, dh_original in low_detected.items():
                if key.replace('_',' ') in dh_lower or key in dh_lower:
                    header_map[key] = dh_original
                    break
        missing_required = [k for k in EXPECTED_KEYS if k not in header_map]
    if missing_required:
        return [], [{
            'row_number': 0,
            'field': 'header',
            'error': f'Missing required columns (could not identify): {missing_required}. Detected headers: {detected_headers}'
        }]

    valid_candidates: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    row_number = 1
    for raw_row in data_rows:
        row_number += 1
        try:
            def get_val(key: str) -> str:
                hdr = header_map.get(key)
                if not hdr:
                    return ''
                return (raw_row.get(hdr) or '').strip()

            raw_full = get_val('full_name')
            raw_cpf = get_val('cpf')
            raw_reg = get_val('registration_number')
            raw_gender = get_val('gender')
            raw_batch = get_val('batch_name') if 'batch_name' in header_map else ''

            full_name = normalize_name(raw_full)
            cpf = only_digits(raw_cpf)
            registration_number = str(raw_reg).strip()
            gender = str(raw_gender).strip().upper()

            if not full_name:
                errors.append({'row_number': row_number, 'field': 'full_name', 'error': 'full_name missing', 'raw': raw_row})
                continue
            if not cpf:
                errors.append({'row_number': row_number, 'field': 'cpf', 'error': 'cpf missing', 'raw': raw_row})
                continue
            if not registration_number:
                errors.append({'row_number': row_number, 'field': 'registration_number', 'error': 'registration_number missing', 'raw': raw_row})
                continue
            if gender not in ('M', 'F'):
                errors.append({'row_number': row_number, 'field': 'gender', 'error': f"Invalid gender: '{raw_gender}'. Use 'M' or 'F'.", 'raw': raw_row})
                continue

            candidate_obj: Dict[str, Any] = {
                'full_name': full_name,
                'cpf': cpf,
                'registration_number': registration_number,
                'gender': gender,
            }
            if raw_batch:
                candidate_obj['batch_name'] = raw_batch

            valid_candidates.append(candidate_obj)
        except Exception as ex:
            errors.append({'row_number': row_number, 'field': 'row', 'error': f'Unexpected error parsing row: {ex}', 'raw_row': raw_row})
            continue

    return valid_candidates, errors

def generate_sample_csv() -> str:
    """
    Simple CSV sample generator used by endpoints/tests.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['full_name', 'cpf', 'registration_number', 'gender'])
    writer.writerow(['Joao Silva', '52998224725', '1001', 'M'])
    writer.writerow(['Maria Souza', '39833144820', '1002', 'F'])
    writer.writerow(['Carlos Pereira', '11144477735', '1003', 'M'])
    return output.getvalue()