import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import re
import os
from deep_translator import GoogleTranslator, MyMemoryTranslator
from datetime import datetime, timedelta
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import random
from collections import defaultdict
import hashlib

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = None # Pon ID de tu server pa sync rápido

# TUS IDs REALES
ID_CANAL_ACTIVATE = 1358237524249542751
ID_CANAL_ANUNCIOS = 1358237524249542751
ID_CANAL_BUFF = 1358237524249542751
ID_CANAL_OFICIALES = 1358237525214236705
ID_CANAL_BITACORA = 1362642374429245440
ID_CANAL_DIPLOMACIA = 1358237524799131664
ID_CANAL_GENERAL = 1358237524799131662

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# SISTEMAS ANTI CRASH
mensajes_con_banderas = {}
ultimo_anuncio = {}
traduciendo_users = set()
cache_traducciones = {} # {hash: traduccion}
cooldowns = defaultdict(lambda: datetime.now() - timedelta(seconds=10))
traducciones_activas = set() # {message_id:idioma} evita dupes simultáneos
flag_mode_channels = set([
    ID_CANAL_OFICIALES,
    ID_CANAL_BITACORA,
    ID_CANAL_DIPLOMACIA,
    ID_CANAL_ANUNCIOS,
    ID_CANAL_GENERAL,
])
rate_limit_lock = asyncio.Lock()
ultima_traduccion = datetime.now()

BANDERAS = {
    '🇧🇷': 'pt', '🇫🇷': 'fr', '🇩🇪': 'de', '🇮🇹': 'it',
    '🇷🇺': 'ru', '🇯🇵': 'ja', '🇰🇷': 'ko', '🇨🇳': 'zh', '🇮🇩': 'id',
    '🇺🇸': 'en', '🇪🇸': 'es', '🇹🇷': 'tr', '🇸🇦': 'ar', '🇹🇭': 'th', '🇻🇳': 'vi'
}

NOMBRES_IDIOMAS = {
    'pt': 'Portugués', 'fr': 'Francés', 'de': 'Alemán', 'it': 'Italiano',
    'ru': 'Ruso', 'ja': 'Japonés', 'ko': 'Coreano', 'zh': 'Chino',
    'id': 'Indonesio', 'en': 'Inglés', 'es': 'Español', 'tr': 'Turco',
    'ar': 'Árabe', 'th': 'Tailandés', 'vi': 'Vietnamita'
}

# ANTI RATE LIMIT GLOBAL 1.2s ENTRE TRADUCCIONES
async def esperar_rate_limit():
    global ultima_traduccion
    async with rate_limit_lock:
        tiempo_espera = 1.2 - (datetime.now() - ultima_traduccion).total_seconds()
        if tiempo_espera > 0:
            await asyncio.sleep(tiempo_espera)
        ultima_traduccion = datetime.now()

# TRADUCTOR CON CACHE + 2 APIS + LIMPIA MENCIONES
async def traducir_seguro(texto, destino, max_reintentos=2):
    if not texto or len(texto.strip()) < 2:
        return "⚠️ Texto muy corto"

    # Limpiar menciones pa que no traduzca @Goloshino
    texto_limpio = re.sub(r'<@!?\d+>', '', texto)
    texto_limpio = re.sub(r'<@&\d+>', '', texto_limpio)
    texto_limpio = re.sub(r'@\w+', '', texto_limpio)
    texto_limpio = texto_limpio.strip()
    if len(texto_limpio) < 2:
        return "⚠️ Solo menciones detectadas"

    hash_texto = hashlib.md5(f"{texto_limpio}:{destino}".encode()).hexdigest()
    if hash_texto in cache_traducciones:
        return cache_traducciones[hash_texto]

    for intento in range(max_reintentos):
        try:
            await esperar_rate_limit()
            if intento == 0:
                traducido = GoogleTranslator(source='auto', target=destino).translate(texto_limpio)
            else:
                traducido = MyMemoryTranslator(source='auto', target=destino).translate(texto_limpio)

            if traducido and 'error' not in traducido.lower() and '500' not in traducido:
                resultado = traducido[:1024]
                cache_traducciones[hash_texto] = resultado
                if len(cache_traducciones) > 500:
                    cache_traducciones.clear()
                return resultado
        except Exception as e:
            print(f"[TRAD INTENTO {intento+1}] {destino}: {e}")
            await asyncio.sleep(0.8 * (intento + 1))

    return "⚠️ Translation failed"

async def corregir_y_traducir_ia(texto_original: str):
    texto_limpio = re.sub(r'[@#]', '', texto_original)
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
    if len(texto_limpio) < 3:
        return {'es': texto_original, 'en': '⚠️ Message too short'}

    traducido = await traducir_seguro(texto_limpio, 'en')
    return {'es': texto_limpio[:1024], 'en': traducido}

@bot.event
async def on_ready():
    print(f'{bot.user} conectado. V3 Anti-Crash ON.')
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            synced = await bot.tree.sync(guild=guild)
            print(f'Synceado {len(synced)} comandos a guild {GUILD_ID}')
        else:
            synced = await bot.tree.sync()
            print(f'Synceado {len(synced)} comandos globalmente')
    except Exception as e:
        print(f'Error sync: {e}')

def tiene_cooldown(user_id):
    ahora = datetime.now()
    if (ahora - cooldowns[user_id]).total_seconds() < 3:
        return True
    cooldowns[user_id] = ahora
    return False

# SLASH COMMANDS
@bot.tree.command(name="activate", description="🚨 Código de emergencia TFT")
@app_commands.describe(usuario="Usuario en peligro", mensaje="Mensaje adicional")
async def activate(interaction: discord.Interaction, usuario: discord.Member, mensaje: str = ""):
    if tiene_cooldown(interaction.user.id):
        return await interaction.response.send_message("⏳ Espera 3s entre comandos", ephemeral=True)

    await interaction.response.defer()
    datos = await corregir_y_traducir_ia(mensaje)

    if "⚠️" in datos['en']:
        mensaje_extra = f"\n\n💬 MENSAJE:\n🇲🇽 {datos['es']}\n🇺🇸 Translation failed"
    else:
        mensaje_extra = f"\n\n💬 MENSAJE:\n🇲🇽 {datos['es']}\n🇺🇸 {datos['en']}" if mensaje else ""

    descripcion = f"🚨 CÓDIGO DE EMERGENCIA TFT 🚨\n⚠️ ALERTA ROJA\n🎯 OBJETIVO: {usuario.mention}\n❌ ESTADO: SIN ESCUDO ACTIVO\n🛡️ PROTOCOLO: 1. MUÉVETE YA 2. ESCUDO 8H 3. TELEPORT{mensaje_extra}"[:4096]
    embed = discord.Embed(description=descripcion, color=0xFF0000)

    canal = bot.get_channel(ID_CANAL_ACTIVATE) or interaction.channel
    msg = await canal.send(content=usuario.mention, embed=embed)
    mensajes_con_banderas[msg.id] = {"texto_es": mensaje if mensaje else "Código de emergencia", "tipo": "activate"}
    await interaction.followup.send("✅ Alerta enviada", ephemeral=True)

@bot.tree.command(name="cumpleaños", description="🎂 Felicita a alguien")
@app_commands.describe(usuario="Cumpleañero", mensaje="Mensaje personalizado")
async def cumpleaños(interaction: discord.Interaction, usuario: discord.Member, mensaje: str = ""):
    if tiene_cooldown(interaction.user.id):
        return await interaction.response.send_message("⏳ Espera 3s", ephemeral=True)

    await interaction.response.defer()
    if mensaje:
        datos = await corregir_y_traducir_ia(mensaje)
        mensaje_es = datos['es']
        mensaje_en = datos['en']
    else:
        mensaje_es = f"¡Feliz cumpleaños {usuario.display_name}! 🎉🎂 Que tengas un día increíble."
        mensaje_en = f"Happy birthday {usuario.display_name}! 🎉🎂 Have an amazing day."

    embed = discord.Embed(title="🎂 ¡FELIZ CUMPLEAÑOS!", color=0xFF69B4)
    embed.add_field(name="🇲🇽 Español", value=mensaje_es, inline=False)
    embed.add_field(name="🇺🇸 English", value=mensaje_en, inline=False)
    embed.set_thumbnail(url=usuario.display_avatar.url)

    canal = bot.get_channel(ID_CANAL_ANUNCIOS) or interaction.channel
    msg = await canal.send(content=f"{usuario.mention} @everyone", embed=embed)
    mensajes_con_banderas[msg.id] = {"texto_es": mensaje_es, "tipo": "cumpleaños"}
    ultimo_anuncio[interaction.channel_id] = msg
    await interaction.followup.send("✅ Felicitación enviada", ephemeral=True)

@bot.tree.command(name="alerta", description="📢 Crea una alerta bilingüe")
@app_commands.describe(texto="Texto de la alerta")
async def alerta(interaction: discord.Interaction, texto: str):
    if tiene_cooldown(interaction.user.id):
        return await interaction.response.send_message("⏳ Espera 3s", ephemeral=True)

    await interaction.response.defer()
    datos = await traducir_seguro(texto, 'en')

    embed = discord.Embed(title="🚨 ALERTA", color=0x3498DB)
    embed.add_field(name="🇲🇽 Español", value=texto[:1024], inline=False)
    embed.add_field(name="🇺🇸 English", value=datos, inline=False)
    embed.set_footer(text=f"Por {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

    canal = bot.get_channel(ID_CANAL_ANUNCIOS) or interaction.channel
    msg = await canal.send("@everyone", embed=embed)
    mensajes_con_banderas[msg.id] = {"texto_es": texto, "tipo": "alerta"}
    ultimo_anuncio[interaction.channel_id] = msg
    await interaction.followup.send("✅ Alerta publicada", ephemeral=True)

@bot.tree.command(name="buffo", description="🛎️ Activa bufo de alianza")
@app_commands.describe(texto="Detalles del bufo")
async def buffo(interaction: discord.Interaction, texto: str):
    if tiene_cooldown(interaction.user.id):
        return await interaction.response.send_message("⏳ Espera 3s", ephemeral=True)

    await interaction.response.defer()
    datos = await traducir_seguro(texto, 'en')

    embed = discord.Embed(title="🛎️ BUFO ACTIVADO", color=0x9B59B6)
    embed.add_field(name="🇲🇽 Español", value=f"✅ {texto[:1024]}", inline=False)
    embed.add_field(name="🇺🇸 English", value=f"✅ {datos}", inline=False)

    canal = bot.get_channel(ID_CANAL_BUFF) or interaction.channel
    msg = await canal.send("@everyone", embed=embed)
    mensajes_con_banderas[msg.id] = {"texto_es": texto, "tipo": "buffo"}
    ultimo_anuncio[interaction.channel_id] = msg
    await interaction.followup.send("✅ Bufo activado", ephemeral=True)

@bot.tree.command(name="ping", description="🟢 Verifica latencia del bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🟢 Pong! {round(bot.latency*1000)}ms", ephemeral=True)

@bot.tree.command(name="editar", description="✏️ Edita el último anuncio")
@app_commands.describe(texto="Nuevo texto")
async def editar(interaction: discord.Interaction, texto: str):
    if tiene_cooldown(interaction.user.id):
        return await interaction.response.send_message("⏳ Espera 3s", ephemeral=True)

    if interaction.channel_id not in ultimo_anuncio:
        return await interaction.response.send_message("❌ No hay anuncio reciente en este canal", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    msg_a_editar = ultimo_anuncio[interaction.channel_id]
    datos = await corregir_y_traducir_ia(texto)

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
        await interaction.followup.send("✅ Anuncio editado", ephemeral=True)
    except Exception as e:
        print(f"Error editar: {e}")
        await interaction.followup.send("❌ No se pudo editar", ephemeral=True)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id: return
    if payload.user_id in traduciendo_users: return

    emoji = str(payload.emoji)
    if emoji not in BANDERAS: return

    idioma = BANDERAS[emoji]
    lock_key = f"{payload.message_id}:{idioma}"

    # ANTI SPAM: Si ya se está traduciendo este mensaje a este idioma, salir
    if lock_key in traducciones_activas: return

    traducciones_activas.add(lock_key)
    traduciendo_users.add(payload.user_id)

    try:
        channel = bot.get_channel(payload.channel_id)
        if channel is None: return
        message = await channel.fetch_message(payload.message_id)

        try:
            user = await bot.fetch_user(payload.user_id)
            await message.remove_reaction(payload.emoji, user)
        except: pass

        # Solo últimos 50 mensajes
        encontrado = False
        async for msg in channel.history(limit=50):
            if msg.id == message.id:
                encontrado = True
                break
        if not encontrado: return

        texto_a_traducir = ""
        if payload.message_id in mensajes_con_banderas:
            texto_a_traducir = mensajes_con_banderas[payload.message_id]["texto_es"]
        elif payload.channel_id in flag_mode_channels and not message.author.bot:
            texto_a_traducir = message.content

        if not texto_a_traducir or len(texto_a_traducir.strip()) < 2: return

        traduccion = await traducir_seguro(texto_a_traducir, idioma)

        # Si falló, avisar por DM sin spamear canal
        if "⚠️" in traduccion:
            try:
                await user.send(f"❌ No pude traducir ese mensaje a {NOMBRES_IDIOMAS[idioma]}. Intenta más tarde.")
            except: pass
            return

        delete_timer = 40 if idioma == 'tr' else 20

        if idioma in ['es', 'en', 'tr']:
            flag_emoji = '🇪🇸' if idioma == 'es' else '🇺🇸' if idioma == 'en' else '🇹🇷'
            embed = discord.Embed(description=f"{flag_emoji} {traduccion}", color=0x00B0F4)
            await channel.send(embed=embed, delete_after=delete_timer)
        else:
            nombre = NOMBRES_IDIOMAS.get(idioma, idioma)
            embed_dm = discord.Embed(title=f"{emoji} Traducción a {nombre}", color=0x00FF00)
            embed_dm.add_field(name="Original", value=texto_a_traducir[:1024], inline=False)
            embed_dm.add_field(name="Traducción", value=traduccion, inline=False)
            await user.send(embed=embed_dm)

    except Exception as e:
        print(f"[ERROR REACCIÓN] {e}")
    finally:
        await asyncio.sleep(1)
        traducciones_activas.discard(lock_key)
        traduciendo_users.discard(payload.user_id)

# PUERTO FAKE PA RENDER
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
bot.run(TOKEN)
