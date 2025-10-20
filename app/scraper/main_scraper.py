"""
Scraper principal de Vinted - VERSIÓN MEJORADA

⭐ Mejoras:
- Guarda métricas detalladas en ScrapingLog (filtros, notificaciones, vendedores)
- Sistema de notificaciones automáticas integrado
- Manejo robusto de errores
- Logs optimizados
"""

import time
import asyncio
from typing import Optional, List
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Search, Product, Seller, ScrapingLog
from app.schemas import ProductCreate, SellerCreate
from app.scraper.vinted_client import VintedRequester
from app.utils.scraper_config import ScraperConfig
from app.utils.filter_manager import FilterManager


class VintedScraper:
    """
    Scraper principal de Vinted con todas las funcionalidades.
    
    - Configuración dinámica desde Settings
    - Filtros globales y personalizados
    - Notificaciones automáticas a Telegram/Discord/Webhook
    - Logs completos de operaciones con métricas detalladas
    """
    
    def __init__(self, db: Optional[Session] = None, config: Optional[ScraperConfig] = None, 
                 filter_manager: Optional[FilterManager] = None):
        """
        Inicializa el scraper.
        
        Args:
            db: Sesión de base de datos (se crea una si no se proporciona)
            config: Configuración del scraper (se crea una si no se proporciona)
            filter_manager: Gestor de filtros (se crea uno si no se proporciona)
        """
        self.db = db or SessionLocal()
        self.config = config or ScraperConfig(db=self.db)
        self.filter_manager = filter_manager or FilterManager(db=self.db)
        self.requester = VintedRequester(config=self.config, debug=False)
        
        # Flag para saber si debemos cerrar la BD
        self._own_db = db is None
    
    def scrape_and_save(self, search: Search) -> dict:
        """
        Ejecuta el scraping completo y guarda los resultados.
        
        Flujo optimizado:
        1. Scrapea productos del catálogo (~600ms)
        2. Aplica filtros globales y personalizados (~5ms)
        3. Scrapea vendedores únicos (~150ms por vendedor)
        4. Guarda productos con seller_id ya disponible
        5. Envía notificaciones automáticas si hay canales configurados
        6. ⭐ Guarda métricas detalladas en ScrapingLog
        
        Args:
            search: Objeto Search con los parámetros de búsqueda
        
        Returns:
            dict: Estadísticas completas del scraping
        """
        start_time = time.time()
        
        # Crear log de ejecución
        log = ScrapingLog(
            search_id=search.id,
            started_at=datetime.utcnow(),
            status="running"
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Iniciando scraping para búsqueda: {search.name}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}]    Query: {search.query}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}]    Precio: {search.price_from}€ - {search.price_to}€")
        
        # Mostrar configuración de scraping
        config_stats = self.config.get_stats()
        print(f"[{datetime.now().strftime('%H:%M:%S')}]    User-Agents: {config_stats['user_agents_count']} ({'rotativo' if config_stats['user_agent_rotation'] else 'fijo'})")
        if config_stats['proxies_enabled']:
            print(f"[{datetime.now().strftime('%H:%M:%S')}]    Proxies: {config_stats['proxies_count']} ({'rotativo' if config_stats['proxy_rotation'] else 'fijo'})")
        
        # Mostrar configuración de filtros
        filter_stats = self.filter_manager.get_stats()
        if filter_stats['filters_active']:
            print(f"[{datetime.now().strftime('%H:%M:%S')}]    Filtros: {filter_stats['global_banned_words_count']} palabras, {filter_stats['global_banned_sellers_count']} vendedores, precio mín {filter_stats['global_min_price']}€")
        
        # PASO 1: SCRAPEAR PRODUCTOS DEL CATÁLOGO
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📦 Scrapeando productos del catálogo...")
        scrape_start = time.time()
        
        try:
            # Si hay query string original, usarla para scraping fiel
            if getattr(search, "vinted_query_string", None):
                products_data = self.requester.scrape_catalog(query_string=search.vinted_query_string)
            else:
                # Preparar parámetros de búsqueda
                scrape_params = {
                    "search_text": search.query or "",
                    "price_from": search.price_from,
                    "price_to": search.price_to,
                    "order": search.order or "newest_first"
                }
                
                # Añadir filtros avanzados si existen
                if getattr(search, "brand_ids", None) is not None:
                    scrape_params["brand_ids"] = search.brand_ids
                if getattr(search, "size_ids", None) is not None:
                    scrape_params["size_ids"] = search.size_ids
                if getattr(search, "color_ids", None) is not None:
                    scrape_params["color_ids"] = search.color_ids
                if getattr(search, "category_ids", None) is not None:
                    scrape_params["category_ids"] = search.category_ids
                if getattr(search, "platform_ids", None) is not None:
                    scrape_params["platform_ids"] = search.platform_ids
                if getattr(search, "material_ids", None) is not None:
                    scrape_params["material_ids"] = search.material_ids
                if getattr(search, "status_ids", None) is not None:
                    scrape_params["status_ids"] = search.status_ids
                
                products_data = self.requester.scrape_catalog(**scrape_params)
            
            # Invertir lista para procesar más recientes primero
            products_data = list(reversed(products_data))
            
            # Aplicar límite de configuración
            max_products = self.config.get_max_products()
            if len(products_data) > max_products:
                print(f"[{datetime.now().strftime('%H:%M:%S')}]    ⚠️  Limitando a {max_products} productos (config)")
                products_data = products_data[:max_products]
            
            scrape_time = int((time.time() - scrape_start) * 1000)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {len(products_data)} productos encontrados en {scrape_time}ms")
            
            # Si no hay productos, terminar aquí
            if not products_data:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  No se encontraron productos")
                self._finish_log(log, "success", 0)
                return self._build_empty_result(start_time)
        
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error scrapeando catálogo: {e}")
            self._finish_log(log, "failed", 0, str(e))
            return self._build_error_result(start_time, str(e))
        
        # PASO 2: APLICAR FILTROS
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚫 Aplicando filtros...")
        filter_start = time.time()
        
        try:
            products_filtered, filter_stats_result = self.filter_manager.filter_products(products_data, search)
            
            filter_time = int((time.time() - filter_start) * 1000)
            products_rejected = filter_stats_result['rejected']
            
            # Mostrar resultados de filtrado
            if products_rejected > 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚫 {products_rejected} productos rechazados por filtros en {filter_time}ms")
                
                # Mostrar top 3 razones de rechazo
                rejection_reasons = filter_stats_result['rejection_reasons']
                for reason, count in sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True)[:3]:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}]    • {reason}: {count} productos")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Todos los productos pasaron filtros ({filter_time}ms)")
            
            # Continuar solo con productos aprobados
            products_data = products_filtered
            
            # Si no quedan productos después de filtrar, terminar
            if not products_data:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Todos los productos fueron filtrados")
                self._finish_log(log, "success", 0, products_filtered=products_rejected)
                return {
                    "products_found": filter_stats_result['total'],
                    "products_new": 0,
                    "products_filtered": products_rejected,
                    "products_notified": 0,
                    "sellers_new": 0,
                    "sellers_updated": 0,
                    "duration_ms": int((time.time() - start_time) * 1000)
                }
        
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error aplicando filtros: {e}")
            # Continuar sin filtrar si hay error
            products_rejected = 0
            filter_stats_result = {'total': len(products_data), 'accepted': len(products_data), 'rejected': 0}
        
        # PASO 3: SCRAPEAR VENDEDORES
        seller_vinted_ids = list(set(p.seller_vinted_id for p in products_data))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 👥 Scrapeando {len(seller_vinted_ids)} vendedores únicos...")
        sellers_start = time.time()
        sellers_new = 0
        sellers_updated = 0
        
        # Configuración: actualizar vendedores antiguos
        UPDATE_SELLER_AFTER_DAYS = 1
        update_threshold = datetime.utcnow() - timedelta(days=UPDATE_SELLER_AFTER_DAYS)
        
        try:
            for seller_vinted_id in seller_vinted_ids:
                try:
                    # Verificar si ya existe
                    existing_seller = self.db.query(Seller).filter(
                        Seller.vinted_id == seller_vinted_id
                    ).first()

                    if existing_seller:
                        # ¿Necesita actualización?
                        last_updated = getattr(existing_seller, "last_updated_at", None)
                        if last_updated and last_updated > update_threshold:
                            continue

                        # Actualizar vendedor existente
                        print(f"[{datetime.now().strftime('%H:%M:%S')}]    🔄 Actualizando vendedor {existing_seller.login}...")
                        seller_data = self.requester.get_seller_info(seller_vinted_id)

                        if not seller_data:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}]    ⚠️  Vendedor no disponible")
                            continue

                        # Actualizar campos
                        for key, value in seller_data.model_dump().items():
                            if key not in ['id', 'first_seen_at']:
                                setattr(existing_seller, key, value)

                        setattr(existing_seller, "last_updated_at", datetime.utcnow())
                        self.db.commit()
                        sellers_updated += 1
                        
                        rep = getattr(existing_seller, "feedback_reputation", 0.0)
                        count = getattr(existing_seller, "feedback_count", 0)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}]    ✅ Actualizado: {existing_seller.login} - {int(rep * 100)}% ({count} valoraciones)")

                    else:
                        # Scrapear vendedor nuevo
                        print(f"[{datetime.now().strftime('%H:%M:%S')}]    📥 Scrapeando vendedor {seller_vinted_id}...")
                        seller_data = self.requester.get_seller_info(seller_vinted_id)

                        if not seller_data:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}]    ⚠️  Vendedor no disponible")
                            continue

                        new_seller = Seller(**seller_data.model_dump())
                        self.db.add(new_seller)
                        self.db.commit()
                        self.db.refresh(new_seller)
                        sellers_new += 1
                        
                        rep = getattr(new_seller, "feedback_reputation", 0.0)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}]    ✅ Guardado: {new_seller.login} ({new_seller.country_code}) - {int(rep * 100)}%")
                
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}]    ❌ Error con vendedor: {e}")
                    self.db.rollback()
                    continue

            sellers_time = int((time.time() - sellers_start) * 1000)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Vendedores procesados ({sellers_new} nuevos, {sellers_updated} actualizados) en {sellers_time}ms")

        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error procesando vendedores: {e}")
            self.db.rollback()
        
        # PASO 4: GUARDAR PRODUCTOS
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 💾 Guardando productos...")
        save_start = time.time()
        products_new = 0
        new_products_for_notification: List[Product] = []

        try:
            for product_data in products_data:
                # Verificar si ya existe
                existing = self.db.query(Product).filter(
                    Product.vinted_id == product_data.vinted_id
                ).first()

                if existing:
                    continue

                # Buscar seller_id
                seller = self.db.query(Seller).filter(
                    Seller.vinted_id == product_data.seller_vinted_id
                ).first()

                # Crear producto con seller_id
                product_dict = product_data.model_dump()
                product_dict['search_id'] = search.id
                product_dict['seller_id'] = seller.id if seller else None

                new_product = Product(**product_dict)
                self.db.add(new_product)
                products_new += 1
                
                # Guardar para notificación posterior
                new_products_for_notification.append(new_product)

            self.db.commit()
            save_time = int((time.time() - save_start) * 1000)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {products_new} productos guardados en {save_time}ms")

        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error guardando productos: {e}")
            self.db.rollback()
            self._finish_log(log, "failed", 0, str(e))
            return self._build_error_result(start_time, str(e))
        
        # PASO 5: ENVIAR NOTIFICACIONES
        products_notified = 0
        
        if products_new > 0 and new_products_for_notification:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📨 Enviando notificaciones...")
            notify_start = time.time()
            
            try:
                from app.notifications.notification_manager import NotificationManager
                
                # Crear NotificationManager
                nm = NotificationManager(db=self.db)
                
                # Verificar si hay canales configurados
                nm_stats = nm.get_stats()
                
                if nm_stats['any_active']:
                    # Refrescar productos para tener IDs y relaciones
                    products_to_notify = []
                    for p in new_products_for_notification:
                        self.db.refresh(p)
                        products_to_notify.append(p)
                    
                    # Enviar notificaciones async
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        notify_results = loop.run_until_complete(nm.notify_products(products_to_notify))
                        products_notified = notify_results['success']
                        
                        notify_time = int((time.time() - notify_start) * 1000)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {products_notified}/{products_new} notificaciones enviadas en {notify_time}ms")
                        
                        # Mostrar canales que enviaron
                        channels = []
                        if nm_stats['telegram_active']:
                            channels.append("📱 Telegram")
                        if nm_stats['discord_active']:
                            channels.append("💬 Discord")
                        if nm_stats['webhook_active']:
                            channels.append("🌐 Webhook")
                        
                        if channels:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}]    Canales: {', '.join(channels)}")
                    
                    finally:
                        loop.close()
                
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  No hay canales de notificación configurados")
            
            except ImportError:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Sistema de notificaciones no disponible")
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error enviando notificaciones: {e}")
        
        # ESTADÍSTICAS FINALES
        total_time = int((time.time() - start_time) * 1000)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 Scraping completado en {total_time}ms")
        print(f"[{datetime.now().strftime('%H:%M:%S')}]    📊 Productos: {products_new}/{filter_stats_result['total']} guardados ({products_rejected} filtrados)")
        print(f"[{datetime.now().strftime('%H:%M:%S')}]    👥 Vendedores: {sellers_new} nuevos, {sellers_updated} actualizados")
        if products_notified > 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}]    📨 Notificaciones: {products_notified} enviadas")

        # ⭐ ACTUALIZAR LOG CON TODAS LAS MÉTRICAS
        self._finish_log(
            log, 
            "success", 
            products_new,
            products_filtered=products_rejected,
            products_notified=products_notified,
            sellers_new=sellers_new,
            sellers_updated=sellers_updated,
            duration_ms=total_time
        )

        return {
            "products_found": filter_stats_result['total'],
            "products_new": products_new,
            "products_filtered": products_rejected,
            "products_notified": products_notified,
            "sellers_new": sellers_new,
            "sellers_updated": sellers_updated,
            "duration_ms": total_time
        }
    
    def _finish_log(self, log: ScrapingLog, status: str, products_found: int, 
                    error_message: str = None, products_filtered: int = 0,
                    products_notified: int = 0, sellers_new: int = 0,
                    sellers_updated: int = 0, duration_ms: int = None):
        """⭐ MEJORADO: Guardar métricas completas en log."""
        setattr(log, "status", status)
        setattr(log, "finished_at", datetime.utcnow())
        setattr(log, "products_found", products_found)
        setattr(log, "products_filtered", products_filtered)
        setattr(log, "products_notified", products_notified)
        setattr(log, "sellers_new", sellers_new)
        setattr(log, "sellers_updated", sellers_updated)
        if duration_ms:
            setattr(log, "duration_ms", duration_ms)
        if error_message:
            setattr(log, "error_message", error_message)
        self.db.commit()
    
    def _build_empty_result(self, start_time: float) -> dict:
        """Helper para construir resultado vacío."""
        return {
            "products_found": 0,
            "products_new": 0,
            "products_filtered": 0,
            "products_notified": 0,
            "sellers_new": 0,
            "sellers_updated": 0,
            "duration_ms": int((time.time() - start_time) * 1000)
        }
    
    def _build_error_result(self, start_time: float, error: str) -> dict:
        """Helper para construir resultado de error."""
        return {
            "products_found": 0,
            "products_new": 0,
            "products_filtered": 0,
            "products_notified": 0,
            "sellers_new": 0,
            "sellers_updated": 0,
            "duration_ms": int((time.time() - start_time) * 1000),
            "error": error
        }
    
    def close(self):
        """Cierra las sesiones y recursos."""
        if self.requester:
            try:
                self.requester.close()
            except:
                pass
        
        if self._own_db and self.db:
            try:
                self.db.close()
            except:
                pass


def run_search(search_id: int) -> dict:
    """
    Función auxiliar para ejecutar una búsqueda por ID.
    
    Args:
        search_id: ID de la búsqueda a ejecutar
    
    Returns:
        dict: Resultados del scraping
    
    Raises:
        ValueError: Si la búsqueda no existe o está desactivada
    """
    db = SessionLocal()
    
    try:
        search = db.query(Search).filter(Search.id == search_id).first()
        
        if not search:
            raise ValueError(f"Búsqueda con ID {search_id} no encontrada")
        
        if not getattr(search, "is_active", True):
            raise ValueError(f"Búsqueda '{search.name}' está desactivada")
        
        # Ejecutar scraping
        scraper = VintedScraper(db=db)
        
        try:
            results = scraper.scrape_and_save(search)
        finally:
            scraper.close()

        # Actualizar timestamps de la búsqueda
        setattr(search, "last_run_at", datetime.utcnow())
        if results.get("products_new", 0) > 0:
            setattr(search, "last_success_at", datetime.utcnow())
        setattr(search, "updated_at", datetime.utcnow())
        db.commit()

        return results
        
    except Exception as e:
        db.rollback()
        raise
    
    finally:
        db.close()
