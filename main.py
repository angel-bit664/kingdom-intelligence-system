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
# CONFIGURACION
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

if not TOKEN:
    raise RuntimeError("Falta DISCORD_TOKEN en Render.")

# IDs de tus canales
ID_CANAL_ACTIVATE = 1358237524249542751
ID_CANAL_ANUNCIOS = 1358237524249542751
ID_CANAL_BUFF = 1358237524249542751

ID_CANAL_OFICIALES = 1358237525214236705
ID_CANAL_BITACORA = 1362642374429245440
ID_CANAL_DIPLOMACIA = 1358237524799131664
ID_CANAL_GENERAL = 1358237524799131662

# SOLO en estos 4 canales, ES/EN/TR se publican en el canal.
CANALES_TRADUCCION_DIRECTA = {
    ID_CANAL_OFICIALES,
    ID_CANAL_DIPLOMACIA,
    ID_CANAL_GENERAL,
    ID_CANAL_BITACORA,
}

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

client = discord.Client(intents=intents)

# ============================================================
# MEMORIA TEMPORAL
# ============================================================

# message_id -> {"texto_es": "...", "tipo": "..."}
mensajes_con_banderas = {}

# channel_id -> discord.Message
ultimo_anuncio = {}

# Protege activate contra duplicados simultaneos.
procesando_activate = set()

# (user_id, message_id, emoji)
traduciendo_users = set()

# ============================================================
# REINICIO MANUAL DE SERVICIOS
# ============================================================

def reiniciar_groq():
    global groq_client
    global groq_failures, groq_last_error, groq_last_success
    global groq_circuit_open_until

    groq_failures = 0
    groq_last_error = None
    groq_last_success = None
    groq_circuit_open_until = 0.0

    if GROQ_API_KEY and AsyncGroq is not None:
        try:
            groq_client = AsyncGroq(api_key=GROQ_API_KEY)
            print("🔄 GROQ reiniciado manualmente.")
            return True, "Groq fue reiniciado y la conexión fue reconstruida."
        except Exception as error:
            groq_client = None
            print(f"❌ Error reiniciando Groq: {error}")
            return False, f"No se pudo reconstruir Groq: {error}"

    groq_client = None
    return False, "Groq no está configurado o falta la librería/API key."


def reiniciar_google():
    global google_failures, google_last_error, google_last_success
    global google_circuit_open_until

    google_failures = 0
    google_last_error = None
    google_last_success = None
    google_circuit_open_until = 0.0

    print("🔄 GOOGLE reiniciado manualmente.")
    return True, "Google fue reiniciado. El siguiente intento volverá a probarlo."


def reiniciar_mymemory():
    global mymemory_failures, mymemory_last_error, mymemory_last_success

    mymemory_failures = 0
    mymemory_last_error = None
    mymemory_last_success = None

    print("🔄 MYMEMORY reiniciado manualmente.")
    return True, "MyMemory fue reiniciado."


def reiniciar_sistema_traduccion():
    groq_ok, groq_msg = reiniciar_groq()
    _, google_msg = reiniciar_google()
    _, mymemory_msg = reiniciar_mymemory()

    return groq_ok, groq_msg, google_msg, mymemory_msg


def usuario_puede_reiniciar(message):
    # Solo administradores del servidor pueden ejecutar reinicios.
    if message.guild is None:
        return False

    permisos = getattr(message.author, "guild_permissions", None)
    return bool(permisos and permisos.administrator)


# ============================================================
# ESTADO
# ============================================================

translation_enabled = True
bot_started_at = time.time()

groq_client = None
translation_semaphore = None
cleanup_task = None

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

# ============================================================
# BANDERAS / IDIOMAS
# ============================================================

BANDERAS = {
    "🇧🇷": "pt",
    "🇫🇷": "fr",
    "🇩🇪": "de",
    "🇮🇹": "it",
    "🇷🇺": "ru",
    "🇯🇵": "ja",
    "🇰🇷": "ko",
    "🇨🇳": "zh",
    "🇮🇩": "id",
    "🇺🇸": "en",
    "🇪🇸": "es",
    "🇹🇷": "tr",
}

NOMBRES_IDIOMAS = {
    "pt": "Portugués",
    "fr": "Francés",
    "de": "Alemán",
    "it": "Italiano",
    "ru": "Ruso",
    "ja": "Japonés",
    "ko": "Coreano",
    "zh": "Chino",
    "id": "Indonesio",
    "en": "Inglés",
    "es": "Español",
    "tr": "Turco",
}

COLOR_META = 0x9B59B6
COLOR_ALERTA = 0x3498DB
COLOR_ACTIVATE = 0xFF0000
COLOR_CUMPLEANOS = 0xFF69B4
COLOR_TRADUCCION = 0x00B0F4
COLOR_EXITO = 0x00FF00
COLOR_ERROR = 0xE74C3C


# ============================================================
# UTILIDADES
# ============================================================

def limitar_texto(texto, limite=1024):
    if texto is None:
        return ""
    texto = str(texto)
    if len(texto) <= limite:
        return texto
    return texto[:limite - 3] + "..."


def limpiar_texto(texto):
    if not texto:
        return ""

    texto = re.sub(r"<@!?\d+>", "", texto)
    texto = re.sub(r"<@&\d+>", "", texto)
    texto = re.sub(r"<#\d+>", "", texto)
    texto = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


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

    segundos = max(0, int(time.time() - timestamp))

    if segundos < 60:
        return f"hace {segundos}s"

    minutos = segundos // 60

    if minutos < 60:
        return f"hace {minutos}m"

    horas = minutos // 60
    return f"hace {horas}h"


# ============================================================
# CIRCUIT BREAKER
# ============================================================

def groq_disponible():
    return time.time() >= groq_circuit_open_until


def google_disponible():
    return time.time() >= google_circuit_open_until


def registrar_fallo_groq(error):
    global groq_failures, groq_last_error, groq_circuit_open_until

    groq_failures += 1
    groq_last_error = str(error)[:300]

    print(
        f"⚠️ GROQ FALLÓ "
        f"({groq_failures}/{CIRCUIT_FAILURE_LIMIT}): {error}"
    )

    if groq_failures >= CIRCUIT_FAILURE_LIMIT:
        groq_circuit_open_until = time.time() + CIRCUIT_COOLDOWN
        print(
            "🔌 CIRCUITO GROQ ABIERTO. "
            f"Reintento automático en {CIRCUIT_COOLDOWN}s."
        )


def registrar_exito_groq():
    global groq_failures, groq_last_success, groq_circuit_open_until

    groq_failures = 0
    groq_last_success = time.time()
    groq_circuit_open_until = 0.0


def registrar_fallo_google(error):
    global google_failures, google_last_error, google_circuit_open_until

    google_failures += 1
    google_last_error = str(error)[:300]

    print(
        f"⚠️ GOOGLE FALLÓ "
        f"({google_failures}/{CIRCUIT_FAILURE_LIMIT}): {error}"
    )

    if google_failures >= CIRCUIT_FAILURE_LIMIT:
        google_circuit_open_until = time.time() + CIRCUIT_COOLDOWN
        print(
            "🔌 CIRCUITO GOOGLE ABIERTO. "
            f"Reintento automático en {CIRCUIT_COOLDOWN}s."
        )


def registrar_exito_google():
    global google_failures, google_last_success, google_circuit_open_until

    google_failures = 0
    google_last_success = time.time()
    google_circuit_open_until = 0.0


# ============================================================
# GROQ
# ============================================================

async def traducir_con_groq(texto, destino):
    if groq_client is None:
        raise RuntimeError("Groq no está configurado.")

    if not groq_disponible():
        raise RuntimeError("Circuito Groq temporalmente cerrado.")

    idioma_nombre = NOMBRES_IDIOMAS.get(destino, destino)

    system_prompt = """
Eres el traductor de un bot de Discord para una comunidad internacional
de gaming.

Traduce únicamente el mensaje recibido al idioma solicitado.

Reglas:
- Conserva nombres de jugadores, lugares y nombres propios.
- Conserva números, horas, emojis y términos de videojuegos.
- No inventes información.
- No agregues explicaciones.
- No respondas preguntas.
- Mantén el tono del mensaje.
- Devuelve únicamente la traducción.
"""

    user_prompt = (
        f"Traduce al idioma {idioma_nombre}.\n\n"
        f"MENSAJE:\n{texto}"
    )

    try:
        response = await asyncio.wait_for(
            groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=1200,
                stream=False,
            ),
            timeout=12,
        )

        resultado = response.choices[0].message.content

        if not resultado:
            raise RuntimeError("Groq devolvió una respuesta vacía.")

        resultado = resultado.strip()
        registrar_exito_groq()
        return limitar_texto(resultado)

    except Exception as error:
        registrar_fallo_groq(error)
        raise


# ============================================================
# GOOGLE
# ============================================================

def google_sync(texto, destino):
    return GoogleTranslator(
        source="auto",
        target=destino,
    ).translate(texto)


async def traducir_con_google(texto, destino):
    if not google_disponible():
        raise RuntimeError("Circuito Google temporalmente cerrado.")

    try:
        await asyncio.sleep(random.uniform(0.2, 0.6))

        resultado = await asyncio.wait_for(
            asyncio.to_thread(google_sync, texto, destino),
            timeout=10,
        )

        if not resultado:
            raise RuntimeError("Google devolvió una respuesta vacía.")

        resultado = resultado.strip()

        if "error 500" in resultado.lower():
            raise RuntimeError("Google devolvió Error 500.")

        registrar_exito_google()
        return limitar_texto(resultado)

    except Exception as error:
        registrar_fallo_google(error)
        raise


# ============================================================
# MYMEMORY
# ============================================================

def mymemory_sync(texto, destino):
    return MyMemoryTranslator(
        source="auto",
        target=destino,
    ).translate(texto)


async def traducir_con_mymemory(texto, destino):
    global mymemory_failures, mymemory_last_error, mymemory_last_success

    try:
        await asyncio.sleep(0.4)

        resultado = await asyncio.wait_for(
            asyncio.to_thread(mymemory_sync, texto, destino),
            timeout=12,
        )

        if not resultado:
            raise RuntimeError("MyMemory devolvió una respuesta vacía.")

        resultado = resultado.strip()

        if "error" in resultado.lower():
            raise RuntimeError("MyMemory devolvió un error.")

        mymemory_failures = 0
        mymemory_last_success = time.time()
        return limitar_texto(resultado)

    except Exception as error:
        mymemory_failures += 1
        mymemory_last_error = str(error)[:300]
        print(f"⚠️ MYMEMORY FALLÓ: {error}")
        raise


# ============================================================
# TRADUCCIÓN SEGURA
# ============================================================

async def traducir_seguro(texto, destino):
    if not translation_enabled:
        return (
            "⚠️ El sistema de traducción está "
            "temporalmente desactivado."
        )

    texto = limpiar_texto(texto)

    if not texto:
        return ""

    texto = texto[:5000]

    if translation_semaphore is None:
        raise RuntimeError("El sistema de traducción todavía no está listo.")

    async with translation_semaphore:
        # Nivel 1: Groq
        try:
            resultado = await traducir_con_groq(texto, destino)
            print(f"🧠 Traducción Groq → {destino}")
            return resultado
        except Exception:
            print(f"🔄 Groq no disponible. Fallback Google → {destino}")

        # Nivel 2: Google
        try:
            resultado = await traducir_con_google(texto, destino)
            print(f"🌎 Traducción Google → {destino}")
            return resultado
        except Exception:
            print(f"🔄 Google no disponible. Fallback MyMemory → {destino}")

        # Nivel 3: MyMemory
        try:
            resultado = await traducir_con_mymemory(texto, destino)
            print(f"🆘 Traducción MyMemory → {destino}")
            return resultado
        except Exception:
            print("❌ Groq, Google y MyMemory fallaron.")

    # Nivel 4: fallback seguro
    return (
        "⚠️ No fue posible realizar la traducción "
        "en este momento. Intenta nuevamente más tarde."
    )


async def corregir_y_traducir_ia(texto_original):
    texto_limpio = limpiar_texto(texto_original)

    if len(texto_limpio) < 3:
        return {
            "es": texto_limpio,
            "en": "⚠️ Message too short",
        }

    # Para anuncios: Groq intenta primero.
    try:
        texto_en = await traducir_con_groq(
            texto_limpio,
            "en",
        )

        return {
            "es": limitar_texto(texto_limpio),
            "en": limitar_texto(texto_en),
        }

    except Exception:
        pass

    texto_en = await traducir_seguro(
        texto_limpio,
        "en",
    )

    return {
        "es": limitar_texto(texto_limpio),
        "en": limitar_texto(texto_en),
    }


# ============================================================
# EMBEDS
# ============================================================

def crear_embed_traduccion(emoji, nombre, original, traduccion):
    embed = discord.Embed(
        title=f"{emoji} Traducción a {nombre}",
        color=COLOR_EXITO,
    )

    embed.add_field(
        name="Original",
        value=limitar_texto(original),
        inline=False,
    )

    embed.add_field(
        name="Traducción",
        value=limitar_texto(traduccion),
        inline=False,
    )

    embed.set_footer(
        text="META • Traducción privada",
    )

    return embed


# ============================================================
# ESTADO
# ============================================================

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
        restante = max(0, int(groq_circuit_open_until - time.time()))
        groq_estado = f"🟡 FALLA / ESPERA ({restante}s)"
    elif groq_last_success:
        groq_estado = "🟢 ACTIVO"
    else:
        groq_estado = "🟢 CONFIGURADO / SIN PRUEBA"

    if not google_disponible():
        restante = max(0, int(google_circuit_open_until - time.time()))
        google_estado = f"🟡 FALLA / ESPERA ({restante}s)"
    elif google_last_success:
        google_estado = "🟢 ACTIVO"
    else:
        google_estado = "🟢 DISPONIBLE / SIN PRUEBA"

    if mymemory_last_success:
        mymemory_estado = "🟢 ACTIVO"
    elif mymemory_failures >= 3:
        mymemory_estado = "🟡 CON ERRORES"
    else:
        mymemory_estado = "🟢 DISPONIBLE / SIN PRUEBA"

    traduccion_estado = (
        "🟢 ACTIVA" if translation_enabled else "🔴 DESACTIVADA"
    )

    uptime = max(0, int(time.time() - bot_started_at))
    horas = uptime // 3600
    minutos = (uptime % 3600) // 60
    segundos = uptime % 60

    embed = discord.Embed(
        title="🛡️ KINGDOM INTELLIGENCE SYSTEM",
        description=(
            "Estado general del bot y del sistema de traducción.\n"
            "Los estados de APIs se basan en la última actividad."
        ),
        color=COLOR_META,
    )

    embed.add_field(
        name="🤖 Discord",
        value=f"{discord_estado}\nLatencia: {latency}ms",
        inline=True,
    )

    embed.add_field(
        name="🧠 Groq",
        value=groq_estado,
        inline=True,
    )

    embed.add_field(
        name="🌎 Google",
        value=google_estado,
        inline=True,
    )

    embed.add_field(
        name="🆘 MyMemory",
        value=mymemory_estado,
        inline=True,
    )

    embed.add_field(
        name="🌐 Traducción",
        value=traduccion_estado,
        inline=True,
    )

    embed.add_field(
        name="🚦 Protección",
        value=f"Máx. {MAX_TRANSLATIONS_CONCURRENT} simultáneas",
        inline=True,
    )

    embed.add_field(
        name="⏱️ Uptime",
        value=f"{horas}h {minutos}m {segundos}s",
        inline=False,
    )

    embed.add_field(
        name="🔄 Último Groq",
        value=tiempo_desde(groq_last_success),
        inline=True,
    )

    embed.add_field(
        name="🔄 Último Google",
        value=tiempo_desde(google_last_success),
        inline=True,
    )

    embed.add_field(
        name="🔄 Último MyMemory",
        value=tiempo_desde(mymemory_last_success),
        inline=True,
    )

    if groq_last_error:
        embed.add_field(
            name="⚠️ Último error Groq",
            value=limitar_texto(groq_last_error, 500),
            inline=False,
        )

    if google_last_error:
        embed.add_field(
            name="⚠️ Último error Google",
            value=limitar_texto(google_last_error, 500),
            inline=False,
        )

    embed.set_footer(
        text="META • Diagnóstico del sistema",
    )

    await message.channel.send(embed=embed)


# ============================================================
# READY
# ============================================================

@client.event
async def on_ready():
    global groq_client, translation_semaphore, cleanup_task

    if GROQ_API_KEY and AsyncGroq is not None and groq_client is None:
        try:
            groq_client = AsyncGroq(api_key=GROQ_API_KEY)
        except Exception as error:
            print(f"⚠️ No se pudo inicializar Groq: {error}")
            groq_client = None

    if translation_semaphore is None:
        translation_semaphore = asyncio.Semaphore(
            MAX_TRANSLATIONS_CONCURRENT
        )

    if cleanup_task is None or cleanup_task.done():
        cleanup_task = asyncio.create_task(limpieza_memoria())

    print("=" * 65)
    print(f"🤖 {client.user} conectado.")
    print(f"🆔 ID: {client.user.id}")
    print(
        f"🧠 Groq: "
        f"{'CONFIGURADO' if groq_client else 'NO DISPONIBLE'}"
    )
    print(
        f"🌎 Traducción: "
        f"{'ACTIVA' if translation_enabled else 'DESACTIVADA'}"
    )
    print("📍 ES/EN/TR directos solamente en:")
    print("   #oficiales")
    print("   #diplomacia")
    print("   #general")
    print("   #bitácora")
    print("👻 Las banderas NO se agregan automáticamente.")
    print("=" * 65)


# ============================================================
# COMANDOS
# ============================================================

@client.event
async def on_message(message):
    global translation_enabled

    if message.author.bot:
        return

    contenido = message.content.strip()

    if not contenido:
        return

    if not contenido.lower().startswith("meta "):
        return

    partes = contenido[5:].strip().split()

    if not partes:
        return

    comando = partes[0].lower()
    args = " ".join(partes[1:]).strip()

    # --------------------------------------------------------
    # META ESTADO
    # --------------------------------------------------------

    if comando == "estado":
        await comando_estado(message)
        return

    # --------------------------------------------------------
    # META TRADUCCION ON/OFF
    # --------------------------------------------------------

    if comando == "traduccion":
        opcion = args.lower()

        if opcion == "off":
            translation_enabled = False

            await message.channel.send(
                "🛑 Sistema de traducción desactivado temporalmente.",
                delete_after=8,
            )
            return

        if opcion == "on":
            translation_enabled = True

            await message.channel.send(
                "🟢 Sistema de traducción activado nuevamente.",
                delete_after=8,
            )
            return

        await message.channel.send(
            "❌ Usa:\n"
            "`meta traduccion on`\n"
            "`meta traduccion off`"
        )
        return

    # --------------------------------------------------------
    # META REINICIAR
    # --------------------------------------------------------

    if comando == "reiniciar":
        if not usuario_puede_reiniciar(message):
            await message.channel.send(
                "🔒 Solo un administrador del servidor puede reiniciar "
                "los servicios del traductor.",
                delete_after=8,
            )
            return

        servicio = args.lower().strip()

        if servicio in ("groq", "grok"):
            ok, respuesta = reiniciar_groq()
            await message.channel.send(
                ("🟢 " if ok else "🔴 ") + respuesta,
                delete_after=10,
            )
            return

        if servicio == "google":
            ok, respuesta = reiniciar_google()
            await message.channel.send(
                ("🟢 " if ok else "🔴 ") + respuesta,
                delete_after=10,
            )
            return

        if servicio in ("mymemory", "my-memory"):
            ok, respuesta = reiniciar_mymemory()
            await message.channel.send(
                ("🟢 " if ok else "🔴 ") + respuesta,
                delete_after=10,
            )
            return

        if servicio in ("todo", "traductor", "traduccion", "traducción"):
            groq_ok, groq_msg, google_msg, mymemory_msg = (
                reiniciar_sistema_traduccion()
            )

            estado_general = "🟢" if groq_ok else "🟡"

            await message.channel.send(
                f"{estado_general} Sistema de traducción reiniciado.\n"
                f"🧠 {groq_msg}\n"
                f"🌎 {google_msg}\n"
                f"🆘 {mymemory_msg}",
                delete_after=12,
            )
            return

        await message.channel.send(
            "🔄 **Reinicio manual disponible:**\n"
            "`meta reiniciar groq`\n"
            "`meta reiniciar google`\n"
            "`meta reiniciar mymemory`\n"
            "`meta reiniciar todo`",
            delete_after=12,
        )
        return

    # --------------------------------------------------------
    # META ACTIVATE
    # --------------------------------------------------------

    if comando == "activate":
        if message.author.id in procesando_activate:
            try:
                await message.delete()
            except Exception:
                pass
            return

        if not message.mentions:
            await message.channel.send(
                "❌ Menciona al usuario:\n"
                "`meta activate @usuario [mensaje]`"
            )
            return

        procesando_activate.add(message.author.id)

        try:
            usuario = message.mentions[0]
            texto_mensaje = obtener_texto_sin_menciones(message)
            datos = await corregir_y_traducir_ia(texto_mensaje)

            if "⚠️" in datos["en"]:
                mensaje_extra = (
                    "\n\n"
                    "💬 MENSAJE / MESSAGE:\n"
                    f"🇲🇽 {datos['es']}\n"
                    "🇺🇸 Translation failed - Use ES text"
                )
            else:
                mensaje_extra = (
                    "\n\n"
                    "💬 MENSAJE / MESSAGE:\n"
                    f"🇲🇽 {datos['es']}\n"
                    f"🇺🇸 {datos['en']}"
                )

            descripcion = (
                "🚨 CÓDIGO DE EMERGENCIA TFT 🚨\n"
                "⚠️ ALERTA ROJA\n"
                f"🎯 OBJETIVO: {usuario.mention}\n"
                "❌ ESTADO: SIN ESCUDO ACTIVO\n"
                "🛡️ PROTOCOLO:\n"
                "1. MUÉVETE YA\n"
                "2. ESCUDO 8H\n"
                "3. TELEPORT"
                f"{mensaje_extra}"
            )

            embed = discord.Embed(
                description=descripcion[:4096],
                color=COLOR_ACTIVATE,
            )

            embed.set_footer(
                text="Agrega una bandera al mensaje para solicitar traducción."
            )

            canal = client.get_channel(ID_CANAL_ACTIVATE) or message.channel

            msg_publicado = await canal.send(
                content=usuario.mention,
                embed=embed,
            )

            mensajes_con_banderas[msg_publicado.id] = {
                "texto_es": datos["es"],
                "tipo": "activate",
            }

            try:
                await message.delete()
            except Exception:
                pass

        except Exception as error:
            print(f"[ERROR ACTIVATE] {error}")

            try:
                await message.channel.send(
                    "❌ Ocurrió un error al activar el protocolo."
                )
            except Exception:
                pass

        finally:
            procesando_activate.discard(message.author.id)

        return

    # --------------------------------------------------------
    # META CUMPLEAÑOS
    # --------------------------------------------------------

    if comando == "cumpleaños":
        if not message.mentions:
            await message.channel.send(
                "❌ Menciona al usuario:\n"
                "`meta cumpleaños @usuario [mensaje]`"
            )
            return

        usuario = message.mentions[0]
        texto_custom = obtener_texto_sin_menciones(message)

        try:
            await message.delete()
        except Exception:
            pass

        if texto_custom:
            datos = await corregir_y_traducir_ia(texto_custom)
            mensaje_es = datos["es"]
            mensaje_en = datos["en"]
        else:
            mensaje_es = (
                f"¡Feliz cumpleaños {usuario.display_name}! "
                "🎉🎂 Que tengas un día increíble."
            )
            mensaje_en = (
                f"Happy birthday {usuario.display_name}! "
                "🎉🎂 Have an amazing day."
            )

        embed = discord.Embed(
            title="🎂 ¡FELIZ CUMPLEAÑOS!",
            color=COLOR_CUMPLEANOS,
        )

        embed.add_field(
            name="🇲🇽 Español",
            value=limitar_texto(mensaje_es),
            inline=False,
        )

        embed.add_field(
            name="🇺🇸 English",
            value=limitar_texto(mensaje_en),
            inline=False,
        )

        embed.set_thumbnail(url=usuario.display_avatar.url)

        embed.set_footer(
            text="Agrega una bandera al mensaje para solicitar traducción."
        )

        canal = client.get_channel(ID_CANAL_ANUNCIOS) or message.channel

        msg_publicado = await canal.send(
            content=f"{usuario.mention} @everyone",
            embed=embed,
        )

        mensajes_con_banderas[msg_publicado.id] = {
            "texto_es": mensaje_es,
            "tipo": "cumpleaños",
        }

        ultimo_anuncio[message.channel.id] = msg_publicado
        return

    # --------------------------------------------------------
    # META EVENTO / ALERTA
    # --------------------------------------------------------

    if comando in ("evento", "alerta"):
        if not args:
            return

        try:
            await message.delete()
        except Exception:
            pass

        procesando = await message.channel.send(
            "⏳ Corrigiendo y traduciendo..."
        )

        try:
            datos = await corregir_y_traducir_ia(args)
        finally:
            try:
                await procesando.delete()
            except Exception:
                pass

        titulo = "⚔️ EVENTO" if comando == "evento" else "🚨 ALERTA"

        embed = discord.Embed(
            title=titulo,
            color=COLOR_ALERTA,
        )

        embed.add_field(
            name="🇲🇽 Español",
            value=limitar_texto(datos["es"]),
            inline=False,
        )

        embed.add_field(
            name="🇺🇸 English",
            value=limitar_texto(datos["en"]),
            inline=False,
        )

        embed.set_footer(
            text="Agrega una bandera al mensaje para solicitar traducción."
        )

        canal = client.get_channel(ID_CANAL_ANUNCIOS) or message.channel

        msg_publicado = await canal.send(
            content="@everyone",
            embed=embed,
        )

        mensajes_con_banderas[msg_publicado.id] = {
            "texto_es": datos["es"],
            "tipo": comando,
        }

        ultimo_anuncio[message.channel.id] = msg_publicado
        return

    # --------------------------------------------------------
    # META BUFFO
    # --------------------------------------------------------

    if comando in ("buffo", "bufo", "buff"):
        if not args:
            return

        try:
            await message.delete()
        except Exception:
            pass

        datos = await corregir_y_traducir_ia(args)

        embed = discord.Embed(
            title="🛎️ BUFO ACTIVADO",
            color=COLOR_META,
        )

        embed.add_field(
            name="🇲🇽 Español",
            value=f"✅ {limitar_texto(datos['es'])}",
            inline=False,
        )

        embed.add_field(
            name="🇺🇸 English",
            value=f"✅ {limitar_texto(datos['en'])}",
            inline=False,
        )

        embed.set_footer(
            text="Agrega una bandera al mensaje para solicitar traducción."
        )

        canal = client.get_channel(ID_CANAL_BUFF) or message.channel

        msg_publicado = await canal.send(
            content="@everyone",
            embed=embed,
        )

        mensajes_con_banderas[msg_publicado.id] = {
            "texto_es": datos["es"],
            "tipo": "buffo",
        }

        ultimo_anuncio[message.channel.id] = msg_publicado
        return

    # --------------------------------------------------------
    # META EDITAR
    # --------------------------------------------------------

    if comando == "editar":
        if not args:
            await message.channel.send(
                "❌ Escribe el nuevo texto:\n"
                "`meta editar nuevo texto`"
            )
            return

        if message.channel.id not in ultimo_anuncio:
            await message.channel.send(
                "❌ No hay anuncio reciente para editar en este canal."
            )
            return

        msg_a_editar = ultimo_anuncio[message.channel.id]
        datos = await corregir_y_traducir_ia(args)

        try:
            if not msg_a_editar.embeds:
                raise RuntimeError("El mensaje no tiene embed.")

            embed = msg_a_editar.embeds[0]
            embed.clear_fields()

            titulo = embed.title or ""

            if "CUMPLEAÑOS" in titulo:
                embed.add_field(
                    name="🇲🇽 Español",
                    value=datos["es"],
                    inline=False,
                )
                embed.add_field(
                    name="🇺🇸 English",
                    value=datos["en"],
                    inline=False,
                )

            elif "BUFO" in titulo:
                embed.add_field(
                    name="🇲🇽 Español",
                    value=f"✅ {datos['es']}",
                    inline=False,
                )
                embed.add_field(
                    name="🇺🇸 English",
                    value=f"✅ {datos['en']}",
                    inline=False,
                )

            else:
                embed.add_field(
                    name="🇲🇽 Español",
                    value=datos["es"],
                    inline=False,
                )
                embed.add_field(
                    name="🇺🇸 English",
                    value=datos["en"],
                    inline=False,
                )

            await msg_a_editar.edit(embed=embed)

            if msg_a_editar.id in mensajes_con_banderas:
                mensajes_con_banderas[msg_a_editar.id]["texto_es"] = datos["es"]

            try:
                await message.delete()
            except Exception:
                pass

            await message.channel.send(
                "✅ Anuncio editado.",
                delete_after=5,
            )

        except Exception as error:
            print(f"[ERROR EDITAR] {error}")

            await message.channel.send(
                "❌ No se pudo editar el anuncio."
            )

        return

    # --------------------------------------------------------
    # META LIMPIA
    # --------------------------------------------------------

    if comando == "limpia":
        cantidad = 10

        if args.isdigit():
            cantidad = int(args)

        cantidad = max(1, min(cantidad, 50))

        try:
            await message.delete()
        except Exception:
            pass

        borrados = 0

        try:
            async for msg in message.channel.history(limit=100):
                if not client.user or msg.author.id != client.user.id:
                    continue

                try:
                    await msg.delete()
                    borrados += 1

                    if borrados >= cantidad:
                        break

                    await asyncio.sleep(0.5)

                except Exception:
                    pass

        except Exception as error:
            print(f"[ERROR LIMPIA] {error}")

        await message.channel.send(
            f"🧹 Borrados {borrados} mensajes del bot.",
            delete_after=5,
        )
        return

    # --------------------------------------------------------
    # META PING
    # --------------------------------------------------------

    if comando == "ping":
        latencia = round(client.latency * 1000)
        await message.channel.send(
            f"🟢 Latencia: {latencia}ms"
        )
        return

    # --------------------------------------------------------
    # META AYUDA
    # --------------------------------------------------------

    if comando == "ayuda":
        embed = discord.Embed(
            title="📋 COMANDOS META BOT",
            color=COLOR_META,
        )

        embed.add_field(
            name="🚨 meta activate @usuario [mensaje]",
            value="Código de emergencia ES/EN",
            inline=False,
        )

        embed.add_field(
            name="🎂 meta cumpleaños @usuario [mensaje]",
            value="Felicitación ES/EN",
            inline=False,
        )

        embed.add_field(
            name="📢 meta alerta <texto>",
            value="Alerta ES/EN",
            inline=False,
        )

        embed.add_field(
            name="⚔️ meta evento <texto>",
            value="Evento ES/EN",
            inline=False,
        )

        embed.add_field(
            name="🛎️ meta buffo <texto>",
            value="Bufo ES/EN + @everyone",
            inline=False,
        )

        embed.add_field(
            name="✏️ meta editar <texto>",
            value="Edita el último anuncio del bot",
            inline=False,
        )

        embed.add_field(
            name="🧹 meta limpia [cantidad]",
            value="Borra mensajes del bot | Máx. 50",
            inline=False,
        )

        embed.add_field(
            name="🟢 meta ping",
            value="Verifica latencia",
            inline=False,
        )

        embed.add_field(
            name="🛡️ meta estado",
            value="Revisa Discord, Groq, Google y MyMemory.",
            inline=False,
        )

        embed.add_field(
            name="🔄 meta reiniciar <servicio>",
            value=(
                "Solo administradores. Reinicia Groq, Google, MyMemory "
                "o todo el sistema de traducción."
            ),
            inline=False,
        )

        embed.add_field(
            name="🌎 meta traduccion on/off",
            value="Activa o desactiva el traductor.",
            inline=False,
        )

        embed.add_field(
            name="👻 Banderas",
            value=(
                "El bot NO agrega banderas automáticamente. "
                "Agrega manualmente una bandera al mensaje."
            ),
            inline=False,
        )

        embed.add_field(
            name="📩 Traducciones",
            value=(
                "Por defecto van por DM. "
                "Solo 🇪🇸 🇺🇸 🇹🇷 aparecen en canal dentro de "
                "#oficiales, #diplomacia, #general y #bitácora."
            ),
            inline=False,
        )

        embed.set_footer(
            text="META ESTÁ CONTIGO. UN REINO, UNA ALIANZA, UNA META"
        )

        await message.channel.send(embed=embed)
        return


# ============================================================
# REACCIONES / BANDERAS
# ============================================================

@client.event
async def on_raw_reaction_add(payload):
    if client.user and payload.user_id == client.user.id:
        return

    emoji = str(payload.emoji)

    if emoji not in BANDERAS:
        return

    reaction_key = (
        payload.user_id,
        payload.message_id,
        emoji,
    )

    if reaction_key in traduciendo_users:
        return

    traduciendo_users.add(reaction_key)

    try:
        if not translation_enabled:
            return

        channel = client.get_channel(payload.channel_id)

        if channel is None:
            return

        try:
            message = await channel.fetch_message(
                payload.message_id
            )
        except discord.NotFound:
            return
        except discord.HTTPException as error:
            print(f"[ERROR FETCH MESSAGE] {error}")
            return

        try:
            user = await client.fetch_user(
                payload.user_id
            )
        except Exception as error:
            print(f"[ERROR FETCH USER] {error}")
            return

        # La bandera se elimina para que no quede basura visual.
        try:
            await message.remove_reaction(
                payload.emoji,
                user,
            )
        except Exception as error:
            print(f"[WARN REMOVE REACTION] {error}")

        # Obtener texto
        texto_original = None

        if payload.message_id in mensajes_con_banderas:
            data = mensajes_con_banderas[payload.message_id]
            texto_original = data.get("texto_es")
        else:
            if message.author.bot:
                return

            texto_original = message.content.strip()

        if not texto_original:
            return

        texto_original = limpiar_texto(
            texto_original
        )

        if len(texto_original) < 2:
            return

        idioma = BANDERAS[emoji]
        nombre = NOMBRES_IDIOMAS.get(
            idioma,
            idioma,
        )

        # Traducir
        traduccion = await traducir_seguro(
            texto_original,
            idioma,
        )

        # ES / EN / TR directo al canal, SOLO en los 4 canales.
        if (
            payload.channel_id in CANALES_TRADUCCION_DIRECTA
            and idioma in {"es", "en", "tr"}
        ):
            if idioma == "es":
                flag_emoji = "🇪🇸"
            elif idioma == "en":
                flag_emoji = "🇺🇸"
            else:
                flag_emoji = "🇹🇷"

            texto_canal = limitar_texto(
                traduccion,
                4000,
            )

            embed = discord.Embed(
                description=f"{flag_emoji} {texto_canal}",
                color=COLOR_TRADUCCION,
            )

            delete_timer = 40 if idioma == "tr" else 20

            await channel.send(
                embed=embed,
                delete_after=delete_timer,
            )

            return

        # Todos los demás -> DM.
        embed_dm = crear_embed_traduccion(
            emoji,
            nombre,
            texto_original,
            traduccion,
        )

        try:
            await user.send(
                embed=embed_dm
            )

        except discord.Forbidden:
            print(
                f"📩 DM cerrado para {user}."
            )

        except discord.HTTPException as error:
            print(
                f"[ERROR DM] {error}"
            )

    except Exception as error:
        print(
            f"[ERROR REACCIÓN] {error}"
        )

    finally:
        await asyncio.sleep(3)
        traduciendo_users.discard(reaction_key)


# ============================================================
# LIMPIEZA DE MEMORIA
# ============================================================

async def limpieza_memoria():
    while True:
        await asyncio.sleep(3600)

        if len(mensajes_con_banderas) > 1000:
            ids = list(mensajes_con_banderas.keys())

            for message_id in ids[:500]:
                mensajes_con_banderas.pop(
                    message_id,
                    None,
                )

        if len(ultimo_anuncio) > 500:
            ids = list(ultimo_anuncio.keys())

            for channel_id in ids[:250]:
                ultimo_anuncio.pop(
                    channel_id,
                    None,
                )

        print(
            "🧹 Limpieza de memoria ejecutada."
        )


# ============================================================
# SERVIDOR HTTP PARA RENDER / UPTIMEROBOT
# ============================================================

class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8",
        )
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8",
        )
        self.end_headers()
        self.wfile.write(
            b"Kingdom Intelligence System - Bot alive"
        )

    def log_message(self, format, *args):
        return


def run_server():
    port = int(
        os.getenv(
            "PORT",
            "10000",
        )
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        Handler,
    )

    print(
        f"🌐 HTTP Server activo en puerto {port}"
    )

    server.serve_forever()


# ============================================================
# INICIO
# ============================================================

threading.Thread(
    target=run_server,
    daemon=True,
).start()

print(
    "🚀 Iniciando Kingdom Intelligence System..."
)

client.run(TOKEN)
