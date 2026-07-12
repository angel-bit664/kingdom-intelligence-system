import discord
import os
import asyncio
from deep_translator import GoogleTranslator
from collections import defaultdict
import re
import time
from dotenv import load_dotenv

load_dotenv()

# ===== CONFIG =====
TOKEN = os.getenv("DISCORD_TOKEN")
ID_CANAL_ANUNCIOS = 1358237524249542751 # Para meta alerta y meta evento
ID_CANAL_ACTIVATE = 1358237524799131662 # Para meta activate y meta cumpleaños
# ==================

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

procesando_activate = set() # CANDADO ANTI-DUPLICADOS

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')
    print(f'✅ ID del bot: {client.user.id}')
    print(f'✅ Listo en {len(client.guilds)} servidores')
    print(f'✅ Canal anuncios: {ID_CANAL_ANUNCIOS}')
    print(f'✅ Canal activate/cumple: {ID_CANAL_ACTIVATE}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if not message.content.lower().startswith("meta "):
        return

    peticion = message.content[5:].strip().lower()
    autor_nombre = message.author.display_name

    # ===== META ACTIVATE - CON CANDADO ANTI-DUPLICADOS =====
    if peticion.startswith("activate"):
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
            await canal_activate.send(content=usuarios_texto, embed=embed)
            print(f'[ACTIVATE] Mensaje enviado exitosamente')
            await message.delete()

        finally:
            procesando_activate.discard(message.author.id)
            print(f'[ACTIVATE] Candado liberado para {autor_nombre}')
        return

    # ===== META CUMPLEAÑOS - ESTILO ACTIVATE BILINGÜE =====
    if peticion.startswith("cumpleaños") or peticion.startswith("cumpleanos"):
        if not message.mentions:
            await message.channel.send("❌ **Debes mencionar al usuario**\n\nEjemplo: `meta cumpleaños @Juan` o `meta cumpleaños @Juan que la pases bien`")
            return

        usuario_cumple = message.mentions[0]

        # Mensaje personalizado opcional - todo después de la mención
        partes = message.content.split()
        mensaje_es = ""
        if len(partes) > 3: # meta cumpleaños @usuario mensaje...
            mensaje_es = " ".join(partes[3:]).strip()

        if not mensaje_es:
            mensaje_es = "Que tengas un día increíble lleno de alegría. Te deseamos lo mejor hoy y siempre."

        try:
            mensaje_en = GoogleTranslator(source='es', target='en').translate(mensaje_es)
        except:
            mensaje_en = "Translation failed"

        descripcion = f"""🎉 *FELIZ CUMPLEAÑOS* 🎉
🎂 *CELEBRACIÓN ESPECIAL / SPECIAL CELEBRATION* 🎂

🎯 *CUMPLEAÑERO / BIRTHDAY:* *{usuario_cumple.mention}*

🎊 *ESTADO / STATUS:* DÍA DE FIESTA - MODO CELEBRACIÓN ACTIVADO
CELEBRATION MODE - PARTY TIME

🎁 *MENSAJE / MESSAGE:*
🇲🇽 {mensaje_es}
🇺🇸 {mensaje_en}

⚔️ *LA FAMILIA TFT TE CELEBRA*
TFT FAMILY CELEBRATES YOU

Felicitación enviada por: Todo el grupo de Oficiales

📍 QUE LA PASES INCREÍBLE / HAVE AN AMAZING TIME"""

        embed = discord.Embed(description=descripcion, color=0xFFD700) # Dorado
        canal_cumple = client.get_channel(ID_CANAL_ACTIVATE)
        if not canal_cumple:
            await message.channel.send(f"❌ **No encontré el canal**\nID configurado: {ID_CANAL_ACTIVATE}")
            return

        await canal_cumple.send(content=usuario_cumple.mention, embed=embed)
        await message.delete()
        return

    # ===== META ALERTA =====
    if peticion.startswith("alerta"):
        texto_es = message.content[11:].strip()
        if not texto_es:
            await message.channel.send("❌ **Uso:** `meta alerta <mensaje en español>`")
            return

        try:
            texto_en = GoogleTranslator(source='es', target='en').translate(texto_es)
        except:
            texto_en = "Translation failed"

        canal = client.get_channel(ID_CANAL_ANUNCIOS)
        embed = discord.Embed(title="🚨 ALERTA GENERAL BILINGÜE", color=0xF1C40F)
        embed.add_field(name="👨‍👩‍👧‍👦 Familia TFT / TFT Family 👨‍👩‍👧‍👦", value="📢 Necesitamos el apoyo de todos / We need everyone's support", inline=False)
        embed.add_field(name="🎯 Misión / Mission:", value=f"🇲🇽 {texto_es}\n🇺🇸 {texto_en}", inline=False)
        embed.add_field(name="🔥 Todos están invitados / Everyone is invited.", value="Si quieren pelear y defender / If you want to fight and defend", inline=False)
        embed.set_footer(text=f"Alerta enviada por: {autor_nombre}")
        await canal.send("@everyone", embed=embed)
        await message.channel.send("✅ **Alerta enviada**")
        return

    # ===== META EVENTO =====
    if peticion.startswith("evento"):
        texto_es = message.content[11:].strip()
        if not texto_es:
            await message.channel.send("❌ **Uso:** `meta evento <descripción en español>`")
            return

        try:
            texto_en = GoogleTranslator(source='es', target='en').translate(texto_es)
        except:
            texto_en = "Translation failed"

        canal = client.get_channel(ID_CANAL_ANUNCIOS)
        embed = discord.Embed(title="📅 EVENTO OFICIAL / OFFICIAL EVENT", color=0x3498DB)
        embed.add_field(name="🇲🇽 Español", value=texto_es, inline=False)
        embed.add_field(name="🇺🇸 English", value=texto_en, inline=False)
        embed.set_footer(text=f"Evento creado por: {autor_nombre}")
        msg = await canal.send("@everyone", embed=embed)
        await msg.add_reaction("👍")
        await message.channel.send("✅ **Evento publicado**")
        return

    # ===== META EDITAR =====
    if peticion.startswith("editar"):
        texto_nuevo = message.content[11:].strip()
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

    # ===== META LIMPIA - CON DEBUG Y VALIDACIÓN =====
    if peticion.startswith("limpia"):
        args = peticion.split()
        cantidad = 50 # default
        if len(args) > 1 and args[1].isdigit():
            cantidad = int(args[1])

        if cantidad > 100:
            await message.channel.send("❌ **Máximo 100 mensajes** por Discord API")
            return
        if cantidad < 1:
            await message.channel.send("❌ **Mínimo 1 mensaje**")
            return

        perms = message.channel.permissions_for(message.guild.me)
        if not perms.manage_messages:
            await message.channel.send("❌ **No tengo permiso 'Gestionar Mensajes'**\nVe a Server Settings → Roles → Bot → Activar 'Gestionar Mensajes'")
            return

        def es_bot_o_meta(m):
            return m.author == client.user or m.content.lower().startswith("meta ")

        try:
            borrados = await message.channel.purge(limit=cantidad, check=es_bot_o_meta)
            if len(borrados) == 0:
                await message.channel.send("⚠️ **No encontré mensajes del bot para borrar** en los últimos 100", delete_after=5)
            else:
                await message.channel.send(f"✨ **Limpié {len(borrados)} mensajes**", delete_after=5)
        except discord.Forbidden:
            await message.channel.send("❌ **Discord me bloqueó**. Revisa permisos del canal también")
        except discord.HTTPException:
            await message.channel.send("❌ **Error:** Solo puedo borrar mensajes de menos de 14 días")
        return

    # ===== META PING =====
    if peticion == "ping":
        latencia = round(client.latency * 1000)
        await message.channel.send(f"🟢 **Bot activo** | Latencia: `{latencia}ms`")
        return

    # ===== META AYUDA =====
    if peticion == "ayuda":
        embed = discord.Embed(title="📋 COMANDOS DISPONIBLES - META BOT", color=0x9B59B6)
        embed.add_field(name="🚨 meta activate @usuario", value="Código de emergencia individual", inline=False)
        embed.add_field(name="🎂 meta cumpleaños @usuario", value="Felicitación de cumpleaños bilingüe", inline=False)
        embed.add_field(name="📢 meta alerta <texto>", value="Alerta general bilingüe para @everyone", inline=False)
        embed.add_field(name="⚔️ meta evento <texto>", value="Evento oficial con reacción 👍", inline=False)
        embed.add_field(name="✏️ meta editar <texto>", value="Edita el último anuncio enviado", inline=False)
        embed.add_field(name="🧹 meta limpia [cantidad]", value="Borra mensajes del bot. Ej: `meta limpia 20`", inline=False)
        embed.add_field(name="🟢 meta ping", value="Verifica si el bot está activo", inline=False)
        embed.add_field(name="🌐 meta traducir <texto>", value="Traducción automática ES → EN", inline=False)
        embed.set_footer(text="META ESTÁ CONTIGO. UN REINO, UNA ALIANZA, UNA META.")
        await message.channel.send(embed=embed)
        return

    # ===== META TRADUCIR =====
    if peticion.startswith("traducir "):
        texto = message.content[14:].strip()
        if not texto:
            await message.channel.send("❌ **Uso:** `meta traducir hola mundo`")
            return

        try:
            traducido = GoogleTranslator(source='auto', target='en').translate(texto)
            await message.channel.send(f"🇲🇽→🇺🇸 **{traducido}**")
        except Exception as e:
            await message.channel.send(f"❌ Error al traducir: {e}")
        return

client.run(TOKEN)
