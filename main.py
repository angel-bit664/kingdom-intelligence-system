import discord
import os
import asyncio
from datetime import datetime, timedelta
import pytz
import pandas as pd
import io
from discord import ui
from kvk_diario import procesar_kvk_por_dia

TOKEN = os.getenv("DISCORD_TOKEN")
ID_CANAL_ACTIVATE = 1358237524799313662 # <-- REVISA QUE ESTE ID SEA CORRECTO
ID_CANAL_LOGS = 1358265885264494694
ID_CANAL_EVENTOS = 1358265885264494694
ID_CANAL_ALERTAS = 1358265885264494694

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)

def get_hora_cdmx():
    return datetime.now(pytz.timezone("America/Mexico_City"))

def format_tiempo(seconds):
    if seconds < 0:
        return "0s"
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

    # ===== META ACTIVATE =====
    if peticion.lower().startswith("activate"):
        canal = bot.get_channel(ID_CANAL_ACTIVATE)
        if not canal:
            await message.channel.send(f"❌ **No encontré el canal de activate** con ID `{ID_CANAL_ACTIVATE}`")
            return

        await message.channel.send("🔴 **CÓDIGO ROJO TFT ACTIVADO**\nRastreando usuarios sin escudo...")

        miembros_sin_escudo = []
        for member in message.guild.members:
            if member.bot:
                continue
            # Aquí va tu lógica para detectar sin escudo
            # miembros_sin_escudo.append(member.mention)

        if miembros_sin_escudo:
            lista = "\n".join(miembros_sin_escudo[:20])
            await canal.send(f"🚨 **ALERTA ROJA** 🚨\n{lista}")
        else:
            await canal.send("✅ **Todos con escudo activo**")
        return

    # ===== META EDITAR =====
    if peticion.lower().startswith("editar"):
        args = peticion.split(maxsplit=2)
        if len(args) < 3:
            await message.channel.send("❌ **Uso:** `meta editar <ID_mensaje> <nuevo_texto>`")
            return

        try:
            msg_id = int(args[1])
            nuevo_texto = args[2]
            msg_editar = await message.channel.fetch_message(msg_id)
            await msg_editar.edit(content=nuevo_texto)
            await message.channel.send("✅ **Mensaje editado**")
        except Exception as e:
            await message.channel.send(f"❌ **Error:** {e}")
        return

    # ===== META LIMPIA =====
    if peticion.lower().startswith("limpia"):
        args = peticion.split()
        cantidad = 10
        if len(args) > 1 and args[1].isdigit():
            cantidad = int(args[1])

        def es_bot_o_meta(m):
            return m.author == bot.user or m.content.lower().startswith("meta ")

        borrados = await message.channel.purge(limit=cantidad, check=es_bot_o_meta)
        await message.channel.send(f"🧹 **Limpié {len(borrados)} mensajes**", delete_after=5)
        return

    # ===== META PING =====
    if peticion.lower().startswith("ping"):
        latencia = round(bot.latency * 1000)
        await message.channel.send(f"🏓 **Pong!** `{latencia}ms`")
        return

    # ===== META AYUDA =====
    if peticion.lower().startswith("ayuda"):
        embed = discord.Embed(
            title="📋 Comandos Meta",
            description="Lista de comandos disponibles:",
            color=0x3498db
        )
        embed.add_field(name="🔴 meta activate", value="Código rojo TFT", inline=False)
        embed.add_field(name="✏️ meta editar <ID> <texto>", value="Edita mensajes del bot", inline=False)
        embed.add_field(name="🧹 meta limpia [cantidad]", value="Borra mensajes del bot", inline=False)
        embed.add_field(name="🏓 meta ping", value="Latencia del bot", inline=False)
        embed.add_field(name="🚨 meta alerta <texto>", value="Crea alerta bilingüe ES/EN", inline=False)
        embed.add_field(name="📅 meta evento <texto>", value="Crea evento bilingüe ES/EN", inline=False)
        embed.add_field(name="🌐 meta traducir <texto>", value="Traduce ES ↔ EN", inline=False)
        embed.add_field(name="🧮 meta calc tropas <tipo> <cant>", value="Calcula tiempo entrenamiento", inline=False)
        embed.add_field(name="⚡ meta calc speedup <tiempo>", value="Convierte a speedups", inline=False)
        embed.add_field(name="📊 meta kvkdiario", value="Procesa Excel KVK acumulado", inline=False)
        embed.set_footer(text=f"Solicitado por {autor_nombre}")
        await message.channel.send(embed=embed)
        return

    # ===== META ALERTA =====
    if peticion.lower().startswith("alerta"):
        texto = peticion[6:].strip()
        if not texto:
            await message.channel.send("❌ **Uso:** `meta alerta <mensaje>`")
            return

        class AlertaView(ui.View):
            def __init__(self):
                super().__init__(timeout=None)

            @ui.button(label="🇲🇽 Español", style=discord.ButtonStyle.primary)
            async def es_btn(self, interaction, button):
                await interaction.response.send_message(f"🚨 **ALERTA** 🚨\n{texto}", ephemeral=False)

            @ui.button(label="🇺🇸 English", style=discord.ButtonStyle.secondary)
            async def en_btn(self, interaction, button):
                # Aquí tu lógica de traducción
                await interaction.response.send_message(f"🚨 **ALERT** 🚨\n{texto}", ephemeral=False)

        embed = discord.Embed(
            title="🚨 Sistema de Alertas",
            description="Selecciona idioma para ver la alerta:",
            color=0xe74c3c
        )
        await message.channel.send(embed=embed, view=AlertaView())
        return

    # ===== META EVENTO =====
    if peticion.lower().startswith("evento"):
        texto = peticion[6:].strip()
        if not texto:
            await message.channel.send("❌ **Uso:** `meta evento <descripción>`")
            return

        class EventoView(ui.View):
            def __init__(self):
                super().__init__(timeout=None)

            @ui.button(label="🇲🇽 Español", style=discord.ButtonStyle.success)
            async def es_btn(self, interaction, button):
                await interaction.response.send_message(f"📅 **EVENTO** 📅\n{texto}", ephemeral=False)

            @ui.button(label="🇺🇸 English", style=discord.ButtonStyle.secondary)
            async def en_btn(self, interaction, button):
                await interaction.response.send_message(f"📅 **EVENT** 📅\n{texto}", ephemeral=False)

        embed = discord.Embed(
            title="📅 Sistema de Eventos",
            description="Selecciona idioma para ver el evento:",
            color=0x2ecc71
        )
        await message.channel.send(embed=embed, view=EventoView())
        return

    # ===== META TRADUCIR =====
    if peticion.lower().startswith("traducir"):
        texto = peticion[8:].strip()
        if not texto:
            await message.channel.send("❌ **Uso:** `meta traducir <texto>`")
            return

        # Detección simple de idioma
        es_espanol = any(palabra in texto.lower() for palabra in ["el", "la", "de", "que", "y", "en"])

        if es_espanol:
            traducido = f"[TRADUCIDO A EN] {texto}"
            await message.channel.send(f"🇲🇽 ➡️ 🇺🇸\n**Original:** {texto}\n**Traducido:** {traducido}")
        else:
            traducido = f"[TRADUCIDO A ES] {texto}"
            await message.channel.send(f"🇺🇸 ➡️ 🇲🇽\n**Original:** {texto}\n**Traducido:** {traducido}")
        return

    # ===== META CALC TROPAS =====
    if peticion.lower().startswith("calc tropas"):
        args = peticion.split()
        if len(args) < 4:
            await message.channel.send("❌ **Uso:** `meta calc tropas <T1-T5> <cantidad>`")
            return

        tipo = args[2].upper()
        try:
            cantidad = int(args[3])
            tiempos = {"T1": 10, "T2": 20, "T3": 30, "T4": 45, "T5": 60}
            if tipo not in tiempos:
                await message.channel.send("❌ **Tipo inválido.** Usa T1, T2, T3, T4 o T5")
                return

            segundos_totales = tiempos[tipo] * cantidad
            tiempo_formateado = format_tiempo(segundos_totales)
            await message.channel.send(f"⚔️ **{cantidad:,} {tipo}** = `{tiempo_formateado}` de entrenamiento")
        except:
            await message.channel.send("❌ **Cantidad inválida**")
        return

    # ===== META CALC SPEEDUP =====
    if peticion.lower().startswith("calc speedup"):
        args = peticion.split(maxsplit=2)
        if len(args) < 3:
            await message.channel.send("❌ **Uso:** `meta calc speedup <1d 2h 30m>`")
            return

        tiempo_str = args[2]
        # Parse simple: 1d 2h 30m 45s
        segundos = 0
        for parte in tiempo_str.split():
            if parte.endswith('d'): segundos += int(parte[:-1]) * 86400
            elif parte.endswith('h'): segundos += int(parte[:-1]) * 3600
            elif parte.endswith('m'): segundos += int(parte[:-1]) * 60
            elif parte.endswith('s'): segundos += int(parte[:-1])

        # Speedups comunes
        s_1m = segundos // 60
        s_5m = segundos // 300
        s_15m = segundos // 900
        s_60m = segundos // 3600

        embed = discord.Embed(title="⚡ Conversión a Speedups", color=0xf39c12)
        embed.add_field(name="1 minuto", value=f"`{s_1m:,}`", inline=True)
        embed.add_field(name="5 minutos", value=f"`{s_5m:,}`", inline=True)
        embed.add_field(name="15 minutos", value=f"`{s_15m:,}`", inline=True)
        embed.add_field(name="60 minutos", value=f"`{s_60m:,}`", inline=True)
        embed.set_footer(text=f"Total: {format_tiempo(segundos)}")
        await message.channel.send(embed=embed)
        return

    # ===== META KVKDIARIO ===== NUEVO
    if peticion.lower().startswith("kvkdiario"):
        if not message.attachments:
            await message.channel.send("❌ **Sube mínimo 2 archivos Excel del KVK** junto con el comando `meta kvkdiario`")
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
