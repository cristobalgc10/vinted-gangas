"""
Data Management - Gestión automática de datos según configuración.

Este módulo se encarga de:
1. Eliminar productos antiguos automáticamente (DIARIO)
2. Aplicar límites máximos de productos en BD (DIARIO)
3. Limpiar productos duplicados (DIARIO)
4. Marcar productos como notificados después de X horas (PERIÓDICO)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Product, Settings
from app.database import SessionLocal

# Configurar logging
logger = logging.getLogger(__name__)


class DataManager:
    """
    Gestor de limpieza y mantenimiento de datos.
    Lee la configuración de Settings y aplica las reglas automáticamente.
    """
    
    def __init__(self, db: Optional[Session] = None):
        """
        Inicializa el gestor.
        
        Args:
            db: Sesión de base de datos (opcional, se crea una si no se pasa)
        """
        self.db = db or SessionLocal()
        self._own_db = db is None  # Indica si creamos nuestra propia sesión
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._own_db:
            self.db.close()
    
    def get_settings(self) -> Settings:
        """
        Obtiene la configuración actual de la aplicación.
        
        Returns:
            Settings: Configuración activa
        """
        settings = self.db.query(Settings).filter(Settings.id == 1).first()
        
        if not settings:
            # Crear configuración por defecto si no existe
            logger.warning("⚠️  No se encontró configuración, creando valores por defecto")
            settings = Settings(id=1)
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)
        
        return settings
    
    # ========================================================================
    # TAREAS DIARIAS
    # ========================================================================
    
    def delete_old_products(self) -> Dict[str, int]:
        """
        Elimina productos más antiguos según configuración.
        
        Returns:
            dict: {'deleted': número de productos eliminados, 'days': días configurados, 'enabled': bool}
        """
        settings = self.get_settings()
        days = settings.auto_delete_products_days
        
        if days <= 0:
            logger.info("⏭️  Auto-eliminación de productos antiguos desactivada (days=0)")
            return {"deleted": 0, "days": 0, "enabled": False}
        
        # Calcular fecha límite
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Buscar productos antiguos
        old_products = self.db.query(Product).filter(
            Product.found_at < cutoff_date
        ).all()
        
        count = len(old_products)
        
        if count == 0:
            logger.info(f"✅ No hay productos más antiguos de {days} días")
            return {"deleted": 0, "days": days, "enabled": True}
        
        # Eliminar productos
        for product in old_products:
            self.db.delete(product)
        
        self.db.commit()
        
        logger.info(f"🗑️  Eliminados {count} productos más antiguos de {days} días")
        return {"deleted": count, "days": days, "enabled": True}
    
    def apply_database_limit(self) -> Dict[str, int]:
        """
        Aplica límite máximo de productos en BD.
        Elimina los más antiguos cuando se supera el límite.
        
        Returns:
            dict: {'deleted': número de productos eliminados, 'limit': límite configurado, 'total': total actual, 'enabled': bool}
        """
        settings = self.get_settings()
        max_products = settings.max_products_in_db
        
        if max_products <= 0:
            logger.info("⏭️  Límite de productos desactivado (limit=0)")
            return {"deleted": 0, "limit": 0, "total": 0, "enabled": False}
        
        # Contar productos actuales
        total_products = self.db.query(Product).count()
        
        if total_products <= max_products:
            logger.info(f"✅ Productos en BD ({total_products}) dentro del límite ({max_products})")
            return {"deleted": 0, "limit": max_products, "total": total_products, "enabled": True}
        
        # Calcular cuántos hay que eliminar
        to_delete = total_products - max_products
        
        # Obtener los más antiguos (ordenar por found_at ascendente)
        old_products = self.db.query(Product).order_by(
            Product.found_at.asc()
        ).limit(to_delete).all()
        
        # Eliminar productos
        for product in old_products:
            self.db.delete(product)
        
        self.db.commit()
        
        logger.info(
            f"🗑️  Eliminados {to_delete} productos más antiguos "
            f"(límite: {max_products}, total antes: {total_products})"
        )
        return {"deleted": to_delete, "limit": max_products, "total": total_products, "enabled": True}
    
    def clean_duplicate_products(self) -> Dict[str, int]:
        """
        Elimina productos duplicados (mismo vinted_id).
        Mantiene el más reciente (found_at más nuevo).
        
        Returns:
            dict: {'deleted': número de duplicados eliminados, 'vinted_ids': lista de IDs afectados}
        """
        logger.info("🔍 Buscando productos duplicados...")
        
        # Buscar vinted_ids duplicados
        duplicates = self.db.query(
            Product.vinted_id,
            func.count(Product.id).label('count')
        ).group_by(
            Product.vinted_id
        ).having(
            func.count(Product.id) > 1
        ).all()
        
        if not duplicates:
            logger.info("✅ No se encontraron productos duplicados")
            return {"deleted": 0, "vinted_ids": []}
        
        deleted_count = 0
        affected_vinted_ids = []
        
        # Para cada vinted_id duplicado
        for vinted_id, count in duplicates:
            # Obtener todos los productos con ese vinted_id
            products = self.db.query(Product).filter(
                Product.vinted_id == vinted_id
            ).order_by(
                Product.found_at.desc()  # Más reciente primero
            ).all()
            
            # Mantener el primero (más reciente), eliminar el resto
            to_delete = products[1:]  # Todos menos el primero
            
            for product in to_delete:
                self.db.delete(product)
                deleted_count += 1
            
            affected_vinted_ids.append(vinted_id)
        
        self.db.commit()
        
        logger.info(
            f"🧹 Eliminados {deleted_count} productos duplicados "
            f"({len(affected_vinted_ids)} vinted_ids afectados)"
        )
        
        return {
            "deleted": deleted_count,
            "vinted_ids": affected_vinted_ids
        }
    
    def run_daily_tasks(self) -> Dict[str, Dict]:
        """
        Ejecuta las tareas de mantenimiento DIARIAS.
        
        Returns:
            dict: Resultados de cada tarea
        """
        logger.info("📅 Iniciando tareas diarias de gestión de datos...")
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "task_type": "daily",
            "old_products_deleted": {},
            "database_limit_applied": {},
            "duplicates_cleaned": {}
        }
        
        try:
            # 1. Eliminar productos antiguos
            results["old_products_deleted"] = self.delete_old_products()
            
            # 2. Aplicar límite de BD
            results["database_limit_applied"] = self.apply_database_limit()
            
            # 3. Limpiar duplicados
            results["duplicates_cleaned"] = self.clean_duplicate_products()
            
            logger.info("✅ Tareas diarias completadas exitosamente")
            
        except Exception as e:
            logger.error(f"❌ Error en tareas diarias: {e}", exc_info=True)
            results["error"] = str(e)
        
        return results
    
    # ========================================================================
    # TAREAS PERIÓDICAS
    # ========================================================================
    
    def mark_products_as_notified(self) -> Dict[str, int]:
        """
        Marca productos como notificados después de X horas.
        
        Returns:
            dict: {'marked': número de productos marcados, 'hours': horas configuradas, 'enabled': bool}
        """
        settings = self.get_settings()
        hours = settings.auto_mark_notified_hours
        
        if hours <= 0:
            logger.info("⏭️  Auto-marcar como notificados desactivado (hours=0)")
            return {"marked": 0, "hours": 0, "enabled": False}
        
        # Calcular fecha límite
        cutoff_date = datetime.utcnow() - timedelta(hours=hours)
        
        # Buscar productos no notificados y antiguos
        old_unnotified = self.db.query(Product).filter(
            Product.is_notified == False,
            Product.found_at < cutoff_date
        ).all()
        
        count = len(old_unnotified)
        
        if count == 0:
            logger.info(f"✅ No hay productos sin notificar más antiguos de {hours} horas")
            return {"marked": 0, "hours": hours, "enabled": True}
        
        # Marcar como notificados
        for product in old_unnotified:
            product.is_notified = True
        
        self.db.commit()
        
        logger.info(f"✅ Marcados {count} productos como notificados (>{hours}h)")
        return {"marked": count, "hours": hours, "enabled": True}
    
    def run_periodic_tasks(self) -> Dict[str, Dict]:
        """
        Ejecuta las tareas de mantenimiento PERIÓDICAS.
        
        Returns:
            dict: Resultados de cada tarea
        """
        logger.info("⏰ Iniciando tareas periódicas de gestión de datos...")
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "task_type": "periodic",
            "products_marked_notified": {}
        }
        
        try:
            # Marcar productos como notificados
            results["products_marked_notified"] = self.mark_products_as_notified()
            
            logger.info("✅ Tareas periódicas completadas exitosamente")
            
        except Exception as e:
            logger.error(f"❌ Error en tareas periódicas: {e}", exc_info=True)
            results["error"] = str(e)
        
        return results
    
    # ========================================================================
    # MÉTODOS LEGACY (mantener compatibilidad)
    # ========================================================================
    
    def run_all_tasks(self) -> Dict[str, Dict]:
        """
        Ejecuta TODAS las tareas (diarias + periódicas).
        Útil para ejecución manual completa.
        
        Returns:
            dict: Resultados de todas las tareas
        """
        logger.info("🔧 Iniciando TODAS las tareas de gestión de datos...")
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "task_type": "all",
            "old_products_deleted": {},
            "database_limit_applied": {},
            "duplicates_cleaned": {},
            "products_marked_notified": {}
        }
        
        try:
            # Ejecutar tareas diarias
            results["old_products_deleted"] = self.delete_old_products()
            results["database_limit_applied"] = self.apply_database_limit()
            results["duplicates_cleaned"] = self.clean_duplicate_products()
            
            # Ejecutar tareas periódicas
            results["products_marked_notified"] = self.mark_products_as_notified()
            
            logger.info("✅ Todas las tareas completadas exitosamente")
            
        except Exception as e:
            logger.error(f"❌ Error en gestión de datos: {e}", exc_info=True)
            results["error"] = str(e)
        
        return results


# ============================================================================
# FUNCIONES HELPER (para usar desde scheduler o API)
# ============================================================================

def run_daily_maintenance() -> Dict[str, Dict]:
    """
    Ejecuta tareas de mantenimiento DIARIAS.
    Crea su propia sesión de BD y la cierra automáticamente.
    
    Returns:
        dict: Resultados de las tareas diarias
    """
    with DataManager() as manager:
        return manager.run_daily_tasks()


def run_periodic_maintenance() -> Dict[str, Dict]:
    """
    Ejecuta tareas de mantenimiento PERIÓDICAS.
    Crea su propia sesión de BD y la cierra automáticamente.
    
    Returns:
        dict: Resultados de las tareas periódicas
    """
    with DataManager() as manager:
        return manager.run_periodic_tasks()


def run_all_maintenance() -> Dict[str, Dict]:
    """
    Ejecuta TODAS las tareas de mantenimiento.
    Útil para ejecución manual completa.
    
    Returns:
        dict: Resultados de todas las tareas
    """
    with DataManager() as manager:
        return manager.run_all_tasks()


# ============================================================================
# FUNCIONES INDIVIDUALES (para usar desde API o scripts)
# ============================================================================

def delete_old_products(db: Optional[Session] = None) -> Dict[str, int]:
    """
    Elimina productos antiguos.
    
    Args:
        db: Sesión de BD (opcional)
    
    Returns:
        dict: Información de eliminación
    """
    with DataManager(db) as manager:
        return manager.delete_old_products()


def mark_old_as_notified(db: Optional[Session] = None) -> Dict[str, int]:
    """
    Marca productos antiguos como notificados.
    
    Args:
        db: Sesión de BD (opcional)
    
    Returns:
        dict: Información de marcado
    """
    with DataManager(db) as manager:
        return manager.mark_products_as_notified()


def apply_db_limit(db: Optional[Session] = None) -> Dict[str, int]:
    """
    Aplica límite de productos en BD.
    
    Args:
        db: Sesión de BD (opcional)
    
    Returns:
        dict: Información de eliminación
    """
    with DataManager(db) as manager:
        return manager.apply_database_limit()


def clean_duplicates(db: Optional[Session] = None) -> Dict[str, int]:
    """
    Limpia productos duplicados.
    
    Args:
        db: Sesión de BD (opcional)
    
    Returns:
        dict: Información de limpieza
    """
    with DataManager(db) as manager:
        return manager.clean_duplicate_products()
