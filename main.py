import discord
import os
import asyncio
from deep_translator import GoogleTranslator
from collections import defaultdict
import re
import time

# ===== CONFIG =====
TOKEN = os.getenv("DISCORD_TOKEN")
ID_CANAL_ANUNCIOS = 1358237524249542751 # Para meta alerta y meta evento
ID_CANAL_ACTIVATE = 1358237524799313662 # Solo para meta activate
# ==================

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

mensajes_para_borrar = defaultdict(list)
ultimo_anuncio = {}
procesando_activate = set() # CANDADO ANTI-DUPLICADOS

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')
    print(f'✅ ID del bot: {client.user.id}')
    print(f'✅ Listo en {len(client.guilds)} servidores')
    print(f'✅ Canal anuncios: {ID_CANAL_ANUNCIOS}')
    print(f'✅ Canal activate: {ID_CANAL_ACTIVATE}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id not in mensajes_para_borrar:
        mensajes_para_borrar[message.channel.id] = []

    if not message.content.lower().startswith("meta "):
        return

    peticion = message.content[5:].strip()
    autor_nombre = message.author.display_name

    # ===== META ACTIVATE - CON LOGS PARA DEBUG =====
    if peticion.lower().startswith("activate"):
        print(f'[ACTIVATE] Comando recibido de {autor_nombre} - {time.time()}')

        # CANDADO: Si ya se está procesando un activate de este usuario, ignora
        if message.author.id in procesando_activate:
            print(f'[ACTIVATE] BLOQUEADO - Ya se está procesando activate de {autor_nombre}')
            return

        procesando_activate.add(message.author.id)
        print(f'[ACTIVATE] Candado puesto para {autor_nombre}')

        try:
            usuarios_mencionados = []

            if message.mentions:
                usuarios_mencionados = message.mentions
                print(f'[ACTIVATE] Menciones directas: {len(usuarios_mencionados)}')
            else:
                msg = await message.channel.send("👤 Menciona a los usuarios a activar (puedes mencionar varios):")

                def check(m):
                    return m.author == message.author and m.channel == message.channel and len(m.mentions) > 0

                try:
                    respuesta = await client.wait_for('message', timeout=30.0, check=check)
                    usuarios_mencionados = respuesta.mentions
                    print(f'[ACTIVATE] Menciones interactivas: {len(usuarios_mencionados)}')
                    await respuesta.delete()
                    await msg.delete()
                except asyncio.TimeoutError:
                    await message.channel.send("⏰ Tiempo agotado. Usa `meta activate @usuario1 @usuario2`")
                    await msg.delete()
                    return

            if not usuarios_mencionados:
                await message.channel.send("❌ **Debes mencionar al menos 1 usuario**\n\nEjemplo: `meta activate @Juan`")
                return

            usuarios = " ".join([u.mention for u in usuarios_mencionados])
            usuarios_texto = ", ".join([u.mention for u in usuarios_mencionados])

            texto_plural = "ACTÍVENSE" if len(usuarios_mencionados) > 1 else "ACTÍVATE"
            texto_sin = "NO TIENEN" if len(usuarios_mencionados) > 1 else "NO TIENE"
            texto_escudo = "ESCUDOS" if len(usuarios_mencionados) > 1 else "ESCUDO"

            descripcion = f"""🚨 **CÓDIGO DE EMERGENCIA TFT** 🚨
⚠️ **ALERTA ROJA / RED ALERT** ⚠️

🎯 **OBJETIVO / TARGET:**
**{usuarios_texto}**

❌ **ESTADO / STATUS**
{texto_sin} {texto_escudo} ACTIVO - ZONA DE PELIGRO
NO ACTIVE SHIELD - DANGER ZONE

🛡️ **PROTOCOLO DE EMERGENCIA / EMERGENCY PROTOCOL:**
1. **{texto_plural} INMEDIATAMENTE / CONNECT NOW**
2. **ESCUDO 8H YA / 8h SHIELD NOW**
3. **TELEPORT DE EMERGENCIA / EMERGENCY TELEPORT**

⚔️ **ALIANZA TFT EN ALERTA MÁXIMA**
TFT ALLIANCE ON MAXIMUM ALERT

Código emitido por: {autor_nombre}
⏰ TIEMPO ES CRÍTICO / TIME IS CRITICAL"""

            embed = discord.Embed(description=descripcion, color=0xFF0000)
            embed.set_footer(text=f"🚨 CÓDIGO ROJO TFT | {autor_nombre}")

            canal_activate = client.get_channel(ID_CANAL_ACTIVATE)
            if not canal_activate:
                await message.channel.send(f"❌ **No encontré el canal de activate**\nID configurado: `{ID_CANAL_ACTIVATE}`")
                return

            print(f'[ACTIVATE] Enviando mensaje ÚNICO al canal {ID_CANAL_ACTIVATE}')
            # UNICO SEND - SOLO 1 VEZ
            await canal_activate.send(content=usuarios, embed=embed)
            print(f'[ACTIVATE] Mensaje enviado exitosamente')
            await message.delete()

        finally:
            # QUITA EL CANDADO SIEMPRE, aunque haya error
            procesando_activate.discard(message.author.id)
            print(f'[ACTIVATE] Candado liberado para {autor_nombre}')

        return # CORTA AQUÍ - NO EJECUTA NADA MAS

    try:
        # ===== META EDITAR =====
        if peticion.lower() == "editar":
            if message.channel.id not in ultimo_anuncio:
                msg = await message.channel.send("❌ No hay ningún anuncio reciente para editar\n\nCrea uno primero con `meta alerta` o `meta evento`")
                mensajes_para_borrar[message.channel.id].append(msg)
                return

            msg = await message.channel.send("✏️ **¿Qué quieres editar?**\n\n1. Escribe el **nuevo mensaje en Español**")
            mensajes_para_borrar[message.channel.id].append(msg)

            def check(m):
                return m.author == message.author and m.channel == message.channel

            try:
                resp_es = await client.wait_for('message', timeout=60.0, check=check)
                if resp_es.content.lower() == "cancelar":
                    msg = await message.channel.send("❌ Edición cancelada")
                    mensajes_para_borrar[message.channel.id].append(msg)
                    return
                texto_es = resp_es.content
                mensajes_para_borrar[message.channel.id].append(resp_es)

                msg = await message.channel.send("🇺🇸 **Ahora escribe el mensaje en Inglés:**")
                mensajes_para_borrar[message.channel.id].append(msg)
                resp_en = await client.wait_for('message', timeout=60.0, check=check)
                texto_en = resp_en.content
                mensajes_para_borrar[message.channel.id].append(resp_en)

                anuncio_viejo = ultimo_anuncio[message.channel.id]
                embed_viejo = anuncio_viejo.embeds[0]

                if "EVENTO" in embed_viejo.description:
                    descripcion = f"""🎊 **Familia TFT / TFT Family** 🎊
📅 **EVENTO OFICIAL / OFFICIAL EVENT**

### 📌 EVENTO / EVENT ###
🇲🇽 **ES:** {texto_es.upper()}
🇺🇸 **EN:** {texto_en.upper()}

✅ **Confirmen asistencia / Confirm attendance**
Reacciona con 👍 si vas a participar / React 👍 if you're joining

¡Preparados TFT / Ready TFT! ⚔️
Vamos por la victoria / Let's go for victory"""
                    color = 0x3498DB
                else:
                    descripcion = f"""🎊 **Familia TFT / TFT Family** 🎊
🚨 **Necesitamos el apoyo de todos / We need everyone's support**

🎯 **Misión / Mission:**
🇲🇽 **ES:** {texto_es}
🇺🇸 **EN:** {texto_en}

🔥 **Todos están invitados / Everyone is invited**
Si quieren pelear y defender / If you want to fight and defend, los esperamos / we are waiting for you.

¡Vamos TFT / Let's go TFT! ¡Aún queda guerra por delante / War is still ahead! ⚔️"""
                    color = 0xF1C40F

                embed_nuevo = discord.Embed(description=descripcion, color=color)
                embed_nuevo.set_footer(text=f"Editado por: {autor_nombre}")

                await anuncio_viejo.edit(embed=embed_nuevo)
                await message.delete()
                await resp_es.delete()
                await resp_en.delete()
                await msg.delete()

            except asyncio.TimeoutError:
                msg = await message.channel.send("⏰ Tiempo agotado. Edición cancelada")
                mensajes_para_borrar[message.channel.id].append(msg)
            return

        # ===== META KVKDIARIO - NUEVO =====
        if peticion.lower().startswith("kvkdiario"):
            if len(message.attachments) < 2:
                msg = await message.channel.send("❌ **Sube mínimo 2 Excel**\n`01_dia1.xlsx`, `02_dia2.xlsx`...\n\n**Orden:** El nombre del archivo define el orden")
                mensajes_para_borrar[message.channel.id].append(msg)
                return
            if len(message.attachments) > 10:
                msg = await message.channel.send("❌ Máximo 10 archivos bro")
                mensajes_para_borrar[message.channel.id].append(msg)
                return
            from kvk_diario import procesar_kvk_por_dia
            import os
            msg = await message.channel.send(f"⏳ Procesando {len(message.attachments)} días KVK...")
            mensajes_para_borrar[message.channel.id].append(msg)
            try:
                attachments = sorted(message.attachments, key=lambda x: x.filename)
                rutas = []
                for i, adj in enumerate(attachments):
                    ruta = f'temp_kvk_dia{i+1}.xlsx'
                    await adj.save(ruta)
                    rutas.append(ruta)
                embed, archivo = await procesar_kvk_por_dia(rutas)
                await message.channel.send(embed=embed, file=archivo)
                await msg.delete()
                for ruta in rutas:
                    os.remove(ruta)
            except Exception as e:
                await msg.edit(content=f"❌ **Error:** {e}")
            return

        # ===== META LIMPIA =====
        if peticion.lower() == "limpia":
            if not message.channel.permissions_for(message.guild.me).manage_messages:
                await message.channel.send("❌ **Sin permisos**\n\n**Cómo arreglar:**\n1. Server Settings → Roles → Meta TFT\n2. Activa 'Manage Messages'\n3. Guarda")
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
            embed.add_field(name="🚨 meta activate @usuario1 @usuario2", value="Código de emergencia a jugadores inactivos", inline=False)
            embed.add_field(name="📢 meta alerta", value="Alerta bilingüe interactiva para @everyone", inline=False)
            embed.add_field(name="📅 meta evento", value="Evento bilingüe interactivo para @everyone", inline=False)
            embed.add_field(name="✏️ meta editar", value="Edita el último anuncio enviado", inline=False)
            embed.add_field(name="🌐 meta traducir <texto>", value="Traduce ES ↔ EN", inline=False)
            embed.add_field(name="⚔️ meta calc tropas <cant> <tier>", value="Calcula tiempo entrenamiento", inline=False)
            embed.add_field(name="⚡ meta calc speedup <tiempo>", value="Convierte a speedups", inline=False)
            embed.add_field(name="📊 meta kvkdiario", value="Progreso KVK acumulado por días", inline=False)
            embed.set_footer(text="Tip: Usa meta alerta/evento y luego meta editar para corregir")
            msg = await message.channel.send(embed=embed)
            mensajes_para_borrar[message.channel.id].append(msg)
            return

        # ===== META ALERTA =====
        if peticion.lower() == "alerta":
            canal = client.get_channel(ID_CANAL_ANUNCIOS)
            if not canal:
                await message.channel.send(f"❌ **No encontré el canal**\nID: `{ID_CANAL_ANUNCIOS}`")
                return

            msg = await message.channel.send("🚨 **Creando ALERTA TFT**\n\n🇲🇽 Escribe el mensaje en **Español**:")
            mensajes_para_borrar[message.channel.id].append(msg)

            def check(m):
                return m.author == message.author and m.channel == message.channel

            try:
                resp_es = await client.wait_for('message', timeout=60.0, check=check)
                if resp_es.content.lower() == "cancelar":
                    msg = await message.channel.send("❌ Alerta cancelada")
                    mensajes_para_borrar[message.channel.id].append(msg)
                    return
                texto_es = resp_es.content
                mensajes_para_borrar[message.channel.id].append(resp_es)

                msg = await message.channel.send("🇺🇸 Ahora escribe el mensaje en **Inglés**:")
                mensajes_para_borrar[message.channel.id].append(msg)
                resp_en = await client.wait_for('message', timeout=60.0, check=check)
                texto_en = resp_en.content
                mensajes_para_borrar[message.channel.id].append(resp_en)

                descripcion = f"""🎊 **Familia TFT / TFT Family** 🎊
🚨 **Necesitamos el apoyo de todos / We need everyone's support**

🎯 **Misión / Mission:**
🇲🇽 **ES:** {texto_es}
🇺🇸 **EN:** {texto_en}

🔥 **Todos están invitados / Everyone is invited**
Si quieren pelear y defender / If you want to fight and defend, los esperamos / we are waiting for you.

¡Vamos TFT / Let's go TFT! ¡Aún queda guerra por delante / War is still ahead! ⚔️"""

                embed = discord.Embed(description=descripcion, color=0xF1C40F)
                embed.set_footer(text=f"Alerta enviada por: {autor_nombre}")

                anuncio_msg = await canal.send("@everyone", embed=embed)
                ultimo_anuncio[message.channel.id] = anuncio_msg
                await message.delete()
                await resp_es.delete()
                await resp_en.delete()
                await msg.delete()

            except asyncio.TimeoutError:
                msg = await message.channel.send("⏰ Tiempo agotado. Alerta cancelada")
                mensajes_para_borrar[message.channel.id].append(msg)
            return

        # ===== META EVENTO =====
        if peticion.lower() == "evento":
            canal = client.get_channel(ID_CANAL_ANUNCIOS)
            if not canal:
                await message.channel.send(f"❌ **No encontré el canal**\nID: `{ID_CANAL_ANUNCIOS}`")
                return

            msg = await message.channel.send("📅 **Creando EVENTO TFT**\n\n🇲🇽 Escribe el mensaje en **Español**:")
            mensajes_para_borrar[message.channel.id].append(msg)

            def check(m):
                return m.author == message.author and m.channel == message.channel

            try:
                resp_es = await client.wait_for('message', timeout=60.0, check=check)
                if resp_es.content.lower() == "cancelar":
                    msg = await message.channel.send("❌ Evento cancelado")
                    mensajes_para_borrar[message.channel.id].append(msg)
                    return
                texto_es = resp_es.content
                mensajes_para_borrar[message.channel.id].append(resp_es)

                msg = await message.channel.send("🇺🇸 Ahora escribe el mensaje en **Inglés**:")
                mensajes_para_borrar[message.channel.id].append(msg)
                resp_en = await client.wait_for('message', timeout=60.0, check=check)
                texto_en = resp_en.content
                mensajes_para_borrar[message.channel.id].append(resp_en)

                descripcion = f"""🎊 **Familia TFT / TFT Family** 🎊
📅 **EVENTO OFICIAL / OFFICIAL EVENT**

### 📌 EVENTO / EVENT ###
🇲🇽 **ES:** {texto_es.upper()}
🇺🇸 **EN:** {texto_en.upper()}

✅ **Confirmen asistencia / Confirm attendance**
Reacciona con 👍 si vas a participar / React 👍 if you're joining

¡Preparados TFT / Ready TFT! ⚔️
Vamos por la victoria / Let's go for victory"""

                embed = discord.Embed(description=descripcion, color=0x3498DB)
                embed.set_footer(text=f"Evento publicado por: {autor_nombre}")

                msg_evento = await canal.send("@everyone", embed=embed)
                await msg_evento.add_reaction("👍")
                ultimo_anuncio[message.channel.id] = msg_evento
                await message.delete()
                await resp_es.delete()
                await resp_en.delete()
                await msg.delete()

            except asyncio.TimeoutError:
                msg = await message.channel.send("⏰ Tiempo agotado. Evento cancelado")
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
                        await message.channel.send("❌ **Tier inválido**\n\nUsa: T1, T2, T3, T4 o T5\nEjemplo: `meta calc tropas 100000 T5`")
                        return

                    total_segundos = cantidad * tiempos[tier]
                    dias = total_segundos // 86400
                    horas = (total_segundos % 86400) // 3600
                    minutos = (total_segundos % 3600) // 60

                    embed = discord.Embed(title="⚔️ Calculadora de Tropas", color=0xF39C12)
                    embed.add_field(name="Cantidad", value=f"{cantidad:,} {tier}", inline=True)
                    embed.add_field(name="Tiempo Base", value=f"{dias}d {horas}h {minutos}m", inline=True)
                    embed.add_field(name="Con Buff 20%", value=f"{int(total_segundos*0.8//86400)}d {int((total_segundos*0.8%86400)//3600)}h", inline=False)
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

        # Si no matcheó ningún comando
        msg = await message.channel.send(f"❌ **Comando no reconocido:** `meta {peticion}`\n\nEscribe `meta ayuda` para ver comandos")
        mensajes_para_borrar[message.channel.id].append(msg)

    except Exception as e:
        print(f"[ERROR CRÍTICO] {e}")
        try:
            await message.channel.send(f"❌ **Error crítico**\n\n`{str(e)[:150]}`\n\nReporta esto si persiste")
        except:
            pass

client.run(TOKEN)
