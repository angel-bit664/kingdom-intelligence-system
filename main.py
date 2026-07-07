import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
import requests
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

def buscar_google(query):
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    data = {"q": query, "num": 3}
    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        if response.status_code == 200:
            return response.json().get("organic", [])
        return []
    except Exception as e:
        print(f"Error en búsqueda: {e}")
        return []

def traducir_es_en(texto):
    """Traduce de español a inglés. Si falla, regresa el original"""
    try:
        return GoogleTranslator(source='es', target='en').translate(texto)
    except:
        return "Translation failed"

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    print('------')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong! 📬 Bot activo')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    msg = message.content.lower()

    if msg.startswith("meta "):
        peticion = message.content[5:].strip()

        # META ALERTA - SOLO R5 Y R4 OFICIALES - 3 TIPOS: GUERRA, EVENTO, INFO
        if peticion.lower().startswith("alerta "):
            # RESTRICCIÓN DE ROLES - SOLO R5 Y R4
            # AJUSTA ESTOS NOMBRES A COMO SE LLAMAN TUS ROLES EXACTO
            roles_permitidos = ["R5", "Líder", "Oficiales | R4", "R4"]
            tiene_permiso = any(any(rol_busqueda.lower() in role.name.lower() for rol_busqueda in roles_permitidos) for role in message.author.roles)

            if not tiene_permiso:
                await message.channel.send("❌ Solo R5 y R4 Oficiales pueden enviar alertas")
                return

            resto = peticion[7:].strip()

            # Detectar tipo de alerta
            tipo_alerta = "guerra" # default
            if resto.lower().startswith("guerra "):
                tipo_alerta = "guerra"
                resto = resto[7:].strip()
            elif resto.lower().startswith("evento "):
                tipo_alerta = "evento"
                resto = resto[7:].strip()
            elif resto.lower().startswith("info "):
                tipo_alerta = "info"
                resto = resto[5:].strip()

            if message.channel_mentions:
                canal_destino = message.channel_mentions[0]
                contenido_es = resto.replace(canal_destino.mention, "").strip()
                canal_aviso = message.channel
            else:
                canal_destino = message.channel
                contenido_es = resto
                canal_aviso = None

            if not contenido_es:
                ayuda = """**Usa:**
`meta alerta guerra texto` - Para batallas/KVK
`meta alerta evento texto` - Para eventos/premios
`meta alerta info texto` - Para avisos generales
Ej: `meta alerta evento #anuncios Torneo hoy 9pm UTC`"""
                await message.channel.send(ayuda)
                return

            permisos = canal_destino.permissions_for(message.guild.me)
            if not permisos.send_messages or not permisos.mention_everyone:
                await message.channel.send(f"❌ No tengo permisos en {canal_destino.mention}. Activa 'Enviar Mensajes' y 'Mencionar @everyone'")
                return

            contenido_en = traducir_es_en(contenido_es)
            organizador = message.author.display_name

            # FORMATO GUERRA
            if tipo_alerta == "guerra":
                mensaje_formateado = f"""@everyone

👑 **Familia TFT / TFT Family** 👑

📢 **Necesitamos el apoyo de todos / We need everyone's support.**

🎯 **Misión / Mission:**
🇲🇽 {contenido_es}
🇺🇸 {contenido_en}

⏰ **Hora / Time:** Preguntar a líder / Ask leader
👤 **Organiza / Host:** {organizador}
💬 **Dudas / Questions:** #{message.channel.name}

🔥 **Todos están invitados / Everyone is invited.** Si quieren pelear y defender / If you want to fight and defend, los esperamos / we are waiting for you.

**¡Vamos TFT / Let's go TFT! ¡Aún queda guerra por delante / War is still ahead!** 👑 ⚔️"""

            # FORMATO EVENTO
            elif tipo_alerta == "evento":
                mensaje_formateado = f"""@everyone

🎉 **Evento TFT / TFT Event** 🎉

📢 **Atención familia / Attention family**

🎯 **Detalles / Details:**
🇲🇽 {contenido_es}
🇺🇸 {contenido_en}

👤 **Organiza / Host:** {organizador}
💬 **Info / Info:** #{message.channel.name}

✨ **¡Los esperamos / We await you!** ¡No falten / Don't miss it! 🎁"""

            # FORMATO INFO/AVISO
            else:
                mensaje_formateado = f"""@everyone

📢 **Aviso TFT / TFT Notice** 📢

ℹ️ **Información / Information:**
🇲🇽 {contenido_es}
🇺🇸 {contenido_en}

👤 **Organiza / Host:** {organizador}"""

            try:
                await canal_destino.send(mensaje_formateado)
                if canal_aviso:
                    await canal_aviso.send(f"✅ Alerta `{tipo_alerta}` ES/EN enviada a {canal_destino.mention}")
            except Exception as e:
                await message.channel.send(f"Error al enviar: {e}")
            return

        # META CREAR ANUNCIO - BILINGÜE
        elif peticion.lower().startswith("crear anuncio"):
            anuncio_es = peticion[14:].strip()
            if not anuncio_es:
                await message.channel.send("¿Cuál es el anuncio? `meta crear anuncio texto`")
                return
            anuncio_en = traducir_es_en(anuncio_es)
            embed = discord.Embed(title="📢 ANUNCIO / ANNOUNCEMENT", color=discord.Color.red())
            embed.add_field(name="🇲🇽 Español", value=anuncio_es, inline=False)
            embed.add_field(name="🇺🇸 English", value=anuncio_en, inline=False)
            embed.set_footer(text=f"Anuncio por {message.author.display_name}")
            await message.channel.send(content="@everyone", embed=embed)
            return

        # META ANUNCIAR - BILINGÜE A OTRO CANAL
        elif peticion.lower().startswith("anunciar "):
            resto = peticion[9:].strip()
            if not message.channel_mentions:
                await message.channel.send("Menciona el canal. Ej: `meta anunciar #anuncios KVK en 1 hora`")
                return
            canal_destino = message.channel_mentions[0]
            anuncio_es = resto.replace(canal_destino.mention, "").strip()
            if not anuncio_es:
                await message.channel.send("¿Cuál es el anuncio?")
                return
            permisos = canal_destino.permissions_for(message.guild.me)
            if not permisos.send_messages or not permisos.mention_everyone:
                await message.channel.send(f"No tengo permisos en {canal_destino.mention}")
                return
            anuncio_en = traducir_es_en(anuncio_es)
            embed = discord.Embed(title="📢 ANUNCIO / ANNOUNCEMENT", color=discord.Color.red())
            embed.add_field(name="🇲🇽 Español", value=anuncio_es, inline=False)
            embed.add_field(name="🇺🇸 English", value=anuncio_en, inline=False)
            embed.set_footer(text=f"Anuncio por {message.author.display_name} desde #{message.channel.name}")
            try:
                await canal_destino.send(content="@everyone", embed=embed)
                await message.channel.send(f"✅ Anuncio ES/EN enviado a {canal_destino.mention}")
            except Exception as e:
                await message.channel.send(f"Error: {e}")
            return

        # META INFO COD - SIN TRADUCTOR
        elif peticion.lower().startswith("info cod"):
            comando = peticion[8:].strip().lower()
            if comando.startswith("reino "):
                num_reino = comando[6:].strip()
                if not num_reino.isdigit():
                    await message.channel.send("Pon el número. Ej: `meta info cod reino 1234`")
                    return
                msg_busqueda = await message.channel.send(f"🔍 Buscando datos del Reino #{num_reino}...")
                query = f"Call of Dragons kingdom {num_reino} power top alliances"
                resultados = buscar_google(query)
                if not resultados:
                    await msg_busqueda.edit(content=f"No encontré info del Reino #{num_reino} 😔")
                    return
                embed = discord.Embed(title=f"🏰 Reino #{num_reino}", color=0x3498db)
                desc = ""
                for r in resultados[:3]:
                    desc += f"**{r.get('title', '')[:60]}**\n{r.get('snippet', '')[:120]}...\n[Ver]({r.get('link', '')})\n\n"
                embed.description = desc
                await msg_busqueda.edit(content=None,
