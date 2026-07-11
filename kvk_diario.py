import pandas as pd
import discord
from discord.ext import commands
from discord import app_commands
from typing import List
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule, IconSetRule
from openpyxl.utils.dataframe import dataframe_to_rows
import io
import zipfile
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

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

async def procesar_kvk_por_dia(archivos_bytes_list):
    # 1. CARGAR ARCHIVOS
    dfs = []
    nombres_archivos = []
    for i, archivo_bytes in enumerate(archivos_bytes_list):
        try:
            with zipfile.ZipFile(io.BytesIO(archivo_bytes), 'r') as zip_ref:
                for name in sorted(zip_ref.namelist()):
                    if name.endswith('.xlsx'):
                        df = pd.read_excel(io.BytesIO(zip_ref.read(name)))
                        dfs.append(df)
                        nombres_archivos.append(name.replace('.xlsx', ''))
        except:
            df = pd.read_excel(io.BytesIO(archivo_bytes))
            dfs.append(df)
            nombres_archivos.append(f"Dia_{i+1}")

    if len(dfs) < 2:
        raise ValueError("❌ Necesitas mínimo 2 días de KVK")

    # 2. LEER Y LIMPIAR
    for df in dfs:
        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')

    df_inicial = dfs[0].copy()
    df_final = dfs[-1].copy()
    dia_actual = len(dfs)

    # 3. DETECTAR COLUMNAS - CORREGIDO PARA CoD
    col_nombre = detectar_columna(df_final, ['nombre_de_personaje', 'nombre', 'name', 'jugador', 'player'])
    col_poder = detectar_columna(df_final, ['poder_actual', 'poder', 'power'])
    col_meritos = detectar_columna(df_final, ['meritos', 'méritos', 'merits', 'honor_points', 'honor'])

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
        f'{col_poder}': 'poder_actual', f'{col_poder}_old': 'poder_inicial',
        f'{col_meritos}': 'meritos_final', f'{col_meritos}_old': 'meritos_inicial'
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

    for col in range(1, 17):
        ws_dash.column_dimensions[get_column_letter(col)].width = 14

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer

# BOT DISCORD
class KVKBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

bot = KVKBot()

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'✅ Comandos sincronizados: {len(synced)}')
    except Exception as e:
        print(f'Error sync: {e}')

@bot.tree.command(name="kvk", description="Reporte KVK")
@app_commands.describe(archivos="Sube tus Excel o ZIP")
async def kvk_slash(interaction: discord.Interaction, archivos: List[discord.Attachment]):
    await interaction.response.defer(thinking=True)
    try:
        archivos_bytes = [await a.read() for a in archivos]
        excel = await procesar_kvk_por_dia(archivos_bytes)
        await interaction.followup.send(file=discord.File(fp=excel, filename=f"Reporte_KVK_{datetime.now().day}.xlsx"))
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error: `{str(e)}`", ephemeral=True)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN:
    bot.run(TOKEN)
