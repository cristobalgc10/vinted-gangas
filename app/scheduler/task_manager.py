"""
Task Manager - Gestor de tareas programadas con APScheduler

⭐ VERSIÓN MEJORADA CON:
- Registro completo en SchedulerLog de cada ejecución
- Sistema de notificaciones de errores automático
- Contador de errores consecutivos por búsqueda
- Jobs de mantenimiento (cleanup, mark_notified)
- API completa para gestión del scheduler
"""

import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import traceback

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import Search, Product, SchedulerLog, Settings
from app.scraper.main_scraper import VintedScraper


class TaskManager:
    """
    Gestor de tareas programadas para ejecutar búsquedas automáticamente.
    
    Funcionalidades:
    - Ejecuta búsquedas según su intervalo configurado
    - Registra todas las ejecuciones en SchedulerLog
    - Envía notificaciones automáticas si una búsqueda falla repetidamente
    - Jobs de mantenimiento diarios (limpieza de productos antiguos, etc.)
    - API completa para gestionar el scheduler desde la web
    """
    
    def __init__(self):
        """Inicializa el scheduler en modo background."""
        self.scheduler = BackgroundScheduler(
            timezone='UTC',
            job_defaults={
                'coalesce': True,  # Si se acumulan jobs, ejecutar solo el último
                'max_instances': 1,  # Un job a la vez
                'misfire_grace_time': 300  # 5 minutos de gracia si el sistema estaba apagado
            }
        )
        
        # Diccionario para tracking de errores: {search_id: consecutive_errors}
        self._error_counts: Dict[int, int] = {}
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📅 TaskManager inicializado")
    
    def start(self):
        """
        Inicia el scheduler y carga todas las búsquedas activas.
        """
        if self.scheduler.running:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Scheduler ya está en ejecución")
            return
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Iniciando scheduler...")
        
        # Cargar búsquedas activas
        self.load_all_searches()
        
        # Añadir jobs de mantenimiento
        self._add_maintenance_jobs()
        
        # Iniciar scheduler
        self.scheduler.start()
        
        # Mostrar resumen
        jobs = self.scheduler.get_jobs()
        search_jobs = [j for j in jobs if j.id.startswith('search_')]
        maintenance_jobs = [j for j in jobs if not j.id.startswith('search_')]
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Scheduler iniciado")
        print(f"[{datetime.now().strftime('%H:%M:%S')}]    • {len(search_jobs)} búsquedas activas")
        print(f"[{datetime.now().strftime('%H:%M:%S')}]    • {len(maintenance_jobs)} jobs de mantenimiento")
        
        # Mostrar próximas ejecuciones
        if search_jobs:
            next_jobs = sorted(search_jobs, key=lambda j: j.next_run_time)[:3]
            print(f"[{datetime.now().strftime('%H:%M:%S')}]    Próximas ejecuciones:")
            for job in next_jobs:
                search_id = int(job.id.split('_')[1])
                print(f"[{datetime.now().strftime('%H:%M:%S')}]      - Búsqueda #{search_id}: {job.next_run_time.strftime('%H:%M:%S')}")
    
    def stop(self):
        """Detiene el scheduler."""
        if not self.scheduler.running:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Scheduler no está en ejecución")
            return
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛑 Deteniendo scheduler...")
        self.scheduler.shutdown(wait=True)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Scheduler detenido")
    
    def load_all_searches(self):
        """
        Carga todas las búsquedas activas y las programa en el scheduler.
        """
        db = SessionLocal()
        
        try:
            # Obtener búsquedas activas
            searches = db.query(Search).filter(Search.is_active == True).all()
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📋 Cargando {len(searches)} búsquedas activas...")
            
            for search in searches:
                self.add_search_job(search)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Búsquedas cargadas")
        
        finally:
            db.close()
    
    def add_search_job(self, search: Search):
        """
        Añade o actualiza un job para una búsqueda.
        
        Args:
            search: Objeto Search a programar
        """
        job_id = f"search_{search.id}"
        
        # Eliminar job existente si existe
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        
        # Crear trigger de intervalo
        trigger = IntervalTrigger(
            minutes=search.interval_minutes,
            timezone='UTC'
        )
        
        # Añadir job
        self.scheduler.add_job(
            func=self._run_search_job,
            trigger=trigger,
            id=job_id,
            name=f"Búsqueda: {search.name}",
            args=[search.id],
            replace_existing=True
        )
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ➕ Job añadido: {search.name} (cada {search.interval_minutes} min)")
    
    def remove_search_job(self, search_id: int):
        """
        Elimina un job de búsqueda del scheduler.
        
        Args:
            search_id: ID de la búsqueda
        """
        job_id = f"search_{search_id}"
        
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ➖ Job eliminado: búsqueda #{search_id}")
            
            # Limpiar contador de errores
            if search_id in self._error_counts:
                del self._error_counts[search_id]
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Job no encontrado: búsqueda #{search_id}")
    
    def pause_search_job(self, search_id: int):
        """Pausa un job de búsqueda."""
        job_id = f"search_{search_id}"
        job = self.scheduler.get_job(job_id)
        
        if job:
            self.scheduler.pause_job(job_id)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏸️  Job pausado: búsqueda #{search_id}")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Job no encontrado: búsqueda #{search_id}")
    
    def resume_search_job(self, search_id: int):
        """Reanuda un job de búsqueda pausado."""
        job_id = f"search_{search_id}"
        job = self.scheduler.get_job(job_id)
        
        if job:
            self.scheduler.resume_job(job_id)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ▶️  Job reanudado: búsqueda #{search_id}")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Job no encontrado: búsqueda #{search_id}")
    
    def run_search_now(self, search_id: int):
        """
        Ejecuta una búsqueda inmediatamente (sin esperar al scheduler).
        
        Args:
            search_id: ID de la búsqueda a ejecutar
        """
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ Ejecución manual: búsqueda #{search_id}")
        self._run_search_job(search_id, manual=True)
    
    def _run_search_job(self, search_id: int, manual: bool = False):
        """
        ⭐ FUNCIÓN PRINCIPAL: Ejecuta un job de búsqueda y registra en SchedulerLog.
        
        Args:
            search_id: ID de la búsqueda
            manual: Si es ejecución manual o automática
        """
        db = SessionLocal()
        start_time = time.time()
        job_id = f"search_{search_id}"
        
        # Crear log inicial
        log = SchedulerLog(
            search_id=search_id,
            job_id=job_id,
            job_name=f"Búsqueda #{search_id}",
            job_type="search",
            started_at=datetime.utcnow(),
            status="running"
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        
        try:
            # Obtener búsqueda
            search = db.query(Search).filter(Search.id == search_id).first()
            
            if not search:
                raise ValueError(f"Búsqueda #{search_id} no encontrada")
            
            if not search.is_active and not manual:
                raise ValueError(f"Búsqueda '{search.name}' está desactivada")
            
            # Actualizar nombre del job
            log.job_name = f"Búsqueda: {search.name}"
            db.commit()
            
            print(f"\n{'='*80}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 {'[MANUAL]' if manual else '[AUTO]'} Ejecutando: {search.name}")
            print(f"{'='*80}")
            
            # Ejecutar scraper
            scraper = VintedScraper(db=db)
            
            try:
                results = scraper.scrape_and_save(search)
            finally:
                scraper.close()
            
            # Calcular duración
            duration_ms = int((time.time() - start_time) * 1000)
            
            # ⭐ ACTUALIZAR LOG CON RESULTADOS
            log.status = "success"
            log.finished_at = datetime.utcnow()
            log.duration_ms = duration_ms
            log.products_found = results.get('products_found', 0)
            log.products_new = results.get('products_new', 0)
            log.products_filtered = results.get('products_filtered', 0)
            log.products_notified = results.get('products_notified', 0)
            log.error_count = 0  # Reiniciar contador de errores
            db.commit()
            
            # Reiniciar contador de errores en memoria
            self._error_counts[search_id] = 0
            
            # Actualizar timestamps de la búsqueda
            search.last_run_at = datetime.utcnow()
            if results.get('products_new', 0) > 0:
                search.last_success_at = datetime.utcnow()
            db.commit()
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Job completado exitosamente")
            print(f"{'='*80}\n")
        
        except Exception as e:
            # Calcular duración
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Incrementar contador de errores
            if search_id not in self._error_counts:
                self._error_counts[search_id] = 0
            self._error_counts[search_id] += 1
            
            error_msg = str(e)
            error_trace = traceback.format_exc()
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ ERROR en job: {error_msg}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}]    Errores consecutivos: {self._error_counts[search_id]}")
            
            # ⭐ ACTUALIZAR LOG CON ERROR
            log.status = "error"
            log.finished_at = datetime.utcnow()
            log.duration_ms = duration_ms
            log.error_message = f"{error_msg}\n\n{error_trace}"
            log.error_count = self._error_counts[search_id]
            db.commit()
            
            # ⭐ ENVIAR NOTIFICACIÓN DE ERROR SI SE SUPERA EL UMBRAL
            self._check_and_notify_error(search_id, error_msg, db)
            
            print(f"{'='*80}\n")
        
        finally:
            db.close()
    
    def _check_and_notify_error(self, search_id: int, error_msg: str, db: Session):
        """
        ⭐ NUEVO: Verifica si se debe enviar notificación de error.
        
        Envía notificación si:
        - Las notificaciones de errores están habilitadas en Settings
        - Los errores consecutivos superan el umbral configurado
        """
        try:
            # Obtener configuración
            settings = db.query(Settings).first()
            
            if not settings:
                return
            
            # Verificar si las notificaciones están habilitadas
            if not settings.scheduler_error_notifications_enabled:
                return
            
            # Verificar umbral
            error_count = self._error_counts.get(search_id, 0)
            threshold = settings.scheduler_error_threshold or 3
            
            if error_count < threshold:
                return
            
            # Obtener búsqueda
            search = db.query(Search).filter(Search.id == search_id).first()
            if not search:
                return
            
            # Enviar notificación
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 Enviando notificación de error (umbral alcanzado: {error_count}/{threshold})")
            
            notification_text = f"""
🚨 **ALERTA: Búsqueda con errores repetidos**

**Búsqueda:** {search.name}
**Errores consecutivos:** {error_count}
**Último error:** {error_msg}

La búsqueda ha fallado {error_count} veces consecutivas. Por favor, revisa la configuración.
            """.strip()
            
            # Intentar enviar por todos los canales disponibles
            try:
                from app.notifications.notification_manager import NotificationManager
                nm = NotificationManager(db=db)
                
                # Enviar a Telegram si está configurado
                if settings.telegram_bot_token and settings.telegram_chat_id:
                    try:
                        from app.notifications.telegram_notifier import TelegramNotifier
                        telegram = TelegramNotifier(
                            bot_token=settings.telegram_bot_token,
                            chat_id=settings.telegram_chat_id
                        )
                        telegram.send_text(notification_text)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Notificación enviada a Telegram")
                    except Exception as e:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error enviando a Telegram: {e}")
                
                # Enviar a Discord si está configurado
                if settings.discord_webhook_url:
                    try:
                        import requests
                        requests.post(settings.discord_webhook_url, json={"content": notification_text})
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Notificación enviada a Discord")
                    except Exception as e:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error enviando a Discord: {e}")
                
                # Enviar a Webhook genérico si está configurado
                if settings.webhook_url:
                    try:
                        import requests
                        requests.post(settings.webhook_url, json={
                            "type": "scheduler_error",
                            "search_id": search_id,
                            "search_name": search.name,
                            "error_count": error_count,
                            "error_message": error_msg
                        })
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Notificación enviada a Webhook")
                    except Exception as e:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error enviando a Webhook: {e}")
            
            except ImportError:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Sistema de notificaciones no disponible")
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error enviando notificación de error: {e}")
        
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error en _check_and_notify_error: {e}")
    
    def _add_maintenance_jobs(self):
        """
        Añade jobs de mantenimiento periódicos.
        
        Jobs incluidos:
        - Limpieza diaria de productos antiguos (01:00 UTC)
        - Marcar productos como notificados (cada hora)
        """
        # Job 1: Limpieza diaria de productos antiguos
        self.scheduler.add_job(
            func=self._cleanup_old_products,
            trigger=CronTrigger(hour=1, minute=0, timezone='UTC'),
            id='data_cleanup_daily',
            name='Limpieza diaria de productos antiguos',
            replace_existing=True
        )
        
        # Job 2: Marcar productos antiguos como notificados
        self.scheduler.add_job(
            func=self._mark_old_products_as_notified,
            trigger=IntervalTrigger(hours=1, timezone='UTC'),
            id='data_mark_notified_periodic',
            name='Marcar productos antiguos como notificados',
            replace_existing=True
        )
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔧 Jobs de mantenimiento añadidos")
    
    def _cleanup_old_products(self):
        """
        ⭐ Job de mantenimiento: Elimina productos antiguos según configuración.
        """
        db = SessionLocal()
        start_time = time.time()
        
        # Crear log
        log = SchedulerLog(
            job_id='data_cleanup_daily',
            job_name='Limpieza diaria de productos antiguos',
            job_type='cleanup',
            started_at=datetime.utcnow(),
            status='running'
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        
        try:
            # Obtener configuración
            settings = db.query(Settings).first()
            
            if not settings or settings.auto_delete_products_days == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Limpieza automática desactivada")
                log.status = 'success'
                log.finished_at = datetime.utcnow()
                log.duration_ms = int((time.time() - start_time) * 1000)
                db.commit()
                return
            
            # Calcular fecha límite
            days = settings.auto_delete_products_days
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Contar productos a eliminar
            products_to_delete = db.query(Product).filter(
                Product.found_at < cutoff_date
            ).count()
            
            if products_to_delete == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ No hay productos antiguos para eliminar")
                log.status = 'success'
                log.finished_at = datetime.utcnow()
                log.duration_ms = int((time.time() - start_time) * 1000)
                db.commit()
                return
            
            # Eliminar productos
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🗑️  Eliminando {products_to_delete} productos más antiguos de {days} días...")
            
            db.query(Product).filter(
                Product.found_at < cutoff_date
            ).delete()
            
            db.commit()
            
            duration_ms = int((time.time() - start_time) * 1000)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {products_to_delete} productos eliminados en {duration_ms}ms")
            
            # Actualizar log
            log.status = 'success'
            log.finished_at = datetime.utcnow()
            log.duration_ms = duration_ms
            db.commit()
        
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error en limpieza: {e}")
            
            log.status = 'error'
            log.finished_at = datetime.utcnow()
            log.duration_ms = int((time.time() - start_time) * 1000)
            log.error_message = str(e)
            db.commit()
        
        finally:
            db.close()
    
    def _mark_old_products_as_notified(self):
        """
        ⭐ Job de mantenimiento: Marca productos antiguos como notificados.
        """
        db = SessionLocal()
        start_time = time.time()
        
        # Crear log
        log = SchedulerLog(
            job_id='data_mark_notified_periodic',
            job_name='Marcar productos antiguos como notificados',
            job_type='maintenance',
            started_at=datetime.utcnow(),
            status='running'
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        
        try:
            # Obtener configuración
            settings = db.query(Settings).first()
            
            if not settings or settings.auto_mark_notified_hours == 0:
                log.status = 'success'
                log.finished_at = datetime.utcnow()
                log.duration_ms = int((time.time() - start_time) * 1000)
                db.commit()
                return
            
            # Calcular fecha límite
            hours = settings.auto_mark_notified_hours
            cutoff_date = datetime.utcnow() - timedelta(hours=hours)
            
            # Actualizar productos
            products_updated = db.query(Product).filter(
                Product.is_notified == False,
                Product.found_at < cutoff_date
            ).update({
                'is_notified': True,
                'notified_at': datetime.utcnow()
            })
            
            db.commit()
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            if products_updated > 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {products_updated} productos marcados como notificados")
            
            # Actualizar log
            log.status = 'success'
            log.finished_at = datetime.utcnow()
            log.duration_ms = duration_ms
            db.commit()
        
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error marcando productos: {e}")
            
            log.status = 'error'
            log.finished_at = datetime.utcnow()
            log.duration_ms = int((time.time() - start_time) * 1000)
            log.error_message = str(e)
            db.commit()
        
        finally:
            db.close()
    
    def get_status(self) -> dict:
        """
        ⭐ Obtiene el estado actual del scheduler.
        
        Returns:
            dict: Información completa del scheduler
        """
        jobs = self.scheduler.get_jobs()
        search_jobs = [j for j in jobs if j.id.startswith('search_')]
        
        # Obtener próximas ejecuciones
        next_executions = []
        for job in sorted(search_jobs, key=lambda j: j.next_run_time)[:10]:
            search_id = int(job.id.split('_')[1])
            next_executions.append({
                'search_id': search_id,
                'job_id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        
        return {
            'running': self.scheduler.running,
            'jobs_count': len(jobs),
            'search_jobs_count': len(search_jobs),
            'maintenance_jobs_count': len(jobs) - len(search_jobs),
            'next_executions': next_executions
        }
    
    def get_all_jobs(self) -> List[dict]:
        """
        Obtiene información de todos los jobs.
        
        Returns:
            List[dict]: Lista con información de cada job
        """
        jobs = self.scheduler.get_jobs()
        
        result = []
        for job in jobs:
            result.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger),
                'pending': job.pending
            })
        
        return result


# ============================================================================
# INSTANCIA GLOBAL DEL SCHEDULER
# ============================================================================

# Crear instancia global (singleton)
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """
    Obtiene la instancia global del TaskManager (singleton).
    
    Returns:
        TaskManager: Instancia del gestor de tareas
    """
    global _task_manager
    
    if _task_manager is None:
        _task_manager = TaskManager()
    
    return _task_manager


def start_scheduler():
    """Inicia el scheduler global."""
    tm = get_task_manager()
    tm.start()


def stop_scheduler():
    """Detiene el scheduler global."""
    tm = get_task_manager()
    tm.stop()