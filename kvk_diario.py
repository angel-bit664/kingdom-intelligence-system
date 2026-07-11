import discord
from discord.ext import commands

async def procesar_kvk_por_dia(rutas_archivos):
    # TODO: Aqui va tu logica del Excel
    return None

def setup(bot):
    @bot.command(name="kvkdiario")
    async def kvkdiario(ctx):
        archivos = ctx.message.attachments
        if not archivos:
            await ctx.send("Error: Sube minimo 2 archivos Excel o 1 ZIP")
            return
        await ctx.send(f"Comando OK. Recibi {len(archivos)} archivo(s). Procesando...")

    print("KVK Diario cargado sin errores")
