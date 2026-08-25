import discord
import asyncio
import re
import os
from deep_translator import GoogleTranslator, MyMemoryTranslator
from datetime import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import random

TOKEN = os.getenv("DISCORD_TOKEN")

# TUS IDs REALES
ID_CANAL_ACTIVATE = 1358237524249542751
ID_CANAL_ANUNCIOS = 1358237524249542751
ID_CANAL_BUFF = 1358237524249542751
ID_CANAL_OFICIALES = 1358237525214236705
ID_CANAL_BITACORA = 1362642374429245440
ID_CANAL_DIPLOMACIA = 1358237524799131664
ID_CANAL_GENERAL = 1358237524799131662 # CHAT GENERAL AGREGADO

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
client = discord.Client(intents=intents)

mensajes_con_banderas = {}
ultimo_anuncio = {}
# CANALES CON AUTOTRADUCIR SIEMPRE ACTIVO
flag_mode_channels = set([
    ID_CANAL_OFICIALES,
    ID_CANAL_BITACORA,
    ID_CANAL_DIPLOMACIA,
    ID_CANAL_ANUNCIOS,
    ID_CANAL_GENERAL, # AGREGADO
])
procesando_activate = set()
traduciendo_users = set()

BANDERAS = {
    '🇧🇷': 'pt', '🇫🇷': 'fr', '🇩🇪': 'de', '🇮🇹': 'it',
    '🇷🇺': 'ru', '🇯🇵': 'ja', '🇰🇷': 'ko', '🇨🇳': 'zh', '🇮🇩': 'id',
    '🇺🇸': 'en', '🇪🇸': 'es', '🇹🇷': 'tr'
}

NOMBRES_IDIOMAS = {
    'pt': 'Portugués', 'fr': 'Francés', 'de': 'Alemán', 'it': 'Italiano',
    'ru': 'Ruso', 'ja': 'Japonés', 'ko': 'Coreano', 'zh': 'Chino',
    'id': 'Indonesio', 'en': 'Inglés', 'es': 'Español', 'tr': 'Turco'
}

# TRADUCTOR CON REINTENTOS Y FALLBACK - ARREGLA EL ERROR 500
async def traducir_seguro(texto, destino, max_reintentos=3):
    for intento in range(max_reintentos):
        try:
            # Intento 1-2: Google
            if intento < 2:
                await asyncio.sleep(random.uniform(0.3, 0.8)) # Anti rate-limit
                traducido = GoogleTranslator(source='auto', target=destino).translate(texto)
                if traducido and 'error' not in traducido.lower() and 'Error 500' not in traducido:
                    return traducido[:1024]
            # Intento 3: MyMemory como respaldo
            else:
                await asyncio.sleep(0.5)
                traducido = MyMemoryTranslator(source='auto', target=destino).translate(texto)
                if traducido and 'error' not in traducido.lower():
                    return traducido[:1024]
        except Exception as e:
            print(f"[INTENTO {intento+1} FAIL] {e}")
            await asyncio.sleep(1)

    return "⚠️ Translation failed - Try again later"

async def corregir_y_traducir_ia(texto_original: str):
    texto_limpio = re.sub(r'[@#]', '', texto_original)
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
    if len(texto_limpio) < 3:
        return {'es': texto_original, 'en': '⚠️ Message too short'}

    traducido = await traducir_seguro(texto_limpio, 'en')
    return {'es': texto_limpio[:1024], 'en': traducido}

async def traducir_a_idioma(texto, idioma_destino):
    return await traducir_seguro(texto, idioma_destino)

@client.event
async def on_ready():
    print(f'{client.user} conectado. Banderas ocultas ON. Autotraducir activo en: oficiales, bitácora, diplomacia, anuncios, general.')

@client.event
async def on_message(message):
    if message.author == client.user: return
    if not message.content.lower().startswith("meta "): return
    args = message.content[5:].strip()
    comando = args.split()[0].lower() if args else ""
    args = " ".join(args.split()[1:]) if len(args.split()) > 1 else ""

    if comando == "activate":
        if not message.mentions:
            await message.channel.send("❌ Menciona al usuario: `meta activate @usuario [mensaje]`")
            return
        usuario = message.mentions[0]
        usuarios_texto = usuario.mention
        texto_plural = "MUÉVETE"
        texto_sin = "SIN"
        texto_escudo = "ESCUDO"
        datos = await corregir_y_traducir_ia(args)
        if "⚠️" in datos['en']:
            mensaje_extra = f"\n\n💬 MENSAJE / MESSAGE:\n🇲🇽 {datos['es']}\n🇺🇸 Translation failed - Use ES text"
        else:
            mensaje_extra = f"\n\n💬 MENSAJE / MESSAGE:\n🇲🇽 {datos['es']}\n🇺🇸 {datos['en']}"
        descripcion = f"🚨 CÓDIGO DE EMERGENCIA TFT 🚨\n⚠️ ALERTA ROJA\n🎯 OBJETIVO: {usuarios_texto}\n❌ ESTADO: {texto_sin} {texto_escudo} ACTIVO\n🛡️ PROTOCOLO: 1. {texto_plural} YA 2. ESCUDO 8H 3. TELEPORT{mensaje_extra}"[:4096]
        embed = discord.Embed(description=descripcion, color=0xFF0000)
        embed.set_footer(text="Reacciona con 🇺🇸🇧🇷🇯🇵🇹🇷 para traducir a otros idiomas")
        canal_activate = client.get_channel(ID_CANAL_ACTIVATE)
        if canal_activate is None: canal_activate = message.channel
        try:
            msg_publicado = await canal_activate.send(content=usuarios_texto, embed=embed)
            mensajes_con_banderas[msg_publicado.id] = {"texto_es": datos['es'], "tipo": "activate"}
        except Exception as e: print(f"Error en activate: {e}")
        try: await message.delete()
        except: pass
        finally: procesando_activate.discard(message.author.id)
        return

    if comando == "cumpleaños":
        if not message.mentions:
            await message.channel.send("❌ Menciona al usuario: `meta cumpleaños @usuario [mensaje]`")
            return
        usuario = message.mentions[0]
        texto_custom = args
        for mention in [f'<@{usuario.id}>', f'<@!{usuario.id}>']:
            texto_custom = texto_custom.replace(mention, '').strip()
        try: await message.delete()
        except: pass
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
        embed.set_footer(text="Reacciona con 🇺🇸🇧🇷🇯🇵🇹🇷 para traducir a otros idiomas")
        canal = client.get_channel(ID_CANAL_ANUNCIOS) or message.channel
        msg_publicado = await canal.send(content=f"{usuario.mention} @everyone", embed=embed)
        mensajes_con_banderas[msg_publicado.id] = {"texto_es": mensaje_es, "tipo": "cumpleaños"}
        ultimo_anuncio[message.channel.id] = msg_publicado
        return

    if comando in ["evento", "alerta"]:
        if not args: return
        try: await message.delete()
        except: pass
        procesando = await message.channel.send("⏳ Corrigiendo...")
        datos = await corregir_y_traducir_ia(args)
        try: await procesando.delete()
        except: pass
        embed = discord.Embed(title="📅 EVENTO / 🚨 ALERTA", color=0x3498DB)
        embed.add_field(name="🇲🇽 Español", value=datos['es'], inline=False)
        embed.add_field(name="🇺🇸 English", value=datos['en'], inline=False)
        embed.set_footer(text="Reacciona con 🇺🇸🇧🇷🇯🇵🇹🇷 para traducir a otros idiomas")
        canal = client.get_channel(ID_CANAL_ANUNCIOS) or message.channel
        msg_publicado = await canal.send("@everyone", embed=embed)
        mensajes_con_banderas[msg_publicado.id] = {"texto_es": datos['es'], "tipo": comando}
        ultimo_anuncio[message.channel.id] = msg_publicado
        return

    if comando in ["buffo", "bufo", "buff"]:
        if not args: return
        try: await message.delete()
        except: pass
        datos = await corregir_y_traducir_ia(args)
        embed = discord.Embed(title="🛎️ BUFO ACTIVADO", color=0x9B59B6)
        embed.add_field(name="🇲🇽 Español", value=f"✅ {datos['es']}", inline=False)
        embed.add_field(name="🇺🇸 English", value=f"✅ {datos['en']}", inline=False)
        embed.set_footer(text="Reacciona con 🇺🇸🇧🇷🇯🇵🇹🇷 para traducir a otros idiomas")
        canal_buff = client.get_channel(ID_CANAL_BUFF) or message.channel
        msg_publicado = await canal_buff.send("@everyone", embed=embed)
        mensajes_con_banderas[msg_publicado.id] = {"texto_es": datos['es'], "tipo": "buffo"}
        ultimo_anuncio[message.channel.id] = msg_publicado
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
            try: await message.delete()
            except: pass
            await message.channel.send("✅ Anuncio editado.", delete_after=5)
        except Exception as e:
            print(f"Error editar: {e}")
            await message.channel.send("❌ No se pudo editar el anuncio.")
        return

    if comando == "limpia":
        cantidad = 10
        if args and args.isdigit(): cantidad = int(args)
        if cantidad > 50: cantidad = 50
        try: await message.delete()
        except: pass
        borrados = 0
        async for msg in message.channel.history(limit=100):
            if msg.author == client.user:
                try:
                    await msg.delete()
                    borrados += 1
                    if borrados >= cantidad: break
                    await asyncio.sleep(0.5)
                except: pass
        await message.channel.send(f"🧹 Borrados {borrados} mensajes del bot.", delete_after=5)
        return

    if comando == "ping":
        await message.channel.send(f"🟢 Latencia: {round(client.latency*1000)}ms")
        return

    if comando == "ayuda":
        embed = discord.Embed(title="📋 COMANDOS META BOT", color=0x9B59B6)
        embed.add_field(name="🚨 meta activate @usuario [mensaje]", value="Código de emergencia ES/EN", inline=False)
        embed.add_field(name="🎂 meta cumpleaños @usuario [mensaje]", value="Felicitación ES/EN", inline=False)
        embed.add_field(name="📢 meta alerta <texto>", value="Alerta ES/EN", inline=False)
        embed.add_field(name="⚔️ meta evento <texto>", value="Evento ES/EN", inline=False)
        embed.add_field(name="🛎️ meta buffo <texto>", value="Bufo ES/EN + @everyone", inline=False)
        embed.add_field(name="✏️ meta editar <texto>", value="Edita el último anuncio del bot", inline=False)
        embed.add_field(name="🧹 meta limpia [cantidad]", value="Borra mensajes del bot | Max 50", inline=False)
        embed.add_field(name="🟢 meta ping", value="Verifica latencia", inline=False)
        embed.add_field(name="🌍 Traductor", value="Siempre activo en #oficiales, #diplomacia, #bitácora, #anuncios, #general", inline=False)
        embed.add_field(name="🌍 Banderas", value="Reacciona con 🇺🇸🇧🇷🇯🇵🇫🇷🇩🇪🇮🇹🇷🇺🇰🇷🇨🇳🇮🇩🇹🇷 pa traducir", inline=False)
        embed.set_footer(text="META ESTÁ CONTIGO. UN REINO, UNA ALIANZA, UNA META")
        await message.channel.send(embed=embed)
        return

@client.event
async def on_raw_reaction_add(payload):
    if payload.user_id == client.user.id: return
    if payload.user_id in traduciendo_users: return
    traduciendo_users.add(payload.user_id)

    emoji = str(payload.emoji)
    if emoji not in BANDERAS:
        traduciendo_users.discard(payload.user_id)
        return

    try:
        channel = client.get_channel(payload.channel_id)
        if channel is None: return
        message = await channel.fetch_message(payload.message_id)

        try:
            user = await client.fetch_user(payload.user_id)
            await message.remove_reaction(payload.emoji, user)
        except: pass

        ultimos_50 = [msg async for msg in channel.history(limit=50)]
        if message.id not in [m.id for m in ultimos_50]:
            return

        if payload.message_id in mensajes_con_banderas:
            data = mensajes_con_banderas[payload.message_id]
            traduccion = await traducir_a_idioma(data['texto_es'], BANDERAS[emoji])
            nombre = NOMBRES_IDIOMAS.get(BANDERAS[emoji], BANDERAS[emoji])
            embed_dm = discord.Embed(title=f"{emoji} Traducción a {nombre}", color=0x00FF00)
            embed_dm.add_field(name="Original", value=data['texto_es'], inline=False)
            embed_dm.add_field(name="Traducción", value=traduccion, inline=False)
            await user.send(embed=embed_dm)
            return

        if payload.channel_id in flag_mode_channels:
            if message.author.bot or len(message.content.strip()) < 2: return
            traduccion = await traducir_a_idioma(message.content, BANDERAS[emoji])

            # TIMER ESPECIAL PA TURCO: 40 SEGUNDOS, RESTO 20 SEGUNDOS
            delete_timer = 40 if BANDERAS[emoji] == 'tr' else 20

            if BANDERAS[emoji] in ['es', 'en', 'tr']:
                flag_emoji = '🇪🇸' if BANDERAS[emoji] == 'es' else '🇺🇸' if BANDERAS[emoji] == 'en' else '🇹🇷'
                embed = discord.Embed(description=f"{flag_emoji} {traduccion}", color=0x00B0F4)
                await channel.send(embed=embed, delete_after=delete_timer)
            else:
                nombre = NOMBRES_IDIOMAS.get(BANDERAS[emoji], BANDERAS[emoji])
                embed_dm = discord.Embed(title=f"{emoji} Traducción a {nombre}", color=0x00FF00)
                embed_dm.add_field(name="Original", value=message.content[:1024], inline=False)
                embed_dm.add_field(name="Traducción", value=traduccion[:1024], inline=False)
                await user.send(embed=embed_dm)

    except Exception as e:
        print(f"[ERROR REACCIÓN] {e}")
    finally:
        await asyncio.sleep(3)
        traduciendo_users.discard(payload.user_id)

# PUERTO FAKE PA RENDER - ARREGLA EL 501 DE UPTIMEROBOT
class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot alive')
    def log_message(self, format, *args):
        return

def run_server():
    server = HTTPServer(('0.0.0.0', 10000), Handler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()
client.run(TOKEN)
