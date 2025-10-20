"""
Discord Notifier - Envío de notificaciones a Discord

Características:
- Embeds bonitos con colores
- Imágenes de productos
- Información estructurada
- Rate limiting automático
"""

import aiohttp
import asyncio
from typing import Optional
from app.models import Product


class DiscordNotifier:
    """
    Notificador para Discord.
    Envía embeds ricos con imagen y información estructurada.
    """
    
    def __init__(self, webhook_url: str):
        """
        Inicializa el notificador de Discord.
        
        Args:
            webhook_url: URL del webhook de Discord
        """
        self.webhook_url = webhook_url
    
    def _format_product_embed(self, product: Product) -> dict:
        """
        Formatea el producto como embed de Discord.
        
        Args:
            product: Producto a formatear
        
        Returns:
            dict: Estructura de embed para Discord
        """
        # Color del embed (verde para productos disponibles)
        color = 0x2ecc71  # Verde
        
        # Título y descripción
        embed = {
            "title": f"🆕 {product.title[:240]}",
            "url": product.url,
            "color": color,
            "timestamp": product.found_at.isoformat() if product.found_at else None,
            "fields": [],
            "footer": {
                "text": "Vinted Scraper"
            }
        }
        
        # Precio (campo destacado)
        embed["fields"].append({
            "name": "💰 Precio",
            "value": f"**{product.price}€**",
            "inline": True
        })
        
        # Marca
        if product.brand:
            embed["fields"].append({
                "name": "🏷 Marca",
                "value": product.brand,
                "inline": True
            })
        
        # Talla
        if product.size:
            embed["fields"].append({
                "name": "📏 Talla",
                "value": product.size,
                "inline": True
            })
        
        # Estado
        if product.condition:
            embed["fields"].append({
                "name": "✨ Estado",
                "value": product.condition,
                "inline": True
            })
        
        # Vendedor
        if product.seller_name:
            seller_info = product.seller_name
            
            if product.seller_country:
                flag = self._get_country_flag(product.seller_country)
                seller_info += f" {flag} {product.seller_country}"
            
            embed["fields"].append({
                "name": "👤 Vendedor",
                "value": seller_info,
                "inline": True
            })
        
        # Reputación del vendedor
        if product.seller:
            rep = getattr(product.seller, 'feedback_reputation', None)
            count = getattr(product.seller, 'feedback_count', 0)
            
            if rep is not None and count > 0:
                rep_percent = int(rep * 100)
                emoji = "⭐" if rep >= 0.9 else "🌟" if rep >= 0.7 else "⚡"
                
                embed["fields"].append({
                    "name": f"{emoji} Reputación",
                    "value": f"{rep_percent}% ({count} valoraciones)",
                    "inline": True
                })
        
        # Búsqueda
        if product.search:
            embed["fields"].append({
                "name": "🔍 Búsqueda",
                "value": product.search.name,
                "inline": False
            })
        
        # Imagen
        if product.image_url:
            embed["image"] = {
                "url": product.image_url
            }
        
        return embed
    
    def _get_country_flag(self, country_code: str) -> str:
        """
        Obtiene el emoji de bandera para un código de país.
        
        Args:
            country_code: Código ISO del país
        
        Returns:
            str: Emoji de bandera
        """
        flags = {
            'ES': '🇪🇸', 'FR': '🇫🇷', 'IT': '🇮🇹', 'DE': '🇩🇪',
            'PT': '🇵🇹', 'UK': '🇬🇧', 'US': '🇺🇸', 'NL': '🇳🇱',
            'BE': '🇧🇪', 'PL': '🇵🇱', 'CZ': '🇨🇿', 'AT': '🇦🇹',
            'SE': '🇸🇪', 'DK': '🇩🇰', 'LT': '🇱🇹'
        }
        return flags.get(country_code, '🌍')
    
    async def send_product_notification(self, product: Product) -> bool:
        """
        Envía notificación de un producto a Discord.
        
        Args:
            product: Producto a notificar
        
        Returns:
            bool: True si se envió correctamente
        """
        try:
            embed = self._format_product_embed(product)
            
            payload = {
                "embeds": [embed]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 204:
                        return True
                    elif response.status == 429:
                        # Rate limit - esperar y reintentar
                        retry_after = int(response.headers.get('Retry-After', 1))
                        print(f"[DISCORD] Rate limited, esperando {retry_after}s")
                        await asyncio.sleep(retry_after)
                        
                        # Reintentar una vez
                        async with session.post(self.webhook_url, json=payload) as retry_response:
                            return retry_response.status == 204
                    else:
                        text = await response.text()
                        print(f"[DISCORD] Error {response.status}: {text}")
                        return False
        
        except Exception as e:
            print(f"[DISCORD] Exception: {e}")
            return False
    
    async def send_test_message(self) -> bool:
        """
        Envía un mensaje de prueba.
        
        Returns:
            bool: True si se envió correctamente
        """
        try:
            embed = {
                "title": "🧪 Test de Notificaciones",
                "description": "✅ Webhook de Discord configurado correctamente\n\n📨 Recibirás notificaciones de productos nuevos aquí",
                "color": 0x3498db,  # Azul
                "footer": {
                    "text": "Vinted Scraper"
                }
            }
            
            payload = {
                "embeds": [embed]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 204:
                        return True
                    else:
                        text = await response.text()
                        print(f"[DISCORD] Error {response.status}: {text}")
                        return False
        
        except Exception as e:
            print(f"[DISCORD] Exception: {e}")
            return False
