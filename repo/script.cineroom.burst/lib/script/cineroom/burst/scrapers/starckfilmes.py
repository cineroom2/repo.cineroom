# -*- coding: utf-8 -*-
"""
Scraper para Starck Filmes
"""
import re
import time
import base64
import unicodedata
import xbmc
import requests
from urllib.parse import unquote, unquote_plus, urljoin
from bs4 import BeautifulSoup

from .scraper_config import get_url
BASE_URL   = get_url('starckfilmes', fallback='https://starckfilmes-v29.com')
SEARCH_URL = BASE_URL + "/?s={query}"
HEADERS    = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
}

# ---------------------------------------------------------------------------
# Sessão compartilhada + bypass do gate de "verificação"
# ---------------------------------------------------------------------------

_session = None

# Timeout por request, configurável via settings.xml (scraper.timeout).
_TIMEOUT = 15


def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)
        xbmc.log("[Starck] Nova sessão criada", xbmc.LOGINFO)
    return _session


def _eh_pagina_verificacao(html):
    """Detecta a página fake de 'Verificação de Segurança'."""
    resultado = ('id="verifyBox"' in html) or ('Verificação de Segurança' in html) or ('Comunicado Importante' in html)
    return resultado


def _resolver_verificacao(session, url):
    """
    Replica o handshake da página de verificação:
      1. Aguarda 5.5s (o JS do gate checa se passaram 5000ms)
      2. POST /current-address com {"timeMonit": "14542588"}
      3. GET na mesma URL com cookies da sessão
    """
    xbmc.log("[Starck] Gate detectado — aguardando 5.5s (timer do JS)...", xbmc.LOGINFO)
    time.sleep(5.5)

    try:
        post_url = BASE_URL + "/current-address"
        resp_post = session.post(
            post_url,
            json={"timeMonit": "14542588"},
            timeout=_TIMEOUT
        )
        xbmc.log(f"[Starck] POST status: {resp_post.status_code} | body: {resp_post.text[:200]}", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[Starck] Erro no POST de verificação: {e}", xbmc.LOGERROR)

    try:
        r = session.get(url, timeout=_TIMEOUT)
        r.raise_for_status()
        r.encoding = 'utf-8'
        return r
    except Exception as e:
        xbmc.log(f"[Starck] Erro ao revalidar após verificação: {e}", xbmc.LOGERROR)
        return None


def _get(url, timeout=None, max_tentativas=2):
    """
    Substitui requests.get(url, headers=HEADERS).
    Mantém sessão/cookies e resolve o gate de verificação se aparecer.
    """
    if timeout is None:
        timeout = _TIMEOUT
    session = _get_session()
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        r.encoding = 'utf-8'
    except Exception as e:
        xbmc.log(f"[Starck] Erro no GET {url}: {e}", xbmc.LOGWARNING)
        return None

    tentativas = 0
    while _eh_pagina_verificacao(r.text) and tentativas < max_tentativas:
        nova = _resolver_verificacao(session, url)
        if nova is None:
            xbmc.log("[Starck] _resolver_verificacao retornou None", xbmc.LOGERROR)
            return None
        r = nova
        tentativas += 1

    if _eh_pagina_verificacao(r.text):
        return None

    return r


# ---------------------------------------------------------------------------
# Decodificador do magnet embaralhado
# ---------------------------------------------------------------------------

def unshuffle_string(shuffled):
    try:
        length   = len(shuffled)
        original = [''] * length
        used     = [False] * length
        step     = 3
        index    = 0
        for i in range(length):
            while used[index]:
                index = (index + 1) % length
            used[index]  = True
            original[i]  = shuffled[index]
            index        = (index + step) % length
        result = ''.join(original)
        return result
    except Exception as e:
        xbmc.log(f"[Starck] unshuffle erro: {e}", xbmc.LOGERROR)
        return None


# ---------------------------------------------------------------------------
# Links de download
#
# Layout novo: <a href="https://filmedl.com/?xid=..."> — o xid é o magnet em
# base64, embaralhado com o mesmo unshuffle (passo 3). Decodificado aqui, sem
# abrir o filmedl.com.
# Layout antigo: <a data-u="..."> — só unshuffle. Ainda suportado.
# ---------------------------------------------------------------------------

_RE_XID = re.compile(r'[?&]xid=([^&#\s]+)')


def _decodificar_xid(xid):
    try:
        b64 = unshuffle_string(xid)
        if not b64:
            return None
        b64 = b64.strip()
        b64 += '=' * (-len(b64) % 4)
        magnet = base64.b64decode(b64).decode('utf-8', errors='replace')
        return magnet if magnet.startswith('magnet:') else None
    except Exception as e:
        xbmc.log(f"[Starck] xid erro: {e}", xbmc.LOGERROR)
        return None


def _extrair_links_magnet(elemento):
    """Retorna [(magnet, texto_do_link)] de todos os <a> do elemento."""
    vistos = set()
    saida  = []
    for a in elemento.find_all('a'):
        magnet = None

        m = _RE_XID.search(a.get('href', '') or '')
        if m:
            magnet = _decodificar_xid(unquote(m.group(1)))

        if not magnet:
            data_u = a.get('data-u', '')
            if data_u:
                cand = unshuffle_string(data_u)
                if cand and cand.startswith('magnet:'):
                    magnet = cand

        if not magnet or magnet in vistos:
            continue
        vistos.add(magnet)
        saida.append((magnet, a.get_text(' ', strip=True)))
    return saida


def _formatar_tamanho(b):
    if b <= 0:
        return 'N/A'
    if b < 1024 ** 2:
        return f"{b / 1024:.2f} KB"
    if b < 1024 ** 3:
        return f"{b / 1024 ** 2:.2f} MB"
    return f"{b / 1024 ** 3:.2f} GB"


def _info_magnet(magnet):
    """Extrai nome (dn) e tamanho (xl) do magnet."""
    dn = ''
    m = re.search(r'[?&]dn=([^&]+)', magnet)
    if m:
        dn = unquote_plus(m.group(1))
    tamanho = 'N/A'
    m = re.search(r'[?&]xl=(\d+)', magnet)
    if m:
        tamanho = _formatar_tamanho(int(m.group(1)))
    return dn, tamanho


def _ano_do_torrent(dn):
    """Último ano de 4 dígitos no nome do torrent (o ano costuma vir depois do título)."""
    anos = re.findall(r'(?<![0-9])((?:19|20)\d{2})(?![0-9xX])', dn or '')
    return int(anos[-1]) if anos else None


def _montar_stream(magnet, titulo, qualidade_pagina, tamanho_pagina,
                   texto_extra='', idioma_padrao=None):
    dn, tamanho = _info_magnet(magnet)
    contexto = f"{dn} {texto_extra}"

    m_q = re.search(r'(4K|2160p|1080p|720p|480p)', contexto, re.IGNORECASE)
    qualidade = m_q.group(1) if m_q else qualidade_pagina

    idioma = _idioma_do_texto(contexto)
    if idioma == 'PT-BR' and idioma_padrao:
        idioma = idioma_padrao

    return {
        'url':       magnet,
        'title':     titulo,
        'quality':   qualidade,
        'size':      tamanho if tamanho != 'N/A' else tamanho_pagina,
        'type':      'Torrent',
        'seeders':   0,
        'extras':    [],
        'languages': idioma,
    }


# ---------------------------------------------------------------------------
# Helpers de validação
# ---------------------------------------------------------------------------

_SERIE_PATTERNS = re.compile(
    r'\b(\d+[aªº°]\s*temporada|temporada\s*\d+|t\d+\b|season\s*\d+|'
    r'episod|completo\s+\d+|parte\s+\d+)\b',
    re.IGNORECASE
)

_RE_CARD_SERIE = re.compile(r'temporada|\bs\d{1,2}e\d{1,2}\b', re.IGNORECASE)
_RE_TORRENT_EPISODIO = re.compile(r'\bs\d{1,2}e\d{1,2}\b', re.IGNORECASE)


def _titulo_parece_serie(texto):
    return bool(_SERIE_PATTERNS.search(texto or ''))


def _normalizar_titulo(texto):
    nfkd = unicodedata.normalize('NFKD', texto or '')
    s = ''.join(c for c in nfkd if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[',\.\-_:]", ' ', s)
    s = re.sub(r'\b(the|a|an|o|a|os|as|de|do|da|um|uma)\b', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def _titulo_compativel(titulo_pagina, titulo_busca, is_serie=False):
    if not is_serie and _titulo_parece_serie(titulo_pagina):
        return False

    norm_pagina = _normalizar_titulo(titulo_pagina)
    norm_busca  = _normalizar_titulo(titulo_busca)

    if not norm_busca:
        return True

    pattern = r'^' + re.escape(norm_busca) + r'(\s|$)'
    if re.match(pattern, norm_pagina):
        return True

    tokens_busca  = norm_busca.split()
    tokens_pagina = norm_pagina.split()

    if not tokens_busca:
        return True

    matches = sum(1 for t in tokens_busca if t in tokens_pagina)
    ratio   = matches / len(tokens_busca)

    threshold = 1.0 if len(tokens_busca) <= 3 else 0.90
    if ratio < threshold:
        return False

    idx = norm_pagina.find(norm_busca)
    if idx > 0:
        prefix_words = [
            w for w in norm_pagina[:idx].split()
            if w not in {'the', 'a', 'an', 'o', 'os', 'as', 'de', 'do', 'da',
                 'in', 'of', 'and', 'em', 'no', 'na', 'nos', 'nas', 'e'}
        ]
        if prefix_words:
            xbmc.log(
                f"[Starck] Rejeitado (palavras antes do título): {prefix_words} em '{titulo_pagina}'",
                xbmc.LOGDEBUG
            )
            return False

    return True


# ---------------------------------------------------------------------------
# Helpers de idioma
# ---------------------------------------------------------------------------

def _idioma_do_texto(texto):
    t = (texto or '').lower()
    if 'dual' in t:
        return 'DUAL'
    if 'dublado' in t:
        return 'DUBLADO'
    if 'legendado' in t:
        return 'LEGENDADO'
    return 'PT-BR'


# ---------------------------------------------------------------------------
# Parsers da página de conteúdo
# ---------------------------------------------------------------------------

def _get_titulo_limpo(soup):
    h2 = soup.find('h2', class_='post-title')
    if h2:
        return h2.get_text(strip=True)
    h1 = soup.find('h1')
    if h1:
        t = h1.get_text(strip=True)
        return re.sub(r'\s*[Tt]orrent.*$', '', t).strip()
    return ''


def _get_ano(soup):
    desc = soup.find('div', class_='post-description')
    if not desc:
        return ''
    for p in desc.find_all('p'):
        spans = p.find_all('span')
        if len(spans) >= 2 and 'lançamento' in spans[0].get_text().lower():
            return spans[1].get_text(strip=True)
    return ''


def _get_qualidade(soup):
    span = soup.find('span', class_='sl-quality')
    if not span:
        return 'HD'
    return {'FHD': '1080p', 'UHD': '4K', 'HD': '720p', 'SD': '480p'}.get(
        span.get_text(strip=True).upper(), span.get_text(strip=True)
    )


def _get_tamanho(soup):
    desc = soup.find('div', class_='post-description')
    if not desc:
        return 'N/A'
    for p in desc.find_all('p'):
        spans = p.find_all('span')
        if len(spans) >= 2 and 'tamanho' in spans[0].get_text().lower():
            return spans[1].get_text(strip=True)
    return 'N/A'


# ---------------------------------------------------------------------------
# Busca no site
# ---------------------------------------------------------------------------

def _executar_busca(query):
    """
    Faz o GET de busca e retorna [(titulo, url)] dos cards encontrados.
    Layout antigo: cards .sub-item. Layout novo: qualquer <a href="/catalog/..."
    com atributo title.
    """
    search_url = SEARCH_URL.format(query=requests.utils.quote(query))
    r = _get(search_url)
    if r is None:
        xbmc.log("[Starck] _get retornou None na busca", xbmc.LOGERROR)
        return []

    soup = BeautifulSoup(r.text, 'html.parser')
    achados = []
    vistos  = set()

    def _add(a):
        href   = a.get('href', '')
        titulo = a.get('title', '') or a.get_text(strip=True)
        if not href or not titulo:
            return
        url = urljoin(BASE_URL + '/', href)
        if url in vistos:
            return
        vistos.add(url)
        achados.append((titulo, url))

    for card in soup.select('.sub-item'):
        a_pai = card.find('a', href=re.compile(r'/catalog/'))
        if a_pai:
            _add(a_pai)

    if not achados:
        for a in soup.find_all('a', href=re.compile(r'/catalog/')):
            if a.get('title'):
                _add(a)

    xbmc.log(f"[Starck] busca '{query}': {len(achados)} card(s)", xbmc.LOGDEBUG)
    return achados


def _buscar_paginas(query, max_results=5, titulo_busca=''):
    cards = _executar_busca(query)

    itens = []
    for titulo, url in cards:
        if titulo_busca:
            norm_card  = _normalizar_titulo(titulo)
            norm_busca = _normalizar_titulo(titulo_busca)
            tokens_busca = norm_busca.split()
            tokens_card  = norm_card.split()
            if tokens_busca:
                matches = sum(1 for t in tokens_busca if t in tokens_card)
                ratio   = matches / len(tokens_busca)
                if ratio < 1.0:
                    xbmc.log(
                        f"[Starck] Card descartado: '{titulo}' vs '{titulo_busca}' (ratio={ratio:.2f})",
                        xbmc.LOGDEBUG
                    )
                    continue

        itens.append((titulo, url))
        if len(itens) >= max_results:
            break

    return itens


def _fetch_pagina(url):
    r = _get(url)
    if r is None:
        return None
    return BeautifulSoup(r.text, 'html.parser')


def _ano_ok(soup, ano_esperado):
    if not ano_esperado:
        return True
    ano_pagina = _get_ano(soup)
    m = re.search(r'(?:19|20)\d{2}', ano_pagina or '')
    try:
        return abs(int(m.group(0)) - int(ano_esperado)) <= 1
    except Exception:
        xbmc.log(f"[Starck] Ano: não foi possível comparar (página='{ano_pagina}' esperado='{ano_esperado}')", xbmc.LOGDEBUG)
        return True


# ---------------------------------------------------------------------------
# Busca de FILME
# ---------------------------------------------------------------------------

def buscar_filme(item_data):
    titulo          = item_data.get('title', '')
    titulo_original = item_data.get('original_title', '')
    ano             = item_data.get('year', '')

    try:
        ano_int = int(ano)
    except Exception:
        ano_int = None

    if not titulo:
        xbmc.log("[Starck] buscar_filme: título vazio, abortando", xbmc.LOGERROR)
        return []

    queries = [titulo]
    if titulo_original and titulo_original.lower() != titulo.lower():
        queries.append(titulo_original)

    sources = []

    for query in queries:
        paginas = _buscar_paginas(query, max_results=8, titulo_busca=titulo)

        for titulo_card, url in paginas:
            # Busca de filme não deve abrir páginas de série
            if _RE_CARD_SERIE.search(f"{titulo_card} {url}"):
                xbmc.log(f"[Starck] Ignorado (parece série): {url}", xbmc.LOGDEBUG)
                continue

            soup = _fetch_pagina(url)
            if not soup:
                continue

            if not _ano_ok(soup, ano):
                continue

            titulo_limpo = _get_titulo_limpo(soup) or titulo

            if not _titulo_compativel(titulo_limpo, titulo, is_serie=False):
                xbmc.log(f"[Starck] Título incompatível: '{titulo_limpo}' vs '{titulo}'", xbmc.LOGDEBUG)
                continue

            qualidade = _get_qualidade(soup)
            tamanho   = _get_tamanho(soup)

            for magnet, texto in _extrair_links_magnet(soup):
                dn, _tam = _info_magnet(magnet)

                if _RE_TORRENT_EPISODIO.search(dn):
                    xbmc.log(f"[Starck] Ignorado (episódio de série): {dn}", xbmc.LOGDEBUG)
                    continue

                ano_torrent = _ano_do_torrent(dn)
                if ano_torrent and ano_int and abs(ano_torrent - ano_int) > 1:
                    xbmc.log(
                        f"[Starck] Ignorado por ano: torrent={ano_torrent} esperado={ano_int} ({titulo_limpo})",
                        xbmc.LOGDEBUG
                    )
                    continue

                sources.append(_montar_stream(magnet, titulo_limpo, qualidade, tamanho, texto))

            if sources:
                break

        if sources:
            break

    return sources


# ---------------------------------------------------------------------------
# Busca de SÉRIE
# ---------------------------------------------------------------------------

def buscar_serie(item_data, season, episode):
    titulo          = item_data.get('title', '')
    titulo_original = item_data.get('original_title', '')

    if not titulo or season is None or episode is None:
        xbmc.log("[Starck] buscar_serie: parâmetros inválidos, abortando", xbmc.LOGERROR)
        return []

    s_num = int(season)
    e_num = int(episode)
    s_pad = str(s_num).zfill(2)
    e_pad = str(e_num).zfill(2)

    queries = [titulo]
    if titulo_original and titulo_original.lower() != titulo.lower():
        queries.append(titulo_original)

    sources = []

    for query in queries:
        for _titulo_card, url in _buscar_paginas(query, max_results=8, titulo_busca=titulo):
            soup = _fetch_pagina(url)
            if not soup:
                continue

            titulo_pagina = _get_titulo_limpo(soup).lower()

            # CASO A: episódios separados
            epsodios_div = soup.find('div', class_='epsodios')
            if epsodios_div:
                padrao_temporada = re.search(
                    rf'({s_num}[aªº°]?\s*temporada|temporada\s*{s_num})',
                    titulo_pagina, re.IGNORECASE
                )
                if not padrao_temporada:
                    continue

                h3 = epsodios_div.find('h3')
                idioma_ep = _idioma_do_texto(h3.get_text() if h3 else '')

                qualidade    = _get_qualidade(soup)
                tamanho      = _get_tamanho(soup)
                titulo_limpo = _get_titulo_limpo(soup) or titulo

                if not _titulo_compativel(titulo_limpo, titulo, is_serie=True):
                    continue

                paragrafos = epsodios_div.find_all('p')

                for p in paragrafos:
                    strong = p.find('strong')
                    if not strong:
                        continue

                    ep_text = strong.get_text().lower()
                    episodio_encontrado = False

                    # Verifica episódio único: "EPISÓDIO 03" ou "EPISÓDIOS 03"
                    if re.search(rf'episódios?\s+0?{e_num}\b', ep_text):
                        episodio_encontrado = True

                    # Verifica range: "EPISÓDIOS 01 E 02"
                    if not episodio_encontrado:
                        m = re.search(r'episódios?\s+0?(\d+)\s+(?:e|ao)\s+0?(\d+)', ep_text)
                        if m and int(m.group(1)) <= e_num <= int(m.group(2)):
                            episodio_encontrado = True

                    if not episodio_encontrado:
                        continue

                    # Pega TODOS os links de download (múltiplas qualidades)
                    links = _extrair_links_magnet(p)
                    if not links:
                        xbmc.log("[Starck] Episódio sem links de download", xbmc.LOGDEBUG)
                        continue

                    for magnet, q_link in links:
                        sources.append(_montar_stream(
                            magnet,
                            f"{titulo_limpo} S{s_pad}E{e_pad}",
                            qualidade, tamanho, q_link,
                            idioma_padrao=idioma_ep,
                        ))

                    # Sai do loop de parágrafos após processar o episódio encontrado
                    break

                if sources:
                    break
                continue

            # CASO B: temporada inteira
            padrao_temporada = re.search(
                rf'({s_num}[aªº°]?\s*temporada|temporada\s*{s_num})',
                titulo_pagina, re.IGNORECASE
            )
            if not padrao_temporada:
                continue

            titulo_limpo = _get_titulo_limpo(soup) or titulo
            qualidade    = _get_qualidade(soup)
            tamanho      = _get_tamanho(soup)

            for magnet, texto in _extrair_links_magnet(soup):
                sources.append(_montar_stream(magnet, titulo_limpo, qualidade, tamanho, texto))

            if sources:
                break

        if sources:
            break

    return sources


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def scrape(provider_url, item_data, season=None, episode=None, timeout=None):
    global _TIMEOUT
    if timeout:
        _TIMEOUT = timeout

    media_type = item_data.get('media_type', 'movie')

    if media_type == 'movie':
        result = buscar_filme(item_data)
    elif media_type == 'tvshow':
        result = buscar_serie(item_data, season, episode)
    else:
        result = []

    xbmc.log(f"[Starck] ===== SCRAPE FINALIZADO: {len(result)} fonte(s) =====", xbmc.LOGINFO)
    return result
