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

def buscar_google(query):
    """Busca en Google usando Serper API"""
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    data = {"q": query, "num": 3} # Solo 3 resultados
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        if response.status_code == 200:
            resultados = response.json()
            return resultados.get("organic", [])
        else:
            return []
    except:
        return []

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

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
        
        # META CREAR ANUNCIO
        if peticion.lower().startswith("crear anuncio"):
            anuncio = peticion[14:].strip()
            if not anuncio:
                await message.channel.send("¿Cuál es el anuncio bro?")
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
            
        # META BUSCAME INFORMACION + GOOGLE
        elif peticion.lower().startswith("buscame informacion"):
            tema = peticion[20:].strip()
            if not tema:
                await message.channel.send("¿De qué quieres info? Ej: `meta buscame informacion call of dragons`")
                return
                
            msg_busqueda = await message.channel.send(f"🔍 Buscando info de **{tema}** en Google...")
            
            resultados = buscar_google(tema)
            
            if not resultados:
                await msg_busqueda.edit(content=f"No encontré nada de **{tema}** en Google 😔")
                return
            
            # Arma el embed con los 3 primeros resultados
            embed = discord.Embed(
                title=f"📚 Resultados para: {tema}", 
                color=discord.Color.blue()
            )
            
            descripcion = ""
            for i, r in enumerate(resultados[:3], 1):
                titulo = r.get("title", "Sin título")[:60]
                link = r.get("link", "")
                snippet = r.get("snippet", "Sin descripción")[:100]
                descripcion += f"**{i}. {titulo}**\n{snippet}...\n[Leer más]({link})\n\n"
            
            embed.description = descripcion
            embed.set_footer(text=f"Búsqueda hecha por {message.author.display_name}")
            
            await msg_busqueda.edit(content=None, embed=embed)
            return
    
    # TRADUCTOR AUTOMÁTICO
    if not message.content.startswith('!') and not msg.startswith("meta "):
        try:
            detectado = GoogleTranslator(source='auto', target='en').translate(message.content)
            if detectado.lower()!= message.content.lower() and len(message.content) > 3:
                await message.reply(f"🇺🇸 **Auto-Translate:** {detectado}", mention_author=False)
        except:
            pass
            
    await bot.process_commands(message)

bot.run(os.getenv("DISCORD_TOKEN"))

bot.run('TU_TOKEN') # Railway lo agarra de las Variables
