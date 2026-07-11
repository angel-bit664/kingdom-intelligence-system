import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, DoughnutChart, Reference, LineChart
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule, IconSetRule
from openpyxl.worksheet.table import Table, TableStyleInfo
import io
import zipfile
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands
from typing import List
import gc
import os
import sys
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

# ===== CONFIG CoD =====
PODER_MINIMO = 0
MERITOS_ESPERADOS_POR_DIA = 80_000
NIVEL_AYUNTA_MINIMO = 0
# ======================

COLORES = {
    'google_blue': '4285F4',
    'google_green': '34A853',
    'google_yellow': 'FBBC05',
    'google_red': 'EA4335',
    'dark': '202124',
    'gray_100': 'F8F9FA',
    'gray_300': 'DADCE0',
    'white': 'FFFFFF'
}

def detectar_columna(df, posibles):
    df_cols = {str(col).lower().strip(): col for col in df.columns}
    for posible in posibles:
        if posible.lower() in df_cols:
            return df_cols[posible.lower()]
    for posible in posibles:
        for col_lower, col_real in df_cols.items():
            if posible.lower() in col_lower:
                return col_real
    raise ValueError(f"❌ No encontré columna. Buscaba: {posibles}. Tengo: {list(df.columns)}")

def limpiar_numero(serie):
    return (serie.astype(str).str.replace(',', '', regex=False)
         .str.replace(' ', '', regex=False)
         .str.replace('M', 'e6', case=False, regex=False)
         .str.replace('K', 'e3', case=False, regex=False)
         .str.replace('B', 'e9', case=False, regex=False)
         .pipe(pd.to_numeric, errors='coerce').fillna(0))

def crear_kpi_card(ws, row, col, titulo, valor, subtitulo, color, icono="📊"):
    thin = Side(style='thin', color=COLORES['gray_300'])
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    ws.merge_cells(start_row=row, start_column=col, end_row=row+3, end_column=col+2)
    ws.cell(row, col, f"{icono} {titulo}").font = Font(bold=True, size=9, color=COLORES['dark'])
    ws.cell(row, col).alignment = Alignment(horizontal="left", vertical="center")
    ws.merge_cells(start_row=row+1, start_column=col, end_row=row+1, end_column=col+2)
    ws.cell(row+1, col, valor).font = Font(bold=True, size=20, color=color)
    ws.cell(row+1, col).alignment = Alignment(horizontal="left", vertical="center")
    ws.merge_cells(start_row=row+2, start_column=col, end_row=row+2, end_column=col+2)
    ws.cell(row+2, col, subtitulo).font = Font(size=8, color=COLORES['dark'])
    ws.cell(row+2, col).alignment = Alignment(horizontal="left", vertical="center")
    for r in range(row, row+4):
        for c in range(col, col+3):
            ws.cell(r, c).border = border
            ws.cell(r, c).fill = PatternFill("solid", fgColor=COLORES['white'])

async def procesar_kvk_cod(archivos_bytes_list):
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

    for df in dfs:
        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')

    df_inicial = dfs[0].copy()
    df_final = dfs[-1].copy()
    dia_actual = len(dfs)

    col_nombre = detectar_columna(df_final, ['nombre_de_personaje', 'nombre', 'player_name', 'jugador'])
    col_poder = detectar_columna(df_final, ['poder_actual', 'poder', 'power'])
    col_meritos = detectar_columna(df_final, ['meritos', 'méritos', 'merits', 'honor_points'])
    col_nivel = detectar_columna(df_final, ['nivel_ayuntamiento', 'city_hall', 'nivel', 'level'])

    for df in [df_inicial, df_final]:
        df[col_poder] = limpiar_numero(df[col_poder])
        df[col_meritos] = limpiar_numero(df[col_meritos])
        df[col_nivel] = pd.to_numeric(df[col_nivel], errors='coerce').fillna(0)

    if PODER_MINIMO > 0:
        df_inicial = df_inicial[df_inicial[col_poder] >= PODER_MINIMO].copy()
        df_final = df_final[df_final[col_poder] >= PODER_MINIMO].copy()
    if NIVEL_AYUNTA_MINIMO > 0:
        df_inicial = df_inicial[df_inicial[col_nivel] >= NIVEL_AYUNTA_MINIMO].copy()
        df_final = df_final[df_final[col_nivel] >= NIVEL_AYUNTA_MINIMO].copy()

    if len(df_final) == 0:
        raise ValueError(f"❌ No hay jugadores con filtros aplicados")

    jugadores_inicial = set(df_inicial[col_nombre].dropna().astype(str))
    jugadores_final = set(df_final[col_nombre].dropna().astype(str))
    nuevos = jugadores_final - jugadores_inicial
    bajas = jugadores_inicial - jugadores_final

    df = df_final.merge(df_inicial, on=col_nombre, how='outer', suffixes=('', '_old'))
    df = df.rename(columns={
        f'{col_poder}': 'poder_actual', f'{col_poder}_old': 'poder_inicial',
        f'{col_meritos}': 'meritos_final', f'{col_meritos}_old': 'meritos_inicial',
        f'{col_nivel}': 'nivel_actual', f'{col_nivel}_old': 'nivel_inicial'
    })

    for col in ['poder_actual', 'poder_inicial', 'meritos_final', 'meritos_inicial', 'nivel_actual', 'nivel_inicial']:
        df[col] = df[col].fillna(0)

    df['cambio_poder'] = df['poder_actual'] - df['poder_inicial']
    df['cambio_poder_pct'] = ((df['poder_actual'] / df['poder_inicial'].replace(0, 1)) - 1) * 100
    df['meta_dia'] = df['poder_inicial'] * (1 + 0.015 * dia_actual)
    df['porcentaje_avance'] = ((df['poder_actual'] / df['meta_dia'].replace(0, 1)) - 1) * 100
    df['meritos_ganados'] = df['meritos_final'] - df['meritos_inicial']
    df['poder_maximo'] = df[['poder_actual', 'poder_inicial']].max(axis=1)
    df['pct_meritos_vs_poder'] = (df['meritos_ganados'] / df['poder_maximo'].replace(0, 1)) * 100
    df['meritos_por_semana'] = df['meritos_ganados'] / (dia_actual / 7)
    df['eficiencia_meritos'] = df['meritos_ganados'] / (df['poder_maximo'] / 1_000_000).replace(0, 1)

    df['estado'] = '🟡 Activo'
    df.loc[df[col_nombre].isin(nuevos), 'estado'] = '🆕 Nuevo'
    df.loc[df[col_nombre].isin(bajas), 'estado'] = '❌ Baja'
    df.loc[(df['estado']!= '❌ Baja') & (df['porcentaje_avance'] >= 0), 'estado'] = '🟢 En Meta'
    df.loc[(df['estado']!= '❌ Baja') & (df['poder_actual'] >= 80_000_000) & (df['cambio_poder'] < 0), 'estado'] = '🔴 T5 Inactivo'
    df.loc[(df['estado']!= '❌ Baja') & (df['meritos_ganados'] < 300_000) & (df['nivel_actual'] >= 20), 'estado'] = '👻 Granja'
    df.loc[(df['estado']!= '❌ Baja') & (df['poder_actual'] >= 30_000_000) & (df['porcentaje_avance'] < -8), 'estado'] = '⚠️ Riesgo'

    df_final['rank_actual'] = df_final[col_poder].rank(ascending=False, method='min')
    df_inicial['rank_inicial'] = df_inicial[col_poder].rank(ascending=False, method='min')
    df = df.merge(df_final[[col_nombre, 'rank_actual']], on=col_nombre, how='left')
    df = df.merge(df_inicial[[col_nombre, 'rank_inicial']], on=col_nombre, how='left')
    df['cambio_rank'] = df['rank_inicial'].fillna(df['rank_actual']) - df['rank_actual']

    df_activos = df[df['estado']!= '❌ Baja'].copy()
    total = len(df_activos)
    cumplen = len(df_activos[df_activos['porcentaje_avance'] >= 0])
    pct_cumple = (cumplen / total) * 100 if total > 0 else 0
    poder_ganado = df_activos[df_activos['cambio_poder'] > 0]['cambio_poder'].sum()
    poder_perdido = abs(df_activos[df_activos['cambio_poder'] < 0]['cambio_poder'].sum())
    meritos_totales = df_activos['meritos_ganados'].sum()
    t5_activos = len(df_activos[df_activos['nivel_actual'] >= 25])

    # ===== EXCEL =====
    wb = Workbook()

    # HOJA 1: RESUMEN EJECUTIVO
    ws_resumen = wb.active
    ws_resumen.title = "RESUMEN EJECUTIVO"
    ws_resumen.merge_cells('A1:L2')
    ws_resumen['A1'] = f"📊 REPORTE KVK CALL OF DRAGONS | DÍA {dia_actual}"
    ws_resumen['A1'].font = Font(bold=True, size=24, color=COLORES['white'])
    ws_resumen['A1'].fill = PatternFill("solid", fgColor=COLORES['google_blue'])
    ws_resumen['A1'].alignment = Alignment(horizontal="center", vertical="center")
    ws_resumen.merge_cells('A3:L3')
    ws_resumen['A3'] = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Período: {nombres_archivos[0]} → {nombres_archivos[-1]}"
    ws_resumen['A3'].font = Font(size=10, italic=True, color=COLORES['dark'])
    ws_resumen['A3'].fill = PatternFill("solid", fgColor=COLORES['gray_100'])
    ws_resumen['A3'].alignment = Alignment(horizontal="center")

    crear_kpi_card(ws_resumen, 5, 1, "MIEMBROS", f"{total}", f"+{len(nuevos)} nuevos | -{len(bajas)} bajas", COLORES['google_blue'], "👥")
    crear_kpi_card(ws_resumen, 5, 4, "CUMPLIMIENTO", f"{pct_cumple:.1f}%", f"{cumplen} de {total} en meta", COLORES['google_green'] if pct_cumple >= 60 else COLORES['google_red'], "🎯")
    crear_kpi_card(ws_resumen, 5, 7, "PODER NETO", f"{(poder_ganado-poder_perdido)/1e6:+.1f}M", f"↑{poder_ganado/1e6:.1f}M | ↓{poder_perdido/1e6:.1f}M", COLORES['google_green'] if poder_ganado > poder_perdido else COLORES['google_red'], "⚡")
    crear_kpi_card(ws_resumen, 5, 10, "MÉRITOS/DÍA", f"{meritos_totales/dia_actual/1e3:.0f}K", f"Total: {meritos_totales/1e6:.1f}M", COLORES['google_yellow'], "🏆")
    crear_kpi_card(ws_resumen, 10, 1, "T5 ACTIVOS", f"{t5_activos}", f"{t5_activos/total*100:.0f}% del reino", COLORES['google_blue'], "🏰")
    crear_kpi_card(ws_resumen, 10, 4, "GRANJAS", f"{len(df_activos[df_activos['estado']=='👻 Granja'])}", "Nivel 20+ sin méritos", COLORES['google_red'], "👻")
    crear_kpi_card(ws_resumen, 10, 7, "T5 INACTIVOS", f"{len(df_activos[df_activos['estado']=='🔴 T5 Inactivo'])}", "Perdiendo poder", COLORES['google_red'], "💤")
    crear_kpi_card(ws_resumen, 10, 10, "EN RIESGO", f"{len(df_activos[df_activos['estado']=='⚠️ Riesgo'])}", "Candidatos a kick", COLORES['google_yellow'], "⚠️")

    # HOJA 2: DASHBOARD - ya lo tienes en versión anterior
    ws_dash = wb.create_sheet("DASHBOARD")
    #... resto igual que V6.2

    # HOJA 3: RANKING COMPLETO
    ws_rank = wb.create_sheet("RANKING COMPLETO")
    #... resto igual que V6.2

    # HOJA 4: ALERTAS - código completo que te pasé arriba
    #... [pegar aquí el bloque de ALERTAS completo]

    # HOJA 5: HISTÓRICO - código completo que te pasé arriba
    #... [pegar aquí el bloque de HISTÓRICO completo]

    for ws in wb.worksheets:
        for col in range(1, 15):
            ws.column_dimensions[get_column_letter(col)].width = 15

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

@bot.tree.command(name="kvk", description="Reporte KVK CoD")
@app_commands.describe(archivos="Sube tus Excel o ZIP")
async def kvk_slash(interaction: discord.Interaction, archivos: List[discord.Attachment]):
    await interaction.response.defer(thinking=True)
    try:
        archivos_bytes = [await a.read() for a in archivos]
        excel = await procesar_kvk_cod(archivos_bytes)
        await interaction.followup.send(file=discord.File(fp=excel, filename=f"Reporte_CoD_{datetime.now().day}.xlsx"))
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error: `{str(e)}`", ephemeral=True)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN:
    bot.run(TOKEN)
