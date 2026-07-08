import discord
from discord.ext import commands
import os
import requests
from deep_translator import GoogleTranslator
import pandas as pd
from io import BytesIO
from bs4 import BeautifulSoup
import cloudscraper

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
ID_CANAL_ANUNCIOS = 1358237524249542751 # Tu canal ❄️・anuncios🔹announcements┋📣

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    print('Comandos: meta ping, meta ayuda, meta alerta, meta evento, meta traducir, meta codstats, meta build, meta pet, meta <búsqueda>')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.lower().startswith("meta "):
        peticion = message.content[5:].strip()

        # ===== COMANDO: META PING =====
        if peticion.lower() == "ping":
            latencia = round(bot.latency * 1000)
            await message.channel.send(f"🏓 Pong! Latencia: `{latencia}ms` | Bot activo ✅")
            return

        # ===== COMANDO: META AYUDA =====
        if peticion.lower() == "ayuda":
            embed = discord.Embed(title="🤖 Comandos Meta TFT - Call of Dragons", color=0x3498DB)
            embed.add_field(name="📢 `meta alerta <texto>`", value="Alerta oficial bilingüe de guerra al canal de anuncios", inline=False)
            embed.add_field(name="📅 `meta evento <texto>`", value="Publica evento oficial bilingüe con reacción 👍", inline=False)
            embed.add_field(name="⚔️ `meta build <héroe>`", value="Top 3 builds de héroes desde YouTube + Webs TFT", inline=False)
            embed.add_field(name="🐾 `meta pet <mascota>`", value="Top 3 guías de mascotas con stats + skills", inline=False)
            embed.add_field(name="📊 `meta codstats <reino>`", value="Excel con stats del reino desde dragonstat", inline=False)
            embed.add_field(name="🔍 `meta <búsqueda>`", value="Busca en Google cualquier cosa", inline=False)
            embed.add_field(name="🌐 `meta traducir <texto>`", value="Traduce ES ↔ EN automático", inline=False)
            embed.add_field(name="🏓 `meta ping`", value="Checa latencia del bot", inline=False)
            embed.set_footer(text="Solo oficiales R4/R5 en este canal")
            await message.channel.send(embed=embed)
            return

        # ===== COMANDO: META ALERTA BILINGÜE A CANAL FIJO =====
        if peticion.lower().startswith("alerta "):
            try:
                texto_alerta_es = peticion[7:].strip()
                if not texto_alerta_es:
                    await message.channel.send("Uso: `meta alerta Nos atacan en el paso 4`")
                    return

                canal_anuncios = bot.get_channel(ID_CANAL_ANUNCIOS)
                if not canal_anuncios:
                    await message.channel.send("❌ No encontré el canal de anuncios. Revisa el ID_CANAL_ANUNCIOS")
                    return

                try:
                    texto_alerta_en = GoogleTranslator(source='es', target='en').translate(texto_alerta_es)
                except:
                    texto_alerta_en = "Translation failed. Check original message above."

                embed = discord.Embed(color=0xF1C40F)
                embed.add_field(name="👑 Familia TFT / TFT Family 👑", value="📢 Necesitamos el apoyo de todos / We need everyone's support.", inline=False)
                embed.add_field(
                    name="### 🎯 MISIÓN / MISSION ###",
                    value=f"> 🇲🇽 **ES:** **{texto_alerta_es.upper()}**\n> 🇺🇸 **EN:** **{texto_alerta_en.upper()}**",
                    inline=False
                )
                embed.add_field(name="🔥 Todos están invitados / Everyone is invited.", value="Si quieren pelear y defender / If you want to fight and defend, los esperamos / we are waiting for you.", inline=False)
                embed.add_field(name="¡Vamos TFT / Let's go TFT! ¡Aún queda guerra por delante / War is still ahead! 👑", value="⚔️", inline=False)
                embed.set_footer(text=f"Alerta enviada por: {message.author.display_name}")

                await canal_anuncios.send("@everyone", embed=embed)
                await message.channel.send(f"✅ Alerta enviada a {canal_anuncios.mention}")
                return
            except Exception as e:
                await message.channel.send(f"Error al procesar la alerta: {e}")
                return

        # ===== COMANDO: META EVENTO BILINGÜE =====
        if peticion.lower().startswith("evento "):
            try:
                texto_evento_es = peticion[7:].strip()
                if not texto_evento_es:
                    await message.channel.send("Uso: `meta evento Grandes Alturas mañana 8pm server`")
                    return

                canal_anuncios = bot.get_channel(ID_CANAL_ANUNCIOS)
                if not canal_anuncios:
                    await message.channel.send("❌ No encontré el canal de anuncios. Revisa el ID_CANAL_ANUNCIOS")
                    return

                try:
                    texto_evento_en = GoogleTranslator(source='es', target='en').translate(texto_evento_es)
                except:
                    texto_evento_en = "Translation failed. Check original message above."

                embed = discord.Embed(color=0x5865F2)
                embed.add_field(name="🎉 Familia TFT / TFT Family 🎉", value="📅 **EVENTO OFICIAL / OFFICIAL EVENT**", inline=False)
                embed.add_field(
                    name="### 📌 EVENTO / EVENT ###",
                    value=f"> 🇲🇽 **ES:** **{texto_evento_es.upper()}**\n> 🇺🇸 **EN:** **{texto_evento_en.upper()}**",
                    inline=False
                )
                embed.add_field(name="✅ Confirmen asistencia / Confirm attendance", value="Reacciona con 👍 si vas a participar / React 👍 if you're joining", inline=False)
                embed.add_field(name="¡Preparados TFT / Ready TFT! 🏆", value="Vamos por la victoria / Let's go for victory", inline=False)
                embed.set_footer(text=f"Evento publicado por: {message.author.display_name}")

                mensaje_evento = await canal_anuncios.send("@everyone", embed=embed)
                await mensaje_evento.add_reaction("👍")
                await message.channel.send(f"✅ Evento publicado en {canal_anuncios.mention}")
                return
            except Exception as e:
                await message.channel.send(f"Error al publicar evento: {e}")
                return

        # ===== COMANDO: META TRADUCIR =====
        if peticion.lower().startswith("traducir "):
            texto = peticion[9:].strip()
            if not texto:
                await message.channel.send("Uso: `meta traducir Hola mundo`")
                return

            try:
                idioma_detectado = GoogleTranslator().detect(texto)
                if idioma_detectado == 'es':
                    traducido = GoogleTranslator(source='es', target='en').translate(texto)
                    await message.channel.send(f"🇲🇽→🇺🇸 **{traducido}**")
                else:
                    traducido = GoogleTranslator(source='auto', target='es').translate(texto)
                    await message.channel.send(f"🇺🇸→🇲🇽 **{traducido}**")
                return
            except Exception as e:
                await message.channel.send(f"Error al traducir: {e}")
                return

        # ===== COMANDO: META CODSTATS =====
        comando_parts = peticion.lower().split()
        if len(comando_parts) >= 2 and comando_parts[0] in ["codstats", "codstat", "stats"]:
            try:
                reino = comando_parts[1].strip()
                if not reino.isdigit():
                    await message.channel.send("Uso: `meta codstats 127`")
                    return

                msg = await message.channel.send(f"📊 Sacando stats del Reino {reino} desde dragonstat.com ~20 seg")

                url = f"https://dragonstat.com/server/{reino}"
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url, timeout=30)

                if response.status_code!= 200:
                    await msg.edit(content=f"❌ Error {response.status_code}: No pude acceder a dragonstat")
                    return

                soup = BeautifulSoup(response.text, 'html.parser')
                tabla = soup.find('table')

                if not tabla:
                    await msg.edit(content=f"❌ No encontré la tabla. El reino {reino} no existe en dragonstat")
                    return

                df = pd.read_html(str(tabla))[0]
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name=f'Reino_{reino}', index=False)
                output.seek(0)

                archivo = discord.File(output, filename=f'COD_Reino_{reino}_Stats.xlsx')
                await msg.delete()
                await message.channel.send(f"✅ **Stats del Reino {reino}** | {len(df)} jugadores", file=archivo)
                return
            except Exception as e:
                await message.channel.send(f"❌ Error: {e}")
                return

        # ===== COMANDO NUEVO: META BUILD - HÉROES =====
        if peticion.lower().startswith("build "):
            try:
                heroe = peticion[6:].strip().lower()
                if not heroe:
                    await message.channel.send("Usage: `meta build goresh` or `meta build emrys pvp`")
                    return

                msg = await message.channel.send(f"🔍 Comparing builds for **{heroe.title()}** from TFT channels... 10s")

                partes = heroe.split()
                heroe_nombre = partes[0]
                tipo_build = partes[1] if len(partes) > 1 else "pvp"
                query_base = f"{heroe_nombre} {tipo_build} build call of dragons 2026"

                sitios = [
                    "site:youtube.com/@BOSSNASTi",
                    "site:youtube.com/@thefluffywafles",
                    "site:youtube.com/@YTGunzCOD",
                    "site:youtube.com",
                    "site:reddit.com/r/callofdragons",
                    "site:codgaming.gg"
                ]

                todos_los_resultados = []
                for sitio in sitios:
                    try:
                        url = "https://google.serper.dev/search"
                        headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
                        payload = {"q": f"{query_base} {sitio}", "num": 2, "gl": "us", "hl": "en"}
                        response = requests.post(url, headers=headers, json=payload, timeout=10)
                        data = response.json()
                        if "organic" in data:
                            todos_los_resultados.extend(data["organic"][:2])
                    except:
                        pass

                if not todos_los_resultados:
                    await msg.edit(content=f"❌ No builds found for {heroe_nombre}")
                    return

                mejores_3 = []
                links_usados = []
                for resultado in todos_los_resultados:
                    if resultado["link"] not in links_usados and len(mejores_3) < 3:
                        mejores_3.append(resultado)
                        links_usados.append(resultado["link"])

                embed = discord.Embed(
                    title=f"⚔️ TOP 3 Builds {heroe_nombre.title()} - {tipo_build.upper()}",
                    color=0xF39C12,
                    description=f"Analyzed {len(todos_los_resultados)} sources | **TFT Curated Channels**"
                )

                emojis = ["🥇", "🥈", "🥉"]
                for i, build in enumerate(mejores_3):
                    if "@BOSSNASTi" in build["link"]: fuente = "BOSS NASTi"
                    elif "@thefluffywafles" in build["link"]: fuente = "Fluffy Waffles"
                    elif "@YTGunzCOD" in build["link"]: fuente = "GunzCOD"
                    elif "youtube" in build["link"]: fuente = "YouTube CoD"
                    elif "reddit" in build["link"]: fuente = "Reddit"
                    else: fuente = "CodGaming"

                    if i == 0 and "youtube.com" in build["link"]:
                        try:
                            video_id = build["link"].split("v=")[-1].split("&")[0]
                            embed.set_thumbnail(url=f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg")
                        except:
                            pass

                    embed.add_field(
                        name=f"{emojis[i]} {fuente}",
                        value=f"**{build['title'][:55]}...**\n{build['snippet'][:130]}...\n[View Guide]({build['link']})",
                        inline=False
                    )

                embed.add_field(
                    name="📊 How to choose:",
                    value="🥇 **Option 1**: Latest meta/current patch\n🥈 **Option 2**: Best for F2P/open field\n🥉 **Option 3**: Counter builds/specific use",
                    inline=False
                )
                embed.set_footer(text=f"TFT | React 🥇🥈🥉 to vote | September 2026 Meta")
                await msg.delete()
                mensaje = await message.channel.send(embed=embed)
                await mensaje.add_reaction("🥇")
                await mensaje.add_reaction("🥈")
                await mensaje.add_reaction("🥉")
                return
            except Exception as e:
                await message.channel.send(f"❌ Error: {e}")
                return

        # ===== COMANDO NUEVO: META PET - MASCOTAS =====
        if peticion.lower().startswith("pet "):
            try:
                mascota = peticion[4:].strip().lower()
                if not mascota:
                    await message.channel.send("Usage: `meta pet firebird` or `meta pet polar bear pvp`")
                    return

                msg = await message.channel.send(f"🔍 Analyzing pets **{mascota.title()}** from TFT channels... 10s")

                partes = mascota.split()
                mascota_nombre = " ".join(partes[:-1]) if partes[-1] in ["pvp", "rally", "bears", "garrison"] else " ".join(partes)
                tipo_uso = partes[-1] if partes[-1] in ["pvp", "rally", "bears", "garrison"] else "pvp"

                query_base = f"{mascota_nombre} pet {tipo_uso} call of dragons 2026 stats skills"

                sitios = [
                    "site:youtube.com/@BOSSNASTi",
                    "site:youtube.com/@thefluffywafles",
                    "site:youtube.com/@YTGunzCOD",
                    "site:youtube.com",
                    "site:reddit.com/r/callofdragons",
                    "site:callofdragons.fandom.com"
                ]

                todos_los_resultados = []
                for sitio in sitios:
                    try:
                        url = "https://google.serper.dev/search"
                        headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
                        payload = {"q": f"{query_base} {sitio}", "num": 2, "gl": "us", "hl": "en"}
                        response = requests.post(url, headers=headers, json=payload, timeout=10)
                        data = response.json()
                        if "organic" in data:
                            todos_los_resultados.extend(data["organic"][:2])
                    except:
                        pass

                if not todos_los_resultados:
                    await msg.edit(content=f"❌ No guides found for pet {mascota_nombre}")
                    return

                mejores_3 = []
                links_usados = []
                for resultado in todos_los_resultados:
                    if resultado["link"] not in links_usados and len(mejores_3) < 3:
                        mejores_3.append(resultado)
                        links_usados.append(resultado["link"])

                embed = discord.Embed(
                    title=f"🐾 TOP 3 Guides {mascota_nombre.title()} - {tipo_uso.upper()}",
                    color=0x9B59B6,
                    description=f"Analyzed {len(todos_los_resultados)} sources | **Stats + Skills + Usage**"
                )

                emojis = ["🥇", "🥈", "🥉"]
                for i, build in enumerate(mejores_3):
                    if "@BOSSNASTi" in build["link"]: fuente = "BOSS NASTi"
                    elif "@thefluffywafles" in build["link"]: fuente = "Fluffy Waffles"
                    elif "@YTGunzCOD" in build["link"]: fuente = "GunzCOD"
                    elif "youtube" in build["link"]: fuente = "YouTube CoD"
                    elif "reddit" in build["link"]: fuente = "Reddit"
                    else: fuente = "Fandom Wiki"

                    if i == 0 and "youtube.com" in build["link"]:
                        try:
                            video_id = build["link"].split("v=")[-1].split("&")[0]
                            embed.set_thumbnail(url=f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg")
                        except:
                            pass

                    embed.add_field(
                        name=f"{emojis[i]} {fuente}",
                        value=f"**{build['title'][:55]}...**\n{build['snippet'][:130]}...\n[View Guide]({build['link']})",
                        inline=False
                    )

                embed.add_field(
                    name="📊 What to check in each guide:",
                    value="**Skills:** Active + Key Passives\n**Stats:** Attack/Defense/Health %\n**Best for:** PvP Field | Rally | Garrison | Bears",
                    inline=False
                )
                embed.set_footer(text=f"TFT | React 🥇🥈🥉 to vote | September 2026 Meta")
                await msg.delete()
                mensaje = await message.channel.send(embed=embed)
                await mensaje.add_reaction("🥇")
                await mensaje.add_reaction("🥈")
                await mensaje.add_reaction("🥉")
                return
            except Exception as e:
                await message.channel.send(f"❌ Error: {e}")
                return

        # ===== COMANDO: META BUSQUEDA GOOGLE =====
        await message.channel.send(f"🔍 Buscando: `{peticion}`")
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
                await message.channel.send("No encontré nada bro 🤷")
        except Exception as e:
            await message.channel.send(f"Error: {e}")

    await bot.process_commands(message)

bot.run(os.getenv("DISCORD_TOKEN"))
