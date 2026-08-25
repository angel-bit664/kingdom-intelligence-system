import discord
from discord.ext import commands, tasks
import asyncio
import re
import os
import sqlite3
import time
import logging
from logging.handlers import RotatingFileHandler
from deep_translator import GoogleTranslator, MyMemoryTranslator, single_detection
from datetime import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict
import hashlib
from typing import Dict, Optional
import psutil

TOKEN = os.getenv("DISCORD_TOKEN")

# LOGGING
log = logging.getLogger('META_BOT')
log.setLevel(logging.INFO)
handler = RotatingFileHandler('bot.log', maxBytes=2*1024*1024, backupCount=1)
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
log.addHandler(handler)

# IDS - ESTOS 5 CANALES TENDRÁN AUTOTRADUCIR ON SIEMPRE
ID_CANAL_ACTIVATE = 1358237524249542751
ID_CANAL_ANUNCIOS = 1358237524249542751
ID_CANAL_BUFF = 1358237524249542751
ID_CANAL_OFICIALES = 1358237525214236705
ID_CANAL_BITACORA = 1362642374429245440
ID_CANAL_DIPLOMACIA = 1358237524799131664
ID_CANAL_GENERAL = 1358237524799131662

CANALES_AUTOTRADUCIR_DEFAULT = [
    ID_CANAL_OFICIALES, ID_CANAL_BITACORA, ID_CANAL_DIPLOMACIA,
    ID_CANAL_ANUNCIOS, ID_CANAL_GENERAL
]

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
bot = commands.Bot(command_prefix="meta ", case_insensitive=True, intents=intents, max_messages=1000, help_command=None)

# DB SQLITE
def init_db():
    conn = sqlite3.connect('meta_bot.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS traducciones
                    (hash TEXT PRIMARY KEY, texto TEXT, destino TEXT, resultado TEXT, timestamp REAL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS config
                    (guild_id INTEGER, user_id INTEGER, idioma TEXT, PRIMARY KEY (guild_id, user_id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS canales_activos (channel_id INTEGER PRIMARY KEY)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS ultimos_anuncios
                    (guild_id INTEGER, channel_id INTEGER, message_id INTEGER, tipo TEXT, PRIMARY KEY (guild_id, channel_id, tipo))''')
    for canal_id in CANALES_AUTOTRADUCIR_DEFAULT:
        conn.execute('INSERT OR IGNORE INTO canales_activos VALUES (?)', (canal_id,))
    conn.commit()
    return conn

db = init_db()

# SISTEMAS
class CircuitBreaker:
    def __init__(self, fail_max=5, reset_timeout=30):
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure = 0
        self.state = 'CLOSED'

    def call_allowed(self):
        if self.state == 'OPEN':
            if time.time() - self.last_failure > self.reset_timeout:
                self.state = 'HALF_OPEN'
                return True
            return False
        return True

    def record_success(self):
        self.failures = 0
        self.state = 'CLOSED'

    def record_failure(self):
        self.failures += 1
        self.last_failure = time.time()
        if self.failures >= self.fail_max:
            self.state = 'OPEN'
            log.warning(f"Circuit breaker OPEN por {self.reset_timeout}s")

google_cb = CircuitBreaker()
translation_queue = asyncio.Queue(maxsize=100)
user_cooldowns: Dict[int, float] = defaultdict(float)
message_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
stats = {'traducidas': 0, 'comandos': 0, 'errores': 0, 'inicio': time.time()}

BANDERAS = {
    '🇧🇷': 'pt', '🇫🇷': 'fr', '🇩🇪': 'de', '🇮🇹': 'it', '🇷🇺': 'ru',
    '🇯🇵': 'ja', '🇰🇷': 'ko', '🇨🇳': 'zh', '🇮🇩': 'id', '🇺🇸': 'en',
    '🇪🇸': 'es', '🇹🇷': 'tr', '🇸🇦': 'ar', '🇹🇭': 'th', '🇻🇳': 'vi'
}

NOMBRES_IDIOMAS = {
    'pt': 'Portugués', 'fr': 'Francés', 'de': 'Alemán', 'it': 'Italiano',
    'ru': 'Ruso', 'ja': 'Japonés', 'ko': 'Coreano', 'zh': 'Chino',
    'id': 'Indonesio', 'en': 'Inglés', 'es': 'Español', 'tr': 'Turco',
    'ar': 'Árabe', 'th': 'Tailandés', 'vi': 'Vietnamita'
}

def canal_tiene_autotraducir(channel_id: int) -> bool:
    cursor = db.execute('SELECT 1 FROM canales_activos WHERE channel_id =?', (channel_id,))
    return cursor.fetchone() is not None

def get_cache_db(hash_texto: str) -> Optional[str]:
    cursor = db.execute('SELECT resultado FROM traducciones WHERE hash =? AND timestamp >?',
                        (hash_texto, time.time() - 86400*7))
    row = cursor.fetchone()
    return row[0] if row else None

def set_cache_db(hash_texto: str, texto: str, destino: str, resultado: str):
    db.execute('INSERT OR REPLACE INTO traducciones VALUES (?,?,?,?,?)',
               (hash_texto, texto[:500], destino, resultado, time.time()))
    db.commit()

def get_user_idioma(guild_id: int, user_id: int) -> Optional[str]:
    cursor = db.execute('SELECT idioma FROM config WHERE guild_id =? AND user_id =?', (guild_id, user_id))
    row = cursor.fetchone()
    return row[0] if row else None

def guardar_ultimo_anuncio(guild_id: int, channel_id: int, message_id: int, tipo: str):
    db.execute('INSERT OR REPLACE INTO ultimos_anuncios VALUES (?,?,?,?)', (guild_id, channel_id, message_id, tipo))
    db.commit()

def get_ultimo_anuncio(guild_id: int, channel_id: int, tipo: str) -> Optional[int]:
    cursor = db.execute('SELECT message_id FROM ultimos_anuncios WHERE guild_id =? AND channel_id =? AND tipo =?',
                        (guild_id, channel_id, tipo))
    row = cursor.fetchone()
    return row[0] if row else None

async def traducir_seguro_v5(texto: str, destino: str, forzar: bool = False) -> Optional[str]:
    if not texto or len(texto.strip()) < 2:
        return "⚠️ Texto muy corto"

    texto_limpio = re.sub(r'<@!?\d+>|<@&\d+>|@\w+|<#[^>]+>|<a?:\w+:\d+>', '', texto).strip()
    if len(texto_limpio) < 2:
        return "⚠️ Solo menciones/emojis"

    if not forzar:
        try:
            idioma_origen = await asyncio.to_thread(single_detection, texto_limpio, api_key=None)
            if idioma_origen == destino:
                return None
        except:
            pass

    hash_texto = hashlib.md5(f"{texto_limpio}:{destino}".encode()).hexdigest()
    cached = get_cache_db(hash_texto)
    if cached:
        return cached

    if google_cb.call_allowed():
        for intento in range(2):
            try:
                resultado = await asyncio.wait_for(
                    asyncio.to_thread(GoogleTranslator(source='auto', target=destino).translate, texto_limpio),
                    timeout=5.0
                )
                if resultado and 'error' not in resultado.lower():
                    google_cb.record_success()
                    resultado = resultado[:1024]
                    set_cache_db(hash_texto, texto_limpio, destino, resultado)
                    stats['traducidas'] += 1
                    return resultado
            except:
                await asyncio.sleep(1)
        google_cb.record_failure()

    try:
        resultado = await asyncio.wait_for(
            asyncio.to_thread(MyMemoryTranslator(source='auto', target=destino).translate, texto_limpio),
            timeout=5.0
        )
        if resultado and 'error' not in resultado.lower():
            resultado = resultado[:1024]
            set_cache_db(hash_texto, texto_limpio, destino, resultado)
            stats['traducidas'] += 1
            return resultado
    except Exception as e:
        log.error(f"Trad fallo MyMemory: {e}")
        stats['errores'] += 1

    return "⚠️ Servicios de traducción saturados. Intenta en 5 min"

async def translation_worker():
    while True:
        try:
            task = await translation_queue.get()
            if task is None: break
            msg, user, idioma, texto, es_bandera = task
            traduccion = await traducir_seguro_v5(texto, idioma, forzar=es_bandera)

            if not traduccion:
                continue

            if "⚠️" in traduccion:
                try: await user.send(f"❌ No pude traducir a {NOMBRES_IDIOMAS[idioma]}")
                except: pass
                continue

            if idioma in ['es', 'en', 'tr']:
                flag = '🇪🇸' if idioma == 'es' else '🇺🇸' if idioma == 'en' else '🇹🇷'
                embed = discord.Embed(description=f"{flag} {traduccion}", color=0x00B0F4)
                await msg.channel.send(embed=embed, delete_after=40 if idioma == 'tr' else 20)
            else:
                embed = discord.Embed(title=f"{NOMBRES_IDIOMAS[idioma]}", color=0x00FF00)
                embed.add_field(name="Original", value=texto[:1024], inline=False)
                embed.add_field(name="Traducción", value=traduccion, inline=False)
                await user.send(embed=embed)
        except Exception as e:
            log.error(f"Worker error: {e}")
        finally:
            translation_queue.task_done()

@bot.event
async def on_ready():
    log.info(f'{bot.user} V5 PREFIX META ON - Autotraducir activo en 5 canales')
    for _ in range(5):
        bot.loop.create_task(translation_worker())
    limpiar_db_old.start()

@tasks.loop(hours=6)
async def limpiar_db_old():
    db.execute('DELETE FROM traducciones WHERE timestamp <?', (time.time() - 86400*7,))
    db.commit()
    log.info("DB limpia: borradas traducciones >7 días")

def tiene_cooldown(user_id: int) -> bool:
    ahora = time.time()
    if ahora - user_cooldowns[user_id] < 2.5:
        return True
    user_cooldowns[user_id] = ahora
    return False

# COMANDOS CON PREFIX "meta"
@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🟢 {round(bot.latency*1000)}ms")

@bot.command(name="health")
async def health(ctx):
    uptime = int(time.time() - stats['inicio'])
    ram = psutil.Process().memory_info().rss / 1024
    embed = discord.Embed(title="🟢 META BOT HEALTH", color=0x00FF00)
    embed.add_field(name="Uptime", value=f"{uptime//3600}h {(uptime%3600)//60}m", inline=True)
    embed.add_field(name="RAM", value=f"{ram:.1f}MB / 512MB", inline=True)
    embed.add_field(name="Latencia", value=f"{round(bot.latency*1000)}ms", inline=True)
    embed.add_field(name="Traducidas", value=str(stats['traducidas']), inline=True)
    embed.add_field(name="Comandos", value=str(stats['comandos']), inline=True)
    embed.add_field(name="Errores", value=str(stats['errores']), inline=True)
    embed.add_field(name="Circuit Breaker", value=google_cb.state, inline=True)
    embed.add_field(name="Queue", value=f"{translation_queue.qsize()}/100", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="fix")
@commands.has_permissions(administrator=True)
async def fix(ctx):
    global google_cb
    google_cb = CircuitBreaker()
    await ctx.send("✅ Circuit Breaker reseteado. Ya debería traducir")

@bot.command(name="activate")
async def activate(ctx, usuario: discord.Member, *, mensaje=""):
    if tiene_cooldown(ctx.author.id):
        return await ctx.send("⏳ Espera 2.5s", delete_after=3)
    stats['comandos'] += 1

    texto_en = await traducir_seguro_v5(mensaje, 'en') if mensaje else ""
    if texto_en and "⚠️" in texto_en: texto_en = ""
    mensaje_extra = f"\n\n💬 MENSAJE:\n🇲🇽 {mensaje}\n🇺🇸 {texto_en}" if mensaje else ""
    descripcion = f"🚨 CÓDIGO DE EMERGENCIA TFT 🚨\n⚠️ ALERTA ROJA\n🎯 OBJETIVO: {usuario.mention}\n❌ ESTADO: SIN ESCUDO ACTIVO\n🛡️ PROTOCOLO: 1. MUÉVETE YA 2. ESCUDO 8H 3. TELEPORT{mensaje_extra}"[:4096]

    embed = discord.Embed(description=descripcion, color=0xFF0000)
    canal = bot.get_channel(ID_CANAL_ACTIVATE) or ctx.channel
    msg = await canal.send(content=usuario.mention, embed=embed)
    guardar_ultimo_anuncio(ctx.guild.id, canal.id, msg.id, "activate")
    await ctx.message.add_reaction("✅")

@bot.command(name="alerta")
async def alerta(ctx, *, texto: str):
    if tiene_cooldown(ctx.author.id):
        return await ctx.send("⏳ Espera 2.5s", delete_after=3)
    stats['comandos'] += 1

    texto_en = await traducir_seguro_v5(texto, 'en')
    if not texto_en or "⚠️" in texto_en: texto_en = "Translation failed"
    embed = discord.Embed(title="🚨 ALERTA", color=0x3498DB)
    embed.add_field(name="🇲🇽 Español", value=texto[:1024], inline=False)
    embed.add_field(name="🇺🇸 English", value=texto_en, inline=False)

    canal = bot.get_channel(ID_CANAL_ANUNCIOS) or ctx.channel
    msg = await canal.send("@everyone", embed=embed)
    guardar_ultimo_anuncio(ctx.guild.id, canal.id, msg.id, "alerta")
    await ctx.message.add_reaction("✅")

@bot.command(name="evento")
async def evento(ctx, *, texto: str):
    if tiene_cooldown(ctx.author.id):
        return await ctx.send("⏳ Espera 2.5s", delete_after=3)
    stats['comandos'] += 1

    texto_en = await traducir_seguro_v5(texto, 'en')
    if not texto_en or "⚠️" in texto_en: texto_en = "Translation failed"
    embed = discord.Embed(title="⚔️ EVENTO", color=0xE67E22)
    embed.add_field(name="🇲🇽 Español", value=texto[:1024], inline=False)
    embed.add_field(name="🇺🇸 English", value=texto_en, inline=False)

    canal = bot.get_channel(ID_CANAL_ANUNCIOS) or ctx.channel
    msg = await canal.send("@everyone", embed=embed)
    guardar_ultimo_anuncio(ctx.guild.id, canal.id, msg.id, "evento")
    await ctx.message.add_reaction("✅")

@bot.command(name="buffo")
async def buffo(ctx, *, texto: str):
    if tiene_cooldown(ctx.author.id):
        return await ctx.send("⏳ Espera 2.5s", delete_after=3)
    stats['comandos'] += 1

    texto_en = await traducir_seguro_v5(texto, 'en')
    if not texto_en or "⚠️" in texto_en: texto_en = "Translation failed"
    embed = discord.Embed(title="🛎️ BUFO ACTIVADO", color=0x9B59B6)
    embed.add_field(name="🇲🇽 Español", value=f"✅ {texto[:1024]}", inline=False)
    embed.add_field(name="🇺🇸 English", value=f"✅ {texto_en}", inline=False)

    canal = bot.get_channel(ID_CANAL_BUFF) or ctx.channel
    msg = await canal.send("@everyone", embed=embed)
    guardar_ultimo_anuncio(ctx.guild.id, canal.id, msg.id, "buffo")
    await ctx.message.add_reaction("✅")

@bot.command(name="cumpleaños")
async def cumpleaños(ctx, usuario: discord.Member, *, mensaje=""):
    if tiene_cooldown(ctx.author.id):
        return await ctx.send("⏳ Espera 2.5s", delete_after=3)
    stats['comandos'] += 1

    if mensaje:
        texto_en = await traducir_seguro_v5(mensaje, 'en')
        if not texto_en or "⚠️" in texto_en: texto_en = mensaje
        mensaje_es, mensaje_en = mensaje, texto_en
    else:
        mensaje_es = f"¡Feliz cumpleaños {usuario.display_name}! 🎉🎂"
        mensaje_en = f"Happy birthday {usuario.display_name}! 🎉🎂"

    embed = discord.Embed(title="🎂 ¡FELIZ CUMPLEAÑOS!", color=0xFF69B4)
    embed.add_field(name="🇲🇽 Español", value=mensaje_es, inline=False)
    embed.add_field(name="🇺🇸 English", value=mensaje_en, inline=False)
    embed.set_thumbnail(url=usuario.display_avatar.url)

    canal = bot.get_channel(ID_CANAL_ANUNCIOS) or ctx.channel
    msg = await canal.send(content=f"{usuario.mention} @everyone", embed=embed)
    guardar_ultimo_anuncio(ctx.guild.id, canal.id, msg.id, "cumpleaños")
    await ctx.message.add_reaction("✅")

@bot.command(name="editar")
@commands.has_permissions(manage_messages=True)
async def editar(ctx, *, texto: str):
    if tiene_cooldown(ctx.author.id):
        return await ctx.send("⏳ Espera 2.5s", delete_after=3)

    tipos = ["activate", "alerta", "evento", "buffo", "cumpleaños"]
    ultimo_id = None
    ultimo_tipo = None
    for tipo in tipos:
        msg_id = get_ultimo_anuncio(ctx.guild.id, ctx.channel.id, tipo)
        if msg_id:
            ultimo_id = msg_id
            ultimo_tipo = tipo
            break

    if not ultimo_id:
        return await ctx.send("❌ No encontré anuncios recientes del bot para editar")

    try:
        mensaje = await ctx.channel.fetch_message(ultimo_id)
        texto_en = await traducir_seguro_v5(texto, 'en')
        if not texto_en or "⚠️" in texto_en: texto_en = "Translation failed"

        if ultimo_tipo == "activate":
            descripcion = f"🚨 CÓDIGO DE EMERGENCIA TFT 🚨\n⚠️ ALERTA ROJA\n💬 MENSAJE:\n🇲🇽 {texto}\n🇺🇸 {texto_en}"[:4096]
            embed = discord.Embed(description=descripcion, color=0xFF0000)
        elif ultimo_tipo == "alerta":
            embed = discord.Embed(title="🚨 ALERTA", color=0x3498DB)
            embed.add_field(name="🇲🇽 Español", value=texto[:1024], inline=False)
            embed.add_field(name="🇺🇸 English", value=texto_en, inline=False)
        elif ultimo_tipo == "evento":
            embed = discord.Embed(title="⚔️ EVENTO", color=0xE67E22)
            embed.add_field(name="🇲🇽 Español", value=texto[:1024], inline=False)
            embed.add_field(name="🇺🇸 English", value=texto_en, inline=False)
        elif ultimo_tipo == "buffo":
            embed = discord.Embed(title="🛎️ BUFO ACTIVADO", color=0x9B59B6)
            embed.add_field(name="🇲🇽 Español", value=f"✅ {texto[:1024]}", inline=False)
            embed.add_field(name="🇺🇸 English", value=f"✅ {texto_en}", inline=False)
        else:
            embed = mensaje.embeds[0]

        await mensaje.edit(embed=embed)
        await ctx.message.add_reaction("✅")
    except Exception as e:
        await ctx.send(f"❌ Error al editar: {e}")

@bot.command(name="limpia")
@commands.has_permissions(manage_messages=True)
async def limpia(ctx, cantidad: int = 10):
    if cantidad > 50:
        return await ctx.send("❌ Máximo 50 mensajes")

    def es_bot(m):
        return m.author == bot.user

    borrados = await ctx.channel.purge(limit=cantidad, check=es_bot)
    await ctx.send(f"✅ Borré {len(borrados)} mensajes del bot", delete_after=5)

@bot.command(name="idioma")
async def idioma(ctx, *, idioma_nuevo: str):
    idioma_lower = idioma_nuevo.lower()
    codigos = {v.lower(): k for k, v in NOMBRES_IDIOMAS.items()}
    if idioma_lower not in codigos:
        return await ctx.send(f"❌ Idioma no válido. Usa: {', '.join(NOMBRES_IDIOMAS.values())}")

    codigo = codigos[idioma_lower]
    db.execute('INSERT OR REPLACE INTO config VALUES (?,?,?)', (ctx.guild.id, ctx.author.id, codigo))
    db.commit()
    await ctx.send(f"✅ Ahora te autotraduzco todo a {NOMBRES_IDIOMAS[codigo]}")

@bot.command(name="autotraducir")
@commands.has_permissions(manage_channels=True)
async def autotraducir_cmd(ctx, estado: str):
    if estado.lower() in ['on', 'true', 'si', '1']:
        db.execute('INSERT OR IGNORE INTO canales_activos VALUES (?)', (ctx.channel.id,))
        await ctx.send("✅ Autotraducir ON")
    else:
        db.execute('DELETE FROM canales_activos WHERE channel_id =?', (ctx.channel.id,))
        await ctx.send("❌ Autotraducir OFF")
    db.commit()

@bot.command(name="ayuda")
async def ayuda(ctx):
    embed = discord.Embed(title="📋 COMANDOS META BOT", color=0x9B59B6)

    embed.add_field(name="🚨 meta activate @usuario [mensaje]", value="Código de emergencia ES/EN", inline=False)
    embed.add_field(name="🎂 meta cumpleaños @usuario [mensaje]", value="Felicitación ES/EN", inline=False)
    embed.add_field(name="📢 meta alerta <texto>", value="Alerta ES/EN", inline=False)
    embed.add_field(name="⚔️ meta evento <texto>", value="Evento ES/EN", inline=False)
    embed.add_field(name="🛎️ meta buffo <texto>", value="Bufo ES/EN + @everyone", inline=False)
    embed.add_field(name="✏️ meta editar <texto>", value="Edita el último anuncio del bot", inline=False)
    embed.add_field(name="🧹 meta limpia [cantidad]", value="Borra mensajes del bot | Max 50", inline=False)
    embed.add_field(name="🟢 meta ping", value="Verifica latencia", inline=False)
    embed.add_field(name="🌍 Traductor", value="Siempre activo en #oficiales, #diplomacia, #bitácora y #anuncios", inline=False)
    embed.add_field(name="🌍 Banderas", value="Reacciona con 🇺🇸🇧🇷🇯🇵🇫🇷🇩🇪🇮🇹🇷🇺🇰🇷🇨🇳🇮🇩🇹🇷 pa traducir", inline=False)

    embed.set_footer(text="META ESTÁ CONTIGO. UN REINO, UNA ALIANZA UNA META")
    await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    if canal_tiene_autotraducir(message.channel.id):
        idioma_destino = get_user_idioma(message.guild.id, message.author.id)
        if idioma_destino:
            await translation_queue.put((message, message.author, idioma_destino, message.content, False))

    await bot.process_commands(message)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id: return
    emoji = str(payload.emoji)
    if emoji not in BANDERAS: return

    lock_key = f"{payload.message_id}:{payload.user_id}"
    async with message_locks[lock_key]:
        try:
            channel = bot.get_channel(payload.channel_id)
            if not channel: return
            message = await channel.fetch_message(payload.message_id)

            try:
                user = await bot.fetch_user(payload.user_id)
                await message.remove_reaction(payload.emoji, user)
            except: pass

            if not canal_tiene_autotraducir(payload.channel_id) or message.author.bot:
                return

            texto = message.content
            if not texto: return

            idioma = BANDERAS[emoji]
            await translation_queue.put((message, user, idioma, texto, True))
        except Exception as e:
            log.error(f"Reacción error: {e}")

# WEB SERVER PA UPTIMEROBOT
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args): pass

threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 10000), Handler).serve_forever(), daemon=True).start()
bot.run(TOKEN)
