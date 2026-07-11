import pandas as pd
import discord
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule, IconSetRule
from openpyxl.utils.dataframe import dataframe_to_rows
import io
import zipfile

# ===== CONFIG =====
PODER_MINIMO = 0 # 0 = Todos los jugadores | 30_000_000 = Solo >30M
MERITOS_ESPERADOS_POR_DIA = 100_000 # Meta: 100k méritos diarios
# ==================

COLORES = {
    'azul_oscuro': '1F4E78',
    'azul_claro': '4472C4',
    'verde': '70AD47',
    'rojo': 'C00000',
    'amarillo': 'FFC000',
    'naranja': 'FF6B35',
    'gris': 'D9D9D9',
    'blanco': 'FFFFFF'
}

def detectar_columna(df, posibles):
    """Detecta columna aunque tenga espacios o mayúsculas"""
    df_cols_lower = {str(col).lower().strip(): col for col in df.columns}
    for posible in posibles:
        if posible.lower() in df_cols_lower:
            return df_cols_lower[posible.lower()]
    raise ValueError(f"❌ No encontré columna. Buscaba: {posibles}. Tengo: {list(df.columns)}")

async def procesar_kvk_por_dia(rutas_archivos):
    # 1. CARGAR ARCHIVOS
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
        raise ValueError("❌ Necesitas mínimo 2 días de KVK en Excel o 1 ZIP con varios")

    # 2. LEER Y LIMPIAR
    dfs = []
    nombres_archivos = []
    for ruta in sorted(archivos_excel):
        df = pd.read_excel(ruta)
        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
        dfs.append(df)
        nombres_archivos.append(ruta.split('/')[-1].replace('.xlsx', ''))

    df_inicial = dfs[0].copy()
    df_final = dfs[-1].copy()
    dia_actual = len(dfs)

    # 3. DETECTAR COLUMNAS
    col_nombre = detectar_columna(df_final, ['nombre', 'name', 'jugador', 'player'])
    col_poder = detectar_columna(df_final, ['poder', 'power'])
    col_meritos = detectar_columna(df_final, ['meritos', 'méritos', 'merits', 'honor'])

    # 4. LIMPIAR NÚMEROS - ROBUSTO CONTRA M, K, B
    for df in [df_inicial, df_final]:
        # Poder
        df[col_poder] = (df[col_poder].astype(str)
                      .str.replace(',', '', regex=False)
                      .str.replace(' ', '', regex=False)
                      .str.replace('M', 'e6', case=False, regex=False)
                      .str.replace('K', 'e3', case=False, regex=False)
                      .str.replace('B', 'e9', case=False, regex=False))
        df[col_poder] = pd.to_numeric(df[col_poder], errors='coerce').fillna(0)

        # Méritos
        df[col_meritos] = (df[col_meritos].astype(str)
                      .str.replace(',', '', regex=False)
                      .str.replace(' ', '', regex=False)
                      .str.replace('M', 'e6', case=False, regex=False)
                      .str.replace('K', 'e3', case=False, regex=False))
        df[col_meritos] = pd.to_numeric(df[col_meritos], errors='coerce').fillna(0)

    # 5. FILTRAR SI HAY LÍMITE
    if PODER_MINIMO > 0:
        df_inicial = df_inicial[df_inicial[col_poder] >= PODER_MINIMO].copy()
        df_final = df_final[df_final[col_poder] >= PODER_MINIMO].copy()

    if len(df_final) == 0:
        raise ValueError(f"❌ No hay jugadores con poder > {PODER_MINIMO:,}")

    # 6. DETECTAR ALTAS Y BAJAS
    jugadores_inicial = set(df_inicial[col_nombre].dropna().astype(str))
    jugadores_final = set(df_final[col_nombre].dropna().astype(str))
    nuevos = jugadores_final - jugadores_inicial
    bajas = jugadores_inicial - jugadores_final

    # 7. MERGE
    df = df_final.merge(df_inicial, on=col_nombre, how='outer', suffixes=('', '_old'))
    df = df.rename(columns={
        f'{col_poder}': 'poder_actual',
        f'{col_poder}_old': 'poder_inicial',
        f'{col_meritos}': 'meritos_final',
        f'{col_meritos}_old': 'meritos_inicial'
    })

    df['poder_actual'] = df['poder_actual'].fillna(0)
    df['poder_inicial'] = df['poder_inicial'].fillna(0)
    df['meritos_final'] = df['meritos_final'].fillna(0)
    df['meritos_inicial'] = df['meritos_inicial'].fillna(0)

    if PODER_MINIMO > 0:
        df = df[df['poder_actual'] >= PODER_MINIMO].copy()

    # 8. CÁLCULOS - PROTEGIDO CONTRA DIVISIÓN POR CERO
    df['cambio_poder'] = df['poder_actual'] - df['poder_inicial']
    df['cambio_poder_pct'] = ((df['poder_actual'] / df['poder_inicial'].replace(0, 1)) - 1) * 100
    df['meta_dia'] = df['poder_inicial'] * (1 + 0.017 * dia_actual)
    df['porcentaje_avance'] = ((df['poder_actual'] / df['meta_dia'].replace(0, 1)) - 1) * 100
    df['meritos_ganados'] = df['meritos_final'] - df['meritos_inicial']
    df['meritos_por_dia'] = df['meritos_ganados'] / dia_actual

    # MÉTRICAS PARA RANKING GENERAL
    df['poder_maximo'] = df[['poder_actual', 'poder_inicial']].max(axis=1)
    df['pct_meritos_vs_poder'] = (df['meritos_ganados'] / df['poder_maximo'].replace(0, 1)) * 100
    df['meritos_por_semana'] = df['meritos_ganados'] / (dia_actual / 7)
    df['eficiencia_meritos'] = df['meritos_ganados'] / (df['poder_maximo'] / 1_000_000).replace(0, 1)
    df['meta_meritos'] = MERITOS_ESPERADOS_POR_DIA * dia_actual
    df['pct_meta_meritos'] = ((df['meritos_ganados'] / df['meta_meritos'].replace(0, 1)) - 1) * 100

    # 9. ESTADOS
    df['estado'] = '🟡 Normal'
    df.loc[df[col_nombre].isin(nuevos), 'estado'] = '🆕 NUEVO'
    df.loc[df[col_nombre].isin(bajas), 'estado'] = '❌ BAJA'
    df.loc[(df['estado']!= '❌ BAJA') & (df['porcentaje_avance'] >= 0), 'estado'] = '🟢 Cumple Meta'
    df.loc[(df['estado']!= '❌ BAJA') & (df['poder_actual'] >= 150_000_000) & (df['cambio_poder'] < 0), 'estado'] = '🔴 Ballena Muerta'
    df.loc[(df['estado']!= '❌ BAJA') & (df['meritos_ganados'] < 500_000) & (df['poder_actual'] > 0), 'estado'] = '👻 Fantasma'
    df.loc[(df['estado']!= '❌ BAJA') & (df['poder_actual'] >= 50_000_000) & (df['porcentaje_avance'] < -5), 'estado'] = '⚠️ Riesgo Kick'
    df.loc[(df['estado']!= '❌ BAJA') & (df['pct_meta_meritos'] < -50), 'estado'] = '📉 Sin Méritos'

    # 10. RANKINGS - CON PROTECCIÓN pd.notna()
    df_final_rank = df_final[[col_nombre, col_poder]].copy()
    df_final_rank['rank_actual'] = df_final_rank[col_poder].rank(ascending=False, method='min')

    df_inicial_rank = df_inicial[[col_nombre, col_poder]].copy()
    df_inicial_rank['rank_inicial'] = df_inicial_rank[col_poder].rank(ascending=False, method='min')

    df = df.merge(df_final_rank[[col_nombre, 'rank_actual']], on=col_nombre, how='left')
    df = df.merge(df_inicial_rank[[col_nombre, 'rank_inicial']], on=col_nombre, how='left')
    df['cambio_rank'] = df['rank_inicial'].fillna(df['rank_actual']) - df['rank_actual']

    # 11. MÉTRICAS GLOBALES
    df_activos = df[df['estado']!= '❌ BAJA'].copy()
    total = len(df_activos)
    cumplen = len(df_activos[df_activos['porcentaje_avance'] >= 0])
    pct_cumple = (cumplen / total) * 100 if total > 0 else 0
    poder_ganado = df_activos[df_activos['cambio_poder'] > 0]['cambio_poder'].sum()
    poder_perdido = abs(df_activos[df_activos['cambio_poder'] < 0]['cambio_poder'].sum())
    fantasmas = len(df_activos[df_activos['estado'] == '👻 Fantasma'])
    ballenas_muertas = len(df_activos[df_activos['estado'] == '🔴 Ballena Muerta'])
    sin_meritos = len(df_activos[df_activos['estado'] == '📉 Sin Méritos'])
    meritos_totales = df_activos['meritos_ganados'].sum()
    eficiencia_promedio = df_activos[df_activos['poder_maximo'] > 0]['eficiencia_meritos'].mean()

    # ===== CREAR EXCEL =====
    wb = Workbook()
    ws_dash = wb.active
    ws_dash.title = "EXECUTIVE DASHBOARD"

    # Estilos
    titulo_style = Font(bold=True, size=22, color=COLORES['blanco'], name='Calibri')
    header_style = Font(bold=True, size=11, color=COLORES['blanco'], name='Calibri')
    kpi_valor_style = Font(bold=True, size=24, color=COLORES['blanco'], name='Calibri')
    kpi_titulo_style = Font(bold=True, size=10, color=COLORES['azul_oscuro'], name='Calibri')

    border_thick = Border(
        left=Side(style='medium', color=COLORES['azul_oscuro']),
        right=Side(style='medium', color=COLORES['azul_oscuro']),
        top=Side(style='medium', color=COLORES['azul_oscuro']),
        bottom=Side(style='medium', color=COLORES['azul_oscuro'])
    )
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # HEADER
    ws_dash.merge_cells('A1:P3')
    ws_dash['A1'] = f"⚔️ REPORTE EJECUTIVO KVK | DÍA {dia_actual}"
    ws_dash['A1'].font = titulo_style
    ws_dash['A1'].fill = PatternFill("solid", fgColor=COLORES['azul_oscuro'])
    ws_dash['A1'].alignment = center
    ws_dash['A1'].border = border_thick

    ws_dash.merge_cells('A4:P4')
    filtro_txt = f"Filtro: >{PODER_MINIMO/1e6:.0f}M" if PODER_MINIMO > 0 else "Todos los jugadores"
    ws_dash['A4'] = f"Período: {nombres_archivos[0]} → {nombres_archivos[-1]} | {filtro_txt}"
    ws_dash['A4'].font = Font(size=11, italic=True, color=COLORES['azul_oscuro'])
    ws_dash['A4'].fill = PatternFill("solid", fgColor=COLORES['gris'])
    ws_dash['A4'].alignment = center

    # SEMÁFORO
    ws_dash['A6'] = "ESTADO GENERAL"
    ws_dash['A6'].font = kpi_titulo_style
    ws_dash.merge_cells('A6:C6')

    if pct_cumple >= 70:
        estado_txt, color = "🟢 ESTABLE", COLORES['verde']
    elif pct_cumple >= 40:
        estado_txt, color = "🟡 ALERTA", COLORES['amarillo']
    else:
        estado_txt, color = "🔴 CRÍTICO", COLORES['rojo']

    ws_dash['A7'] = estado_txt
    ws_dash['A7'].font = Font(bold=True, size=28, color=COLORES['blanco'])
    ws_dash['A7'].fill = PatternFill("solid", fgColor=color)
    ws_dash['A7'].alignment = center
    ws_dash['A7'].border = border_thick
    ws_dash.merge_cells('A7:C9')

    # KPIs
    kpi_data = [
        ("MIEMBROS ACTIVOS", f"{total}", f"+{len(nuevos)} -{len(bajas)}", COLORES['azul_claro']),
        ("TASA CUMPLIMIENTO", f"{pct_cumple:.1f}%", f"{cumplen}/{total}", COLORES['verde'] if pct_cumple >= 50 else COLORES['rojo']),
        ("PODER GANADO", f"{poder_ganado/1e9:.2f}B", "Total", COLORES['verde']),
        ("PODER PERDIDO", f"{poder_perdido/1e9:.2f}B", "Total", COLORES['rojo']),
        ("MÉRITOS/DÍA", f"{meritos_totales/dia_actual/1e6:.1f}M", f"Meta: {MERITOS_ESPERADOS_POR_DIA/1e3:.0f}K", COLORES['naranja']),
        ("EFICIENCIA MÉRITOS", f"{eficiencia_promedio:.1f}", "Méritos/1M Poder", COLORES['azul_claro']),
        ("FANTASMAS", f"{fantasmas}", f"{fantasmas/total*100:.0f}%", COLORES['amarillo']),
        ("SIN MÉRITOS", f"{sin_meritos}", f"{sin_meritos/total*100:.0f}%", COLORES['rojo'])
    ]

    col_start = 4
    for i, (titulo, valor, sub, color_fill) in enumerate(kpi_data):
        col = col_start + (i * 2)
        ws_dash.cell(6, col, titulo).font = kpi_titulo_style
        ws_dash.cell(6, col).alignment = center
        ws_dash.merge_cells(start_row=6, start_column=col, end_row=6, end_column=col+1)

        ws_dash.cell(7, col, valor).font = kpi_valor_style
        ws_dash.cell(7, col).fill = PatternFill("solid", fgColor=color_fill)
        ws_dash.cell(7, col).alignment = center
        ws_dash.cell(7, col).border = border_thick
        ws_dash.merge_cells(start_row=7, start_column=col, end_row=8, end_column=col+1)

        ws_dash.cell(9, col, sub).font = Font(size=9, color=COLORES['azul_oscuro'])
        ws_dash.cell(9, col).alignment = center
        ws_dash.merge_cells(start_row=9, start_column=col, end_row=9, end_column=col+1)

    # TOP MOVERS
    ws_dash['A11'] = "📈 TOP 5 ESCALARON POSICIONES"
    ws_dash['A11'].font = header_style
    ws_dash['A11'].fill = PatternFill("solid", fgColor=COLORES['verde'])
    ws_dash.merge_cells('A11:D11')

    headers = ['Jugador', '↑ Pos', 'Poder Ganado', 'Eficiencia']
    for i, h in enumerate(headers):
        cell = ws_dash.cell(12, i+1, h)
        cell.font = Font(bold=True, color=COLORES['blanco'])
        cell.fill = PatternFill("solid", fgColor=COLORES['azul_claro'])
        cell.alignment = center

    top_suben = df_activos[df_activos['cambio_rank'] > 0].nlargest(5, 'cambio_rank')[[col_nombre, 'cambio_rank', 'cambio_poder', 'eficiencia_meritos']]
    for i, (_, row) in enumerate(top_suben.iterrows()):
        ws_dash.cell(13 + i, 1, str(row[col_nombre])[:25])
        ws_dash.cell(13 + i, 2, f"+{int(row['cambio_rank'])}")
        ws_dash.cell(13 + i, 3, f"{row['cambio_poder']/1e6:.1f}M")
        ws_dash.cell(13 + i, 4, f"{row['eficiencia_meritos']:.1f}")
        for col in range(1, 5):
            ws_dash.cell(13 + i, col).alignment = Alignment(horizontal="center")

    ws_dash['F11'] = "📉 TOP 5 CAYERON POSICIONES"
    ws_dash['F11'].font = header_style
    ws_dash['F11'].fill = PatternFill("solid", fgColor=COLORES['rojo'])
    ws_dash.merge_cells('F11:I11')

    for i, h in enumerate(headers):
        cell = ws_dash.cell(12, i+6, h)
        cell.font = Font(bold=True, color=COLORES['blanco'])
        cell.fill = PatternFill("solid", fgColor=COLORES['azul_claro'])
        cell.alignment = center

    top_bajan = df_activos[df_activos['cambio_rank'] < 0].nsmallest(5, 'cambio_rank')[[col_nombre, 'cambio_rank', 'cambio_poder', 'eficiencia_meritos']]
    for i, (_, row) in enumerate(top_bajan.iterrows()):
        ws_dash.cell(13 + i, 6, str(row[col_nombre])[:25])
        ws_dash.cell(13 + i, 7, f"{int(row['cambio_rank'])}")
        ws_dash.cell(13 + i, 8, f"{abs(row['cambio_poder'])/1e6:.1f}M")
        ws_dash.cell(13 + i, 9, f"{row['eficiencia_meritos']:.1f}")
        for col in range(6, 10):
            ws_dash.cell(13 + i, col).alignment = Alignment(horizontal="center")

    # Gráfica
    ws_dash['A20'] = "Cumplen"
    ws_dash['A21'] = "No Cumplen"
    ws_dash['B20'] = cumplen
    ws_dash['B21'] = total - cumplen

    pie = PieChart()
    pie.add_data(Reference(ws_dash, min_col=2, max_col=2, min_row=20, max_row=21))
    pie.set_categories(Reference(ws_dash, min_col=1, max_col=1, min_row=20, max_row=21))
    pie.title = "Distribución de Cumplimiento"
    pie.height = 8
    pie.width = 12
    ws_dash.add_chart(pie, "A23")

    for col in range(1, 17):
        ws_dash.column_dimensions[get_column_letter(col)].width = 14

    # ===== HOJA 2: RANKING GENERAL =====
    ws_ranking = wb.create_sheet("RANKING GENERAL")
    ws_ranking.merge_cells('A1:I1')
    ws_ranking['A1'] = f"🏆 RANKING GENERAL - TODOS LOS JUGADORES"
    ws_ranking['A1'].font = titulo_style
    ws_ranking['A1'].fill = PatternFill("solid", fgColor=COLORES['azul_oscuro'])
    ws_ranking['A1'].alignment = center

    ws_ranking.merge_cells('A2:I2')
    ws_ranking['A2'] = f"Ordenado por % Méritos vs Poder Máximo | Período: {dia_actual} días"
    ws_ranking['A2'].font = Font(size=11, italic=True, color=COLORES['azul_oscuro'])
    ws_ranking['A2'].fill = PatternFill("solid", fgColor=COLORES['gris'])
    ws_ranking['A2'].alignment = center

    df_ranking = df_activos.sort_values('pct_meritos_vs_poder', ascending=False).copy()
    df_ranking['posicion'] = range(1, len(df_ranking) + 1)

    headers_ranking = ['Pos', 'Jugador', 'Poder Máx', 'Méritos Ganados', '% Méritos/Poder', 'Méritos/Semana', 'Efic. Méritos', 'Estado', 'Cambio Rank']
    for i, h in enumerate(headers_ranking):
        cell = ws_ranking.cell(4, i+1, h)
        cell.font = header_style
        cell.fill = PatternFill("solid", fgColor=COLORES['azul_claro'])
        cell.alignment = center
        cell.border = border_thick

    row_start = 5
    for idx, (_, row) in enumerate(df_ranking.iterrows()):
        ws_ranking.cell(row_start + idx, 1, int(row['posicion']))
        ws_ranking.cell(row_start + idx, 2, str(row[col_nombre])[:30])
        ws_ranking.cell(row_start + idx, 3, row['poder_maximo'])
        ws_ranking.cell(row_start + idx, 4, row['meritos_ganados'])
        ws_ranking.cell(row_start + idx, 5, row['pct_meritos_vs_poder'] / 100)
        ws_ranking.cell(row_start + idx, 6, row['meritos_por_semana'])
        ws_ranking.cell(row_start + idx, 7, row['eficiencia_meritos'])
        ws_ranking.cell(row_start + idx, 8, str(row['estado']))
        ws_ranking.cell(row_start + idx, 9, int(row['cambio_rank']) if pd.notna(row['cambio_rank']) else 0)

        ws_ranking.cell(row_start + idx, 3).number_format = '#,##0'
        ws_ranking.cell(row_start + idx, 4).number_format = '#,##0'
        ws_ranking.cell(row_start + idx, 5).number_format = '0.00%'
        ws_ranking.cell(row_start + idx, 6).number_format = '#,##0'
        ws_ranking.cell(row_start + idx, 7).number_format = '0.00'
        ws_ranking.cell(row_start + idx, 9).number_format = '+0;-0;0'

        if idx < 3:
            for col in range(1, 10):
                ws_ranking.cell(row_start + idx, col).fill = PatternFill("solid", fgColor='FFD700')
        elif idx < 10:
            for col in range(1, 10):
                ws_ranking.cell(row_start + idx, col).fill = PatternFill("solid", fgColor='E8E8E8')

        for col in range(1, 10):
            ws_ranking.cell(row_start + idx, col).alignment = Alignment(horizontal="center")

    ws_ranking.conditional_formatting.add(
        f'E{row_start}:E{row_start + len(df_ranking) - 1}',
        DataBarRule(start_type='num', start_value=0, end_type='max',
                   color=COLORES['verde'], showValue=True)
    )

    ws_ranking.conditional_formatting.add(
        f'G{row_start}:G{row_start + len(df_ranking) - 1}',
        IconSetRule('3TrafficLights1', 'num', [0, 5, 10], showValue=True)
    )

    ws_ranking.auto_filter.ref = f"A4:I{row_start + len(df_ranking) - 1}"
    ws_ranking.freeze_panes = 'A5'

    for col in range(1, 10):
        ws_ranking.column_dimensions[get_column_letter(col)].width = 18

    # HOJA 3: MOVIMIENTOS
    ws_mov = wb.create_sheet("MOVIMIENTOS")
    ws_mov.merge_cells('A1:F1')
    ws_mov['A1'] = f"🔄 MOVIMIENTOS DEL REINO | DÍA {dia_actual}"
    ws_mov['A1'].font = titulo_style
    ws_mov['A1'].fill = PatternFill("solid", fgColor=COLORES['azul_oscuro'])
    ws_mov['A1'].alignment = center

    ws_mov['A3'] = f"🆕 NUEVOS INGRESOS ({len(nuevos)})"
    ws_mov['A3'].font = header_style
    ws_mov['A3'].fill = PatternFill("solid", fgColor=COLORES['verde'])
    ws_mov.merge_cells('A3:C3')

    headers_altas = ['Jugador', 'Poder', 'Eficiencia Méritos']
    for i, h in enumerate(headers_altas):
        cell = ws_mov.cell(4, i+1, h)
        cell.font = Font(bold=True, color=COLORES['blanco'])
        cell.fill = PatternFill("solid", fgColor=COLORES['azul_claro'])
        cell.alignment = center

    row = 5
    df_nuevos = df[df[col_nombre].isin(nuevos)].sort_values('poder_actual', ascending=False)
    for _, jugador in df_nuevos.iterrows():
        ws_mov.cell(row, 1, str(jugador[col_nombre])[:30])
        ws_mov.cell(row, 2, jugador['poder_actual'])
        ws_mov.cell(row, 3, jugador['eficiencia_meritos'])
        ws_mov.cell(row, 2).number_format = '#,##0'
        ws_mov.cell(row, 3).number_format = '0.00'
        row += 1

    ws_mov['E3'] = f"❌ BAJAS ({len(bajas)})"
    ws_mov['E3'].font = header_style
    ws_mov['E3'].fill = PatternFill("solid", fgColor=COLORES['rojo'])
    ws_mov.merge_cells('E3:G3')

    headers_bajas = ['Jugador', 'Último Poder', 'Rank']
    for i, h in enumerate(headers_bajas):
        cell = ws_mov.cell(4, i+5, h)
        cell.font = Font(bold=True, color=COLORES['blanco'])
        cell.fill = PatternFill("solid", fgColor=COLORES['azul_claro'])
        cell.alignment = center

    row = 5
    df_bajas = df[df[col_nombre].isin(bajas)].sort_values('poder_inicial', ascending=False)
    for _, jugador in df_bajas.iterrows():
        ws_mov.cell(row, 5, str(jugador[col_nombre])[:30])
        ws_mov.cell(row, 6, jugador['poder_inicial'])
        ws_mov.cell(row, 7, f"#{int(jugador['rank_inicial'])}" if pd.notna(jugador['rank_inicial']) else "N/A")
        ws_mov.cell(row, 6).number_format = '#,##0'
        row += 1

    for col in range(1, 8):
        ws_mov.column_dimensions[get_column_letter(col)].width = 20

    # HOJA 4: DETALLE COMPLETO
    ws_tabla = wb.create_sheet("DETALLE COMPLETO")
    ws_tabla.merge_cells('A1:L1')
    ws_tabla['A1'] = f"📊 DETALLE DE TODOS LOS JUGADORES"
    ws_tabla['A1'].font = titulo_style
    ws_tabla['A1'].fill = PatternFill("solid", fgColor=COLORES['azul_oscuro'])
    ws_tabla['A1'].alignment = center

    df_export = df[[col_nombre, 'poder_actual', 'poder_inicial', 'cambio_poder', 'cambio_poder_pct', 'meta_dia', 'porcentaje_avance', 'meritos_ganados', 'eficiencia_meritos', 'pct_meta_meritos', 'estado', 'cambio_rank']].copy()
    df_export.columns = ['Nombre', 'Poder Actual', 'Poder Inicial', 'Cambio Poder', '% Cambio', 'Meta Día 7', '% vs Meta', 'Méritos Ganados', 'Efic. Méritos', '% Meta Méritos', 'Estado', 'Cambio Rank']

    for r in dataframe_to_rows(df_export, index=False, header=True):
        ws_tabla.append(r)

    for cell in ws_tabla[2]:
        cell.font = header_style
        cell.fill = PatternFill("solid", fgColor=COLORES['azul_claro'])
        cell.alignment = center
        cell.border = border_thick

    for row in ws_tabla.iter_rows(min_row=3, max_row=len(df_export)+2):
        row[1].number_format = '#,##0'
        row[2].number_format = '#,##0'
        row[3].number_format = '#,##0'
        row[4].number_format = '0.0%'
        row[5].number_format = '#,##0'
        row[6].number_format = '0.0%'
        row[7].number_format = '#,##0'
        row[8].number_format = '0.00'
        row[9].number_format = '0.0%'
        row[11].number_format = '0'

    ws_tabla.conditional_formatting.add(
        f'D3:D{len(df_export)+2}',
        DataBarRule(start_type='num', start_value=-10000000, end_type='num', end_value=10000000,
                   color=COLORES['azul_claro'], showValue=True)
    )

    ws_tabla.conditional_formatting.add(
        f'G3:G{len(df_export)+2}',
        IconSetRule('3Arrows', 'percent', [0, 33, 67], showValue=True)
    )

    ws_tabla.conditional_formatting.add(
        f'I3:I{len(df_export)+2}',
        ColorScaleRule(start_type='min', start_color='FF6B6B',
                      mid_type='percentile', mid_value=50, mid_color='FFD93D',
                      end_type='max', end_color='6BCF7F')
    )

    for row in ws_tabla.iter_rows(min_row=3, max_row=len(df_export)+2):
        estado = str(row[10].value)
        if '🟢' in estado:
            for cell in row: cell.fill = PatternFill("solid", fgColor='E2EFDA')
        elif '🔴' in estado:
            for cell in row: cell.fill = PatternFill("solid", fgColor='FFC7CE')
        elif '👻' in estado:
            for cell in row: cell.fill = PatternFill("solid", fgColor='FFF2CC')
        elif '⚠️' in estado:
            for cell in row: cell.fill = PatternFill("solid", fgColor='FFE699')
        elif '🆕' in estado:
            for cell in row: cell.fill = PatternFill("solid", fgColor='C6E0B4')
        elif '📉' in estado:
            for cell in row: cell.fill = PatternFill("solid", fgColor='FCE4D6')

    ws_tabla.auto_filter.ref = f"A2:L{len(df_export)+2}"
    ws_tabla.freeze_panes = 'A3'

    for col in range(1, 13):
        ws_tabla.column_dimensions[get_column_letter(col)].width = 18

    # HOJAS DE CATEGORÍAS
    hojas_categorias = [
        ("FANTASMAS", df_activos[df_activos['estado'] == '👻 Fantasma'], 'meritos_ganados', 'asc'),
        ("BALLENAS MUERTAS", df_activos[df_activos['estado'] == '🔴 Ballena Muerta'], 'cambio_poder', 'asc'),
        ("RIESGO KICK", df_activos[df_activos['estado'] == '⚠️ Riesgo Kick'], 'porcentaje_avance', 'asc'),
        ("SIN MÉRITOS", df_activos[df_activos['estado'] == '📉 Sin Méritos'], 'pct_meta_meritos', 'asc')
    ]

    for nombre_hoja, df_cat, sort_col, orden in hojas_categorias:
        ws = wb.create_sheet(nombre_hoja)
        ws.merge_cells('A1:F1')
        ws['A1'] = f"⚠️ {nombre_hoja} - {len(df_cat)} JUGADORES"
        ws['A1'].font = titulo_style
        ws['A1'].fill = PatternFill("solid", fgColor=COLORES['rojo'])
        ws['A1'].alignment = center

        df_cat_export = df_cat[[col_nombre, 'poder_actual', 'cambio_poder', 'porcentaje_avance', 'meritos_ganados', 'eficiencia_meritos']].copy()
        df_cat_export = df_cat_export.sort_values(sort_col, ascending=(orden=='asc'))
        df_cat_export.columns = ['Nombre', 'Poder Actual', 'Cambio Poder', '% vs Meta', 'Méritos Ganados', 'Efic. Méritos']

        for r in dataframe_to_rows(df_cat_export, index=False, header=True):
            ws.append(r)

        for cell in ws[2]:
            cell.font
