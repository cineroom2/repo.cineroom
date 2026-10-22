# resources/lib/tmdb_api.py
# -*- coding: utf-8 -*-
import requests
import xbmc
import xbmcaddon
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from .db import db
import re
from datetime import date

ADDON = xbmcaddon.Addon()
TMDB_API_KEY = ADDON.getSetting("tmdb_api") or "fbd7330e6872ea2d2ef87adc1ca6102a"
TMDB_LANG = ADDON.getSetting("tmdb_language") or "pt-BR"
BASE_URL = "https://api.themoviedb.org/3"

# --- CONFIGURAÇÕES DE IMAGEM ---
IMG_POSTER = "https://image.tmdb.org/t/p/w342"
IMG_BACKDROP = "https://image.tmdb.org/t/p/original"

# --- SESSION REUTILIZÁVEL (GRANDE MELHORIA) ---
# Reutilizar conexões HTTP é MUITO mais rápido que criar novas a cada request
_session = None

def get_session():
    """Retorna uma sessão HTTP reutilizável com pool de conexões."""
    global _session
    if _session is None:
        _session = requests.Session()
        # Aumenta o pool de conexões para requisições paralelas
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=20,
            max_retries=2,
            pool_block=False
        )
        _session.mount('https://', adapter)
        _session.mount('http://', adapter)
    return _session

# --- MAPAS DE GÊNEROS (Unificados) ---
GENRES_MAP = {
    'movie': {28: "Ação", 12: "Aventura", 16: "Animação", 35: "Comédia", 80: "Crime", 99: "Documentário", 18: "Drama", 10751: "Família", 14: "Fantasia", 36: "História", 27: "Terror", 10402: "Música", 9648: "Mistério", 10749: "Romance", 878: "Ficção científica", 10770: "Cinema TV", 53: "Suspense", 10752: "Guerra", 37: "Faroeste"},
    'tv': {10759: 'Ação e Aventura', 16: 'Animação', 35: 'Comédia', 80: 'Crime', 99: 'Documentário', 18: 'Drama', 10751: 'Família', 10762: 'Infantil', 9648: 'Mistério', 10763: 'Notícias', 10764: 'Reality Show', 10765: 'Ficção Científica e Fantasia', 10766: 'Novela', 10767: 'Talk Show', 10768: 'Guerra e Política', 37: 'Faroeste'}
}

# --- FUNÇÕES INTERNAS (Helpers) ---

def _normalize_item(item, media_type, extra=None):
    """Padroniza os campos para filmes e séries em um único lugar."""
    is_movie = media_type == 'movie'
    extra = extra or {'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0, 'certification': '', 'episodes_count': 0, 'seasons_count': 0}
    
    g_ids = item.get('genre_ids', [])
    g_map = GENRES_MAP.get('movie' if is_movie else 'tv', {})
    g_names = [g_map.get(gid) for gid in g_ids if gid in g_map]

    backdrop = item.get('backdrop_path')
    return {
        'tmdb_id': item.get('id'),
        'imdb_id': extra.get('imdb_id'),
        'title': item.get('title' if is_movie else 'name'),
        'original_title': item.get('original_title' if is_movie else 'original_name'),
        'genres': g_names or [g.get('name') for g in item.get('genres', [])],
        'poster': f"{IMG_POSTER}{item.get('poster_path')}" if item.get('poster_path') else '',
        'backdrop': f"{IMG_BACKDROP}{backdrop}" if backdrop else '',
        'fanart': f"{IMG_BACKDROP}{backdrop}" if backdrop else '',
        'clearlogo': extra.get('clearlogo'),
        'providers': extra.get('providers'),
        'synopsis': item.get('overview', ''),
        'year': (item.get('release_date' if is_movie else 'first_air_date') or '0000')[:4],
        'rating': item.get('vote_average', 0.0),
        'runtime': extra.get('runtime', 0),
        'certification': extra.get('certification', ''),
        'media_type': 'movie' if is_movie else 'tvshow',
        'episodes_count': extra.get('episodes_count', 0),
        'seasons_count': extra.get('seasons_count', 0),
    }
    
    

# ── Cache de lookups locais ────────────────────────────────────────────────
from typing import Optional

_local_movie_ids: Optional[set] = None
_local_tv_ids: Optional[set] = None

def _get_local_ids(media_type):
    global _local_movie_ids, _local_tv_ids
    if media_type == 'movie':
        if _local_movie_ids is None:
            try:
                from .db import db as _db
                _local_movie_ids = _db.get_all_movie_ids_set()
            except Exception:
                _local_movie_ids = set()
        return _local_movie_ids
    else:
        if _local_tv_ids is None:
            try:
                from .db import db as _db
                _local_tv_ids = _db.get_all_tvshow_ids_set()
            except Exception:
                _local_tv_ids = set()
        return _local_tv_ids


def _extras_from_local(tmdb_id, media_type):
    """
    Tenta montar o dict de extras direto do banco local.
    Retorna None se o item não estiver no catálogo.
    """
    try:
        from .db import db as _db
        if media_type == 'movie':
            row = _db.get_movie_by_id(tmdb_id)
        else:
            row = _db.get_tvshow_by_id(tmdb_id)

        if not row:
            return None

        # row é dict (base_db usa row_factory=sqlite3.Row + _rows_to_dict)
        if isinstance(row, list):
            row = row[0] if row else None
        if not row:
            return None

        providers = row.get('providers') or []
        if isinstance(providers, str):
            try:
                import json as _json
                providers = _json.loads(providers)
            except Exception:
                providers = []

        return {
            'imdb_id':       row.get('imdb_id', ''),
            'clearlogo':     row.get('clearlogo', ''),
            'providers':     providers,
            'runtime':       row.get('runtime', 0),
            'certification': row.get('certification', ''),
            'tagline':       row.get('tagline', ''),
            'episodes_count': row.get('number_of_episodes', 0),
            'seasons_count':  row.get('number_of_seasons', 0)
                              or row.get('season_count', 0),
        }
    except Exception:
        return None


_EMPTY_EXTRA = {
    'imdb_id': '', 'clearlogo': '', 'providers': [],
    'runtime': 0, 'certification': '', 'tagline': '',
    'episodes_count': 0, 'seasons_count': 0,
}


def _fetch_tmdb_extra(item, media_type):
    """Request ao TMDB — só chamada quando o item NÃO está no banco local."""
    tmdb_id  = item.get('id')
    endpoint = 'movie' if media_type == 'movie' else 'tv'
    url      = f"{BASE_URL}/{endpoint}/{tmdb_id}"

    append = "external_ids,images,watch/providers"
    append += ",release_dates" if media_type == 'movie' else ",content_ratings"

    params = {
        "api_key":            TMDB_API_KEY,
        "append_to_response": append,
        "include_image_language": "en,pt,null"
    }
    try:
        res      = get_session().get(url, params=params, timeout=3).json()
        logos    = res.get('images', {}).get('logos', [])
        watch    = res.get('watch/providers', {}).get('results', {}).get('BR', {})
        br_prov  = watch.get('flatrate') or watch.get('buy') or []

        certification = ''
        if media_type == 'movie':
            for r in res.get('release_dates', {}).get('results', []):
                if r.get('iso_3166_1') == 'BR':
                    for rd in r.get('release_dates', []):
                        cert = rd.get('certification', '')
                        if cert:
                            certification = cert
                            break
                    break
        else:
            for r in res.get('content_ratings', {}).get('results', []):
                if r.get('iso_3166_1') == 'BR':
                    certification = r.get('rating', '')
                    break

        return {
            'imdb_id':        res.get('external_ids', {}).get('imdb_id', ''),
            'clearlogo':      f"{IMG_POSTER}{logos[0]['file_path']}" if logos else '',
            'providers':      [p.get('provider_name') for p in br_prov],
            'runtime':        res.get('runtime', 0) if media_type == 'movie' else 0,
            'certification':  certification,
            'tagline':        res.get('tagline', ''),
            'episodes_count': res.get('number_of_episodes', 0) if media_type == 'tv' else 0,
            'seasons_count':  res.get('number_of_seasons',  0) if media_type == 'tv' else 0,
        }
    except Exception:
        return _EMPTY_EXTRA


def _fetch_extras_batch(items, media_type):
    """
    Monta extras para uma lista de itens do TMDB.

    Estratégia em dois passos:
      1. Para cada item, tenta servir do banco local (zero requests).
      2. Apenas os itens ausentes do catálogo vão para o TMDB em paralelo.

    Com conteúdo majoritariamente curado, a grande maioria dos itens
    de listas populares/trending já estará no banco — as requests ao TMDB
    ficam reservadas para itens genuinamente externos (ex: resultados de
    busca fora do catálogo).
    """
    if not items:
        return []

    results   = [None] * len(items)
    need_tmdb = []  # [(original_index, item), ...]

    local_ids = _get_local_ids(media_type)

    for idx, item in enumerate(items):
        tmdb_id = item.get('id')
        if tmdb_id and tmdb_id in local_ids:
            extra = _extras_from_local(tmdb_id, media_type)
            if extra is not None:
                results[idx] = extra
                continue
        # Não está no banco local (ou banco falhou) → vai pro TMDB
        need_tmdb.append((idx, item))

    if need_tmdb:
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_map = {
                executor.submit(_fetch_tmdb_extra, item, media_type): idx
                for idx, item in need_tmdb
            }
            for future in as_completed(future_map):
                idx = future_map[future]
                try:
                    results[idx] = future.result(timeout=5)
                except Exception:
                    results[idx] = _EMPTY_EXTRA

    # Garante que nenhuma posição ficou None
    for i in range(len(results)):
        if results[i] is None:
            results[i] = _EMPTY_EXTRA

    return results

# --- FUNÇÕES PÚBLICAS DE LISTAGEM ---

def fetch_trending(media_type='movie', page=1):
    """Função genérica para Trending de filmes ou séries - OTIMIZADA."""
    cache_key = f"trending_{media_type}_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: 
        return cached

    url = f"{BASE_URL}/trending/{media_type}/day"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG}
    
    try:
        # USA SESSÃO + TIMEOUT REDUZIDO
        r = get_session().get(url, params=params, timeout=5)
        data = r.json().get('results', [])

        # DEBUG: Verifique se os IDs estão corretos
        
        # OTIMIZAÇÃO: Só busca extras se realmente necessário
        extra_results = _fetch_extras_batch(data, media_type)
        
        # DEBUG: Verifique extras IDs

        # Normaliza o resultado final
        results = []
        for item, extra in zip(data, extra_results):
            # Verificação de segurança
            if item.get('id') and extra.get('imdb_id'):
                # Pode adicionar verificação aqui
                pass
            normalized = _normalize_item(item, media_type, extra)
            results.append(normalized)
            
            # DEBUG: Log para identificar problemas

        if results:
            db.save_tmdb_cache(cache_key, results)
        return results
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro Trending {media_type}: {str(e)}", xbmc.LOGERROR)
        return []
    
    
def fetch_certification(tmdb_id, media_type='movie'):
    endpoint = 'movie' if media_type == 'movie' else 'tv'
    url = f"{BASE_URL}/{endpoint}/{tmdb_id}/release_dates" if media_type == 'movie' \
          else f"{BASE_URL}/{endpoint}/{tmdb_id}/content_ratings"
    params = {"api_key": TMDB_API_KEY}
    try:
        data = get_session().get(url, params=params, timeout=5).json()
        if media_type == 'movie':
            for result in data.get('results', []):
                if result.get('iso_3166_1') == 'BR':
                    for rd in result.get('release_dates', []):
                        cert = rd.get('certification', '')
                        if cert:
                            return cert
        else:
            for result in data.get('results', []):
                if result.get('iso_3166_1') == 'BR':
                    return result.get('rating', '')
    except Exception:
        pass
    return ''

def fetch_recommendations(tmdb_id, media_type='movie', limit=10):
    cache_key = f"rec_{media_type}_{tmdb_id}"
    cached = db.get_tmdb_cache(cache_key, hours=72)
    if cached:
        return cached

    endpoint = 'movie' if media_type == 'movie' else 'tv'
    url = f"{BASE_URL}/{endpoint}/{tmdb_id}/recommendations"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": 1}

    try:
        data = get_session().get(url, params=params, timeout=5).json().get('results', [])[:limit]
        results = [_normalize_item(item, media_type) for item in data]
        if results:
            db.save_tmdb_cache(cache_key, results)
        return results
    except Exception:
        return []


def fetch_similar(tmdb_id, media_type='movie', limit=10):
    cache_key = f"similar_{media_type}_{tmdb_id}"
    cached = db.get_tmdb_cache(cache_key, hours=72)
    if cached:
        return cached

    endpoint = 'movie' if media_type == 'movie' else 'tv'
    url = f"{BASE_URL}/{endpoint}/{tmdb_id}/similar"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": 1}

    try:
        data = get_session().get(url, params=params, timeout=5).json().get('results', [])[:limit]
        results = [_normalize_item(item, media_type) for item in data]
        if results:
            db.save_tmdb_cache(cache_key, results)
        return results
    except Exception:
        return []    
    
def resolve_keyword_ids(keyword_strings):
    """
    Converte uma lista de strings de keyword nos IDs numéricos da TMDB.

    Usa /search/keyword para cada string e retorna todos os IDs encontrados
    (OR entre eles, igual ao comportamento anterior com IDs hardcoded).
    Resultado cacheado por 30 dias — praticamente permanente, pois IDs de
    keyword na TMDB são estáveis.

    Parâmetros
    ----------
    keyword_strings : list[str]
        Ex: ["heist", "bank robbery"]

    Retorna
    -------
    list[int] — IDs resolvidos. Lista vazia se nenhum for encontrado.
    """
    if not keyword_strings:
        return []

    resolved = []
    for kw in keyword_strings:
        cache_key = f"kwid_{kw.replace(' ', '_')}"
        cached = db.get_tmdb_cache(cache_key, hours=720)   # 30 dias
        if cached:
            resolved.extend(cached)
            continue

        try:
            r = get_session().get(
                f"{BASE_URL}/search/keyword",
                params={"api_key": TMDB_API_KEY, "query": kw},
                timeout=5,
            )
            ids = [item["id"] for item in r.json().get("results", []) if item.get("name", "").lower() == kw.lower()]
            if ids:
                db.save_tmdb_cache(cache_key, ids)
                resolved.extend(ids)
        except Exception as e:
            xbmc.log(f"[TMDB] resolve_keyword_ids('{kw}'): {e}", xbmc.LOGWARNING)

    return resolved


def fetch_by_keyword(keyword_ids, media_type='movie', page=1):
    """
    Busca filmes ou séries na TMDB usando keyword IDs reais (/discover).
 
    Parâmetros
    ----------
    keyword_ids : list[int]
        IDs numéricos vindos de keywords.get_theme_keyword_ids().
        São combinados com OR (pipe '|') no parâmetro with_keywords.
    media_type  : 'movie' | 'tv'
    page        : página (1-based, a TMDB suporta até 500)
 
    Retorna
    -------
    list[dict] — mesma estrutura de _normalize_item usada no resto do addon.
    Lista vazia em caso de erro ou sem resultados.
 
    Cache
    -----
    TTL de 72 h em tmdb_cache. Chave: "kw_{media_type}_{ids_joined}_p{page}".
    """
    if not keyword_ids:
        return []
 
    # Chave de cache estável independente da ordem dos IDs
    ids_key   = "_".join(str(i) for i in sorted(keyword_ids))
    cache_key = f"kw_{media_type}_{ids_key}_p{page}"
 
    cached = db.get_tmdb_cache(cache_key, hours=168)  # 7 dias, pois keywords são estáveis
    if cached:
        return cached
 
    endpoint = 'movie' if media_type == 'movie' else 'tv'
    url      = f"{BASE_URL}/discover/{endpoint}"
 
    params = {
        "api_key":       TMDB_API_KEY,
        "language":      TMDB_LANG,
        "page":          page,
        "sort_by":       "vote_count.desc",      # os mais votados primeiro
        "vote_count.gte": 50,                    # filtra lixo sem votos
        "with_keywords": "|".join(str(i) for i in keyword_ids),  # OR
    }
 
    try:
        r    = get_session().get(url, params=params, timeout=6)
        data = r.json().get('results', [])
 
        if not data:
            return []
 
        # Busca extras em batch (clearlogo, providers BR, certificação…)
        extras  = _fetch_extras_batch(data, media_type)
        results = [
            _normalize_item(item, media_type, extra)
            for item, extra in zip(data, extras)
        ]
 
        if results:
            db.save_tmdb_cache(cache_key, results)
 
        return results
 
    except Exception as e:
        xbmc.log(f"[TMDB] fetch_by_keyword({keyword_ids}): {e}", xbmc.LOGERROR)
        return []    

# Wrappers para manter compatibilidade
def fetch_trending_movies(page=1): 
    return fetch_trending('movie', page)

def fetch_trending_tvshows(page=1): 
    return fetch_trending('tv', page)

def search_tmdb(query, page=1, media_type=None):
    """Busca TMDB. media_type='movie'|'tv' filtra o tipo; None retorna ambos."""
    if media_type in ('movie', 'tv'):
        endpoint = 'movie' if media_type == 'movie' else 'tv'
        url = f"{BASE_URL}/search/{endpoint}"
    else:
        url = f"{BASE_URL}/search/multi"

    params = {
        "api_key":       TMDB_API_KEY,
        "query":         query,
        "language":      TMDB_LANG,
        "page":          page,
        "include_adult": "false"
    }

    try:
        r = get_session().get(url, params=params, timeout=5)
        data = r.json().get('results', [])

        if media_type in ('movie', 'tv'):
            for item in data:
                item['media_type'] = media_type
            filtered = data
        else:
            filtered = [i for i in data if i.get('media_type') in ['movie', 'tv']]

        movies  = [i for i in filtered if i.get('media_type') == 'movie']
        tvshows = [i for i in filtered if i.get('media_type') == 'tv']

        movie_extras = _fetch_extras_batch(movies,  'movie')
        tv_extras    = _fetch_extras_batch(tvshows, 'tv')

        results   = []
        movie_idx = 0
        tv_idx    = 0

        for item in filtered:
            mt = item.get('media_type')
            if mt == 'movie':
                extra = movie_extras[movie_idx]
                movie_idx += 1
            else:
                extra = tv_extras[tv_idx]
                tv_idx += 1
            results.append(_normalize_item(item, mt, extra))

        return results

    except Exception as e:
        xbmc.log(f"[TMDB SEARCH] Erro: {str(e)}", xbmc.LOGERROR)
        return []

# --- FUNÇÕES DE POPULARIDADE LOCAL ---

def update_local_popularity():
    """Sincroniza popularidade - OTIMIZADA."""
    _sync_popularity('movie', db.get_all_movie_ids_set(), db.update_popularity_bulk)
    _sync_popularity('tv', db.get_all_tvshow_ids_set(), db.update_tv_popularity_bulk)

def _sync_popularity(media_type, local_ids, update_func):
    """Lógica auxiliar para baixar popularidade - OTIMIZADA."""
    if not local_ids: 
        return
    
    popular_tmdb = []
    
    # OTIMIZAÇÃO: Busca paralela de páginas
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for p in range(1, 4):
            url = f"{BASE_URL}/{media_type}/popular"
            params = {"api_key": TMDB_API_KEY, "page": p}
            futures.append(executor.submit(get_session().get, url, params=params, timeout=5))
        
        for future in as_completed(futures):
            try:
                r = future.result()
                popular_tmdb.extend(r.json().get('results', []))
            except:
                continue

    # Filtra apenas os que temos no banco local
    updates = [
        {'tmdb_id': i['id'], 'popularity': i['popularity']} 
        for i in popular_tmdb if i['id'] in local_ids
    ]

    if updates:
        update_func(updates)

# --- FUNÇÕES DE DETALHES (INDEXER/DB) ---

def get_movie_details(tmdb_id):
    """Busca detalhes completos de um filme - OTIMIZADA."""
    url = f"{BASE_URL}/movie/{tmdb_id}"
    params = {
        "api_key": TMDB_API_KEY, 
        "language": TMDB_LANG, 
        "append_to_response": "external_ids,images,watch/providers,release_dates",
        "include_image_language": "en,pt,null"
    }
    
    try:
        # USA SESSÃO
        r = get_session().get(url, params=params, timeout=8)
        item = r.json()
        
        logos = item.get('images', {}).get('logos', [])
        watch = item.get('watch/providers', {}).get('results', {}).get('BR', {})
        br_providers = watch.get('flatrate') or watch.get('buy') or []
        
        certification = ''
        for r in item.get('release_dates', {}).get('results', []):
            if r.get('iso_3166_1') == 'BR':
                for rd in r.get('release_dates', []):
                    cert = rd.get('certification', '')
                    if cert:
                        certification = cert
                        break
                break
        
        return {
            'tmdb_id': item.get('id'),
            'imdb_id': item.get('external_ids', {}).get('imdb_id'),
            'title': item.get('title'),
            'original_title': item.get('original_title'),
            'tagline': item.get('tagline', ''),
            'year': item.get('release_date', '0000')[:4],
            'rating': item.get('vote_average', 0.0),
            'poster': f"{IMG_POSTER}{item.get('poster_path')}" if item.get('poster_path') else '',
            'backdrop': f"{IMG_BACKDROP}{item.get('backdrop_path')}" if item.get('backdrop_path') else '',
            'synopsis': item.get('overview', ''),
            'runtime': item.get('runtime', 0),
            'popularity': item.get('popularity', 0.0),
            'genres': [g.get('name') for g in item.get('genres', [])],
            'clearlogo': f"{IMG_POSTER}{logos[0]['file_path']}" if logos else '',
            'providers': [p.get('provider_name') for p in br_providers],
            'certification': certification,
            'popularity_updated': None
        }
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro detalhes filme {tmdb_id}: {str(e)}", xbmc.LOGERROR)
        return None

def fetch_show_details(tmdb_id):
    """Busca detalhes completos de uma série - OTIMIZADA."""
    if not tmdb_id:
        return None

    url = f"{BASE_URL}/tv/{tmdb_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": TMDB_LANG,
        "append_to_response": "external_ids,images,watch/providers,content_ratings",
        "include_image_language": "en,pt,null"
    }

    try:
        response = get_session().get(url, params=params, timeout=8)
        response.raise_for_status()
        show_data = response.json()

        logos = show_data.get('images', {}).get('logos', [])
        watch = show_data.get('watch/providers', {}).get('results', {}).get('BR', {})
        br_providers = watch.get('flatrate') or watch.get('buy') or []

        certification = ''
        for r in show_data.get('content_ratings', {}).get('results', []):
            if r.get('iso_3166_1') == 'BR':
                certification = r.get('rating', '')
                break

        return {
            'tmdb_id': show_data.get('id'),
            'imdb_id': show_data.get('external_ids', {}).get('imdb_id'),
            'title': show_data.get('name'),
            'original_title': show_data.get('original_name'),
            'tagline': show_data.get('tagline', ''),
            'year': show_data.get('first_air_date', '')[:4],
            'poster': f"{IMG_POSTER}{show_data.get('poster_path')}" if show_data.get('poster_path') else '',
            'backdrop': f"{IMG_BACKDROP}{show_data.get('backdrop_path')}" if show_data.get('backdrop_path') else '',
            'fanart': f"{IMG_BACKDROP}{show_data.get('backdrop_path')}" if show_data.get('backdrop_path') else '',
            'synopsis': show_data.get('overview'),
            'popularity': show_data.get('popularity'),
            'rating': show_data.get('vote_average'),
            'certification': certification,
            'clearlogo': f"{IMG_POSTER}{logos[0]['file_path']}" if logos else '',
            'providers': [p.get('provider_name') for p in br_providers],
            'genres': [g.get('name') for g in show_data.get('genres', [])],
            'number_of_seasons': show_data.get('number_of_seasons', 0),
            'number_of_episodes': show_data.get('number_of_episodes', 0),
            'status': show_data.get('status'),
            'tagline': show_data.get('tagline'),
            'seasons_data': show_data.get('seasons', [])
        }
    except Exception as e:
        xbmc.log(f"[TMDB API ERROR] Falha ao buscar detalhes da série {tmdb_id}: {e}", xbmc.LOGERROR)
        return None

def fetch_tvshows_list(list_type, page=1):
    """Busca listas simples de séries - OTIMIZADA."""
    endpoint_map = {
        'popular': 'tv/popular',
        'top_rated': 'tv/top_rated',
        'on_the_air': 'tv/on_the_air',
        'trending': 'trending/tv/week' 
    }
    endpoint = endpoint_map.get(list_type, 'tv/popular')
    url = f"{BASE_URL}/{endpoint}"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": page}
    
    try:
        # USA SESSÃO
        response = get_session().get(url, params=params, timeout=5)
        data = response.json()
        
        normalized_shows = []
        for show in data.get('results', []):
            g_ids = show.get('genre_ids', [])
            g_names = [GENRES_MAP['tv'].get(gid, 'Desconhecido') for gid in g_ids]
            
            normalized_shows.append({
                'tmdb_id': show.get('id'),
                'title': show.get('name'),
                'original_title': show.get('original_name'),
                'year': show.get('first_air_date', '')[:4],
                'poster': f"{IMG_POSTER}{show.get('poster_path')}" if show.get('poster_path') else '',
                'backdrop': f"{IMG_BACKDROP}{show.get('backdrop_path')}" if show.get('backdrop_path') else '',
                'synopsis': show.get('overview'),
                'popularity': show.get('popularity'),
                'rating': show.get('vote_average'),
                'genres': g_names
            })
        return normalized_shows
        
    except Exception as e:
        xbmc.log(f"[TMDB API ERROR] Falha ao buscar lista {list_type}: {e}", xbmc.LOGERROR)
        return []

@lru_cache(maxsize=128)
def get_collection_art(collection_name):
    url = f"{BASE_URL}/search/collection"
    params = {"api_key": TMDB_API_KEY, "query": collection_name, "language": TMDB_LANG}

    try:
        r = get_session().get(url, params=params, timeout=3)
        results = r.json().get('results', [])
        if results:
            col      = results[0]
            poster   = col.get('poster_path')
            backdrop = col.get('backdrop_path')
            overview = col.get('overview', '')

            if not overview:
                col_id = col.get('id')
                if col_id:
                    try:
                        det = get_session().get(
                            f"{BASE_URL}/collection/{col_id}",
                            params={"api_key": TMDB_API_KEY, "language": TMDB_LANG},
                            timeout=3
                        ).json()
                        overview = det.get('overview', '')
                    except Exception:
                        pass

            return {
                'poster':   f"{IMG_BACKDROP}{poster}"   if poster   else '',
                'backdrop': f"{IMG_BACKDROP}{backdrop}" if backdrop else '',
                'overview': overview,
            }
    except Exception:
        pass
    return None

def fetch_popular_movies_pages(pages=5):
    """Busca páginas populares - OTIMIZADA."""
    all_movies = []
    
    # OTIMIZAÇÃO: Busca paralela
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for page in range(1, pages + 1):
            url = f"{BASE_URL}/movie/popular"
            params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": page}
            futures.append(executor.submit(get_session().get, url, params=params, timeout=5))
        
        for future in as_completed(futures):
            try:
                r = future.result()
                data = r.json().get('results', [])
                for item in data:
                    all_movies.append({
                        'tmdb_id': item.get('id'),
                        'title': item.get('title'),
                        'original_title': item.get('original_title'),
                        'year': item.get('release_date', '0000')[:4],
                        'rating': item.get('vote_average'),
                        'poster': f"{IMG_POSTER}{item.get('poster_path')}",
                        'backdrop': f"{IMG_BACKDROP}{item.get('backdrop_path')}",
                        'synopsis': item.get('overview'),
                        'popularity': item.get('popularity'),
                        'popularity_updated': None
                    })
            except:
                continue
                
    return all_movies

def get_tvshow_seasons(tmdb_id):
    """Busca temporadas de uma série - OTIMIZADA."""
    if not tmdb_id:
        return []
    
    url = f"{BASE_URL}/tv/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG}
    
    try:
        response = get_session().get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        seasons = data.get('seasons', [])
        
        formatted_seasons = []
        for season in seasons:
            formatted_seasons.append({
                'season_number': season.get('season_number', 0),
                'name': season.get('name', ''),
                'overview': season.get('overview', ''),
                'poster_path': season.get('poster_path', ''),
                'air_date': season.get('air_date', ''),
                'episode_count': season.get('episode_count', 0),
                'vote_average': season.get('vote_average', 0.0)
            })
        
        return formatted_seasons
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro ao buscar temporadas {tmdb_id}: {e}", xbmc.LOGERROR)
        return []

def get_season_episodes(tmdb_id, season_number):
    """Busca episódios de uma temporada - OTIMIZADA."""
    if not tmdb_id or season_number is None:
        return []
    
    url = f"{BASE_URL}/tv/{tmdb_id}/season/{season_number}"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG}
    
    try:
        response = get_session().get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        episodes = data.get('episodes', [])
        
        formatted_episodes = []
        for episode in episodes:
            formatted_episodes.append({
                'episode_number': episode.get('episode_number', 0),
                'name': episode.get('name', ''),
                'overview': episode.get('overview', ''),
                'still_path': episode.get('still_path', ''),
                'air_date': episode.get('air_date', ''),
                'vote_average': episode.get('vote_average', 0.0),
                'runtime': episode.get('runtime', 0)
            })
        
        return formatted_episodes
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro ao buscar episódios {tmdb_id} S{season_number}: {e}", xbmc.LOGERROR)
        return []
    
def fetch_movies_by_keywords(keyword_ids, genres=None, page=1):
    """
    Busca filmes por keywords (COM INFO DE PAGINAÇÃO)
    """
    if not keyword_ids:
        return []
    
    cache_key = f"keywords_movies_{','.join(map(str, keyword_ids))}_{','.join(map(str, genres or []))}_{page}"
    cached = db.get_tmdb_cache(cache_key, hours=168)
    if cached:
        return cached
    
    url = f"{BASE_URL}/discover/movie"
    
    params = {
        "api_key": TMDB_API_KEY,
        "language": TMDB_LANG,
        "page": page,
        "sort_by": "popularity.desc",
        "vote_count.gte": 100,
        "with_keywords": "|".join(map(str, keyword_ids)),
        "include_adult": False
    }
    
    if genres:
        params["with_genres"] = ",".join(map(str, genres))
    
    try:
        response = get_session().get(url, params=params, timeout=5)
        json_data = response.json()  # ✅ Pega o JSON completo
        data = json_data.get('results', [])
        
        # ✅ PEGA INFO DE PÁGINAS
        total_pages = json_data.get('total_pages', 1)
        
        extra_results = _fetch_extras_batch(data, 'movie')
        
        results = []
        for item, extra in zip(data, extra_results):
            normalized = _normalize_item(item, 'movie', extra)
            results.append(normalized)
        
        # ✅ ADICIONA INFO DE PÁGINAS AOS RESULTADOS
        # Hack: adiciona como propriedade do primeiro item
        if results:
            results[0]['_has_next_page'] = (page < total_pages)
            db.save_tmdb_cache(cache_key, results)
        
        return results
        
    except Exception as e:
        xbmc.log(f"[TMDB] Erro busca keywords: {e}", xbmc.LOGERROR)
        return []

def fetch_tvshows_by_keywords(keyword_ids, genres=None, page=1):
    """
    Busca séries por keywords (COM INFO DE PAGINAÇÃO)
    """
    if not keyword_ids:
        return []
    
    cache_key = f"keywords_tv_{','.join(map(str, keyword_ids))}_{','.join(map(str, genres or []))}_{page}"
    cached = db.get_tmdb_cache(cache_key, hours=168)
    if cached:
        return cached
    
    url = f"{BASE_URL}/discover/tv"
    
    params = {
        "api_key": TMDB_API_KEY,
        "language": TMDB_LANG,
        "page": page,
        "sort_by": "popularity.desc",
        "vote_count.gte": 50,
        "with_keywords": "|".join(map(str, keyword_ids)),
        "include_adult": False
    }
    
    if genres:
        params["with_genres"] = ",".join(map(str, genres))
    
    try:
        response = get_session().get(url, params=params, timeout=5)
        json_data = response.json()
        data = json_data.get('results', [])
        
        # ✅ PEGA INFO DE PÁGINAS
        total_pages = json_data.get('total_pages', 1)
        
        extra_results = _fetch_extras_batch(data, 'tv')
        
        results = []
        for item, extra in zip(data, extra_results):
            normalized = _normalize_item(item, 'tv', extra)
            results.append(normalized)
        
        # ✅ ADICIONA INFO DE PÁGINAS
        if results:
            results[0]['_has_next_page'] = (page < total_pages)
            db.save_tmdb_cache(cache_key, results)
        
        return results
        
    except Exception as e:
        xbmc.log(f"[TMDB] Erro busca keywords séries: {e}", xbmc.LOGERROR)
        return []
    
    

def search_people(query, page=1):
    try:
        url = f"{BASE_URL}/search/person"
        params = {
            'query': query,
            'page': page,
            'language': TMDB_LANG,
            'api_key': TMDB_API_KEY,
        }
        data = get_session().get(url, params=params, timeout=5).json()

        results = data.get('results', [])[:10]
        people = []

        for p in results:
            raw_profile = p.get('profile_path') or ''
            profile_url = f"https://image.tmdb.org/t/p/w185{raw_profile}" if raw_profile else ''

            known_for_raw = p.get('known_for', [])
            known_titles = ', '.join(
                kf.get('title') or kf.get('name') or ''
                for kf in known_for_raw[:3]
                if kf.get('title') or kf.get('name')
            )

            people.append({
                'id': p.get('id'),
                'name': p.get('name', ''),
                'known_for_department': p.get('known_for_department', ''),
                'profile_path_full': profile_url,
                'known_for_titles': known_titles,
                'popularity': p.get('popularity', 0),
            })

        return people

    except Exception as e:
        xbmc.log(f"[TMDB] search_people error: {e}", xbmc.LOGERROR)
        return []


def fetch_person_details(tmdb_person_id):
    """
    Busca bio completa, foto, filmografia e premiações do ator.
 
    Novidades vs versão anterior:
    - Adiciona `external_ids` no append_to_response → imdb_id do ator
    - Calcula `age` a partir de birthday
    - Busca `awards` via OMDB (requer OMDB_API_KEY na config do addon)
    - Extrai `oscar_count` e `globe_count` do texto de awards para os chips
    - Formata `birthday_br` no padrão dd/mm/aaaa para exibição
    """
    import re
    from datetime import date as _date
 
    try:
        url = f"{BASE_URL}/person/{tmdb_person_id}"
        params = {
            'api_key': TMDB_API_KEY,
            'language': TMDB_LANG,
            'append_to_response': 'combined_credits,images,external_ids',
        }
        data = get_session().get(url, params=params, timeout=5).json()
 
        if not data:
            return {}
 
        # ── Foto em alta resolução ────────────────────────────────────────
        raw_profile = data.get('profile_path') or ''
        profile_url = f"https://image.tmdb.org/t/p/h632{raw_profile}" if raw_profile else ''
 
        profiles = (data.get('images') or {}).get('profiles', [])
        if profiles:
            best = sorted(profiles, key=lambda x: x.get('vote_count', 0), reverse=True)
            best_path = best[0].get('file_path', '')
            if best_path:
                profile_url = f"https://image.tmdb.org/t/p/h632{best_path}"
 
        # ── Gênero ───────────────────────────────────────────────────────
        gender_map = {1: 'Feminino', 2: 'Masculino', 3: 'Não-binário'}
        gender_label = gender_map.get(data.get('gender', 0), '')
 
        # ── Idade calculada ──────────────────────────────────────────────
        birthday_raw = data.get('birthday') or ''
        deathday_raw = data.get('deathday') or ''
        age = ''
        birthday_br = birthday_raw  # fallback: ISO
 
        if birthday_raw:
            try:
                parts = birthday_raw.split('-')
                if len(parts) == 3:
                    bday = _date(int(parts[0]), int(parts[1]), int(parts[2]))
                    birthday_br = f"{parts[2]}/{parts[1]}/{parts[0]}"
 
                    if deathday_raw:
                        ref_parts = deathday_raw.split('-')
                        ref = _date(int(ref_parts[0]), int(ref_parts[1]), int(ref_parts[2]))
                    else:
                        ref = _date.today()
 
                    years = ref.year - bday.year - (
                        (ref.month, ref.day) < (bday.month, bday.day)
                    )
                    age = str(years)
            except Exception:
                pass
 
        # ── IMDb ID do ator (via external_ids) ──────────────────────────
        imdb_person_id = (data.get('external_ids') or {}).get('imdb_id', '')
 
        # ── Premiações via OMDB ──────────────────────────────────────────
        # OMDB retorna campo "Awards" como string legível:
        # "Won 2 Oscars. 14 wins & 37 nominations total."
        # Requer configuração: addon → OMDB API Key
        awards_raw = ''
        oscar_count = '0'
        globe_count = '0'
        wins_total = '0'
        noms_total = '0'
 
        if imdb_person_id:
            try:
                omdb_key = ADDON.getSetting('omdb_api_key') or ''
                if omdb_key:
                    omdb_url = f"https://www.omdbapi.com/?apikey={omdb_key}&i={imdb_person_id}"
                    omdb_res = get_session().get(omdb_url, timeout=4).json()
                    awards_raw = omdb_res.get('Awards') or ''
 
                    if awards_raw and awards_raw.lower() != 'n/a':
                        # "Won 2 Oscars." → oscar_count = "2"
                        m = re.search(r'Won\s+(\d+)\s+Oscar', awards_raw, re.IGNORECASE)
                        if m:
                            oscar_count = m.group(1)
 
                        # "Won 2 Golden Globe" → globe_count = "2"
                        m = re.search(r'Won\s+(\d+)\s+Golden Globe', awards_raw, re.IGNORECASE)
                        if m:
                            globe_count = m.group(1)
 
                        # "14 wins" → wins_total = "14"
                        m = re.search(r'(\d+)\s+win', awards_raw, re.IGNORECASE)
                        if m:
                            wins_total = m.group(1)
 
                        # "37 nominations" → noms_total = "37"
                        m = re.search(r'(\d+)\s+nomination', awards_raw, re.IGNORECASE)
                        if m:
                            noms_total = m.group(1)
            except Exception as e:
                xbmc.log(f"[TMDB] OMDB awards error: {e}", xbmc.LOGWARNING)
 
        # ── Filmografia ──────────────────────────────────────────────────
        combined = data.get('combined_credits', {})
        cast_credits = sorted(
            [c for c in combined.get('cast', []) if c.get('vote_count', 0) > 10],
            key=lambda x: x.get('popularity', 0),
            reverse=True
        )
 
        credits = []
        seen_ids = set()
        for c in cast_credits[:40]:
            tid = c.get('id')
            if not tid or tid in seen_ids:
                continue
            seen_ids.add(tid)
 
            raw_poster = c.get('poster_path') or ''
            poster_url = f"https://image.tmdb.org/t/p/w342{raw_poster}" if raw_poster else ''
 
            media_type = c.get('media_type', 'movie')
            if media_type == 'tv':
                media_type = 'tvshow'
 
            release = c.get('release_date') or c.get('first_air_date') or ''
 
            credits.append({
                'tmdb_id':      tid,
                'title':        c.get('title') or c.get('name') or '',
                'year':         release[:4] if release else '',
                'media_type':   media_type,
                'poster':       poster_url,
                'character':    c.get('character', ''),
                'vote_average': c.get('vote_average', 0),
            })
 
        return {
            # Campos existentes (mantidos)
            'name':             data.get('name', ''),
            'biography':        data.get('biography', ''),
            'birthday':         birthday_raw,
            'deathday':         deathday_raw,
            'birthplace':       data.get('place_of_birth') or '',
            'gender_label':     gender_label,
            'known_for':        data.get('known_for_department', ''),
            'also_known_as':    data.get('also_known_as', []),
            'profile_path_full': profile_url,
            'credits_count':    len(credits),
            'credits':          credits,
 
            # Campos novos
            'imdb_person_id':   imdb_person_id,
            'birthday_br':      birthday_br,      # "18/12/1963"
            'age':              age,              # "61"
            'awards_raw':       awards_raw,       # string completa OMDB
            'oscar_count':      oscar_count,      # "2"
            'globe_count':      globe_count,      # "2"
            'wins_total':       wins_total,       # "14"
            'noms_total':       noms_total,       # "37"
        }
 
    except Exception as e:
        xbmc.log(f"[TMDB] fetch_person_details error: {e}", xbmc.LOGERROR)
        return {}
    
    
def get_full_item_details(tmdb_id, media_type):
    """
    Busca detalhes completos de um item (fora do catálogo local) para exibir
    no CineroomDetailsWindow. Reutiliza _fetch_tmdb_extra + campos básicos.
    """
    endpoint = 'movie' if media_type == 'movie' else 'tv'
    url      = f"{BASE_URL}/{endpoint}/{tmdb_id}"

    append = "external_ids,images,watch/providers,credits"
    append += ",release_dates" if media_type == 'movie' else ",content_ratings"

    params = {
        "api_key":            TMDB_API_KEY,
        "language":           TMDB_LANG,
        "append_to_response": append,
        "include_image_language": "en,pt,null",
    }

    try:
        res = get_session().get(url, params=params, timeout=8).json()

        # Poster / backdrop
        poster   = f"{IMG_POSTER}{res['poster_path']}"   if res.get('poster_path')   else ''
        backdrop = f"{IMG_BACKDROP}{res['backdrop_path']}" if res.get('backdrop_path') else ''

        # Clearlogo
        logos    = res.get('images', {}).get('logos', [])
        clearlogo = f"{IMG_POSTER}{logos[0]['file_path']}" if logos else ''

        # Providers BR
        watch       = res.get('watch/providers', {}).get('results', {}).get('BR', {})
        br_providers = watch.get('flatrate') or watch.get('buy') or []
        providers   = [p.get('provider_name') for p in br_providers]

        # Certification BR
        certification = ''
        if media_type == 'movie':
            for r in res.get('release_dates', {}).get('results', []):
                if r.get('iso_3166_1') == 'BR':
                    for rd in r.get('release_dates', []):
                        cert = rd.get('certification', '')
                        if cert:
                            certification = cert
                            break
                    break
        else:
            for r in res.get('content_ratings', {}).get('results', []):
                if r.get('iso_3166_1') == 'BR':
                    certification = r.get('rating', '')
                    break

        # Gêneros
        g_map   = GENRES_MAP.get('movie' if media_type == 'movie' else 'tv', {})
        genres  = [g_map.get(g['id'], g.get('name', '')) for g in res.get('genres', [])]

        # Cast (top 8)
        cast_raw = res.get('credits', {}).get('cast', [])[:8]
        cast = [
            {
                'name':           c.get('name', ''),
                'character':      c.get('character', ''),
                'tmdb_person_id': c.get('id'),
                'profile':        f"https://image.tmdb.org/t/p/w185{c['profile_path']}"
                                  if c.get('profile_path') else '',
            }
            for c in cast_raw
        ]

        title = res.get('title') if media_type == 'movie' else res.get('name', '')
        year  = (res.get('release_date') or res.get('first_air_date') or '')[:4]

        return {
            'title':         title,
            'synopsis':      res.get('overview', ''),
            'poster':        poster,
            'backdrop':      backdrop,
            'fanart':        backdrop,
            'clearlogo':     clearlogo,
            'providers':     providers,
            'certification': certification,
            'genres':        genres,
            'year':          year,
            'rating':        res.get('vote_average', 0.0),
            'runtime':       res.get('runtime', 0) if media_type == 'movie' else 0,
            'cast':          cast,
            'imdb_id':       res.get('external_ids', {}).get('imdb_id', ''),
            # Sinaliza que não tem stream local — o details pode mostrar badge
            'streams':       [],
        }

    except Exception as e:
        xbmc.log(f"[TMDB] get_full_item_details({tmdb_id}): {e}", xbmc.LOGERROR)
        return None