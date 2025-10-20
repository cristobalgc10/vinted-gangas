"""
Script para ejecutar manualmente la gestión de datos.

Útil para:
- Probar la gestión de datos sin esperar al scheduler
- Ejecutar limpieza bajo demanda
- Debug y testing

Uso:
    # Ejecutar TODAS las tareas
    python scripts/run_data_cleanup.py
    
    # Solo tareas DIARIAS
    python scripts/run_data_cleanup.py --daily
    
    # Solo tareas PERIÓDICAS
    python scripts/run_data_cleanup.py --periodic
"""

import sys
import os
import argparse

# Añadir el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.data_management import DataManager
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def print_header(title: str):
    """Imprime un encabezado bonito."""
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)
    print()


def print_config(settings):
    """Muestra la configuración actual."""
    print("⚙️  CONFIGURACIÓN ACTUAL:")
    print(f"   • Auto-eliminar productos: {settings.auto_delete_products_days} días")
    print(f"   • Auto-marcar notificados: {settings.auto_mark_notified_hours} horas")
    print(f"   • Límite máximo productos: {settings.max_products_in_db}")
    print()


def print_daily_results(results):
    """Muestra resultados de tareas diarias."""
    print_header("📊 RESULTADOS - TAREAS DIARIAS")
    
    # Productos antiguos eliminados
    old_deleted = results.get("old_products_deleted", {})
    enabled = old_deleted.get("enabled", False)
    deleted = old_deleted.get("deleted", 0)
    days = old_deleted.get("days", 0)
    
    status = "✅" if enabled else "⏭️ "
    print(f"{status} Productos antiguos eliminados: {deleted}")
    if enabled and days > 0:
        print(f"   (configurado: más antiguos de {days} días)")
    elif not enabled:
        print(f"   (función desactivada)")
    
    # Límite de base de datos aplicado
    limit_applied = results.get("database_limit_applied", {})
    enabled = limit_applied.get("enabled", False)
    deleted = limit_applied.get("deleted", 0)
    limit = limit_applied.get("limit", 0)
    total = limit_applied.get("total", 0)
    
    status = "✅" if enabled else "⏭️ "
    print(f"\n{status} Productos eliminados por límite: {deleted}")
    if enabled and limit > 0:
        print(f"   (configurado: máximo {limit} productos, había {total})")
    elif not enabled:
        print(f"   (función desactivada)")
    
    # Duplicados limpiados
    dupes = results.get("duplicates_cleaned", {})
    deleted = dupes.get("deleted", 0)
    vinted_ids = dupes.get("vinted_ids", [])
    
    print(f"\n🧹 Productos duplicados eliminados: {deleted}")
    if deleted > 0:
        print(f"   ({len(vinted_ids)} vinted_ids afectados)")


def print_periodic_results(results):
    """Muestra resultados de tareas periódicas."""
    print_header("📊 RESULTADOS - TAREAS PERIÓDICAS")
    
    # Productos marcados como notificados
    marked_data = results.get("products_marked_notified", {})
    enabled = marked_data.get("enabled", False)
    marked = marked_data.get("marked", 0)
    hours = marked_data.get("hours", 0)
    
    status = "✅" if enabled else "⏭️ "
    print(f"{status} Productos marcados como notificados: {marked}")
    if enabled and hours > 0:
        print(f"   (configurado: más antiguos de {hours} horas)")
    elif not enabled:
        print(f"   (función desactivada)")


def run_all():
    """Ejecuta todas las tareas."""
    print_header("🔧 GESTIÓN DE DATOS - EJECUCIÓN COMPLETA")
    
    try:
        with DataManager() as manager:
            # Obtener y mostrar configuración
            settings = manager.get_settings()
            print_config(settings)
            
            # Ejecutar todas las tareas
            print("🚀 Ejecutando TODAS las tareas...")
            print()
            results = manager.run_all_tasks()
            
            # Mostrar resultados
            print_daily_results(results)
            print_periodic_results(results)
            
            print()
            print_header("✅ GESTIÓN COMPLETADA EXITOSAMENTE")
            
    except Exception as e:
        print()
        print_header("❌ ERROR EN GESTIÓN DE DATOS")
        print(f"Error: {e}")
        logger.error("Error ejecutando gestión de datos", exc_info=True)
        sys.exit(1)


def run_daily():
    """Ejecuta solo tareas diarias."""
    print_header("📅 GESTIÓN DE DATOS - TAREAS DIARIAS")
    
    try:
        with DataManager() as manager:
            # Obtener y mostrar configuración
            settings = manager.get_settings()
            print_config(settings)
            
            # Ejecutar tareas diarias
            print("🚀 Ejecutando tareas DIARIAS...")
            print()
            results = manager.run_daily_tasks()
            
            # Mostrar resultados
            print_daily_results(results)
            
            print()
            print_header("✅ TAREAS DIARIAS COMPLETADAS")
            
    except Exception as e:
        print()
        print_header("❌ ERROR EN TAREAS DIARIAS")
        print(f"Error: {e}")
        logger.error("Error ejecutando tareas diarias", exc_info=True)
        sys.exit(1)


def run_periodic():
    """Ejecuta solo tareas periódicas."""
    print_header("⏰ GESTIÓN DE DATOS - TAREAS PERIÓDICAS")
    
    try:
        with DataManager() as manager:
            # Obtener y mostrar configuración
            settings = manager.get_settings()
            print_config(settings)
            
            # Ejecutar tareas periódicas
            print("🚀 Ejecutando tareas PERIÓDICAS...")
            print()
            results = manager.run_periodic_tasks()
            
            # Mostrar resultados
            print_periodic_results(results)
            
            print()
            print_header("✅ TAREAS PERIÓDICAS COMPLETADAS")
            
    except Exception as e:
        print()
        print_header("❌ ERROR EN TAREAS PERIÓDICAS")
        print(f"Error: {e}")
        logger.error("Error ejecutando tareas periódicas", exc_info=True)
        sys.exit(1)


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="Ejecutar gestión de datos manualmente"
    )
    parser.add_argument(
        "--daily",
        action="store_true",
        help="Ejecutar solo tareas diarias"
    )
    parser.add_argument(
        "--periodic",
        action="store_true",
        help="Ejecutar solo tareas periódicas"
    )
    
    args = parser.parse_args()
    
    if args.daily:
        run_daily()
    elif args.periodic:
        run_periodic()
    else:
        run_all()


if __name__ == "__main__":
    main()
