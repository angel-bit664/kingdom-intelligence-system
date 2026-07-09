import discord
import os
import asyncio
from deep_translator import GoogleTranslator
from collections import defaultdict
import re

# ===== CONFIG =====
TOKEN = os.getenv("DISCORD_TOKEN")
ID_CANAL_ANUNCIOS = 1358237524249542751 # Solo para meta alerta y meta evento
ID_CANAL_ACTIVATE = 1358237524799131662 # Solo para meta activate
# ==================

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

mensajes_para_borrar = defaultdict(list)
ultimo_anuncio = {}

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')
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

    # ===== META ACTIVATE - INTERACTIVO MULTIUSUARIO =====
    if peticion.lower().strip() == "activate":
        msg = await message.channel.send("👤 Menciona a los usuarios a activar (puedes mencionar varios):")
        mensajes_para_borrar[message.channel.id].append(msg)

        def check(m):
            return m.author == message.author and m.channel == message.channel and len(m.mentions) > 0

        try:
            respuesta = await client.wait_for('message', timeout=30.0, check=check)
            usuarios_mencionados = respuesta.mentions
            usuarios = " ".join([u.mention for u in usuarios_mencionados])
            usuarios_texto = ", ".join([u.mention for u in usuarios_mencionados])
            mensajes_para_borrar[message.channel.id].append(respuesta)
        except asyncio.TimeoutError:
            msg = await message.channel.send("⏰ Tiempo agotado. Usa `meta activate @usuario1 @usuario2`")
            mensajes_para_borrar[message.channel.id].append(msg)
            return

        texto_plural = "SE CONECTEN" if len(usuarios_mencionados) > 1 else "SE CONECTE"
        texto_salvarse = "salvarse" if len(usuarios_mencionados) > 1 else "salvarte"
        texto_conecten = "Conecten" if len(usuarios_mencionados) > 1 else "Conecta"
        texto_defiendan = "defiendan" if len(usuarios_mencionados) > 1 else "defiende"
        texto_hagan = "Hagan" if len(usuarios_mencionados) > 1 else "Haz"

        descripcion = f"""👑 **Familia TFT / TFT Family** 👑
📢 **¡NECESITAMOS QUE {texto_plural}! / WE NEED YOU ONLINE!**

🎯 **Misión / Mission:**
⚔️ **{usuarios_texto}** no tienen escudo y hay enemigos cerca
🛡️ **Opciones para {texto_salvarse} / Save yourselves:**
1. **{texto_conecten} y {texto_defiendan} AHORA / Connect and defend NOW**
2. **Escudo 8h YA / 8h Shield NOW**
3. **{texto_hagan} teleport a otra zona / Teleport to safety**

🔥 **Todos listos para defender / Everyone ready to defend**
¡Vamos TFT! ¡Aún queda guerra por delante / War is still ahead! 👑
⚔️"""

        embed = discord.Embed(description=descripcion, color=0xFF0000)
        embed.set_footer(text=f"Alerta enviada por: {autor_nombre}")

        # VALIDACIÓN: Solo manda a ID_CANAL_ACTIVATE, nunca a ID_CANAL_ANUNCIOS
        canal_activate = client.get_channel(ID_CANAL_ACTIVATE)
        if not canal_activate:
            msg = await message.channel.send(f"❌ **No encontré el canal de activate**\nID configurado: `{ID_CANAL_ACTIVATE}`")
            mensajes_para_borrar[message.channel.id].append(msg)
            return

        anuncio_msg = await canal_activate.send(content=usuarios, embed=embed)
        ultimo_anuncio[message.channel.id] = anuncio_msg
        await respuesta.delete()
        await msg.delete()
        return

    # ===== META ACTIVATE - DIRECTO MULTIUSUARIO =====
    if peticion.lower().startswith("activate ") and message.mentions:
        usuarios_mencionados = message.mentions
        usuarios = " ".join([u.mention for u in usuarios_mencionados])
        usuarios_texto = ", ".join([u.mention for u in usuarios_mencionados])
        
        texto_plural = "SE CONECTEN" if len(usuarios_mencionados) > 1 else "SE CONECTE"
        texto_salvarse = "salvarse" if len(usuarios_mencionados) > 1 else "salvarte"
        texto_conecten = "Conecten" if len(usuarios_mencionados) > 1 else "Conecta"
        texto_defiendan = "defiendan" if len(usuarios_mencionados) > 1 else "defiende"
        texto_hagan = "Hagan" if len(usuarios_mencionados) > 1 else "Haz"
        
        descripcion = f"""👑 **Familia TFT / TFT Family** 👑
📢 **¡NECESITAMOS QUE {texto_plural}! / WE NEED YOU ONLINE!**

🎯 **Misión / Mission:**
⚔️ **{usuarios_texto}** no tienen escudo y hay enemigos cerca
🛡️ **Opciones para {texto_salvarse} / Save yourselves:**
1. **{texto_conecten} y {texto_defiendan} AHORA / Connect and defend NOW**
2. **Escudo 8h YA / 8h Shield NOW**
3. **{texto_hagan} teleport a otra zona / Teleport to safety**

🔥 **Todos listos para defender / Everyone ready to defend**
¡Vamos TFT! ¡Aún queda guerra por delante / War is still ahead! 👑
⚔️"""

        embed = discord.Embed(description=descripcion, color=0xFF0000)
        embed.set_footer(text=f"Alerta enviada por: {autor_nombre}")

        # VALIDACIÓN: Solo manda a ID_CANAL_ACTIVATE, nunca a ID_CANAL_ANUNCIOS
        canal_activate = client.get_channel(ID_CANAL_ACTIVATE)
        if not canal_activate:
            msg = await message.channel.send(f"❌ **No encontré el canal de activate**\nID configurado: `{ID_CANAL_ACTIVATE}`")
            mensajes_para_borrar[message.channel.id].append(msg)
            return

        anuncio_msg = await canal_activate.send(content=usuarios, embed=embed)
        ultimo_anuncio[message.channel.id] = anuncio_msg
        await message.delete()
        return

    try:
        # ===== META EDITAR =====
        if peticion.lower() == "editar":
            if message.channel.id not in ultimo_anuncio:
                msg = await message.channel.send("❌ No hay ningún anuncio reciente para editar\n\nCrea uno primero con `meta alerta` o `meta evento`")
                mensajes_para_borrar[message.channel.id].append(msg)
                return

            msg = await message.channel.send("✏️ **¿Qué quieres editar?**\n\n1. Escribe el **nuevo mensaje en Español**\n2. Luego te pido el de Inglés\n\n*Escribe `cancelar` para salir*")
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
                    descripcion = f"""🎉 **Familia TFT / TFT Family** 🎉
📅 **EVENTO OFICIAL / OFFICIAL EVENT**

### 📌 EVENTO / EVENT ###
🇲🇽 **ES:** {texto_es.upper()}
🇺🇸 **EN:** {texto_en.upper()}

✅ **Confirmen asistencia / Confirm attendance**
Reacciona con 👍 si vas a participar / React 👍 if you're joining

¡Preparados TFT / Ready TFT! 🏆
Vamos por la victoria / Let's go for victory"""
                    color = 0x3498DB
                else:
                    descripcion = f"""👑 **Familia TFT / TFT Family** 👑
📢 **Necesitamos el apoyo de todos / We need everyone's support**

🎯 **Misión / Mission:**
🇲🇽 **ES:** {texto_es}
🇺🇸 **EN:** {texto_en}

🔥 **Todos están invitados / Everyone is invited**
Si quieren pelear y defender / If you want to fight and defend, los esperamos / we are waiting for you.

¡Vamos TFT / Let's go TFT! ¡Aún queda guerra por delante / War is still ahead! 👑
⚔️"""
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
            embed.add_field(name="🚨 meta activate @usuario1 @usuario2", value="Aviso urgente a jugadores inactivos", inline=False)
            embed.add_field(name="📢 meta alerta", value="Alerta bilingüe interactiva para @everyone", inline=False)
            embed.add_field(name="📅 meta evento", value="Evento bilingüe interactivo para @everyone", inline=False)
            embed.add_field(name="✏️ meta editar", value="Edita el último anuncio enviado", inline=False)
            embed.add_field(name="🌐 meta traducir <texto>", value="Traduce ES ↔ EN", inline=False)
            embed.add_field(name="⚔️ meta calc tropas <cant> <tier>", value="Calcula tiempo entrenamiento", inline=False)
            embed.add_field(name="⏰ meta calc speedup <tiempo>", value="Convierte a speedups", inline=False)
            embed.set_footer(text="Tip: Usa meta alerta/evento y luego meta editar para corregir")
            msg = await message.channel.send(embed=embed)
            mensajes_para_borrar[message.channel.id].append(msg)
            return

        # ===== META ALERTA =====
        if peticion.lower() == "alerta":
            canal = client.get_channel(ID_CANAL_ANUNCIOS)
            if not canal:
                await message.channel.send(f"❌ **No encontré el canal**\nID configurado: `{ID_CANAL_ANUNCIOS}`")
                return

            msg = await message.channel.send("📢 **Creando ALERTA TFT**\n\n🇲🇽 Escribe el mensaje en **Español**:\n*Escribe `cancelar` para salir*")
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

                descripcion = f"""👑 **Familia TFT / TFT Family** 👑
📢 **Necesitamos el apoyo de todos / We need everyone's support**

🎯 **Misión / Mission:**
🇲🇽 **ES:** {texto_es}
🇺🇸 **EN:** {texto_en}

🔥 **Todos están invitados / Everyone is invited**
Si quieren pelear y defender / If you want to fight and defend, los esperamos / we are waiting for you.

¡Vamos TFT / Let's go TFT! ¡Aún queda guerra por delante / War is still ahead! 👑
⚔️"""

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

            msg = await message.channel.send("📅 **Creando EVENTO TFT**\n\n🇲🇽 Escribe el mensaje en **Español**:\n*Escribe `cancelar` para salir*")
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

                descripcion = f"""🎉 **Familia TFT / TFT Family** 🎉
📅 **EVENTO OFICIAL / OFFICIAL EVENT**

### 📌 EVENTO / EVENT ###
🇲🇽 **ES:** {texto_es.upper()}
🇺🇸 **EN:** {texto_en.upper()}

✅ **Confirmen asistencia / Confirm attendance**
Reacciona con 👍 si vas a participar / React 👍 if you're joining

¡Preparados TFT / Ready TFT! 🏆
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
                        await message.channel.send("❌ **Tier inválido**\n\nUsa: T1, T2, T3, T4 o T5\nEjemplo: `meta calc tropas 50000 T5`")
                        return

                    total_segundos = cantidad * tiempos
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
