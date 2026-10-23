# -*- coding: utf-8 -*-
"""
Processamento e formatação de streams
"""
import re
import xbmcaddon

ADDON = xbmcaddon.Addon()


_PROVIDERS_ALWAYS_PTBR = {'FrostStream'}
_PROVIDERS_DEFAULT_720P = {''}

def extrair_idiomas_do_titulo(titulo, extras=None, provider=None):
    if provider in _PROVIDERS_ALWAYS_PTBR:
        return 'PT-BR'

    provedores_br = ['Fenixflix', 'StarckFilmes', 'SkyFlix', 'Brazuca', 'CDFlix',
                     'ComandoTop', 'Mico-Leão', 'AnimeZey', 'Fonte Local']

    if provider in provedores_br:
        t = (titulo or '').lower()
        if 'dual' in t or 'multi' in t:
            return 'DUAL'
        if 'legendado' in t or ' leg' in t:
            return 'LEG'
        return 'PT-BR'

    if not titulo:
        return 'LEG'

    t = titulo.lower()

    has_pt = any(x in t for x in ['dublado', 'portugues', 'português', 'pt-br', ' pt '])
    has_dual = any(x in t for x in ['dual', 'dual audio', 'dublado e legendado', 'dub e leg'])
    has_multi = 'multi' in t

    if has_dual:
        return 'DUAL'
    if has_multi and has_pt:
        return 'DUAL'
    if has_pt:
        return 'PT-BR'

    return 'LEG'


def get_color_seeders(val, stream_type):
    """
    Retorna label colorido e score para seeders
    """
    if stream_type == 'Direto' or val == 999:
        return "Direct", 999
    
    try:
        v = int(val)
        color = "green" if v >= 10 else ("yellow" if v >= 5 else "red")
        return f"[COLOR {color}]{v}[/COLOR]", v
    except:
        return "[COLOR grey]S:0[/COLOR]", 0


def get_color_quality(q):
    """
    Retorna label colorido e score para qualidade
    """
    q = q.upper()
    if '4K' in q or '2160P' in q:
        return f"[COLOR gold]{q}[/COLOR]", 4
    if '1080P' in q:
        return f"[COLOR blue]{q}[/COLOR]", 3
    if '720P' in q:
        return f"[COLOR orange]{q}[/COLOR]", 2
    return f"[COLOR grey]{q}[/COLOR]", 1


def extrair_codec_hdr(raw_title):
    """
    Extrai codec, HDR e source do título
    """
    t = raw_title.lower()

    # Source
    source = ""
    if any(x in t for x in ['web-dl', 'webdl', 'webrip']):
        source = "web-dl"
    elif any(x in t for x in ['bluray', 'blu-ray', 'bdrip', 'bdremux']):
        source = "bluray"
    elif 'hdrip' in t:
        source = "hdrip"
    elif 'dvdrip' in t:
        source = "dvdrip"
    elif '3d' in t:
        source = "3d"
    elif 'cam' in t:
        source = "cam"
    elif re.search(r'\bts\b', t):
        source = "ts"

    # Codec
    codec = ""
    if any(x in t for x in ('h265', 'x265', 'hevc')):
        codec = "HEVC"
    elif any(x in t for x in ('h264', 'x264', 'avc')):
        codec = "AVC"

    # HDR
    hdr = ""
    if 'hdr' in t:
        hdr = "HDR"
    elif '10bit' in t or '10-bit' in t:
        hdr = "10bit"

    return codec, hdr, source


def extrair_audio(raw_title):
    """
    Extrai informações de áudio do título
    """
    t = raw_title.lower()

    # Canais
    canais = ""
    if re.search(r'7[\.\s]?1', t):
        canais = "7.1"
    elif re.search(r'5[\.\s]?1', t):
        canais = "5.1"
    elif re.search(r'2[\.\s]?0', t):
        canais = "2.0"

    # Codec
    codec = ""
    if 'atmos' in t:
        codec = "Atmos"
    elif 'truehd' in t:
        codec = "TrueHD"
    elif 'dts-hd' in t or 'dtshd' in t:
        codec = "DTS-HD"
    elif 'dts' in t:
        codec = "DTS"
    elif 'eac3' in t or 'dd+' in t:
        codec = "DD+"
    elif 'ac3' in t:
        codec = "AC3"
    elif 'aac' in t:
        codec = "AAC"

    return " ".join(x for x in (codec, canais) if x)


def _parse_lang_hint(hint):
    if not hint:
        return ''
    h = hint.lower()
    if 'legendado' in h:
        return 'LEG'
    if 'português e inglês' in h or 'dual' in h:
        return 'DUAL'
    if 'português' in h or 'portugues' in h:
        return 'PT-BR'
    return ''


def process_single_stream(stream, is_local=False, p_name='Fonte Local', p_priority=999, item_data=None):
    """
    Processa um único stream e retorna dict formatado
    """
    url = stream.get('url') or stream.get('infoHash')
    if not url:
        return None

    raw_title = stream.get('title') or stream.get('name') or ""
    if raw_title and isinstance(raw_title, str):
        try:
            raw_title = raw_title.encode('latin-1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass  # já está correto, ignora

    # Providers cujo raw_title é o nome do addon, não metadados técnicos reais.
    # Para eles, os regexes de qualidade/codec/audio são aplicados em string vazia,
    # confiando apenas nos campos explícitos do objeto stream (ex: stream['quality']).
    _UNRELIABLE_TITLE_PROVIDERS = {'NebulaStreams', 'HdHub'}

    # Limpa título para display
    display_title = raw_title

    # Para providers com título = nome do addon (ex: "4KHDHub 1080p", "4KHDHub 4K"),
    # separa o sufixo (qualidade real) do prefixo (nome do addon) e limpa o display_title
    if p_name in _UNRELIABLE_TITLE_PROVIDERS:
        suffix_match = re.match(
            r'^[\w\d]*hub\s*(4K|2160p|1080p|720p|480p)?\s*(.*)',
            display_title, flags=re.IGNORECASE
        )
        if suffix_match:
            quality_from_name = suffix_match.group(1) or ''   # ex: "1080p" ou "4K"
            leftover          = (suffix_match.group(2) or '').strip()  # qualquer coisa depois
            display_title     = leftover  # vazio → cai no fallback com título real
        else:
            quality_from_name = ''
    else:
        quality_from_name = ''

    display_title = re.sub(r'👤\s*\d+', '', display_title)
    display_title = re.sub(r'S:\s*\d+', '', display_title)
    display_title = re.sub(r'\[\s*\d+\.?\d*\s*(?:GB|MB)\s*\]', '', display_title, flags=re.IGNORECASE)
    display_title = re.sub(r'⚙️\s*[^\n]+$', '', display_title)
    display_title = ' '.join(display_title.split()).strip()
    
    if len(display_title) > 80:
        display_title = display_title[:77] + '...'
    
    # Fallback se vazio
    if not display_title and item_data:
        nome_base = item_data.get('title') or 'Vídeo'
        ano = item_data.get('year') or ''
        if item_data.get('season') and item_data.get('episode'):
            s = str(item_data['season']).zfill(2)
            e = str(item_data['episode']).zfill(2)
            display_title = f"{nome_base} S{s}E{e}"
        else:
            display_title = f"{nome_base} ({ano})" if ano else nome_base

    # Detecta tipo
    # Detecta tipo
    if is_local:
        is_torrent = (
            "elementum" in url
            or url.lower().startswith('magnet:')
            or bool(re.match(r'^[a-fA-F0-9]{40}$', url))
            or stream.get('server_name', '').upper() == 'TORRENT'
        )
        stype = 'Torrent' if is_torrent else 'Direto'
    else:
        force_direct_providers = ('Fenixflix', 'Nuvio')

        if p_name in force_direct_providers:
            stype = 'Direto'
        else:
            stype = stream.get('type', 'Direto')
            if re.match(r'^[a-fA-F0-9]{40}$', url) or url.startswith('magnet:'):
                stype = 'Torrent'

    # Seeders
    seed_match = re.search(r'(?:👤|S:)\s*(\d+)', raw_title)
    s_val = seed_match.group(1) if seed_match else stream.get('seeders', 0)
    if stype == 'Direto':
        s_val = 999

    # Substitui apenas o bloco do size_str em process_single_stream:

    # 1. sizeBytes na raiz (KOD/Torrentio via KOD)
    size_bytes = stream.get('sizeBytes') or stream.get('videoSize')

    # 2. behaviorHints.videoSize (NebulaStreams / 4KHDHub)
    if not size_bytes:
        hints = stream.get('behaviorHints') or {}
        size_bytes = hints.get('videoSize')

    # 3. Converte bytes → string legível
    if size_bytes:
        try:
            size_bytes = int(size_bytes)
            if size_bytes >= 1_073_741_824:
                size_str = f"{size_bytes / 1_073_741_824:.2f} GB"
            else:
                size_str = f"{size_bytes / 1_048_576:.0f} MB"
        except (ValueError, TypeError):
            size_str = 'N/A'
    else:
        # 4. Fallback: 💾 no title/description (Torrentio puro, alguns Knaben)
        size_match = (
            re.search(r'💾\s*(\d+(?:[.,]\d+)?\s*(?:GB|MB))', raw_title, re.IGNORECASE)
            or re.search(r'(\d+(?:[.,]\d+)?\s*(?:GB|MB))', raw_title, re.IGNORECASE)
        )
        size_str = size_match.group(1).strip() if size_match else stream.get('size', 'N/A')

    _title_for_meta = "" if p_name in _UNRELIABLE_TITLE_PROVIDERS else raw_title

    # Quality — para providers com título não confiável, usa o sufixo extraído do nome
    # (ex: "1080p" de "4KHDHub 1080p"), não o raw_title inteiro (que contém "4K" no prefixo)
    if quality_from_name:
        q_str = quality_from_name.upper()
    elif p_name in _PROVIDERS_DEFAULT_720P:
        q_str = '720P'
    else:
        q_match = re.search(r'(4K|2160p|1080p|720p|480p)', _title_for_meta, re.IGNORECASE)
        if q_match:
            q_str = q_match.group(1).upper()
        else:
            name_match = re.search(r'(4K|2160p|1080p|720p|480p)', stream.get('name', ''), re.IGNORECASE)
            q_str = name_match.group(1).upper() if name_match else str(stream.get('quality', 'SD')).upper()

    # Codec/HDR/Source
    codec, hdr, source = extrair_codec_hdr(_title_for_meta)
    audio = extrair_audio(_title_for_meta)
    video_info = " ".join(x for x in (codec, hdr, audio) if x)

    # Labels coloridos
    seed_label, seed_score = get_color_seeders(s_val, stype)
    qual_label, qual_score = get_color_quality(q_str)

    _LANG_MAP = {
        'DUB':        'PT-BR',
        'DUBLADO':    'PT-BR',
        'Dublado':    'PT-BR',
        'PT-BR':      'PT-BR',
        'PT':         'PT-BR',
        'PORTUGUESE': 'PT-BR',
        'Legendado':  'LEG',
        'LEG':        'LEG',
        'LEGENDADO':  'LEG',
        'DUBBED':     'LEG',
        'DUAL':       'DUAL',
        'DUAL AUDIO': 'DUAL',
        'MULTI':      'DUAL',
    }
    
    raw_lang = (
        _parse_lang_hint(stream.get('_lang_hint', ''))
        or stream.get('languages')
        or stream.get('audio_label')
        or extrair_idiomas_do_titulo(stream.get('description', ''), stream.get('extras', []), p_name)
        or extrair_idiomas_do_titulo(raw_title, stream.get('extras', []), p_name)
    )
    languages = _LANG_MAP.get((raw_lang or '').upper(), raw_lang) if raw_lang else 'LEG'
    

    return {
        'url': url,
        'display_title': display_title,
        'raw_title': raw_title,
        'quality_label': qual_label,
        'seeders_label': seed_label,
        'size': size_str,
        'provider': p_name,
        'languages': languages,
        'codec': codec.lower() if codec else '',
        'hdr': hdr.lower() if hdr else '',
        'audio': audio.lower() if audio else '',
        'source': source,
        'video_info': video_info,
        'p_priority': p_priority,
        'q_score': qual_score,
        's_score': int(s_val),
        'manifest_type': stream.get('manifest_type', ''),
        'headers': stream.get('headers', ''),
        'type': stype,
    }