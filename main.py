import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import discord
import asyncio
from deep_translator import GoogleTranslator, MyMemoryTranslator
from dotenv import load_dotenv
from groq import Groq
import json
import time
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

ID_CANAL_ANUNCIOS = 1358237524249542751
ID_CANAL_ACTIVATE = 1358237524799131662
ID_CANAL_BUFF = 1404721557279871056

# CANALES CON TRADUCCION SIEMPRE ACTIVA
CANALES_TRADUCCION_SIEMPRE_ACTIVOS = [
    1358237525214236705, # oficiales
    1358237524799131664, # diplomacia
    1362642374429245440 # bitácora
]

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Kingdom bot is alive!')

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return

def start_web_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), PingHandler)
    server.serve_forever()

threading.Thread(target=start_web_server, daemon=True).start()

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
client = discord.Client(intents=intents)
procesando_activate = set()

BANDERAS = {
    '🇺🇸': 'en', '🇧🇷': 'pt', '🇫🇷': 'fr', '🇩🇪': 'de', '🇮🇹': 'it', '🇷🇺': 'ru',
    '🇯🇵': 'ja', '🇰🇷': 'ko', '🇨🇳': 'zh-CN', '🇸🇦': 'ar', '🇹🇷': 'tr', '🇮🇩': 'id',
    '🇹🇭': 'th', '🇻🇳': 'vi', '🇵🇱': 'pl'
}

NOMBRES_IDIOMAS = {
    'en': 'English', 'pt': 'Português', 'fr': 'Français', 'de': 'Deutsch',
    'it': 'Italiano', 'ru': 'Русский', 'ja': '日本語', 'ko': '한국어',
    'zh-CN': '中文', 'ar': 'العربية', 'tr': 'Türkçe', 'id': 'Indonesia',
    'th': 'ไทย', 'vi': 'Tiếng Việt', 'pl': 'Polski'
}

mensajes_con_banderas = {}
mensajes_diplomacia = {}
flag_mode_channels = set(CANALES_TRADUCCION_SIEMPRE_ACTIVOS)
automensajes_activos = {}
ultimo_anuncio = {}

# ========== LIMPIEZA RAM CADA 48H ==========
async def limpieza_memoria_48h():
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(172800) # 48 horas
        count_diplo = len(mensajes_diplomacia)
        count_banderas = len(mensajes_con_banderas)
        mensajes_diplomacia.clear()
        mensajes_con_banderas.clear()
        print(f"🧹 Limpieza 48h: {count_diplo} msgs diplomacia + {count_banderas} banderas borrados de RAM")

# ========== AUTOMENSAJE SIMPLE DEFAULT 8H ==========
async def enviar_automensaje(user_id, mensaje, autor_id, intervalo_horas=8):
    try:
        user = await client.fetch_user(user_id)
        autor = await client.fetch_user(autor_id)
        inicio = time.time()
        intervalo_segundos = intervalo_horas * 3600

        while True:
            if time.time() - inicio >= 86400:
                if user_id in automensajes_activos:
                    del automensajes_activos[user_id]
                try:
                    await user.send(f"⏰ **Automensaje desactivado**\nTerminó después de 24h.")
                except:
                    pass
                break

            try:
                embed = discord.Embed(
                    title="⏰ RECORDATORIO AUTOMÁTICO",
                    description=f"{mensaje}",
                    color=0xFF9900
                )
                embed.set_footer(text=f"Enviado por: {autor.display_name} | Cada {intervalo_horas}h por 24h")
                await user.send(embed=embed)

            except discord.Forbidden:
                if user_id in automensajes_activos:
                    del automensajes_activos[user_id]
                try:
                    await autor.send(f"❌ No pude enviarle DM a {user.display_name}. Tiene DMs cerrados o me bloqueó.")
                except:
                    pass
                break
            except discord.HTTPException:
                await asyncio.sleep(10)
                continue

            await asyncio.sleep(intervalo_segundos)

    except asyncio.CancelledError:
        pass
    finally:
        if user_id in automensajes_activos:
            del automensajes_activos[user_id]

async def corregir_y_traducir_ia(texto_original):
    prompt = f"""Eres un asistente para un clan de Rise of Kingdoms. 1. Detecta el idioma. 2. Corrige errores. 3. Traduce a Español e Inglés. 4. Responde SOLO JSON: {{"idioma_detectado": "es", "original_corregido": "texto", "es": "texto", "en": "texto"}} Texto: "{texto_original}" """
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
        try:
            en = GoogleTranslator(source='auto', target='en').translate(texto_original)
        except:
            en = texto_original
        return {"idioma_detectado": "es", "original_corregido": texto_original, "es": texto_original, "en": en}

async def traducir_a_idioma(texto, idioma_destino):
    if idioma_destino.lower() == 'zh-cn':
        idioma_destino = 'zh-CN'
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(GoogleTranslator(source='auto', target=idioma_destino).translate, texto),
            timeout=3.0
        )
    except:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(MyMemoryTranslator(source='auto', target=idioma_destino).translate, texto),
                timeout=3.0
            )
        except:
            return f"No se pudo traducir a {idioma_destino}."

@client.event
async def on_ready():
    print(f'✅ Bot conectado como {client.user}')
    for channel_id in CANALES_TRADUCCION_SIEMPRE_ACTIVOS:
        try:
            canal = client.get_channel(channel_id)
            if canal:
                count = 0
                async for msg in canal.history(limit=50): # 50 MENSAJES
                    if not msg.author.bot and len(msg.content.strip()) > 2:
                        mensajes_diplomacia[msg.id] = msg.content
                        count += 1
                print(f"Historial {canal.name}: {count} msgs")
        except Exception as e:
            print(f"Error canal {channel_id}: {e}")

    asyncio.create_task(limpieza_memoria_48h())

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.id in flag_mode_channels:
        if not message.content.lower().startswith("meta "):
            if len(message.content.strip()) >= 2:
                mensajes_diplomacia[message.id] = message.content

    if not message.content.lower().startswith("meta "):
        return

    partes = message.content.split(' ', 2)
    if len(partes) < 2:
        return

    comando = partes[1].lower()
    args = partes[2] if len(partes) > 2 else ""
    autor = message.author

    if comando == "automensaje":
        args_split = args.split(' ', 1)
        if not args_split or args_split[0] == "":
            await message.channel.send("❌ Uso: `meta automensaje on @usuario [horas] mensaje`\nEjemplo: `meta automensaje on @Juan 8 Recuerda escudo`")
            return

        subcomando = args_split[0].lower()

        if subcomando == "on":
            if not message.mentions:
                await message.channel.send("❌ Menciona al usuario")
                return

            usuario = message.mentions[0]
            resto = args_split[1] if len(args_split) > 1 else ""

            for mention in [f'<@{usuario.id}>', f'<@!{usuario.id}>']:
                resto = resto.replace(mention, '').strip()

            partes_resto = resto.split(' ', 1)
            intervalo_horas = 8
            texto_mensaje = resto

            if partes_resto and partes_resto[0].isdigit():
                horas = int(partes_resto[0])
                if 1 <= horas <= 24:
                    intervalo_horas = horas
                    texto_mensaje = partes_resto[1] if len(partes_resto) > 1 else ""
                else:
                    await message.channel.send("❌ Horas entre 1 y 24")
                    return

            if not texto_mensaje:
                await message.channel.send("❌ Escribe un mensaje")
                return

            if usuario.id in automensajes_activos:
                automensajes_activos[usuario.id]["task"].cancel()
                del automensajes_activos[usuario.id]

            task = asyncio.create_task(enviar_automensaje(usuario.id, texto_mensaje, autor.id, intervalo_horas))
            automensajes_activos[usuario.id] = {"mensaje": texto_mensaje, "task": task, "inicio": time.time(), "autor": autor.id}

            embed = discord.Embed(
                title="✅ Automensaje Activado",
                description=f"DM a {usuario.mention} cada {intervalo_horas} horas por 24h",
                color=0x00FF00
            )
            embed.add_field(name="Mensaje", value=texto_mensaje, inline=False)
            await message.channel.send(embed=embed)

        elif subcomando == "off":
            if not message.mentions:
                return
            usuario = message.mentions[0]
            if usuario.id in automensajes_activos:
                automensajes_activos[usuario.id]["task"].cancel()
                del automensajes_activos[usuario.id]
                await message.channel.send(f"🛑 Automensaje para {usuario.mention} desactivado.")
        return

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
                msg = await message.channel.send("👤 Menciona a los usuarios:")
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
                    await message.channel.send("⏰ Tiempo agotado.")
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

            descripcion = f"🚨 CÓDIGO DE EMERGENCIA TFT 🚨\n⚠️ ALERTA ROJA\n🎯 OBJETIVO: {usuarios_texto}\n❌ ESTADO: {texto_sin} {texto_escudo} ACTIVO\n🛡️ PROTOCOLO: 1. {texto_plural} YA 2. ESCUDO 8H 3. TELEPORT{mensaje_extra}"
            embed = discord.Embed(description=descripcion, color=0xFF0000)
            canal_activate = client.get_channel(ID_CANAL_ACTIVATE)
            if canal_activate:
                await canal_activate.send(content=usuarios_texto, embed=embed)
            await message.delete()
        finally:
            procesando_activate.discard(message.author.id)
        return

    if comando == "cumpleaños":
        if not message.mentions:
            await message.channel.send("❌ Menciona al usuario: `meta cumpleaños @usuario [mensaje]`")
            return

        usuario = message.mentions[0]
        texto_custom = args
        for mention in [f'<@{usuario.id}>', f'<@!{usuario.id}>']:
            texto_custom = texto_custom.replace(mention, '').strip()

        await message.delete()

        if texto_custom:
            datos = await corregir_y_traducir_ia(texto_custom)
            mensaje_es = datos['es']
            mensaje_en = datos['en']
        else:
            mensaje_es = f"¡Feliz cumpleaños {usuario.display_name}! 🎉🎂 Que tengas un día increíble."
            mensaje_en = f"Happy birthday {usuario.display_name}! 🎉🎂 Have an amazing day."

        embed = discord.Embed(title="🎂 ¡FELIZ CUMPLEAÑOS!", color=0xFF69B4)
        embed.add_field(name="🇲🇽 Español", value=mensaje_es, inline=False)
        embed.add_field(name="🇺🇸 English", value=mensaje_en, inline=False)
        embed.set_thumbnail(url=usuario.display_avatar.url)

        canal = client.get_channel(ID_CANAL_ANUNCIOS) or message.channel
        msg_publicado = await canal.send(content=f"{usuario.mention} @everyone", embed=embed)
        mensajes_con_banderas[msg_publicado.id] = {"texto_es": mensaje_es, "tipo": "cumpleaños"}
        ultimo_anuncio[message.channel.id] = msg_publicado

        for bandera in ['🇧🇷', '🇫🇷', '🇩🇪', '🇮🇹', '🇷🇺', '🇯🇵', '🇰🇷', '🇨🇳', '🇮🇩']:
            try:
                await msg_publicado.add_reaction(bandera)
                await asyncio.sleep(0.35)
            except:
                pass
        return

    if comando in ["evento", "alerta"]:
        if not args:
            return
        await message.delete()
        procesando = await message.channel.send("⏳ Corrigiendo...")
        datos = await corregir_y_traducir_ia(args)
        await procesando.delete()
        embed = discord.Embed(title="📅 EVENTO / 🚨 ALERTA", color=0x3498DB)
        embed.add_field(name="🇲🇽 Español", value=datos['es'], inline=False)
        embed.add_field(name="🇺🇸 English", value=datos['en'], inline=False)
        canal = client.get_channel(ID_CANAL_ANUNCIOS) or message.channel
        msg_publicado = await canal.send("@everyone", embed=embed)
        mensajes_con_banderas[msg_publicado.id] = {"texto_es": datos['es'], "tipo": comando}
        ultimo_anuncio[message.channel.id] = msg_publicado
        for bandera in ['🇧🇷', '🇫🇷', '🇩🇪', '🇮🇹', '🇷🇺', '🇯🇵', '🇰🇷', '🇨🇳', '🇮🇩']:
            try:
                await msg_publicado.add_reaction(bandera)
                await asyncio.sleep(0.35)
            except:
                pass
        return

    if comando in ["buffo", "bufo", "buff"]:
        if not args:
            return
        await message.delete()
        datos = await corregir_y_traducir_ia(args)
        embed = discord.Embed(title="🛎️ BUFO ACTIVADO", color=0x9B59B6)
        embed.add_field(name="🇲🇽 Español", value=f"✅ {datos['es']}", inline=False)
        embed.add_field(name="🇺🇸 English", value=f"✅ {datos['en']}", inline=False)
        canal_buff = client.get_channel(ID_CANAL_BUFF) or message.channel
        msg_publicado = await canal_buff.send("@everyone", embed=embed)
        mensajes_con_banderas[msg_publicado.id] = {"texto_es": datos['es'], "tipo": "buffo"}
        ultimo_anuncio[message.channel.id] = msg_publicado
        for bandera in ['🇧🇷', '🇫🇷', '🇩🇪', '🇮🇹', '🇷🇺', '🇯🇵', '🇰🇷', '🇨🇳', '🇮🇩']:
            try:
                await msg_publicado.add_reaction(bandera)
                await asyncio.sleep(0.35)
            except:
                pass
        return

    if comando == "editar":
        if not args:
            await message.channel.send("❌ Escribe el nuevo texto: `meta editar nuevo texto`")
            return

        if message.channel.id not in ultimo_anuncio:
            await message.channel.send("❌ No hay anuncio reciente para editar en este canal.")
            return

        msg_a_editar = ultimo_anuncio[message.channel.id]
        datos = await corregir_y_traducir_ia(args)

        try:
            embed = msg_a_editar.embeds[0]
            embed.clear_fields()
            if "CUMPLEAÑOS" in embed.title:
                embed.add_field(name="🇲🇽 Español", value=datos['es'], inline=False)
                embed.add_field(name="🇺🇸 English", value=datos['en'], inline=False)
            elif "BUFO" in embed.title:
                embed.add_field(name="🇲🇽 Español", value=f"✅ {datos['es']}", inline=False)
                embed.add_field(name="🇺🇸 English", value=f"✅ {datos['en']}", inline=False)
            else:
                embed.add_field(name="🇲🇽 Español", value=datos['es'], inline=False)
                embed.add_field(name="🇺🇸 English", value=datos['en'], inline=False)

            await msg_a_editar.edit(embed=embed)
            mensajes_con_banderas[msg_a_editar.id]["texto_es"] = datos['es']
            await message.delete()
            await message.channel.send("✅ Anuncio editado.", delete_after=5)
        except:
            await message.channel.send("❌ No se pudo editar el anuncio.")
        return

    if comando == "limpia":
        cantidad = 10
        if args and args.isdigit():
            cantidad = int(args)
            if cantidad > 50:
                cantidad = 50

        await message.delete()
        borrados = 0
        async for msg in message.channel.history(limit=100):
            if msg.author == client.user:
                try:
                    await msg.delete()
                    borrados += 1
                    if borrados >= cantidad:
                        break
                    await asyncio.sleep(0.5)
                except:
                    pass

        confirmacion = await message.channel.send(f"🧹 Borrados {borrados} mensajes del bot.", delete_after=5)
        return

    if comando == "ping":
        await message.channel.send(f"🟢 Latencia: {round(client.latency*1000)}ms")
        return

    if comando == "ayuda":
        embed = discord.Embed(title="📋 COMANDOS META BOT", color=0x9B59B6)
        embed.add_field(name="🚨 meta activate @usuario [mensaje]", value="Código de emergencia ES/EN", inline=False)
        embed.add_field(name="⏰ meta automensaje on @usuario [horas] <mensaje>", value="DM cada X horas por 24h | Default 8h", inline=False)
        embed.add_field(name="🛑 meta automensaje off @usuario", value="Cancela automensaje", inline=False)
        embed.add_field(name="🎂 meta cumpleaños @usuario [mensaje]", value="Felicitación ES/EN + banderas", inline=False)
        embed.add_field(name="📢 meta alerta <texto>", value="Alerta ES/EN + banderas", inline=False)
        embed.add_field(name="⚔️ meta evento <texto>", value="Evento ES/EN + banderas", inline=False)
        embed.add_field(name="🛎️ meta buffo <texto>", value="Bufo ES/EN + @everyone + banderas", inline=False)
        embed.add_field(name="✏️ meta editar <texto>", value="Edita el último anuncio del bot", inline=False)
        embed.add_field(name="🧹 meta limpia [cantidad]", value="Borra mensajes del bot | Max 50", inline=False)
        embed.add_field(name="🟢 meta ping", value="Verifica latencia", inline=False)
        embed.add_field(name="🌐 Traductor", value="Siempre activo en #oficiales, #diplomacia y #bitácora. Reacciona con bandera. ES/EN = 20s en canal, otros = DM", inline=False)
        embed.add_field(name="🌍 Banderas", value="🇧🇷🇫🇷🇩🇪🇮🇹🇷🇺🇯🇵🇰🇷🇨🇳🇮🇩🇸🇦🇹🇷🇹🇭🇻🇳🇵🇱", inline=False)
        embed.set_footer(text="META ESTÁ CONTIGO. UN REINO, UNA ALIANZA, UNA META")
        await message.channel.send(embed=embed)
        return

@client.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    # MODO AUTOTRADUCIR - Diplomacia/Oficiales/Bitácora
    if reaction.message.channel.id in flag_mode_channels:
        emoji = str(reaction.emoji)
        if emoji not in BANDERAS:
            return

        # SI NO ESTÁ EN MEMORIA, IGNORA - NO FETCH PA NO GASTAR RAM
        if reaction.message.id not in mensajes_diplomacia:
            try:
                await reaction.remove(user)
            except:
                pass
            return

        texto_original = mensajes_diplomacia[reaction.message.id]
        idioma_destino = BANDERAS[emoji]

        try:
            await reaction.remove(user)
        except:
            pass

        try:
            traduccion = await traducir_a_idioma(texto_original, idioma_destino)

            if idioma_destino in ['es', 'en']:
                flag_emoji = '🇪🇸' if idioma_destino == 'es' else '🇺🇸'
                embed = discord.Embed(description=f"{flag_emoji} {traduccion}", color=0x00B0F4)
                await reaction.message.channel.send(embed=embed, delete_after=20)
            else:
                nombre = NOMBRES_IDIOMAS.get(idioma_destino, idioma_destino)
                embed_dm = discord.Embed(title=f"{emoji} Traducción a {nombre}", color=0x00FF00)
                embed_dm.add_field(name="Original", value=texto_original[:1024], inline=False)
                embed_dm.add_field(name="Traducción", value=traduccion[:1024], inline=False)
                await user.send(embed=embed_dm)
        except:
            pass
        return

    # BANDERAS EN ANUNCIOS/EVENTOS - Solo DM
    if reaction.message.id not in mensajes_con_banderas:
        return

    emoji = str(reaction.emoji)
    if emoji not in BANDERAS:
        return

    data = mensajes_con_banderas[reaction.message.id]

    try:
        await reaction.remove(user)
    except:
        pass

    try:
        traduccion = await traducir_a_idioma(data['texto_es'], BANDERAS[emoji])
        nombre = NOMBRES_IDIOMAS.get(BANDERAS[emoji], BANDERAS[emoji])
        embed_dm = discord.Embed(title=f"{emoji} Traducción a {nombre}", color=0x00FF00)
        embed_dm.add_field(name="Original", value=data['texto_es'], inline=False)
        embed_dm.add_field(name="Traducción", value=traduccion, inline=False)
        await user.send(embed=embed_dm)
    except:
        pass

client.run(TOKEN)
