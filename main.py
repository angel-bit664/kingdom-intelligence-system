import discord
from discord.ext import commands
import os
import requests
from deep_translator import GoogleTranslator

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.content.lower().startswith("meta "):
        peticion = message.content[5:].strip()
        await message.channel.send(f"Buscando: {peticion}")
        
        url = "https://google.serper.dev/search"
        headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
        payload = {"q": peticion, "gl": "mx", "hl": "es"}
        try:
            response = requests.post(url, headers=headers, json=payload)
            data = response.json()
            if "organic" in data and len(data["organic"]) > 0:
                respuesta = data["organic"][0]["snippet"]
                await message.channel.send(respuesta[:2000])
            else:
                await message.channel.send("No encontré nada bro")
        except Exception as e:
            await message.channel.send(f"Error: {e}")
    
    await bot.process_commands(message)

bot.run(os.getenv("DISCORD_TOKEN"))
