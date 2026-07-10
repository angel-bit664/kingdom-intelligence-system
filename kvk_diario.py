import pandas as pd
import discord
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import PieChart, Reference
from openpyxl.utils import get_column_letter
import io

async def procesar_kvk_por_dia(rutas_archivos):
    # Leer todos los archivos y ordenar por día
    dfs = []
    for ruta in sorted(rutas_archivos):
        df = pd.read_excel(ruta)
        # Normalizar nombres de columnas comunes
        df.columns = df.columns.str.lower().str.strip()
        dfs.append(df)

    if len(dfs) < 2:
        raise ValueError("Necesitas mínimo 2 días de KVK")

    df_inicial = dfs[0]
    df_final = dfs[-1]
    dia_actual = len(dfs)

    # Detectar columnas clave
    col_nombre = detectar_columna(df_final, ['nombre', 'name', 'jugador'])
    col_poder = detectar_columna(df_final, ['poder', 'power'])
    col_meritos = detectar_columna(df_final, ['meritos', 'méritos', 'merits'])

    # Merge inicial vs final
    df = df_final.merge(df_inicial, on=col_nombre, suffixes=('_final', '_inicial'), how='left')

    # Calcular métricas
    df['poder_actual'] = df[f'{col_poder}_final'].fillna(0)
    df['poder_inicial'] = df[f'{col_poder}_inicial'].fillna(df['poder_actual'])
    df['cambio_poder'] = df['poder_actual'] - df['poder_inicial']
    df['meta_dia'] = df['poder_inicial'] * (1 + 0.017 * dia_actual) # 1.7% por día
    df['porcentaje_avance'] = ((df['poder_actual'] / df['meta_dia']) - 1) * 100
    df['meritos_ganados'] = df[f'{col_meritos}_final'] - df[f'{col_meritos}_inicial'].fillna(0)

    # Clasificar estados
    df['estado'] = 'Normal'
    df.loc[df['porcentaje_avance'] >= 0, 'estado'] = '🟢 Cumple'
    df.loc[(df['poder_actual'] >= 150_000_000) & (df['cambio_poder'] < 0), 'estado'] = '🔴 Ballena Muerta'
    df.loc[df['meritos_ganados'] < 500_000, 'estado'] = '👻 Fantasma'
    df.loc[(df['poder_actual'] >= 50_000_000) & (df['porcentaje_avance'] < -3), 'estado'] = '⚠️ Riesgo Kick'

    # Métricas generales
    total_jugadores = len(df)
    cumplen = len(df[df['porcentaje_avance'] >= 0])
    porcentaje_cumple = (cumplen / total_jugadores) * 100
    poder_ganado = df[df['cambio_poder'] > 0]['cambio_poder'].sum()
    poder_perdido = abs(df[df['cambio_poder'] < 0]['cambio_poder'].sum())

    # Crear Excel con formato
    wb = Workbook()

    # ===== HOJA 1: DASHBOARD =====
    ws_dash = wb.active
    ws_dash.title = "DASHBOARD"

    # Estilos
    header_font = Font(bold=True, size=14, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="366092")
    rojo_fill = PatternFill("solid", fgColor="FF0000")
    verde_fill = PatternFill("solid", fgColor="00B050")
    amarillo_fill = PatternFill("solid", fgColor="FFC000")
    center_align = Alignment(horizontal="center", vertical="center")

    # Título
    ws_dash.merge_cells('A1:H1')
    ws_dash['A1'] = f"KVK DÍA {dia_actual} | REINO #127 - DASHBOARD"
    ws_dash['A1'].font = Font(bold=True, size=18)
    ws_dash['A1'].alignment = center_align

    # Semáforo
    ws_dash['A3'] = "ESTADO GENERAL"
    ws_dash['A3'].font = header_font
    ws_dash['A3'].fill = header_fill

    if porcentaje_cumple >= 70:
        ws_dash['B3'] = "🟢 ESTABLE"
        ws_dash['B3'].fill = verde_fill
    elif porcentaje_cumple >= 40:
        ws_dash['B3'] = "🟡 ALERTA"
        ws_dash['B3'].fill = amarillo_fill
    else:
        ws_dash['B3'] = "🔴 CRÍTICO"
        ws_dash['B3'].fill = rojo_fill

    ws_dash['B3'].font = Font(bold=True, size=12, color="FFFFFF")
    ws_dash['B3'].alignment = center_align

    # KPIs
    kpis = [
        ("Cumplimiento", f"{cumplen}/{total_jugadores}", f"{porcentaje_cumple:.1f}%"),
        ("Poder Ganado", f"{poder_ganado/1e9:.2f}B", "🟢"),
        ("Poder Perdido", f"{poder_perdido/1e9:.2f}B", "🔴"),
        ("Fantasmas", len(df[df['estado'] == '👻 Fantasma']), "<500K méritos")
    ]

    row = 5
    for i, (titulo, valor, extra) in enumerate(kpis):
        col = i * 2 + 1
        ws_dash.cell(row, col, titulo).font = Font(bold=True)
        ws_dash.cell(row + 1, col, valor).font = Font(size=16, bold=True)
        ws_dash.cell(row + 2, col, extra)
        ws_dash.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col+1)
        ws_dash.merge_cells(start_row=row+1, start_column=col, end_row=row+1, end_column=col+1)
        ws_dash.merge_cells(start_row=row+2, start_column=col, end_row=row+2, end_column=col+1)

    # Top 3 Buenos y Malos
    ws_dash['A9'] = "🥇 TOP 3 MEJORES"
    ws_dash['A9'].font = header_font
    ws_dash['A9'].fill = verde_fill
    ws_dash.merge_cells('A9:D9')

    top_buenos = df.nlargest(3, 'porcentaje_avance')[[col_nombre, 'poder_actual', 'porcentaje_avance']]
    for i, (_, row_data) in enumerate(top_buenos.iterrows(), 10):
        ws_dash[f'A{i}'] = f"{i-9}. {row_data[col_nombre]}"
        ws_dash[f'B{i}'] = f"{row_data['poder_actual']/1e6:.1f}M"
        ws_dash[f'C{i}'] = f"+{row_data['porcentaje_avance']:.1f}%"

    ws_dash['E9'] = "⚠️ TOP 3 RIESGO KICK"
    ws_dash['E9'].font = header_font
    ws_dash['E9'].fill = rojo_fill
    ws_dash.merge_cells('E9:H9')

    top_malos = df[df['poder_actual'] >= 50_000_000].nsmallest(3, 'porcentaje_avance')[[col_nombre, 'poder_actual', 'porcentaje_avance']]
    for i, (_, row_data) in enumerate(top_malos.iterrows(), 10):
        ws_dash[f'E{i}'] = f"{i-9}. {row_data[col_nombre]}"
        ws_dash[f'F{i}'] = f"{row_data['poder_actual']/1e6:.1f}M"
        ws_dash[f'G{i}'] = f"{row_data['porcentaje_avance']:.1f}%"

    # Gráfica de pastel
    pie = PieChart()
    labels = Reference(ws_dash, min_col=1, min_row=15, max_row=16)
    data = Reference(ws_dash, min_col=2, min_row=15, max_row=16)
    pie.add_data(data, titles_from_data=False)
    pie.set_categories(labels)
    pie.title = "Cumplimiento de Meta"
    ws_dash['A15'] = "Cumplen"
    ws_dash['A16'] = "No Cumplen"
    ws_dash['B15'] = cumplen
    ws_dash['B16'] = total_jugadores - cumplen
    ws_dash.add_chart(pie, "A18")

    # Ajustar anchos
    for col in range(1, 9):
        ws_dash.column_dimensions[get_column_letter(col)].width = 18

    # ===== HOJA 2: DETALLE JUGADORES =====
    ws_detalle = wb.create_sheet("DETALLE JUGADORES")
    df_export = df[[col_nombre, 'poder_actual', 'poder_inicial', 'cambio_poder', 'meta_dia', 'porcentaje_avance', 'meritos_ganados', 'estado']].copy()
    df_export.columns = ['Nombre', 'Poder Actual', 'Poder Día 1', 'Cambio', 'Meta Día 7', '% Avance', 'Méritos Ganados', 'Estado']

    # Formato números
    for r in dataframe_to_rows(df_export, index=False, header=True):
        ws_detalle.append(r)

    for row in ws_detalle.iter_rows(min_row=2):
        for cell in row[1:6]: # Columnas de números
            cell.number_format = '#,##0'
        row[5].number_format = '0.0%' # % Avance

    # Colorear filas según estado
    for i, row in enumerate(ws_detalle.iter_rows(min_row=2), 2):
        estado = row[7].value
        if '🟢' in str(estado):
            for cell in row: cell.fill = PatternFill("solid", fgColor="C6EFCE")
        elif '🔴' in str(estado):
            for cell in row: cell.fill = PatternFill("solid", fgColor="FFC7CE")
        elif '👻' in str(estado):
            for cell in row: cell.fill = PatternFill("solid", fgColor="FFEB9C")

    # Filtros y anchos
    ws_detalle.auto_filter.ref = ws_detalle.dimensions
    for col in ws_detalle.columns:
        ws_detalle.column_dimensions[get_column_letter(col[0].column)].width = 18

    # ===== HOJA 3: FANTASMAS =====
    ws_fant = wb.create_sheet("FANTASMAS")
    df_fantasmas = df[df['estado'] == '👻 Fantasma'].sort_values('meritos_ganados')[[col_nombre, 'poder_actual', 'meritos_ganados']]
    for r in dataframe_to_rows(df_fantasmas, index=False, header=True):
        ws_fant.append(r)

    # ===== HOJA 4: BALLENAS EN RIESGO =====
    ws_ballenas = wb.create_sheet("BALLENAS RIESGO")
    df_ballenas = df[df['estado'] == '🔴 Ballena Muerta'].sort_values('cambio_poder')[[col_nombre, 'poder_actual', 'cambio_poder', 'meta_dia']]
    df_ballenas['A Recuperar'] = df_ballenas['meta_dia'] - df_ballenas['poder_actual']
    for r in dataframe_to_rows(df_ballenas, index=False, header=True):
        ws_ballenas.append(r)

    # Guardar en memoria
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    # Embed de Discord
    color = 0xFF0000 if porcentaje_cumple < 40 else 0xF1C40F if porcentaje_cumple < 70 else 0x00FF00
    embed = discord.Embed(
        title=f"⚔️ KVK DÍA {dia_actual} | REINO #127",
        description=f"Progreso acumulado desde Día 1 del KVK",
        color=color
    )
    embed.add_field(name="🎯 META INDIVIDUAL 12% ACUMULADA", value=f"**CUMPLIMIENTO: {cumplen}/{total_jugadores} ({porcentaje_cumple:.1f}%)**", inline=False)
    embed.add_field(name="📊 Poder Ganado", value=f"🟢 +{poder_ganado/1e9:.2f}B", inline=True)
    embed.add_field(name="📊 Poder Perdido", value=f"🔴 -{poder_perdido/1e9:.2f}B", inline=True)
    embed.add_field(name="👻 Fantasmas", value=f"{len(df[df['estado'] == '👻 Fantasma'])} jugadores", inline=True)
    embed.set_footer(text=f"Día {dia_actual} KVK | Dashboard generado")

    archivo = discord.File(buffer, filename=f"KVK_Dia{dia_actual}_Dashboard.xlsx")
    return embed, archivo

def detectar_columna(df, posibles_nombres):
    for col in df.columns:
        if any(nombre in str(col).lower() for nombre in posibles_nombres):
            return col
    raise ValueError(f"No encontré columna con nombres: {posibles_nombres}")

from openpyxl.utils.dataframe import dataframe_to_rows
