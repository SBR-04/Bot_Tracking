import requests
from bs4 import BeautifulSoup
from log_config import logger
import random

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/118.0",
]

def extraer_precio(url):
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept-Language': 'es-ES,es;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.google.com/'
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            logger.warning(f"[{url}] Error HTTP {r.status_code}")
            return None

        soup = BeautifulSoup(r.content, 'html.parser')

        if "amazon" in url:
            span = soup.select_one('span.a-price span.a-offscreen')
            if span:
                precio = float(span.text.replace('€', '').replace('.', '').replace(',', '.'))
                logger.info(f"[{url}] Precio encontrado: {precio}€")
                return precio
            else:
                if "captcha" in r.text.lower() or "robot" in r.text.lower():
                    logger.warning(f"[{url}] Amazon probablemente bloqueó la petición (captcha o bot detectado)")
                else:
                    logger.warning(f"[{url}] No se encontró el span de precio en Amazon")
        elif "coolmod" in url:
            span = soup.select_one('div.precio-main span')
            if span:
                precio = float(span.text.replace('€', '').replace('.', '').replace(',', '.'))
                logger.info(f"[{url}] Precio encontrado: {precio}€")
                return precio
            else:
                logger.warning(f"[{url}] No se encontró el span de precio en Coolmod")

    except Exception as e:
        logger.exception(f"[{url}] Excepción al intentar obtener el precio: {e}")

    return None

def extraer_imagen(url):
    try:
        r = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept-Language': 'es-ES,es;q=0.9'
        }, timeout=10)
        if r.status_code != 200:
            logger.warning(f"[{url}] Error HTTP al obtener imagen: {r.status_code}")
            return None

        soup = BeautifulSoup(r.content, 'html.parser')
        if "amazon" in url:
            img_tag = soup.select_one("#imgTagWrapperId img")
            if img_tag and img_tag.has_attr("src"):
                return img_tag["src"]
    except Exception as e:
        logger.exception(f"[{url}] Excepción al obtener la imagen: {e}")
    return None
