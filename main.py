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
    """Busca en Google usando Serper API"""
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

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    print(f'Bot ID: {bot.user.id}')
    print('------')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong! 📬 Bot activo')

@bot.command()
async def traducir(ctx, idioma=None, *, texto=None):
    """Solo traduce cuando usas!traducir"""
    if idioma is None or texto is None:
        await ctx.send("Uso: `!traducir en hola mundo` o `!traducir es hello world`")
        return
    try:
        traducido = GoogleTranslator(source='auto', target=idioma).translate(texto)
        embed = discord.Embed(color=discord.Color.green())
        embed.add_field(name="Original", value=texto, inline=False)
        embed.add_field(name=f"Traducido a {idioma.upper()}", value=traducido, inline=False)
        await ctx.send(embed=embed)
    except:
        await ctx.send("No pude traducir eso 😔 Checa el código de idioma: es, en, fr, de, etc")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    msg = message.content.lower()

    if msg.startswith("meta "):
        peticion = message.content[5:].strip()

        # META CREAR ANUNCIO - MANDA EN EL MISMO CANAL
        if peticion.lower().startswith("crear anuncio"):
            anuncio = peticion[14:].strip()
            if not anuncio:
                await message.channel.send("¿Cuál es el anuncio bro? `meta crear anuncio texto`")
                return
            try:
                anuncio_en = GoogleTranslator(source='es', target='en').translate(anuncio)
            except:
                anuncio_en = "Translation failed"
            embed = discord.Embed(title="📢 ANUNCIO IMPORTANTE", color=discord.Color.red())
            embed.add_field(name="🇲🇽 Español", value=anuncio, inline=False)
            embed.add_field(name="🇺🇸 English", value=anuncio_en, inline=False)
            embed.set_footer(text=f"Anuncio por {message.author.display_name}")
            await message.channel.send(content="@everyone", embed=embed)
            return

        # META ANUNCIAR - NUEVO: MANDA A OTRO CANAL CON @everyone
        elif peticion.lower().startswith("anunciar "):
            resto = peticion[9:].strip()
            
            # Busca si mencionó un canal #anuncios
            if not message.channel_mentions:
                await message.channel.send("Menciona el canal donde lo quieres mandar. Ej: `meta anunciar #anuncios KVK en 1 hora`")
                return
            
            canal_destino = message.channel_mentions[0]
            # Quita la mención del texto
            anuncio = resto.replace(canal_destino.mention, "").strip()
            
            if not anuncio:
                await message.channel.send("¿Cuál es el anuncio? Ej: `meta anunciar #anuncios KVK en 1 hora`")
                return

            # Checa permisos en el canal destino
            permisos = canal_destino.permissions_for(message.guild.me)
            if not permisos.send_messages or not permisos.mention_everyone:
                await message.channel.send(f"No tengo permisos para enviar mensajes o mencionar @everyone en {canal_destino.mention}")
                return

            try:
                anuncio_en = GoogleTranslator(source='es', target='en').translate(anuncio)
            except:
                anuncio_en = "Translation failed"
                
            embed = discord.Embed(title="📢 ANUNCIO IMPORTANTE", color=discord.Color.red())
            embed.add_field(name="🇲🇽 Español", value=anuncio, inline=False)
            embed.add_field(name="🇺🇸 English", value=anuncio_en, inline=False)
            embed.set_footer(text=f"Anuncio por {message.author.display_name} desde #{message.channel.name}")
            
            try:
                await canal_destino.send(content="@everyone", embed=embed)
                await message.channel.send(f"✅ Anuncio enviado a {canal_destino.mention}")
            except Exception as e:
                await message.channel.send(f"Error al enviar: {e}")
            return

        # META INFO COD - MÓDULO CALL OF DRAGONS
        elif peticion.lower().startswith("info cod"):
            comando = peticion[8:].strip().lower()

            if comando.startswith("reino "):
                num_reino = comando[6:].strip()
                if not num_reino.isdigit():
                    await message.channel.send("Pon el número del reino. Ej: `meta info cod reino 1234`")
                    return
                msg_busqueda = await message.channel.send(f"🔍 Buscando datos del Reino #{num_reino}...")
                query = f"Call of Dragons kingdom {num_reino} power top alliances"
                resultados = buscar_google(query)
                if not resultados:
                    await msg_busqueda.edit(content=f"No encontré info pública del Reino #{num_reino} 😔")
                    return
                embed = discord.Embed(title=f"🏰 Reino #{num_reino} - Call of Dragons", color=0x3498db)
                desc = ""
                for r in resultados[:3]:
                    desc += f"**{r.get('title', '')[:60]}**\n{r.get('snippet', '')[:120]}...\n[Ver fuente]({r.get('link', '')})\n\n"
                embed.description = desc
                embed.set_footer(text="Info de Google.")
                await msg_busqueda.edit(content=None, embed=embed)
                return

            elif comando.startswith("heroe "):
                nombre_heroe = comando[6:].strip()
                if not nombre_heroe:
                    await message.channel.send("¿Qué héroe? Ej: `meta info cod heroe liliya`")
                    return
                msg_busqueda = await message.channel.send(f"🔍 Buscando build de **{nombre_heroe}**...")
                query = f"Call of Dragons {nombre_heroe} hero guide build talents 2026"
                resultados = buscar_google(query)
                if not resultados:
                    await msg_busqueda.edit(content=f"No encontré builds de **{nombre_heroe}**")
                    return
                embed = discord.Embed(title=f"⚔️ Héroe: {nombre_heroe.title()}", color=0xe74c3c)
                desc = ""
                for r in resultados[:3]:
                    desc += f"**{r.get('title', '')[:60]}**\n{r.get('snippet', '')[:120]}...\n[Guía]({r.get('link', '')})\n\n"
                embed.description = desc
                await msg_busqueda.edit(content=None, embed=embed)
                return

            elif comando.startswith("mascota ") or comando.startswith("pet "):
                nombre_pet = comando.split(" ", 1)[1] if " " in comando else ""
                if not nombre_pet:
                    await message.channel.send("¿Qué mascota? Ej: `meta info cod mascota frost dragon`")
                    return
                msg_busqueda = await message.channel.send(f"🔍 Buscando info de la mascota **{nombre_pet}**...")
                query = f"Call of Dragons {nombre_pet} pet war pet skills guide"
                resultados = buscar_google(query)
                if not resultados:
                    await msg_busqueda.edit(content=f"No encontré info de **{nombre_pet}**")
                    return
                embed = discord.Embed(title=f"🐾 Mascota: {nombre_pet.title()}", color=0x2ecc71)
                desc = ""
                for r in resultados[:3]:
                    desc += f"**{r.get('title', '')[:60]}**\n{r.get('snippet', '')[:120]}...\n[Info]({r.get('link', '')})\n\n"
                embed.description = desc
                await msg_busqueda.edit(content=None, embed=embed)
                return

            elif comando.startswith("top") or comando.startswith("rankings"):
                msg_busqueda = await message.channel.send("🔍 Buscando rankings actuales de CoD...")
                query = "Call of Dragons top kingdoms players power rankings 2026"
                resultados = buscar_google(query)
                embed = discord.Embed(title="🏆 Top Rankings Call of Dragons", color=0xf1c40f)
                desc = ""
                for r in resultados[:4]:
                    desc += f"**{r.get('title', '')[:60]}**\n{r.get('snippet', '')[:100]}...\n[Ver]({r.get('link', '')})\n\n"
                embed.description = desc if desc else "No hay rankings públicos actualizados"
                await msg_busqueda.edit(content=None, embed=embed)
                return

            else:
                ayuda = """
**Comandos Call of Dragons:**
`meta info cod reino 1234` - Info de un reino
`meta info cod heroe liliya` - Build/talentos de héroe 
`meta info cod mascota bear` - Skills de mascota
`meta info cod top` - Rankings actuales

**Comandos de Anuncios:**
`meta crear anuncio texto` - Anuncio ES/EN aquí con @everyone
`meta anunciar #canal texto` - Manda anuncio a otro canal con @everyone

**Otros:**
`!traducir en texto` - Traductor directo
`!ping` - Ver si estoy vivo
                """
                await message.channel.send(ayuda)
                return

    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
