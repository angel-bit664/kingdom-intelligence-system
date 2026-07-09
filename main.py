import discord
import os
import asyncio
import cloudscraper
from bs4 import BeautifulSoup
import re
import pandas as pd
from io import BytesIO
from deep_translator import GoogleTranslator
from collections import defaultdict

# ===== CONFIG =====
TOKEN = os.getenv("DISCORD_TOKEN")
ID_CANAL_ANUNCIOS = 1358237524249542751
# ==================

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

mensajes_para_borrar = defaultdict(list)

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')
    print(f'✅ Listo en {len(client.guilds)} servidores')
    print(f'✅ Canal anuncios ID: {ID_CANAL_ANUNCIOS}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id not in mensajes_para_borrar:
        mensajes_para_borrar[message.channel.id] = []

    if not message.content.lower().startswith("meta "):
        return

    peticion = message.content[5:].strip()

    # ===== META ACTIVATE - INTERACTIVO =====
    if peticion.lower().strip() == "activate":
        msg = await message.channel.send("👤 Menciona al usuario a activar:")
        mensajes_para_borrar[message.channel.id].append(msg)

        def check(m):
            return m.author == message.author and m.channel == message.channel and len(m.mentions) > 0

        try:
            respuesta = await client.wait_for('message', timeout=30.0, check=check)
            usuario = respuesta.mentions[0].mention
            mensajes_para_borrar[message.channel.id].append(respuesta)
        except asyncio.TimeoutError:
            msg = await message.channel.send("⏰ Tiempo agotado. Usa `meta activate @usuario`")
            mensajes_para_borrar[message.channel.id].append(msg)
            return

        embed = discord.Embed(
            title=f"💀 {usuario} ACTÍVATE O TE QUEMAN 💀",
            description="🏰 **LA TORRE CAERÁ**",
            color=0xFF0000
        )
        embed.add_field(name="⚔️ Situación", value="Inactivo | Sin escudo | Enemigo en zona", inline=False)
        embed.add_field(name="🛡️ OPCIONES PARA SALVARTE", value="1. **Conecta y defiende AHORA**\n2. **Escudo 8h YA**\n3. **Haz teleport a otra zona**", inline=False)

        canal_anuncios = client.get_channel(ID_CANAL_ANUNCIOS)
        if not canal_anuncios:
            msg = await message.channel.send(f"❌ **No encontré el canal**\nID configurado: `{ID_CANAL_ANUNCIOS}`")
            mensajes_para_borrar[message.channel.id].append(msg)
            return
            
        await canal_anuncios.send(content=f"{usuario}", embed=embed)
        msg = await message.channel.send(f"✅ Aviso enviado a {canal_anuncios.mention}")
        mensajes_para_borrar[message.channel.id].append(msg)
        return

    # ===== META ACTIVATE - DIRECTO =====
    if peticion.lower().startswith("activate ") and message.mentions:
        usuario = message.mentions[0].mention
        embed = discord.Embed(
            title=f"💀 {usuario} ACTÍVATE O TE QUEMAN 💀",
            description="🏰 **LA TORRE CAERÁ**",
            color=0xFF0000
        )
        embed.add_field(name="⚔️ Situación", value="Inactivo | Sin escudo | Enemigo en zona", inline=False)
        embed.add_field(name="🛡️ OPCIONES PARA SALVARTE", value="1. **Conecta y defiende AHORA**\n2. **Escudo 8h YA**\n3. **Haz teleport a otra zona**", inline=False)

        canal_anuncios = client.get_channel(ID_CANAL_ANUNCIOS)
        if not canal_anuncios:
            msg = await message.channel.send(f"❌ **No encontré el canal**\nID configurado: `{ID_CANAL_ANUNCIOS}`")
            mensajes_para_borrar[message.channel.id].append(msg)
            return
            
        await canal_anuncios.send(content=f"{usuario}", embed=embed)
        msg = await message.channel.send(f"✅ Aviso enviado a {canal_anuncios.mention}")
        mensajes_para_borrar[message.channel.id].append(msg)
        return

    try:
        # ===== META LIMPIA =====
        if peticion.lower() == "limpia":
            if not message.channel.permissions_for(message.guild.me).manage_messages:
                await message.channel.send("❌ **Sin permisos**\n\n**Cómo arreglar:**\n1. Server Settings → Roles → Me\n2. Activa 'Manage Messages'")
                return

            await message.delete()
            borrados = 0
            async for msg in message.channel.history(limit=100):
                if msg.author == client.user or msg.content.lower().startswith("meta "):
                    try:
                        await msg.delete()
                        borrados += 1
                        await asyncio.sleep(0.5)
                    except:
                        pass

            confirm = await message.channel.send(f"🧹 Limpieza: {borrados} mensajes borrados")
            await asyncio.sleep(3)
            await confirm.delete()
            return

        # ===== META PING =====
        if peticion.lower() == "ping":
            latencia = round(client.latency * 1000)
            embed = discord.Embed(title="🏓 Pong!", color=0x2ECC71)
            embed.add_field(name="Latencia", value=f"{latencia}ms", inline=True)
            embed.add_field(name="Estado", value="✅ Bot activo", inline=True)
            embed.add_field(name="Servidores", value=str(len(client.guilds)), inline=True)
            msg = await message.channel.send(embed=embed)
            mensajes_para_borrar[message.channel.id].append(msg)
            return

        # ===== META AYUDA =====
        if peticion.lower() == "ayuda":
            embed = discord.Embed(title="📋 Comandos Meta TFT", color=0x3498DB)
            embed.add_field(name="🧹 meta limpia", value="Borra spam de meta", inline=False)
            embed.add_field(name="🏓 meta ping", value="Revisa si el bot está vivo", inline=False)
            embed.add_field(name="🚨 meta activate @usuario", value="Aviso urgente a jugador inactivo", inline=False)
            embed.add_field(name="📢 meta alerta <texto>", value="Alerta oficial bilingüe", inline=False)
            embed.add_field(name="📅 meta evento <texto>", value="Evento bilingüe con reacción", inline=False)
            embed.add_field(name="🌐 meta traducir <texto>", value="Traduce ES ↔ EN", inline=False)
            embed.add_field(name="🔍 meta check id <número>", value="Stats jugador por ID", inline=False)
            embed.add_field(name="🌍 meta check reino <número>", value="Top 50 reino", inline=False)
            embed.add_field(name="📊 meta codstats <reino>", value="Excel stats completos del reino", inline=False)
            embed.add_field(name="⚔️ meta calc tropas <cant> <tier>", value="Calcula tiempo entrenamiento", inline=False)
            embed.add_field(name="⏰ meta calc speedup <tiempo>", value="Convierte a speedups", inline=False)
            embed.add_field(name="⚠️ meta talentos/mascota", value="Deshabilitado - migrando API", inline=False)
            embed.set_footer(text="Tip: IDs se sacan de callofstats.com/player/1234567")
            msg = await message.channel.send(embed=embed)
            mensajes_para_borrar[message.channel.id].append(msg)
            return

        # ===== META ALERTA =====
        if peticion.lower().startswith("alerta "):
            texto = peticion[7:].strip()
            if not texto:
                msg = await message.channel.send("❌ **Uso:** `meta alerta Reunión en fortaleza 20:00 UTC`")
                mensajes_para_borrar[message.channel.id].append(msg)
                return

            if ID_CANAL_ANUNCIOS == 0:
                await message.channel.send("❌ **ID_CANAL_ANUNCIOS no configurado**\nRailway → Variables → Agrega ID")
                return

            canal = client.get_channel(ID_CANAL_ANUNCIOS)
            if not canal:
                await message.channel.send(f"❌ **No encontré el canal**\nID configurado: `{ID_CANAL_ANUNCIOS}`")
                return

            try:
                traduccion = GoogleTranslator(source='auto', target='en').translate(texto)
            except:
                traduccion = "Translation failed"

            embed = discord.Embed(title="🚨 ALERTA OFICIAL TFT", color=0xE74C3C)
            embed.add_field(name="🇲🇽 Español", value=texto, inline=False)
            embed.add_field(name="🇺🇸 English", value=traduccion, inline=False)
            embed.set_footer(text="TFT Alliance")

            await canal.send("@everyone", embed=embed)
            msg = await message.channel.send(f"✅ Alerta enviada a {canal.mention}")
            mensajes_para_borrar[message.channel.id].append(msg)
            return

        # ===== META EVENTO =====
        if peticion.lower().startswith("evento "):
            texto = peticion[7:].strip()
            if not texto:
                msg = await message.channel.send("❌ **Uso:** `meta evento Ruinas antiguas 18:00 UTC`")
                mensajes_para_borrar[message.channel.id].append(msg)
                return

            if ID_CANAL_ANUNCIOS == 0:
                await message.channel.send("❌ **ID_CANAL_ANUNCIOS no configurado**\nRailway → Variables → Agrega ID")
                return

            canal = client.get_channel(ID_CANAL_ANUNCIOS)
            if not canal:
                await message.channel.send(f"❌ **No encontré el canal**\nID: `{ID_CANAL_ANUNCIOS}`")
                return

            try:
                traduccion = GoogleTranslator(source='auto', target='en').translate(texto)
            except:
                traduccion = "Translation failed"

            embed = discord.Embed(title="📅 EVENTO TFT", color=0x9B59B6)
            embed.add_field(name="🇲🇽 Español", value=texto, inline=False)
            embed.add_field(name="🇺🇸 English", value=traduccion, inline=False)
            embed.set_footer(text="Reacciona con 👍 si asistirás")

            msg_evento = await canal.send("@everyone", embed=embed)
            await msg_evento.add_reaction("👍")
            msg = await message.channel.send(f"✅ Evento publicado en {canal.mention}")
            mensajes_para_borrar[message.channel.id].append(msg)
            return

        # ===== META TRADUCIR =====
        if peticion.lower().startswith("traducir "):
            texto = peticion[9:].strip()
            if not texto:
                msg = await message.channel.send("❌ **Uso:** `meta traducir hola mundo`")
                mensajes_para_borrar[message.channel.id].append(msg)
                return

            try:
                if re.search(r'[áéíóúñ]', texto.lower()):
                    traduccion = GoogleTranslator(source='es', target='en').translate(texto)
                    embed = discord.Embed(title="🌐 Traducción", color=0x1ABC9C)
                    embed.add_field(name="🇲🇽 Español", value=texto, inline=False)
                    embed.add_field(name="🇺🇸 English", value=traduccion, inline=False)
                else:
                    traduccion = GoogleTranslator(source='en', target='es').translate(texto)
                    embed = discord.Embed(title="🌐 Traducción", color=0x1ABC9C)
                    embed.add_field(name="🇺🇸 English", value=texto, inline=False)
                    embed.add_field(name="🇲🇽 Español", value=traduccion, inline=False)

                msg = await message.channel.send(embed=embed)
                mensajes_para_borrar[message.channel.id].append(msg)
            except Exception as e:
                await message.channel.send(f"❌ **Error traduciendo**\n\n`{str(e)[:100]}`")
            return

        # ===== META CHECK =====
        if peticion.lower().startswith("check "):
            args = peticion[6:].strip().split()
            if not args:
                embed = discord.Embed(title="🔍 Meta Check - Opciones", color=0x3498DB)
                embed.add_field(name="Por ID", value="`meta check id 1234567`", inline=False)
                embed.add_field(name="Top reino", value="`meta check reino 127`", inline=False)
                embed.add_field(name="💡 Tip", value="Saca el ID de: callofstats.com/player/1234567", inline=False)
                msg = await message.channel.send(embed=embed)
                mensajes_para_borrar[message.channel.id].append(msg)
                return

            msg = await message.channel.send("🔍 Buscando...")
            mensajes_para_borrar[message.channel.id].append(msg)

            scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows'})
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

            try:
                if args[0].lower() == "id":
                    if len(args) < 2 or not args[1].isdigit():
                        await msg.edit(content="❌ **Uso:** `meta check id 1234567`\n\n**Cómo sacar ID:**\n1. Ve a callofstats.com\n2. Busca jugador\n3. Copia número de URL")
                        return

                    player_id = args[1]
                    url = f"https://callofstats.com/player/{player_id}"
                    await msg.edit(content=f"🔍 Conectando a callofstats.com...")

                    response = scraper.get(url, headers=headers, timeout=25)

                    if response.status_code == 404:
                        await msg.edit(content=f"❌ **Error 404**: ID `{player_id}` no existe\n\n**Saca el ID correcto:**\n1. callofstats.com/player/...\n2. Copia SOLO el número")
                        return
                    elif response.status_code == 403:
                        await msg.edit(content=f"❌ **Error 403**: Cloudflare bloqueó Railway\n\n**Solución:** Abre {url} en navegador y verifica")
                        return
                    elif response.status_code!= 200:
                        await msg.edit(content=f"❌ **Error {response.status_code}**: No pude cargar el perfil")
                        return

                    soup = BeautifulSoup(response.text, 'html.parser')

                    def get_stat(nombre):
                        try:
                            elemento = soup.find(text=re.compile(nombre, re.I))
                            if elemento:
                                parent = elemento.parent
                                next_el = parent.find_next(['td', 'div', 'span']) if parent else None
                                if next_el and next_el.get_text(strip=True):
                                    return next_el.get_text(strip=True)
                        except:
                            pass
                        return "N/A"

                    poder = get_stat("Power")
                    kills = get_stat("Kill")
                    muertes = get_stat("Dead")
                    reino = get_stat("Kingdom")
                    alianza = get_stat("Alliance")
                    nombre_real = get_stat("Name") or f"ID {player_id}"

                    embed = discord.Embed(title=f"⚔️ {nombre_real}", color=0x3498DB, url=url)
                    embed.add_field(name="🆔 ID", value=player_id, inline=True)
                    embed.add_field(name="🏰 Reino", value=reino, inline=True)
                    embed.add_field(name="🛡️ Alianza", value=alianza, inline=True)
                    embed.add_field(name="💪 Poder", value=poder, inline=True)
                    embed.add_field(name="⚔️ Kills", value=kills, inline=True)
                    embed.add_field(name="💀 Muertes", value=muertes, inline=True)

                    try:
                        if kills!= "N/A" and muertes!= "N/A" and muertes!= "0":
                            k = float(kills.replace(',', '').replace('.', ''))
                            d = float(muertes.replace(',', '').replace('.', ''))
                            if d > 0:
                                embed.add_field(name="K/D", value=f"{k/d:.2f}", inline=True)
                    except:
                        pass

                    embed.set_footer(text="Fuente: callofstats.com")
                    await msg.delete()
                    msg_final = await message.channel.send(embed=embed)
                    mensajes_para_borrar[message.channel.id].append(msg_final)

                elif args[0].lower() == "reino":
                    if len(args) < 2 or not args[1].isdigit():
                        await msg.edit(content="❌ **Uso:** `meta check reino 127`\n\n**Reinos activos:** 127, 128, 129, 300, 301, 305")
                        return

                    reino = args[1]
                    url = f"https://callofstats.com/server/{reino}"
                    await msg.edit(content=f"📊 Descargando reino {reino}...")

                    response = scraper.get(url, headers=headers, timeout=25)

                    if response.status_code == 404:
                        await msg.edit(content=f"❌ **Error 404**: Reino {reino} no existe\n\n**Reinos activos:** 127, 128, 129, 300, 301, 305")
                        return
                    elif response.status_code == 403:
                        await msg.edit(content=f"❌ **Error 403**: Cloudflare bloqueó Railway para reino {reino}\n\nIntenta más tarde o usa `meta codstats {reino}`")
                        return
                    elif response.status_code!= 200:
                        await msg.edit(content=f"❌ **Error {response.status_code}**")
                        return

                    soup = BeautifulSoup(response.text, 'html.parser')
                    tabla = soup.find('table')
                    if not tabla:
                        await msg.edit(content=f"❌ **Reino {reino} sin datos**\n\nEl reino existe pero no tiene tabla de jugadores.\nPuede ser nuevo o inactivo.")
                        return

                    df = pd.read_html(str(tabla))[0].head(50)
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, sheet_name=f'Reino_{reino}', index=False)
                    output.seek(0)

                    archivo = discord.File(output, filename=f'COD_Reino_{reino}_Top50.xlsx')
                    await msg.delete()
                    msg_final = await message.channel.send(f"✅ **Top 50 Reino {reino}**", file=archivo)
                    mensajes_para_borrar[message.channel.id].append(msg_final)

                else:
                    await msg.edit(content="❌ **Uso:** `meta check id 1234567` o `meta check reino 127`\n\nEscribe `meta ayuda` para ver opciones")

            except asyncio.TimeoutError:
                await msg.edit(content="❌ **Timeout**: Railway tardó +25s\n\n**Causa:** Cloudflare bloqueando o servidor lento\n**Solución:** Intenta de nuevo en 30s")
            except Exception as e:
                print(f"[ERROR] Meta check: {e}")
                await msg.edit(content=f"❌ **Error inesperado**\n\n`{str(e)[:150]}`\n\nReporta esto si persiste")
            return

        # ===== META CALC =====
        if peticion.lower().startswith("calc "):
            args = peticion[5:].strip().split()
            if len(args) < 2:
                embed = discord.Embed(title="🧮 Meta Calc", color=0xF39C12)
                embed.add_field(name="Tropas", value="`meta calc tropas 100000 T5`\nCalcula tiempo de entrenamiento", inline=False)
                embed.add_field(name="Speedups", value="`meta calc speedup 7d 12h`\nConvierte tiempo a speedups", inline=False)
                msg = await message.channel.send(embed=embed)
                mensajes_para_borrar[message.channel.id].append(msg)
                return

            tipo = args[0].lower()

            if tipo == "tropas":
                if len(args) < 3:
                    await message.channel.send("❌ **Uso:** `meta calc tropas 100000 T5`\n\n**Tiers:** T1, T2, T3, T4, T5")
                    return

                try:
                    cantidad = int(args[1].replace(',', ''))
                    tier = args[2].upper()
                    tiempos = {'T1': 30, 'T2': 60, 'T3': 120, 'T4': 240, 'T5': 480}

                    if tier not in tiempos:
                        await message.channel.send("❌ **Tier inválido**\n\nUsa: T1, T2, T3, T4 o T5\nEjemplo: `meta calc tropas 50000 T5`")
                        return

                    total_segundos = cantidad * tiempos[tier]
                    dias = total_segundos // 86400
                    horas = (total_segundos % 86400) // 3600
                    minutos = (total_segundos % 3600) // 60

                    embed = discord.Embed(title="⚔️ Calculadora de Tropas", color=0xF39C12)
                    embed.add_field(name="Cantidad", value=f"{cantidad:,} {tier}", inline=True)
                    embed.add_field(name="Tiempo Base", value=f"{dias}d {horas}h {minutos}m", inline=True)
                    embed.add_field(name="Con Buff 20%", value=f"{int(total_segundos*0.8//86400)}d {int((total_segundos*0.8%86400)//3600)}h", inline=True)
                    embed.set_footer(text="Sin buffs de alianza/tecnología/héroes")

                    msg = await message.channel.send(embed=embed)
                    mensajes_para_borrar[message.channel.id].append(msg)
                except ValueError:
                    await message.channel.send("❌ **Cantidad inválida**\n\nUsa números: `meta calc tropas 100000 T5`")

            elif tipo == "speedup":
                if len(args) < 2:
                    await message.channel.send("❌ **Uso:** `meta calc speedup 7d 12h 30m`\n\n**Formato:** `1d 5h 30m`")
                    return

                tiempo_str = " ".join(args[1:])
                dias = horas = minutos = 0
                d_match = re.search(r'(\d+)d', tiempo_str)
                h_match = re.search(r'(\d+)h', tiempo_str)
                m_match = re.search(r'(\d+)m', tiempo_str)
                if d_match: dias = int(d_match.group(1))
                if h_match: horas = int(h_match.group(1))
                if m_match: minutos = int(m_match.group(1))

                total_horas = dias * 24 + horas + minutos / 60
                speed_24h = int(total_horas // 24)
                resto = total_horas % 24
                speed_8h = int(resto // 8)
                resto = resto % 8
                speed_1h = int(resto)

                embed = discord.Embed(title="⚡ Calculadora Speedups", color=0xF39C12)
                embed.add_field(name="Tiempo Total", value=f"{dias}d {horas}h {minutos}m", inline=False)
                embed.add_field(name="Speedups 24h", value=str(speed_24h), inline=True)
                embed.add_field(name="Speedups 8h", value=str(speed_8h), inline=True)
                embed.add_field(name="Speedups 1h", value=str(speed_1h), inline=True)

                msg = await message.channel.send(embed=embed)
                mensajes_para_borrar[message.channel.id].append(msg)
            else:
                await message.channel.send("❌ **Uso:** `meta calc tropas 100000 T5` o `meta calc speedup 7d 12h`")
            return

        # ===== META CODSTATS =====
        if peticion.lower().startswith("codstats "):
            args = peticion[9:].strip().split()
            if not args or not args[0].isdigit():
                msg = await message.channel.send("❌ **Uso:** `meta codstats 127`\n\nDescarga Excel completo del reino")
                mensajes_para_borrar[message.channel.id].append(msg)
                return

            reino = args[0]
            msg = await message.channel.send(f"📊 Descargando stats completos del reino {reino}...")
            mensajes_para_borrar[message.channel.id].append(msg)

            try:
                scraper = cloudscraper.create_scraper()
                url = f"https://callofstats.com/server/{reino}"
                response = scraper.get(url, timeout=30)

                if response.status_code == 404:
                    await msg.edit(content=f"❌ **Error 404**: Reino {reino} no existe\n\n**Reinos activos:** 127, 128, 300, 305")
                    return
                elif response.status_code == 403:
                    await msg.edit(content=f"❌ **Error 403**: Cloudflare bloqueó Railway")
                    return
                elif response.status_code!= 200:
                    await msg.edit(content=f"❌ **Error {response.status_code}**")
                    return

                soup = BeautifulSoup(response.text, 'html.parser')
                tabla = soup.find('table')
                if not tabla:
                    await msg.edit(content=f"❌ **Reino {reino} sin datos**\n\nNo encontré tabla de jugadores")
                    return

                df = pd.read_html(str(tabla))[0]
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name=f'Reino_{reino}', index=False)
                output.seek(0)

                archivo = discord.File(output, filename=f'COD_Reino_{reino}_Completo.xlsx')
                await msg.delete()
                msg_final = await message.channel.send(f"✅ **Stats Completos Reino {reino}**\n{len(df)} jugadores", file=archivo)
                mensajes_para_borrar[message.channel.id].append(msg_final)

            except Exception as e:
                print(f"[ERROR] Meta codstats: {e}")
                await msg.edit(content=f"❌ **Error**\n\n`{str(e)[:150]}`")
            return

        # ===== COMANDOS DESHABILITADOS TEMPORALMENTE =====
        if peticion.lower().startswith("talentos ") or peticion.lower().startswith("mascota ") or peticion.lower().startswith("mascotas"):
            heroe = peticion.split(" ", 1)[1] if " " in peticion else "general"
            embed = discord.Embed(title="⚠️ Comando Deshabilitado", color=0xF39C12)
            embed.add_field(name="Motivo", value="Migrando a API directa", inline=False)
            embed.add_field(name="Mientras tanto usa:", value=f"🔗 callofdragonsguides.com\n🔗 coddb.app/pets", inline=False)
            embed.set_footer(text="Vuelve a estar activo en 2-3 días")
            msg = await message.channel.send(embed=embed)
            mensajes_para_borrar[message.channel.id].append(msg)
            return

        # Si no matcheó ningún comando
        msg = await message.channel.send(f"❌ **Comando no reconocido:** `meta {peticion}`\n\nEscribe `meta ayuda` para ver la lista")
        mensajes_para_borrar[message.channel.id].append(msg)

    except Exception as e:
        print(f"[ERROR CRÍTICO] {e}")
        try:
            await message.channel.send(f"❌ **Error crítico**\n\n`{str(e)[:150]}`\n\nReporta esto si persiste")
        except:
            pass

client.run(TOKEN)
