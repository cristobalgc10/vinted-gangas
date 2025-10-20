"""
API Router - Endpoints REST para gestionar búsquedas y productos.

⭐ VERSIÓN MEJORADA CON:
- Endpoints completos del scheduler (/api/scheduler/...)
- Estadísticas detalladas (/api/stats/detailed, /api/stats/scheduler)
- Logs del scheduler (/api/scheduler/logs)
- Optimizaciones y código más limpio
"""

from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Search, Product, SchedulerLog, ScrapingLog
from app.schemas import (
    SearchCreate, SearchUpdate, SearchResponse,
    ProductResponse, StatsResponse, MessageResponse,
    SchedulerLogResponse, SchedulerStatusResponse, DetailedStatsResponse,
    SchedulerStatsResponse
)

# Crear el router con prefijo /api
router = APIRouter()


# ============================================================================
# ENDPOINTS DE BÚSQUEDAS
# ============================================================================

@router.get("/searches", response_model=List[SearchResponse])
async def get_searches(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """Obtener lista de búsquedas."""
    query = db.query(Search)
    
    if active_only:
        query = query.filter(Search.is_active == True)
    
    searches = query.offset(skip).limit(limit).all()
    
    # Añadir contador de productos
    for search in searches:
        search.products_count = len(search.products)
    
    return searches


@router.get("/searches/{search_id}", response_model=SearchResponse)
async def get_search(search_id: int, db: Session = Depends(get_db)):
    """Obtener una búsqueda específica por ID."""
    search = db.query(Search).filter(Search.id == search_id).first()
    
    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Búsqueda con ID {search_id} no encontrada"
        )
    
    search.products_count = len(search.products)
    return search


@router.post("/searches", response_model=SearchResponse, status_code=status.HTTP_201_CREATED)
async def create_search(search_data: SearchCreate, db: Session = Depends(get_db)):
    """Crear una nueva búsqueda."""
    db_search = Search(**search_data.model_dump())
    
    db.add(db_search)
    db.commit()
    db.refresh(db_search)
    
    # Añadir al scheduler si está activo
    if db_search.is_active:
        try:
            from app.scheduler.task_manager import get_task_manager
            tm = get_task_manager()
            if tm.scheduler.running:
                tm.add_search_job(db_search)
        except Exception as e:
            print(f"Error añadiendo job al scheduler: {e}")
    
    db_search.products_count = 0
    return db_search


@router.put("/searches/{search_id}", response_model=SearchResponse)
async def update_search(
    search_id: int,
    search_data: SearchUpdate,
    db: Session = Depends(get_db)
):
    """Actualizar una búsqueda existente."""
    db_search = db.query(Search).filter(Search.id == search_id).first()
    
    if not db_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Búsqueda con ID {search_id} no encontrada"
        )
    
    # Actualizar campos
    update_data = search_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_search, field, value)
    
    db_search.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_search)
    
    # Actualizar en el scheduler
    try:
        from app.scheduler.task_manager import get_task_manager
        tm = get_task_manager()
        if tm.scheduler.running:
            if db_search.is_active:
                tm.add_search_job(db_search)
            else:
                tm.remove_search_job(search_id)
    except Exception as e:
        print(f"Error actualizando job en scheduler: {e}")
    
    db_search.products_count = len(db_search.products)
    return db_search


@router.delete("/searches/{search_id}", response_model=MessageResponse)
async def delete_search(search_id: int, db: Session = Depends(get_db)):
    """Eliminar una búsqueda."""
    db_search = db.query(Search).filter(Search.id == search_id).first()
    
    if not db_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Búsqueda con ID {search_id} no encontrada"
        )
    
    search_name = db_search.name
    
    # Eliminar del scheduler
    try:
        from app.scheduler.task_manager import get_task_manager
        tm = get_task_manager()
        if tm.scheduler.running:
            tm.remove_search_job(search_id)
    except Exception as e:
        print(f"Error eliminando job del scheduler: {e}")
    
    db.delete(db_search)
    db.commit()
    
    return MessageResponse(
        message=f"Búsqueda '{search_name}' eliminada correctamente",
        success=True
    )


@router.post("/searches/{search_id}/toggle", response_model=MessageResponse)
async def toggle_search(search_id: int, db: Session = Depends(get_db)):
    """Activar/desactivar una búsqueda (toggle)."""
    db_search = db.query(Search).filter(Search.id == search_id).first()
    
    if not db_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Búsqueda con ID {search_id} no encontrada"
        )
    
    # Cambiar estado
    db_search.is_active = not db_search.is_active
    db_search.updated_at = datetime.utcnow()
    db.commit()
    
    # Actualizar scheduler
    try:
        from app.scheduler.task_manager import get_task_manager
        tm = get_task_manager()
        if tm.scheduler.running:
            if db_search.is_active:
                tm.add_search_job(db_search)
            else:
                tm.remove_search_job(search_id)
    except Exception as e:
        print(f"Error actualizando scheduler: {e}")
    
    estado = "activada" if db_search.is_active else "desactivada"
    return MessageResponse(
        message=f"Búsqueda '{db_search.name}' {estado}",
        success=True
    )


@router.post("/searches/{search_id}/run", response_model=MessageResponse)
async def run_search_now(search_id: int, db: Session = Depends(get_db)):
    """Ejecutar una búsqueda manualmente (forzar scraping)."""
    db_search = db.query(Search).filter(Search.id == search_id).first()
    
    if not db_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Búsqueda con ID {search_id} no encontrada"
        )
    
    # Ejecutar en el scheduler
    try:
        from app.scheduler.task_manager import get_task_manager
        tm = get_task_manager()
        
        # Ejecutar en background
        import threading
        thread = threading.Thread(target=tm.run_search_now, args=(search_id,))
        thread.daemon = True
        thread.start()
        
        return MessageResponse(
            message=f"Búsqueda '{db_search.name}' ejecutándose en background...",
            success=True
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando búsqueda: {e}"
        )


# ============================================================================
# ENDPOINTS DE PRODUCTOS
# ============================================================================

@router.get("/products", response_model=List[ProductResponse])
async def get_products(
    skip: int = 0,
    limit: int = 50,
    search_id: int = None,
    available_only: bool = False,
    new_only: bool = False,
    db: Session = Depends(get_db)
):
    """Obtener lista de productos encontrados."""
    query = db.query(Product)
    
    if search_id:
        query = query.filter(Product.search_id == search_id)
    
    if available_only:
        query = query.filter(Product.is_available == True)
    
    if new_only:
        query = query.filter(Product.is_notified == False)
    
    products = query.order_by(Product.found_at.desc()).offset(skip).limit(limit).all()
    
    return products


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """Obtener un producto específico."""
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto con ID {product_id} no encontrado"
        )
    
    return product


@router.post("/products/{product_id}/favorite")
async def toggle_favorite(product_id: int, db: Session = Depends(get_db)):
    """Marcar/desmarcar producto como favorito."""
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto con ID {product_id} no encontrado"
        )
    
    product.is_favorite = not product.is_favorite
    db.commit()
    
    estado = "añadido a favoritos" if product.is_favorite else "eliminado de favoritos"
    return JSONResponse(content={
        "message": f"Producto {estado}",
        "success": True,
        "is_favorite": product.is_favorite
    })


# ============================================================================
# ⭐ NUEVOS ENDPOINTS DEL SCHEDULER
# ============================================================================

@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status():
    """Obtiene el estado actual del scheduler."""
    try:
        from app.scheduler.task_manager import get_task_manager
        tm = get_task_manager()
        
        status_data = tm.get_status()
        
        return SchedulerStatusResponse(
            running=status_data['running'],
            jobs_count=status_data['jobs_count'],
            active_searches=status_data['search_jobs_count'],
            next_executions=status_data['next_executions']
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estado del scheduler: {e}"
        )


@router.post("/scheduler/start", response_model=MessageResponse)
async def start_scheduler():
    """Inicia el scheduler."""
    try:
        from app.scheduler.task_manager import get_task_manager
        tm = get_task_manager()
        
        if tm.scheduler.running:
            return MessageResponse(
                message="El scheduler ya está en ejecución",
                success=True
            )
        
        tm.start()
        
        return MessageResponse(
            message="Scheduler iniciado correctamente",
            success=True
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error iniciando scheduler: {e}"
        )


@router.post("/scheduler/stop", response_model=MessageResponse)
async def stop_scheduler():
    """Detiene el scheduler."""
    try:
        from app.scheduler.task_manager import get_task_manager
        tm = get_task_manager()
        
        if not tm.scheduler.running:
            return MessageResponse(
                message="El scheduler no está en ejecución",
                success=True
            )
        
        tm.stop()
        
        return MessageResponse(
            message="Scheduler detenido correctamente",
            success=True
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deteniendo scheduler: {e}"
        )


@router.get("/scheduler/logs", response_model=List[SchedulerLogResponse])
async def get_scheduler_logs(
    skip: int = 0,
    limit: int = 50,
    search_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Obtiene logs del scheduler."""
    query = db.query(SchedulerLog)
    
    if search_id:
        query = query.filter(SchedulerLog.search_id == search_id)
    
    if status_filter:
        query = query.filter(SchedulerLog.status == status_filter)
    
    logs = query.order_by(SchedulerLog.started_at.desc()).offset(skip).limit(limit).all()
    
    return logs


# ============================================================================
# ⭐ ENDPOINTS DE ESTADÍSTICAS MEJORADAS
# ============================================================================

@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """Obtener estadísticas generales de la aplicación."""
    # Contar búsquedas
    total_searches = db.query(Search).count()
    active_searches = db.query(Search).filter(Search.is_active == True).count()
    
    # Contar productos
    total_products = db.query(Product).count()
    new_products = db.query(Product).filter(Product.is_notified == False).count()
    
    # Productos encontrados hoy
    today = datetime.utcnow().date()
    products_today = db.query(Product).filter(
        Product.found_at >= datetime.combine(today, datetime.min.time())
    ).count()
    
    return StatsResponse(
        total_searches=total_searches,
        active_searches=active_searches,
        total_products=total_products,
        new_products=new_products,
        products_today=products_today
    )


@router.get("/stats/detailed", response_model=DetailedStatsResponse)
async def get_detailed_stats(db: Session = Depends(get_db)):
    """⭐ NUEVO: Estadísticas detalladas para dashboard."""
    
    # Búsquedas
    searches_stats = {
        'total': db.query(Search).count(),
        'active': db.query(Search).filter(Search.is_active == True).count(),
        'inactive': db.query(Search).filter(Search.is_active == False).count()
    }
    
    # Productos
    products_stats = {
        'total': db.query(Product).count(),
        'new': db.query(Product).filter(Product.is_notified == False).count(),
        'favorites': db.query(Product).filter(Product.is_favorite == True).count(),
        'available': db.query(Product).filter(Product.is_available == True).count()
    }
    
    # Top 5 búsquedas por productos encontrados
    top_searches = db.query(
        Search.id,
        Search.name,
        func.count(Product.id).label('products_count')
    ).join(Product).group_by(Search.id).order_by(desc('products_count')).limit(5).all()
    
    top_searches_list = [
        {
            'search_id': s.id,
            'search_name': s.name,
            'products_count': s.products_count
        }
        for s in top_searches
    ]
    
    # Precio promedio
    avg_price = db.query(func.avg(Product.price)).scalar() or 0.0
    
    # Productos por día (últimos 7 días)
    products_by_day = []
    for i in range(6, -1, -1):
        day = datetime.utcnow().date() - timedelta(days=i)
        count = db.query(Product).filter(
            func.date(Product.found_at) == day
        ).count()
        products_by_day.append({
            'date': day.isoformat(),
            'count': count
        })
    
    # Tasa de éxito (scraping logs)
    total_logs = db.query(ScrapingLog).count()
    success_logs = db.query(ScrapingLog).filter(ScrapingLog.status == 'success').count()
    success_rate = (success_logs / total_logs * 100) if total_logs > 0 else 0.0
    
    return DetailedStatsResponse(
        searches=searches_stats,
        products=products_stats,
        top_searches=top_searches_list,
        avg_price=round(avg_price, 2),
        products_by_day=products_by_day,
        success_rate=round(success_rate, 2)
    )


@router.get("/stats/scheduler", response_model=SchedulerStatsResponse)
async def get_scheduler_stats(db: Session = Depends(get_db)):
    """⭐ NUEVO: Estadísticas del scheduler."""
    
    # Total de ejecuciones
    total_executions = db.query(SchedulerLog).count()
    
    # Ejecuciones exitosas y fallidas
    successful = db.query(SchedulerLog).filter(SchedulerLog.status == 'success').count()
    failed = db.query(SchedulerLog).filter(SchedulerLog.status == 'error').count()
    
    # Tasa de éxito
    success_rate = (successful / total_executions * 100) if total_executions > 0 else 0.0
    
    # Duración promedio
    avg_duration = db.query(func.avg(SchedulerLog.duration_ms)).filter(
        SchedulerLog.duration_ms.isnot(None)
    ).scalar() or 0.0
    
    # Total de productos encontrados y nuevos
    total_products_found = db.query(func.sum(SchedulerLog.products_found)).scalar() or 0
    total_products_new = db.query(func.sum(SchedulerLog.products_new)).scalar() or 0
    
    # Ejecuciones en las últimas 24h
    yesterday = datetime.utcnow() - timedelta(hours=24)
    last_24h = db.query(SchedulerLog).filter(
        SchedulerLog.started_at >= yesterday
    ).count()
    
    # Errores por búsqueda (top 5 con más errores)
    errors_by_search = db.query(
        Search.id,
        Search.name,
        func.count(SchedulerLog.id).label('error_count'),
        func.max(SchedulerLog.error_count).label('consecutive_errors')
    ).join(
        SchedulerLog, Search.id == SchedulerLog.search_id
    ).filter(
        SchedulerLog.status == 'error'
    ).group_by(
        Search.id
    ).order_by(
        desc('error_count')
    ).limit(5).all()
    
    errors_list = [
        {
            'search_id': e.id,
            'search_name': e.name,
            'total_errors': e.error_count,
            'consecutive_errors': e.consecutive_errors or 0
        }
        for e in errors_by_search
    ]
    
    return SchedulerStatsResponse(
        total_executions=total_executions,
        successful_executions=successful,
        failed_executions=failed,
        success_rate=round(success_rate, 2),
        avg_duration_ms=round(avg_duration, 2),
        total_products_found=total_products_found,
        total_products_new=total_products_new,
        last_24h_executions=last_24h,
        errors_by_search=errors_list
    )


# ============================================================================
# ENDPOINTS HTMX (para formularios)
# ============================================================================

@router.post("/searches/create", response_model=MessageResponse)
async def create_search_htmx(
    name: str = Form(...),
    query: Optional[str] = Form(None),
    price_from: Optional[float] = Form(None),
    price_to: Optional[float] = Form(None),
    interval_minutes: int = Form(5),
    is_active: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Crear búsqueda desde formulario HTMX."""
    is_active_bool = is_active == "true" if is_active else False
    
    db_search = Search(
        name=name,
        query=query if query else None,
        price_from=price_from,
        price_to=price_to,
        interval_minutes=interval_minutes,
        is_active=is_active_bool
    )
    
    db.add(db_search)
    db.commit()
    
    # Añadir al scheduler
    if is_active_bool:
        try:
            from app.scheduler.task_manager import get_task_manager
            tm = get_task_manager()
            if tm.scheduler.running:
                tm.add_search_job(db_search)
        except Exception as e:
            print(f"Error añadiendo job: {e}")
    
    return MessageResponse(
        message=f"Búsqueda '{name}' creada correctamente",
        success=True
    )


@router.post("/searches/{search_id}/update", response_model=MessageResponse)
async def update_search_htmx(
    search_id: int,
    name: str = Form(...),
    query: Optional[str] = Form(None),
    price_from: Optional[float] = Form(None),
    price_to: Optional[float] = Form(None),
    interval_minutes: int = Form(5),
    is_active: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Actualizar búsqueda desde formulario HTMX."""
    db_search = db.query(Search).filter(Search.id == search_id).first()
    
    if not db_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Búsqueda con ID {search_id} no encontrada"
        )
    
    # Actualizar campos
    db_search.name = name
    db_search.query = query if query else None
    db_search.price_from = price_from
    db_search.price_to = price_to
    db_search.interval_minutes = interval_minutes
    db_search.is_active = is_active == "true" if is_active else False
    db_search.updated_at = datetime.utcnow()
    
    db.commit()
    
    # Actualizar scheduler
    try:
        from app.scheduler.task_manager import get_task_manager
        tm = get_task_manager()
        if tm.scheduler.running:
            if db_search.is_active:
                tm.add_search_job(db_search)
            else:
                tm.remove_search_job(search_id)
    except Exception as e:
        print(f"Error actualizando scheduler: {e}")
    
    return MessageResponse(
        message=f"Búsqueda '{name}' actualizada correctamente",
        success=True
    )