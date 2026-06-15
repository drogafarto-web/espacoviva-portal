import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_a4_pdf(ficha_data):
    """Generates a professional A4 PDF for Espaço Viva academia."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    primary_color = colors.HexColor("#0a3c2a")  # Deep Forest Green
    secondary_color = colors.HexColor("#00ff88") # Lime/Neon Green
    dark_neutral = colors.HexColor("#222222")
    light_neutral = colors.HexColor("#f4f6f5")
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=primary_color,
        alignment=1, # Center
        spaceAfter=15
    )
    
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=primary_color,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=dark_neutral
    )
    
    body_bold_style = ParagraphStyle(
        'DocBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    exercise_header_style = ParagraphStyle(
        'ExerciseHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.white
    )
    
    exercise_cell_style = ParagraphStyle(
        'ExerciseCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=dark_neutral
    )
    
    exercise_cell_bold_style = ParagraphStyle(
        'ExerciseCellBold',
        parent=exercise_cell_style,
        fontName='Helvetica-Bold'
    )

    story = []
    
    # Header Logo / Title
    story.append(Paragraph("ESPAÇO VIVA — FICHA DE TREINO", title_style))
    story.append(Spacer(1, 2*mm))
    
    # ── ALUNO INFO TABLE ──
    aluno_name = ficha_data.get("aluno_name", "Aluno de Teste")
    sexo = ficha_data.get("sexo", "Não informado")
    objetivo = ficha_data.get("objetivo", "Não informado")
    nivel = ficha_data.get("nivel", "Não informado")
    frequencia = f"{ficha_data.get('frequencia', 4)}x na semana"
    divisao = ficha_data.get("divisao", "Automática")
    
    info_data = [
        [
            Paragraph("<b>Aluno:</b>", body_style), Paragraph(aluno_name, body_bold_style),
            Paragraph("<b>Sexo:</b>", body_style), Paragraph(sexo, body_style)
        ],
        [
            Paragraph("<b>Objetivo:</b>", body_style), Paragraph(objetivo.capitalize(), body_style),
            Paragraph("<b>Nível:</b>", body_style), Paragraph(nivel.capitalize(), body_style)
        ],
        [
            Paragraph("<b>Freq. Semanal:</b>", body_style), Paragraph(frequencia, body_style),
            Paragraph("<b>Divisão:</b>", body_style), Paragraph(divisao, body_style)
        ]
    ]
    
    info_table = Table(info_data, colWidths=[35*mm, 55*mm, 30*mm, 60*mm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), light_neutral),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#dddddd")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#eeeeee")),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 4*mm))
    
    # ── ANAMNESE & AVALIAÇÃO FÍSICA ──
    anamnese = ficha_data.get("anamnese", "Nenhuma observação.")
    peso = ficha_data.get("peso", "—")
    altura = ficha_data.get("altura", "—")
    bf = ficha_data.get("bf", "—")
    
    cli_data = [
        [
            Paragraph("<b>Anamnese / Limitações:</b>", body_style), 
            Paragraph(anamnese, body_style),
            Paragraph(f"<b>Peso:</b> {peso} kg<br/><b>Altura:</b> {altura} m<br/><b>BF%:</b> {bf}%", body_style)
        ]
    ]
    cli_table = Table(cli_data, colWidths=[45*mm, 90*mm, 45*mm])
    cli_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.white),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#dddddd")),
    ]))
    story.append(cli_table)
    story.append(Spacer(1, 5*mm))
    
    # ── EXERCISES GROUPED BY WORKOUT ──
    treinos = ficha_data.get("treinos", {})
    
    for nome_treino, blocos in treinos.items():
        story.append(Paragraph(nome_treino.upper(), section_style))
        
        # Table of Exercises
        table_content = [
            [
                Paragraph("Ord.", exercise_header_style),
                Paragraph("Exercício", exercise_header_style),
                Paragraph("Séries e Repetições / Tempo", exercise_header_style),
                Paragraph("Bloco de Origem", exercise_header_style)
            ]
        ]
        
        ex_idx = 1
        for cod_bloco in blocos:
            local_items = ficha_data.get("local_exercises", {}).get(cod_bloco, [])
            bloco_nome = ficha_data.get("bloco_nomes", {}).get(cod_bloco, cod_bloco)
            
            for item in local_items:
                name = item.get("name", "Exercício")
                comments = item.get("comments", "A critério")
                table_content.append([
                    Paragraph(str(ex_idx), exercise_cell_bold_style),
                    Paragraph(name, exercise_cell_bold_style),
                    Paragraph(comments, exercise_cell_style),
                    Paragraph(bloco_nome, exercise_cell_style)
                ])
                ex_idx += 1
                
        ex_table = Table(table_content, colWidths=[12*mm, 68*mm, 50*mm, 50*mm])
        ex_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), primary_color),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#fcfcfc")]),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#eeeeee")),
        ]))
        story.append(ex_table)
        story.append(Spacer(1, 4*mm))
        
    # ── RECOMMENDATIONS / OBSERVATIONS ──
    recs = ficha_data.get("recomendacoes", [])
    if recs:
        story.append(Paragraph("RECOMENDAÇÕES DA ASSESSORIA ESPAÇO VIVA", section_style))
        rec_text = "<br/>".join([f"• {r}" for r in recs])
        story.append(Paragraph(rec_text, body_style))
        
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_thermal_pdf(ficha_data):
    """Generates a compact PDF optimized for 80mm thermal receipt printers."""
    buffer = io.BytesIO()
    
    # 80mm is approx 3.15 inches = 226.7 points
    width = 226.7
    # Height will be dynamically sized in code, or a long scroll that cuts off
    # We estimate height by counting exercises.
    num_ex = sum(len(ficha_data.get("local_exercises", {}).get(cod, [])) for _, blocos in ficha_data.get("treinos", {}).items() for cod in blocos)
    estimated_height = 180 + (num_ex * 25) + (len(ficha_data.get("treinos", {})) * 30)
    estimated_height = max(estimated_height, 400) # Minimum height
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(width, estimated_height),
        rightMargin=4*mm,
        leftMargin=4*mm,
        topMargin=4*mm,
        bottomMargin=4*mm
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'ThTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        alignment=1, # Center
        spaceAfter=4
    )
    
    section_style = ParagraphStyle(
        'ThSection',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        spaceBefore=6,
        spaceAfter=3
    )
    
    body_style = ParagraphStyle(
        'ThBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9
    )
    
    body_bold_style = ParagraphStyle(
        'ThBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    story = []
    
    # Header
    story.append(Paragraph("<b>ESPAÇO VIVA ACADEMIA</b>", title_style))
    story.append(Paragraph("Ficha de Treinamento", ParagraphStyle('Sub', parent=title_style, fontSize=8, spaceAfter=8)))
    
    aluno_name = ficha_data.get("aluno_name", "Aluno de Teste")
    sexo = ficha_data.get("sexo", "Não informado")
    objetivo = ficha_data.get("objetivo", "Não informado")
    divisao = ficha_data.get("divisao", "Automática")
    
    story.append(Paragraph(f"<b>Aluno:</b> {aluno_name}", body_style))
    story.append(Paragraph(f"<b>Objetivo:</b> {objetivo.upper()} | <b>Divisão:</b> {divisao}", body_style))
    story.append(Paragraph("-" * 45, body_style))
    
    # Workouts
    treinos = ficha_data.get("treinos", {})
    for nome_treino, blocos in treinos.items():
        story.append(Paragraph(f"<b>{nome_treino.upper()}</b>", section_style))
        story.append(Paragraph("-" * 45, body_style))
        
        ex_idx = 1
        for cod_bloco in blocos:
            local_items = ficha_data.get("local_exercises", {}).get(cod_bloco, [])
            for item in local_items:
                name = item.get("name", "Exercício")
                comments = item.get("comments", "A critério")
                story.append(Paragraph(f"<b>{ex_idx}. {name}</b>", body_bold_style))
                story.append(Paragraph(f"   Séries/Reps: {comments}", body_style))
                ex_idx += 1
                
        story.append(Paragraph("-" * 45, body_style))
        
    recs = ficha_data.get("recomendacoes", [])
    if recs:
        story.append(Paragraph("<b>Recomendações:</b>", section_style))
        for r in recs:
            story.append(Paragraph(f"• {r}", body_style))
            
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("Bons treinos!", ParagraphStyle('End', parent=title_style, fontSize=7, alignment=1)))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
