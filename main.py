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

        # ===== META TALENTOS - CALLOFDRAGONSGUIDES.COM + YOUTUBE =====
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

        # ===== META MASCOTA - CODDB.APP + YOUTUBE =====
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

        # ===== META CODSTATS - CALLOFSTATS.COM =====
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

        # ===== META CHECK JUGADOR - V3 CON ID =====
        if peticion.lower().startswith("check "):
            try:
                args = peticion[6:].strip().split()
                if not args:
                    embed = discord.Embed(title="🔍 Meta Check - Opciones", color=0x3498DB)
                    embed.add_field(name="Por nombre", value="`meta check Pishiux`", inline=False)
                    embed.add_field(name="Por ID", value="`meta check id 1234567`", inline=False)
                    embed.add_field(name="Top reino", value="`meta check reino 127`", inline=False)
                    embed.set_footer(text="ID lo sacas de dragonstats.com/player/1234567")
                    msg = await message.channel.send(embed=embed)
                    mensajes_para_borrar[message.channel.id].append(msg)
                    return

                scraper = cloudscraper.create_scraper()
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

                # OPCIÓN 1: BUSCAR POR ID
                if args[0].lower() == "id":
                    if len(args) < 2 or not args[1].isdigit():
                        msg = await message.channel.send("Uso: `meta check id 1234567`\nSaca el ID de dragonstats.com/player/ID")
                        mensajes_para_borrar[message.channel.id].append(msg)
                        return

                    player_id = args[1]
                    msg = await message.channel.send(f"🔍 Buscando jugador ID **{player_id}**...")
                    mensajes_para_borrar[message.channel.id].append(msg)

                    link_perfil = f"https://dragonstats.com/player/{player_id}"

                # OPCIÓN 2: BUSCAR TOP REINO
                elif args[0].lower() == "reino":
                    if len(args) < 2 or not args[1].isdigit():
                        msg = await message.channel.send("Uso: `meta check reino 127`")
                        mensajes_para_borrar[message.channel.id].append(msg)
                        return

                    reino = args[1]
                    msg = await message.channel.send(f"📊 Sacando top del Reino {reino}...")
                    mensajes_para_borrar[message.channel.id].append(msg)

                    url = f"https://dragonstats.com/server/{reino}"
                    response = scraper.get(url, headers=headers, timeout=30)

                    if response.status_code!= 200:
                        await msg.edit(content=f"❌ Error: Reino {reino} no encontrado")
                        return

                    soup = BeautifulSoup(response.text, 'html.parser')
                    tabla = soup.find('table')
                    if not tabla:
                        await msg.edit(content=f"❌ No encontré tabla para reino {reino}")
                        return

                    df = pd.read_html(str(tabla))[0].head(50)
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, sheet_name=f'Reino_{reino}', index=False)
                    output.seek(0)

                    archivo = discord.File(output, filename=f'COD_Reino_{reino}_Top50.xlsx')
                    await msg.delete()
                    msg_final = await message.channel.send(f"✅ **Top 50 Reino {reino}** | Fuente: dragonstats.com", file=archivo)
                    mensajes_para_borrar[message.channel.id].append(msg_final)
                    return

                # OPCIÓN 3: BUSCAR POR NOMBRE
                else:
                    nombre_jugador = ' '.join(args)
                    msg = await message.channel.send(f"🔍 Buscando a **{nombre_jugador}**...")
                    mensajes_para_borrar[message.channel.id].append(msg)

                    nombre_encoded = urllib.parse.quote(nombre_jugador)
                    url_busqueda = f"https://dragonstats.com/search?query={nombre_encoded}"
                    response = scraper.get(url_busqueda, headers=headers, timeout=30)

                    if response.status_code!= 200:
                        await msg.edit(content=f"❌ Error {response.status_code}: dragonstats.com no responde")
                        return

                    soup = BeautifulSoup(response.text, 'html.parser')
                    link_perfil = None
                    for a in soup.find_all('a', href=True):
                        if '/player/' in a['href']:
                            link_perfil = "https://dragonstats.com" + a['href']
                            break

                    if not link_perfil:
                        await msg.edit(content=f"❌ Jugador `{nombre_jugador}` no encontrado.\nTip: Usa `meta check id 1234567` con el ID de dragonstats.com")
                        return

                # SCRAPEA EL PERFIL DEL JUGADOR
                response = scraper.get(link_perfil, headers=headers, timeout=30)
                if response.status_code!= 200:
                    await msg.edit(content=f"❌ Error {response.status_code}: No pude cargar el perfil")
                    return

                soup = BeautifulSoup(response.text, 'html.parser')

                def get_stat(nombre):
                    elemento = soup.find(text=re.compile(nombre, re.I))
                    if elemento:
                        next_el = elemento.find_next(['td', 'div', 'span'])
                        return next_el.get_text(strip=True) if next_el else "N/A"
                    return "N/A"

                poder = get_stat("Power")
                kills = get_stat("Kill")
                muertes = get_stat("Dead")
                reino = get_stat("Kingdom")
                alianza = get_stat("Alliance")
                nombre_real = get_stat("Name") or "N/A"
                player_id_extraido = link_perfil.split('/')[-1]

                embed = discord.Embed(title=f"⚔️ {nombre_real}", color=0x3498DB, url=link_perfil)
                embed.add_field(name="🆔 ID", value=player_id_extraido, inline=True)
                embed.add_field(name="🏰 Reino", value=reino, inline=True)
                embed.add_field(name="🛡️ Alianza", value=alianza, inline=True)
                embed.add_field(name="💪 Poder", value=poder, inline=True)
                embed.add_field(name="⚔️ Kills", value=kills, inline=True)
                embed.add_field(name="💀 Muertes", value=muertes, inline=True)
                try:
                    kd = f"{float(kills.replace(',',''))/float(muertes.replace(',','')):.2f}" if kills!="N/A" and muertes!="N/A" and muertes!="0" else "N/A"
                    embed.add_field(name="K/D", value=kd, inline=True)
                except: pass
                embed.set_footer(text="Fuente: dragonstats.com")

                await msg.delete()
                msg_final = await message.channel.send(embed=embed)
                mensajes_para_borrar[message.channel.id].append(msg_final)
                return

            except Exception as e:
                await msg.edit(content=f"❌ Error: {e}")
                return

        # ===== META CALC - CODDB.APP =====
        if peticion.lower().startswith("calc "):
            try:
                args = peticion[5:].strip().split()
                if len(args) < 2:
                    embed = discord.Embed(title="🧮 Meta Calc - coddb.app", color=0x9B59B6)
                    embed.description = "**Usos:**\n`meta calc tropas 100k t5` - Tiempo entrenamiento\n`meta calc speedup 30d 12h` - Convierte a speedups"
                    embed.set_footer(text="Datos de coddb.app")
                    msg = await message.channel.send(embed=embed)
                    mensajes_para_borrar[message.channel.id].append(msg)
                    return

                tipo = args[0].lower()

                if tipo == "tropas":
                    cantidad = args[1].replace('k','000').replace('m','000000')
                    tier = args[2].lower() if len(args) > 2 else "t5"
                    tiempos_base = {"t1": 30, "t2": 45, "t3": 60, "t4": 120, "t5": 180}
                    tiempo_seg = int(cantidad) * tiempos_base.get(tier, 180)
                    dias = tiempo_seg // 86400
                    horas = (tiempo_seg % 86400) // 3600
                    mins = (tiempo_seg % 3600) // 60

                    embed = discord.Embed(title="🏹 Calculadora de Entrenamiento", color=0x2ECC71)
                    embed.add_field(name="Tropas", value=f"{args[1]} {tier.upper()}", inline=True)
                    embed.add_field(name="Tiempo Base", value=f"{dias}d {horas}h {mins}m", inline=True)
                    embed.add_field(name="Con 25% boost", value=f"{int(dias*0.75)}d {int(horas*0.75)}h", inline=True)
                    embed.set_footer(text="Fuente: coddb.app | Sin buffs de alianza")
                    msg = await message.channel.send(embed=embed)
                    mensajes_para_borrar[message.channel.id].append(msg)
                    return

                elif tipo == "speedup":
                    tiempo = ' '.join(args[1:])
                    dias = int(re.findall(r'(\d+)d', tiempo)[0]) if 'd' in tiempo else 0
                    horas = int(re.findall(r'(\d+)h', tiempo)[0]) if 'h' in tiempo else 0
                    total_mins = (dias * 1440) + (horas * 60)

                    embed = discord.Embed(title="⚡ Calculadora de Speedups", color=0xF39C12)
                    embed.add_field(name="Tiempo", value=f"{dias}d {horas}h", inline=True)
                    embed.add_field(name="Speedups 60min", value=f"{total_mins // 60}", inline=True)
                    embed.add_field(name="Speedups 8h", value=f"{total_mins // 480}", inline=True)
                    embed.add_field(name="Speedups 24h", value=f"{total_mins // 1440}", inline=True)
                    embed.set_footer(text="Fuente: coddb.app")
                    msg = await message.channel.send(embed=embed)
                    mensajes_para_borrar[message.channel.id].append(msg)
                    return

                else:
                    msg = await message.channel.send("Tipos: `tropas`, `speedup`. Ej: `meta calc tropas 50k t5`")
                    mensajes_para_borrar[message.channel.id].append(msg)
                    return

            except Exception as e:
                msg = await message.channel.send(f"❌ Error: {e}\nUso: `meta calc tropas 100k t5`")
                mensajes_para_borrar[message.channel.id].append(msg)
                return

        # ===== META BÚSQUEDA GOOGLE =====
        if len(peticion) > 0 and not peticion.lower().startswith(("alerta ", "evento ", "traducir ", "talentos ", "mascota ", "check ", "calc ")):
            try:
                msg = await message.channel.send(f"🔍 Buscando: **{peticion}**...")
                mensajes_para_borrar[message.channel.id].append(msg)
                url = "https://google.serper.dev/search"
                payload = {"q": f"call of dragons {peticion}", "num": 3}
                headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
                response = requests.post(url, json=payload, headers=headers)
                data = response.json()
                resultados = data.get("organic", [])[:3]
                if not resultados:
                    await msg.edit(content="❌ No encontré resultados")
                    return
                embed = discord.Embed(title=f"🔍 Resultados: {peticion}", color=0x00D9FF)
                for i, resultado in enumerate(resultados, 1):
                    embed.add_field(name=f"{i}. {resultado['title'][:50]}", value=f"{resultado['snippet'][:100]}...\n[Link]({resultado['link']})", inline=False)
                await msg.delete()
                msg_final = await message.channel.send(embed=embed)
                mensajes_para_borrar[message.channel.id].append(msg_final)
                return
            except Exception as e:
                await msg.edit(content=f"❌ Error: {e}")
                return

        # ===== PING =====
        if peticion.lower() == "ping":
            latencia = round(bot.latency * 1000)
            msg = await message.channel.send(f"🏓 Pong! `{latencia}ms`\n✅ callofstats.com\n✅ dragonstats.com\n✅ coddb.app\n✅ callofdragonsguides.com")
            mensajes_para_borrar[message.channel.id].append(msg)
            return

        # ===== AYUDA =====
        if peticion.lower() == "ayuda":
            embed = discord.Embed(title="🤖 Comandos Meta TFT - Call of Dragons", color=0x3498DB)
            embed.add_field(name="📢 `meta alerta <texto>`", value="Alerta oficial bilingüe", inline=False)
            embed.add_field(name="📅 `meta evento <texto>`", value="Evento oficial bilingüe", inline=False)
            embed.add_field(name="🌐 `meta traducir <texto>`", value="Traduce ES ↔ EN", inline=False)
            embed.add_field(name="⚔️ `meta talentos <héroe>`", value="Top 3 builds callofdragonsguides.com + YT", inline=False)
            embed.add_field(name="🐾 `meta mascota <nombre>`", value="Top 3 guías coddb.app + YT", inline=False)
            embed.add_field(name="📊 `meta codstats <reino>`", value="Stats de reino desde callofstats.com", inline=False)
            embed.add_field(name="🔍 `meta check <nombre/id/reino>`", value="Stats jugador por nombre, ID o top reino", inline=False)
            embed.add_field(name="🧮 `meta calc tropas <cant> <tier>`", value="Calcula tiempo entrenamiento T1-T5", inline=False)
            embed.add_field(name="⚡ `meta calc speedup <tiempo>`", value="Convierte días/horas a speedups", inline=False)
            embed.add_field(name="🔍 `meta <búsqueda>`", value="Busca en Google", inline=False)
            embed.set_footer(text="Fuentes: callofstats.com | dragonstats.com | coddb.app | callofdragonsguides.com | YouTube")
            msg = await message.channel.send(embed=embed)
            mensajes_para_borrar[message.channel.id].append(msg)
            return

    await bot.process_commands(message)

bot.run(os.getenv("DISCORD_TOKEN"))
