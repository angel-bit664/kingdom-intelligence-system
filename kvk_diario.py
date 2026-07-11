import discord
from discord.ext import commands
import io
import os
import zipfile
import pandas as pd

def setup(bot):
    @bot.command(name="kvkdiario")
    async def kvkdiario(ctx):
        """Procesa archivos Excel de KVK. Uso: meta kvkdiario + adjuntar 2+ archivos Excel o ZIP"""
        archivos = ctx.message.attachments

        if not archivos:
            await ctx.send("Error: Sube minimo 2 archivos Excel o 1 ZIP con varios dias de KVK")
            return

        await ctx.send(f"Recibi {len(archivos)} archivo(s). Comando cargado correctamente.")
        # TODO: Aqui va la logica del Excel cuando confirmes que prende

    print("KVK Diario cargado sin errores")
