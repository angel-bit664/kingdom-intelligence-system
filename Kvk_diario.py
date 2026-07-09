import discord
from discord.ext import commands
import asyncio
import os
from kvk_diario import procesar_kvk_por_dia

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot KVK Diario conectado como {bot.user}')

@bot.command(name='kvkdiario')
async def kvk_diario_cmd(ctx):
    """Comando independiente para KVK por días"""
    if len(ctx.message.attachments) < 2:
        await ctx.send("❌ **Sube mínimo 2 Excel**\n`01_dia1.xlsx`, `02_dia2.xlsx`...")
        return

    if len(ctx.message.attachments) > 10:
        await ctx.send("❌ Máximo 10 archivos bro")
        return

    msg = await ctx.send(f"⏳ Procesando {len(ctx.message.attachments)} días...")

    try:
        attachments = sorted(ctx.message.attachments, key=lambda x: x.filename)
        rutas = []
        for i, adj in enumerate(attachments):
            ruta = f'temp_kvk_dia{i+1}.xlsx'
            await adj.save(ruta)
            rutas.append(ruta)

        embed, archivo = await procesar_kvk_por_dia(rutas)
        await msg.edit(content=None, embed=embed, file=archivo)
        
        for ruta in rutas:
            os.remove(ruta)

    except Exception as e:
        await msg.edit(content=f"❌ **Error:** {e}")

# Usa el mismo token que tu bot actual
bot.run(os.getenv('DISCORD_TOKEN'))
