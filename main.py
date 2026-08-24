import discord
import asyncio
import re
import json
import os
import openai
from datetime import datetime

TOKEN = os.getenv("DISCORD_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

ID_CANAL_ACTIVATE = 123456789 # Tu ID
ID_CANAL_ANUNCIOS = 123456789 # Tu ID
ID_CANAL_BUFF = 123456789 # Tu ID

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
client = discord.Client(intents=intents)

mensajes_con_banderas = {}
ultimo_anuncio = {}
flag_mode_channels = set([ID_CANAL_ANUNCIOS, ID_CANAL_BUFF])
procesando_activate = set()
traduciendo_users = set() # Anti-spam

BANDERAS = {
    '🇧🇷': 'pt', '🇫🇷': 'fr', '🇩🇪': 'de', '🇮🇹': 'it',
    '🇷🇺': 'ru', '🇯🇵': 'ja', '🇰🇷': 'ko', '🇨🇳': 'zh', '🇮🇩': 'id',
    '🇺🇸': 'en', '🇪🇸': 'es'
}

NOMBRES_IDIOMAS = {
    'pt': 'Portugués', 'fr': 'Francés', 'de': 'Alemán', 'it': 'Italiano',
    'ru': 'Ruso', 'ja': 'Japonés', 'ko': 'Coreano', 'zh': 'Chino',
    'id': 'Indonesio', 'en': 'Inglés', 'es': 'Español'
}

async def corregir_y_traducir_ia(texto_original: str):
    texto_limpio = re.sub(r'[@#]', '', texto_original)
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()

    if len(texto_limpio) < 3:
        return {'es': texto_original, 'en': '⚠️ Message too short'}

    try:
        response = await asyncio.wait_for(
            openai.ChatCompletion.acreate(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": f"Corrige español y traduce a inglés. Solo JSON: {{\"es\": \"...\", \"en\": \"...\"}}. Texto: {texto_limpio}"
                }],
                temperature=0.1,
                response_format={"type": "json_object"}
            ),
            timeout=8.0
        )
        datos = json.loads(response.choices[0].message.content)
        if any(x in datos['en'].lower() for x in ['error 500', 'server error', 'there was an error']):
            raise Exception("API devolvió error")
        return {'es': datos['es'][:1024], 'en': datos['en'][:1024]}
    except Exception as e:
        print(f"[IA FAIL] {datetime.now()} | {e}")
        return {'es': texto_limpio, 'en': '⚠️ Auto-translation failed. Use ES text above.'}

async def traducir_a_idioma(texto, idioma_destino):
    try:
        response = await asyncio.wait_for(
            openai.ChatCompletion.acreate(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": f"Traduce a {idioma_destino}. Solo texto: {texto}"}],
                temperature=0.1
            ),
            timeout=8.0
        )
        return response.choices[0].message.content[:1024]
    except:
        return "⚠️ Translation failed"

@client.event
async def on_ready():
    print(f'{client.user} conectado. Banderas ocultas ON.')

@client.event
async def on_message(message):
    if message.author == client.user: return
    if not message.content.startswith("meta "): return

    args = message.content[5:].strip()
    comando = args.split()[0].lower() if args else ""
    args = " ".join(args.split()[1:]) if len(args.split()) > 1 else ""

    # ACTIVATE
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
        embed.set_footer(text="Reacciona con 🇺🇸🇧🇷🇯🇵 para traducir a otros idiomas")

        canal_activate = client.get_channel(ID_CANAL_ACTIVATE)
        if canal_activate is None: canal_activate = message.channel
        try:
            msg_publicado = await canal_activate.send(content=usuarios_texto, embed=embed)
            mensajes_con_banderas[msg_publicado.id] = {"texto_es": datos['es'], "tipo": "activate"}
        except: pass

        try: await message.delete()
        except: pass
        finally: procesando_activate.discard(message.author.id)
        return

    # CUMPLEAÑOS
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
        embed.set_footer(text="Reacciona con 🇺🇸🇧🇷🇯🇵 para traducir a otros idiomas")

        canal = client.get_channel(ID_CANAL_ANUNCIOS)
        if canal is None: canal = message.channel
        msg_publicado = await canal.send(content=f"{usuario.mention} @everyone", embed=embed)
        mensajes_con_banderas[msg_publicado.id] = {"texto_es": mensaje_es, "tipo": "cumpleaños"}
        ultimo_anuncio[message.channel.id] = msg_publicado
        # YA NO PONE BANDERAS AUTOMÁTICAS
        return

    # EVENTO / ALERTA
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

        if "⚠️" in datos['en']:
            embed.set_footer(text="Traducción automática falló. Reacciona con 🇺🇸🇧🇷🇯🇵 para traducir manual")
        else:
            embed.set_footer(text="Reacciona con 🇺🇸🇧🇷🇯🇵 para traducir a otros idiomas")

        canal = client.get_channel(ID_CANAL_ANUNCIOS)
        if canal is None: canal = message.channel
        msg_publicado = await canal.send("@everyone", embed=embed)
        mensajes_con_banderas[msg_publicado.id] = {"texto_es": datos['es'], "tipo": comando}
        ultimo_anuncio[message.channel.id] = msg_publicado
        # YA NO PONE BANDERAS AUTOMÁTICAS
        return

    # BUFFO
    if comando in ["buffo", "bufo", "buff"]:
        if not args: return
        try: await message.delete()
        except: pass

        datos = await corregir_y_traducir_ia(args)
        embed = discord.Embed(title="🛎️ BUFO ACTIVADO", color=0x9B59B6)
        embed.add_field(name="🇲🇽 Español", value=f"✅ {datos['es']}", inline=False)
        embed.add_field(name="🇺🇸 English", value=f"✅ {datos['en']}", inline=False)
        embed.set_footer(text="Reacciona con 🇺🇸🇧🇷🇯🇵 para traducir a otros idiomas")

        canal_buff = client.get_channel(ID_CANAL_BUFF)
        if canal_buff is None: canal_buff = message.channel
        msg_publicado = await canal_buff.send("@everyone", embed=embed)
        mensajes_con_banderas[msg_publicado.id] = {"texto_es": datos['es'], "tipo": "buffo"}
        ultimo_anuncio[message.channel.id] = msg_publicado
        # YA NO PONE BANDERAS AUTOMÁTICAS
        return

    # EDITAR
    if comando == "editar":
        if not args:
            await message.channel.send("❌ Escribe el nuevo texto: `meta editar nuevo texto`")
            return
        if message.channel.id not in ultimo_anuncio:
            await message.channel.send("❌ No hay anuncio reciente para editar.")
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
        except:
            await message.channel.send("❌ No se pudo editar.")
        return

    # LIMPIA
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
        await message.channel.send(f"🧹 Borrados {borrados} mensajes.", delete_after=5)
        return

    # PING
    if comando == "ping":
        await message.channel.send(f"🟢 Latencia: {round(client.latency*1000)}ms")
        return

    # AYUDA
    if comando == "ayuda":
        embed = discord.Embed(title="📋 COMANDOS META BOT", color=0x9B59B6)
        embed.add_field(name="🚨 meta activate @usuario [mensaje]", value="Código emergencia ES/EN", inline=False)
        embed.add_field(name="🎂 meta cumpleaños @usuario [mensaje]", value="Felicitación ES/EN", inline=False)
        embed.add_field(name="📢 meta alerta <texto>", value="Alerta ES/EN", inline=False)
        embed.add_field(name="⚔️ meta evento <texto>", value="Evento ES/EN", inline=False)
        embed.add_field(name="🛎️ meta buffo <texto>", value="Bufo ES/EN + @everyone", inline=False)
        embed.add_field(name="✏️ meta editar <texto>", value="Edita último anuncio", inline=False)
        embed.add_field(name="🧹 meta limpia [cantidad]", value="Borra mensajes bot | Max 50", inline=False)
        embed.add_field(name="🟢 meta ping", value="Verifica latencia", inline=False)
        embed.add_field(name="🌍 Traducir", value="Reacciona con 🇺🇸🇧🇷🇯🇵🇫🇷🇩🇪 en cualquier anuncio pa traducir", inline=False)
        embed.set_footer(text="META ESTÁ CONTIGO. UN REINO, UNA ALIANZA, UNA META")
        await message.channel.send(embed=embed)
        return

@client.event
async def on_raw_reaction_add(payload):
    if payload.user_id == client.user.id: return
    emoji = str(payload.emoji)
    if emoji not in BANDERAS: return

    # ANTI-SPAM: Si el user ya está traduciendo, ignora
    if payload.user_id in traduciendo_users: return
    traduciendo_users.add(payload.user_id)

    try:
        channel = client.get_channel(payload.channel_id)
        if channel is None: return
        message = await channel.fetch_message(payload.message_id)

        # SOLO TRADUCE SI ESTÁ EN LOS ÚLTIMOS 50
        ultimos_50 = [msg async for msg in channel.history(limit=50)]
        if message.id not in [m.id for m in ultimos_50]:
            try:
                user = await client.fetch_user(payload.user_id)
                await message.remove_reaction(payload.emoji, user)
            except: pass
            return

        # QUITA LA REACCIÓN DEL USER PA QUE PUEDA USARLA OTRA VEZ
        try:
            user = await client.fetch_user(payload.user_id)
            await message.remove_reaction(payload.emoji, user)
        except: pass

        # TRADUCE ANUNCIOS DEL BOT
        if payload.message_id in mensajes_con_banderas:
            data = mensajes_con_banderas[payload.message_id]
            traduccion = await traducir_a_idioma(data['texto_es'], BANDERAS[emoji])
            nombre = NOMBRES_IDIOMAS.get(BANDERAS[emoji], BANDERAS[emoji])
            embed_dm = discord.Embed(title=f"{emoji} Traducción a {nombre}", color=0x00FF00)
            embed_dm.add_field(name="Original", value=data['texto_es'][:1024], inline=False)
            embed_dm.add_field(name="Traducción", value=traduccion, inline=False)
            await user.send(embed=embed_dm)
            return

        # TRADUCE MENSAJES NORMALES EN CANALES ACTIVOS
        if payload.channel_id in flag_mode_channels:
            if message.author.bot or len(message.content.strip()) < 2: return
            traduccion = await traducir_a_idioma(message.content, BANDERAS[emoji])
            if BANDERAS[emoji] in ['es', 'en']:
                flag_emoji = '🇪🇸' if BANDERAS[emoji] == 'es' else '🇺🇸'
                embed = discord.Embed(description=f"{flag_emoji} {traduccion}", color=0x00B0F4)
                await channel.send(embed=embed, delete_after=20)
            else:
                nombre = NOMBRES_IDIOMAS.get(BANDERAS[emoji], BANDERAS[emoji])
                embed_dm = discord.Embed(title=f"{emoji} Traducción a {nombre}", color=0x00FF00)
                embed_dm.add_field(name="Original", value=message.content[:1024], inline=False)
                embed_dm.add_field(name="Traducción", value=traduccion, inline=False)
                await user.send(embed=embed_dm)

    except Exception as e:
        print(f"[ERROR REACCIÓN] {e}")
    finally:
        # Quita el lock después de 3s pa evitar spam
        await asyncio.sleep(3)
        traduciendo_users.discard(payload.user_id)

client.run(TOKEN)
