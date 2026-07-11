import pandas as pd
import discord
import os

async def procesar_kvk_por_dia(rutas_archivos):
    try:
        dataframes = []
        
        # 1. Leer archivos
        for ruta in rutas_archivos:
            if ruta.endswith('.xlsx'):
                df = pd.read_excel(ruta)
                dataframes.append(df)
            elif ruta.endswith('.zip'):
                # Limpia antes de salir
                for r in rutas_archivos:
                    if os.path.exists(r): os.remove(r)
                embed = discord.Embed(
                    description="❌ **ZIP aún no soportado.** Sube los 2 Excel por separado.",
                    color=0xFF0000
                )
                return embed, None
        
        # 2. Validar que haya mínimo 2 Excel
        if len(dataframes) < 2:
            for r in rutas_archivos:
                if os.path.exists(r): os.remove(r)
            embed = discord.Embed(
                description="❌ **Error:** Necesito mínimo 2 archivos Excel para comparar el KVK",
                color=0xFF0000
            )
            return embed, None
        
        # === 3. AQUÍ VA TU LÓGICA REAL DE KVK ===
        # Este es solo un ejemplo. Cambia esto por tu código real.
        df1 = dataframes[0]
        df2 = dataframes[1]
        
        total_registros_1 = len(df1)
        total_registros_2 = len(df2)
        diferencia = total_registros_2 - total_registros_1
        
        embed = discord.Embed(
            title="📊 Reporte KVK Diario",
            description="Comparación completada",
            color=0x00FF00
        )
        embed.add_field(name="Registros día 1", value=f"{total_registros_1:,}", inline=True)
        embed.add_field(name="Registros día 2", value=f"{total_registros_2:,}", inline=True)
        embed.add_field(name="Diferencia", value=f"{diferencia:+,}", inline=True)
        embed.set_footer(text="Usa 'meta ayuda' para ver todos los comandos")
        
        # 4. Borrar archivos temporales
        for ruta in rutas_archivos:
            if os.path.exists(ruta):
                os.remove(ruta)
        
        # 5. Siempre regresa 2 valores: embed y archivo_excel
        # Como no generamos Excel nuevo, regresamos None
        return embed, None
        
    except Exception as e:
        # Si cualquier cosa truena, no matamos el bot
        for ruta in rutas_archivos:
            if os.path.exists(ruta):
                os.remove(ruta)
                
        embed = discord.Embed(
            description=f"❌ **Error al procesar KVK:** {str(e)[:500]}",
            color=0xFF0000
        )
        return embed, None
