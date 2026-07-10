import pandas as pd
import discord
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.utils import get_column_letter
import io
import zipfile

# ===== CONFIG =====
PODER_MINIMO = 30_000_000 # Ignorar cuentas menores a 30M
# ==================

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
    nombres_archivos = []
    for ruta in sorted(archivos_excel):
        df = pd.read_excel(ruta)
        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
        dfs.append(df)
        nombres_archivos.append(ruta.split('/')[-1])

    df_inicial = dfs[0]
    df_final = dfs[-1]
    dia_actual = len(dfs)

    # Detectar columnas - más flexible
    col_nombre = detectar_columna(df_final, ['nombre', 'name', 'jugador', 'player'])
    col_poder = detectar_columna(df_final, ['poder', 'power'])
    col_meritos = detectar_columna(df_final, ['meritos', 'méritos', 'merits', 'honor'])

    # ===== FILTRAR GRANJAS < 30M =====
    df_inicial = df_inicial[df_inicial[col_poder] >= PODER_MINIMO].copy()
    df_final = df_final[df_final[col_poder] >= PODER_MINIMO].copy()

    # ===== DETECTAR ALTAS Y BAJAS =====
    jugadores_inicial = set(df_inicial[col_nombre].dropna().astype(str))
    jugadores_final = set(df_final[col_nombre].dropna().astype(str))

    nuevos = jugadores_final - jugadores_inicial # Altas
    bajas = jugadores_inicial - jugadores_final # Bajas

    # Merge y cálculos - CORREGIDO
    df = df_final.merge(df_inicial, on=col_nombre, suffixes=('_final', '_inicial'), how='outer')

    # Limpiar números - quitar comas, M, K, etc
    for col in [f'{col_poder}_final', f'{col_poder}_inicial', f'{col_meritos}_final', f'{col_meritos}_inicial']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '').str.replace('M', 'e6').str.replace('K', 'e3')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 👇 AQUÍ ESTABA EL ERROR - NOMBRES CORREGIDOS
    df['poder_actual'] = df[f'{col_poder}_final'].fillna(0)
    df['poder_inicial'] = df[f'{col_poder}_inicial'].fillna(0)
    df['cambio_poder'] = df['poder_actual'] - df['poder_inicial']
    df['meta_dia'] = df['poder_inicial'] * (1 + 0.017 * dia_actual)
    df['porcentaje_avance'] = ((df['poder_actual'] / df['meta_dia'].replace(0, 1)) - 1) * 100
    df['meritos_ganados'] = df[f'{col_meritos}_final'].fillna(0) - df[f'{col_meritos}_inicial'].fillna(0)

    # Filtrar granjas del resultado final también
    df = df[df['poder_actual'] >= PODER_MINIMO].copy()

    # Estados con emojis claros
    df['estado'] = '🟡 Normal'
    df.loc[df[col_nombre].isin(nuevos), 'estado'] = '🆕 NUEVO'
    df.loc[df[col_nombre].isin(bajas), 'estado'] = '❌ BAJA'
    df.loc[(df['estado']!= '❌ BAJA') & (df['porcentaje_avance'] >= 0), 'estado'] = '🟢 Cumple Meta'
    df.loc[(df['estado']!= '❌ BAJA') & (df['poder_actual'] >= 150_000_000) & (df['cambio_poder'] < 0), 'estado'] = '🔴 Ballena Muerta'
    df.loc[(df['estado']!= '❌ BAJA') & (df['meritos_ganados'] < 500_000) & (df['poder_actual'] > 0), 'estado'] = '👻 Fantasma'
    df.loc[(df['estado']!= '❌ BAJA') & (df['poder_actual'] >= 50_000_000) & (df['porcentaje_avance'] < -5), 'estado'] = '⚠️ Riesgo Kick'

    # Rankings - cambios de posición
    df_final_rank = df_final.copy()
    df_final_rank['rank_actual'] = df_final_rank[col_poder].rank(ascending=False, method='min')
    df_inicial_rank = df_inicial.copy()
    df_inicial_rank['rank_inicial'] = df_inicial_rank[col_poder].rank(ascending=False, method='min')

    df = df.merge(df_final_rank[[col_nombre, 'rank_actual']], on=col_nombre, how='left')
    df = df.merge(df_inicial_rank[[col_nombre, 'rank_inicial']], on=col_nombre, how='left')
    df['cambio_rank'] = df['rank_inicial'].fillna(df['rank_actual']) - df['rank_actual']

    # Métricas - solo jugadores activos y >= 30M
    df_activos = df[df['estado']!= '❌ BAJA'].copy()
    total = len(df_activos)
    cumplen = len(df_activos[df_activos['porcentaje_avance'] >= 0])
    pct_cumple = (cumplen / total) * 100 if total > 0 else 0
    poder_ganado = df_activos[df_activos['cambio_poder'] > 0]['cambio_poder'].sum()
    poder_perdido = abs(df_activos[df_activos['cambio_poder'] < 0]['cambio_poder'].sum())
    fantasmas = len(df_activos[df_activos['estado'] == '👻 Fantasma'])
    ballenas_muertas = len(df_activos[df_activos['estado'] == '🔴 Ballena Muerta'])

    # ===== CREAR EXCEL =====
    wb = Workbook()
    ws_dash = wb.active
    ws_dash.title = "DASHBOARD"

    # Estilos
    titulo_font = Font(bold=True, size=20, color="FFFFFF")
    header_font = Font(bold=True, size=12, color="FFFFFF")
    azul_fill = PatternFill("solid", fgColor="1F4E78")
    verde_fill = PatternFill("solid", fgColor="70AD47")
    rojo_fill = PatternFill("solid", fgColor="C00000")
    amarillo_fill = PatternFill("solid", fgColor="FFC000")
    naranja_fill = PatternFill("solid", fgColor="FF6B35")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Título Dashboard
    ws_dash.merge_cells('A1:N2')
    ws_dash['A1'] = f"⚔️ KVK DÍA {dia_actual} | REPORTE EJECUTIVO TFT"
    ws_dash['A1'].font = titulo_font
    ws_dash['A1'].fill = azul_fill
    ws_dash['A1'].alignment = center

    # ===== RESUMEN EJECUTIVO - 1 LÍNEA =====
    ws_dash.merge_cells('A4:N4')
    resumen = f"📊 {total} ACTIVOS | 🆕 {len(nuevos)} NUEVOS | ❌ {len(bajas)} BAJAS | 🟢 {pct_cumple:.0f}% CUMPLE | 🔴 {poder_perdido/1e9:.1f}B PERDIDO | 💎 FILTRO: >30M"
    ws_dash['A4'] = resumen
    ws_dash['A4'].font = Font(bold=True, size=11)
    ws_dash['A4'].fill = PatternFill("solid", fgColor="E7E6E6")
    ws_dash['A4'].alignment = center

    # Semáforo grande
    ws_dash['A6'] = "ESTADO DEL REINO"
    ws_dash['A6'].font = Font(bold=True, size=14)
    ws_dash.merge_cells('A6:C6')

    if pct_cumple >= 70:
        estado_txt, color = "🟢 ESTABLE", verde_fill
    elif pct_cumple >= 40:
        estado_txt, color = "🟡 EN ALERTA", amarillo_fill
    else:
        estado_txt, color = "🔴 CRÍTICO", rojo_fill

    ws_dash['A7'] = estado_txt
    ws_dash['A7'].font = Font(bold=True, size=24, color="FFFFFF")
    ws_dash['A7'].fill = color
    ws_dash['A7'].alignment = center
    ws_dash.merge_cells('A7:C8')

    # 6 KPIs principales
    kpi_data = [
        ("ACTIVOS", f"{total}", ">30M", azul_fill),
        ("CUMPLEN", f"{cumplen}/{total}", f"{pct_cumple:.0f}%", verde_fill if pct_cumple >= 50 else rojo_fill),
        ("NUEVOS", f"{len(nuevos)}", "Altas", naranja_fill),
        ("BAJAS", f"{len(bajas)}", "Salieron", rojo_fill),
        ("GANADO", f"{poder_ganado/1e9:.1f}B", "Poder", verde_fill),
        ("PERDIDO", f"{poder_perdido/1e9:.1f}B", "Poder", rojo_fill)
    ]

    col_start = 4
    for i, (titulo, valor, sub, color_fill) in enumerate(kpi_data):
        col = col_start + (i * 2)
        ws_dash.cell(6, col, titulo).font = Font(bold=True, size=10)
        ws_dash.cell(7, col, valor).font = Font(size=20, bold=True)
        ws_dash.cell(7, col).fill = color_fill
        ws_dash.cell(7, col).font = Font(size=20, bold=True, color="FFFFFF")
        ws_dash.cell(7, col).alignment = center
        ws_dash.cell(8, col, sub).font = Font(size=9)
        ws_dash.cell(8, col).alignment = center
        ws_dash.merge_cells(start_row=7, start_column=col, end_row=7, end_column=col+1)
        ws_dash.merge_cells(start_row=8, start_column=col, end_row=8, end_column=col+1)

    # ===== TOP MOVERS =====
    ws_dash['A10'] = "📈 TOP 5 SUBIERON MÁS POSICIONES"
    ws_dash['A10'].font = header_font
    ws_dash['A10'].fill = verde_fill
    ws_dash.merge_cells('A10:D10')

    top_suben = df_activos[df_activos['cambio_rank'] > 0].nlargest(5, 'cambio_rank')[[col_nombre, 'cambio_rank', 'cambio_poder']]
    row_start = 11
    ws_dash.cell(row_start, 1, "Jugador").font = Font(bold=True)
    ws_dash.cell(row_start, 2, "↑ Pos").font = Font(bold=True)
    ws_dash.cell(row_start, 3, "Poder Ganado").font = Font(bold=True)

    for i, (_, row) in enumerate(top_suben.iterrows()):
        ws_dash.cell(row_start + 1 + i, 1, str(row[col_nombre])[:20])
        ws_dash.cell(row_start + 1 + i, 2, f"+{int(row['cambio_rank'])}")
        ws_dash.cell(row_start + 1 + i, 3, f"{row['cambio_poder']/1e6:.1f}M")

    ws_dash['F10'] = "📉 TOP 5 BAJARON MÁS POSICIONES"
    ws_dash['F10'].font = header_font
    ws_dash['F10'].fill = rojo_fill
    ws_dash.merge_cells('F10:I10')

    top_bajan = df_activos[df_activos['cambio_rank'] < 0].nsmallest(5, 'cambio_rank')[[col_nombre, 'cambio_rank', 'cambio_poder']]
    ws_dash.cell(row_start, 6, "Jugador").font = Font(bold=True)
    ws_dash.cell(row_start, 7, "↓ Pos").font = Font(bold=True)
    ws_dash.cell(row_start, 8, "Poder Perdido").font = Font(bold=True)

    for i, (_, row) in enumerate(top_bajan.iterrows()):
        ws_dash.cell(row_start + 1 + i, 6, str(row[col_nombre])[:20])
        ws_dash.cell(row_start + 1 + i, 7, f"{int(row['cambio_rank'])}")
        ws_dash.cell(row_start + 1 + i, 8, f"{abs(row['cambio_poder'])/1e6:.1f}M")

    # Gráfica de pastel cumplimiento
    ws_dash['A18'] = "Cumplen"
    ws_dash['A19'] = "No Cumplen"
    ws_dash['B18'] = cumplen
    ws_dash['B19'] = total - cumplen

    pie = PieChart()
    labels = Reference(ws_dash, min_col=1, min_row=18, max_row=19)
    data_pie = Reference(ws_dash, min_col=2, min_row=18, max_row=19)
    pie.add_data(data_pie, titles_from_data=False)
    pie.set_categories(labels)
    pie.title = "Cumplimiento de Meta (>30M)"
    pie.height = 8
    pie.width = 12
    ws_dash.add_chart(pie, "A21")

    # Anchos
    for col in range(1, 15):
        ws_dash.column_dimensions[get_column_letter(col)].width = 16

    # ===== HOJA 2: ALTAS Y BAJAS =====
    ws_mov = wb.create_sheet("ALTAS Y BAJAS")
    ws_mov.merge_cells('A1:E1')
    ws_mov['A1'] = f"🔄 MOVIMIENTOS DEL REINO - DÍA {dia_actual} (FILTRO: >30M)"
    ws_mov['A1'].font = Font(bold=True, size=16, color="FFFFFF")
    ws_mov['A1'].fill = azul_fill
    ws_mov['A1'].alignment = center

    # ALTAS
    ws_mov['A3'] = f"🆕 NUEVOS ({len(nuevos)})"
    ws_mov['A3'].font = header_font
    ws_mov['A3'].fill = verde_fill
    ws_mov.merge_cells('A3:B3')

    ws_mov['A4'] = "Jugador"
    ws_mov['B4'] = "Poder Inicial"
    ws_mov['A4'].font = Font(bold=True)
    ws_mov['B4'].font = Font(bold=True)

    row = 5
    for jugador in sorted(nuevos):
        datos = df[df[col_nombre] == jugador]
        if not datos.empty:
            ws_mov.cell(row, 1, jugador)
            ws_mov.cell(row, 2, f"{datos.iloc[0]['poder_actual']:,.0f}")
            row += 1

    # BAJAS
    ws_mov['D3'] = f"❌ BAJAS ({len(bajas)})"
    ws_mov['D3'].font = header_font
    ws_mov['D3'].fill = rojo_fill
    ws_mov.merge_cells('D3:E3')

    ws_mov['D4'] = "Jugador"
    ws_mov['E4'] = "Último Poder"
    ws_mov['D4'].font = Font(bold=True)
    ws_mov['E4'].font = Font(bold=True)

    row = 5
    for jugador in sorted(bajas):
        datos = df[df[col_nombre] == jugador]
        if not datos.empty:
            ws_mov.cell(row, 4, jugador)
            ws_mov.cell(row, 5, f"{datos.iloc[0]['poder_inicial']:,.0f}")
            row += 1

    for col in range(1, 6):
        ws_mov.column_dimensions[get_column_letter(col)].width = 20

    # ===== HOJA 3: TABLA COMPLETA =====
    ws_tabla = wb.create_sheet("JUGADORES >30M")
    df_export = df[[col_nombre, 'poder_actual', 'poder_inicial', 'cambio_poder', 'meta_dia', 'porcentaje_avance', 'meritos_ganados', 'estado', 'cambio_rank']].copy()
    df_export.columns = ['Nombre', 'Poder Actual', 'Poder Día 1', 'Cambio Poder', 'Meta Día 7', '% vs Meta', 'Méritos Ganados', 'Estado', 'Cambio Rank']

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
        row[8].number_format = '0'

        # Color fila según estado
        if '🟢' in str(row[7].value):
            for cell in row: cell.fill = PatternFill("solid", fgColor="C6EFCE")
        elif '🔴' in str(row[7].value):
            for cell in row: cell.fill = PatternFill("solid", fgColor="FFC7CE")
        elif '👻' in str(row[7].value):
            for cell in row: cell.fill = PatternFill("solid", fgColor="FFEB9C")
        elif '⚠️' in str(row[7].value):
            for cell in row: cell.fill = PatternFill("solid", fgColor="FFD966")
        elif '🆕' in str(row[7].value):
            for cell in row: cell.fill = PatternFill("solid", fgColor="C6EFCE")
        elif '❌' in str(row[7].value):
            for cell in row: cell.fill = PatternFill("solid", fgColor="FFC7CE")

    ws_tabla.auto_filter.ref = ws_tabla.dimensions
    ws_tabla.freeze_panes = 'A2'

    for col in ws_tabla.columns:
        ws_tabla.column_dimensions[get_column_letter(col[0].column)].width = 18

    # ===== HOJA 4: FANTASMAS =====
    ws_fant = wb.create_sheet("FANTASMAS <500K")
    df_fant = df_activos[df_activos['estado'] == '👻 Fantasma'].sort_values('meritos_ganados')[[col_nombre, 'poder_actual', 'meritos_ganados', 'cambio_poder']]
    df_fant.columns = ['Nombre', 'Poder', 'Méritos Ganados', 'Cambio Poder']
    for r in dataframe_to_rows(df_fant, index=False, header=True):
        ws_fant.append(r)

    # ===== HOJA 5: BALLENAS MUERTAS =====
    ws_ball = wb.create_sheet("BALLENAS MUERTAS")
    df_ball = df_activos[df_activos['estado'] == '🔴 Ballena Muerta'].sort_values('cambio_poder')[[col_nombre, 'poder_actual', 'cambio_poder', 'meta_dia']]
    df_ball['Falta para Meta'] = df_ball['meta_dia'] - df_ball['poder_actual']
    df_ball.columns = ['Nombre', 'Poder Actual', 'Perdido', 'Meta Día 7', 'Falta']
    for r in dataframe_to_rows(df_ball, index=False, header=True):
        ws_ball.append(r)

    # ===== HOJA 6: RIESGO KICK =====
    ws_kick = wb.create_sheet("RIESGO KICK")
    df_kick = df_activos[df_activos['estado'] == '⚠️ Riesgo Kick'].sort_values('porcentaje_avance')[[col_nombre, 'poder_actual', 'porcentaje_avance', 'meritos_ganados']]
    df_kick.columns = ['Nombre', 'Poder', '% vs Meta', 'Méritos']
    for r in dataframe_to_rows(df_kick, index=False, header=True):
        ws_kick.append(r)

    # Guardar
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    # Embed DIRECTO - con filtro
    color = 0xFF0000 if pct_cumple < 40 else 0xF1C40F if pct_cumple < 70 else 0x00FF00
    embed = discord.Embed(
        title=f"⚔️ KVK DÍA {dia_actual} | REINO #127",
        description=f"**{estado_txt}** | {cumplen}/{total} cumplen meta | Filtro: >30M",
        color=color
    )

    embed.add_field(
        name="📊 MOVIMIENTOS",
        value=f"🆕 {len(nuevos)} Nuevos\n❌ {len(bajas)} Bajas\n👥 {total} Activos",
        inline=True
    )

    embed.add_field(
        name="💰 PODER",
        value=f"🟢 +{poder_ganado/1e9:.1f}B Ganado\n🔴 -{poder_perdido/1e9:.1f}B Perdido",
        inline=True
    )

    embed.add_field(
        name="⚠️ ALERTAS",
        value=f"👻 {fantasmas} Fantasmas\n🐋 {ballenas_muertas} Ballenas Muertas",
        inline=True
    )

    if len(df_activos) > 0:
        embed.add_field(
            name="📈 TOP GANADORES",
            value="\n".join([f"{i+1}. {row[col_nombre][:15]} +{row['cambio_poder']/1e6:.0f}M"
                            for i, (_, row) in enumerate(df_activos.nlargest(3, 'cambio_poder')[[col_nombre, 'cambio_poder']].iterrows())]),
            inline=True
        )

        embed.add_field(
            name="📉 TOP PERDEDORES",
            value="\n".join([f"{i+1}. {row[col_nombre][:15]} {row['cambio_poder']/1e6:.0f}M"
                            for i, (_, row) in enumerate(df_activos.nsmallest(3, 'cambio_poder')[[col_nombre, 'cambio_poder']].iterrows())]),
            inline=True
        )

    embed.add_field(
        name="📁 HOJAS INCLUIDAS",
        value="✅ Dashboard\n✅ Altas/Bajas\n✅ Jugadores >30M\n✅ Fantasmas\n✅ Ballenas Muertas\n✅ Riesgo Kick",
        inline=False
    )

    embed.set_footer(text=f"Día {dia_actual}/{dia_actual} KVK | Granjas <30M ignoradas | Altas: {len(nuevos)} | Bajas: {len(bajas)}")

    archivo = discord.File(buffer, filename=f"KVK_Dia{dia_actual}_PRO.xlsx")
    return embed, archivo

def detectar_columna(df, posibles):
    for col in df.columns:
        if any(p in str(col).lower() for p in posibles):
            return col
    raise ValueError(f"No encontré columna. Buscaba: {posibles}. Tengo: {list(df.columns)}")

from openpyxl.utils.dataframe import dataframe_to_rows
