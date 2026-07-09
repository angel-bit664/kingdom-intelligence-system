import discord
import os
import asyncio
from datetime import datetime
import pytz
import pandas as pd
import io
from discord import ui
from deep_translator import GoogleTranslator
from kvk_diario import procesar_kvk_por_dia

TOKEN = os.getenv("DISCORD_TOKEN")

# ===== IDS DE CANALES SEGÚN TU IMAGEN =====
ID_CANAL_ACTIVATE = 1358237524799131662 # #general según me dijiste
ID_CANAL_ALERTAS = 1358237524249542751 # Canal para alertas
ID_CANAL_EVENTOS = 1358237524249542751 # Canal para eventos

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)

def get_hora_cdmx():
    return datetime.now(pytz.timezone("America/Mexico_City"))

def format_tiempo(seconds):
    if seconds < 0: return "0s"
    dias = int(seconds // 86400)
    horas = int((seconds % 86400) // 3600)
    minutos = int((seconds % 3600) // 60)
    segs = int(seconds % 60)
    partes = []
    if dias > 0: partes.append(f"{dias}d")
    if horas > 0: partes.append(f"{horas}h")
    if minutos > 0: partes.append(f"{minutos}m")
    if segs > 0 or not partes: partes.append(f"{segs}s")
    return " ".join(partes)

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    print(f"📅 Hora CDMX: {get_hora_cdmx().strftime('%Y-%m-%d %H:%M:%S')}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if not message.content.lower().startswith("meta "):
        return

    autor_nombre = message.author.display_name
    peticion = message.content[5:].strip()

    # ===== 1. META ACTIVATE =====
    if peticion.lower().startswith("activate"):
        args = peticion.split()[1:] # @R4 Sauron @R4 CaCoX
        canal = bot.get_channel(ID_CANAL_ACTIVATE)
        if not canal:
            await message.channel.send(f"❌ **No encontré el canal** con ID `{ID_CANAL_ACTIVATE}`")
            return

        menciones = " ".join(args) if args else "@here"
        embed = discord.Embed(
            title="🚨 CÓDIGO DE EMERGENCIA INDIVIDUAL",
            description=f"**Menciona solo a los usuarios indicados**\n{menciones}",
            color=0xFF0000
        )
        embed.set_footer(text=f"Activado por: {autor_nombre}")
        await canal.send(embed=embed)
        await message.channel.send("✅ **Código rojo enviado a #general**")
        return

    # ===== 2. META ALERTA =====
    if peticion.lower().startswith("alerta"):
        texto = peticion[6:].strip()
        if not texto:
            await message.channel.send("❌ **Uso:** `meta alerta <mensaje en ES y EN>`")
            return

        canal = bot.get_channel(ID_CANAL_ALERTAS)
        embed = discord.Embed(title="📢 ALERTA GENERAL BILINGÜE", color=0xF1C40F)
        embed.add_field(name="👑 Familia TFT / TFT Family 👑", value="📢 Necesitamos el apoyo de todos / We need everyone's support.", inline=False)
        embed.add_field(name="🎯 Misión / Mission:", value=texto, inline=False)
        embed.add_field(name="🔥 Todos están invitados / Everyone is invited.", value="Si quieren pelear y defender / If you want to fight and defend, los esperamos / we are waiting for you.", inline=False)
        embed.set_footer(text=f"Alerta enviada por: {autor_nombre}")
        await canal.send("@everyone", embed=embed)
        await message.channel.send("✅ **Alerta enviada**")
        return

    # ===== 3. META EVENTO =====
    if peticion.lower().startswith("evento"):
        texto = peticion[6:].strip()
        if not texto:
            await message.channel.send("❌ **Uso:** `meta evento <texto en ES y EN>`")
            return

        canal = bot.get_channel(ID_CANAL_EVENTOS)
        embed = discord.Embed(title="⚔️ EVENTO OFICIAL", description=texto, color=0x3498DB)
        embed.set_footer(text=f"Evento creado por: {autor_nombre}")
        msg = await canal.send("@everyone", embed=embed)
        await msg.add_reaction("👍")
        await message.channel.send("✅ **Evento publicado con reacción 👍**")
        return

    # ===== 4. META EDITAR =====
    if peticion.lower().startswith("editar"):
        texto_nuevo = peticion[6:].strip()
        if not texto_nuevo:
            await message.channel.send("❌ **Uso:** `meta editar <nuevo texto ES y EN>`")
            return

        # Busca el último mensaje del bot en el canal
        async for msg in message.channel.history(limit=50):
            if msg.author == bot.user and msg.embeds:
                try:
                    embed = msg.embeds[0]
                    embed.set_field_at(1, name="🎯 Misión / Mission:", value=texto_nuevo, inline=False)
                    await msg.edit(embed=embed)
                    await message.channel.send("✅ **Último anuncio editado**")
                    return
                except:
                    pass
        await message.channel.send("❌ **No encontré anuncio para editar**")
        return

    # ===== 5. META LIMPIA =====
    if peticion.lower().startswith("limpia"):
        def es_bot_o_meta(m):
            return m.author == bot.user or m.content.lower().startswith("meta ")

        borrados = await message.channel.purge(limit=50, check=es_bot_o_meta)
        await message.channel.send(f"🧹 **Limpié {len(borrados)} mensajes** del bot y comandos", delete_after=5)
        return

    # ===== 6. META PING =====
    if peticion.lower() == "ping":
        latencia = round(bot.latency * 1000)
        await message.channel.send(f"🟢 **Bot activo** | Latencia: `{latencia}ms`")
        return

    # ===== 7. META AYUDA =====
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

    # ===== 8. META TRADUCIR =====
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

    # ===== 9. META CALC TROPAS =====
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
            await message.channel.send(f"⚔️ **{cantidad:,} {tier}** = `{format_tiempo(segundos)}` de entrenamiento")
        except:
            await message.channel.send("❌ **Cantidad inválida**")
        return

    # ===== 10. META CALC SPEEDUP =====
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
        embed.set_footer(text=f"Total: {format_tiempo(segundos)}")
        await message.channel.send(embed=embed)
        return

    # ===== 11. META KVKDIARIO - NUEVO =====
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

bot.run(TOKEN)
