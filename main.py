import discord
import os
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    print('Kingdom Intelligence System Online')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong! 🏰 Bot activo')

@bot.command()
async def hola(ctx):
    await ctx.send(f'Qué onda {ctx.author.mention}, soy el bot de Kingdom Intelligence')

bot.run(os.getenv('DISCORD_TOKEN'))


import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong! 📬 Bot activo')

# COMANDO: meta crear anuncio [mensaje]
@bot.command()
async def meta(ctx, *, mensaje=None):
    if mensaje is None:
        await ctx.send("Usa: `!meta crear anuncio tu mensaje aqui`")
        return
    
    # Si el mensaje empieza con "crear anuncio"
    if mensaje.lower().startswith("crear anuncio"):
        anuncio = mensaje[14:].strip() # Quita "crear anuncio"
        
        if not anuncio:
            await ctx.send("¿Cuál es el anuncio bro? Ejemplo: `!meta crear anuncio vamos a peliar en zona 1 todos activos`")
            return
            
        # Traduce a inglés
        try:
            anuncio_en = GoogleTranslator(source='es', target='en').translate(anuncio)
        except:
            anuncio_en = "Translation failed"
            
        # Crea el embed chido
        embed = discord.Embed(
            title="📢 ANUNCIO IMPORTANTE",
            color=discord.Color.red()
        )
        embed.add_field(name="🇲🇽 Español", value=anuncio, inline=False)
        embed.add_field(name="🇺🇸 English", value=anuncio_en, inline=False)
        embed.set_footer(text=f"Anuncio creado por {ctx.author.display_name}")
        
        # Manda ping a @everyone
        await ctx.send(content="@everyone", embed=embed)
        
    else:
        await ctx.send("Comando no reconocido. Usa: `!meta crear anuncio tu mensaje`")

# TRADUCTOR AUTOMÁTICO: Detecta idioma y traduce
@bot.event
async def on_message(message):
    # Ignora mensajes del bot
    if message.author == bot.user:
        return
        
    # Ignora comandos
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return
    
    # Solo traduce en canales de texto, no DMs
    if not isinstance(message.channel, discord.TextChannel):
        await bot.process_commands(message)
        return
        
    # Detecta si es español o inglés y traduce
    try:
        # Intenta detectar español
        detectado = GoogleTranslator(source='auto', target='en').translate(message.content)
        
        # Si el texto original es diferente al traducido, probablemente era español
        if detectado.lower()!= message.content.lower() and len(message.content) > 3:
            # Es español, traduce a inglés
            trad = detectado
            await message.reply(f"🇺🇸 **Auto-Translate:** {trad}", mention_author=False)
            
    except:
        pass # Si falla la traducción, no hace nada
        
    await bot.process_commands(message)

bot.run('TU_TOKEN') # Railway lo agarra de las Variables
