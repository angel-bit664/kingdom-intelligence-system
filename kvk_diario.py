import pandas as pd
import discord
import os

async def procesar_kvk_por_dia(rutas_archivos):
    try:
        dataframes = []
        
        for ruta in rutas_archivos:
            if ruta.endswith('.xlsx'):
                df = pd.read_excel(ruta)
                dataframes.append(df)
            elif ruta.endswith('.zip'):
                embed = discord.Embed(
                    description="❌ **ZIP aún no soportado.** Sube los 2 Excel por separado.",
                    color=0xFF0000
                )
                # Borrar archivos antes de salir
                for r in rutas_archivos:
                    if os.path.exists(r): os.remove(r)
                return embed, None
        
        if len(dataframes) < 2:
            embed = discord.Embed(
                description="❌ **Error:** Necesito mínimo 2 archivos Excel para comparar el KVK",
                color=0xFF0000
            )
            for r in rutas_archivos:
                if os.path.exists(r): os.remove(r)
            return embed, None
        
        # === AQUÍ VA TU LÓGICA REAL DE KVK ===
        # Ejemplo básico:
        total_filas = sum(len(df) for df in dataframes)
        
        embed = discord.Embed(
            title="📊 Reporte KVK Diario",
            description="Procesamiento completado",
            color=0x00FF00
        )
        embed.add_field(name="Archivos procesados", value=f"{len(dataframes)}", inline=True)
        embed.add_field(name="Total de registros", value=f"{total_filas:,}", inline=True)
        embed.set_footer(text="KVK Diario v1.0")
        
        # Limpia los Excel temporales
        for ruta in rutas_archivos:
            if os.path.exists(ruta):
                os.remove(ruta)
        
        # Regresamos el embed y None porque no generamos archivo nuevo
        return embed, None
        
    except Exception as e:
        # Si algo truena, borramos archivos y regresamos el error
        for ruta in rutas_archivos:
            if os.path.exists(ruta):
                os.remove(ruta)
                
        embed = discord.Embed(
            description=f"❌ **Error al procesar:** {str(e)[:500]}",
            color=0xFF0000
        )
        return embed, None
