import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import discord
import asyncio
from deep_translator import GoogleTranslator, MyMemoryTranslator
from dotenv import load_dotenv
from groq import Groq
import json
load_dotenv()

##====== CONFIG ======
TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not TOKEN or not GROQ_API_KEY:
    print("❌ FALTA TOKEN o GROQ_API_KEY en Environment de Render")

groq_client = Groq(api_key=GROQ_API_KEY)
ID_CANAL_ANUNCIOS = 1358237524249542751
ID_CANAL_ACTIVATE = 1358237524799131662
ID_CANAL_BUFF = 1404721557279871056
##==================

# ========== WEB SERVER PARA RENDER - NO TOCAR ==========
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Kingdom bot is alive!')

    def log_message(self, format, *args):
        return

def start_web_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), PingHandler)
    print(f"Dummy web server running on port {port}")
    server.serve_forever()

threading.Thread(target=start_web_server, daemon=True).start()
# =======================================================

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
client = discord.Client(intents=intents)
procesando_activate = set()

BANDERAS = {
    '🇺🇸': 'en', '🇧🇷': 'pt', '🇫🇷': 'fr', '🇩🇪': 'de', '🇮🇹': 'it',
    '🇷🇺': 'ru', '🇯🇵': 'ja', '🇰🇷': 'ko', '🇨🇳': 'zh-CN', '🇸🇦': 'ar',
    '🇹🇷': 'tr', '🇮🇩': 'id', '🇹🇭': 'th', '🇻🇳': 'vi', '🇵🇱': 'pl',
    '🏳️‍🌈': 'lgbt' # Bandera especial
}

NOMBRES_IDIOMAS = {
    'en': 'English', 'pt': 'Português', 'fr': 'Français', 'de': 'Deutsch',
    'it': 'Italiano', 'ru': 'Русский', 'ja': '日本語', 'ko': '한국어',
    'zh-CN': '中文', 'ar': 'العربية', 'tr': 'Türkçe', 'id': 'Indonesia',
    'th': 'ไทย', 'vi': 'Tiếng Việt', 'pl': 'Polski'
}

mensajes_con_banderas = {}
mensajes_diplomacia = {}
flag_mode_channels = set()

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
        try:
            en = GoogleTranslator(source='auto', target='en').translate(texto_original)
        except:
            en = texto_original
        return {"idioma_detectado": "es", "original_corregido": texto_original, "es": es, "en": en}

async def traducir_a_idioma(texto, idioma_destino):
    if idioma_destino.lower() == 'zh-cn':
        idioma_destino = 'zh-CN'
    for intento in range(3):
        try:
            resultado = GoogleTranslator(source='auto', target=idioma_destino).translate(texto)
            if "Error 500" in resultado or "Server Error" in resultado or "Error 400" in resultado:
                raise Exception("Google devolvió error")
            return resultado
        except Exception as e:
            print(f"Intento {intento+1} Google falló para {idioma_destino}: {e}")
            if intento == 2:
                try:
                    return MyMemoryTranslator(source='auto', target=idioma_destino).translate(texto)
                except Exception as e2:
                    print(f"MyMemory también falló: {e2}")
                    return f"No se pudo traducir a {idioma_destino}."
        await asyncio.sleep(1.5)

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if not message.content.lower().startswith("meta "):
        if message.channel.id in flag_mode_channels:
            if len(message.content.strip()) < 2:
                return
            mensajes_diplomacia[message.id] = message.content
            # YA NO AGREGA EMOJIS AUTOMÁTICAMENTE - Solo escucha reacciones
            return

    partes = message.content.split(' ', 2)
    if len(partes) < 2:
        return

    comando = partes[1].lower()
    args = partes[2] if len(partes) > 2 else ""
    autor = message.author

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
                texto_despues = texto_despues.replace('meta activate', '').replace('Meta activate', '').strip()
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
                    if texto_despues.strip():
                        mensaje_custom = texto_despues.strip()
                    await respuesta.delete()
                    await msg.delete()
                except asyncio.TimeoutError:
                    await message.channel.send("⏰ Tiempo agotado. Usa meta activate @usuario1 @usuario2 [mensaje]")
                    await msg.delete()
                    return

            if not usuarios_mencionados:
                await message.channel.send("❌ Debes mencionar al menos 1 usuario")
                return

            usuarios_texto = ", ".join([u.mention for u in usuarios_mencionados])
            texto_plural = "ACTÍVENSE" if len(usuarios_mencionados) > 1 else "ACTÍVATE"
            texto_sin = "NO TIENEN" if len(usuarios_mencionados) > 1 else "NO TIENE"
            texto_escudo = "ESCUDOS" if len(usuarios_mencionados) > 1 else "ESCUDO"
            mensaje_extra = ""
            if mensaje_custom:
                datos = await corregir_y_traducir_ia(mensaje_custom)
                mensaje_extra = f"\n\n💬 MENSAJE / MESSAGE:\n🇲🇽 {datos['es']}\n🇺🇸 {datos['en']}"

            descripcion = f"""🚨 CÓDIGO DE EMERGENCIA TFT 🚨
⚠️ ALERTA ROJA / RED ALERT ⚠️
🎯 OBJETIVO / TARGET: {usuarios_texto}
❌ ESTADO / STATUS: {texto_sin} {texto_escudo} ACTIVO - ZONA DE PELIGRO
🛡️ PROTOCOLO DE EMERGENCIA / EMERGENCY PROTOCOL:
1. {texto_plural} INMEDIATAMENTE / CONNECT NOW
2. ESCUDO 8H YA / 8h SHIELD NOW
3. TELEPORT DE EMERGENCIA / EMERGENCY TELEPORT{mensaje_extra}
⚔️ ALIANZA TFT EN ALERTA MÁXIMA
Código emitido por: {autor.display_name}"""
            embed = discord.Embed(description=descripcion, color=0xFF0000)
            embed.set_footer(text=f"🚨 CÓDIGO ROJO TFT | {autor.display_name}")
            canal_activate = client.get_channel(ID_CANAL_ACTIVATE)
            if canal_activate:
                await canal_activate.send(content=usuarios_texto, embed=embed)
            await message.delete()
        finally:
            procesando_activate.discard(message.author.id)
        return

    if comando in ["cumpleaños", "cumpleanos"]:
        if not message.mentions:
            await message.channel.send("❌ Debes mencionar al usuario")
            return
        usuario_cumple = message.mentions[0]
        partes_msg = message.content.split()
        mensaje_es = " ".join(partes_msg[3:]).strip() if len(partes_msg) > 3 else "Que tengas un día increíble lleno de alegría."
        datos = await corregir_y_traducir_ia(mensaje_es)
        descripcion = f"""🎉 FELIZ CUMPLEAÑOS 🎉
🎯 CUMPLEAÑERO / BIRTHDAY: {usuario_cumple.mention}
🎁 MENSAJE / MESSAGE:
🇲🇽 {datos['es']}
🇺🇸 {datos['en']}
⚔️ LA FAMILIA TFT TE CELEBRA"""
        embed = discord.Embed(description=descripcion, color=0xFFD700)
        canal_cumple = client.get_channel(ID_CANAL_ACTIVATE)
        if canal_cumple:
            await canal_cumple.send(content=usuario_cumple.mention, embed=embed)
        await message.delete()
        return

    if comando in ["evento", "alerta"]:
        if not args:
            await message.channel.send(f"❌ Uso: meta {comando} <texto>", delete_after=10)
            return
        await message.delete()
        procesando = await message.channel.send("⏳ Corrigiendo con IA...")
        datos = await corregir_y_traducir_ia(args)
        await procesando.delete()
        es, en = datos['es'], datos['en']
        color = 0x3498DB if comando == "evento" else 0xF1C40F
        titulo = "📅 EVENTO OFICIAL / OFFICIAL EVENT" if comando == "evento" else "🚨 ALERTA GENERAL / GENERAL ALERT"
        embed = discord.Embed(title=titulo, color=color)
        embed.add_field(name="🇲🇽 Español", value=es, inline=False)
        embed.add_field(name="🇺🇸 English", value=en, inline=False)
        embed.set_footer(text=f"{comando.capitalize()} creado por: {autor.display_name}")
        canal = client.get_channel(ID_CANAL_ANUNCIOS) or message.channel
        msg_publicado = await canal.send("@everyone", embed=embed)
        mensajes_con_banderas[msg_publicado.id] = {"texto_es": es, "tipo": comando}
        for bandera in ['🇧🇷', '🇫🇷', '🇩🇪', '🇮🇹', '🇷🇺', '🇯🇵', '🇰🇷', '🇨🇳', '🇮🇩']:
            try:
                await msg_publicado.add_reaction(bandera)
            except:
                pass
        if comando == "evento":
            try:
                await msg_publicado.add_reaction("👍")
            except:
                pass
        return

    if comando in ["buffo", "bufo", "buff"]:
        if not args:
            await message.channel.send("❌ Uso: meta buffo <texto>", delete_after=10)
            return
        await message.delete()
        procesando = await message.channel.send("⏳ Procesando bufo...")
        datos = await corregir_y_traducir_ia(args)
        await procesando.delete()
        es, en = datos['es'], datos['en']
        embed = discord.Embed(title="🛎️ BUFO DEL REINO ACTIVADO / KINGDOM BUFF ACTIVATED", color=0x9B59B6)
        embed.add_field(name="🇲🇽 Español", value=f"✅ {es}", inline=False)
        embed.add_field(name="🇺🇸 English", value=f"✅ {en}", inline=False)
        embed.add_field(name="⚠️ Nota / Note", value="Los bufos podrán ser modificados en caso de necesidad.", inline=False)
        embed.set_footer(text=f"Bufo activado por: {autor.display_name}")
        canal_buff = client.get_channel(ID_CANAL_BUFF) or message.channel
        msg_publicado = await canal_buff.send("@everyone", embed=embed)
        for bandera in ['🇧🇷', '🇫🇷', '🇩🇪', '🇮🇹', '🇷🇺', '🇯🇵', '🇰🇷', '🇨🇳', '🇮🇩']:
            try:
                await msg_publicado.add_reaction(bandera)
            except:
                pass
        mensajes_con_banderas[msg_publicado.id] = {"texto_es": es, "tipo": "buffo"}
        return

    if comando == "editar":
        if not args:
            return
        canal = client.get_channel(ID_CANAL_ANUNCIOS)
        if not canal:
            return
        async for msg in canal.history(limit=50):
            if msg.author == client.user and msg.embeds:
                try:
                    embed = msg.embeds[0]
                    if "EVENTO OFICIAL" in str(embed.title) or "ALERTA GENERAL" in str(embed.title):
                        datos = await corregir_y_traducir_ia(args)
                        embed.set_field_at(0, name="🇲🇽 Español", value=datos['es'], inline=False)
                        embed.set_field_at(1, name="🇺🇸 English", value=datos['en'], inline=False)
                        await msg.edit(embed=embed)
                        await message.channel.send("✅ Anuncio editado", delete_after=5)
                        return
                except:
                    pass
        return

    if comando == "limpia":
        args_split = args.split()
        cantidad = int(args_split[0]) if args_split and args_split[0].isdigit() else 50
        cantidad = min(max(cantidad, 1), 100)
        def es_bot_o_meta(m):
            return m.author == client.user or m.content.lower().startswith("meta ")
        try:
            borrados = await message.channel.purge(limit=cantidad, check=es_bot_o_meta)
            await message.channel.send(f"✨ Limpié {len(borrados)} mensajes", delete_after=5)
        except:
            pass
        return

    if comando == "ping":
        latencia = round(client.latency * 1000)
        await message.channel.send(f"🟢 Bot activo | Latencia: {latencia}ms")
        return

    if comando == "autotraducir":
        if args.lower() == "on":
            flag_mode_channels.add(message.channel.id)
            await message.channel.send(embed=discord.Embed(
                title="✅ Modo autotraducir activado",
                description="Reacciona con cualquier bandera para traducir\n🇺🇸🇪🇸 = 20s en canal\nOtros idiomas = DM\n🏳️‍🌈 = Declaración LGBT",
                color=0x00FF00
            ))
        elif args.lower() == "off":
            flag_mode_channels.discard(message.channel.id)
            await message.channel.send(embed=discord.Embed(title="❌ Modo desactivado", color=0xFF0000))
        return

    if comando == "ayuda":
        embed = discord.Embed(title="📋 COMANDOS DISPONIBLES - META BOT", color=0x9B59B6)
        embed.add_field(name="🚨 meta activate @usuario [mensaje]", value="Código de emergencia ES/EN", inline=False)
        embed.add_field(name="🎂 meta cumpleaños @usuario [mensaje]", value="Felicitación ES/EN", inline=False)
        embed.add_field(name="📢 meta alerta <texto>", value="Alerta ES/EN + banderas para DM", inline=False)
        embed.add_field(name="⚔️ meta evento <texto>", value="Evento ES/EN + banderas para DM", inline=False)
        embed.add_field(name="🛎️ meta buffo <texto>", value="Bufo del reino ES/EN + @everyone + banderas", inline=False)
        embed.add_field(name="✏️ meta editar <texto>", value="Edita el último anuncio", inline=False)
        embed.add_field(name="🧹 meta limpia [cantidad]", value="Borra mensajes del bot", inline=False)
        embed.add_field(name="🟢 meta ping", value="Verifica si el bot está activo", inline=False)
        embed.add_field(name="🌐 meta autotraducir on/off", value="Modo banderas: ES/EN canal 20s, otros DM", inline=False)
        embed.add_field(name="🌍 Banderas disponibles", value="🇧🇷🇫🇷🇩🇪🇮🇹🇷🇺🇯🇵🇰🇷🇨🇳🇮🇩🇸🇦🇹🇷🇹🇭🇻🇳🇵🇱\n🏳️‍🌈 Declaración LGBT pública", inline=False)
        embed.set_footer(text="META ESTÁ CONTIGO. UN REINO, UNA ALIANZA, UNA META.")
        await message.channel.send(embed=embed)
        return

@client.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    # MODO AUTOTRADUCIR - Diplomacia
    if reaction.message.id in mensajes_diplomacia:
        emoji = str(reaction.emoji)

        # BANDERA LGBT - Anuncio público
        if emoji == '🏳️‍🌈':
            embed = discord.Embed(
                title="🏳️‍🌈 ORGULLO TFT 🏳️‍🌈",
                description=f"{user.mention} ha declarado con orgullo que es parte de la comunidad LGBT+.\n\n**{user.display_name} está orgulloso de ser gay** ❤️🧡💛💚💙💜\n\nEn TFT celebramos la diversidad. UN REINO, UNA ALIANZA, UNA META.",
                color=0xFF69B4
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text="El amor es amor - Love is love")
            await reaction.message.channel.send("@everyone", embed=embed)
            try:
                await reaction.remove(user)
            except:
                pass
            return

        # Solo procesar banderas de idiomas
        if emoji not in BANDERAS or BANDERAS[emoji] == 'lgbt':
            return

        texto_original = mensajes_diplomacia[reaction.message.id]
        idioma_destino = BANDERAS[emoji]

        try:
            await reaction.remove(user)
        except:
            pass

        try:
            traduccion = await traducir_a_idioma(texto_original, idioma_destino)

            # ES/EN = Mensaje en canal por 20 segundos
            if idioma_destino in ['es', 'en']:
                flag_emoji = '🇪🇸' if idioma_destino == 'es' else '🇺🇸'
                embed = discord.Embed(description=f"{flag_emoji} {traduccion}", color=0x00B0F4)
                await reaction.message.channel.send(embed=embed, delete_after=20)
            else:
                # Otros idiomas = DM
                nombre_idioma = NOMBRES_IDIOMAS.get(idioma_destino, idioma_destino)
                embed_dm = discord.Embed(title=f"{emoji} Traducción a {nombre_idioma}", color=0x00FF00)
                embed_dm.add_field(name="Original", value=texto_original, inline=False)
                embed_dm.add_field(name="Traducción", value=traduccion, inline=False)
                await user.send(embed=embed_dm)
        except:
            pass
        return

    # BANDERAS EN ANUNCIOS/EVENTOS - Solo DM
    if reaction.message.id not in mensajes_con_banderas:
        return

    emoji = str(reaction.emoji)
    if emoji not in BANDERAS or BANDERAS[emoji] == 'lgbt':
        return

    data = mensajes_con_banderas[reaction.message.id]
    try:
        await reaction.remove(user)
    except:
        pass

    try:
        traduccion = await traducir_a_idioma(data['texto_es'], BANDERAS[emoji])
        nombre_idioma = NOMBRES_IDIOMAS.get(BANDERAS[emoji], BANDERAS[emoji])
        embed_dm = discord.Embed(title=f"{emoji} Traducción a {nombre_idioma}", color=0x00FF00)
        embed_dm.add_field(name="Original", value=data['texto_es'], inline=False)
        embed_dm.add_field(name="Traducción", value=traduccion, inline=False)
        await user.send(embed=embed_dm)
    except:
        pass

client.run(TOKEN)
