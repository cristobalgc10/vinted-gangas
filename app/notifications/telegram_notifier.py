"""
Telegram Notifier - Envío de notificaciones a Telegram

Características:
- Mensajes con formato rich (HTML/Markdown)
- Imágenes de productos
- Botones para ver en Vinted
- Rate limiting automático
"""

import aiohttp
import asyncio
from typing import Optional
from app.models import Product


class TelegramNotifier:
    """
    Notificador para Telegram.
    Envía mensajes bonitos con imagen y botones.
    """
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Inicializa el notificador de Telegram.
        
        Args:
            bot_token: Token del bot de Telegram
            chat_id: ID del chat donde enviar mensajes
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def _format_product_message(self, product: Product) -> str:
        """
        Formatea el mensaje del producto para Telegram (HTML).
        
        Args:
            product: Producto a formatear
        
        Returns:
            str: Mensaje formateado en HTML
        """
        # Título con emoji
        message = f"🆕 <b>{product.title}</b>\n\n"
        
        # Precio destacado
        message += f"💰 <b>{product.price}€</b>\n"
        
        # Información del producto
        if product.brand:
            message += f"🏷 Marca: {product.brand}\n"
        
        if product.size:
            message += f"📏 Talla: {product.size}\n"
        
        if product.condition:
            message += f"✨ Estado: {product.condition}\n"
        
        message += "\n"
        
        # Información del vendedor
        if product.seller_name:
            message += f"👤 <b>Vendedor:</b> {product.seller_name}\n"
        
        if product.seller_country:
            flag = self._get_country_flag(product.seller_country)
            message += f"{flag} País: {product.seller_country}\n"
        
        # Reputación del vendedor (si existe)
        if product.seller:
            rep = getattr(product.seller, 'feedback_reputation', None)
            count = getattr(product.seller, 'feedback_count', 0)
            
            if rep is not None and count > 0:
                rep_percent = int(rep * 100)
                emoji = "⭐" if rep >= 0.9 else "🌟" if rep >= 0.7 else "⚡"
                message += f"{emoji} Reputación: {rep_percent}% ({count} valoraciones)\n"
        
        message += "\n"
        
        # Búsqueda que encontró el producto
        if product.search:
            message += f"🔍 Búsqueda: <i>{product.search.name}</i>\n"
        
        return message
    
    def _get_country_flag(self, country_code: str) -> str:
        """
        Obtiene el emoji de bandera para un código de país.
        
        Args:
            country_code: Código ISO del país (ES, FR, etc.)
        
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
        Envía notificación de un producto a Telegram.
        
        Args:
            product: Producto a notificar
        
        Returns:
            bool: True si se envió correctamente
        """
        try:
            message_text = self._format_product_message(product)
            
            # Botón inline para ver en Vinted
            keyboard = {
                "inline_keyboard": [[
                    {
                        "text": "🔗 Ver en Vinted",
                        "url": product.url
                    }
                ]]
            }
            
            async with aiohttp.ClientSession() as session:
                # Si hay imagen, enviar foto con caption
                if product.image_url:
                    url = f"{self.base_url}/sendPhoto"
                    
                    data = {
                        'chat_id': self.chat_id,
                        'photo': product.image_url,
                        'caption': message_text,
                        'parse_mode': 'HTML',
                        'reply_markup': keyboard
                    }
                    
                    async with session.post(url, json=data) as response:
                        result = await response.json()
                        
                        if not result.get('ok'):
                            print(f"[TELEGRAM] Error: {result.get('description')}")
                            return False
                        
                        return True
                
                # Sin imagen, enviar solo mensaje
                else:
                    url = f"{self.base_url}/sendMessage"
                    
                    data = {
                        'chat_id': self.chat_id,
                        'text': message_text,
                        'parse_mode': 'HTML',
                        'reply_markup': keyboard
                    }
                    
                    async with session.post(url, json=data) as response:
                        result = await response.json()
                        
                        if not result.get('ok'):
                            print(f"[TELEGRAM] Error: {result.get('description')}")
                            return False
                        
                        return True
        
        except Exception as e:
            print(f"[TELEGRAM] Exception: {e}")
            return False
    
    async def send_test_message(self) -> bool:
        """
        Envía un mensaje de prueba.
        
        Returns:
            bool: True si se envió correctamente
        """
        try:
            message = "🧪 <b>Test de Notificaciones</b>\n\n"
            message += "✅ Bot de Telegram configurado correctamente\n"
            message += "📨 Recibirás notificaciones de productos nuevos aquí"
            
            url = f"{self.base_url}/sendMessage"
            
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    result = await response.json()
                    
                    if not result.get('ok'):
                        print(f"[TELEGRAM] Error: {result.get('description')}")
                        return False
                    
                    return True
        
        except Exception as e:
            print(f"[TELEGRAM] Exception: {e}")
            return False
