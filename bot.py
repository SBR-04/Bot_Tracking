import discord
from discord import app_commands
from discord.ext import tasks
import asyncio
import json
import random
from datetime import datetime
from typing import List
from scraper import extraer_precio, extraer_imagen
from config import TOKEN, GUILD_ID, CANAL_ALERTAS_ID
from log_config import logger

TIEMPO_ESPERA = 300  # Tiempo total del ciclo (5 minutos)
#ROL_ALERTA_ID = 

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Diccionario en memoria de búsquedas activas
busquedas = {}
productos_reportados = set()
countdown_message = None
mensajes_activos = {}

try:
    with open("busquedas.json", "r", encoding="utf-8") as f:
        busquedas = json.load(f)
except FileNotFoundError:
    busquedas = {}

def generar_embed(nombre, url, tienda, precio, variacion, imagen_url=None):
    emojis = {
        "subida": "📈",
        "bajada": "📉",
        "igual": "➖"
    }

    embed = discord.Embed(
        title=nombre,
        url=url,
        color=discord.Color.green() if variacion == "bajada" else (
            discord.Color.red() if variacion == "subida" else discord.Color.gold())
    )

    embed.set_author(name=tienda)
    embed.add_field(name="💶 Precio", value=f"{precio:.2f}€", inline=True)
    embed.add_field(name="🔁 Estado", value=emojis[variacion], inline=True)
    embed.add_field(name="🕒 Fecha", value=datetime.now().strftime("%d/%m/%Y %H:%M"), inline=True)
    embed.add_field(name="🔗 Enlace de Compra", value=f"[Click aquí]({url})", inline=False)
    if imagen_url:
        embed.set_thumbnail(url=imagen_url)
    return embed

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    logger.info(f"Bot conectado como {bot.user}")
    if not monitor.is_running():
        logger.info("Intentando iniciar el monitor...")
        monitor.start()
        logger.info("Monitor iniciado.")

@tree.command(name="nbusqueda", description="Añadir una nueva búsqueda", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(nombre="Nombre del producto", url="URL del producto (Amazon, Coolmod...)")
async def nuevabusqueda(interaction: discord.Interaction, nombre: str, url: str):
    busquedas[nombre] = {"url": url, "precio": None}
    with open("busquedas.json", "w", encoding="utf-8") as f:
        json.dump(busquedas, f, indent=2, ensure_ascii=False)
    await interaction.response.send_message(f"🔎 Añadida nueva búsqueda: **{nombre}**\nURL: {url}", ephemeral=True)

@tree.command(name="bbusqueda", description="Eliminar una búsqueda", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(nombre="Nombre del producto a borrar")
async def bbusqueda(interaction: discord.Interaction, nombre: str):
    if nombre in busquedas:
        del busquedas[nombre]
        with open("busquedas.json", "w", encoding="utf-8") as f:
            json.dump(busquedas, f, indent=2, ensure_ascii=False)
        await interaction.response.send_message(f"🗑️ Borrada búsqueda: **{nombre}**", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Esa búsqueda no existe.", ephemeral=True)

@bbusqueda.autocomplete("nombre")
async def bbusqueda_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    return [app_commands.Choice(name=nombre, value=nombre) for nombre in busquedas if current.lower() in nombre.lower()]

@tasks.loop(seconds=TIEMPO_ESPERA)
async def monitor():
    global countdown_message
    logger.info("⏱️ monitor(): ejecutando comprobación de precios...")
    canal = bot.get_channel(CANAL_ALERTAS_ID)
    if canal is None:
        logger.error("❌ No se pudo obtener el canal de alertas. Verifica CANAL_ALERTAS_ID.")
        return

    if countdown_message:
        try:
            await countdown_message.delete()
        except:
            pass

    delay_por_producto = max(60, TIEMPO_ESPERA // max(len(busquedas), 1))

    for nombre, datos in list(busquedas.items()):
        url = datos["url"]
        await asyncio.sleep(random.randint(5, 10))
        nuevo_precio = extraer_precio(url)
        imagen_url = extraer_imagen(url)

        if nuevo_precio is None:
            logger.warning(f"[{url}] No se pudo obtener el precio. HTML posiblemente modificado o bloqueado.")
            continue

        if "amazon" in url:
            tienda = "Amazon"
        elif "coolmod" in url:
            tienda = "Coolmod"
        else:
            tienda = "Tienda desconocida"

        try:
            precio_guardado = float(datos.get("precio")) if datos.get("precio") is not None else None
        except (ValueError, TypeError):
            precio_guardado = None

        variacion = "igual"
        if precio_guardado is None:
            busquedas[nombre]["precio"] = nuevo_precio
        elif nuevo_precio < precio_guardado:
            variacion = "bajada"
            busquedas[nombre]["precio"] = nuevo_precio
        elif nuevo_precio > precio_guardado:
            variacion = "subida"
            busquedas[nombre]["precio"] = nuevo_precio
        else:
            busquedas[nombre]["precio"] = nuevo_precio

        embed = generar_embed(nombre, url, tienda, nuevo_precio, variacion, imagen_url)
        content = f"<@&{ROL_ALERTA_ID}> 💸 {nuevo_precio:.2f}€ | {tienda} | {nombre}" if variacion == "bajada" else f"💸 {nuevo_precio:.2f}€ | {tienda} | {nombre}"

        if nombre in mensajes_activos:
            try:
                mensaje_antiguo = await canal.fetch_message(mensajes_activos[nombre])
                await mensaje_antiguo.edit(content=content, embed=embed)
            except Exception as e:
                logger.warning(f"No se pudo editar el mensaje anterior de {nombre}: {e}")
                msg = await canal.send(content=content, embed=embed)
                mensajes_activos[nombre] = msg.id
        else:
            msg = await canal.send(content=content, embed=embed)
            mensajes_activos[nombre] = msg.id

        await asyncio.sleep(delay_por_producto)

    with open("busquedas.json", "w", encoding="utf-8") as f:
        json.dump(busquedas, f, indent=2, ensure_ascii=False)

    countdown_message = await canal.send("⏳ Próxima comprobación en 5 minutos...")
    for i in range(TIEMPO_ESPERA, 0, -60):
        try:
            await countdown_message.edit(content=f"⏳ Próxima comprobación en {i//60} minutos...")
            await asyncio.sleep(60)
        except:
            break

bot.run(TOKEN)
