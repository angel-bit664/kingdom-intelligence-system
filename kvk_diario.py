import pandas as pd
import sqlite3
import discord
import io

async def procesar_kvk_por_dia(rutas_archivos):
    conn = sqlite3.connect('kvk_diario_historico.db')
    dia_actual = len(rutas_archivos)
    
    dfs = []
    for i, ruta in enumerate(rutas_archivos):
        df = pd.read_excel(ruta)
        df.columns = df.columns.str.strip()
        df['dia_kvk'] = i + 1
        columnas_ok = ['ID de personaje', 'Nombre de personaje', 'Poder actual', 'Total de méritos']
        for col in columnas_ok:
            if col not in df.columns:
                raise ValueError(f"Falta columna '{col}' en archivo día {i+1}")
        dfs.append(df)
        df.to_sql('stats_diarios', conn, if_exists='append', index=False)
    
    df_completo = pd.concat(dfs, ignore_index=True)
    df_hoy = dfs[-1].copy()
    
    primer_dia = df_completo.groupby('ID de personaje').first().reset_index()
    meritos_dia1 = primer_dia[['ID de personaje','Total de méritos']].rename(columns={'Total de méritos':'meritos_dia1'})
    df_hoy = df_hoy.merge(meritos_dia1, on='ID de personaje', how='left')
    df_hoy['meritos_dia1'].fillna(0, inplace=True)
    df_hoy['meritos_ganados_kvk'] = df_hoy['Total de méritos'] - df_hoy['meritos_dia1']
    
    poder_max = df_completo.groupby('ID de personaje')['Poder actual'].max().reset_index()
    poder_max = poder_max.rename(columns={'Poder actual':'poder_max_kvk'})
    df_hoy = df_hoy.merge(poder_max, on='ID de personaje')
    
    df_hoy['meta_meritos'] = df_hoy['poder_max_kvk'] * 0.12
    df_hoy['porcentaje_meta'] = (df_hoy['meritos_ganados_kvk'] / df_hoy['meta_meritos']) * 100
    df_hoy['cumple_meta'] = df_hoy['porcentaje_meta'] >= 100
    
    jugadores_30m = df_hoy[df_hoy['Poder actual'] > 30000000]
    total = len(jugadores_30m)
    cumplen = len(jugadores_30m[jugadores_30m['cumple_meta'] == True])
    porcentaje = (cumplen / total) * 100 if total > 0 else 100
    
    fantasmas = df_hoy[(df_hoy['Poder actual'] > 50000000) & (df_hoy['meritos_ganados_kvk'] < 500000)].sort_values('Poder actual', ascending=False)
    ballenas = df_hoy[(df_hoy['Poder actual'] > 160000000) & (df_hoy['porcentaje_meta'] < 50)].nsmallest(5, 'porcentaje_meta')
    candidatos_kick = df_hoy[(df_hoy['Poder actual'] > 50000000) & (df_hoy['cumple_meta'] == False)].nsmallest(5, 'porcentaje_meta')
    
    if porcentaje >= 95:
        barra = '🟩' * 20
        estado = '🟢 EXCELENTE'
        color = 0x57F287
    elif porcentaje >= 80:
        bloques_verdes = int(porcentaje / 5)
        barra = '🟩' * bloques_verdes + '⬜' * (20 - bloques_verdes)
        estado = '🟡 ACEPTABLE'
        color = 0xFEE75C
    else:
        bloques_verdes = int(porcentaje / 5)
        barra = '🟩' * bloques_verdes + '🟥' * (20 - bloques_verdes)
        estado = '🔴 CRÍTICO'
        color = 0xED4245
    
    embed = discord.Embed(title=f"⚔️ KVK DÍA {dia_actual} | REINO #127", description="**Progreso acumulado desde Día 1 del KVK**", color=color)
    embed.add_field(name="🎯 META INDIVIDUAL 12% ACUMULADA", value=f"📊 **CUMPLIMIENTO:** {cumplen}/{total} ({porcentaje:.1f}%) {estado}\n{barra}\n🟢 {porcentaje:.1f}% cumple | 🔴 {total-cumplen} bajo meta", inline=False)
    
    if not ballenas.empty:
        texto = ""
        for _, row in ballenas.iterrows():
            texto += f"`{row['Nombre de personaje'][:15]:<15}` {row['Poder actual']/1e6:.0f}M | {row['meritos_ganados_kvk']/1e6:.1f}M/{row['meta_meritos']/1e6:.1f}M **{row['porcentaje_meta']:.0f}%**🐋\n"
        embed.add_field(name=f"🐋 BALLENAS MUERTAS - {dia_actual} DÍAS KVK", value=texto, inline=False)
    
    if not fantasmas.empty:
        texto = ""
        for _, row in fantasmas.head(5).iterrows():
            texto += f"• `{row['Nombre de personaje'][:15]}` - {row['Poder actual']/1e6:.1f}M | **{row['meritos_ganados_kvk']/1e6:.2f}M ganados**\n"
        embed.add_field(name=f"👻 FANTASMAS - <500K MÉRITOS EN {dia_actual} DÍAS", value=f"{texto}⚠️ **Poder muerto:** {fantasmas['Poder actual'].sum()/1e9:.1f}B", inline=False)
    
    if not candidatos_kick.empty:
        kick_text = ""
        for _, row in candidatos_kick.iterrows():
            kick_text += f"• `{row['Nombre de personaje'][:15]}` {row['Poder actual']/1e6:.0f}M | **{row['porcentaje_meta']:.0f}%**\n"
        embed.add_field(name="🚨 TOP 5 CANDIDATOS KICK +50M", value=kick_text, inline=False)
    
    embed.set_footer(text=f"⏰ Día {dia_actual} KVK | codigo generado por angel")
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        columnas_salida = ['ID de personaje','Nombre de personaje','Poder actual','poder_max_kvk','Total de méritos','meritos_ganados_kvk','meta_meritos','porcentaje_meta','cumple_meta']
        df_hoy[columnas_salida].to_excel(writer, sheet_name='Resumen KVK', index=False)
        if not ballenas.empty: ballenas.to_excel(writer, sheet_name='Ballenas Muertas', index=False)
        if not fantasmas.empty: fantasmas.to_excel(writer, sheet_name='Fantasmas KVK', index=False)
        if not candidatos_kick.empty: candidatos_kick.to_excel(writer, sheet_name='Candidatos Kick', index=False)
    
    output.seek(0)
    archivo = discord.File(output, filename=f"KVK_Dia{dia_actual}_Acumulado.xlsx")
    conn.close()
    return embed, archivo
