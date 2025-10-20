"""
Notification Manager - Sistema de notificaciones multi-canal

Soporta:
- Telegram (mensajes con imagen y botones)
- Discord (embeds con imagen)
- Webhook genérico (HTTP POST con JSON)
- Push notifications del navegador (futuro)
"""

import asyncio
from typing import Optional, List, Dict
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Settings, Product, Notification, Search, Seller
from app.database import SessionLocal


class NotificationManager:
    """
    Gestor principal de notificaciones.
    Lee configuración desde Settings y envía notificaciones según canales activos.
    """
    
    def __init__(self, db: Optional[Session] = None):
        """
        Inicializa el gestor de notificaciones.
        
        Args:
            db: Sesión de BD (opcional, se crea una si no se pasa)
        """
        self.db = db or SessionLocal()
        self._own_db = db is None
        
        # Cache de configuración
        self._settings: Optional[Settings] = None
        
        # Notificadores por canal
        self._telegram = None
        self._discord = None
        self._webhook = None
        
        # Cargar configuración inicial
        self._load_config()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._own_db:
            self.db.close()
    
    def _load_config(self):
        """Carga la configuración desde Settings."""
        self._settings = self.db.query(Settings).filter(Settings.id == 1).first()
        
        if not self._settings:
            return
        
        # Inicializar notificadores según configuración
        self._init_notifiers()
    
    def _init_notifiers(self):
        """Inicializa los notificadores activos."""
        # Importar solo cuando sea necesario
        from app.notifications.telegram_notifier import TelegramNotifier
        from app.notifications.discord_notifier import DiscordNotifier
        from app.notifications.webhook_notifier import WebhookNotifier
        
        # Telegram
        telegram_token = getattr(self._settings, 'telegram_bot_token', None)
        telegram_chat = getattr(self._settings, 'telegram_chat_id', None)
        
        if telegram_token and telegram_chat:
            self._telegram = TelegramNotifier(
                bot_token=telegram_token,
                chat_id=telegram_chat
            )
        
        # Discord
        discord_webhook = getattr(self._settings, 'discord_webhook_url', None)
        
        if discord_webhook:
            self._discord = DiscordNotifier(webhook_url=discord_webhook)
        
        # Webhook genérico
        webhook_url = getattr(self._settings, 'webhook_url', None)
        
        if webhook_url:
            self._webhook = WebhookNotifier(webhook_url=webhook_url)
    
    def reload(self):
        """Recarga la configuración desde la base de datos."""
        self.db.expire_all()
        self._load_config()
    
    async def notify_product(self, product: Product) -> Dict[str, bool]:
        """
        Envía notificación de un producto a todos los canales activos.
        
        Args:
            product: Producto a notificar
        
        Returns:
            dict: Resultado por canal {'telegram': True, 'discord': False, ...}
        """
        results = {}
        
        # Cargar relaciones necesarias
        if not product.search:
            product.search = self.db.query(Search).filter(Search.id == product.search_id).first()
        
        if not product.seller and product.seller_id:
            product.seller = self.db.query(Seller).filter(Seller.id == product.seller_id).first()
        
        # Enviar a Telegram
        if self._telegram:
            try:
                success = await self._telegram.send_product_notification(product)
                results['telegram'] = success
                
                # Registrar notificación
                self._log_notification(product.id, 'telegram', 'sent' if success else 'failed')
                
            except Exception as e:
                results['telegram'] = False
                self._log_notification(product.id, 'telegram', 'failed', str(e))
        
        # Enviar a Discord
        if self._discord:
            try:
                success = await self._discord.send_product_notification(product)
                results['discord'] = success
                
                # Registrar notificación
                self._log_notification(product.id, 'discord', 'sent' if success else 'failed')
                
            except Exception as e:
                results['discord'] = False
                self._log_notification(product.id, 'discord', 'failed', str(e))
        
        # Enviar a Webhook
        if self._webhook:
            try:
                success = await self._webhook.send_product_notification(product)
                results['webhook'] = success
                
                # Registrar notificación
                self._log_notification(product.id, 'webhook', 'sent' if success else 'failed')
                
            except Exception as e:
                results['webhook'] = False
                self._log_notification(product.id, 'webhook', 'failed', str(e))
        
        # Marcar producto como notificado si al menos un canal tuvo éxito
        if any(results.values()):
            product.is_notified = True
            product.notified_at = datetime.utcnow()
            self.db.commit()
        
        return results
    
    async def notify_products(self, products: List[Product]) -> Dict:
        """
        Envía notificaciones de múltiples productos.
        
        Args:
            products: Lista de productos a notificar
        
        Returns:
            dict: Estadísticas de envío
        """
        total = len(products)
        success = 0
        failed = 0
        
        for product in products:
            results = await self.notify_product(product)
            
            if any(results.values()):
                success += 1
            else:
                failed += 1
        
        return {
            'total': total,
            'success': success,
            'failed': failed
        }
    
    def _log_notification(self, product_id: int, channel: str, status: str, error: Optional[str] = None):
        """
        Registra una notificación en la BD.
        
        Args:
            product_id: ID del producto
            channel: Canal usado
            status: Estado (sent, failed)
            error: Mensaje de error (opcional)
        """
        notification = Notification(
            product_id=product_id,
            channel=channel,
            status=status,
            error_message=error
        )
        
        self.db.add(notification)
        self.db.commit()
    
    def get_stats(self) -> Dict:
        """
        Obtiene estadísticas de canales activos.
        
        Returns:
            dict: Canales activos y configuración
        """
        return {
            'telegram_active': self._telegram is not None,
            'discord_active': self._discord is not None,
            'webhook_active': self._webhook is not None,
            'any_active': any([self._telegram, self._discord, self._webhook])
        }


# ============================================================================
# FUNCIONES HELPER
# ============================================================================

def get_notification_manager(db: Optional[Session] = None) -> NotificationManager:
    """
    Obtiene una instancia de NotificationManager.
    
    Args:
        db: Sesión de BD (opcional)
    
    Returns:
        NotificationManager instance
    """
    return NotificationManager(db=db)


async def notify_new_products(db: Optional[Session] = None):
    """
    Notifica todos los productos nuevos (is_notified=False).
    
    Args:
        db: Sesión de BD (opcional)
    
    Returns:
        dict: Estadísticas de notificaciones enviadas
    """
    db = db or SessionLocal()
    
    try:
        # Obtener productos no notificados
        products = db.query(Product).filter(
            Product.is_notified == False,
            Product.is_available == True
        ).all()
        
        if not products:
            return {'total': 0, 'success': 0, 'failed': 0}
        
        # Enviar notificaciones
        async with NotificationManager(db=db) as nm:
            results = await nm.notify_products(products)
        
        return results
        
    finally:
        if db:
            db.close()


def test_notifications():
    """Función de testing para verificar configuración de notificaciones."""
    print("=" * 60)
    print("📨 TEST DE NOTIFICACIONES")
    print("=" * 60)
    print()
    
    with NotificationManager() as nm:
        stats = nm.get_stats()
        
        print("📊 CANALES ACTIVOS:")
        print(f"   • Telegram: {'✅ Configurado' if stats['telegram_active'] else '❌ No configurado'}")
        print(f"   • Discord: {'✅ Configurado' if stats['discord_active'] else '❌ No configurado'}")
        print(f"   • Webhook: {'✅ Configurado' if stats['webhook_active'] else '❌ No configurado'}")
        print()
        
        if not stats['any_active']:
            print("⚠️  NO HAY CANALES CONFIGURADOS")
            print()
            print("Para configurar notificaciones:")
            print("   1. Ve a http://localhost:8000/settings")
            print("   2. Pestaña 'Notificaciones'")
            print("   3. Configura al menos un canal")
            print()
        else:
            print("✅ Sistema de notificaciones listo")
            print()
        
        # Ver productos pendientes de notificación
        pending = nm.db.query(Product).filter(
            Product.is_notified == False,
            Product.is_available == True
        ).count()
        
        print(f"📦 PRODUCTOS PENDIENTES: {pending}")
        print()
        
        if pending > 0:
            print("💡 Para enviar notificaciones:")
            print("   python -c \"from app.notifications.notification_manager import notify_new_products; import asyncio; asyncio.run(notify_new_products())\"")
            print()
        
        print("=" * 60)
        print("✅ TEST COMPLETADO")
        print("=" * 60)


if __name__ == "__main__":
    test_notifications()
