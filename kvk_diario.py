import pandas as pd
import discord

async def procesar_kvk_por_dia(rutas_archivos):
    try:
        dataframes = []
        for ruta in rutas_archivos:
            if ruta.endswith('.xlsx'):
                df = pd.read_excel(ruta)
                dataframes.append(df)
        
        if len(dataframes) < 2:
            embed = discord.Embed(description="Error: Necesito mínimo 2 archivos Excel", color=0xFF0000)
            return embed, None
        
        total_filas = sum(len(df) for df in dataframes)
        texto = f"KVK procesado. Leí {len(dataframes)} archivos con {total_filas} filas totales."
        embed = discord.Embed(title="Reporte KVK", description=texto, color=0x00FF00)
        return embed, None
        
    except Exception as e:
        embed = discord.Embed(description=f"Error: {str(e)[:500]}", color=0xFF0000)
        return embed, None
