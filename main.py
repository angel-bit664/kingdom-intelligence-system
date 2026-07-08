import discord
from discord.ext import commands
import os
import requests
from deep_translator import GoogleTranslator
import pandas as pd
from io import BytesIO
from bs4 import BeautifulSoup
import cloudscraper

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
ID_CANAL_ANUNCIOS = 1358237524249542751 # Tu canal ❄️・anuncios🔹announcements┋📣

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    print('Comandos: meta ping, meta ayuda, meta alerta, meta traducir, meta codstats, meta <búsqueda>')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.lower().startswith("meta "):
        peticion = message.content[5:].strip()

        # ===== COMANDO: META PING =====
        if peticion.lower() == "ping":
            latencia = round(bot.latency * 1000)
            await message.channel.send(f"🏓 Pong! Latencia: `{latencia}ms` | Bot activo ✅")
            return

        # ===== COMANDO: META AYUDA =====
        if peticion.lower() == "ayuda":
            embed = discord.Embed(title="🤖 Comandos Meta TFT - Call of Dragons", color=0x3498DB)
            embed.add_field(name="📢 `meta alerta <texto>`", value="Manda alerta oficial bilingüe al canal de anuncios", inline=False)
            embed.add_field(name="📊 `meta codstats <reino>`", value="Excel con stats del reino desde dragonstat", inline=False)
            embed.add_field(name="🔍 `meta <búsqueda>`", value="Busca en Google cualquier cosa", inline=False)
            embed.add_field(name="🌐 `meta traducir <texto>`", value="Traduce ES ↔ EN automático", inline=False)
            embed.add_field(name="🏓 `meta ping`", value="Checa latencia del bot", inline=False)
            embed.set_footer(text="Solo oficiales R4/R5 en este canal")
            await message.channel.send(embed=embed)
            return

        # ===== COMANDO: META ALERTA BILINGÜE A CANAL FIJO =====
        if peticion.lower().startswith("alerta "):
            try:
                texto_alerta_es = peticion[7:].strip()
                if not texto_alerta_es:
                    await message.channel.send("Uso: `meta alerta Nos atacan en el paso 4`")
                    return

                # Busca el canal de anuncios
                canal_anuncios = bot.get_channel(ID_CANAL_ANUNCIOS)
                if not canal_anuncios:
                    await message.channel.send("❌ No encontré el canal de anuncios. Revisa el ID_CANAL_ANUNCIOS")
                    return

                # Traduce a inglés automático
                try:
                    texto_alerta_en = GoogleTranslator(source='es', target='en').translate(texto_alerta_es)
                except:
                    texto_alerta_en = "Translation failed. Check original message above."

                embed = discord.Embed(color=0xF1C40F)
                embed.add_field(name="👑 Familia TFT / TFT Family 👑", value="📢 Necesitamos el apoyo de todos / We need everyone's support.", inline=False)
                embed.add_field(
                    name="🎯 Misión / Mission:",
                    value=f"🇲🇽 **ES:** {texto_alerta_es}\n🇺🇸 **EN:** {texto_alerta_en}",
                    inline=False
                )
                embed.add_field(name="🔥 Todos están invitados / Everyone is invited.", value="Si quieren pelear y defender / If you want to fight and defend, los esperamos / we are waiting for you.", inline=False)
                embed.add_field(name="¡Vamos TFT / Let's go TFT! ¡Aún queda guerra por delante / War is still ahead! 👑", value="⚔️", inline=False)
                embed.set_footer(text=f"Alerta enviada por: {message.author.display_name}")

                # Manda la alerta al canal de anuncios
                await canal_anuncios.send("@everyone", embed=embed)

                # Confirma en el canal donde escribiste el comando
                await message.channel.send(f"✅ Alerta enviada a {canal_anuncios.mention}")
                return

            except Exception as e:
                await message.channel.send(f"Error al procesar la alerta: {e}")
                return

        # ===== COMANDO: META TRADUCIR =====
        if peticion.lower().startswith("traducir "):
            texto = peticion[9:].strip()
            if not texto:
                await message.channel.send("Uso: `meta traducir Hola mundo`")
                return
            try:
                idioma_detectado = GoogleTranslator().detect(texto)
                if idioma_detectado == 'es':
                    traducido = GoogleTranslator(source='es', target='en').translate(texto)
                    await message.channel.send(f"🇲🇽→🇺🇸 **{traducido}**")
                else:
                    traducido = GoogleTranslator(source='auto', target='es').translate(texto)
                    await message.channel.send(f"🇺🇸→🇲🇽 **{traducido}**")
                return
            except Exception as e:
                await message.channel.send(f"Error al traducir: {e}")
                return

        # ===== COMANDO: META CODSTATS =====
        comando_parts = peticion.lower().split()
        if len(comando_parts) >= 2 and comando_parts[0] in ["codstats", "codstat", "stats"]:
            try:
                reino = comando_parts[1].strip()
                if not reino.isdigit():
                    await message.channel.send("Uso: `meta codstats 127`")
                    return

                msg = await message.channel.send(f"📊 Sacando stats del Reino {reino} desde dragonstat.com ~20 seg")
                url = f"https://dragonstat.com/server/{reino}"
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url, timeout=30)

                if response.status_code!= 200:
                    await msg.edit(content=f"❌ Error {response.status_code}: No pude acceder a dragonstat")
                    return

                soup = BeautifulSoup(response.text, 'html.parser')
                tabla = soup.find('table')
                if not tabla:
                    await msg.edit(content=f"❌ No encontré la tabla. El reino {reino} no existe en dragonstat")
                    return

                df = pd.read_html(str(tabla))[0]
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name=f'Reino_{reino}', index=False)
                output.seek(0)
                archivo = discord.File(output, filename=f'COD_Reino_{reino}_Stats.xlsx')
                await msg.delete()
                await message.channel.send(f"✅ **Stats del Reino {reino}** | {len(df)} jugadores", file=archivo)
                return
            except Exception as e:
                await message.channel.send(f"❌ Error: {e}")
                return

        # ===== COMANDO: META BUSQUEDA GOOGLE =====
        await message.channel.send(f"🔍 Buscando: `{peticion}`")
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
                await message.channel.send("No encontré nada bro 🤷")
        except Exception as e:
            await message.channel.send(f"Error: {e}")

    await bot.process_commands(message)

bot.run(os.getenv("DISCORD_TOKEN"))
