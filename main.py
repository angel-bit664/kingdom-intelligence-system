import discord
from discord.ext import commands, tasks
import os
import requests
from deep_translator import GoogleTranslator
import pandas as pd
from io import BytesIO
from bs4 import BeautifulSoup
import cloudscraper
from datetime import datetime, timedelta
import re
import urllib.parse
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
ID_CANAL_ANUNCIOS = 1358237524249542751

mensajes_para_borrar = {}

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    print('Fuentes: callofstats.com | dragonstats.com | coddb.app | callofdragonsguides.com | YouTube')
    limpiar_canales.start()

@tasks.loop(hours=1)
async def limpiar_canales():
    try:
        for channel_id, mensajes in list(mensajes_para_borrar.items()):
            canal = bot.get_channel(channel_id)
            if not canal: continue
            hace_una_hora = datetime.utcnow() - timedelta(hours=1)
            mensajes_viejos = [msg for msg in mensajes if msg.created_at < hace_una_hora]
            if mensajes_viejos:
                try:
                    await canal.delete_messages(mensajes_viejos)
                    print(f'Limpiados {len(mensajes_viejos)} mensajes')
                except:
                    for msg in mensajes_viejos:
                        try: await msg.delete()
                        except: pass
                mensajes_para_borrar[channel_id] = [msg for msg in mensajes if msg not in mensajes_viejos]
    except Exception as e:
        print(f'Error en limpieza: {e}')

@limpiar_canales.before_loop
async def before_limpiar():
    await bot.wait_until_ready()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.lower().startswith("meta "):
        if message.channel.id not in mensajes_para_borrar:
            mensajes_para_borrar[message.channel.id] = []
        mensajes_para_borrar[message.channel.id].append(message)

        peticion = message.content[5:].strip()

        # ===== META LIMPIA =====
        if peticion.lower() == "limpia":
            try:
                msg = await message.channel.send("🧹 Limpiando spam de meta... 10 seg")
                mensajes_para_borrar[message.channel.id].append(msg)
                await asyncio.sleep(2)
                borrados = 0
                async for mensaje in message.channel.history(limit=100):
                    if mensaje.author == bot.user or mensaje.content.lower().startswith("meta "):
                        try:
                            await mensaje.delete()
                            borrados += 1
                            await asyncio.sleep(0.5)
                        except:
                            pass
                mensajes_para_borrar[message.channel.id] = []
                confirmacion = await message.channel.send(f"✅ Limpieza completa: {borrados} mensajes borrados")
                await asyncio.sleep(5)
                await confirmacion.delete()
                return
            except Exception as e:
                msg = await message.channel.send(f"❌ Error limpiando: {e}")
                mensajes_para_borrar[message.channel.id].append(msg)
                return

        # ===== META ALERTA =====
        if peticion.lower().startswith("alerta "):
            texto_alerta = peticion[7:].strip()
            if not texto_alerta:
                msg = await message.channel.send("Uso: `meta alerta <texto>`")
                mensajes_para_borrar[message.channel.id].append(msg)
                return
            try:
                traduccion = GoogleTranslator(source='auto', target='en').translate(texto_alerta)
                embed = discord.Embed(title="🚨 ALERTA OFICIAL TFT 🚨", color=0xFF0000)
                embed.add_field(name="🇲🇽 Español", value=texto_alerta, inline=False)
                embed.add_field(name="🇺🇸 English", value=traduccion, inline=False)
                embed.set_footer(text="Atentamente: R5/R4 TFT")
                canal_anuncios = bot.get_channel(ID_CANAL_ANUNCIOS)
                if canal_anuncios:
                    await canal_anuncios.send("@everyone", embed=embed)
                    msg = await message.channel.send("✅ Alerta enviada a anuncios")
                    mensajes_para_borrar[message.channel.id].append(msg)
                return
            except Exception as e:
                msg = await message.channel.send(f"❌ Error: {e}")
                mensajes_para_borrar[message.channel.id].append(msg)
                return

        # ===== META EVENTO =====
        if peticion.lower().startswith("evento "):
            texto_evento = peticion[7:].strip()
            if not texto_evento:
                msg = await message.channel.send("Uso: `meta evento <texto>`")
                mensajes_para_borrar[message.channel.id].append(msg)
                return
            try:
                traduccion = GoogleTranslator(source='auto', target='en').translate(texto_evento)
                embed = discord.Embed(title="📅 EVENTO OFICIAL TFT 📅", color=0x3498DB)
                embed.add_field(name="🇲🇽 Español", value=texto_evento, inline=False)
                embed.add_field(name="🇺🇸 English", value=traduccion, inline=False)
                embed.set_footer(text="Atentamente: R5/R4 TFT")
                canal_anuncios = bot.get_channel(ID_CANAL_ANUNCIOS)
                if canal_anuncios:
                    msg_evento = await canal_anuncios.send("@everyone", embed=embed)
                    await msg_evento.add_reaction("👍")
                    msg = await message.channel.send("✅ Evento enviado a anuncios")
                    mensajes_para_borrar[message.channel.id].append(msg)
                return
            except Exception as e:
                msg = await message.channel.send(f"❌ Error: {e}")
                mensajes_para_borrar[message.channel.id].append(msg)
                return

        # ===== META TRADUCIR =====
        if peticion.lower().startswith("traducir "):
            texto = peticion[9:].strip()
            if not texto:
                msg = await message.channel.send("Uso: `meta traducir <texto>`")
                mensajes_para_borrar[message.channel.id].append(msg)
                return
            try:
                deteccion = GoogleTranslator(source='auto', target='en').translate(texto)
                if deteccion.lower() == texto.lower():
                    traduccion = GoogleTranslator(source='en', target='es').translate(texto)
                    msg = await message.channel.send(f"🇺🇸→🇲🇽 **{traduccion}**")
                else:
                    msg = await message.channel.send(f"🇲🇽→🇺🇸 **{deteccion}**")
                mensajes_para_borrar[message.channel.id].append(msg)
                return
            except Exception as e:
                msg = await message.channel.send(f"❌ Error: {e}")
                mensajes_para_borrar[message.channel.id].append(msg)
                return

        # ===== META TALENTOS =====
        if peticion.lower().startswith("talentos "):
            heroe = peticion[9:].strip()
            if not heroe:
                msg = await message.channel.send("Uso: `meta talentos <héroe>` ej: `meta talentos emrys`")
                mensajes_para_borrar[message.channel.id].append(msg)
                return
            try:
                msg = await message.channel.send(f"⚔️ Buscando builds de **{heroe}** en callofdragonsguides.com + YouTube...")
                mensajes_para_borrar[message.channel.id].append(msg)
                url_guia = f"https://callofdragonsguides.com/heroes/{heroe.lower().replace(' ', '-')}"
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url_guia, timeout=30)
                embed = discord.Embed(title=f"⚔️ Builds de {heroe.title()}", color=0xE67E22)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    talentos_section = soup.find(['div', 'section'], class_=re.compile('talent|build', re.I))
                    if talentos_section:
                        texto_guia = talentos_section.get_text(strip=True)[:200]
                        embed.add_field(name="📖 Guía Principal", value=f"{texto_guia}...\n[Ver guía completa]({url_guia})", inline=False)
                url = "https://google.serper.dev/videos"
                payload = {"q": f"call of dragons {heroe} talents build 2026", "num": 2}
                headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
                response = requests.post(url, json=payload, headers=headers)
                data = response.json()
                videos = data.get("videos", [])[:2]
                if videos:
                    videos_texto = ""
                    for i, video in enumerate(videos, 1):
                        videos_texto += f"{i}. [{video['title'][:40]}]({video['link']})\n"
                    embed.add_field(name="🎥 Videos Top", value=videos_texto, inline=False)
                if response.status_code!= 200 and not videos:
                    await msg.edit(content=f"❌ No encontré builds para {heroe}")
                    return
                embed.set_footer(text="Fuentes: callofdragonsguides.com + YouTube")
                await msg.delete()
                msg_final = await message.channel.send(embed=embed)
                mensajes_para_borrar[message.channel.id].append(msg_final)
                return
            except Exception as e:
                await msg.edit(content=f"❌ Error: {e}")
                return

        # ===== META MASCOTA =====
        if peticion.lower().startswith("mascota "):
            mascota = peticion[8:].strip()
            if not mascota:
                msg = await message.channel.send("Uso: `meta mascota <nombre>` ej: `meta mascota sabre`")
                mensajes_para_borrar[message.channel.id].append(msg)
                return
            try:
                msg = await message.channel.send(f"🐾 Buscando guías de **{mascota}** en coddb.app + YouTube...")
                mensajes_para_borrar[message.channel.id].append(msg)
                url_coddb = f"https://coddb.app/pets/{mascota.lower().replace(' ', '-')}"
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url_coddb, timeout=30)
                embed = discord.Embed(title=f"🐾 Guía de {mascota.title()}", color=0x1ABC9C)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    stats_div = soup.find(['div', 'table'], class_=re.compile('stat|skill', re.I))
                    if stats_div:
                        texto_stats = stats_div.get_text(strip=True)[:200]
                        embed.add_field(name="📊 Stats & Skills", value=f"{texto_stats}...\n[Ver en coddb.app]({url_coddb})", inline=False)
                url = "https://google.serper.dev/videos"
                payload = {"q": f"call of dragons {mascota} pet guide 2026", "num": 2}
                headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
                response = requests.post(url, json=payload, headers=headers)
                data = response.json()
                videos = data.get("videos", [])[:2]
                if videos:
                    videos_texto = ""
                    for i, video in enumerate(videos, 1):
                        videos_texto += f"{i}. [{video['title'][:40]}]({video['link']})\n"
                    embed.add_field(name="🎥 Videos Top", value=videos_texto, inline=False)
                if response.status_code!= 200 and not videos:
                    await msg.edit(content=f"❌ No encontré guías para {mascota}")
                    return
                embed.set_footer(text="Fuentes: coddb.app + YouTube")
                await msg.delete()
                msg_final = await message.channel.send(embed=embed)
                mensajes_para_borrar[message.channel.id].append(msg_final)
                return
            except Exception as e:
                await msg.edit(content=f"❌ Error: {e}")
                return

        # ===== META CODSTATS =====
        comando_parts = peticion.lower().split()
        if len(comando_parts) >= 2 and comando_parts[0] in ["codstats", "codstat", "stats"]:
            try:
                reino = comando_parts[1].strip()
                if not reino.isdigit():
                    msg = await message.channel.send("Uso: `meta codstats 127`")
                    mensajes_para_borrar[message.channel.id].append(msg)
                    return
                msg = await message.channel.send(f"📊 Sacando stats del Reino {reino} desde callofstats.com ~20 seg")
                mensajes_para_borrar[message.channel.id].append(msg)
                url = f"https://callofstats.com/server/{reino}"
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url, timeout=30)
                if response.status_code!= 200:
                    url = f"https://dragonstats.com/server/{reino}"
                    response = scraper.get(url, timeout=30)
                    if response.status_code!= 200:
                        await msg.edit(content=f"❌ Error: Reino {reino} no encontrado")
                        return
                soup = BeautifulSoup(response.text, 'html.parser')
                tabla = soup.find('table')
                if not tabla:
                    await msg.edit(content=f"❌ No encontré tabla de stats para reino {reino}")
                    return
                df = pd.read_html(str(tabla))[0]
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name=f'Reino_{reino}', index=False)
                output.seek(0)
                archivo = discord.File(output, filename=f'COD_Reino_{reino}_Stats.xlsx')
                await msg.delete()
                msg_final = await message.channel.send(f"✅ **Stats Reino {reino}** | {len(df)} jugadores", file=archivo)
                mensajes_para_borrar[message.channel.id].append(msg_final)
                return
            except Exception as e:
                await msg.edit(content=f"❌ Error: {e}")
                return

        # ===== META CHECK JUGADOR - V5 =====
        if peticion.lower().startswith("check "):
            try:
                args = peticion[6:].strip().split()
                if not args:
                    embed = discord.Embed(title="
