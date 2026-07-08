import discord
from discord.ext import commands
import os
import requests
from deep_translator import GoogleTranslator
import pandas as pd
from io import BytesIO
from bs4 import BeautifulSoup
import cloudscraper
import math

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# DATOS DE COD - COSTOS T4 A T5 POR TROPA
T5_COSTOS = {
    "infanteria": {"oro": 10800, "madera": 10800, "piedra": 10800, "mana": 8100, "tiempo_seg": 12960},
    "arqueros": {"oro": 10800, "madera": 10800, "piedra": 8100, "mana": 10800, "tiempo_seg": 12960},
    "caballeria": {"oro": 10800, "madera": 8100, "piedra": 10800, "mana": 10800, "tiempo_seg": 12960},
    "magos": {"oro": 8100, "madera": 10800, "piedra": 10800, "mana": 10800, "tiempo_seg": 12960}
}

# META HEROES TEMPORADA ACTUAL
META_HEROES = {
    "emrys": {"tipo": "Caballería", "mascota": "Oso Terrestre", "artefacto": "Cuerno de Guerra", "rol": "Open Field"},
    "nico": {"tipo": "Infantería", "mascota": "Oso Polar", "artefacto": "Corona Brillante", "rol": "Rally/Guarnición"},
    "theia": {"tipo": "Magos", "mascota": "Fénix", "artefacto": "Vara de Primavera", "rol": "Soporte/Debuff"},
    "garwood": {"tipo": "Infantería", "mascota": "Oso Terrestre", "artefacto": "Escudo de Roca", "rol": "Tanque"},
    "kinna": {"tipo": "Arqueros", "mascota": "Águila Tormenta", "artefacto": "Arco Rúnico", "rol": "Nuke"}
}

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    print('Comandos: meta ping, meta ayuda, meta t5, meta heroes, meta build, meta artefactos')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.lower().startswith("meta "):
        peticion = message.content[5:].strip()

        if peticion.lower() == "ping":
            latencia = round(bot.latency * 1000)
            await message.channel.send(f"🏓 Pong! Latencia: `{latencia}ms` | Bot activo ✅")
            return

        if peticion.lower() == "ayuda":
            embed = discord.Embed(title="🤖 Comandos Meta TFT - Call of Dragons", color=0x3498DB)
            embed.add_field(name="📢 `meta alerta <texto>`", value="Manda alerta oficial con @everyone", inline=False)
            embed.add_field(name="⚔️ `meta t5 <cant> <tipo>`", value="Calcula recursos/aceleradores T4→T5", inline=False)
            embed.add_field(name="👑 `meta heroes`", value="Lista heroes meta actuales", inline=False)
            embed.add_field(name="🛠️ `meta build <héroe>`", value="Build completo de héroe: mascota+artefacto", inline=False)
            embed.add_field(name="💎 `meta artefactos`", value="Top artefactos por tipo de tropa", inline=False)
            embed.add_field(name="📊 `meta codstats <reino>`", value="Excel con stats del reino desde dragonstat", inline=False)
            embed.add_field(name="🔍 `meta <búsqueda>`", value="Busca en Google cualquier cosa", inline=False)
            embed.add_field(name="🌐 `meta traducir <texto>`", value="Traduce ES ↔ EN automático", inline=False)
            embed.set_footer(text="Solo oficiales R4/R5 en este canal")
            await message.channel.send(embed=embed)
            return

        # ===== COMANDO: META T5 CALCULADORA =====
        if peticion.lower().startswith("t5 "):
            try:
                partes = peticion[3:].strip().split()
                if len(partes) < 2:
                    await message.channel.send("Uso: `meta t5 100000 infanteria`\nTipos: infanteria, arqueros, caballeria, magos")
                    return

                cantidad = int(partes[0].replace(',', '').replace('.', ''))
                tipo = partes[1].lower()

                if tipo not in T5_COSTOS:
                    await message.channel.send("Tipo inválido. Usa: infanteria, arqueros, caballeria, magos")
                    return

                c = T5_COSTOS[tipo]

                # Recursos totales
                oro_total = c["oro"] * cantidad
                madera_total = c["madera"] * cantidad
                piedra_total = c["piedra"] * cantidad
                mana_total = c["mana"] * cantidad

                # Tiempo con 0% de velocidad
                tiempo_total_seg = c["tiempo_seg"] * cantidad
                dias = tiempo_total_seg // 86400
                horas = (tiempo_total_seg % 86400) // 3600

                # Aceleradores: 1 acelerador de 1h = 3600 seg
                acel_1h = math.ceil(tiempo_total_seg / 3600)
                acel_8h = math.ceil(tiempo_total_seg / 28800)
                acel_24h = math.ceil(tiempo_total_seg / 86400)

                embed = discord.Embed(title=f"⚔️ Upgrade T4→T5 | {cantidad:,} {tipo}", color=0xE74C3C)
                embed.add_field(name="💰 Recursos necesarios", value=f"**Oro:** {oro_total:,}\n**Madera:** {madera_total:,}\n**Piedra:** {piedra_total:,}\n**Maná:** {mana_total:,}", inline=False)
                embed.add_field(name="⏱️ Tiempo base 0% vel.", value=f"{dias} días {horas} horas", inline=True)
                embed.add_field(name="⚡ Aceleradores necesarios", value=f"**1h:** {acel_1h:,}\n**8h:** {acel_8h:,}\n**24h:** {acel_24h:,}", inline=True)
                embed.set_footer(text="Tip: Con 50% vel. de entrenamiento usas mitad de aceleradores")

                await message.channel.send(embed=embed)
                return

            except Exception as e:
                await message.channel.send(f"Error: {e}. Uso: `meta t5 100000 infanteria`")
                return

        # ===== COMANDO: META HEROES =====
        if peticion.lower() == "heroes":
            embed = discord.Embed(title="👑 Meta Heroes COD - Temporada Actual", color=0x9B59B6)
            for nombre, data in META_HEROES.items():
                embed.add_field(
                    name=f"{nombre.capitalize()} - {data['tipo']}",
                    value=f"**Rol:** {data['rol']}\n**Mascota:** {data['mascota']}\n**Artefacto:** {data['artefacto']}",
                    inline=False
                )
            embed.set_footer(text="Usa: meta build emrys para ver talentos")
            await message.channel.send(embed=embed)
            return

        # ===== COMANDO: META BUILD =====
        if peticion.lower().startswith("build "):
            heroe = peticion[6:].strip().lower()
            if heroe in META_HEROES:
                data = META_HEROES[heroe]
                embed = discord.Embed(title=f"🛠️ Build: {heroe.capitalize()}", color=0x1ABC9C)
                embed.add_field(name="Tipo de Tropa", value=data['tipo'], inline=True)
                embed.add_field(name="Rol Principal", value=data['rol'], inline=True)
                embed.add_field(name="Mascota Recomendada", value=f"🐾 {data['mascota']}", inline=False)
                embed.add_field(name="Artefacto BiS", value=f"💎 {data['artefacto']}", inline=False)
                embed.add_field(name="Talentos", value="Prioriza rama de daño + velocidad de marcha. Busca 'Guía talentos' en cod.guide", inline=False)
                await message.channel.send(embed=embed)
            else:
                await message.channel.send(f"No tengo build de `{heroe}`. Heroes disponibles: {', '.join(META_HEROES.keys())}")
            return

        # ===== COMANDO: META ARTEFACTOS =====
        if peticion.lower() == "artefactos":
            embed = discord.Embed(title="💎 Top Artefactos COD por Tropa", color=0xF39C12)
            embed.add_field(name="🛡️ Infantería", value="1. Corona Brillante\n2. Escudo de Roca\n3. Tomo de Coraje", inline=True)
            embed.add_field(name="🏹 Arqueros", value="1. Arco Rúnico\n2. Cuerno Veloz\n3. Flecha Infernal", inline=True)
            embed.add_field(name="🐎 Caballería", value="1. Cuerno de Guerra\n2. Lanza Tormenta\n3. Estandarte", inline=True)
            embed.add_field(name="🔮 Magos", value="1. Vara de Primavera\n2. Orbe Arcano\n3. Libro Prohibido", inline=True)
            embed.set_footer(text="BiS = Best in Slot. Se consiguen en Eventos de Ruleta o Pase")
            await message.channel.send(embed=embed)
            return

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

        if peticion.lower().startswith("alerta "):
            try:
                texto_alerta = peticion[7:].strip()
                if not texto_alerta:
                    await message.channel.send("Uso: `meta alerta Tu mensaje aquí`")
                    return
                embed = discord.Embed(color=0xF1C40F)
                embed.add_field(name="👑 Familia TFT / TFT Family 👑", value="📢 Necesitamos el apoyo de todos / We need everyone's support.", inline=False)
                embed.add_field(name="🎯 Misión / Mission:", value=f"🇲🇽 {texto_alerta}", inline=False)
                embed.add_field(name="🔥 Todos están invitados / Everyone is invited.", value="Si quieren pelear y defender / If you want to fight and defend, los esperamos / we are waiting for you.", inline=False)
                embed.add_field(name="¡Vamos TFT / Let's go TFT! ¡Aún queda guerra por delante / War is still ahead! 👑", value="⚔️", inline=False)
                embed.set_footer(text=f"Alerta enviada por: {message.author.display_name}")
                await message.channel.send("@everyone", embed=embed)
                return
            except Exception as e:
                await message.channel.send("Hubo un error al procesar la alerta.")
                return

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
