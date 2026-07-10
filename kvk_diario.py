import pandas as pd
import discord
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.utils import get_column_letter
import io
import zipfile

async def procesar_kvk_por_dia(rutas_archivos):
    # Soporte para ZIP
    archivos_excel = []
    for ruta in rutas_archivos:
        if ruta.endswith('.zip'):
            with zipfile.ZipFile(ruta, 'r') as zip_ref:
                for name in zip_ref.namelist():
                    if name.endswith('.xlsx'):
                        zip_ref.extract(name, '/tmp/')
                        archivos_excel.append(f'/tmp/{name}')
        elif ruta.endswith('.xlsx'):
            archivos_excel.append(ruta)

    if len(archivos_excel) < 2:
        raise ValueError("Necesitas mínimo 2 días de KVK en Excel o 1 ZIP con varios")

    # Leer y ordenar por nombre de archivo
    dfs = []
    for ruta in sorted(archivos_excel):
        df = pd.read_excel(ruta)
        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
        dfs.append(df)

    df_inicial = dfs[0]
    df_final = dfs[-1]
    dia_actual = len(dfs)

    # Detectar columnas - más flexible
    col_nombre = detectar_columna(df_final, ['nombre', 'name', 'jugador', 'player'])
    col_poder = detectar_columna(df_final, ['poder', 'power'])
    col_meritos = detectar_columna(df_final, ['meritos', 'méritos', 'merits', 'honor'])

    # Merge y cálculos
    df = df_final.merge(df_inicial, on=col_nombre, suffixes=('_final', '_inicial'), how='left')

    # Limpiar números - quitar comas, M, K, etc
    for col in [f'{col_poder}_final', f'{col_poder}_inicial', f'{col_meritos}_final', f'{col_meritos}_inicial']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '').str.replace('M', 'e6').str.replace('K', 'e3')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df['poder_actual'] = df[f'{col_poder}_final']
    df['poder_inicial'] = df[f'{col_poder}_inicial'].fillna(df['poder_actual'])
    df['cambio_poder'] = df['poder_actual'] - df['poder_inicial']
    df['meta_dia'] = df['poder_inicial'] * (1 + 0.017 * dia_actual)
    # 👇 AQUÍ ESTABA EL ERROR - FALTABA UN PARÉNTESIS
    df['porcentaje_avance'] = ((df['poder_actual'] / df['meta_dia'].replace(0, 1)) - 1) * 100
    df['meritos_ganados'] = df[f'{col_meritos}_final'] - df[f'{col_meritos}_inicial'].fillna(0)

    # Estados con emojis claros
    df['estado'] = '🟡 Normal'
    df.loc[df['porcentaje_avance'] >= 0, 'estado'] = '🟢 Cumple Meta'
    df.loc[(df['poder_actual'] >= 150_000_000) & (df['cambio_poder'] < 0), 'estado'] = '🔴 Ballena Muerta'
    df.loc[df['meritos_ganados'] < 500_000, 'estado'] = '👻 Fantasma'
    df.loc[(df['poder_actual'] >= 50_000_000) & (df['porcentaje_avance'] < -5), 'estado'] = '⚠️ Riesgo Kick'

    # Métricas
    total = len(df)
    cumplen = len(df[df['porcentaje_avance'] >= 0])
    pct_cumple = (cumplen / total) * 100 if total > 0 else 0
    poder_ganado = df[df['cambio_poder'] > 0]['cambio_poder'].sum()
    poder_perdido = abs(df[df['cambio_poder'] < 0]['cambio_poder'].sum())
    fantasmas = len(df[df['estado'] == '👻 Fantasma'])
    ballenas_muertas = len(df[df['estado'] == '🔴 Ballena Muerta'])

    # ===== CREAR EXCEL =====
    wb = Workbook()
    ws_dash = wb.active
    ws_dash.title = "RESUMEN"

    # Estilos
    titulo_font = Font(bold=True, size=16, color="FFFFFF")
    header_font = Font(bold=True, size=12, color="FFFFFF")
    azul_fill = PatternFill("solid", fgColor="1F4E78")
    verde_fill = PatternFill("solid", fgColor="70AD47")
    rojo_fill = PatternFill("solid", fgColor="C00000")
    amarillo_fill = PatternFill("solid", fgColor="FFC000")
    center = Alignment(horizontal="center", vertical="center")

    # Título Dashboard
    ws_dash.merge_cells('A1:L2')
    ws_dash['A1'] = f"KVK DÍA {dia_actual} | REPORTE OFICIAL TFT"
    ws_dash['A1'].font = titulo_font
    ws_dash['A1'].fill = azul_fill
    ws_dash['A1'].alignment = center

    # Semáforo grande
    ws_dash['A4'] = "ESTADO DEL REINO"
    ws_dash['A4'].font = Font(bold=True, size=14)
    ws_dash.merge_cells('A4:B4')

    if pct_cumple >= 70:
        estado_txt, color = "🟢 ESTABLE", verde_fill
    elif pct_cumple >= 40:
        estado_txt, color = "🟡 EN ALERTA", amarillo_fill
    else:
        estado_txt, color = "🔴 CRÍTICO", rojo_fill

    ws_dash['A5'] = estado_txt
    ws_dash['A5'].font = Font(bold=True, size=20, color="FFFFFF")
    ws_dash['A5'].fill = color
    ws_dash['A5'].alignment = center
    ws_dash.merge_cells('A5:B6')

    # 4 KPIs principales
    kpi_data = [
        ("Cumplimiento", f"{cumplen}/{total}", f"{pct_cumple:.1f}%", verde_fill if pct_cumple >= 50 else rojo_fill),
        ("Poder Ganado", f"{poder_ganado/1e9:.2f}B", "🟢 Subiendo", verde_fill),
        ("Poder Perdido", f"{poder_perdido/1e9:.2f}B", "🔴 Bajando", rojo_fill),
        ("Fantasmas", f"{fantasmas}", "< 500K méritos", amarillo_fill)
    ]

    col_start = 4
    for i, (titulo, valor, sub, color_fill) in enumerate(kpi_data):
        col = col_start + (i * 2)
        ws_dash.cell(4, col, titulo).font = Font(bold=True)
        ws_dash.cell(5, col, valor).font = Font(size=18, bold=True)
        ws_dash.cell(5, col).fill = color_fill
        ws_dash.cell(5, col).font = Font(size=18, bold=True, color="FFFFFF")
        ws_dash.cell(5, col).alignment = center
        ws_dash.cell(6, col, sub).font = Font(size=9)
        ws_dash.merge_cells(start_row=5, start_column=col, end_row=5, end_column=col+1)
        ws_dash.merge_cells(start_row=6, start_column=col, end_row=6, end_column=col+1)

    # ===== GRÁFICA 1: TOP 10 GANADORES =====
    ws_dash['A8'] = "📈 TOP 10 QUE MÁS CRECIERON"
    ws_dash['A8'].font = header_font
    ws_dash['A8'].fill = verde_fill
    ws_dash.merge_cells('A8:F8')

    top10_ganan = df.nlargest(10, 'cambio_poder')[[col_nombre, 'cambio_poder']]
    row_start = 9
    for i, (_, row) in enumerate(top10_ganan.iterrows()):
        ws_dash.cell(row_start + i, 1, row[col_nombre])
        ws_dash.cell(row_start + i, 2, row['cambio_poder'] / 1e6)

    chart_ganan = BarChart()
    chart_ganan.type = "col"
    chart_ganan.style = 10
    chart_ganan.title = "Top 10 Ganancia de Poder (Millones)"
    chart_ganan.y_axis.title = 'Millones de Poder'
    chart_ganan.x_axis.title = 'Jugador'

    data = Reference(ws_dash, min_col=2, min_row=row_start-1, max_row=row_start+9)
    cats = Reference(ws_dash, min_col=1, min_row=row_start, max_row=row_start+9)
    chart_ganan.add_data(data, titles_from_data=True)
    chart_ganan.set_categories(cats)
    chart_ganan.height = 10
    chart_ganan.width = 20
    ws_dash.add_chart(chart_ganan, "A20")

    # ===== GRÁFICA 2: TOP 10 PERDEDORES =====
    ws_dash['G8'] = "📉 TOP 10 QUE MÁS PERDIERON"
    ws_dash['G8'].font = header_font
    ws_dash['G8'].fill = rojo_fill
    ws_dash.merge_cells('G8:L8')

    top10_pierden = df.nsmallest(10, 'cambio_poder')[[col_nombre, 'cambio_poder']]
    for i, (_, row) in enumerate(top10_pierden.iterrows()):
        ws_dash.cell(row_start + i, 7, row[col_nombre])
        ws_dash.cell(row_start + i, 8, abs(row['cambio_poder']) / 1e6)

    chart_pierden = BarChart()
    chart_pierden.type = "col"
    chart_pierden.style = 11
    chart_pierden.title = "Top 10 Pérdida de Poder (Millones)"
    chart_pierden.y_axis.title = 'Millones de Poder'
    chart_pierden.x_axis.title = 'Jugador'

    data2 = Reference(ws_dash, min_col=8, min_row=row_start-1, max_row=row_start+9)
    cats2 = Reference(ws_dash, min_col=7, min_row=row_start, max_row=row_start+9)
    chart_pierden.add_data(data2, titles_from_data=True)
    chart_pierden.set_categories(cats2)
    chart_pierden.height = 10
    chart_pierden.width = 20
    ws_dash.add_chart(chart_pierden, "G20")

    # Gráfica de pastel cumplimiento
    ws_dash['A35'] = "Cumplen"
    ws_dash['A36'] = "No Cumplen"
    ws_dash['B35'] = cumplen
    ws_dash['B36'] = total - cumplen

    pie = PieChart()
    labels = Reference(ws_dash, min_col=1, min_row=35, max_row=36)
    data_pie = Reference(ws_dash, min_col=2, min_row=35, max_row=36)
    pie.add_data(data_pie, titles_from_data=False)
    pie.set_categories(labels)
    pie.title = "Cumplimiento de Meta"
    pie.height = 8
    pie.width = 12
    ws_dash.add_chart(pie, "A37")

    # Anchos
    for col in range(1, 13):
        ws_dash.column_dimensions[get_column_letter(col)].width = 18

    # ===== HOJA 2: TABLA COMPLETA =====
    ws_tabla = wb.create_sheet("TODOS LOS JUGADORES")
    df_export = df[[col_nombre, 'poder_actual', 'poder_inicial', 'cambio_poder', 'meta_dia', 'porcentaje_avance', 'meritos_ganados', 'estado']].copy()
    df_export.columns = ['Nombre', 'Poder Actual', 'Poder Día 1', 'Cambio Poder', 'Meta Día 7', '% vs Meta', 'Méritos Ganados', 'Estado']

    for r in dataframe_to_rows(df_export, index=False, header=True):
        ws_tabla.append(r)

    # Formato tabla
    for cell in ws_tabla[1]:
        cell.font = header_font
        cell.fill = azul_fill
        cell.alignment = center

    for row in ws_tabla.iter_rows(min_row=2):
        row[1].number_format = '#,##0'
        row[2].number_format = '#,##0'
        row[3].number_format = '#,##0'
        row[4].number_format = '#,##0'
        row[5].number_format = '0.0%'
        row[6].number_format = '#,##0'

        # Color fila según estado
        if '🟢' in str(row[7].value):
            for cell in row: cell.fill = PatternFill("solid", fgColor="C6EFCE")
        elif '🔴' in str(row[7].value):
            for cell in row: cell.fill = PatternFill("solid", fgColor="FFC7CE")
        elif '👻' in str(row[7].value):
            for cell in row: cell.fill = PatternFill("solid", fgColor="FFEB9C")
        elif '⚠️' in str(row[7].value):
            for cell in row: cell.fill = PatternFill("solid", fgColor="FFD966")

    ws_tabla.auto_filter.ref = ws_tabla.dimensions
    ws_tabla.freeze_panes = 'A2'

    for col in ws_tabla.columns:
        ws_tabla.column_dimensions[get_column_letter(col[0].column)].width = 18

    # ===== HOJA 3: FANTASMAS =====
    ws_fant = wb.create_sheet("FANTASMAS <500K")
    df_fant = df[df['estado'] == '👻 Fantasma'].sort_values('meritos_ganados')[[col_nombre, 'poder_actual', 'meritos_ganados', 'cambio_poder']]
    df_fant.columns = ['Nombre', 'Poder', 'Méritos Ganados', 'Cambio Poder']
    for r in dataframe_to_rows(df_fant, index=False, header=True):
        ws_fant.append(r)

    # ===== HOJA 4: BALLENAS MUERTAS =====
    ws_ball = wb.create_sheet("BALLENAS MUERTAS")
    df_ball = df[df['estado'] == '🔴 Ballena Muerta'].sort_values('cambio_poder')[[col_nombre, 'poder_actual', 'cambio_poder', 'meta_dia']]
    df_ball['Falta para Meta'] = df_ball['meta_dia'] - df_ball['poder_actual']
    df_ball.columns = ['Nombre', 'Poder Actual', 'Perdido', 'Meta Día 7', 'Falta']
    for r in dataframe_to_rows(df_ball, index=False, header=True):
        ws_ball.append(r)

    # ===== HOJA 5: RIESGO KICK =====
    ws_kick = wb.create_sheet("RIESGO KICK")
    df_kick = df[df['estado'] == '⚠️ Riesgo Kick'].sort_values('porcentaje_avance')[[col_nombre, 'poder_actual', 'porcentaje_avance', 'meritos_ganados']]
    df_kick.columns = ['Nombre', 'Poder', '% vs Meta', 'Méritos']
    for r in dataframe_to_rows(df_kick, index=False, header=True):
        ws_kick.append(r)

    # Guardar
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    # Embed bonito
    color = 0xFF0000 if pct_cumple < 40 else 0xF1C40F if pct_cumple < 70 else 0x00FF00
    embed = discord.Embed(
        title=f"⚔️ KVK DÍA {dia_actual} | REINO #127",
        description=f"**Reporte de Progreso Acumulado**\nTodos deben crecer 1.7% diario",
        color=color
    )

    embed.add_field(
        name="🎯 META INDIVIDUAL 12% ACUMULADA",
        value=f"**CUMPLIMIENTO: {cumplen}/{total} ({pct_cumple:.1f}%)**\n{estado_txt}",
        inline=False
    )

    embed.add_field(
        name="🐋 BALLENAS MUERTAS +150M",
        value=f"**{ballenas_muertas} jugadores perdieron poder**\nPoder muerto: {poder_perdido/1e9:.2f}B",
        inline=True
    )

    embed.add_field(
        name="👻 FANTASMAS <500K MÉRITOS",
        value=f"**{fantasmas} jugadores inactivos**\nRevisar en hoja 'FANTASMAS'",
        inline=True
    )

    embed.add_field(
        name="📊 GRÁFICAS INCLUIDAS",
        value="✅ Top 10 Ganadores\n✅ Top 10 Perdedores\n✅ Pastel Cumplimiento",
        inline=False
    )

    embed.set_footer(text=f"Día {dia_actual} KVK | Código generado por TFT")

    archivo = discord.File(buffer, filename=f"KVK_Dia{dia_actual}_Dashboard_PRO.xlsx")
    return embed, archivo

def detectar_columna(df, posibles):
    for col in df.columns:
        if any(p in str(col).lower() for p in posibles):
            return col
    raise ValueError(f"No encontré columna. Buscaba: {posibles}. Tengo: {list(df.columns)}")

from openpyxl.utils.dataframe import dataframe_to_rows
