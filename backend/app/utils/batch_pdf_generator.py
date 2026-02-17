# -*- coding: utf-8 -*-
# backend/app/utils/batch_pdf_generator.py
"""
Gerador de PDFs para turmas:
- Lista de presenca
- Espelhos/etiquetas numeradas
"""

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as PlatypusImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics import renderPDF
from io import BytesIO
from typing import List, Dict, Any
from datetime import datetime
import json
import os


def generate_attendance_list_pdf(
    event_data: Dict[str, Any],
    batch_name: str,
    candidates: List[Dict[str, Any]],
    company_data: Dict[str, Any] = None
) -> bytes:
    """
    Gera PDF de lista de presenca da turma em PAISAGEM.
    
    Args:
        event_data: {name, date, location, start_time}
        batch_name: Nome da turma
        candidates: Lista com {batch_number, full_name, cpf, registration_number}
        company_data: {name, logo_url} - dados da empresa/tenant (opcional)
    
    Returns:
        bytes do PDF
    """
    buffer = BytesIO()
    
    # Paisagem para mais espaco
    page_size = landscape(A4)
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=page_size, 
        topMargin=1.5*cm, 
        bottomMargin=1.5*cm,
        leftMargin=1.5*cm,
        rightMargin=1.5*cm
    )
    elements = []
    styles = getSampleStyleSheet()
    
    # Dados da empresa (fallback)
    if not company_data:
        company_data = {'name': 'TAFON', 'logo_url': None}
    
    # Cabecalho com logo e empresa
    if company_data.get('logo_url'):
        try:
            logo_path = company_data['logo_url']
            if logo_path.startswith('/static/'):
                logo_path = logo_path.replace('/static/', 'static/')
            
            if os.path.exists(logo_path):
                logo = PlatypusImage(logo_path, width=3*cm, height=1.5*cm)
                
                title_style = ParagraphStyle(
                    'TitleWithLogo',
                    parent=styles['Heading1'],
                    fontSize=14,
                    textColor=colors.HexColor('#1976d2'),
                    alignment=TA_LEFT
                )
                
                company_name = Paragraph(f"<b>{company_data.get('name', 'TAFON').upper()}</b>", title_style)
                list_title = Paragraph(f"<b>LISTA DE PRESENCA - {batch_name}</b>", title_style)
                
                header_table = Table(
                    [[logo, [company_name, list_title]]],
                    colWidths=[4*cm, 22*cm]
                )
                header_table.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                    ('ALIGN', (1, 0), (1, 0), 'LEFT'),
                ]))
                
                elements.append(header_table)
        except Exception as e:
            pass
    
    # Se nao conseguiu criar com logo, usa texto simples
    if not elements:
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1976d2'),
            spaceAfter=6,
            alignment=TA_CENTER
        )
        elements.append(Paragraph(company_data.get('name', 'TAFON').upper(), title_style))
        elements.append(Paragraph(f"LISTA DE PRESENCA - {batch_name}", title_style))
    
    # Informacoes do evento
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=12,
        alignment=TA_CENTER
    )
    
    # Converte data para formato brasileiro
    date_str = event_data['date']
    try:
        if '-' in date_str and len(date_str) == 10:
            parts = date_str.split('-')
            if len(parts) == 3:
                date_str = f"{parts[2]}/{parts[1]}/{parts[0]}"
    except:
        pass
    
    # Monta linha de informacoes (com horario se disponivel)
    info_parts = [event_data['name'], date_str, event_data['location']]
    
    if event_data.get('start_time'):
        info_parts.insert(2, f"Horario: {event_data['start_time']}")
    
    info_text = " | ".join(info_parts)
    elements.append(Paragraph(info_text, subtitle_style))
    elements.append(Spacer(1, 0.5*cm))
    
    # Tabela de candidatos
    data = [['#', 'Numero', 'Nome', 'CPF', 'Inscricao', 'Assinatura']]
    
    for idx, candidate in enumerate(candidates, start=1):
        cpf_formatted = f"{candidate['cpf'][:3]}.{candidate['cpf'][3:6]}.{candidate['cpf'][6:9]}-{candidate['cpf'][9:]}"
        data.append([
            str(idx),
            str(candidate['batch_number']).zfill(3),
            candidate['full_name'][:45],
            cpf_formatted,
            candidate['registration_number'],
            ''
        ])
    
    # Coluna assinatura MUITO MAIOR (7cm)
    table = Table(data, colWidths=[1*cm, 1.5*cm, 8*cm, 3.5*cm, 2.5*cm, 7*cm])
    
    table.setStyle(TableStyle([
        # Cabecalho
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        
        # Corpo
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 1), (1, -1), 'CENTER'),
        ('ALIGN', (3, 1), (4, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('ROWHEIGHT', (0, 1), (-1, -1), 1.2*cm),
    ]))
    
    elements.append(table)
    
    # Rodape
    elements.append(Spacer(1, 0.8*cm))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    elements.append(Paragraph(
        f"Total de candidatos: {len(candidates)} | Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        footer_style
    ))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.read()


def generate_batch_badges_pdf(
    event_data: Dict[str, Any],
    batch_name: str,
    candidates: List[Dict[str, Any]],
    company_data: Dict[str, Any] = None
) -> bytes:
    """
    Gera PDF de espelhos/etiquetas numeradas estilo competicao (21cm x 15cm - PAISAGEM).
    """
    buffer = BytesIO()
    
    page_width, page_height = landscape(A4)
    badge_width = 21*cm
    badge_height = 15*cm
    
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    
    margin_x = (page_width - badge_width) / 2
    margin_y = (page_height - badge_height) / 2
    
    if not company_data:
        company_data = {'name': 'TAFON', 'phone': '', 'email': '', 'logo_url': None}
    
    for idx, candidate in enumerate(candidates):
        if idx > 0:
            c.showPage()
        
        x_pos = margin_x
        y_pos = margin_y
        
        # Fundo branco
        c.setFillColor(colors.white)
        c.rect(x_pos, y_pos, badge_width, badge_height, fill=1, stroke=0)
        
        # Borda preta forte
        c.setStrokeColor(colors.black)
        c.setLineWidth(4)
        c.rect(x_pos, y_pos, badge_width, badge_height, fill=0, stroke=1)
        
        # Barra superior azul
        bar_height = 3.5*cm
        c.setFillColor(colors.HexColor('#1976d2'))
        c.rect(x_pos, y_pos + badge_height - bar_height, badge_width, bar_height, fill=1, stroke=0)
        
        # Titulo do evento
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 32)
        event_title = event_data['name'][:30]
        c.drawCentredString(x_pos + badge_width/2, y_pos + badge_height - 1.5*cm, event_title)
        
        # Nome da turma
        c.setFont('Helvetica-Bold', 14)
        c.drawCentredString(x_pos + badge_width/2, y_pos + badge_height - 2.3*cm, batch_name)
        
        # Data, local e horario
        c.setFont('Helvetica', 11)
        date_str = event_data['date']
        try:
            if '-' in date_str and len(date_str) == 10:
                parts = date_str.split('-')
                if len(parts) == 3:
                    date_str = f"{parts[2]}/{parts[1]}/{parts[0]}"
        except:
            pass
        
        info_parts = [date_str, event_data['location']]
        if event_data.get('start_time'):
            info_parts.insert(0, f"Horario: {event_data['start_time']}")
        
        info_text = " | ".join(info_parts)
        c.drawCentredString(x_pos + badge_width/2, y_pos + badge_height - 3*cm, info_text)
        
        # Numero gigante
        numero = str(candidate['batch_number']).zfill(3)
        c.setFillColor(colors.black)
        c.setFont('Helvetica-Bold', 200)
        text_width = c.stringWidth(numero, 'Helvetica-Bold', 200)
        num_x = x_pos + (badge_width - text_width)/2
        num_y = y_pos + 5.5*cm
        c.drawString(num_x, num_y, numero)
        
        # Nome do candidato
        c.setFillColor(colors.HexColor('#1976d2'))
        c.setFont('Helvetica-Bold', 20)
        name = candidate['full_name'][:35].upper()
        c.drawCentredString(x_pos + badge_width/2, y_pos + 4.5*cm, name)
        
        # Numero de inscricao
        c.setFont('Helvetica', 14)
        c.setFillColor(colors.HexColor('#666666'))
        c.drawCentredString(x_pos + badge_width/2, y_pos + 3.5*cm, f"Inscricao: {candidate['registration_number']}")
        
        # Nome vertical
        left_x = x_pos + 0.3*cm
        info_y = y_pos + 3*cm
        c.saveState()
        c.translate(left_x + 0.2*cm, info_y)
        c.rotate(90)
        c.setFillColor(colors.HexColor('#999999'))
        c.setFont('Helvetica', 10)
        name_vertical = candidate['full_name'][:30].lower()
        c.drawString(0, 0, name_vertical)
        c.restoreState()
        
        # QR Code
        qr_data = {
            'numero': numero,
            'nome': candidate['full_name'],
            'inscricao': candidate['registration_number'],
            'sexo': candidate['gender'],
            'turma': batch_name,
            'evento': event_data['name'],
            'data': date_str
        }
        qr_json = json.dumps(qr_data, ensure_ascii=False)
        
        qr_code = QrCodeWidget(qr_json)
        qr_size = 4*cm
        qr_code.barWidth = qr_size
        qr_code.barHeight = qr_size
        
        qr_x = x_pos + badge_width - qr_size - 0.5*cm
        qr_y = y_pos + 0.5*cm
        
        drawing = Drawing(qr_size, qr_size)
        drawing.add(qr_code)
        renderPDF.draw(drawing, c, qr_x, qr_y)
        
        # Badge de sexo
        gender_full = 'FEMININO' if candidate['gender'] == 'F' else 'MASCULINO'
        gender_color = colors.HexColor('#d81b60') if candidate['gender'] == 'F' else colors.HexColor('#1976d2')
        
        circle_x = x_pos + badge_width/2
        circle_y = y_pos + 2*cm
        circle_radius = 1.2*cm
        
        c.setFillColor(gender_color)
        c.circle(circle_x, circle_y, circle_radius, fill=1, stroke=0)
        
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 10)
        c.drawCentredString(circle_x, circle_y - 0.15*cm, gender_full)
        
        # Rodape - logo e nome da empresa
        footer_y = y_pos + 0.5*cm
        
        logo_drawn = False
        if company_data.get('logo_url'):
            try:
                logo_path = company_data['logo_url']
                if logo_path.startswith('/static/'):
                    logo_path = logo_path.replace('/static/', 'static/')
                
                if os.path.exists(logo_path):
                    logo_height = 1*cm
                    logo_width = 2*cm
                    
                    c.drawImage(
                        logo_path,
                        x_pos + 0.5*cm,
                        footer_y - 0.2*cm,
                        width=logo_width,
                        height=logo_height,
                        preserveAspectRatio=True,
                        mask='auto'
                    )
                    logo_drawn = True
            except Exception as e:
                pass
        
        text_x = x_pos + 3*cm if logo_drawn else x_pos + 0.5*cm
        
        c.setFont('Helvetica-Bold', 11)
        c.setFillColor(colors.black)
        c.drawString(text_x, footer_y + 0.2*cm, company_data.get('name', 'TAFON').upper())
    
    c.save()
    buffer.seek(0)
    return buffer.read()
