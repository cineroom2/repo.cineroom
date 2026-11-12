# -*- coding: utf-8 -*-
import sys
import xbmc
from urllib.parse import parse_qsl

# ── Imports mínimos no topo — APENAS o que é necessário antes de ler a action ──
# xbmcaddon.Addon() é instanciado UMA vez em context.py — não repetir aqui.
# ICON_PATH e ADDON_PATH foram removidos: constants.py não depende mais de Addon().

# Sets de actions — custo zero, são apenas literais Python
_HISTORY_ACTIONS = {
    'show_history_menu',
    'list_history_all',
    'list_history_movies',
    'list_history_tvshows',
    'list_history_in_progress',
    'list_history_liked',
    'list_history_liked_movies',
    'list_history_liked_tvshows',
    'list_history_disliked',
    'list_history_disliked_movies',
    'list_history_disliked_tvshows',
    'list_history_movies_in_progress',
    'list_history_tvshows_in_progress',
    'mark_tvshow_watched_dialog',
    'mark_episode_watched',
    'mark_movie_watched',
    'rating_remove',
    'history_remove',
    'history_unwatch',
    'backup_menu',
    'backup_export',
    'backup_import',
    'backup_configure',
    'backup_toggle_auto',
}

_RECOMMENDATIONS_ACTIONS = {
    'show_recommendations_menu',
    'list_recommendations_movies',
    'list_recommendations_tvshows',
}

_WATCHLIST_ACTIONS = {
    'show_watchlist_menu',
    'list_watchlist_all',
    'list_watchlist_movies',
    'list_watchlist_tvshows',
    'watchlist_remove',
    'add_to_watchlist',
    'remove_from_watchlist',
}

_MENU_ACTIONS = {
    'movies_menu',
    'tvshows_menu',
    'tools_menu',
    'account_menu',
    'movies_explore_menu',
    'tvshows_explore_menu',
}

_FAVORITES_ACTIONS = {
    'add_to_favorites',
    'remove_from_favorites',
    'favorites_menu',
    'favorites_movies',
    'favorites_tvshows',
    'favorites_actors',
    'remove_actor_from_favorites',
}

# ── Migração de settings ───────────────────────────────────────────────────────
_details_migrated = False

def _migrate_details_settings():
    global _details_migrated
    if _details_migrated:
        return
    # Lazy import: só acessa ADDON quando realmente necessário
    from .context import ADDON
    if ADDON.getSetting('migrated_details_v3') == '1':
        _details_migrated = True
        return
    try:
        ADDON.setSetting('movie.enable_details', 'false')
        ADDON.setSetting('tvshow.enable_details', 'false')
        ADDON.setSetting('view_mode_enabled', 'true')
        ADDON.setSetting('view_mode', 'infowall')
        ADDON.setSetting('ui.details_style', 'Lite')
        ADDON.setSetting('lightweight_mode', 'false')
        ADDON.setSetting('menu_view_mode', 'list')
        ADDON.setSetting('playback.preferred_quality', '4K')
    except Exception as e:
        xbmc.log(f'[Cineroom] _migrate_details_settings erro: {e}', xbmc.LOGWARNING)
    ADDON.setSetting('migrated_details_v3', '1')
    _details_migrated = True


# ── Router principal ───────────────────────────────────────────────────────────

def router():
    # context importado aqui, não no topo do módulo,
    # para não pagar o custo em imports parciais feitos pelo próprio Kodi
    from .context import ADDON, end_dir, get_module, get_profile_manager

    params = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 and sys.argv[2] else {}
    action = params.get('action', '')

    _migrate_details_settings()

    # ── ROOT ──────────────────────────────────────────────────────────────────
    if not action:
        nav   = get_module('navigation')
        const = get_module('constants')
        pm    = get_profile_manager()

        if pm and pm.should_show_profile_selector():
            profile = pm.show_profile_selector()
            if not profile:
                nav.show_main_menu(const.MAIN_MENU)
            return end_dir(True)

        _build_main_menu(nav, const, pm)
        end_dir(True)


        # Pós-render em background — não bloqueia o menu
        import threading
        def _post_render():
            _auto_heal_db()
            try:
                from resources.lib.notification import show_notifications_panel
                actions = show_notifications_panel()
                for act in actions:
                    xbmc.executebuiltin(
                        f'RunPlugin(plugin://plugin.video.cineroom.lite/?action={act})'
                    )
            except Exception as e:
                xbmc.log(f'[Cineroom] Erro na notificação: {e}', xbmc.LOGWARNING)
        threading.Thread(target=_post_render, daemon=True).start()
        return

    # ── Noop ──────────────────────────────────────────────────────────────────
    if action == 'noop':
        return end_dir(True)

    # ── Troca de perfil ───────────────────────────────────────────────────────
    if action.startswith('profile_'):
        from .handlers.profiles import handle_profiles
        result   = handle_profiles(action, params)
        addon_id = ADDON.getAddonInfo('id')
        xbmc.executebuiltin(f'Container.Update(plugin://{addon_id}/,replace)')
        return end_dir(result)

    # ── Menus (filmes, séries, conta, ferramentas, explorar) ──────────────────
    # Verificado ANTES de history/watchlist para não pagar custo de sets maiores
    if action in _MENU_ACTIONS:
        from .handlers.menu import handle_menu
        handle_menu(action, params)
        return

    # ── Histórico, Avaliações e Backup ────────────────────────────────────────
    if action in _HISTORY_ACTIONS:
        if action in ('backup_menu', 'backup_export', 'backup_import',
                      'backup_configure', 'backup_toggle_auto'):
            from resources.lib.history_backup import (
                show_backup_menu, export_history, import_history,
                configure_backup_folder, toggle_auto_backup,
            )
            {
                'backup_menu':        show_backup_menu,
                'backup_export':      export_history,
                'backup_import':      import_history,
                'backup_configure':   configure_backup_folder,
                'backup_toggle_auto': toggle_auto_backup,
            }[action]()
            return end_dir(True)

        if action == 'mark_tvshow_watched_dialog':
            from resources.lib.tvshows import mark_tvshow_watched_dialog
            tvshow_tmdb_id = int(
                params.get('tvshow_tmdb_id') or params.get('tmdb_id') or 0
            )
            mark_tvshow_watched_dialog(tvshow_tmdb_id)
            return end_dir(True)

        if action == 'mark_episode_watched':
            from resources.lib.history import (
                mark_episode_watched, mark_episode_unwatched, _get_active_profile_id
            )
            from resources.lib.utils import invalidate_watched_cache
            tmdb_id    = int(params.get('tvshow_tmdb_id', 0))
            season     = int(params.get('season', 0))
            episode    = int(params.get('episode', 0))
            profile_id = _get_active_profile_id()
            if params.get('watched') == '1':
                mark_episode_watched(tmdb_id, season, episode, profile_id)
            else:
                mark_episode_unwatched(tmdb_id, season, episode, profile_id)
            invalidate_watched_cache()
            xbmc.sleep(100)
            xbmc.executebuiltin('Container.Refresh()')
            return

        if action == 'mark_movie_watched':
            from resources.lib.history import (
                mark_movie_watched, mark_movie_unwatched, _get_active_profile_id
            )
            from resources.lib.utils import invalidate_watched_cache
            tmdb_id    = int(params.get('tmdb_id', 0))
            profile_id = _get_active_profile_id()
            if params.get('watched') == '1':
                mark_movie_watched(tmdb_id, profile_id=profile_id)
            else:
                mark_movie_unwatched(tmdb_id, profile_id=profile_id)
            invalidate_watched_cache()
            xbmc.sleep(300)
            xbmc.executebuiltin('Container.Refresh()')
            return

        from resources.lib import history as hist_mod
        handler = getattr(hist_mod, action, None)
        if handler:
            if action in ('history_remove', 'history_unwatch', 'rating_remove'):
                handler(params.get('tmdb_id'), params.get('media_type', 'movie'))
            else:
                handler()
            return end_dir(True)
        return end_dir(False)

    # ── Recomendações ─────────────────────────────────────────────────────────
    if action in _RECOMMENDATIONS_ACTIONS:
        from resources.lib import recommendations as rec_mod
        handler = getattr(rec_mod, action, None)
        if handler:
            handler()
            return end_dir(True)
        return end_dir(False)

    # ── Watchlist ─────────────────────────────────────────────────────────────
    if action in _WATCHLIST_ACTIONS:
        from resources.lib import watchlist as wl_mod
        if action == 'add_to_watchlist':
            import json as _json
            _meta = None
            try:
                _meta = _json.loads(params.get('meta', '{}')) or None
            except Exception:
                pass
            wl_mod.add_to_watchlist(
                int(params.get('tmdb_id', 0)),
                params.get('media_type', 'movie'),
                meta=_meta,
            )
        if action == 'remove_from_watchlist':
            wl_mod.remove_from_watchlist(
                int(params.get('tmdb_id', 0)),
                params.get('media_type', 'movie'),
            )
            xbmc.executebuiltin('Container.Refresh')
            return end_dir(True)
        if action == 'watchlist_remove':
            wl_mod.watchlist_remove(
                params.get('tmdb_id'), params.get('media_type', 'movie')
            )
            return end_dir(True)
        handler = getattr(wl_mod, action, None)
        if handler:
            handler()
            return end_dir(True)
        return end_dir(False)

    # ── Favoritos ─────────────────────────────────────────────────────────────
    if action in _FAVORITES_ACTIONS:
        from .handlers.favorites import handle_favorites
        return end_dir(handle_favorites(action, params))

    if action == 'list_actor_titles':
        from .handlers.favorites import handle_list_actor_titles
        return end_dir(handle_list_actor_titles(params))

    # ── Routing genérico ──────────────────────────────────────────────────────
    from .actions import handle_generic_action
    if handle_generic_action(action, params):
        return

    # ── Detalhes ──────────────────────────────────────────────────────────────
    if action == 'show_details':
        if params.get('track') == '1':
            try:
                import json as _json
                from resources.lib.trending_tracker import queue_track
                _data = _json.loads(params.get('data', '{}'))
                queue_track(
                    tmdb_id=_data.get('tmdb_id'),
                    imdb_id=_data.get('imdb_id'),
                    content_type=_data.get('media_type', 'movie'),
                )
            except Exception:
                pass
        from .handlers.details import handle_show_details
        return end_dir(handle_show_details(params))

    # ── TV ────────────────────────────────────────────────────────────────────
    if action == 'list_seasons':
        if params.get('track') == '1':
            try:
                from resources.lib.trending_tracker import queue_track
                queue_track(
                    tmdb_id=params.get('tvshow_tmdb_id'),
                    content_type='tv',
                )
            except Exception:
                pass
        from .handlers.tv import handle_list_seasons
        return end_dir(handle_list_seasons(params))

    if action == 'list_episodes':
        from .handlers.tv import handle_list_episodes
        return end_dir(handle_list_episodes(params))

    # ── Navegação / Busca / Playback ──────────────────────────────────────────
    if action in ('search', 'find_sources', 'play_item_direct', 'find_and_play_episode'):
        if action == 'find_sources' and params.get('track') == '1':
            try:
                from resources.lib.trending_tracker import queue_track
                queue_track(
                    tmdb_id=params.get('tmdb_id'),
                    imdb_id=params.get('imdb_id', ''),
                    content_type=params.get('media_type', 'movie'),
                )
            except Exception:
                pass
        from .handlers.navigation import handle_navigation
        return end_dir(handle_navigation(action, params))

    # ── Trakt ─────────────────────────────────────────────────────────────────
    if action.startswith('trakt_'):
        from .handlers.trakt import handle_trakt
        return end_dir(handle_trakt(action, params))

    # ── Biblioteca ────────────────────────────────────────────────────────────
    if action.startswith('library_'):
        from .handlers.library import handle_library
        return end_dir(handle_library(action, params))

    # ── Sistema ───────────────────────────────────────────────────────────────
    if action in ('run_indexer', 'show_donation', 'open_donation', 'open_settings',
                  'show_changelog', 'open_provider_manager', 'open_burst_settings'):
        from .handlers.system import handle_system
        return end_dir(handle_system(action, params))

    # ── Ator ──────────────────────────────────────────────────────────────────
    if action == 'show_person':
        try:
            from resources.lib.dialog.extras_dialog import show_actor_bio
            show_actor_bio({
                'tmdb_person_id': params.get('person_id'),
                'name':           params.get('name', ''),
                'profile':        params.get('photo', ''),
            })
        except Exception as e:
            xbmc.log(f'[Cineroom] Erro ao abrir ator: {e}', xbmc.LOGERROR)
        return end_dir(True)

    return end_dir(False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_main_menu(nav, const, pm):
    from .context import ADDON
    current_profile = pm.get_current_profile() if pm else None
    is_kids         = current_profile.get('is_kids', False) if current_profile else False

    base_menu      = const.MAIN_MENU_KIDS if is_kids else const.MAIN_MENU
    base_menu_list = list(base_menu)

    if not is_kids:
        trakt_token = ADDON.getSetting('trakt_access_token')
        if trakt_token:
            trakt_item = getattr(const, 'MAIN_MENU_TRAKT_ITEM', None)
            if trakt_item:
                base_menu_list = base_menu_list + [trakt_item]

    nav.show_main_menu(base_menu_list)


_db_healed = False

def _auto_heal_db():
    global _db_healed
    if _db_healed:
        return
    try:
        from .context import get_module
        db = get_module('db')
        if db and not db.get_all_movie_ids_set():
            indexer = get_module('indexer')
            if indexer:
                indexer.run_indexer()
        _db_healed = True
    except Exception as e:
        xbmc.log(f'[Cineroom] Erro na checagem de banco: {e}', xbmc.LOGERROR)


def _invalidate_all_settings_caches():
    """Chamado após fechar a tela de settings."""
    try:
        from resources.lib.utils import (
            invalidate_res_cache,
            invalidate_watched_cache,
            invalidate_library_cache,
            invalidate_favorites_cache,
        )
        invalidate_res_cache()
        invalidate_watched_cache()
        invalidate_library_cache()
        invalidate_favorites_cache()
    except Exception as e:
        xbmc.log(f'[Cineroom] _invalidate_all_settings_caches erro: {e}', xbmc.LOGWARNING)

    try:
        from resources.lib.utils import _SETTINGS
        _SETTINGS._cache.clear()
        _SETTINGS._last_check = 0.0
    except Exception as e:
        xbmc.log(f'[Cineroom] Erro ao limpar SettingsCache: {e}', xbmc.LOGWARNING)

    try:
        import resources.lib.utils as _utils_mod
        _utils_mod._trakt_active = None
        _utils_mod._RES_CACHE    = None
    except Exception:
        pass

    try:
        from resources.lib.router.context import clear_runtime_caches
        clear_runtime_caches()
    except Exception:
        pass


# ── Entrypoint ────────────────────────────────────────────────────────────────

def _safe_init_scrobbler():
    """Scrobbler em background — nunca bloqueia o menu."""
    try:
        from .context import init_scrobbler
        init_scrobbler()
    except Exception as e:
        xbmc.log(f'[Cineroom] Scrobbler erro: {e}', xbmc.LOGWARNING)


def run():
    try:
        # Scrobbler assíncrono: não bloqueia mais o carregamento do menu
        import threading
        threading.Thread(target=_safe_init_scrobbler, daemon=True).start()

        router()
    except Exception as e:
        xbmc.log(f'[Cineroom] ERRO CRÍTICO: {e}', xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        # end_dir precisa ser importado aqui pois context pode não ter sido importado ainda
        try:
            from .context import end_dir
            end_dir(False)
        except Exception:
            pass