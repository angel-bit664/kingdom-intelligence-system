import discord
import os
import asyncio
from deep_translator import GoogleTranslator, MyMemoryTranslator
from dotenv import load_dotenv
from groq import Groq
from langdetect import detect
import json

load_dotenv()

# ===== CONFIG =====
TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

ID_CANAL_ANUNCIOS = 1358237524249542751
ID_CANAL_ACTIVATE = 1358237524799131662
# ==================

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
client = discord.Client(intents=intents)
procesando_activate = set()

BANDERAS = {
    '🇺🇸': 'en', '🇧🇷': 'pt', '🇫🇷': 'fr', '🇩🇪': 'de', '🇮🇹': 'it',
    '🇷🇺': 'ru', '🇯🇵': 'ja', '🇰🇷': 'ko', '🇨🇳': 'zh-CN', '🇸🇦': 'ar',
    '🇹🇷': 'tr', '🇮🇩': 'id', '🇹🇭': 'th', '🇻🇳': 'vi', '🇵🇱': 'pl'
}

NOMBRES_IDIOMAS = {
    'en': 'English', 'pt': 'Português', 'fr': 'Français', 'de': 'Deutsch',
    'it': 'Italiano', 'ru': 'Русский', 'ja': '日本語', 'ko': '한국어', 'zh-CN': '中文',
    'ar': 'العربية', 'tr': 'Türkçe', 'id': 'Indonesia', 'th': 'ไทย', 'vi': 'Tiếng Việt', 'pl': 'Polski'
}

mensajes_con_banderas = {} # {message_id: {"texto_es": "...", "tipo": "evento"}}

async def corregir_y_traducir_ia(texto_original):
    prompt = f"""Eres un asistente para un clan de Rise of Kingdoms.
1. Detecta el idioma del texto.
2. Corrige errores ortográficos y gramaticales del texto original.
3. Traduce el texto corregido a Español e Inglés.
4. Responde SOLO en JSON: {{"idioma_detectado": "es", "original_corregido": "texto", "es": "texto", "en": "texto"}}

Texto: "{texto_original}"
"""
    try:
        respuesta = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(respuesta.choices[0].message.content)
    except Exception as e:
        print(f"Error con Groq: {e}")
        es = texto_original
        en = GoogleTranslator(source='auto', target='en').translate(texto_original)
        return {"idioma_detectado": "es", "original_corregido": texto_original, "es": es, "en": en}

async def traducir_a_idioma(texto, idioma_destino):
    # Fix para chino: Google usa zh-CN no zh-cn
    if idioma_destino.lower() == 'zh-cn':
        idioma_destino = 'zh-CN'

    for intento in range(3): # 3 intentos con Google
        try:
            resultado = GoogleTranslator(source='auto', target=idioma_destino).translate(texto)
            # Validar que no regrese error de Google como texto
            if "Error 500" in resultado or "Server Error" in resultado or "Error 400" in resultado:
                raise Exception("Google devolvió error de servidor")
            return resultado

        except Exception as e:
            print(f"Intento {intento+1} Google falló para {idioma_destino}: {e}")
            if intento == 2: # Último intento, usar respaldo MyMemory
                try:
                    print(f"Usando MyMemory como respaldo para {idioma_destino}")
                    return MyMemoryTranslator(source='auto', target=idioma_destino).translate(texto)
                except Exception as e2:
                    print(f"MyMemory también falló: {e2}")
                    return f"No se pudo traducir a {idioma_destino}. Intenta más tarde."
            await asyncio.sleep(1.5) # Espera 1.5s entre intentos

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if not message.content.lower().startswith("meta "):
        return

    partes = message.content.split(' ', 2)
    if len(partes) < 2:
        return
    comando = partes[1].lower()
    args = partes[2] if len(partes) > 2 else ""
    autor = message.author

    # ===== META ACTIVATE ===== ES/EN AUTOMÁTICO
    if comando == "activate":
        if message.author.id in procesando_activate:
            return
        procesando_activate.add(message.author.id)
        try:
            usuarios_mencionados = []
            mensaje_custom = None
            if message.mentions:
                usuarios_mencionados = message.mentions
                texto_despues = message.content
                for user in message.mentions:
                    texto_despues = texto_despues.replace(f'<@{user.id}>', '').replace(f'<@!{user.id}>', '')
                texto_despues = texto_despues.replace('meta activate', '').strip()
                if texto_despues:
                    mensaje_custom = texto_despues
            else:
                msg = await message.channel.send("👤 Menciona a los usuarios a activar:")
                def check(m):
                    return m.author == message.author and m.channel == message.channel and len(m.mentions) > 0
                try:
                    respuesta = await client.wait_for('message', timeout=30.0, check=check)
                    usuarios_mencionados = respuesta.mentions
                    texto_despues = respuesta.content
                    for user in respuesta.mentions:
                        texto_despues = texto_despues.replace(f'<@{user.id}>', '').replace(f'<@!{user.id}>', '')
                    texto_despues = texto_despues.strip()
                    if texto_despues:
                        mensaje_custom = texto_despues
                    await respuesta.delete()
                    await msg.delete()
                except asyncio.TimeoutError:
                    await message.channel.send("⏰ Tiempo agotado. Usa `meta activate @usuario1 @usuario2 [mensaje]`")
                    await msg.delete()
                    return

            if not usuarios_mencionados:
                await message.channel.send("❌ **Debes mencionar al menos 1 usuario**\n\nEjemplo: `meta activate @Juan ve por escudo`")
                return

            usuarios_texto = ", ".join([u.mention for u in usuarios_mencionados])
            texto_plural = "ACTÍVENSE" if len(usuarios_mencionados) > 1 else "ACTÍVATE"
            texto_sin = "NO TIENEN" if len(usuarios_mencionados) > 1 else "NO TIENE"
            texto_escudo = "ESCUDOS" if len(usuarios_mencionados) > 1 else "ESCUDO"

            mensaje_extra = ""
            if mensaje_custom:
                datos = await corregir_y_traducir_ia(mensaje_custom)
                mensaje_extra = f"\n\n💬 *MENSAJE / MESSAGE:*\n🇲🇽 {datos['es']}\n🇺🇸 {datos['en']}"

            descripcion = f"""🚨 *CÓDIGO DE EMERGENCIA TFT* 🚨

⚠️ *ALERTA ROJA / RED ALERT* ⚠️

🎯 *OBJETIVO / TARGET:* *{usuarios_texto}*

❌ *ESTADO / STATUS:*
{texto_sin} {texto_escudo} ACTIVO - ZONA DE PELIGRO
NO ACTIVE SHIELD - DANGER ZONE

🛡️ *PROTOCOLO DE EMERGENCIA / EMERGENCY PROTOCOL:*
1. *{texto_plural} INMEDIATAMENTE / CONNECT NOW*
2. *ESCUDO 8H YA / 8h SHIELD NOW*
3. *TELEPORT DE EMERGENCIA / EMERGENCY TELEPORT*{mensaje_extra}

⚔️ *ALIANZA TFT EN ALERTA MÁXIMA*
TFT ALLIANCE ON MAXIMUM ALERT

Código emitido por: {autor.display_name}

⏰ TIEMPO ES CRÍTICO / TIME IS CRITICAL"""

            embed = discord.Embed(description=descripcion, color=0xFF0000)
            embed.set_footer(text=f"🚨 CÓDIGO ROJO TFT | {autor.display_name}")

            canal_activate = client.get_channel(ID_CANAL_ACTIVATE)
            if canal_activate:
                await canal_activate.send(content=usuarios_texto, embed=embed)
                await message.delete()
        finally:
            procesando_activate.discard(message.author.id)
        return

    # ===== META CUMPLEAÑOS ===== ES/EN AUTOMÁTICO
    if comando in ["cumpleaños", "cumpleanos"]:
        if not message.mentions:
            await message.channel.send("❌ **Debes mencionar al usuario**\n\nEjemplo: `meta cumpleaños @Juan que la pases chido`")
            return
        usuario_cumple = message.mentions[0]
        partes_msg = message.content.split()
        mensaje_es = ""
        if len(partes_msg) > 3:
            mensaje_es = " ".join(partes_msg[3:]).strip()
        if not mensaje_es:
            mensaje_es = "Que tengas un día increíble lleno de alegría. Te deseamos lo mejor hoy y siempre."

        datos = await corregir_y_traducir_ia(mensaje_es)

        descripcion = f"""🎉 *FELIZ CUMPLEAÑOS* 🎉

🎂 *CELEBRACIÓN ESPECIAL / SPECIAL CELEBRATION* 🎂

🎯 *CUMPLEAÑERO / BIRTHDAY:* *{usuario_cumple.mention}*

🎊 *ESTADO / STATUS:*
DÍA DE FIESTA - MODO CELEBRACIÓN ACTIVADO
CELEBRATION MODE - PARTY TIME

🎁 *MENSAJE / MESSAGE:*
🇲🇽 {datos['es']}
🇺🇸 {datos['en']}

⚔️ *LA FAMILIA TFT TE CELEBRA*
TFT FAMILY CELEBRATES YOU

Felicitación enviada por: Todo el grupo de Oficiales

📍 QUE LA PASES INCREÍBLE / HAVE AN AMAZING TIME"""

        embed = discord.Embed(description=descripcion, color=0xFFD700)
        canal_cumple = client.get_channel(ID_CANAL_ACTIVATE)
        if canal_cumple:
            await canal_cumple.send(content=usuario_cumple.mention, embed=embed)
            await message.delete()
        return

    # ===== META EVENTO / ALERTA ===== CON TU DISEÑO + BANDERAS POR DM
    if comando in ["evento", "alerta"]:
        if not args:
            await message.channel.send(f"❌ **Uso:** `meta {comando} <texto>`", delete_after=10)
            return

        await message.delete()
        procesando = await message.channel.send("⏳ Corrigiendo con IA...")

        datos = await corregir_y_traducir_ia(args)
        await procesando.delete()

        texto_corregido = datos['original_corregido']
        es = datos['es']
        en = datos['en']

        color = 0x3498DB if comando == "evento" else 0xF1C40F
        titulo = "📅 EVENTO OFICIAL / OFFICIAL EVENT" if comando == "evento" else "🚨 ALERTA GENERAL / GENERAL ALERT"

        embed = discord.Embed(title=titulo, color=color)
        embed.add_field(name="🇲🇽 Español", value=es, inline=False)
        embed.add_field(name="🇺🇸 English", value=en, inline=False)
        embed.set_footer(text=f"{comando.capitalize()} creado por: {autor.display_name}")

        canal = client.get_channel(ID_CANAL_ANUNCIOS)
        if not canal:
            canal = message.channel

        msg_publicado = await canal.send("@everyone", embed=embed)

        # Guardar para las reacciones
        mensajes_con_banderas[msg_publicado.id] = {"texto_es": es, "tipo": comando}

        # Agregar banderas abajo - AHORA CON INDONESIA 🇮🇩
        for bandera in ['🇧🇷', '🇫🇷', '🇩🇪', '🇮🇹', '🇷🇺', '🇯🇵', '🇰🇷', '🇨🇳', '🇮🇩']:
            await msg_publicado.add_reaction(bandera)

        if comando == "evento":
            await msg_publicado.add_reaction("👍")

        return

    # ===== RESTO DE COMANDOS =====
    if comando == "editar":
        if not args:
            await message.channel.send("❌ **Uso:** `meta editar <nuevo texto>`")
            return
        canal = client.get_channel(ID_CANAL_ANUNCIOS)
        if not canal:
            await message.channel.send("❌ **No encontré el canal de anuncios**")
            return
        async for msg in canal.history(limit=50):
            if msg.author == client.user and msg.embeds:
                try:
                    embed = msg.embeds[0]
                    if "EVENTO OFICIAL" in embed.title or "ALERTA GENERAL" in embed.title:
                        datos = await corregir_y_traducir_ia(args)
                        embed.set_field_at(0, name="🇲🇽 Español", value=datos['es'], inline=False)
                        embed.set_field_at(1, name="🇺🇸 English", value=datos['en'], inline=False)
                        mensajes_con_banderas[msg.id] = {"texto_es": datos['es'], "tipo": "editado"}
                        await msg.edit(embed=embed)
                        await message.channel.send("✅ **Anuncio editado**", delete_after=5)
                        return
                except:
                    pass
        await message.channel.send("❌ **No encontré anuncio para editar**")
        return

    if comando == "limpia":
        args_split = args.split()
        cantidad = 50
        if args_split and args_split[0].isdigit():
            cantidad = int(args_split[0])
        if cantidad > 100:
            await message.channel.send("❌ **Máximo 100 mensajes**")
            return
        if cantidad < 1:
            await message.channel.send("❌ **Mínimo 1 mensaje**")
            return
        perms = message.channel.permissions_for(message.guild.me)
        if not perms.manage_messages:
            await message.channel.send("❌ **No tengo permiso 'Gestionar Mensajes'**")
            return
        def es_bot_o_meta(m):
            return m.author == client.user or m.content.lower().startswith("meta ")
        try:
            borrados = await message.channel.purge(limit=cantidad, check=es_bot_o_meta)
            await message.channel.send(f"✨ **Limpié {len(borrados)} mensajes**", delete_after=5)
        except:
            await message.channel.send("❌ **Error al borrar**")
        return

    if comando == "ping":
        latencia = round(client.latency * 1000)
        await message.channel.send(f"🟢 **Bot activo** | Latencia: `{latencia}ms`")
        return

    if comando == "ayuda":
        embed = discord.Embed(title="📋 COMANDOS DISPONIBLES - META BOT", color=0x9B59B6)
        embed.add_field(name="🚨 meta activate @usuario [mensaje]", value="Código de emergencia ES/EN", inline=False)
        embed.add_field(name="🎂 meta cumpleaños @usuario [mensaje]", value="Felicitación ES/EN", inline=False)
        embed.add_field(name="📢 meta alerta <texto>", value="Alerta ES/EN + banderas para DM", inline=False)
        embed.add_field(name="⚔️ meta evento <texto>", value="Evento ES/EN + banderas para DM", inline=False)
        embed.add_field(name="✏️ meta editar <texto>", value="Edita el último anuncio", inline=False)
        embed.add_field(name="🧹 meta limpia [cantidad]", value="Borra mensajes del bot", inline=False)
        embed.add_field(name="🟢 meta ping", value="Verifica si el bot está activo", inline=False)
        embed.add_field(name="🌍 Banderas disponibles", value="🇧🇷 🇫🇷 🇩🇪 🇮🇹 🇷🇺 🇯🇵 🇰🇷 🇨🇳 🇮🇩\nReacciona para recibir traducción por DM", inline=False)
        embed.set_footer(text="META ESTÁ CONTIGO. UN REINO, UNA ALIANZA, UNA META.")
        await message.channel.send(embed=embed)
        return

@client.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    if reaction.message.id not in mensajes_con_banderas:
        return

    emoji = str(reaction.emoji)
    if emoji not in BANDERAS:
        return

    data = mensajes_con_banderas[reaction.message.id]
    idioma_destino = BANDERAS[emoji]
    texto_es = data['texto_es']

    try:
        await reaction.remove(user) # Quitar reacción para que pueda volver a pedirla
    except:
        pass

    # Traducir y mandar DM
    try:
        traduccion = await traducir_a_idioma(texto_es, idioma_destino)
        nombre_idioma = NOMBRES_IDIOMAS.get(idioma_destino, idioma_destino.upper())

        embed_dm = discord.Embed(
            title=f"{emoji} Traducción a {nombre_idioma}",
            color=0x00FF00
        )
        embed_dm.add_field(name="Texto original", value=f"```{texto_es}```", inline=False)
        embed_dm.add_field(name="Traducción", value=f"```{traduccion}```", inline=False)
        embed_dm.set_footer(text=f"Traducción del {data['tipo']} de TFT")

        await user.send(embed=embed_dm)

    except discord.Forbidden:
        try:
            await reaction.message.channel.send(f"{user.mention} **Activa tus DMs** para recibir traducciones.", delete_after=10)
        except:
            pass
    except Exception as e:
        print(f"Error en traducción por bandera: {e}")
        try:
            await user.send(f"❌ Error traduciendo. Intenta de nuevo.")
        except:
            pass

client.run(TOKEN)
