import discord
from discord.ext import commands
import os
from groq import Groq
import asyncio

# --- CONFIGURACIÓN ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Intents necesarios
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='meta ', intents=intents)

# Cliente de Groq
groq_client = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        print("🔑 Groq API: Activa")
    except Exception as e:
        print(f"❌ Error al inicializar Groq: {e}")
        groq_client = None
else:
    print("⚠️ GROQ_API_KEY no encontrada. Auto-traducción desactivada.")

# Canales con auto-traducción activa
auto_translate_channels = set()

# --- EVENTOS ---
@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    print(f"📊 Conectado a {len(bot.guilds)} servidores")
    await bot.change_presence(activity=discord.Game(name="Kingdom Intelligence"))

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Auto-traducción EN↔ES
    if message.channel.id in auto_translate_channels:
        # Ignora comandos y mensajes muy cortos
        if message.content.startswith('meta') or len(message.content) < 4:
            await bot.process_commands(message)
            return

        if groq_client:
            try:
                # 1. Detectar idioma
                detection = groq_client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": "Detecta si el texto está en inglés o español. Responde SOLO con 'EN' si es inglés, 'ES' si es español, o 'OTHER' si es otro idioma."
                        },
                        {"role": "user", "content": message.content}
                    ],
                    model="llama-3.1-8b-instant",
                    temperature=0,
                    max_tokens=5
                )

                lang = detection.choices[0].message.content.strip().upper()
                translation = None
                flag = ""
                idioma = ""

                # 2. Traducir según el idioma detectado
                if lang == "EN":
                    # Inglés → Español
                    result = groq_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "Traduce el siguiente texto de inglés a español. Responde SOLO con la traducción, sin explicaciones ni comillas."},
                            {"role": "user", "content": message.content}
                        ],
                        model="llama-3.1-8b-instant",
                        temperature=0.3,
                        max_tokens=200
                    )
                    translation = result.choices[0].message.content.strip()
                    flag = "🇲🇽"
                    idioma = "Español"

                elif lang == "ES":
                    # Español → Inglés
                    result = groq_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "Translate the following text from Spanish to English. Respond ONLY with the translation, no explanations or quotes."},
                            {"role": "user", "content": message.content}
                        ],
                        model="llama-3.1-8b-instant",
                        temperature=0.3,
                        max_tokens=200
                    )
                    translation = result.choices[0].message.content.strip()
                    flag = "🇺🇸"
                    idioma = "English"

                # 3. Enviar embed si hubo traducción
                if translation:
                    embed = discord.Embed(
                        title="Traducción automática:",
                        description=f"{flag} **{idioma}**\n\n{translation}",
                        color=0x00B0F4
                    )
                    embed.set_footer(text=f"Detectado: {lang}")
                    await message.reply(embed=embed, mention_author=False)

            except Exception as e:
                print(f"[GROQ] ERROR: {e}")

    await bot.process_commands(message)

# --- COMANDOS ---
@bot.command(name='ping')
async def ping(ctx):
    await ctx.send(f'🏓 Pong! {round(bot.latency * 1000)}ms')

@bot.command(name='activate')
async def activate(ctx):
    embed = discord.Embed(
        title="🏰 Kingdom Intelligence Activado",
        description="Sistema listo para operar.",
        color=0x00FF00
    )
    await ctx.send(embed=embed)

@bot.command(name='evento')
@commands.cooldown(1, 300, commands.BucketType.guild)
async def evento(ctx):
    embed = discord.Embed(
        title="⚔️ Evento de Kingdom",
        description="¡El evento ha comenzado! Prepara tus tropas.",
        color=0xFF9900
    )
    await ctx.send(embed=embed)

@evento.error
async def evento_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏰ Espera {error.retry_after:.0f}s para usar este comando otra vez.")

@bot.command(name='autotraducir')
async def autotraducir(ctx, estado: str = None):
    if estado == "on":
        auto_translate_channels.add(ctx.channel.id)
        embed = discord.Embed(
            title="✅ Auto-traducción activada",
            description="Traduciré mensajes EN↔ES en este canal automáticamente.",
            color=0x00FF00
        )
        await ctx.send(embed=embed)
    elif estado == "off":
        auto_translate_channels.discard(ctx.channel.id)
        embed = discord.Embed(
            title="❌ Auto-traducción desactivada",
            description="Ya no traduciré mensajes en este canal.",
            color=0xFF0000
        )
        await ctx.send(embed=embed)
    else:
        status = "activada" if ctx.channel.id in auto_translate_channels else "desactivada"
        await ctx.send(f"Auto-traducción: **{status}**\nUsa `meta autotraducir on/off`")

# --- INICIAR BOT ---
if __name__ == "__main__":
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("❌ DISCORD_TOKEN no encontrado en variables de entorno")
