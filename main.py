import asyncio
import os
import random
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import discord
from deep_translator import GoogleTranslator, MyMemoryTranslator

try:
    from groq import AsyncGroq
except ImportError:
    AsyncGroq = None

# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL_CONFIG = os.getenv("GROQ_MODEL", "").strip()

if not TOKEN:
    raise RuntimeError("Falta DISCORD_TOKEN en Render.")

# Modelos actuales de Groq. El primero disponible será usado.
GROQ_MODELOS_DEPRECADOS = {
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen/qwen3-32b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
}

GROQ_MODELOS = []
for model in [
    GROQ_MODEL_CONFIG,
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
]:
    if model and model not in GROQ_MODELOS_DEPRECADOS and model not in GROQ_MODELOS:
        GROQ_MODELOS.append(model)

if not GROQ_MODELOS:
    GROQ_MODELOS = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.6-27b",
    ]

# ============================================================
# CANALES
# ============================================================

ID_CANAL_ACTIVATE = 1358237524249542751
ID_CANAL_ANUNCIOS = 1358237524249542751
ID_CANAL_BUFF = 1358237524249542751

ID_CANAL_OFICIALES = 1358237525214236705
ID_CANAL_BITACORA = 1362642374429245440
ID_CANAL_DIPLOMACIA = 1358237524799131664
ID_CANAL_GENERAL = 1358237524799131662

CANALES_TRADUCCION_DIRECTA = {
    ID_CANAL_OFICIALES,
    ID_CANAL_DIPLOMACIA,
    ID_CANAL_GENERAL,
    ID_CANAL_BITACORA,
}

# ============================================================
# DISCORD
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
client = discord.Client(intents=intents)

# ============================================================
# MEMORIA / ESTADO
# ============================================================

mensajes_con_banderas = {}
ultimo_anuncio = {}
procesando_activate = set()
traduciendo_users = set()

translation_enabled = True
bot_started_at = time.time()

groq_client = None
translation_semaphore = None
cleanup_task = None
groq_model_actual = None
groq_model_index = 0

groq_failures = 0
google_failures = 0
mymemory_failures = 0

groq_last_error = None
google_last_error = None
mymemory_last_error = None

groq_last_success = None
google_last_success = None
mymemory_last_success = None

groq_circuit_open_until = 0.0
google_circuit_open_until = 0.0

CIRCUIT_FAILURE_LIMIT = 5
CIRCUIT_COOLDOWN = 120
MAX_TRANSLATIONS_CONCURRENT = 3
GOOGLE_RETRIES = 3
MYMEMORY_RETRIES = 2

# ============================================================
# IDIOMAS
# ============================================================

BANDERAS = {
    "🇧🇷": "pt", "🇫🇷": "fr", "🇩🇪": "de", "🇮🇹": "it",
    "🇷🇺": "ru", "🇯🇵": "ja", "🇰🇷": "ko", "🇨🇳": "zh",
    "🇮🇩": "id", "🇺🇸": "en", "🇪🇸": "es", "🇹🇷": "tr",
}

NOMBRES_IDIOMAS = {
    "pt": "Portugués", "fr": "Francés", "de": "Alemán",
    "it": "Italiano", "ru": "Ruso", "ja": "Japonés",
    "ko": "Coreano", "zh": "Chino", "id": "Indonesio",
    "en": "Inglés", "es": "Español", "tr": "Turco",
}

GOOGLE_TARGETS = {"zh": "zh-CN"}

MYMEMORY_TARGETS = {
    "pt": "pt-PT", "fr": "fr-FR", "de": "de-DE",
    "it": "it-IT", "ru": "ru-RU", "ja": "ja-JP",
    "ko": "ko-KR", "zh": "zh-CN", "id": "id-ID",
    "en": "en-US", "es": "es-ES", "tr": "tr-TR",
}

COLOR_META = 0x9B59B6
COLOR_ALERTA = 0x3498DB
COLOR_ACTIVATE = 0xFF0000
COLOR_CUMPLEANOS = 0xFF69B4
COLOR_TRADUCCION = 0x00B0F4
COLOR_EXITO = 0x00FF00

# ============================================================
# UTILIDADES
# ============================================================

def limitar_texto(texto, limite=1024):
    if texto is None:
        return ""
    texto = str(texto)
    return texto if len(texto) <= limite else texto[:limite - 3] + "..."

def limpiar_texto(texto):
    if not texto:
        return ""
    texto = re.sub(r"<@!?\d+>", "", texto)
    texto = re.sub(r"<@&\d+>", "", texto)
    texto = re.sub(r"<#\d+>", "", texto)
    texto = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", texto)
    return re.sub(r"\s+", " ", texto).strip()

def obtener_texto_sin_menciones(message):
    texto = message.content
    for usuario in message.mentions:
        texto = texto.replace(usuario.mention, "")
        texto = texto.replace(f"<@{usuario.id}>", "")
        texto = texto.replace(f"<@!{usuario.id}>", "")
    return limpiar_texto(texto)

def tiempo_desde(timestamp):
    if not timestamp:
        return "Nunca"
    s = max(0, int(time.time() - timestamp))
    if s < 60:
        return f"hace {s}s"
    m = s // 60
    if m < 60:
        return f"hace {m}m"
    return f"hace {m // 60}h"

# ============================================================
# GROQ ERROR HELPERS
# ============================================================

def status_code(error):
    return getattr(error, "status_code", None)

def es_modelo_no_disponible(error):
    code = status_code(error)
    text = str(error).lower()
    return (
        code == 404
        or (code == 403 and any(x in text for x in ("model", "permission", "access", "not found")))
        or any(x in text for x in (
            "model_not_found", "model does not exist",
            "do not have access to it", "model not found"
        ))
    )

def es_auth_error(error):
    code = status_code(error)
    text = str(error).lower()
    return code == 401 or any(
        x in text for x in ("invalid api key", "authentication", "unauthorized")
    )

def es_rate_limit(error):
    code = status_code(error)
    text = str(error).lower()
    return code == 429 or "rate limit" in text or "too many requests" in text

def es_transitorio(error):
    code = status_code(error)
    text = str(error).lower()
    return (
        code in {408, 409, 425, 500, 502, 503, 504}
        or any(x in text for x in (
            "timeout", "timed out", "connection",
            "temporarily unavailable", "server error"
        ))
    )

def modelos_en_orden():
    if not GROQ_MODELOS:
        return []
    return [
        (groq_model_index + i) % len(GROQ_MODELOS)
        for i in range(len(GROQ_MODELOS))
    ]

# ============================================================
# REINICIOS
# ============================================================

def reiniciar_groq():
    global groq_client, groq_failures, groq_last_error
    global groq_last_success, groq_circuit_open_until
    global groq_model_index, groq_model_actual

    groq_failures = 0
    groq_last_error = None
    groq_last_success = None
    groq_circuit_open_until = 0.0
    groq_model_index = 0
    groq_model_actual = GROQ_MODELOS[0] if GROQ_MODELOS else None

    if GROQ_API_KEY and AsyncGroq is not None:
        try:
            groq_client = AsyncGroq(api_key=GROQ_API_KEY)
            print(f"🔄 GROQ reiniciado → {groq_model_actual}")
            return True, "Groq fue reiniciado y quedó listo."
        except Exception as error:
            groq_client = None
            return False, f"No se pudo reconstruir Groq: {error}"

    groq_client = None
    return False, "Groq no está configurado o falta GROQ_API_KEY/librería."

def reiniciar_google():
    global google_failures, google_last_error
    global google_last_success, google_circuit_open_until
    google_failures = 0
    google_last_error = None
    google_last_success = None
    google_circuit_open_until = 0.0
    return True, "Google fue reiniciado."

def reiniciar_mymemory():
    global mymemory_failures, mymemory_last_error, mymemory_last_success
    mymemory_failures = 0
    mymemory_last_error = None
    mymemory_last_success = None
    return True, "MyMemory fue reiniciado."

def reiniciar_todo():
    a, b = reiniciar_groq()
    c, d = reiniciar_google()
    e, f = reiniciar_mymemory()
    return a, b, c, d, e, f

def puede_reiniciar(message):
    return bool(
        message.guild
        and getattr(message.author, "guild_permissions", None)
        and message.author.guild_permissions.administrator
    )

# ============================================================
# CIRCUITS
# ============================================================

def groq_disponible():
    return time.time() >= groq_circuit_open_until

def google_disponible():
    return time.time() >= google_circuit_open_until

def fallo_groq(error):
    global groq_failures, groq_last_error, groq_circuit_open_until
    groq_failures += 1
    groq_last_error = str(error)[:500]
    print(f"⚠️ GROQ FALLÓ ({groq_failures}/{CIRCUIT_FAILURE_LIMIT}): {error}")
    if groq_failures >= CIRCUIT_FAILURE_LIMIT:
        groq_circuit_open_until = time.time() + CIRCUIT_COOLDOWN
        print(f"🔌 CIRCUITO GROQ ABIERTO {CIRCUIT_COOLDOWN}s.")

def exito_groq():
    global groq_failures, groq_last_success, groq_last_error, groq_circuit_open_until
    groq_failures = 0
    groq_last_success = time.time()
    groq_last_error = None
    groq_circuit_open_until = 0.0

def fallo_google(error):
    global google_failures, google_last_error, google_circuit_open_until
    google_failures += 1
    google_last_error = str(error)[:500]
    print(f"⚠️ GOOGLE FALLÓ ({google_failures}/{CIRCUIT_FAILURE_LIMIT}): {error}")
    if google_failures >= CIRCUIT_FAILURE_LIMIT:
        google_circuit_open_until = time.time() + CIRCUIT_COOLDOWN

def exito_google():
    global google_failures, google_last_success, google_last_error, google_circuit_open_until
    google_failures = 0
    google_last_success = time.time()
    google_last_error = None
    google_circuit_open_until = 0.0

# ============================================================
# TRADUCTORES
# ============================================================

async def traducir_groq(texto, destino):
    global groq_model_index, groq_model_actual

    if groq_client is None:
        raise RuntimeError("Groq no está configurado.")
    if not groq_disponible():
        raise RuntimeError("Circuito Groq temporalmente cerrado.")

    idioma = NOMBRES_IDIOMAS.get(destino, destino)
    prompt = (
        "Traduce únicamente el mensaje al idioma indicado. "
        "No expliques, no respondas preguntas y no agregues información. "
        "Conserva nombres, números, horas, emojis y términos de gaming.\n\n"
        f"IDIOMA: {idioma}\nMENSAJE:\n{texto}"
    )

    ultimo = None

    for index in modelos_en_orden():
        model = GROQ_MODELOS[index]
        try:
            print(f"🧠 Probando Groq → {model}")

            response = await asyncio.wait_for(
                groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "Eres un traductor. Devuelve solo la traducción.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_completion_tokens=1200,
                    stream=False,
                ),
                timeout=15,
            )

            result = response.choices[0].message.content
            if not result:
                raise RuntimeError("Groq devolvió una respuesta vacía.")

            groq_model_index = index
            groq_model_actual = model
            exito_groq()

            print(f"🟢 GROQ OK → {model} → {destino}")
            return limitar_texto(result.strip())

        except asyncio.TimeoutError as error:
            ultimo = error
            print(f"⏱️ Timeout Groq → {model}")
            continue

        except Exception as error:
            ultimo = error

            if es_modelo_no_disponible(error):
                print(f"⚠️ Modelo no disponible → {model}")
                continue

            if es_auth_error(error):
                fallo_groq(error)
                raise

            if es_rate_limit(error):
                print(f"⏳ Rate limit → {model}")
                continue

            if es_transitorio(error):
                print(f"⚠️ Error transitorio → {model}: {error}")
                continue

            print(f"⚠️ Error Groq → {model}: {error}")
            continue

    fallo_groq(ultimo or "Todos los modelos Groq fallaron.")
    raise RuntimeError("Todos los modelos Groq fallaron.")

def google_sync(texto, destino):
    return GoogleTranslator(
        source="auto",
        target=GOOGLE_TARGETS.get(destino, destino),
    ).translate(texto)

async def traducir_google(texto, destino):
    if not google_disponible():
        raise RuntimeError("Circuito Google temporalmente cerrado.")

    ultimo = None

    for intento in range(1, GOOGLE_RETRIES + 1):
        try:
            await asyncio.sleep(random.uniform(0.3, 0.8))
            result = await asyncio.wait_for(
                asyncio.to_thread(google_sync, texto, destino),
                timeout=12,
            )

            if not result or not result.strip():
                raise RuntimeError("Google devolvió texto vacío.")

            exito_google()
            print(f"🟢 GOOGLE OK → {destino}")
            return limitar_texto(result.strip())

        except Exception as error:
            ultimo = error
            print(f"⚠️ GOOGLE {intento}/{GOOGLE_RETRIES}: {error}")

            if intento < GOOGLE_RETRIES:
                await asyncio.sleep(1.5 * intento)

    fallo_google(ultimo or "Google falló.")
    raise ultimo or RuntimeError("Google falló.")

def mymemory_sync(texto, destino):
    return MyMemoryTranslator(
        source="auto",
        target=MYMEMORY_TARGETS.get(destino, destino),
    ).translate(texto)

async def traducir_mymemory(texto, destino):
    global mymemory_failures, mymemory_last_error, mymemory_last_success

    ultimo = None

    for intento in range(1, MYMEMORY_RETRIES + 1):
        try:
            await asyncio.sleep(0.7)

            result = await asyncio.wait_for(
                asyncio.to_thread(mymemory_sync, texto, destino),
                timeout=15,
            )

            if not result or not result.strip():
                raise RuntimeError("MyMemory devolvió texto vacío.")

            # NO buscamos la palabra "error" en la traducción.
            # Podría ser una palabra legítima del texto traducido.
            mymemory_failures = 0
            mymemory_last_error = None
            mymemory_last_success = time.time()

            print(f"🆘 MYMEMORY OK → {destino}")
            return limitar_texto(result.strip())

        except Exception as error:
            ultimo = error
            print(f"⚠️ MYMEMORY {intento}/{MYMEMORY_RETRIES}: {error}")

            if intento < MYMEMORY_RETRIES:
                await asyncio.sleep(1.5)

    mymemory_failures += 1
    mymemory_last_error = str(ultimo)[:500]
    raise ultimo or RuntimeError("MyMemory falló.")

async def traducir_seguro(texto, destino):
    if not translation_enabled:
        return "⚠️ El sistema de traducción está temporalmente desactivado."

    texto = limpiar_texto(texto)[:5000]
    if not texto:
        return ""

    if translation_semaphore is None:
        raise RuntimeError("El sistema de traducción todavía no está listo.")

    async with translation_semaphore:
        try:
            return await traducir_groq(texto, destino)
        except Exception as error:
            print(f"🔄 Fallback Google: {error}")

        try:
            return await traducir_google(texto, destino)
        except Exception as error:
            print(f"🔄 Fallback MyMemory: {error}")

        try:
            return await traducir_mymemory(texto, destino)
        except Exception as error:
            print(f"❌ Todos los traductores fallaron: {error}")

    return "⚠️ No fue posible realizar la traducción en este momento. Intenta nuevamente más tarde."

async def corregir_y_traducir_ia(texto):
    texto = limpiar_texto(texto)

    if len(texto) < 3:
        return {"es": texto, "en": "⚠️ Message too short"}

    return {
        "es": limitar_texto(texto),
        "en": limitar_texto(await traducir_seguro(texto, "en")),
    }

# ============================================================
# EMBEDS / ESTADO
# ============================================================

def embed_traduccion(emoji, nombre, original, traduccion):
    embed = discord.Embed(
        title=f"{emoji} Traducción a {nombre}",
        color=COLOR_EXITO,
    )
    embed.add_field(name="Original", value=limitar_texto(original), inline=False)
    embed.add_field(name="Traducción", value=limitar_texto(traduccion), inline=False)
    embed.set_footer(text="META • Traducción privada")
    return embed

async def comando_estado(message):
    latency = round(client.latency * 1000)

    if latency < 150:
        discord_estado = "🟢 EXCELENTE"
    elif latency < 300:
        discord_estado = "🟢 NORMAL"
    elif latency < 600:
        discord_estado = "🟡 ALTA"
    else:
        discord_estado = "🔴 MUY ALTA"

    if groq_client is None:
        groq_estado = "🔴 NO CONFIGURADO"
    elif not groq_disponible():
        groq_estado = f"🟡 CIRCUITO ABIERTO ({max(0, int(groq_circuit_open_until-time.time()))}s)"
    else:
        groq_estado = f"🟢 ACTIVO\n{groq_model_actual or 'sin prueba'}"

    if not google_disponible():
        google_estado = f"🟡 CIRCUITO ABIERTO ({max(0, int(google_circuit_open_until-time.time()))}s)"
    elif google_last_success:
        google_estado = "🟢 ACTIVO"
    else:
        google_estado = "🟢 DISPONIBLE / SIN PRUEBA"

    if mymemory_last_success:
        mm_estado = "🟢 ACTIVO"
    elif mymemory_failures >= 3:
        mm_estado = "🟡 CON ERRORES"
    else:
        mm_estado = "🟢 DISPONIBLE / SIN PRUEBA"

    uptime = max(0, int(time.time() - bot_started_at))
    h, r = divmod(uptime, 3600)
    m, s = divmod(r, 60)

    embed = discord.Embed(
        title="🛡️ KINGDOM INTELLIGENCE SYSTEM",
        description="Diagnóstico del bot y del sistema de traducción.",
        color=COLOR_META,
    )

    embed.add_field(name="🤖 Discord", value=f"{discord_estado}\n{latency}ms", inline=True)
    embed.add_field(name="🧠 Groq", value=groq_estado, inline=True)
    embed.add_field(name="🌎 Google", value=google_estado, inline=True)
    embed.add_field(name="🆘 MyMemory", value=mm_estado, inline=True)
    embed.add_field(name="🌐 Traducción", value="🟢 ACTIVA" if translation_enabled else "🔴 DESACTIVADA", inline=True)
    embed.add_field(name="🚦 Protección", value=f"{MAX_TRANSLATIONS_CONCURRENT} simultáneas", inline=True)
    embed.add_field(name="⏱️ Uptime", value=f"{h}h {m}m {s}s", inline=False)

    embed.add_field(name="🔄 Último Groq", value=tiempo_desde(groq_last_success), inline=True)
    embed.add_field(name="🔄 Último Google", value=tiempo_desde(google_last_success), inline=True)
    embed.add_field(name="🔄 Último MyMemory", value=tiempo_desde(mymemory_last_success), inline=True)

    if groq_last_error:
        embed.add_field(name="⚠️ Error Groq", value=limitar_texto(groq_last_error, 500), inline=False)
    if google_last_error:
        embed.add_field(name="⚠️ Error Google", value=limitar_texto(google_last_error, 500), inline=False)
    if mymemory_last_error:
        embed.add_field(name="⚠️ Error MyMemory", value=limitar_texto(mymemory_last_error, 500), inline=False)

    embed.set_footer(text="META • Diagnóstico del sistema")
    await message.channel.send(embed=embed)

# ============================================================
# READY
# ============================================================

@client.event
async def on_ready():
    global groq_client, translation_semaphore, cleanup_task
    global groq_model_actual, groq_model_index

    if GROQ_API_KEY and AsyncGroq is not None and groq_client is None:
        try:
            groq_client = AsyncGroq(api_key=GROQ_API_KEY)
            groq_model_index = 0
            groq_model_actual = GROQ_MODELOS[0] if GROQ_MODELOS else None
        except Exception as error:
            print(f"⚠️ No se pudo inicializar Groq: {error}")

    if translation_semaphore is None:
        translation_semaphore = asyncio.Semaphore(MAX_TRANSLATIONS_CONCURRENT)

    if cleanup_task is None or cleanup_task.done():
        cleanup_task = asyncio.create_task(limpieza_memoria())

    print("=" * 65)
    print(f"🤖 {client.user} conectado.")
    print(f"🧠 Groq: {'CONFIGURADO' if groq_client else 'NO DISPONIBLE'}")
    print(f"🧠 Modelo: {groq_model_actual}")
    print("🔄 Fallback Groq:")
    for model in GROQ_MODELOS:
        print(f"   • {model}")
    print("🌎 Traducción: ACTIVA" if translation_enabled else "🌎 Traducción: DESACTIVADA")
    print("=" * 65)

# ============================================================
# COMANDOS
# ============================================================

@client.event
async def on_message(message):
    global translation_enabled

    if message.author.bot:
        return

    content = message.content.strip()
    if not content or not content.lower().startswith("meta "):
        return

    parts = content[5:].strip().split()
    if not parts:
        return

    command = parts[0].lower()
    args = " ".join(parts[1:]).strip()

    if command == "estado":
        await comando_estado(message)
        return

    if command == "traduccion":
        option = args.lower()

        if option == "off":
            translation_enabled = False
            await message.channel.send("🛑 Sistema de traducción desactivado.", delete_after=8)
        elif option == "on":
            translation_enabled = True
            await message.channel.send("🟢 Sistema de traducción activado.", delete_after=8)
        else:
            await message.channel.send("❌ Usa `meta traduccion on` o `meta traduccion off`")
        return

    if command == "reiniciar":
        if not puede_reiniciar(message):
            await message.channel.send(
                "🔒 Solo un administrador puede reiniciar los servicios.",
                delete_after=8,
            )
            return

        service = args.lower()

        if service in ("groq", "grok"):
            ok, msg = reiniciar_groq()
            await message.channel.send(("🟢 " if ok else "🔴 ") + msg, delete_after=10)
            return

        if service == "google":
            ok, msg = reiniciar_google()
            await message.channel.send(("🟢 " if ok else "🔴 ") + msg, delete_after=10)
            return

        if service in ("mymemory", "my-memory"):
            ok, msg = reiniciar_mymemory()
            await message.channel.send(("🟢 " if ok else "🔴 ") + msg, delete_after=10)
            return

        if service in ("todo", "traductor", "traduccion", "traducción"):
            a,b,c,d,e,f = reiniciar_todo()
            estado = "🟢" if a and c and e else "🟡"
            await message.channel.send(
                f"{estado} Sistema reiniciado.\n"
                f"🧠 {b}\n🌎 {d}\n🆘 {f}\n"
                f"📌 Modelo: {groq_model_actual}",
                delete_after=14,
            )
            return

        await message.channel.send(
            "🔄 Usa:\n"
            "`meta reiniciar groq`\n"
            "`meta reiniciar google`\n"
            "`meta reiniciar mymemory`\n"
            "`meta reiniciar todo`",
            delete_after=12,
        )
        return

    if command == "activate":
        if message.author.id in procesando_activate:
            try: await message.delete()
            except Exception: pass
            return

        if not message.mentions:
            await message.channel.send("❌ `meta activate @usuario [mensaje]`")
            return

        procesando_activate.add(message.author.id)

        try:
            user = message.mentions[0]
            text = obtener_texto_sin_menciones(message)
            data = await corregir_y_traducir_ia(text)

            extra = (
                "\n\n💬 MENSAJE / MESSAGE:\n"
                f"🇲🇽 {data['es']}\n"
                f"🇺🇸 {data['en']}"
            )

            description = (
                "🚨 CÓDIGO DE EMERGENCIA TFT 🚨\n"
                "⚠️ ALERTA ROJA\n"
                f"🎯 OBJETIVO: {user.mention}\n"
                "❌ ESTADO: SIN ESCUDO ACTIVO\n"
                "🛡️ PROTOCOLO:\n"
                "1. MUÉVETE YA\n"
                "2. ESCUDO 8H\n"
                "3. TELEPORT"
                + extra
            )

            embed = discord.Embed(
                description=description[:4096],
                color=COLOR_ACTIVATE,
            )
            embed.set_footer(text="Agrega una bandera al mensaje para solicitar traducción.")

            channel = client.get_channel(ID_CANAL_ACTIVATE) or message.channel
            published = await channel.send(content=user.mention, embed=embed)

            mensajes_con_banderas[published.id] = {
                "texto_es": data["es"],
                "tipo": "activate",
            }

            try: await message.delete()
            except Exception: pass

        except Exception as error:
            print(f"[ERROR ACTIVATE] {error}")
            await message.channel.send("❌ Ocurrió un error al activar el protocolo.")
        finally:
            procesando_activate.discard(message.author.id)

        return

    if command == "cumpleaños":
        if not message.mentions:
            await message.channel.send("❌ `meta cumpleaños @usuario [mensaje]`")
            return

        user = message.mentions[0]
        custom = obtener_texto_sin_menciones(message)

        try: await message.delete()
        except Exception: pass

        if custom:
            data = await corregir_y_traducir_ia(custom)
            es, en = data["es"], data["en"]
        else:
            es = f"¡Feliz cumpleaños {user.display_name}! 🎉🎂 Que tengas un día increíble."
            en = f"Happy birthday {user.display_name}! 🎉🎂 Have an amazing day."

        embed = discord.Embed(title="🎂 ¡FELIZ CUMPLEAÑOS!", color=COLOR_CUMPLEANOS)
        embed.add_field(name="🇲🇽 Español", value=limitar_texto(es), inline=False)
        embed.add_field(name="🇺🇸 English", value=limitar_texto(en), inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Agrega una bandera al mensaje para solicitar traducción.")

        channel = client.get_channel(ID_CANAL_ANUNCIOS) or message.channel
        published = await channel.send(content=f"{user.mention} @everyone", embed=embed)

        mensajes_con_banderas[published.id] = {"texto_es": es, "tipo": "cumpleaños"}
        ultimo_anuncio[message.channel.id] = published
        return

    if command in ("evento", "alerta"):
        if not args:
            return

        try: await message.delete()
        except Exception: pass

        waiting = await message.channel.send("⏳ Corrigiendo y traduciendo...")
        try:
            data = await corregir_y_traducir_ia(args)
        finally:
            try: await waiting.delete()
            except Exception: pass

        title = "⚔️ EVENTO" if command == "evento" else "🚨 ALERTA"
        embed = discord.Embed(title=title, color=COLOR_ALERTA)
        embed.add_field(name="🇲🇽 Español", value=limitar_texto(data["es"]), inline=False)
        embed.add_field(name="🇺🇸 English", value=limitar_texto(data["en"]), inline=False)
        embed.set_footer(text="Agrega una bandera al mensaje para solicitar traducción.")

        channel = client.get_channel(ID_CANAL_ANUNCIOS) or message.channel
        published = await channel.send(content="@everyone", embed=embed)

        mensajes_con_banderas[published.id] = {"texto_es": data["es"], "tipo": command}
        ultimo_anuncio[message.channel.id] = published
        return

    if command in ("buffo", "bufo", "buff"):
        if not args:
            return

        try: await message.delete()
        except Exception: pass

        data = await corregir_y_traducir_ia(args)

        embed = discord.Embed(title="🛎️ BUFO ACTIVADO", color=COLOR_META)
        embed.add_field(name="🇲🇽 Español", value=f"✅ {limitar_texto(data['es'])}", inline=False)
        embed.add_field(name="🇺🇸 English", value=f"✅ {limitar_texto(data['en'])}", inline=False)
        embed.set_footer(text="Agrega una bandera al mensaje para solicitar traducción.")

        channel = client.get_channel(ID_CANAL_BUFF) or message.channel
        published = await channel.send(content="@everyone", embed=embed)

        mensajes_con_banderas[published.id] = {"texto_es": data["es"], "tipo": "buffo"}
        ultimo_anuncio[message.channel.id] = published
        return

    if command == "editar":
        if not args:
            await message.channel.send("❌ `meta editar nuevo texto`")
            return

        if message.channel.id not in ultimo_anuncio:
            await message.channel.send("❌ No hay anuncio reciente para editar.")
            return

        published = ultimo_anuncio[message.channel.id]
        data = await corregir_y_traducir_ia(args)

        try:
            if not published.embeds:
                raise RuntimeError("El mensaje no tiene embed.")

            embed = published.embeds[0]
            embed.clear_fields()
            title = embed.title or ""

            if "CUMPLEAÑOS" in title:
                embed.add_field(name="🇲🇽 Español", value=data["es"], inline=False)
                embed.add_field(name="🇺🇸 English", value=data["en"], inline=False)
            elif "BUFO" in title:
                embed.add_field(name="🇲🇽 Español", value=f"✅ {data['es']}", inline=False)
                embed.add_field(name="🇺🇸 English", value=f"🇺🇸 {data['en']}", inline=False)
            else:
                embed.add_field(name="🇲🇽 Español", value=data["es"], inline=False)
                embed.add_field(name="🇺🇸 English", value=data["en"], inline=False)

            await published.edit(embed=embed)

            if published.id in mensajes_con_banderas:
                mensajes_con_banderas[published.id]["texto_es"] = data["es"]

            try: await message.delete()
            except Exception: pass

            await message.channel.send("✅ Anuncio editado.", delete_after=5)

        except Exception as error:
            print(f"[ERROR EDITAR] {error}")
            await message.channel.send("❌ No se pudo editar el anuncio.")
        return

    if command == "limpia":
        amount = int(args) if args.isdigit() else 10
        amount = max(1, min(amount, 50))

        try: await message.delete()
        except Exception: pass

        deleted = 0
        try:
            async for msg in message.channel.history(limit=100):
                if client.user and msg.author.id == client.user.id:
                    try:
                        await msg.delete()
                        deleted += 1
                        if deleted >= amount:
                            break
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass
        except Exception as error:
            print(f"[ERROR LIMPIA] {error}")

        await message.channel.send(
            f"🧹 Borrados {deleted} mensajes del bot.",
            delete_after=5,
        )
        return

    if command == "ping":
        await message.channel.send(f"🟢 Latencia: {round(client.latency * 1000)}ms")
        return

    if command == "ayuda":
        embed = discord.Embed(title="📋 COMANDOS META BOT", color=COLOR_META)
        commands = [
            ("🚨 meta activate @usuario [mensaje]", "Código de emergencia ES/EN"),
            ("🎂 meta cumpleaños @usuario [mensaje]", "Felicitación ES/EN"),
            ("📢 meta alerta <texto>", "Alerta ES/EN"),
            ("⚔️ meta evento <texto>", "Evento ES/EN"),
            ("🛎️ meta buffo <texto>", "Bufo ES/EN + @everyone"),
            ("✏️ meta editar <texto>", "Edita el último anuncio"),
            ("🧹 meta limpia [cantidad]", "Borra mensajes del bot | Máx. 50"),
            ("🟢 meta ping", "Verifica latencia"),
            ("🛡️ meta estado", "Estado de Discord, Groq, Google y MyMemory"),
            ("🔄 meta reiniciar <servicio>", "Reinicia Groq, Google, MyMemory o todo"),
            ("🌎 meta traduccion on/off", "Activa/desactiva traducción"),
        ]
        for name, value in commands:
            embed.add_field(name=name, value=value, inline=False)

        embed.add_field(
            name="👻 Banderas",
            value="El bot NO agrega banderas automáticamente. Agrégalas manualmente.",
            inline=False,
        )
        embed.add_field(
            name="📩 Traducciones",
            value="Por defecto van por DM. ES/EN/TR salen en canal solo en #oficiales, #diplomacia, #general y #bitácora.",
            inline=False,
        )
        embed.set_footer(text="META ESTÁ CONTIGO. UN REINO, UNA ALIANZA, UNA META")
        await message.channel.send(embed=embed)
        return

# ============================================================
# REACCIONES
# ============================================================

@client.event
async def on_raw_reaction_add(payload):
    if client.user and payload.user_id == client.user.id:
        return

    emoji = str(payload.emoji)
    if emoji not in BANDERAS:
        return

    key = (payload.user_id, payload.message_id, emoji)
    if key in traduciendo_users:
        return

    traduciendo_users.add(key)

    try:
        if not translation_enabled:
            return

        channel = client.get_channel(payload.channel_id)
        if channel is None:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.HTTPException) as error:
            print(f"[ERROR FETCH MESSAGE] {error}")
            return

        try:
            user = await client.fetch_user(payload.user_id)
        except Exception as error:
            print(f"[ERROR FETCH USER] {error}")
            return

        # Si no tiene Manage Messages, la traducción NO se detiene.
        try:
            await message.remove_reaction(payload.emoji, user)
        except discord.Forbidden:
            print("⚠️ Falta Manage Messages. La traducción continúa.")
        except Exception as error:
            print(f"[WARN REMOVE REACTION] {error}")

        if payload.message_id in mensajes_con_banderas:
            texto = mensajes_con_banderas[payload.message_id].get("texto_es")
        else:
            if message.author.bot:
                return
            texto = message.content.strip()

        texto = limpiar_texto(texto)

        if len(texto) < 2:
            return

        idioma = BANDERAS[emoji]
        nombre = NOMBRES_IDIOMAS.get(idioma, idioma)
        traduccion = await traducir_seguro(texto, idioma)

        if (
            payload.channel_id in CANALES_TRADUCCION_DIRECTA
            and idioma in {"es", "en", "tr"}
        ):
            flag = {"es": "🇪🇸", "en": "🇺🇸", "tr": "🇹🇷"}[idioma]

            embed = discord.Embed(
                description=f"{flag} {limitar_texto(traduccion, 4000)}",
                color=COLOR_TRADUCCION,
            )

            await channel.send(
                embed=embed,
                delete_after=40 if idioma == "tr" else 20,
            )
            return

        try:
            await user.send(
                embed=embed_traduccion(
                    emoji,
                    nombre,
                    texto,
                    traduccion,
                )
            )
        except discord.Forbidden:
            print(f"📩 DM cerrado para {user}.")
        except discord.HTTPException as error:
            print(f"[ERROR DM] {error}")

    except Exception as error:
        print(f"[ERROR REACCIÓN] {error}")

    finally:
        await asyncio.sleep(3)
        traduciendo_users.discard(key)

# ============================================================
# LIMPIEZA
# ============================================================

async def limpieza_memoria():
    while True:
        await asyncio.sleep(3600)

        if len(mensajes_con_banderas) > 1000:
            for message_id in list(mensajes_con_banderas)[:500]:
                mensajes_con_banderas.pop(message_id, None)

        if len(ultimo_anuncio) > 500:
            for channel_id in list(ultimo_anuncio)[:250]:
                ultimo_anuncio.pop(channel_id, None)

        print("🧹 Limpieza de memoria ejecutada.")

# ============================================================
# HTTP RENDER
# ============================================================

class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Kingdom Intelligence System - Bot alive")

    def log_message(self, format, *args):
        return

def run_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"🌐 HTTP Server activo en puerto {port}")
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

print("🚀 Iniciando Kingdom Intelligence System...")
client.run(TOKEN)
