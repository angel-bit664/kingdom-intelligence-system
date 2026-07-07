import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
import requests
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

def buscar_google(query):
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    data = {"q": query, "num": 3}
    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        if response.status_code == 200:
            return response.json().get("organic", [])
        return []
    except:
        return []

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
        
    msg_lower = message.content.lower()
    
    # COMANDOS CON "meta" SIN !
    if msg_lower.startswith("meta "):
        peticion = message.content[5:].strip()
        
        if peticion.lower().startswith("crear anuncio"):
            anuncio = peticion[14:].strip()
            if not anuncio:
                await message.channel.send("¿Cuál es el anuncio?")
                return
            try:
                anuncio_en = GoogleTranslator(source='es', target='en').translate(anuncio)
            except:
                anuncio_en = "Translation failed"
            embed = discord.Embed(title="📢 ANUNCIO IMPORTANTE", color=discord.Color.red())
            embed.add_field(name="🇲🇽 Español", value=anuncio, inline=False)
            embed.add_field(name="🇺🇸 English", value=anuncio_en, inline=False)
            await message.channel.send(content="@everyone", embed=embed)
            return
            
        elif peticion.lower().startswith("buscame informacion"):
            tema = peticion[20:].strip()
            if not tema:
                await message.channel.send("¿De qué quieres info?")
                return
            msg_busqueda = await message.channel.send(f"🔍 Buscando **{tema}**...")
            resultados = buscar_google(tema)
            if not resultados:
                await msg_busqueda.edit(content=f"No encontré nada de **{tema}**")
                return
            embed = discord.Embed(title=f"📚 Resultados: {tema}", color=discord.Color.blue())
            desc = ""
            for i, r in enumerate(resultados[:3], 1):
                desc += f"**{i}. {r.get('title', '')[:60]}**\n{r.get('snippet', '')[:100]}...\n[Link]({r.get('link', '')})\n\n"
            embed.description = desc
            await msg_busqueda.edit(content=None, embed=embed)
            return
    
    # Si no es "meta", procesa comandos normales con !
    await bot.process_commands(message)

@bot.command()
async def ping(ctx):
    await ctx.send('Pong! 📬 Bot activo')

bot.run(os.getenv("DISCORD_TOKEN"))
