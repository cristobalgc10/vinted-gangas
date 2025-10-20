"""
Web Router - Rutas de las páginas HTML

⭐ VERSIÓN COMPLETA Y CORREGIDA:
- Todas las variables necesarias para products.html
- Paginación completa
- Filtros (búsqueda, favoritos, ordenar)
- Vista grid/list
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from app.database import get_db
from app.models import Search, Product

# Crear router
router = APIRouter()


# ============================================================================
# PÁGINAS PRINCIPALES
# ============================================================================

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """
    Dashboard principal con resumen de estadísticas.
    """
    # Estadísticas generales
    total_searches = db.query(Search).count()
    active_searches = db.query(Search).filter(Search.is_active == True).count()
    total_products = db.query(Product).count()
    new_products = db.query(Product).filter(Product.is_notified == False).count()
    
    # Búsquedas recientes (últimas 5)
    searches = db.query(Search).order_by(desc(Search.created_at)).limit(5).all()
    
    # Añadir contador de productos a cada búsqueda
    for search in searches:
        search.products_count = len(search.products)
    
    # Productos recientes (últimos 10)
    products = db.query(Product).order_by(desc(Product.found_at)).limit(10).all()
    
    return request.app.state.templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": {
            "total_searches": total_searches,
            "active_searches": active_searches,
            "total_products": total_products,
            "new_products": new_products,
            "products_today": 0
        },
        "searches": searches,
        "products": products
    })


@router.get("/searches", response_class=HTMLResponse)
async def searches_page(request: Request, db: Session = Depends(get_db)):
    """
    Página de gestión de búsquedas.
    """
    searches = db.query(Search).order_by(desc(Search.created_at)).all()
    
    # Añadir contador de productos
    for search in searches:
        search.products_count = len(search.products)
    
    return request.app.state.templates.TemplateResponse("searches.html", {
        "request": request,
        "searches": searches
    })


@router.get("/searches/new", response_class=HTMLResponse)
async def new_search(request: Request, modal: bool = False):
    """
    Formulario para crear una nueva búsqueda.
    """
    template = "search_form_modal.html" if modal else "searches_new.html"
    
    try:
        return request.app.state.templates.TemplateResponse(template, {
            "request": request
        })
    except:
        return request.app.state.templates.TemplateResponse("search_form_modal.html", {
            "request": request,
            "search": None,
            "is_new": True
        })


@router.get("/searches/{search_id}/edit", response_class=HTMLResponse)
async def edit_search(request: Request, search_id: int, modal: bool = False, db: Session = Depends(get_db)):
    """
    Formulario para editar una búsqueda existente.
    """
    search = db.query(Search).filter(Search.id == search_id).first()
    
    if not search:
        return request.app.state.templates.TemplateResponse("404.html", {
            "request": request,
            "message": f"Búsqueda con ID {search_id} no encontrada"
        }, status_code=404)
    
    template = "search_form_modal.html" if modal else "searches_edit.html"
    
    try:
        return request.app.state.templates.TemplateResponse(template, {
            "request": request,
            "search": search,
            "is_new": False
        })
    except:
        return request.app.state.templates.TemplateResponse("search_form_modal.html", {
            "request": request,
            "search": search,
            "is_new": False
        })


@router.get("/products", response_class=HTMLResponse)
async def products_page(
    request: Request,
    search_id: int = None,
    view: str = "grid",
    page: int = 1,
    per_page: int = 25,
    order_by: str = "date_desc",
    favorite_filter: str = "all",
    db: Session = Depends(get_db)
):
    """
    ⭐ Página de productos encontrados - COMPLETA
    
    Con soporte para:
    - Paginación (page, per_page)
    - Filtros (search_id, favorite_filter)
    - Ordenamiento (order_by)
    - Vista (grid/list)
    """
    # Validar per_page
    if per_page not in [25, 50, 75, 100]:
        per_page = 25
    
    # Configuración de paginación
    skip = (page - 1) * per_page
    
    # Query base
    query = db.query(Product)
    
    # ⭐ FILTRO POR BÚSQUEDA
    if search_id:
        query = query.filter(Product.search_id == search_id)
    
    # ⭐ FILTRO DE FAVORITOS
    if favorite_filter == "fav":
        query = query.filter(Product.is_favorite == True)
    
    # ⭐ ORDENAMIENTO
    if order_by == "date_desc":
        query = query.order_by(desc(Product.found_at))
    elif order_by == "date_asc":
        query = query.order_by(asc(Product.found_at))
    elif order_by == "price_asc":
        query = query.order_by(asc(Product.price))
    elif order_by == "price_desc":
        query = query.order_by(desc(Product.price))
    else:
        query = query.order_by(desc(Product.found_at))
    
    # Total de productos (para calcular páginas)
    total_products = query.count()
    total_pages = max(1, (total_products + per_page - 1) // per_page)
    
    # Asegurar que page no exceda total_pages
    if page > total_pages:
        page = total_pages
    
    # Obtener productos de la página actual
    products = query.offset(skip).limit(per_page).all()
    
    # Obtener búsqueda si hay filtro
    selected_search = None
    if search_id:
        selected_search = db.query(Search).filter(Search.id == search_id).first()
    
    # Todas las búsquedas para el filtro (llamado 'searches' en el template)
    searches = db.query(Search).order_by(Search.name).all()
    
    # ⭐ TODAS LAS VARIABLES QUE NECESITA EL TEMPLATE
    return request.app.state.templates.TemplateResponse("products.html", {
        "request": request,
        "products": products,
        "search": selected_search,  # Búsqueda seleccionada actual
        "searches": searches,  # Todas las búsquedas para el dropdown
        "selected_search_id": search_id,  # ID de la búsqueda seleccionada
        "view": view,
        "current_view": view,  # Alias para compatibilidad
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "total_products": total_products,
        "order_by": order_by,
        "view_mode": favorite_filter  # "all" o "fav"
    })


@router.get("/scheduler", response_class=HTMLResponse)
async def scheduler_page(request: Request):
    """
    Página del Scheduler.
    """
    return request.app.state.templates.TemplateResponse("scheduler.html", {
        "request": request
    })


@router.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    """
    Página de ayuda.
    """
    return request.app.state.templates.TemplateResponse("help.html", {
        "request": request
    })