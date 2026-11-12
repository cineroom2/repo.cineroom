# -*- coding: utf-8 -*-

# constants.py
import os

# Sem xbmcaddon.Addon() aqui — usa path relativo ao __file__
_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICON_PATH = os.path.join(_HERE, 'resources', 'medias', 'icons')


# === MENU PERFIS ===
PROFILES_MENU = [
    {'title': 'Selecionar Perfil', 'action': 'profile_select', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Gerenciar Perfis',  'action': 'profile_manage', 'icon': os.path.join(ICON_PATH, 'settings.png')},
    {'title': 'Criar Novo Perfil', 'action': 'profile_create', 'icon': os.path.join(ICON_PATH, 'search.png')},
]

# ============================================================
# MENU PRINCIPAL
# ============================================================
MAIN_MENU = [
    {
        'title': 'Pesquisar',
        'action': 'search',
        'icon': os.path.join(ICON_PATH, 'pesquisar.png'),
        'plot': 'Pesquisar filmes e series por titulo.'
    },
    {
        'title': 'Filmes',
        'action': 'movies_menu',
        'icon': os.path.join(ICON_PATH, 'filmes.png'),
        'plot': 'Filmes do catalogo local.'
    },
    {
        'title': 'Series',
        'action': 'tvshows_menu',
        'icon': os.path.join(ICON_PATH, 'series.png'),
        'plot': 'Series do catalogo local.'
    },
    {
        'title': 'Watchlist',
        'action': 'show_watchlist_menu',
        'icon': os.path.join(ICON_PATH, 'em_andamento.png'),
        'plot': 'Filmes e séries que você quer assistir.',
    },
    {
        'title': 'Minha Lista',
        'action': 'favorites_menu',
        'icon': os.path.join(ICON_PATH, 'minha_lista.png'),
        'plot': 'Seus favoritos salvos localmente.',
    },
    {
        'title': '[COLOR cyan]Minha Conta[/COLOR]',
        'action': 'account_menu',
        'icon': 'DefaultUser.png',  
        'plot': 'Perfis, Trakt e configurações.'
    },
    {
        'title': '[COLOR cyan]Ajustes[/COLOR]',
        'action': 'open_settings',
        'icon': 'DefaultAddonProgram.png',
        'plot': 'Ajustar preferências do addon.',
    },
    {    'title': '[COLOR cyan]Fontes[/COLOR]',         
         'action': 'open_burst_settings', 
         'icon': 'DefaultAddon.png',  
         'plot': 'Abrir configurações do Burst.',
    },

]

# === MENU PRINCIPAL INFANTIL ===
MAIN_MENU_KIDS = [
    {
        'title': 'Pesquisar',
        'action': 'search',
        'icon': os.path.join(ICON_PATH, 'kids_search.png'),
        'plot': 'Pesquisar filmes e series por titulo.'
    },
    {
        'title': 'Filmes',
        'action': 'movies_menu',
        'icon': os.path.join(ICON_PATH, 'kids_movie.png'),
        'plot': 'Filmes infantis e familiares.'
    },
    {
        'title': 'Series',
        'action': 'tvshows_menu',
        'icon': os.path.join(ICON_PATH, 'kids_tv.png'),
        'plot': 'Series infantis e desenhos animados.'
    },
    {
        'title': 'Minha Lista',
        'action': 'favorites_menu',
        'icon': os.path.join(ICON_PATH, 'kids_list.png'),
        'plot': 'Seus favoritos e itens salvos.'
    },
    {
        'title': 'Minha Conta',
        'action': 'account_menu',
        'icon': os.path.join(ICON_PATH, 'minha_conta.png'),
        'plot': 'Perfis e configurações.',
    },
]

# ============================================================
# MENU CONTA
# ============================================================
ACCOUNT_MENU = [
    {
        'title': 'Perfis',
        'action': 'profile_select',
        'icon': os.path.join(ICON_PATH, 'perfil.png'),
        'plot': 'Trocar ou gerenciar perfis.',
    },
    {
        'title': 'Trakt',
        'action': 'trakt_main_menu',
        'icon': os.path.join(ICON_PATH, 'trakt_menu.png'),
        'plot': 'Sincronizar histórico, watchlist e coleção com o Trakt.',
    },
    {
        'title': 'Histórico',
        'action': 'show_history_menu',
        'icon': os.path.join(ICON_PATH, 'historico.png'),
        'plot': 'Tudo que você já assistiu, com progresso salvo.',
    },
    {
        'title': '[COLOR orange]Ferramentas[/COLOR]',
        'action': 'tools_menu',
        'icon': os.path.join(ICON_PATH, 'ferramentas.png'),
        'plot': 'Configuracoes, manutencao e informacoes do addon.',
    },
]

# ============================================================
# FERRAMENTAS
# ============================================================

TOOLS_MENU = [
    {'title': 'Changelog',                'action': 'show_changelog',      'icon': 'DefaultAddon.png',},
    {'title': 'Biblioteca',               'action': 'library_menu',        'icon': 'DefaultFolder.png', 'plot': 'Conteúdo salvo e organizado localmente.',},
    {'title': 'Atualizar Banco de Dados', 'action': 'run_indexer',         'icon': 'DefaultAddon.png',  'plot': 'Atualiza e reorganiza o banco de dados local.',},
]

# ============================================================
# MENU FILMES
# ============================================================
MOVIES_MENU = [
    {'title': 'Mais Buscados', 'action': 'list_most_searched_movies',        'icon': os.path.join(ICON_PATH, 'most_searched.png'), 'plot': 'Filmes mais buscados no momento.'},
    {'title': 'Em Alta',       'action': 'list_trending_movies',             'icon': os.path.join(ICON_PATH, 'trending.png'), 'plot': 'Filmes em alta no momento, com mais acessos recentes.'},
    {'title': 'Populares',     'action': 'list_movies_by_popularity',        'icon': os.path.join(ICON_PATH, 'most_popular.png'), 'plot': 'Filmes mais populares do catalogo local.'},
    {'title': 'Recentes',      'action': 'list_recently_added_movies',       'icon': os.path.join(ICON_PATH, 'recent.png'), 'plot': 'Filmes adicionados recentemente ao catalogo local.'},
    {'title': 'Em Andamento',  'action': 'list_history_movies_in_progress',  'icon': os.path.join(ICON_PATH, 'em_andamento.png'), 'plot': 'Filmes que você começou a assistir mas ainda não terminou.'},
    {'title': '[COLOR cyan]Explorar[/COLOR]',      'action': 'movies_explore_menu',              'icon': os.path.join(ICON_PATH, 'genres.png'), 'plot': 'Explore por mais categorias unicas, como gêneros, temas, coleções e mais.'},
]

# === SUBMENU EXPLORAR FILMES ===
MOVIES_EXPLORE_MENU = [
    {'title': 'Para Você',     'action': 'list_recommendations_movies',    'icon': os.path.join(ICON_PATH, 'for_you.png'), 'plot': 'Recomendações personalizadas com base no seu histórico e preferências.'},
    {'title': 'Bem Avaliados', 'action': 'list_top_rated_movies',          'icon': os.path.join(ICON_PATH, 'top.png'), 'plot': 'Filmes com as melhores avaliações no catalogo local.'},
    {'title': 'Gêneros',       'action': 'list_genres',                    'icon': os.path.join(ICON_PATH, 'genres.png'), 'plot': 'Explore por gêneros, como ação, comédia, terror e mais.'},
    {'title': 'Por Ano',       'action': 'list_years',                     'icon': os.path.join(ICON_PATH, 'years.png'), 'plot': 'Explore por ano de lançamento.'},
    {'title': 'Tags',          'action': 'list_movie_themes',              'icon': os.path.join(ICON_PATH, 'tags.png'), 'plot': 'Explore por temas e características, como "baseado em livro", "filme de época", "cult" e mais.'},
    {'title': 'Provedores',    'action': 'list_movie_providers',           'icon': os.path.join(ICON_PATH, 'providers.png'), 'plot': 'Explore por provedores de conteúdo.'},
    {'title': 'Coleções',      'action': 'list_collections',               'icon': os.path.join(ICON_PATH, 'set.png'), 'plot': 'Explore por coleções, como trilogias, sagas e séries de filmes relacionados.'},
]

# ============================================================
# MENU SERIES
# ============================================================
TVSHOWS_MENU = [
    {'title': 'Mais Buscadas','action': 'list_most_searched_shows',         'icon': os.path.join(ICON_PATH, 'most_searched.png'), 'plot': 'Séries mais buscadas no momento.'},
    {'title': 'Em Alta',      'action': 'list_trending_tvshows',            'icon': os.path.join(ICON_PATH, 'trending.png'), 'plot': 'Séries em alta no momento, com mais acessos recentes.'},
    {'title': 'Populares',    'action': 'list_tvshows_by_popularity',       'icon': os.path.join(ICON_PATH, 'most_popular.png'), 'plot': 'Séries mais populares do catalogo local.'},
    {'title': 'Recentes',     'action': 'list_recently_added_tvshows',      'icon': os.path.join(ICON_PATH, 'recent.png'), 'plot': 'Séries adicionadas recentemente ao catalogo local.'},
    {'title': 'Em Andamento', 'action': 'list_history_tvshows_in_progress', 'icon': os.path.join(ICON_PATH, 'em_andamento.png'), 'plot': 'Séries em andamento.'},
    {'title': '[COLOR cyan]Explorar[/COLOR]',     'action': 'tvshows_explore_menu',             'icon': os.path.join(ICON_PATH, 'genres.png'), 'plot': 'Explore por mais categorias unicas, como gêneros, temas, provedores e mais.'},
]

# === SUBMENU EXPLORAR SERIES ===
TVSHOWS_EXPLORE_MENU = [
    {'title': 'Para Você',    'action': 'list_recommendations_tvshows',     'icon': os.path.join(ICON_PATH, 'for_you.png'), 'plot': 'Séries recomendadas para você.'},
    {'title': 'Bem Avaliadas', 'action': 'list_top_rated_shows',    'icon': os.path.join(ICON_PATH, 'top.png'), 'plot': 'Séries melhor avaliadas.'},
    {'title': 'Gêneros',       'action': 'list_tvshows_genres',     'icon': os.path.join(ICON_PATH, 'genres.png'), 'plot': 'Explore por gêneros, como drama, comédia, ficção científica e mais.'},
    {'title': 'Tags',          'action': 'list_tvshow_themes',      'icon': os.path.join(ICON_PATH, 'tags.png'), 'plot': 'Explore por temas e características, como "baseado em livro", "série de TV", "cult" e mais.'},
    {'title': 'Provedores',    'action': 'list_providers',          'icon': os.path.join(ICON_PATH, 'providers.png'), 'plot': 'Explore por provedores de conteúdo.'},
    {'title': 'Animes',        'action': 'list_animes',             'icon': os.path.join(ICON_PATH, 'animes.png'), 'plot': 'Explore séries de anime disponíveis.'},
]

# === MENU SERIES INFANTIL ===
TVSHOWS_MENU_KIDS = [
    {'title': 'Populares', 'action': 'list_tvshows_by_popularity',  'icon': os.path.join(ICON_PATH, 'populares_kids.png'), 'plot': 'Séries mais populares para crianças.'},
    {'title': 'Recentes',  'action': 'list_recently_added_tvshows', 'icon': os.path.join(ICON_PATH, 'recentes_kids.png'), 'plot': 'Séries adicionadas recentemente para crianças.'},
    {'title': 'Infantil',  'action': 'list_kids_tvshows',           'icon': os.path.join(ICON_PATH, 'infantil_kids.png'), 'plot': 'Séries específicas para crianças.'},
]

# === MENU FILMES INFANTIL ===
MOVIES_MENU_KIDS = [
    {'title': 'Populares', 'action': 'list_movies_by_popularity',  'icon': os.path.join(ICON_PATH, 'populares_kids.png'), 'plot': 'Filmes mais populares para crianças.'},
    {'title': 'Recentes',  'action': 'list_recently_added_movies', 'icon': os.path.join(ICON_PATH, 'recentes_kids.png'), 'plot': 'Filmes adicionados recentemente para crianças.'},
    {'title': 'Gêneros',   'action': 'list_genres',                'icon': os.path.join(ICON_PATH, 'generos_kids.png'), 'plot': 'Explore por gêneros, como ação, comédia, ficção científica e mais.'},
]

# ============================================================
# MENU TRAKT
# ============================================================
TRAKT_MENU = [
    {'title': 'Status / Autenticar', 'action': 'trakt_auth',            'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Filmes',              'action': 'trakt_movies_submenu',   'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Series',              'action': 'trakt_tv_submenu',       'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Watchlist',           'action': 'trakt_watchlist_menu',   'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Colecao',             'action': 'trakt_collection_menu',  'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Assistidos',          'action': 'trakt_watched_menu',     'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Minhas Listas',       'action': 'trakt_lists_menu',       'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Sincronizar',         'action': 'trakt_sync_menu',        'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
]

TRAKT_SYNC_MENU = [
    {'title': 'Sincronizacao Completa', 'action': 'trakt_full_sync',       'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Enviar Trakt',           'action': 'trakt_sync_to_trakt',   'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Importar Trakt',         'action': 'trakt_sync_from_trakt', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Limpar Cache',           'action': 'trakt_clear_cache',     'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
]

# === SUBMENU FILMES TRAKT ===
TRAKT_MOVIES_MENU = [
    {'title': 'Watchlist',        'action': 'trakt_watchlist_menu',              'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Assistidos',       'action': 'trakt_watched_menu',                'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Coleção',          'action': 'trakt_collection_menu',             'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Recomendações',    'action': 'trakt_movies_personal_recommended', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Minhas Listas',    'action': 'trakt_lists_menu',                  'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
]

# === SUBMENU SERIES TRAKT ===
TRAKT_TV_MENU = [
    {'title': 'Watchlist',        'action': 'trakt_watchlist_menu',             'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Assistidas',       'action': 'trakt_watched_menu',               'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Coleção',          'action': 'trakt_collection_menu',            'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Recomendações',    'action': 'trakt_tv_personal_recommended',    'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Minhas Listas',    'action': 'trakt_lists_menu',                 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
]
