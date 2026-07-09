import discord
import os
import asyncio
from deep_translator import GoogleTranslator
from collections import defaultdict
import re
import time
from kvk_diario import procesar_kvk_por_dia
import pandas as pd

# ===== CONFIG =====
TOKEN = os.getenv("DISCORD_TOKEN")
ID_CANAL_ANUNCIOS = 1358237524249542751 # Para meta alerta y meta evento
ID_CANAL_ACTIVATE = 1358237524799131662 # Solo para meta activate
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

    # ===== META ACTIVATE - CON CANDADO ANTI-DUPLICADOS =====
    if peticion.lower().startswith("activate"):
        if message.author.id in procesando_activate:
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

            descripcion = f"""🚨 *CÓDIGO DE EMERGENCIA TFT* 🚨
⚠️ *ALERTA ROJA / RED ALERT* ⚠️

🎯 *OBJETIVO / TARGET:* *{usuarios_texto}*

❌ *ESTADO / STATUS:* {texto_sin} {texto_escudo} ACTIVO - ZONA DE PELIGRO
NO ACTIVE SHIELD - DANGER ZONE

🛡️ *PROTOCOLO DE EMERGENCIA / EMERGENCY PROTOCOL:*
   1. *{texto_plural} INMEDIATAMENTE / CONNECT NOW*
   2. *ESCUDO 8H YA / 8h SHIELD NOW*
   3. *TELEPORT DE EMERGENCIA / EMERGENCY TELEPORT*

⚔️ *ALIANZA TFT EN ALERTA MÁXIMA*
TFT ALLIANCE ON MAXIMUM ALERT

Código emitido por: {autor_nombre}
⏰ TIEMPO ES CRÍTICO / TIME IS CRITICAL"""

            embed = discord.Embed(description=descripcion, color=0xFF0000)
            embed.set_footer(text=f"🚨 CÓDIGO ROJO TFT | {autor_nombre}")

            canal_activate = client.get_channel(ID_CANAL_ACTIVATE)
            if not canal_activate:
                await message.channel.send(f"❌ **No encontré el canal de activate**\nID configurado: {ID_CANAL_ACTIVATE}")
                return

            print(f'[ACTIVATE] Enviando mensaje ÚNICO al canal {ID_CANAL_ACTIVATE}')
            # ÚNICO SEND - SOLO 1 VEZ
            await canal_activate.send(content=usuarios, embed=embed)
            print(f'[ACTIVATE] Mensaje enviado exitosamente')
            await message.delete()

        finally:
            # QUITA EL CANDADO SIEMPRE, aunque haya error
            procesando_activate.discard(message.author.id)
            print(f'[ACTIVATE] Candado liberado para {autor_nombre}')

        return # CORTA AQUÍ - NO EJECUTA NADA MÁS

    # ===== META ALERTA =====
    if peticion.lower().startswith("alerta"):
        texto_es = peticion[6:].strip()
        if not texto_es:
            await message.channel.send("❌ **Uso:** `meta alerta <mensaje en español>`")
            return

        try:
            texto_en = GoogleTranslator(source='es', target='en').translate(texto_es)
        except:
            texto_en = "Translation failed"

        canal = client.get_channel(ID_CANAL_ANUNCIOS)
        embed = discord.Embed(title="📢 ALERTA GENERAL BILINGÜE", color=0xF1C40F)
        embed.add_field(name="👑 Familia TFT / TFT Family 👑", value="📢 Necesitamos el apoyo de todos / We need everyone's support.", inline=False)
        embed.add_field(name="🎯 Misión / Mission:", value=f"🇲🇽 {texto_es}\n🇺🇸 {texto_en}", inline=False)
        embed.add_field(name="🔥 Todos están invitados / Everyone is invited.", value="Si quieren pelear y defender / If you want to fight and defend, los esperamos / we are waiting for you.", inline=False)
        embed.set_footer(text=f"Alerta enviada por: {autor_nombre}")
        await canal.send("@everyone", embed=embed)
        await message.channel.send("✅ **Alerta enviada**")
        return

    # ===== META EVENTO =====
    if peticion.lower().startswith("evento"):
        texto_es = peticion[6:].strip()
        if not texto_es:
            await message.channel.send("❌ **Uso:** `meta evento <descripción en español>`")
            return

        try:
            texto_en = GoogleTranslator(source='es', target='en').translate(texto_es)
        except:
            texto_en = "Translation failed"

        canal = client.get_channel(ID_CANAL_ANUNCIOS)
        embed = discord.Embed(title="⚔️ EVENTO OFICIAL / OFFICIAL EVENT", color=0x3498DB)
        embed.add_field(name="🇲🇽 Español", value=texto_es, inline=False)
        embed.add_field(name="🇺🇸 English", value=texto_en, inline=False)
        embed.set_footer(text=f"Evento creado por: {autor_nombre}")
        msg = await canal.send("@everyone", embed=embed)
        await msg.add_reaction("👍")
        await message.channel.send("✅ **Evento publicado**")
        return

    # ===== META EDITAR =====
    if peticion.lower().startswith("editar"):
        texto_nuevo = peticion[6:].strip()
        if not texto_nuevo:
            await message.channel.send("❌ **Uso:** `meta editar <nuevo texto>`")
            return

        async for msg in message.channel.history(limit=50):
            if msg.author == client.user and msg.embeds:
                try:
                    embed = msg.embeds[0]
                    try:
                        texto_en = GoogleTranslator(source='es', target='en').translate(texto_nuevo)
                    except:
                        texto_en = "Translation failed"
                    embed.set_field_at(1, name="🎯 Misión / Mission:", value=f"🇲🇽 {texto_nuevo}\n🇺🇸 {texto_en}", inline=False)
                    await msg.edit(embed=embed)
                    await message.channel.send("✅ **Último anuncio editado**")
                    return
                except:
                    pass
        await message.channel.send("❌ **No encontré anuncio para editar**")
        return

    # ===== META LIMPIA =====
    if peticion.lower().startswith("limpia"):
        def es_bot_o_meta(m):
            return m.author == client.user or m.content.lower().startswith("meta ")

        borrados = await message.channel.purge(limit=50, check=es_bot_o_meta)
        await message.channel.send(f"🧹 **Limpié {len(borrados)} mensajes** del bot y comandos", delete_after=5)
        return

    # ===== META PING =====
    if peticion.lower() == "ping":
        latencia = round(client.latency * 1000)
        await message.channel.send(f"🟢 **Bot activo** | Latencia: `{latencia}ms`")
        return

    # ===== META AYUDA =====
    if peticion.lower() == "ayuda":
        embed = discord.Embed(title="🤖 COMANDOS DISPONIBLES - META BOT", color=0x9B59B6)
        embed.add_field(name="🚨 meta activate @usuario", value="Código de emergencia individual", inline=False)
        embed.add_field(name="📢 meta alerta <texto>", value="Alerta general bilingüe para @everyone", inline=False)
        embed.add_field(name="⚔️ meta evento <texto>", value="Evento oficial con reacción 👍", inline=False)
        embed.add_field(name="✏️ meta editar <texto>", value="Edita el último anuncio enviado", inline=False)
        embed.add_field(name="🧹 meta limpia", value="Borra spam del bot y comandos", inline=False)
        embed.add_field(name="🟢 meta ping", value="Verifica si el bot está activo", inline=False)
        embed.add_field(name="🌐 meta traducir <texto>", value="Traducción automática ES ↔ EN", inline=False)
        embed.add_field(name="⚔️ meta calc tropas <cant> <tier>", value="Calcula tiempo de entrenamiento", inline=False)
        embed.add_field(name="⏳ meta calc speedup <tiempo>", value="Convierte tiempo a speedups", inline=False)
        embed.add_field(name="📊 meta kvkdiario", value="Procesa Excel KVK acumulado", inline=False)
        embed.set_footer(text="META ESTÁ CONTIGO. UN REINO, UNA ALIANZA, UNA META.")
        await message.channel.send(embed=embed)
        return

    # ===== META TRADUCIR =====
    if peticion.lower().startswith("traducir "):
        texto = peticion[9:].strip()
        if not texto:
            await message.channel.send("❌ **Uso:** `meta traducir hola mundo`")
            return
        try:
            idioma = GoogleTranslator().detect(texto)
            if idioma == 'es':
                traducido = GoogleTranslator(source='es', target='en').translate(texto)
                await message.channel.send(f"🇲🇽→🇺🇸 **{traducido}**")
            else:
                traducido = GoogleTranslator(source='auto', target='es').translate(texto)
                await message.channel.send(f"🇺🇸→🇲🇽 **{traducido}**")
        except Exception as e:
            await message.channel.send(f"❌ Error al traducir: {e}")
        return

    # ===== META CALC TROPAS =====
    if peticion.lower().startswith("calc tropas"):
        args = peticion.split()
        if len(args) < 4:
            await message.channel.send("❌ **Uso:** `meta calc tropas 100000 T5`")
            return
        try:
            cantidad = int(args[2])
            tier = args[3].upper()
            tiempos = {"T1": 10, "T2": 20, "T3": 30, "T4": 45, "T5": 60}
            if tier not in tiempos:
                await message.channel.send("❌ **Tier inválido.** Usa T1, T2, T3, T4 o T5")
                return
            segundos = tiempos[tier] * cantidad
            def format_tiempo(s):
                dias = int(s // 86400)
                horas = int((s % 86400) // 3600)
                minutos = int((s % 3600) // 60)
                segs = int(s % 60)
                partes = []
                if dias > 0: partes.append(f"{dias}d")
                if horas > 0: partes.append(f"{horas}h")
                if minutos > 0: partes.append(f"{minutos}m")
                if segs > 0 or not partes: partes.append(f"{segs}s")
                return " ".join(partes)
            await message.channel.send(f"⚔️ **{cantidad:,} {tier}** = `{format_tiempo(segundos)}` de entrenamiento")
        except:
            await message.channel.send("❌ **Cantidad inválida**")
        return

    # ===== META CALC SPEEDUP =====
    if peticion.lower().startswith("calc speedup"):
        tiempo_str = peticion[12:].strip()
        if not tiempo_str:
            await message.channel.send("❌ **Uso:** `meta calc speedup 7d 12h 30m`")
            return
        segundos = 0
        for parte in tiempo_str.split():
            if parte.endswith('d'): segundos += int(parte[:-1]) * 86400
            elif parte.endswith('h'): segundos += int(parte[:-1]) * 3600
            elif parte.endswith('m'): segundos += int(parte[:-1]) * 60
            elif parte.endswith('s'): segundos += int(parte[:-1])

        embed = discord.Embed(title="⏳ Conversión a Speedups", color=0xF39C12)
        embed.add_field(name="1 minuto", value=f"`{segundos // 60:,}`", inline=True)
        embed.add_field(name="5 minutos", value=f"`{segundos // 300:,}`", inline=True)
        embed.add_field(name="15 minutos", value=f"`{segundos // 900:,}`", inline=True)
        embed.add_field(name="60 minutos", value=f"`{segundos // 3600:,}`", inline=True)
        def format_tiempo(s):
            dias = int(s // 86400)
            horas = int((s % 86400) // 3600)
            minutos = int((s % 3600) // 60)
            segs = int(s % 60)
            partes = []
            if dias > 0: partes.append(f"{dias}d")
            if horas > 0: partes.append(f"{horas}h")
            if minutos > 0: partes.append(f"{minutos}m")
            if segs > 0 or not partes: partes.append(f"{segs}s")
            return " ".join(partes)
        embed.set_footer(text=f"Total: {format_tiempo(segundos)}")
        await message.channel.send(embed=embed)
        return

    # ===== META KVKDIARIO - NUEVO =====
    if peticion.lower().startswith("kvkdiario"):
        if not message.attachments:
            await message.channel.send("❌ **Sube mínimo 2 archivos Excel del KVK** junto con `meta kvkdiario`")
            return

        rutas_archivos = []
        for attachment in message.attachments:
            if attachment.filename.endswith('.xlsx'):
                ruta = f"/tmp/{attachment.filename}"
                await attachment.save(ruta)
                rutas_archivos.append(ruta)

        if len(rutas_archivos) < 2:
            await message.channel.send("❌ **Necesito mínimo 2 días de KVK** para calcular el progreso")
            return

        msg_procesando = await message.channel.send(f"⏳ Procesando {len(rutas_archivos)} días KVK...")

        try:
            embed, archivo_excel = await procesar_kvk_por_dia(rutas_archivos, subido_por=autor_nombre)
            await message.channel.send(embed=embed, file=discord.File(archivo_excel))
            await msg_procesando.delete()
        except Exception as e:
            await msg_procesando.edit(content=f"❌ **Error:** {str(e)[:150]}")
        return

    # Si no matcheó ningún comando
    await message.channel.send("❌ **Comando no reconocido.** Usa `meta ayuda` para ver la lista")

client.run(TOKEN)
