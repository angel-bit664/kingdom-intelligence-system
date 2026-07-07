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

        # ===== BLOQUE META ALERTA R5/R4 - CORREGIDO =====
        if peticion.lower().startswith("alerta "):
            try:
                # 1. NOMBRES EXACTOS DE ROLES R5 Y R4
                roles_permitidos = ["R5", "R4", "R4 Angel", "R4 SAURON"]

                tiene_permiso = any(role.name in roles_permitidos for role in message.author.roles)

                if not tiene_permiso:
                    await message.channel.send("⛔ Solo oficiales R5 y R4 pueden usar `meta alerta`.")
                    return

                texto_alerta = peticion[7:].strip()

                if texto_alerta == "":
                    await message.channel.send("Uso: `meta alerta Tu mensaje aquí`")
                    return

                # 2. EMBED TFT FAMILY
                embed = discord.Embed(color=0xF1C40F)
                embed.add_field(name="👑 Familia TFT / TFT Family 👑", value="📢 Necesitamos el apoyo de todos / We need everyone's support.", inline=False)
                embed.add_field(name="🎯 Misión / Mission:", value=f"🇲🇽 {texto_alerta}", inline=False)
                embed.add_field(name="🔥 Todos están invitados / Everyone is invited.", value="Si quieren pelear y defender / If you want to fight and defend, los esperamos / we are waiting for you.", inline=False)
                embed.add_field(name="¡Vamos TFT / Let's go TFT! ¡Aún queda guerra por delante / War is still ahead! 👑", value="⚔️", inline=False)
                embed.set_footer(text=f"Alerta enviada por: {message.author.display_name}")

                await message.channel.send("@everyone", embed=embed)
                return # Detiene el código para que no busque en Google

            except Exception as e:
                await message.channel.send(f"Error en meta alerta: {e}")
                return
        # ===== FIN BLOQUE META ALERTA =====

        # TU CÓDIGO ORIGINAL DE BÚSQUEDA - INTACTO
        await message.channel.send(f"Buscando: {peticion}")
        url = "https://google.serper.dev/search"
        headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
        payload = {"q": peticion, "gl": "mx", "hl": "es"}
        try:
            response = requests.post(url, headers=headers, json=payload)
            data = response.json()
            if "organic" in data and len(data["organic"]) > 0:
                respuesta = data["organic"][0]["snippet"]
                await message.channel.send(respuesta[:2000])
            else:
                await message.channel.send("No encontré nada bro")
        except Exception as e:
            await message.channel.send(f"Error: {e}")

    await bot.process_commands(message)

bot.run(os.getenv("DISCORD_TOKEN"))
