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
