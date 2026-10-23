import hashlib
import os
import xml.etree.ElementTree as ET
import zipfile
import zlib

REPO_DIR = 'repo'
OUTPUT_XML = 'addons.xml'
OUTPUT_MD5 = 'addons.xml.md5'

SKIP_DIRS = {'__pycache__', '.git', '.github'}
SKIP_EXT = ('.zip', '.pyc', '.pyo')
FIXED_DATE = (2020, 1, 1, 0, 0, 0)  # data fixa => zip identico quando nada mudou

# Addons editados neste push (o workflow preenche). Se o zip da versao atual ja existe,
# so e refeito para esses addons; os demais ficam intocados.
CHANGED = set(os.environ.get('CHANGED_ADDONS', '').split())


def addon_dirs():
    for name in sorted(os.listdir(REPO_DIR)):
        path = os.path.join(REPO_DIR, name)
        if name.startswith('.') or not os.path.isdir(path):
            continue
        if os.path.isfile(os.path.join(path, 'addon.xml')):
            yield name, path


def collect_files(addon_id, addon_path):
    """Retorna {nome_no_zip: caminho_no_disco} sem zips, .pyc e pastas de cache."""
    files = {}
    for root, dirs, names in os.walk(addon_path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for n in sorted(names):
            if n.endswith(SKIP_EXT):
                continue
            full = os.path.join(root, n)
            rel = os.path.relpath(full, addon_path).replace(os.sep, '/')
            files['%s/%s' % (addon_id, rel)] = full
    return files


def crc_of(path):
    crc = 0
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            crc = zlib.crc32(chunk, crc)
    return crc & 0xFFFFFFFF


def zip_is_current(zip_path, files):
    if not os.path.isfile(zip_path):
        return False
    try:
        with zipfile.ZipFile(zip_path) as zf:
            current = {i.filename: i.CRC for i in zf.infolist() if not i.is_dir()}
    except zipfile.BadZipFile:
        return False
    wanted = {name: crc_of(path) for name, path in files.items()}
    return current == wanted


def build_zip(zip_path, files):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(files[name], 'rb') as f:
                zf.writestr(info, f.read())


def build_zips():
    for name, path in addon_dirs():
        root = ET.parse(os.path.join(path, 'addon.xml')).getroot()
        addon_id, version = root.get('id'), root.get('version')
        if addon_id != name:
            print('::warning::pasta %s tem addon id %s no addon.xml' % (name, addon_id))
        zip_path = os.path.join(path, '%s-%s.zip' % (addon_id, version))
        files = collect_files(addon_id, path)

        existed = os.path.isfile(zip_path)
        if existed and addon_id not in CHANGED:
            print('ok      %s %s (zip existente mantido)' % (addon_id, version))
            continue
        if existed and zip_is_current(zip_path, files):
            print('ok      %s %s (zip ja esta atualizado)' % (addon_id, version))
            continue

        build_zip(zip_path, files)
        if existed:
            print('::warning::%s: o codigo mudou mas a versao continua %s. '
                  'O zip foi refeito, porem quem ja tem essa versao instalada NAO vai receber '
                  'a atualizacao. Suba a versao no addon.xml.' % (addon_id, version))
        else:
            print('novo    %s %s -> %s' % (addon_id, version, zip_path))


def generate_addons_file():
    addons = []
    for _, path in addon_dirs():
        with open(os.path.join(path, 'addon.xml'), 'r', encoding='utf-8') as f:
            content = f.read().strip()
        if content.startswith('<?xml'):
            content = content[content.find('?>') + 2:].strip()
        addons.append(content)

    with open(OUTPUT_XML, 'w', encoding='utf-8', newline='\n') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<addons>\n')
        for addon in addons:
            f.write(addon.strip() + '\n')
        f.write('</addons>')


def generate_md5():
    with open(OUTPUT_XML, 'rb') as f:
        data = f.read()
    with open(OUTPUT_MD5, 'w', encoding='utf-8', newline='\n') as f:
        f.write(hashlib.md5(data).hexdigest())


if __name__ == '__main__':
    build_zips()
    generate_addons_file()
    generate_md5()
