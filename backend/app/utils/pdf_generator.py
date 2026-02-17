# backend/app/utils/pdf_generator.py
import io
import os
import tempfile
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as PlatypusImage
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageOps
import logging

logger = logging.getLogger(__name__)

# Se precisar de settings, importe de forma segura:
try:
    from app.core.config import settings as _app_settings
except Exception:
    _app_settings = None

# Try to import requests, but fallback to urllib if not installed
try:
    import requests
    _HAS_REQUESTS = True
except Exception:
    import urllib.request
    _HAS_REQUESTS = False

PAGE_WIDTH, PAGE_HEIGHT = A4


def format_cpf_safe(cpf_str):
    if not cpf_str:
        return ""
    cpf_str = str(cpf_str)
    if len(cpf_str) == 11 and cpf_str.isdigit():
        p1 = cpf_str[0:3]
        p2 = cpf_str[3:6]
        p3 = cpf_str[6:9]
        p4 = cpf_str[9:11]
        formatted = p1 + "." + p2 + "." + p3 + "-" + p4
        return formatted
    return cpf_str


def prepare_image_for_reportlab(path_or_file):
    """
    Abre uma imagem (path string, bytes ou file-like), detecta se tem alpha/transparência
    e, se necessário, converte para RGB com fundo branco. Retorna um BytesIO com PNG RGB
    pronto para ser passado ao reportlab.lib.utils.ImageReader.

    Retorna None em caso de falha.
    """
    try:
        # Abrir via Pillow: aceita path string ou file-like/bytes
        if isinstance(path_or_file, (bytes, bytearray)):
            stream = io.BytesIO(path_or_file)
            img = Image.open(stream)
        elif hasattr(path_or_file, "read"):
            img = Image.open(path_or_file)
        else:
            # assume path string
            img = Image.open(path_or_file)

        # Força carregamento (algumas imagens lazy-load)
        img.load()

        # Normalizar modos com transparência -> compor sobre fundo branco
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            # Converter paletted 'P' primeiro para RGBA
            if img.mode == "P":
                img = img.convert("RGBA")

            # Criar fundo branco
            bg = Image.new("RGB", img.size, (255, 255, 255))
            # Colar usando canal alpha como máscara
            alpha = img.split()[-1]
            bg.paste(img.convert("RGBA"), mask=alpha)
            out_img = bg
        else:
            # Sem alpha: garantir RGB (ReportLab funciona melhor com RGB)
            if img.mode != "RGB":
                out_img = img.convert("RGB")
            else:
                out_img = img

        out = io.BytesIO()
        # Salva como PNG RGB — PNG mantém qualidade e é aceito pelo ImageReader
        out_img.save(out, format="PNG")
        out.seek(0)
        return out

    except Exception:
        logger.exception("prepare_image_for_reportlab: falha ao preparar imagem %r", getattr(path_or_file, "__str__", lambda: path_or_file)())
        return None


# ---------------------
# Logo resolver helper
# ---------------------
def _resolve_logo_path(path_or_url: Optional[str]) -> Tuple[Optional[str], bool]:
    """
    Resolve `path_or_url` para um caminho local, tentando várias estratégias:
      - se for URL http(s): baixa para arquivo temporário -> retorna (tmp_path, True)
      - tenta o caminho tal como recebido
      - tenta caminho relativo ao cwd
      - tenta prefixar 'backend/app/' e '/app/backend/app/' (ambientes containerizados)
      - se começa com '/static/' tenta mapear para 'static/' e 'backend/app/static/'
      - retorna (None, False) se não resolver
    Retorna (resolved_path, is_temp)
    """
    if not path_or_url:
        logger.debug("[_resolve_logo_path] input empty")
        return None, False

    s = str(path_or_url).strip()
    logger.debug("[_resolve_logo_path] attempting to resolve: %r", s)

    # 1) remote URL
    if s.startswith('http://') or s.startswith('https://'):
        logger.debug("[_resolve_logo_path] detected URL, attempting download: %s", s)
        try:
            suffix = os.path.splitext(s)[1] or '.png'
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp_path = tmp.name
            tmp.close()
            if _HAS_REQUESTS:
                resp = requests.get(s, timeout=10)
                resp.raise_for_status()
                with open(tmp_path, 'wb') as f:
                    f.write(resp.content)
            else:
                import urllib.request
                with urllib.request.urlopen(s, timeout=10) as resp:
                    with open(tmp_path, 'wb') as f:
                        shutil.copyfileobj(resp, f)
            logger.debug("[_resolve_logo_path] downloaded URL to tmp: %s", tmp_path)
            return tmp_path, True
        except Exception as e:
            logger.warning("[_resolve_logo_path] failed to download URL %s: %s", s, e)
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            return None, False

    candidates_to_try = []

    # try as received
    candidates_to_try.append(s)

    # try relative to cwd
    try:
        cwd = os.getcwd()
        candidates_to_try.append(os.path.join(cwd, s))
    except Exception:
        pass

    # common project locations
    candidates_to_try.append(os.path.join('backend', 'app', s))
    candidates_to_try.append(os.path.join('/app', 'backend', 'app', s))
    candidates_to_try.append(os.path.join('/app', s))
    candidates_to_try.append(os.path.join('app', s))

    # if startswith /static/, try map to project static locations and relative 'static/...' too
    if s.startswith('/static/'):
        candidates_to_try.append(s.lstrip('/'))  # 'static/xxx'
        candidates_to_try.append(os.path.join('backend', 'app', s.lstrip('/')))
        candidates_to_try.append(os.path.join('/app', 'backend', 'app', s.lstrip('/')))

    # if it's 'static/...' try more variants
    if s.startswith('static/'):
        candidates_to_try.append(os.path.join('backend', 'app', s))
        candidates_to_try.append(os.path.join('/app', 'backend', 'app', s))

    # dedupe while preserving order
    seen = set()
    final_candidates = []
    for c in candidates_to_try:
        if not c:
            continue
        norm = os.path.normpath(c)
        if norm not in seen:
            seen.add(norm)
            final_candidates.append(norm)

    # try each candidate and return first that exists
    for c in final_candidates:
        try:
            if os.path.exists(c):
                logger.debug("[_resolve_logo_path] resolved %r -> exists", c)
                return c, False
            else:
                logger.debug("[_resolve_logo_path] tried %r -> not found", c)
        except Exception as e:
            logger.debug("[_resolve_logo_path] error testing path %r: %s", c, e)

    logger.debug("[_resolve_logo_path] could not resolve logo path for %r", s)
    return None, False


# ---------------------
# Helpers to detect avatar-like images/paths
# ---------------------
def _looks_like_avatar_path(path: Optional[str]) -> bool:
    if not path or not isinstance(path, str):
        return False
    lp = path.lower()
    if 'avatar' in lp or '/avatars/' in lp or 'avatar_' in lp or 'thumb' in lp or 'thumbnail' in lp:
        return True
    return False

def _is_probably_avatar_file(path: str) -> bool:
    try:
        from PIL import Image
    except Exception:
        return False
    try:
        if not os.path.exists(path):
            return False
        with Image.open(path) as im:
            w, h = im.size
            if w <= 0 or h <= 0:
                return False
            ratio = float(w) / float(h)
            if 0.7 <= ratio <= 1.3 and max(w, h) <= 400:
                return True
    except Exception:
        return False
    return False

def _is_probably_avatar_file(path: str) -> bool:
    """
    Se Pillow estiver disponível, abre a imagem e verifica proporção e tamanho.
    Retorna True quando a imagem parece ser um avatar (quase quadrada e pequena).
    """
    try:
        from PIL import Image
    except Exception:
        return False

    try:
        if not os.path.exists(path):
            return False
        with Image.open(path) as im:
            w, h = im.size
            if w <= 0 or h <= 0:
                return False
            ratio = float(w) / float(h)
            # avatar típico: quase quadrado e não muito grande
            if 0.7 <= ratio <= 1.3 and max(w, h) <= 400:
                return True
    except Exception:
        # se qualquer erro, conservador: não marque como avatar
        return False
    return False


# ---------------------
# Header drawer helper
# ---------------------
def _draw_header(canvas, doc, company_name: Optional[str], logo_path: Optional[str]):
    """
    Desenha logo (se existir) e nome da empresa no topo da página.
    Alinha verticalmente o texto com o centro do logo e desenha a linha
    separadora abaixo do cabeçalho (não sobrepondo a imagem).
    """
    page_w, page_h = PAGE_WIDTH, PAGE_HEIGHT
    margin_left = doc.leftMargin if hasattr(doc, 'leftMargin') else 2 * cm
    margin_right = doc.rightMargin if hasattr(doc, 'rightMargin') else 2 * cm

    # distância do topo até a "área de header" (ajuste se precisar)
    header_top = page_h - (10 * mm)

    # limites máximos do logo (reduzidos para evitar overlap)
    logo_max_h = 14 * mm
    logo_max_w = 60 * mm

    x = margin_left
    logo_right_x = x
    logo_drawn = False
    logo_y = header_top  # valor default se não desenhar logo
    draw_h = 0

    # Desenha logo se existir e for acessível
    if logo_path:
        try:
            if os.path.exists(logo_path):
                img = ImageReader(logo_path)
                iw, ih = img.getSize()
                scale = min(logo_max_w / iw, logo_max_h / ih, 1.0)
                draw_w = iw * scale
                draw_h = ih * scale
                # posiciona o logo de forma que sua parte superior fique próxima de header_top
                logo_y = header_top - draw_h
                canvas.drawImage(img, x, logo_y, width=draw_w, height=draw_h, preserveAspectRatio=True, mask='auto')
                logo_right_x = x + draw_w + (6 * mm)
                logo_drawn = True
            else:
                logo_right_x = x
        except Exception:
            # se falhar, não interrompe geração do PDF
            logo_right_x = x

    # Desenha o nome da empresa, verticalmente alinhado com o centro do logo (se houver)
    company_text = company_name or ""
    if company_text:
        font_name = "Helvetica-Bold"
        font_size = 14
        canvas.setFont(font_name, font_size)

        if logo_drawn and draw_h > 0:
            # centralizar verticalmente com o centro do logo
            # nota: ajuste fino do divisor (3.0) pode ser calibrado conforme fonte
            text_y = logo_y + draw_h / 2 - (font_size / 3.0)
        else:
            # sem logo: posiciona em linha com header_top
            text_y = header_top - (font_size / 2.5)

        canvas.drawString(logo_right_x, text_y, company_text)

    # Linha separadora: posicionar abaixo do conteúdo do cabeçalho
    # Calcula altura ocupada pelo cabeçalho (considera logo se desenhado, senão um valor mínimo)
    header_height = max(draw_h, 10 * mm)
    line_y = header_top - header_height - (3 * mm)  # pequeno espaçamento abaixo do header

    canvas.setStrokeColorRGB(0.85, 0.85, 0.85)
    canvas.setLineWidth(0.5)
    # desenha linha de margem a margem, com um leve recuo
    canvas.line(margin_left - 4 * mm, line_y, page_w - margin_right + 4 * mm, line_y)


# ---------------------
# Candidate PDF
# ---------------------
def generate_candidate_pdf(candidate_data: Dict, exercises_results: List[Dict], event_data: Dict,
                           signature_path: Optional[str] = None, coordinator_name: Optional[str] = None,
                           coordinator_cref: Optional[str] = None,
                           company_name: Optional[str] = None, company_logo_path: Optional[str] = None) -> bytes:
    """
    Gera o PDF individual do candidato com header e, no final, mostra:
      - assinatura do coordenador (se fornecida como URL ou caminho local)
      - nome do coordenador
      - CREF do coordenador
    """
    # DEBUG (always visible): log + print para garantir saída nos logs do container
    logger.warning(
        "[PDF_GENERATOR][START] candidate=%r signature_path=%r coordinator_name=%r coordinator_cref=%r company_logo=%r",
        candidate_data.get('registration_number'),
        signature_path,
        coordinator_name,
        coordinator_cref,
        company_name
    )
    # print to stdout (guaranteed visible)
    try:
        print("[PDF_GENERATOR-PRINT]", candidate_data.get('registration_number'), signature_path, coordinator_name, coordinator_cref, company_name, flush=True)
    except Exception:
        pass
    try:
        exists = bool(signature_path and os.path.exists(signature_path))
        logger.warning("[PDF_GENERATOR][START] signature_exists=%s resolved_path=%r", exists, signature_path)
    except Exception:
        logger.exception("Could not check signature_path existence in generate_candidate_pdf")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=3*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1976d2'),
                                 spaceAfter=20, alignment=TA_CENTER, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('CustomSubtitle', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#424242'),
                                    spaceAfter=10, alignment=TA_CENTER)
    normal_style = styles['Normal']
    story = []

    # Conteúdo principal
    story.append(Paragraph("FICHA DE AVALIACAO", title_style))
    story.append(Paragraph("Teste de Aptidao Fisica (TAF)", subtitle_style))
    story.append(Spacer(1, 0.3*inch))

    event_info = [['Evento:', event_data.get('name', 'N/A')], ['Data:', event_data.get('date', 'N/A')], ['Local:', event_data.get('location', 'N/A')]]
    event_table = Table(event_info, colWidths=[3*cm, doc.width - 3*cm])
    event_table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e3f2fd')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ])
    )
    story.append(event_table)
    story.append(Spacer(1, 0.3*inch))

    # Dados do candidato
    story.append(Paragraph("DADOS DO CANDIDATO", ParagraphStyle('SectionTitle', parent=styles['Heading3'], fontSize=11,
                                                                 textColor=colors.HexColor('#1976d2'), spaceAfter=10, fontName='Helvetica-Bold')))

    cpf_formatted = format_cpf_safe(candidate_data.get('cpf', ''))
    gender_text = 'Masculino' if candidate_data.get('gender') == 'M' else 'Feminino'
    candidate_info = [
        ['Nome Completo:', candidate_data.get('full_name', 'N/A')],
        ['No de Inscricao:', candidate_data.get('registration_number', 'N/A')],
        ['CPF:', cpf_formatted],
        ['Sexo:', gender_text],
        ['Turma:', candidate_data.get('batch_name', 'N/A')]
    ]

    candidate_table = Table(candidate_info, colWidths=[4*cm, doc.width - 4*cm])
    candidate_table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ])
    )
    story.append(candidate_table)
    story.append(Spacer(1, 0.4*inch))

    # Resultados dos exercícios
    results_data = [['Exercicio', 'Resultado', 'Unidade', 'Status']]
    for exercise in exercises_results:
        exercise_name = exercise.get('exercise_name', 'N/A')
        best_value = exercise.get('best_value', '-')
        unit = exercise.get('unit_of_measure', '')
        is_approved = exercise.get('is_approved')
        status = 'APTO' if is_approved is True else 'INAPTO' if is_approved is False else 'PENDENTE'
        results_data.append([exercise_name, str(best_value) if best_value != '-' else '-', unit, status])

    results_table = Table(results_data, colWidths=[6*cm, 3*cm, 3*cm, doc.width - 12*cm])
    results_table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ])
    )
    story.append(results_table)
    story.append(Spacer(1, 0.4*inch))

    # Resultado final
    overall_status = candidate_data.get('overall_status', 'in_progress')
    if overall_status == 'approved':
        status_text = "RESULTADO FINAL: APROVADO"
        status_color = colors.HexColor('#4caf50')
    elif overall_status == 'failed':
        status_text = "RESULTADO FINAL: REPROVADO"
        status_color = colors.HexColor('#f44336')
    else:
        status_text = "RESULTADO FINAL: EM ANDAMENTO"
        status_color = colors.HexColor('#ff9800')

    final_result_style = ParagraphStyle('FinalResult', parent=styles['Heading2'], fontSize=14, textColor=status_color,
                                        spaceAfter=20, alignment=TA_CENTER, fontName='Helvetica-Bold', backColor=colors.HexColor('#fafafa'))
    story.append(Paragraph(status_text, final_result_style))
    story.append(Spacer(1, 0.5*inch))

    # ---------------------------
    # Área de assinatura do coordenador (imagem opcional + nome + CREF)
    # ---------------------------
    sig_path_resolved, sig_is_temp = (None, False)
    try:
        if signature_path:
            sig_path_resolved, sig_is_temp = _resolve_logo_path(signature_path)
            logger.info("Signature path provided: %s -> resolved: %s (temp=%s)", signature_path, sig_path_resolved, sig_is_temp)

            if not sig_path_resolved:
                cand_paths = []
                try:
                    cwd = os.getcwd()
                    cand_paths.extend([
                        os.path.join(cwd, signature_path.lstrip('/')),
                        os.path.join(cwd, 'static', signature_path.lstrip('/')),
                        os.path.join('backend', 'app', signature_path.lstrip('/')),
                        os.path.join('backend', 'app', 'static', signature_path.lstrip('/')),
                        os.path.join('app', signature_path.lstrip('/')),
                        os.path.join('app', 'static', signature_path.lstrip('/')),
                    ])
                    try:
                        from app.core.config import settings as app_settings
                        if getattr(app_settings, 'UPLOADS_DIR', None):
                            cand_paths.append(os.path.join(app_settings.UPLOADS_DIR, signature_path.lstrip('/')))
                        if getattr(app_settings, 'MEDIA_ROOT', None):
                            cand_paths.append(os.path.join(app_settings.MEDIA_ROOT, signature_path.lstrip('/')))
                        if getattr(app_settings, 'STATIC_DIR', None):
                            cand_paths.append(os.path.join(app_settings.STATIC_DIR, signature_path.lstrip('/')))
                    except Exception:
                        pass
                except Exception:
                    cand_paths = []

                for c in cand_paths:
                    if c and os.path.exists(c):
                        sig_path_resolved = os.path.normpath(c)
                        sig_is_temp = False
                        logger.info("Resolved signature via candidate path: %s", sig_path_resolved)
                        break

        # permitir explicitamente arquivos de attendance antes de rejeitar por heurística de avatar
        if sig_path_resolved and os.path.exists(sig_path_resolved):
            try:
                lc = str(sig_path_resolved).lower()
                if 'attendance_sig' in lc or ('attendance' in lc and 'sig' in lc):
                    logger.info("Signature path looks like attendance_sig, will use it: %s", sig_path_resolved)
                else:
                    if _looks_like_avatar_path(sig_path_resolved) or _is_probably_avatar_file(sig_path_resolved):
                        logger.info("Resolved signature looks like avatar, skipping: %s", sig_path_resolved)
                        sig_path_resolved = None
            except Exception as _e:
                logger.debug("avatar detection helper failed for %s: %s", sig_path_resolved, _e)

        # Novo: preparar imagem para ReportLab (converte RGBA->RGB quando necessário) e inserir no PDF
        if sig_path_resolved and os.path.exists(sig_path_resolved):
            try:
                # Prepara (pode retornar BytesIO com PNG RGB) ou None em caso de falha
                img_buf = prepare_image_for_reportlab(sig_path_resolved)
                if not img_buf:
                    raise RuntimeError("prepare_image_for_reportlab returned None")

                # Usa ImageReader para obter dimensões e calcular escala
                img_reader = ImageReader(img_buf)
                iw, ih = img_reader.getSize()
                max_w = 6.0 * cm
                max_h = 2.5 * cm
                scale = min(max_w / max(iw, 1), max_h / max(ih, 1), 1.0)
                draw_w = iw * scale
                draw_h = ih * scale

                # PlatypusImage aceita file-like (BytesIO), usamos img_buf já preparado
                plat_img = PlatypusImage(img_buf, width=draw_w, height=draw_h)
                sig_table = Table([[plat_img]], colWidths=[doc.width])
                sig_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
                story.append(Spacer(1, 0.2*inch))
                story.append(sig_table)
            except Exception as e:
                logger.warning("Failed to draw signature image %s: %s", sig_path_resolved, e)
        else:
            if signature_path:
                logger.info("Signature not found or unreadable for path: %s", signature_path)
    except Exception as ex:
        logger.exception("Unexpected error while resolving signature: %s", ex)

    # Linha de assinatura (se não tiver imagem ainda colocamos a linha)
    story.append(Spacer(1, 0.1*inch))
    signature_line = Table([['_' * 80]], colWidths=[doc.width])
    signature_line.setStyle(
        TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.grey),
        ])
    )
    story.append(signature_line)

    # Nome do coordenador
    if coordinator_name:
        story.append(Paragraph(str(coordinator_name), ParagraphStyle('SignatureName', parent=normal_style, fontSize=10, alignment=TA_CENTER, fontName='Helvetica-Bold')))

    # CREF do coordenador (aparecer logo abaixo em fonte menor)
    if coordinator_cref:
        cref_text = f"CREF: {coordinator_cref}"
        story.append(Paragraph(cref_text, ParagraphStyle('SignatureCREF', parent=normal_style, fontSize=9, alignment=TA_CENTER, textColor=colors.grey)))

    story.append(Spacer(1, 0.3*inch))

    # footer / generated on
    now = datetime.now()
    footer_text = "Generated on " + now.strftime("%d/%m/%Y at %H:%M")
    story.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=normal_style, fontSize=8, alignment=TA_CENTER, textColor=colors.grey)))

    # Resolve logo (empresa) e build do PDF com header (igual ao consolidado)
    _resolved_logo, _logo_is_temp = _resolve_logo_path(company_logo_path)
    try:
        doc.build(story, onFirstPage=lambda c, d: _draw_header(c, d, company_name, _resolved_logo),
                  onLaterPages=lambda c, d: _draw_header(c, d, company_name, _resolved_logo))
    except Exception:
        logger.exception("Error building PDF")

    # DEBUG: salvar PDF individual se habilitado na env (ajuda comparar individual vs job)
    try:
        if os.environ.get("TAF_DEBUG_SAVE_INDIVIDUAL", "") == "1":
            debug_dir = os.environ.get("TAF_DEBUG_DIR", "/app/uploads/generated_jobs/debug_individual")
            os.makedirs(debug_dir, exist_ok=True)
            reg = candidate_data.get('registration_number') or candidate_data.get('full_name') or 'unknown'
            safe = "".join(ch for ch in str(reg) if ch.isalnum() or ch in ('_', '-'))[:60]
            filename = f"{safe}_{int(time.time())}.pdf"
            path = os.path.join(debug_dir, filename)
            with open(path, "wb") as fh:
                fh.write(buffer.getvalue())
            logger.warning("[PDF_GENERATOR][DEBUG] saved individual PDF to %s", path)
    except Exception:
        logger.exception("Could not save debug individual PDF")

    # cleanup temporários
    try:
        if _logo_is_temp and _resolved_logo and os.path.exists(_resolved_logo):
            os.remove(_resolved_logo)
    except Exception:
        pass
    try:
        if sig_is_temp and sig_path_resolved and os.path.exists(sig_path_resolved):
            os.remove(sig_path_resolved)
    except Exception:
        pass

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes


def _format_cpf(cpf: str) -> str:
    return format_cpf_safe(cpf)


# ---------------------
# Consolidated PDF
# ---------------------
def generate_consolidated_report_pdf(event_data: Dict, candidates_results: List[Dict], summary: Dict,
                                     company_name: Optional[str] = None, company_logo_path: Optional[str] = None) -> bytes:
    buffer = io.BytesIO()
    # increase topMargin to leave room for header
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=3*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, alignment=TA_CENTER, spaceAfter=12, textColor=colors.HexColor('#1976d2'), fontName='Helvetica-Bold')
    story.append(Paragraph("RELATORIO CONSOLIDADO", title_style))

    event_name = event_data.get('name', 'N/A')
    subtitle_text = "Teste de Aptidao Fisica - " + event_name
    story.append(Paragraph(subtitle_text, ParagraphStyle('Subtitle', parent=styles['Heading2'], fontSize=12, alignment=TA_CENTER, spaceAfter=12)))

    total_cand = str(summary.get('total_candidates', 0))
    approved_num = str(summary.get('approved', 0))
    failed_num = str(summary.get('failed', 0))
    approval_pct = str(round(summary.get('approval_rate', 0), 1)) + "%"

    summary_data = [['Total de Candidatos:', total_cand], ['Aprovados:', approved_num], ['Reprovados:', failed_num], ['Taxa de Aprovacao:', approval_pct]]
    summary_table = Table(summary_data, colWidths=[5*cm, 5*cm])
    summary_table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e3f2fd')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 10),
        ])
    )
    story.append(summary_table)
    story.append(Spacer(1, 0.3*inch))

    story.append(Paragraph("RESULTADOS POR CANDIDATO", ParagraphStyle('SectionTitle', parent=styles['Heading3'], fontSize=11, spaceAfter=8, fontName='Helvetica-Bold')))

    results_data = [['No', 'Nome', 'CPF', 'Sexo', 'Status']]
    idx = 1
    for candidate in candidates_results:
        status = candidate.get('overall_status', 'pending')
        status_display = 'APTO' if status == 'approved' else 'INAPTO' if status == 'failed' else 'EM ANDAMENTO'
        full_name = candidate.get('full_name', 'N/A')
        name_short = full_name[:30] if len(full_name) > 30 else full_name
        cpf_val = candidate.get('cpf', '')
        cpf_fmt = format_cpf_safe(cpf_val)
        gender_val = candidate.get('gender', '')
        results_data.append([str(idx), name_short, cpf_fmt, gender_val, status_display])
        idx = idx + 1

    results_table = Table(results_data, colWidths=[1.5*cm, 7*cm, 3.5*cm, 1.5*cm, 2.5*cm])
    results_table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ])
    )
    story.append(results_table)
    story.append(Spacer(1, 0.3*inch))

    now = datetime.now()
    footer = "Generated on " + now.strftime("%d/%m/%Y at %H:%M")
    story.append(Paragraph(footer, ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=colors.grey)))

    # Resolve logo (may download remote image)
    _resolved_logo, _logo_is_temp = _resolve_logo_path(company_logo_path)

    # Build with header function on every page (uses resolved logo)
    doc.build(story, onFirstPage=lambda c, d: _draw_header(c, d, company_name, _resolved_logo),
              onLaterPages=lambda c, d: _draw_header(c, d, company_name, _resolved_logo))

    # cleanup temp logo if it was downloaded
    try:
        if _logo_is_temp and _resolved_logo and os.path.exists(_resolved_logo):
            os.remove(_resolved_logo)
    except Exception:
        pass

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
