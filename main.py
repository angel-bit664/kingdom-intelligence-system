import discord
import os
import asyncio
from deep_translator import GoogleTranslator
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
client = discord.Client(intents=intents)
procesando_activate = set()

BANDERAS = {
    'es': '🇪🇸', 'en': '🇺🇸', 'pt': '🇧🇷', 'fr': '🇫🇷', 'de': '🇩🇪',
    'it': '🇮🇹', 'ru': '🇷🇺', 'ja': '🇯🇵', 'ko': '🇰🇷', 'zh-cn': '🇨🇳',
    'zh-tw': '🇹🇼', 'ar': '🇸🇦', 'tr': '🇹🇷', 'id': '🇮🇩', 'th': '🇹🇭',
    'vi': '🇻🇳', 'pl': '🇵🇱', 'nl': '🇳🇱', 'sv': '🇸🇪', 'da': '🇩🇰',
    'no': '🇳🇴', 'fi': '🇫🇮', 'cs': '🇨🇿', 'ro': '🇷🇴', 'hu': '🇭🇺',
    'el': '🇬🇷', 'he': '🇮🇱', 'hi': '🇮🇳', 'bn': '🇧🇩', 'ur': '🇵🇰'
}

async def corregir_y_traducir_ia(texto_original):
    prompt = f"""Eres un asistente para un clan de call of dragons. Tu tarea es:
1. Detectar el idioma del texto.
2. Corregir errores ortográficos y gramaticales del texto original.
3. Traducir el texto corregido a Español e Inglés.
4. Responder SOLO en formato JSON con las claves: "idioma_detectado", "original_corregido", "es", "en".

Texto: "{texto_original}"
"""
    try:
        respuesta = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        resultado = json.loads(respuesta.choices[0].message.content)
        return resultado
    except Exception as e:
        print(f"Error con Groq: {e}")
        try:
            idioma = detect(texto_original)
        except:
            idioma = 'es'
        es = texto_original if idioma == 'es' else GoogleTranslator(source='auto', target='es').translate(texto_original)
        en = GoogleTranslator(source='auto', target='en').translate(texto_original)
        return {
            "idioma_detectado": idioma,
            "original_corregido": texto_original,
            "es": es,
            "en": en
        }

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')
    print(f'✅ ID del bot: {client.user.id}')
    print(f'✅ Listo en {len(client.guilds)} servidores')
    print(f'✅ Canal anuncios: {ID_CANAL_ANUNCIOS}')
    print(f'✅ Canal general: {ID_CANAL_ACTIVATE}')

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
    autor_nombre = message.author.display_name

    # ===== META ACTIVATE ===== AHORA CON IA EN MENSAJE CUSTOM
    if comando == "activate":
        if message.author.id in procesando_activate:
            return
        procesando_activate.add(message.author.id)
        print(f'[ACTIVATE] Candado puesto para {autor_nombre}')
        try:
            usuarios_mencionados = []
            mensaje_custom = None

            if message.mentions:
                usuarios_mencionados = message.mentions
                # Extraer texto después de las menciones
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
                    # Extraer mensaje custom si hay
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

            # Si hay mensaje custom, lo pasamos por IA sin spam
            mensaje_extra_es = ""
            mensaje_extra_en = ""
            if mensaje_custom:
                datos = await corregir_y_traducir_ia(mensaje_custom)
                mensaje_extra_es = f"\n\n💬 *MENSAJE EXTRA / EXTRA MESSAGE:*\n🇲🇽 {datos['es']}\n🇺🇸 {datos['en']}"

            descripcion = f"""🚨 *CÓDIGO DE EMERGENCIA TFT* 🚨

⚠️ *ALERTA ROJA / RED ALERT* ⚠️

🎯 *OBJETIVO / TARGET:* *{usuarios_texto}*

❌ *ESTADO / STATUS:*
{texto_sin} {texto_escudo} ACTIVO - ZONA DE PELIGRO
NO ACTIVE SHIELD - DANGER ZONE

🛡️ *PROTOCOLO DE EMERGENCIA / EMERGENCY PROTOCOL:*
1. *{texto_plural} INMEDIATAMENTE / CONNECT NOW*
2. *ESCUDO 8H YA / 8h SHIELD NOW*
3. *TELEPORT DE EMERGENCIA / EMERGENCY TELEPORT*{mensaje_extra_es}

⚔️ *ALIANZA TFT EN ALERTA MÁXIMA*
TFT ALLIANCE ON MAXIMUM ALERT

Código emitido por: {autor_nombre}

⏰ TIEMPO ES CRÍTICO / TIME IS CRITICAL"""

            embed = discord.Embed(description=descripcion, color=0xFF0000)
            embed.set_footer(text=f"🚨 CÓDIGO ROJO TFT | {autor_nombre}")

            canal_activate = client.get_channel(ID_CANAL_ACTIVATE)
            if not canal_activate:
                await message.channel.send(f"❌ **No encontré el canal general**\nID: `{ID_CANAL_ACTIVATE}`\n¿El bot tiene acceso a ese canal?")
                return

            try:
                await canal_activate.send(content=usuarios_texto, embed=embed)
                await message.delete()
            except discord.Forbidden:
                await message.channel.send("❌ **No tengo permisos** para escribir en el canal general")
        finally:
            procesando_activate.discard(message.author.id)
            print(f'[ACTIVATE] Candado liberado para {autor_nombre}')
        return

    # ===== META CUMPLEAÑOS ===== AHORA CON IA
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

        # Pasar por IA sin spam
        datos = await corregir_y_traducir_ia(mensaje_es)
        mensaje_es_corregido = datos['es']
        mensaje_en = datos['en']

        descripcion = f"""🎉 *FELIZ CUMPLEAÑOS* 🎉

🎂 *CELEBRACIÓN ESPECIAL / SPECIAL CELEBRATION* 🎂

🎯 *CUMPLEAÑERO / BIRTHDAY:* *{usuario_cumple.mention}*

🎊 *ESTADO / STATUS:*
DÍA DE FIESTA - MODO CELEBRACIÓN ACTIVADO
CELEBRATION MODE - PARTY TIME

🎁 *MENSAJE / MESSAGE:*
🇲🇽 {mensaje_es_corregido}
🇺🇸 {mensaje_en}

⚔️ *LA FAMILIA TFT TE CELEBRA*
TFT FAMILY CELEBRATES YOU

Felicitación enviada por: Todo el grupo de Oficiales

📍 QUE LA PASES INCREÍBLE / HAVE AN AMAZING TIME"""

        embed = discord.Embed(description=descripcion, color=0xFFD700)
        canal_cumple = client.get_channel(ID_CANAL_ACTIVATE)

        if not canal_cumple:
            await message.channel.send(f"❌ **No encontré el canal general**\nID: `{ID_CANAL_ACTIVATE}`")
            return

        try:
            await canal_cumple.send(content=usuario_cumple.mention, embed=embed)
            await message.delete()
        except discord.Forbidden:
            await message.channel.send("❌ **No tengo permisos** en el canal general")
        return

    # ===== META ALERTA ===== CON IA
    if comando == "alerta":
        if not args:
            await message.channel.send("❌ **Uso:** `meta alerta <mensaje>`")
            return

        procesando = await message.channel.send("⏳ Corrigiendo y traduciendo con IA...")
        datos = await corregir_y_traducir_ia(args)
        await procesando.delete()

        idioma = datos['idioma_detectado']
        bandera = BANDERAS.get(idioma, '🏳️')
        texto_corregido = datos['original_corregido']
        es = datos['es']
        en = datos['en']

        canal = client.get_channel(ID_CANAL_ANUNCIOS)
        if not canal:
            await message.channel.send(f"❌ **No encontré el canal de anuncios**\nID: `{ID_CANAL_ANUNCIOS}`")
            return

        embed = discord.Embed(title=f"🚨 ALERTA GENERAL - {bandera} {idioma.upper()}", color=0xF1C40F)

        if texto_corregido.lower()!= args.lower():
            embed.add_field(name="✍️ Original Corregido", value=f"```{texto_corregido}```", inline=False)

        embed.add_field(name="🇲🇽 Español", value=es, inline=False)
        embed.add_field(name="🇺🇸 English", value=en, inline=False)
        embed.set_footer(text=f"Alerta enviada por: {autor_nombre}")

        try:
            await canal.send("@everyone", embed=embed)
            await message.channel.send("✅ **Alerta enviada con IA**")
        except discord.Forbidden:
            await message.channel.send("❌ **No tengo permisos** para escribir o mencionar @everyone en anuncios")
        return

    # ===== META EVENTO ===== CON IA
    if comando == "evento":
        if not args:
            await message.channel.send("❌ **Uso:** `meta evento <descripción>`")
            return

        procesando = await message.channel.send("⏳ Corrigiendo y traduciendo con IA...")
        datos = await corregir_y_traducir_ia(args)
        await procesando.delete()

        idioma = datos['idioma_detectado']
        bandera = BANDERAS.get(idioma, '🏳️')
        texto_corregido = datos['original_corregido']
        es = datos['es']
        en = datos['en']

        canal = client.get_channel(ID_CANAL_ANUNCIOS)
        if not canal:
            await message.channel.send(f"❌ **No encontré el canal de anuncios**\nID: `{ID_CANAL_ANUNCIOS}`")
            return

        embed = discord.Embed(title=f"📅 EVENTO OFICIAL - {bandera} {idioma.upper()}", color=0x3498DB)

        if texto_corregido.lower()!= args.lower():
            embed.add_field(name="✍️ Original Corregido", value=f"```{texto_corregido}```", inline=False)

        embed.add_field(name="🇲🇽 Español", value=es, inline=False)
        embed.add_field(name="🇺🇸 English", value=en, inline=False)
        embed.set_footer(text=f"Evento creado por: {autor_nombre}")

        try:
            msg = await canal.send("@everyone", embed=embed)
            await msg.add_reaction("👍")
            await message.channel.send("✅ **Evento publicado con IA**")
        except discord.Forbidden:
            await message.channel.send("❌ **No tengo permisos** en el canal de anuncios")
        return

    # ===== RESTO DE COMANDOS: TU CÓDIGO ORIGINAL =====
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
                    try:
                        texto_en = GoogleTranslator(source='es', target='en').translate(args)
                    except:
                        texto_en = "Translation failed"
                    embed.set_field_at(1, name="🎯 Misión / Mission:", value=f"🇲🇽 {args}\n🇺🇸 {texto_en}", inline=False)
                    await msg.edit(embed=embed)
                    await message.channel.send("✅ **Último anuncio editado**")
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
            await message.channel.send("❌ **Máximo 100 mensajes** por Discord API")
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
            if len(borrados) == 0:
                await message.channel.send("⚠️ **No encontré mensajes del bot para borrar**", delete_after=5)
            else:
                await message.channel.send(f"✨ **Limpié {len(borrados)} mensajes**", delete_after=5)
        except discord.Forbidden:
            await message.channel.send("❌ **Discord me bloqueó**. Revisa permisos del canal")
        except discord.HTTPException:
            await message.channel.send("❌ **Error:** Solo puedo borrar mensajes de menos de 14 días")
        return

    if comando == "ping":
        latencia = round(client.latency * 1000)
        await message.channel.send(f"🟢 **Bot activo** | Latencia: `{latencia}ms`")
        return

    if comando == "ayuda":
        embed = discord.Embed(title="📋 COMANDOS DISPONIBLES - META BOT", color=0x9B59B6)
        embed.add_field(name="🚨 meta activate @usuario [mensaje]", value="Código de emergencia con IA opcional", inline=False)
        embed.add_field(name="🎂 meta cumpleaños @usuario [mensaje]", value="Felicitación con IA + corrección", inline=False)
        embed.add_field(name="📢 meta alerta <texto>", value="Alerta general con IA + corrección", inline=False)
        embed.add_field(name="⚔️ meta evento <texto>", value="Evento con IA + corrección + reacción 👍", inline=False)
        embed.add_field(name="✏️ meta editar <texto>", value="Edita el último anuncio enviado", inline=False)
        embed.add_field(name="🧹 meta limpia [cantidad]", value="Borra mensajes del bot. Ej: `meta limpia 20`", inline=False)
        embed.add_field(name="🟢 meta ping", value="Verifica si el bot está activo", inline=False)
        embed.add_field(name="🌐 meta traducir <texto>", value="Traducción automática ES → EN", inline=False)
        embed.set_footer(text="META ESTÁ CONTIGO. UN REINO, UNA ALIANZA, UNA META.")
        await message.channel.send(embed=embed)
        return

    if comando == "traducir":
        if not args:
            await message.channel.send("❌ **Uso:** `meta traducir hola mundo`")
            return
        try:
            traducido = GoogleTranslator(source='auto', target='en').translate(args)
            await message.channel.send(f"🇲🇽→🇺🇸 **{traducido}**")
        except Exception as e:
            await message.channel.send(f"❌ Error al traducir: {e}")
        return

client.run(TOKEN)
