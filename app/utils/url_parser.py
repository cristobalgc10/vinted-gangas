"""
Parser de URLs de Vinted.

Extrae todos los parámetros de una URL de búsqueda de Vinted
para poder replicar búsquedas avanzadas hechas en la web oficial.
"""

from urllib.parse import urlparse, parse_qs
from typing import Optional


def parse_vinted_url(url: str) -> dict:
    """
    Parsea una URL de Vinted y extrae todos los parámetros de búsqueda.
    
    Soporta:
    - Parámetros simples: search_text, price_from, price_to, order
    - Parámetros array: brand_ids[], size_ids[], color_ids[], etc.
    - Múltiples valores para el mismo parámetro
    
    Ejemplos:
        >>> parse_vinted_url("https://www.vinted.es/catalog?search_text=nike&price_from=15&price_to=30")
        {'query': 'nike', 'price_from': 15.0, 'price_to': 30.0}
        
        >>> parse_vinted_url("https://www.vinted.es/catalog?brand_ids[]=53&brand_ids[]=12")
        {'brand_ids': [53, 12]}
    
    Args:
        url: URL completa de Vinted (con o sin https://)
    
    Returns:
        dict con todos los parámetros parseados y convertidos a tipos apropiados
    
    Raises:
        ValueError: Si la URL no es válida o no es de Vinted
    """
    # Validar que es una URL válida
    if not url or not isinstance(url, str):
        raise ValueError("URL no válida: debe ser una cadena de texto")
    
    # Añadir https:// si no lo tiene
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Parsear URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValueError(f"Error parseando URL: {e}")
    
    # Validar que es de Vinted
    if 'vinted' not in parsed.netloc:
        raise ValueError(f"URL no es de Vinted: {parsed.netloc}")
    
    # Extraer query parameters
    params = parse_qs(parsed.query)
    
    # Resultado
    result = {}
    
    # Mapeo de parámetros Vinted → nuestro modelo
    # Parámetros simples (string/number)
    simple_params = {
        'search_text': ('query', str),
        'price_from': ('price_from', float),
        'price_to': ('price_to', float),
        'order': ('order', str),
    }
    
    # Parámetros array conocidos que queremos guardar
    # Mapeo: nombre_en_vinted → nombre_en_nuestro_modelo
    array_params_map = {
        'category_ids[]': 'category_ids',
        'catalog[]': 'category_ids',  # Vinted usa ambos nombres
        'brand_ids[]': 'brand_ids',
        'size_ids[]': 'size_ids',
        'color_ids[]': 'color_ids',
        'material_ids[]': 'material_ids',
        'status_ids[]': 'status_ids',
        'video_game_platform_ids[]': 'platform_ids',  # Añadido para plataformas
    }
    
    # Lista de parámetros que NO guardamos (ignorar)
    ignored_params = [
        # 'video_game_platform_ids[]',  # Ya no se ignora, ahora se mapea
        'order',  # Orden no es filtro de búsqueda
        'currency',  # Siempre EUR en España
        'time',  # Timestamp
        'search_id',  # ID interno de Vinted
    ]
    
    # Procesar parámetros simples
    for vinted_key, (our_key, type_converter) in simple_params.items():
        if vinted_key in params:
            value = params[vinted_key][0]  # parse_qs devuelve listas
            try:
                result[our_key] = type_converter(value)
            except (ValueError, TypeError):
                # Si no se puede convertir, ignorar
                pass
    
    # Procesar parámetros array
    for vinted_key, our_key in array_params_map.items():
        if vinted_key in params:
            # Convertir a lista de enteros
            try:
                values = [int(v) for v in params[vinted_key]]
                # Si ya existe este campo, combinar valores (evitar duplicados)
                if our_key in result:
                    result[our_key] = list(set(result[our_key] + values))
                else:
                    result[our_key] = values
            except (ValueError, TypeError):
                # Si no se puede convertir, ignorar
                pass
    
    # Validar que al menos tiene algo útil
    if not result:
        raise ValueError("URL no contiene parámetros de búsqueda válidos")
    
    return result


def validate_vinted_search_params(params: dict) -> dict:
    """
    Valida y normaliza parámetros de búsqueda de Vinted.
    
    Args:
        params: Diccionario con parámetros (de parse_vinted_url o manual)
    
    Returns:
        dict con parámetros validados y valores por defecto
    
    Raises:
        ValueError: Si faltan parámetros requeridos o hay valores inválidos
    """
    result = params.copy()
    
    # Query por defecto vacío (permitimos búsqueda solo por precio/filtros)
    if 'query' not in result:
        result['query'] = ""
    
    # Validar precios
    if 'price_from' in result and 'price_to' in result:
        if result['price_from'] > result['price_to']:
            raise ValueError("price_from no puede ser mayor que price_to")
        if result['price_from'] < 0 or result['price_to'] < 0:
            raise ValueError("Los precios no pueden ser negativos")
    
    # Validar arrays (deben ser listas no vacías)
    for key in ['category_ids', 'brand_ids', 'size_ids', 'color_ids', 'material_ids', 'status_ids']:
        if key in result:
            if not isinstance(result[key], list) or not result[key]:
                raise ValueError(f"{key} debe ser una lista no vacía")
    
    return result


def format_vinted_url_preview(params: dict) -> str:
    """
    Formatea los parámetros parseados en un texto legible para mostrar al usuario.
    
    Args:
        params: Diccionario con parámetros parseados
    
    Returns:
        str con resumen de filtros aplicados
    
    Example:
        >>> format_vinted_url_preview({'query': 'nike', 'price_from': 15.0, 'price_to': 30.0})
        "🔍 nike | 💰 15€ - 30€"
    """
    parts = []
    
    if params.get('query'):
        parts.append(f"🔍 {params['query']}")
    
    if params.get('price_from') is not None and params.get('price_to') is not None:
        parts.append(f"💰 {params['price_from']}€ - {params['price_to']}€")
    elif params.get('price_from') is not None:
        parts.append(f"💰 Desde {params['price_from']}€")
    elif params.get('price_to') is not None:
        parts.append(f"💰 Hasta {params['price_to']}€")
    
    # Contar filtros adicionales
    filter_counts = []
    if params.get('brand_ids'):
        filter_counts.append(f"{len(params['brand_ids'])} marca(s)")
    if params.get('size_ids'):
        filter_counts.append(f"{len(params['size_ids'])} talla(s)")
    if params.get('color_ids'):
        filter_counts.append(f"{len(params['color_ids'])} color(es)")
    if params.get('category_ids'):
        filter_counts.append(f"{len(params['category_ids'])} categoría(s)")
    
    if filter_counts:
        parts.append(f"🎯 {', '.join(filter_counts)}")
    
    return ' | '.join(parts) if parts else "Sin filtros"
