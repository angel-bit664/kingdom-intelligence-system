import discord
from discord.ext import commands, tasks
import os
import requests
from deep_translator import GoogleTranslator
import pandas as pd
from io import BytesIO
from bs4 import BeautifulSoup
import cloudscraper
from datetime import datetime, timedelta
import re
import urllib.parse
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
ID_CANAL_ANUNCIOS = 1358237524249542751

mensajes_para_borrar = {}

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}')
    print(f'✅ ID: {bot.user.id}')
    print(f'✅ Servidores: {len(bot.guilds)}')
    print('Fuentes: callofstats.com | dragonstats.com | coddb.app | callofdragonsguides.com')
    limpiar_canales.start()

@tasks.loop(hours=1)
async def limpiar_canales():
    try:
        for channel_id, mensajes in list(mensajes_para_borrar.items()):
            canal = bot.get_channel(channel_id)
            if not canal: continue
            hace_una_hora = datetime.utcnow() - timedelta(hours=1)
            mensajes_viejos = [msg for msg in mensajes if msg.created_at < hace_una_hora]
            if mensajes_viejos:
                try:
                    await canal.delete_messages(mensajes_viejos)
                    print(f'Limpiados {len(mensajes_viejos)} mensajes')
                except:
                    for msg in mensajes_viejos:
                        try: await msg.delete()
                        except: pass
                mensajes_para_borrar[channel_id] = [msg for msg in mensajes if msg not in mensajes_viejos]
    except Exception as e:
        print(f'Error en limpieza: {e}')

@limpiar_canales.before_loop
async def before_limpiar():
    await bot.wait_until_ready()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    print(f"[DEBUG] Mensaje recibido: {message.content}") # LOG PARA DEBUG

    if message.content.lower().startswith("meta "):
        print(f"[DEBUG] Comando meta detectado") # LOG PARA DEBUG
        if message.channel.id not in mensajes_para_borrar:
            mensajes_para_borrar[message.channel.id] = []
        mensajes_para_borrar[message.channel.id].append(message)

        peticion = message.content[5:].strip()

        # ===== META PING - PRIMERO PARA TESTEAR =====
        if peticion.lower() == "ping":
            print(f"[DEBUG] Ejecutando ping") # LOG PARA DEBUG
            latencia = round(bot.latency * 1000)
            msg = await message.channel.send(f"🏓 Pong! `{latencia}ms`\n✅ Bot activo")
            mensajes_para_borrar[message.channel.id].append(msg)
            return

        # ===== META LIMPIA =====
        if peticion.lower() == "limpia":
            try:
                msg = await message.channel.send("🧹 Limpiando spam de meta... 10 seg")
                mensajes_para_borrar[message.channel.id].append(msg)
                await asyncio.sleep(2)
                borrados = 0
                async for mensaje in message.channel.history(limit=100):
                    if mensaje.author == bot.user or mensaje.content.lower().startswith("meta "):
                        try:
                            await mensaje.delete()
                            borrados += 1
                            await asyncio.sleep(0.5)
                        except:
                            pass
                mensajes_para_borrar[message.channel.id] = []
                confirmacion = await message.channel.send(f"✅ Limpieza completa: {borrados} mensajes borrados")
                await asyncio.sleep(5)
                await confirmacion.delete()
                return
            except Exception as e:
                msg = await message.channel.send(f"❌ Error limpiando: {e}")
                mensajes_para_borrar[message.channel.id].append(msg)
                return

        # ===== RESTO DE COMANDOS IGUAL QUE ANTES =====
        # ... pega aquí todo el código de meta alerta, evento, traducir, talentos, mascota, codstats, check, calc, etc...
        # Por espacio no lo repito pero usa el del mensaje anterior

        # ===== AYUDA =====
        if peticion.lower() == "ayuda":
            embed = discord.Embed(title="🤖 Comandos Meta TFT", color=0x3498DB)
            embed.add_field(name="🧹 `meta limpia`", value="Borra spam de meta", inline=False)
            embed.add_field(name="🏓 `meta ping`", value="Revisa si el bot está vivo", inline=False)
            embed.add_field(name="📢 `meta alerta <texto>`", value="Alerta oficial bilingüe", inline=False)
            embed.add_field(name="🔍 `meta check id <número>`", value="Stats jugador por ID", inline=False)
            embed.add_field(name="🔍 `meta check reino <número>`", value="Top 50 reino", inline=False)
            msg = await message.channel.send(embed=embed)
            mensajes_para_borrar[message.channel.id].append(msg)
            return

    await bot.process_commands(message)

bot.run(os.getenv("DISCORD_TOKEN"))
