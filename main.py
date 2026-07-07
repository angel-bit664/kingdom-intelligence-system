import discord
from discord.ext import commands
import os
import requests
from deep_translator import GoogleTranslator

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.lower().startswith("meta "):
        peticion = message.content[5:].strip()

        # ===== INICIO: BLOQUE META ALERTA R5/R4 AGREGADO =====
        if peticion.lower().startswith("alerta "):
            # 1. NOMBRES EXACTOS DE ROLES R5 Y R4 - CAMBIA ESTOS
            roles_permitidos = ["R5", "R4", "R4 Angel", "R4 SAURON"]
            
            tiene_permiso = any(role.name in roles_permitidos for role in message.author.roles)
            
            if not tiene_permiso:
                await message.channel.send("⛔ Solo oficiales R5 y R4 pueden usar `meta alerta`.")
                return
            
            texto_alerta = peticion[7:].strip()
            
            if texto_alerta == "":
                await message.channel.send("Uso: `meta alerta Tu mensaje aquí`")
                return
            
            # 2. EMBED CON FORMATO TFT FAMILY COMO EN TU CAPTURA
            embed = discord.Embed(color=0xF1C40F) # Dorado
            
            embed.add_field(
                name="👑 Familia TFT / TFT Family 👑",
                value
