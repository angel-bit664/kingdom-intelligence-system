import discord
import asyncio
import re
import os
import random
import threading
import time

from deep_translator import GoogleTranslator, MyMemoryTranslator
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from groq import AsyncGroq
except ImportError:
    AsyncGroq = None


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "❌ Falta DISCORD_TOKEN en las variables de entorno."
    )


# ============================================================
# GROQ
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Puedes cambiar el modelo desde Render agregando:
# GROQ_MODEL
#
# Si no existe, usamos este.
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

groq_client = None

if GROQ_API_KEY and AsyncGroq is not None:

    try:
        groq_client = AsyncGroq(
            api_key=GROQ_API_KEY
        )

        print("🧠 Groq configurado correctamente.")

    except Exception as e:

        print(
            f"⚠️ No se pudo inicializar Groq: {e}"
        )

else:

    print(
        "⚠️ Groq no está disponible. "
        "Se utilizarán los traductores de respaldo."
    )


# ============================================================
# IDS DE CANALES
# ============================================================

ID_CANAL_ACTIVATE = 1358237524249542751

ID_CANAL_ANUNCIOS = 1358237524249542751

ID_CANAL_BUFF = 1358237524249542751

ID_CANAL_OFICIALES = 1358237525214236705

ID_CANAL_BITACORA = 1362642374429245440

ID_CANAL_DIPLOMACIA = 1358237524799131664

ID_CANAL_GENERAL = 1358237524799131662


# ============================================================
# CANALES ESPECIALES
#
# SOLO EN ESTOS CANALES:
#
# 🇪🇸 Español -> canal
# 🇺🇸 Inglés  -> canal
# 🇹🇷 Turco   -> canal
#
# Los demás idiomas -> DM
# ============================================================

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

client = discord.Client(
    intents=intents
)


# ============================================================
# MEMORIA TEMPORAL
# ============================================================

mensajes_con_banderas = {}

ultimo_anuncio = {}

procesando_activate = set()

traduciendo_users = set()


# ============================================================
# ESTADO DEL SISTEMA
# ============================================================

translation_enabled = True

bot_started_at = time.time()

groq_failures = 0
google_failures = 0
mymemory_failures = 0

groq_last_error = None
google_last_error = None
mymemory_last_error = None

groq_last_success = None
google_last_success = None
mymemory_last_success = None


# ============================================================
# CIRCUIT BREAKER
# ============================================================

CIRCUIT_FAILURE_LIMIT = 5

CIRCUIT_COOLDOWN = 120

groq_circuit_open_until = 0

google_circuit_open_until = 0


# ============================================================
# CONTROL DE CARGA
# ============================================================

# Máximo de traducciones simultáneas.
#
# Si llegan 20 traducciones:
#
# 3 trabajan
# las demás esperan.
#
# Esto evita saturar APIs y el bot.

translation_semaphore = asyncio.Semaphore(3)


# ============================================================
# BANDERAS
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


# ============================================================
# COLORES
# ============================================================

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

def limitar_texto(
    texto,
    limite=1024
):

    if texto is None:
        return ""

    texto = str(texto)

    if len(texto) <= limite:
        return texto

    return texto[:limite - 3] + "..."


def limpiar_texto(
    texto
):

    if not texto:
        return ""

    # Menciones de usuarios
    texto = re.sub(
        r"<@!?\d+>",
        "",
        texto
    )

    # Menciones de roles
    texto = re.sub(
        r"<@&\d+>",
        "",
        texto
    )

    # Menciones de canales
    texto = re.sub(
        r"<#\d+>",
        "",
        texto
    )

    # Evitamos caracteres de control
    texto = re.sub(
        r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]",
        "",
        texto
    )

    # Espacios repetidos
    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


def obtener_texto_sin_menciones(
    message
):

    texto = message.content

    for usuario in message.mentions:

        texto = texto.replace(
            usuario.mention,
            ""
        )

        texto = texto.replace(
            f"<@{usuario.id}>",
            ""
        )

        texto = texto.replace(
            f"<@!{usuario.id}>",
            ""
        )

    return limpiar_texto(texto)


def tiempo_desde(
    timestamp
):

    if not timestamp:
        return "Nunca"

    segundos = int(
        time.time() - timestamp
    )

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

    global groq_circuit_open_until

    return time.time() >= groq_circuit_open_until


def google_disponible():

    global google_circuit_open_until

    return time.time() >= google_circuit_open_until


def registrar_fallo_groq(
    error
):

    global groq_failures
    global groq_last_error
    global groq_circuit_open_until

    groq_failures += 1

    groq_last_error = str(error)[:300]

    print(
        f"⚠️ GROQ FALLÓ "
        f"({groq_failures}/{CIRCUIT_FAILURE_LIMIT}): "
        f"{error}"
    )

    if groq_failures >= CIRCUIT_FAILURE_LIMIT:

        groq_circuit_open_until = (
            time.time() + CIRCUIT_COOLDOWN
        )

        print(
            "🔌 CIRCUITO GROQ ABIERTO. "
            f"Se reintentará en {CIRCUIT_COOLDOWN}s."
        )


def registrar_exito_groq():

    global groq_failures
    global groq_last_success
    global groq_circuit_open_until

    groq_failures = 0

    groq_last_success = time.time()

    groq_circuit_open_until = 0


def registrar_fallo_google(
    error
):

    global google_failures
    global google_last_error
    global google_circuit_open_until

    google_failures += 1

    google_last_error = str(error)[:300]

    print(
        f"⚠️ GOOGLE FALLÓ "
        f"({google_failures}/{CIRCUIT_FAILURE_LIMIT}): "
        f"{error}"
    )

    if google_failures >= CIRCUIT_FAILURE_LIMIT:

        google_circuit_open_until = (
            time.time() + CIRCUIT_COOLDOWN
        )

        print(
            "🔌 CIRCUITO GOOGLE ABIERTO. "
            f"Se reintentará en {CIRCUIT_COOLDOWN}s."
        )


def registrar_exito_google():

    global google_failures
    global google_last_success
    global google_circuit_open_until

    google_failures = 0

    google_last_success = time.time()

    google_circuit_open_until = 0


# ============================================================
# GROQ
# ============================================================

async def traducir_con_groq(
    texto,
    destino
):

    if groq_client is None:

        raise RuntimeError(
            "Groq no está configurado."
        )

    if not groq_disponible():

        raise RuntimeError(
            "Circuito Groq temporalmente cerrado."
        )

    idioma_nombre = NOMBRES_IDIOMAS.get(
        destino,
        destino
    )

    system_prompt = """
Eres el sistema de traducción de un bot de Discord
para una comunidad internacional de gaming.

Tu trabajo es traducir el mensaje al idioma solicitado.

REGLAS:

1. Conserva el significado original.
2. Conserva nombres propios.
3. Conserva nombres de jugadores.
4. Conserva números.
5. Conserva horas.
6. Conserva emojis.
7. Conserva términos de videojuegos.
8. No agregues explicaciones.
9. No inventes información.
10. No respondas preguntas.
11. Devuelve únicamente la traducción.
12. Mantén el tono del mensaje original.
"""

    user_prompt = (
        f"Traduce el siguiente mensaje al idioma "
        f"{idioma_nombre}.\n\n"
        f"MENSAJE:\n{texto}"
    )

    try:

        response = await asyncio.wait_for(

            groq_client.chat.completions.create(

                model=GROQ_MODEL,

                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],

                temperature=0.1,

                max_tokens=1200,

                stream=False,
            ),

            timeout=12

        )

        resultado = (
            response
            .choices[0]
            .message
            .content
        )

        if not resultado:

            raise RuntimeError(
                "Groq devolvió una respuesta vacía."
            )

        resultado = resultado.strip()

        registrar_exito_groq()

        return limitar_texto(
            resultado
        )

    except Exception as e:

        registrar_fallo_groq(e)

        raise


# ============================================================
# GOOGLE
# ============================================================

def google_sync(
    texto,
    destino
):

    return GoogleTranslator(
        source="auto",
        target=destino
    ).translate(
        texto
    )


async def traducir_con_google(
    texto,
    destino
):

    if not google_disponible():

        raise RuntimeError(
            "Circuito Google temporalmente cerrado."
        )

    try:

        await asyncio.sleep(
            random.uniform(
                0.2,
                0.6
            )
        )

        resultado = await asyncio.wait_for(

            asyncio.to_thread(
                google_sync,
                texto,
                destino
            ),

            timeout=10

        )

        if not resultado:

            raise RuntimeError(
                "Google devolvió una respuesta vacía."
            )

        resultado = resultado.strip()

        if "error 500" in resultado.lower():

            raise RuntimeError(
                "Google devolvió Error 500."
            )

        registrar_exito_google()

        return limitar_texto(
            resultado
        )

    except Exception as e:

        registrar_fallo_google(e)

        raise


# ============================================================
# MYMEMORY
# ============================================================

def mymemory_sync(
    texto,
    destino
):

    return MyMemoryTranslator(
        source="auto",
        target=destino
    ).translate(
        texto
    )


async def traducir_con_mymemory(
    texto,
    destino
):

    global mymemory_failures
    global mymemory_last_error
    global mymemory_last_success

    try:

        await asyncio.sleep(0.4)

        resultado = await asyncio.wait_for(

            asyncio.to_thread(
                mymemory_sync,
                texto,
                destino
            ),

            timeout=12

        )

        if not resultado:

            raise RuntimeError(
                "MyMemory devolvió una respuesta vacía."
            )

        resultado = resultado.strip()

        if "error" in resultado.lower():

            raise RuntimeError(
                "MyMemory devolvió un error."
            )

        mymemory_failures = 0

        mymemory_last_success = time.time()

        return limitar_texto(
            resultado
        )

    except Exception as e:

        mymemory_failures += 1

        mymemory_last_error = str(e)[:300]

        print(
            f"⚠️ MYMEMORY FALLÓ: {e}"
        )

        raise


# ============================================================
# SISTEMA PRINCIPAL DE TRADUCCIÓN
# ============================================================

async def traducir_seguro(
    texto,
    destino
):

    if not translation_enabled:

        return (
            "⚠️ El sistema de traducción "
            "está temporalmente desactivado."
        )

    texto = limpiar_texto(
        texto
    )

    if not texto:

        return ""

    # Protección contra textos gigantes
    texto = texto[:5000]

    async with translation_semaphore:

        # ----------------------------------------------------
        # NIVEL 1 — GROQ
        # ----------------------------------------------------

        try:

            resultado = await traducir_con_groq(
                texto,
                destino
            )

            print(
                f"🧠 Traducción Groq → {destino}"
            )

            return resultado

        except Exception:

            print(
                f"🔄 Groq no disponible. "
                f"Pasando a Google → {destino}"
            )


        # ----------------------------------------------------
        # NIVEL 2 — GOOGLE
        # ----------------------------------------------------

        try:

            resultado = await traducir_con_google(
                texto,
                destino
            )

            print(
                f"🌎 Traducción Google → {destino}"
            )

            return resultado

        except Exception:

            print(
                f"🔄 Google no disponible. "
                f"Pasando a MyMemory → {destino}"
            )


        # ----------------------------------------------------
        # NIVEL 3 — MYMEMORY
        # ----------------------------------------------------

        try:

            resultado = await traducir_con_mymemory(
                texto,
                destino
            )

            print(
                f"🆘 Traducción MyMemory → {destino}"
            )

            return resultado

        except Exception:

            print(
                "❌ Todos los traductores fallaron."
            )


    # --------------------------------------------------------
    # NIVEL 4 — FALLBACK SEGURO
    # --------------------------------------------------------

    return (
        "⚠️ No fue posible realizar la traducción "
        "en este momento.\n"
        "Intenta nuevamente más tarde."
    )


# ============================================================
# CORRECCIÓN + TRADUCCIÓN
# ============================================================

async def corregir_y_traducir_ia(
    texto_original
):

    texto_limpio = limpiar_texto(
        texto_original
    )

    if len(texto_limpio) < 3:

        return {
            "es": texto_limpio,
            "en": "⚠️ Message too short"
        }


    # Para los anuncios queremos:
    #
    # Español limpio
    # Inglés contextual
    #
    # Primero intentamos Groq.

    try:

        texto_en = await traducir_con_groq(
            texto_limpio,
            "en"
        )

        return {
            "es": limitar_texto(
                texto_limpio
            ),
            "en": limitar_texto(
                texto_en
            )
        }

    except Exception:

        pass


    # Fallback completo

    texto_en = await traducir_seguro(
        texto_limpio,
        "en"
    )

    return {
        "es": limitar_texto(
            texto_limpio
        ),
        "en": limitar_texto(
            texto_en
        )
    }


# ============================================================
# CREAR EMBED DE TRADUCCIÓN
# ============================================================

def crear_embed_traduccion(
    emoji,
    nombre,
    original,
    traduccion
):

    embed = discord.Embed(
        title=(
            f"{emoji} Traducción a "
            f"{nombre}"
        ),
        color=COLOR_EXITO
    )

    embed.add_field(
        name="Original",
        value=limitar_texto(
            original
        ),
        inline=False
    )

    embed.add_field(
        name="Traducción",
        value=limitar_texto(
            traduccion
        ),
        inline=False
    )

    embed.set_footer(
        text=(
            "META • Traducción privada"
        )
    )

    return embed


# ============================================================
# READY
# ============================================================

@client.event
async def on_ready():

    print("=" * 65)

    print(
        f"🤖 {client.user} conectado."
    )

    print(
        f"🆔 ID: {client.user.id}"
    )

    print(
        f"🧠 Groq: "
        f"{'CONFIGURADO' if groq_client else 'NO DISPONIBLE'}"
    )

    print(
        f"🌎 Traducción: "
        f"{'ACTIVA' if translation_enabled else 'DESACTIVADA'}"
    )

    print(
        "📍 Traducción directa ES/EN/TR:"
    )

    print(
        "   Oficiales"
    )

    print(
        "   Diplomacia"
    )

    print(
        "   General"
    )

    print(
        "   Bitácora"
    )

    print("=" * 65)


# ============================================================
# META ESTADO
# ============================================================

async def comando_estado(
    message
):

    uptime_segundos = int(
        time.time() - bot_started_at
    )

    horas = uptime_segundos // 3600

    minutos = (
        uptime_segundos % 3600
    ) // 60

    segundos = (
        uptime_segundos % 60
    )


    # --------------------------------------------------------
    # GROQ
    # --------------------------------------------------------

    if groq_client is None:

        groq_estado = "🔴 NO CONFIGURADO"

    elif not groq_disponible():

        restantes = int(
            groq_circuit_open_until
            - time.time()
        )

        groq_estado = (
            f"🟡 FALLA / ESPERA "
            f"({max(restantes, 0)}s)"
        )

    elif groq_last_success:

        groq_estado = (
            "🟢 ACTIVO"
        )

    else:

        groq_estado = (
            "🟢 CONFIGURADO"
        )


    # --------------------------------------------------------
    # GOOGLE
    # --------------------------------------------------------

    if not google_disponible():

        restantes = int(
            google_circuit_open_until
            - time.time()
        )

        google_estado = (
            f"🟡 FALLA / ESPERA "
            f"({max(restantes, 0)}s)"
        )

    elif google_last_success:

        google_estado = "🟢 ACTIVO"

    else:

        google_estado = "🟢 DISPONIBLE"


    # --------------------------------------------------------
    # MYMEMORY
    # --------------------------------------------------------

    if mymemory_last_success:

        mymemory_estado = "🟢 ACTIVO"

    elif mymemory_failures >= 3:

        mymemory_estado = "🟡 CON ERRORES"

    else:

        mymemory_estado = "🟢 DISPONIBLE"


    # --------------------------------------------------------
    # DISCORD
    # --------------------------------------------------------

    latency = round(
        client.latency * 1000
    )

    if latency < 150:

        discord_estado = "🟢 EXCELENTE"

    elif latency < 300:

        discord_estado = "🟢 NORMAL"

    elif latency < 600:

        discord_estado = "🟡 ALTA"

    else:

        discord_estado = "🔴 MUY ALTA"


    # --------------------------------------------------------
    # TRADUCCIÓN
    # --------------------------------------------------------

    if not translation_enabled:

        traduccion_estado = (
            "🔴 DESACTIVADA"
        )

    else:

        traduccion_estado = (
            "🟢 ACTIVA"
        )


    # --------------------------------------------------------
    # EMBED
    # --------------------------------------------------------

    embed = discord.Embed(
        title=(
            "🛡️ KINGDOM INTELLIGENCE SYSTEM"
        ),
        description=(
            "Estado general del bot y "
            "servicios de traducción."
        ),
        color=COLOR_META
    )

    embed.add_field(
        name="🤖 Discord",
        value=(
            f"{discord_estado}\n"
            f"Latencia: {latency}ms"
        ),
        inline=True
    )

    embed.add_field(
        name="🧠 Groq",
        value=groq_estado,
        inline=True
    )

    embed.add_field(
        name="🌎 Google",
        value=google_estado,
        inline=True
    )

    embed.add_field(
        name="🆘 MyMemory",
        value=mymemory_estado,
        inline=True
    )

    embed.add_field(
        name="🌐 Traducción",
        value=traduccion_estado,
        inline=True
    )

    embed.add_field(
        name="📦 Cola",
        value=(
            "Máximo: 3 traducciones simultáneas"
        ),
        inline=True
    )

    embed.add_field(
        name="⏱️ Uptime",
        value=(
            f"{horas}h "
            f"{minutos}m "
            f"{segundos}s"
        ),
        inline=False
    )

    embed.add_field(
        name="🔄 Último Groq",
        value=tiempo_desde(
            groq_last_success
        ),
        inline=True
    )

    embed.add_field(
        name="🔄 Último Google",
        value=tiempo_desde(
            google_last_success
        ),
        inline=True
    )

    embed.add_field(
        name="🔄 Último MyMemory",
        value=tiempo_desde(
            mymemory_last_success
        ),
        inline=True
    )

    if groq_last_error:

        embed.add_field(
            name="⚠️ Último error Groq",
            value=limitar_texto(
                groq_last_error,
                500
            ),
            inline=False
        )

    if google_last_error:

        embed.add_field(
            name="⚠️ Último error Google",
            value=limitar_texto(
                google_last_error,
                500
            ),
            inline=False
        )

    embed.set_footer(
        text=(
            "META • Sistema protegido "
            "contra fallos de traducción"
        )
    )

    await message.channel.send(
        embed=embed
    )


# ============================================================
# MENSAJES
# ============================================================

@client.event
async def on_message(
    message
):

    if message.author.bot:
        return

    contenido = message.content.strip()

    if not contenido:
        return

    if not contenido.lower().startswith(
        "meta "
    ):
        return

    partes = contenido[
        5:
    ].strip().split()

    if not partes:
        return

    comando = partes[0].lower()

    args = " ".join(
        partes[1:]
    ).strip()


    # ========================================================
    # META ESTADO
    # ========================================================

    if comando == "estado":

        await comando_estado(
            message
        )

        return


    # ========================================================
    # META TRADUCCION ON/OFF
    # ========================================================

    if comando == "traduccion":

        opcion = args.lower()

        if opcion == "off":

            global translation_enabled

            translation_enabled = False

            await message.channel.send(
                "🛑 Sistema de traducción "
                "desactivado temporalmente.",
                delete_after=8
            )

            return

        if opcion == "on":

            translation_enabled = True

            await message.channel.send(
                "🟢 Sistema de traducción "
                "activado nuevamente.",
                delete_after=8
            )

            return

        await message.channel.send(
            "❌ Usa:\n"
            "`meta traduccion on`\n"
            "`meta traduccion off`"
        )

        return


    # ========================================================
    # META ACTIVATE
    # ========================================================

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

        procesando_activate.add(
            message.author.id
        )

        try:

            usuario = message.mentions[0]

            texto_mensaje = (
                obtener_texto_sin_menciones(
                    message
                )
            )

            datos = (
                await corregir_y_traducir_ia(
                    texto_mensaje
                )
            )

            if "⚠️" in datos["en"]:

                mensaje_extra = (
                    "\n\n"
                    "💬 MENSAJE / MESSAGE:\n"
                    f"🇲🇽 {datos['es']}\n"
                    "🇺🇸 Translation failed - "
                    "Use ES text"
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
                description=descripcion[
                    :4096
                ],
                color=COLOR_ACTIVATE
            )

            embed.set_footer(
                text=(
                    "Agrega una bandera al mensaje "
                    "para solicitar traducción"
                )
            )

            canal_activate = (
                client.get_channel(
                    ID_CANAL_ACTIVATE
                )
            )

            if canal_activate is None:

                canal_activate = (
                    message.channel
                )

            msg_publicado = (
                await canal_activate.send(
                    content=usuario.mention,
                    embed=embed
                )
            )

            mensajes_con_banderas[
                msg_publicado.id
            ] = {
                "texto_es": datos["es"],
                "tipo": "activate"
            }

            try:
                await message.delete()
            except Exception:
                pass

        except Exception as e:

            print(
                f"[ERROR ACTIVATE] {e}"
            )

            try:

                await message.channel.send(
                    "❌ Ocurrió un error "
                    "al activar el protocolo."
                )

            except Exception:
                pass

        finally:

            procesando_activate.discard(
                message.author.id
            )

        return


    # ========================================================
    # META CUMPLEAÑOS
    # ========================================================

    if comando == "cumpleaños":

        if not message.mentions:

            await message.channel.send(
                "❌ Menciona al usuario:\n"
                "`meta cumpleaños @usuario [mensaje]`"
            )

            return

        usuario = message.mentions[0]

        texto_custom = (
            obtener_texto_sin_menciones(
                message
            )
        )

        try:
            await message.delete()
        except Exception:
            pass

        if texto_custom:

            datos = (
                await corregir_y_traducir_ia(
                    texto_custom
                )
            )

            mensaje_es = datos["es"]

            mensaje_en = datos["en"]

        else:

            mensaje_es = (
                f"¡Feliz cumpleaños "
                f"{usuario.display_name}! "
                "🎉🎂 Que tengas un día increíble."
            )

            mensaje_en = (
                f"Happy birthday "
                f"{usuario.display_name}! "
                "🎉🎂 Have an amazing day."
            )

        embed = discord.Embed(
            title="🎂 ¡FELIZ CUMPLEAÑOS!",
            color=COLOR_CUMPLEANOS
        )

        embed.add_field(
            name="🇲🇽 Español",
            value=limitar_texto(
                mensaje_es
            ),
            inline=False
        )

        embed.add_field(
            name="🇺🇸 English",
            value=limitar_texto(
                mensaje_en
            ),
            inline=False
        )

        embed.set_thumbnail(
            url=usuario.display_avatar.url
        )

        embed.set_footer(
            text=(
                "Agrega una bandera al mensaje "
                "para solicitar traducción"
            )
        )

        canal = (
            client.get_channel(
                ID_CANAL_ANUNCIOS
            )
            or message.channel
        )

        msg_publicado = (
            await canal.send(
                content=(
                    f"{usuario.mention} @everyone"
                ),
                embed=embed
            )
        )

        mensajes_con_banderas[
            msg_publicado.id
        ] = {
            "texto_es": mensaje_es,
            "tipo": "cumpleaños"
        }

        ultimo_anuncio[
            message.channel.id
        ] = msg_publicado

        return


    # ========================================================
    # META EVENTO / ALERTA
    # ========================================================

    if comando in [
        "evento",
        "alerta"
    ]:

        if not args:
            return

        try:
            await message.delete()
        except Exception:
            pass

        procesando = (
            await message.channel.send(
                "⏳ Corrigiendo y traduciendo..."
            )
        )

        try:

            datos = (
                await corregir_y_traducir_ia(
                    args
                )
            )

        finally:

            try:
                await procesando.delete()
            except Exception:
                pass

        if comando == "evento":

            titulo = "⚔️ EVENTO"

        else:

            titulo = "🚨 ALERTA"

        embed = discord.Embed(
            title=titulo,
            color=COLOR_ALERTA
        )

        embed.add_field(
            name="🇲🇽 Español",
            value=limitar_texto(
                datos["es"]
            ),
            inline=False
        )

        embed.add_field(
            name="🇺🇸 English",
            value=limitar_texto(
                datos["en"]
            ),
            inline=False
        )

        embed.set_footer(
            text=(
                "Agrega una bandera al mensaje "
                "para solicitar traducción"
            )
        )

        canal = (
            client.get_channel(
                ID_CANAL_ANUNCIOS
            )
            or message.channel
        )

        msg_publicado = (
            await canal.send(
                content="@everyone",
                embed=embed
            )
        )

        mensajes_con_banderas[
            msg_publicado.id
        ] = {
            "texto_es": datos["es"],
            "tipo": comando
        }

        ultimo_anuncio[
            message.channel.id
        ] = msg_publicado

        return


    # ========================================================
    # META BUFF
    # ========================================================

    if comando in [
        "buffo",
        "bufo",
        "buff"
    ]:

        if not args:
            return

        try:
            await message.delete()
        except Exception:
            pass

        datos = (
            await corregir_y_traducir_ia(
                args
            )
        )

        embed = discord.Embed(
            title="🛎️ BUFO ACTIVADO",
            color=COLOR_META
        )

        embed.add_field(
            name="🇲🇽 Español",
            value=(
                "✅ "
                + limitar_texto(
                    datos["es"]
                )
            ),
            inline=False
        )

        embed.add_field(
            name="🇺🇸 English",
            value=(
                "✅ "
                + limitar_texto(
                    datos["en"]
                )
            ),
            inline=False
        )

        embed.set_footer(
            text=(
                "Agrega una bandera al mensaje "
                "para solicitar traducción"
            )
        )

        canal_buff = (
            client.get_channel(
                ID_CANAL_BUFF
            )
            or message.channel
        )

        msg_publicado = (
            await canal_buff.send(
                content="@everyone",
                embed=embed
            )
        )

        mensajes_con_banderas[
            msg_publicado.id
        ] = {
            "texto_es": datos["es"],
            "tipo": "buffo"
        }

        ultimo_anuncio[
            message.channel.id
        ] = msg_publicado

        return


    # ========================================================
    # META EDITAR
    # ========================================================

    if comando == "editar":

        if not args:

            await message.channel.send(
                "❌ Escribe el nuevo texto:\n"
                "`meta editar nuevo texto`"
            )

            return

        if message.channel.id not in (
            ultimo_anuncio
        ):

            await message.channel.send(
                "❌ No hay anuncio reciente "
                "para editar en este canal."
            )

            return

        msg_a_editar = ultimo_anuncio[
            message.channel.id
        ]

        datos = (
            await corregir_y_traducir_ia(
                args
            )
        )

        try:

            if not msg_a_editar.embeds:

                raise RuntimeError(
                    "El mensaje no tiene embed."
                )

            embed = (
                msg_a_editar.embeds[0]
            )

            embed.clear_fields()

            titulo = (
                embed.title or ""
            )

            if "CUMPLEAÑOS" in titulo:

                embed.add_field(
                    name="🇲🇽 Español",
                    value=datos["es"],
                    inline=False
                )

                embed.add_field(
                    name="🇺🇸 English",
                    value=datos["en"],
                    inline=False
                )

            elif "BUFO" in titulo:

                embed.add_field(
                    name="🇲🇽 Español",
                    value=(
                        f"✅ {datos['es']}"
                    ),
                    inline=False
                )

                embed.add_field(
                    name="🇺🇸 English",
                    value=(
                        f"✅ {datos['en']}"
                    ),
                    inline=False
                )

            else:

                embed.add_field(
                    name="🇲🇽 Español",
                    value=datos["es"],
                    inline=False
                )

                embed.add_field(
                    name="🇺🇸 English",
                    value=datos["en"],
                    inline=False
                )

            await msg_a_editar.edit(
                embed=embed
            )

            if (
                msg_a_editar.id
                in mensajes_con_banderas
            ):

                mensajes_con_banderas[
                    msg_a_editar.id
                ]["texto_es"] = datos["es"]

            try:
                await message.delete()
            except Exception:
                pass

            await message.channel.send(
                "✅ Anuncio editado.",
                delete_after=5
            )

        except Exception as e:

            print(
                f"[ERROR EDITAR] {e}"
            )

            await message.channel.send(
                "❌ No se pudo editar "
                "el anuncio."
            )

        return


    # ========================================================
    # META LIMPIA
    # ========================================================

    if comando == "limpia":

        cantidad = 10

        if args and args.isdigit():

            cantidad = int(args)

        cantidad = max(
            1,
            min(cantidad, 50)
        )

        try:
            await message.delete()
        except Exception:
            pass

        borrados = 0

        try:

            async for msg in (
                message.channel.history(
                    limit=100
                )
            ):

                if (
                    client.user
                    and msg.author.id
                    != client.user.id
                ):
                    continue

                try:

                    await msg.delete()

                    borrados += 1

                    if borrados >= cantidad:
                        break

                    await asyncio.sleep(
                        0.5
                    )

                except Exception:
                    pass

        except Exception as e:

            print(
                f"[ERROR LIMPIA] {e}"
            )

        await message.channel.send(
            f"🧹 Borrados {borrados} "
            "mensajes del bot.",
            delete_after=5
        )

        return


    # ========================================================
    # META PING
    # ========================================================

    if comando == "ping":

        latencia = round(
            client.latency * 1000
        )

        await message.channel.send(
            f"🟢 Latencia: {latencia}ms"
        )

        return


    # ========================================================
    # META AYUDA
    # ========================================================

    if comando == "ayuda":

        embed = discord.Embed(
            title="📋 COMANDOS META BOT",
            color=COLOR_META
        )

        embed.add_field(
            name=(
                "🚨 meta activate "
                "@usuario [mensaje]"
            ),
            value=(
                "Código de emergencia ES/EN"
            ),
            inline=False
        )

        embed.add_field(
            name=(
                "🎂 meta cumpleaños "
                "@usuario [mensaje]"
            ),
            value=(
                "Felicitación ES/EN"
            ),
            inline=False
        )

        embed.add_field(
            name="📢 meta alerta <texto>",
            value="Alerta ES/EN",
            inline=False
        )

        embed.add_field(
            name="⚔️ meta evento <texto>",
            value="Evento ES/EN",
            inline=False
        )

        embed.add_field(
            name="🛎️ meta buffo <texto>",
            value=(
                "Bufo ES/EN + @everyone"
            ),
            inline=False
        )

        embed.add_field(
            name="✏️ meta editar <texto>",
            value=(
                "Edita el último anuncio"
            ),
            inline=False
        )

        embed.add_field(
            name="🧹 meta limpia [cantidad]",
            value=(
                "Borra mensajes del bot | "
                "Máx. 50"
            ),
            inline=False
        )

        embed.add_field(
            name="🟢 meta ping",
            value="Verifica latencia",
            inline=False
        )

        embed.add_field(
            name="🛡️ meta estado",
            value=(
                "Revisa Discord, Groq, "
                "Google, MyMemory y traducción."
            ),
            inline=False
        )

        embed.add_field(
            name="🌎 meta traduccion on/off",
            value=(
                "Activa o desactiva "
                "temporalmente el traductor."
            ),
            inline=False
        )

        embed.add_field(
            name="👻 Traducción",
            value=(
                "Las banderas NO son agregadas "
                "automáticamente. "
                "Agrega una bandera manualmente "
                "al mensaje para solicitar traducción."
            ),
            inline=False
        )

        embed.add_field(
            name="📩 DM",
            value=(
                "Las traducciones se envían por DM, "
                "excepto 🇪🇸 🇺🇸 🇹🇷 en "
                "#oficiales, #diplomacia, "
                "#general y #bitácora."
            ),
            inline=False
        )

        embed.set_footer(
            text=(
                "META ESTÁ CONTIGO. "
                "UN REINO, UNA ALIANZA, UNA META"
            )
        )

        await message.channel.send(
            embed=embed
        )

        return


# ============================================================
# REACCIONES / BANDERAS
# ============================================================

@client.event
async def on_raw_reaction_add(
    payload
):

    # --------------------------------------------------------
    # Ignorar al propio bot
    # --------------------------------------------------------

    if (
        client.user
        and payload.user_id
        == client.user.id
    ):
        return


    # --------------------------------------------------------
    # Emoji
    # --------------------------------------------------------

    emoji = str(
        payload.emoji
    )

    if emoji not in BANDERAS:
        return


    # --------------------------------------------------------
    # Evitar duplicados
    # --------------------------------------------------------

    reaction_key = (
        payload.user_id,
        payload.message_id,
        emoji
    )

    if reaction_key in traduciendo_users:
        return

    traduciendo_users.add(
        reaction_key
    )


    try:

        # ----------------------------------------------------
        # Traducción desactivada
        # ----------------------------------------------------

        if not translation_enabled:

            return


        # ----------------------------------------------------
        # Canal
        # ----------------------------------------------------

        channel = client.get_channel(
            payload.channel_id
        )

        if channel is None:
            return


        # ----------------------------------------------------
        # Mensaje
        # ----------------------------------------------------

        message = await channel.fetch_message(
            payload.message_id
        )


        # ----------------------------------------------------
        # Usuario
        # ----------------------------------------------------

        try:

            user = await client.fetch_user(
                payload.user_id
            )

        except Exception as e:

            print(
                f"[ERROR USUARIO] {e}"
            )

            return


        # ----------------------------------------------------
        # ELIMINAR REACCIÓN
        #
        # Esto mantiene las banderas ocultas.
        # ----------------------------------------------------

        try:

            await message.remove_reaction(
                payload.emoji,
                user
            )

        except Exception as e:

            print(
                f"[WARN REACCIÓN] {e}"
            )


        # ====================================================
        # DETERMINAR TEXTO A TRADUCIR
        # ====================================================

        texto_original = None


        # ----------------------------------------------------
        # MENSAJES DEL BOT
        # ----------------------------------------------------

        if (
            payload.message_id
            in mensajes_con_banderas
        ):

            data = (
                mensajes_con_banderas[
                    payload.message_id
                ]
            )

            texto_original = data.get(
                "texto_es"
            )


        # ----------------------------------------------------
        # MENSAJES NORMALES
        # ----------------------------------------------------

        else:

            if message.author.bot:

                return

            texto_original = (
                message.content.strip()
            )


        # ----------------------------------------------------
        # Validación
        # ----------------------------------------------------

        if not texto_original:
            return

        texto_original = limpiar_texto(
            texto_original
        )

        if len(texto_original) < 2:
            return


        # ----------------------------------------------------
        # Idioma
        # ----------------------------------------------------

        idioma = BANDERAS[
            emoji
        ]

        nombre = NOMBRES_IDIOMAS.get(
            idioma,
            idioma
        )


        # ====================================================
        # TRADUCIR
        # ====================================================

        traduccion = (
            await traducir_seguro(
                texto_original,
                idioma
            )
        )


        # ====================================================
        # 🇪🇸 🇺🇸 🇹🇷 DIRECTO AL CANAL
        #
        # SOLO 4 CANALES
        # ====================================================

        if (
            payload.channel_id
            in CANALES_TRADUCCION_DIRECTA
            and idioma in [
                "es",
                "en",
                "tr"
            ]
        ):

            if idioma == "es":

                flag_emoji = "🇪🇸"

            elif idioma == "en":

                flag_emoji = "🇺🇸"

            else:

                flag_emoji = "🇹🇷"


            embed = discord.Embed(
                description=(
                    f"{flag_emoji} "
                    f"{limitar_texto("
                        traduccion,
                        4000
                    )}"
                ),
                color=COLOR_TRADUCCION
            )

            # Mantenerlo temporal para evitar basura.
            delete_timer = 40 if (
                idioma == "tr"
            ) else 20

            await channel.send(
                embed=embed,
                delete_after=delete_timer
            )

            return


        # ====================================================
        # TODO LO DEMÁS → DM
        # ====================================================

        embed_dm = (
            crear_embed_traduccion(
                emoji,
                nombre,
                texto_original,
                traduccion
            )
        )

        try:

            await user.send(
                embed=embed_dm
            )

        except discord.Forbidden:

            print(
                f"📩 DM cerrado para {user}."
            )

            try:

                await channel.send(
                    (
                        f"{user.mention} "
                        "⚠️ No puedo enviarte la "
                        "traducción porque tienes "
                        "los mensajes directos cerrados."
                    ),
                    delete_after=8
                )

            except Exception:
                pass

    except Exception as e:

        print(
            f"[ERROR REACCIÓN] {e}"
        )

    finally:

        await asyncio.sleep(
            3
        )

        traduciendo_users.discard(
            reaction_key
        )


# ============================================================
# LIMPIEZA DE MEMORIA
# ============================================================

async def limpieza_memoria():

    while True:

        await asyncio.sleep(
            3600
        )

        # Limitar memoria de mensajes
        if len(
            mensajes_con_banderas
        ) > 1000:

            ids = list(
                mensajes_con_banderas.keys()
            )

            for message_id in ids[:500]:

                mensajes_con_banderas.pop(
                    message_id,
                    None
                )

        # Limitar memoria de anuncios
        if len(
            ultimo_anuncio
        ) > 500:

            ids = list(
                ultimo_anuncio.keys()
            )

            for channel_id in ids[:250]:

                ultimo_anuncio.pop(
                    channel_id,
                    None
                )

        print(
            "🧹 Limpieza de memoria ejecutada."
        )


# ============================================================
# SERVIDOR HTTP PARA RENDER
# ============================================================

class Handler(
    BaseHTTPRequestHandler
):

    def do_HEAD(self):

        self.send_response(
            200
        )

        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )

        self.end_headers()


    def do_GET(self):

        self.send_response(
            200
        )

        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )

        self.end_headers()

        self.wfile.write(
            b"Kingdom Intelligence System - Bot alive"
        )


    def log_message(
        self,
        format,
        *args
    ):

        return


def run_server():

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    server = HTTPServer(
        (
            "0.0.0.0",
            port
        ),
        Handler
    )

    print(
        f"🌐 HTTP Server activo "
        f"en puerto {port}"
    )

    server.serve_forever()


# ============================================================
# ARRANCAR HTTP
# ============================================================

threading.Thread(
    target=run_server,
    daemon=True
).start()


# ============================================================
# ARRANCAR LIMPIEZA
# ============================================================

async def iniciar_tareas():

    await client.wait_until_ready()

    asyncio.create_task(
        limpieza_memoria()
    )

    print(
        "🧹 Sistema de limpieza iniciado."
    )


# ============================================================
# ARRANCAR BOT
# ============================================================

print(
    "🚀 Iniciando "
    "Kingdom Intelligence System..."
)

client.run(
    TOKEN
)
