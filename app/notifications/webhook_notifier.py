"""
Webhook Notifier - Envío de notificaciones a webhooks genéricos

Características:
- HTTP POST con JSON
- Payload completo del producto
- Timeout configurable
- Retry logic
"""

import aiohttp
import asyncio
from typing import Optional, Dict
from app.models import Product


class WebhookNotifier:
    """
    Notificador para webhooks genéricos.
    Envía HTTP POST con datos completos del producto en JSON.
    """
    
    def __init__(self, webhook_url: str, timeout: int = 10):
        """
        Inicializa el notificador de webhook.
        
        Args:
            webhook_url: URL del webhook
            timeout: Timeout en segundos para la petición
        """
        self.webhook_url = webhook_url
        self.timeout = timeout
    
    def _format_product_payload(self, product: Product) -> Dict:
        """
        Formatea el producto como payload JSON.
        
        Args:
            product: Producto a formatear
        
        Returns:
            dict: Payload JSON con datos del producto
        """
        payload = {
            "event": "new_product",
            "product": {
                "id": product.id,
                "vinted_id": product.vinted_id,
                "title": product.title,
                "description": product.description,
                "price": product.price,
                "currency": product.currency,
                "brand": product.brand,
                "size": product.size,
                "condition": product.condition,
                "url": product.url,
                "image_url": product.image_url,
                "found_at": product.found_at.isoformat() if product.found_at else None
            },
            "seller": {
                "vinted_id": product.seller_vinted_id,
                "name": product.seller_name,
                "country": product.seller_country
            },
            "search": {}
        }
        
        # Añadir datos del vendedor completos si existe
        if product.seller:
            payload["seller"].update({
                "login": product.seller.login,
                "profile_url": product.seller.profile_url,
                "feedback_reputation": float(product.seller.feedback_reputation) if product.seller.feedback_reputation else None,
                "feedback_count": product.seller.feedback_count,
                "positive_feedback": product.seller.positive_feedback_count,
                "item_count": product.seller.item_count,
                "is_business": product.seller.is_business
            })
        
        # Añadir datos de la búsqueda si existe
        if product.search:
            payload["search"] = {
                "id": product.search.id,
                "name": product.search.name,
                "query": product.search.query,
                "price_from": product.search.price_from,
                "price_to": product.search.price_to
            }
        
        return payload
    
    async def send_product_notification(self, product: Product) -> bool:
        """
        Envía notificación de un producto al webhook.
        
        Args:
            product: Producto a notificar
        
        Returns:
            bool: True si se envió correctamente
        """
        try:
            payload = self._format_product_payload(product)
            
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    # Considerar 2xx como éxito
                    if 200 <= response.status < 300:
                        return True
                    else:
                        text = await response.text()
                        print(f"[WEBHOOK] Error {response.status}: {text[:200]}")
                        return False
        
        except asyncio.TimeoutError:
            print(f"[WEBHOOK] Timeout después de {self.timeout}s")
            return False
        
        except Exception as e:
            print(f"[WEBHOOK] Exception: {e}")
            return False
    
    async def send_test_message(self) -> bool:
        """
        Envía un mensaje de prueba.
        
        Returns:
            bool: True si se envió correctamente
        """
        try:
            payload = {
                "event": "test",
                "message": "Webhook configurado correctamente",
                "timestamp": None  # Usar datetime.utcnow().isoformat() si se quiere
            }
            
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if 200 <= response.status < 300:
                        return True
                    else:
                        text = await response.text()
                        print(f"[WEBHOOK] Error {response.status}: {text[:200]}")
                        return False
        
        except Exception as e:
            print(f"[WEBHOOK] Exception: {e}")
            return False
