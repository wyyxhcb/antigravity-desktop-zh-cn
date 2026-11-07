"""Version-pinned, offline, reversible Antigravity desktop localization installer.

Python 3.9+, standard library only. App data, settings and updates are untouched.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
STATE = '.antigravity-zh-cn.json'
MARKER = b'/* ANTIGRAVITY_ZH_CN_LOCAL_PATCH_V1 */'
FUSE_SENTINEL = b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX'


class PackError(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse_archive(data):
    if len(data) < 16:
        raise PackError('程序资源文件不完整。')
    a, header_size, payload_size, json_size = struct.unpack_from('<4I', data)
    start = 8 + header_size
    if a != 4 or payload_size + 4 != header_size or json_size + 8 > header_size or start > len(data):
        raise PackError('无法识别此版本的程序资源格式。')
    try:
        header = json.loads(data[16:16 + json_size])
    except (UnicodeError, ValueError) as error:
        raise PackError('程序资源目录损坏。') from error
    return header, data[start:]


def entries(header, prefix=''):
    for name, entry in header.get('files', {}).items():
        full = prefix + name
        if 'files' in entry:
            yield from entries(entry, full + '/')
        else:
            yield full, entry


def get_file(header, payload, name):
    entry = dict(entries(header)).get(name)
    if not entry or entry.get('unpacked') or 'link' in entry:
        raise PackError('缺少必要的程序资源：' + name)
    offset, size = int(entry['offset']), int(entry['size'])
    if offset < 0 or size < 0 or offset + size > len(payload):
        raise PackError('程序资源范围校验失败：' + name)
    return payload[offset:offset + size]


def integrity(data, block_size=4194304):
    return {
        'algorithm': 'SHA256', 'hash': digest(data), 'blockSize': block_size,
        'blocks': [digest(data[i:i + block_size]) for i in range(0, len(data), block_size)]
    }


def serialize_archive(header, payload):
    raw = json.dumps(header, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    padding = (-len(raw)) % 4
    return struct.pack('<4I', 4, len(raw) + padding + 8, len(raw) + padding + 4, len(raw)) + raw + b'\0' * padding + payload


def replace_file(data, name, replacement):
    header, payload = parse_archive(data)
    result_header = copy.deepcopy(header)
    output = bytearray()
    found = False
    for item_name, entry in entries(result_header):
        if 'offset' not in entry or entry.get('unpacked'):
            continue
        contents = get_file(header, payload, item_name)
        if item_name == name:
            contents = replacement
            entry['integrity'] = integrity(contents)
            found = True
        entry['offset'] = str(len(output))
        entry['size'] = len(contents)
        output.extend(contents)
    if not found:
        raise PackError('没有找到界面加载文件。')
    return serialize_archive(result_header, bytes(output))


def load_manifest():
    return json.loads((ROOT / 'manifest.json').read_text('utf-8'))


def compatibility_profile(manifest, version):
    profile = manifest.get('compatibility', {}).get(version)
    if version not in manifest['supportedAppVersions'] or not isinstance(profile, dict):
        raise PackError(f'当前程序版本为 {version}；本语言包仅适配 ' + ', '.join(manifest['supportedAppVersions']) + '，未修改任何文件。')
    return profile


def load_native_patches(manifest, version):
    filename = compatibility_profile(manifest, version)['nativePatches']
    if not isinstance(filename, str) or Path(filename).name != filename or not filename.endswith('.json'):
        raise PackError('版本适配文件路径不合法。')
    return json.loads((ROOT / filename).read_text('utf-8'))


def render_payload():
    source = (ROOT / 'renderer.js').read_text('utf-8')
    trusted = json.loads((ROOT / 'source-text.json').read_text('utf-8'))
    token = '/*__ZH_CN_SOURCE_TEXT__*/ []'
    if source.count(token) != 1:
        raise PackError('界面翻译模板校验失败。')
    return source.replace(token, json.dumps(trusted, ensure_ascii=False)).encode('utf-8')


def render_localizer():
    dictionary = json.loads((ROOT / 'zh-CN.json').read_text('utf-8'))
    if not dictionary or any(not isinstance(k, str) or not isinstance(v, str) for k, v in dictionary.items()):
        raise PackError('翻译词典格式错误。')
    source = (ROOT / 'localizer.js').read_text('utf-8')
    token = '/*__ZH_CN_DICTIONARY__*/ {}'
    if source.count(token) != 1:
        raise PackError('语言包模板校验失败。')
    patterns = json.loads((ROOT / 'patterns.json').read_text('utf-8'))
    patterns_token = '/*__ZH_CN_PATTERNS__*/ []'
    if source.count(patterns_token) != 1 or any(not isinstance(item.get('regex'), str) or not isinstance(item.get('replacement'), str) for item in patterns):
        raise PackError('动态翻译模板校验失败。')
    return source.replace(token, json.dumps(dictionary, ensure_ascii=False)).replace(patterns_token, json.dumps(patterns, ensure_ascii=False)).encode('utf-8')


def build(original):
    manifest = load_manifest()
    header, payload = parse_archive(original)
    package = json.loads(get_file(header, payload, 'package.json'))
    version = package.get('version')
    if package.get('name') != 'antigravity':
        raise PackError('此资源不属于 Antigravity 桌面版。')
    profile = compatibility_profile(manifest, version)
    preload = get_file(header, payload, 'dist/preload.js')
    if MARKER in preload:
        raise PackError('该程序已包含中文补丁，请先检查状态或恢复英文。')
    if digest(preload) != profile['preloadSha256']:
        raise PackError('界面加载文件与已验证版本不同；为避免覆盖其他修改，已停止安装。')
    menu_hook = b"showContextMenu: (items) => electron_1.ipcRenderer.invoke('window:show-context-menu', items),"
    translated_hook = b"showContextMenu: (items) => electron_1.ipcRenderer.invoke('window:show-context-menu', agZh.menu(items)),"
    if preload.count(menu_hook) != 1:
        raise PackError('无法确认原生右键菜单接口，未修改程序。')
    replacement = b'"use strict";\n' + MARKER + b'\n' + render_localizer() + b'\n' + preload.replace(menu_hook, translated_hook) + b'\n' + render_payload() + b'\n'
    patched = replace_file(original, 'dist/preload.js', replacement)
    native_patches = load_native_patches(manifest, version)
    expected_files = {'dist/preload.js': replacement}
    for name, change in native_patches.items():
        native_source = get_file(header, payload, name)
        if digest(native_source) != change['sha256']:
            raise PackError('系统菜单模块与适配版本不同，未修改程序：' + name)
        native_text = native_source.decode('utf-8')
        for edit in change['replacements']:
            if native_text.count(edit['before']) != edit['count']:
                raise PackError('系统界面文字校验失败：' + name)
            native_text = native_text.replace(edit['before'], edit['after'])
        expected_files[name] = native_text.encode('utf-8')
        patched = replace_file(patched, name, expected_files[name])
    check_header, check_payload = parse_archive(patched)
    for name, expected in expected_files.items():
        if get_file(check_header, check_payload, name) != expected:
            raise PackError('生成后的资源校验失败：' + name)
    for name, entry in entries(header):
        if name not in expected_files and 'offset' in entry and not entry.get('unpacked'):
            if get_file(header, payload, name) != get_file(check_header, check_payload, name):
                raise PackError('发现意外的资源更改，已中止：' + name)
    return patched, version


def app_dir(value=None):
    if value:
        path = Path(value).expanduser().resolve()
        if path.name.lower() == 'antigravity.exe':
            path = path.parent
    else:
        candidates = [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Antigravity',
            Path.home() / 'AppData' / 'Local' / 'Programs' / 'Antigravity',
            Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Antigravity',
        ]
        matches = list(dict.fromkeys(p.resolve() for p in candidates
                                    if (p / 'Antigravity.exe').is_file() and (p / 'resources/app.asar').is_file()))
        if len(matches) != 1:
            raise PackError('无法唯一确定安装位置。请使用 --app-dir 指定 Antigravity 的安装文件夹。')
        path = matches[0].resolve()
    if not (path / 'Antigravity.exe').is_file() or not (path / 'resources/app.asar').is_file():
        raise PackError('此文件夹不是受支持的 Antigravity 桌面版安装目录。')
    return path


def assert_supported_executable(folder):
    data = (folder / 'Antigravity.exe').read_bytes()
    offset = data.find(FUSE_SENTINEL)
    if offset < 0:
        raise PackError('无法确认程序兼容性，已停止。')
    wire = data[offset + len(FUSE_SENTINEL):offset + len(FUSE_SENTINEL) + 20]
    # Electron FuseV1 option 4 = EnableEmbeddedAsarIntegrityValidation.
    # Refuse, rather than disable or modify, executable integrity protection.
    if len(wire) < 7 or wire[0] != 1 or wire[1] < 5 or wire[6] != ord('0'):
        raise PackError('此程序启用了资源完整性保护，语言包不会修改或关闭该保护。')


def assert_closed():
    if os.name != 'nt':
        raise PackError('安装与恢复功能仅支持 Windows。')
    result = subprocess.run(['tasklist.exe', '/FI', 'IMAGENAME eq Antigravity.exe', '/FO', 'CSV', '/NH'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    rows = csv.reader(io.StringIO(result.stdout.decode('utf-8', errors='replace')))
    if any(row and row[0].lower() == 'antigravity.exe' for row in rows):
        raise PackError('请先保存工作，并从 Antigravity 的退出菜单或系统托盘完全退出，再重新运行。语言包不会强行关闭应用。')


def atomic_write(path, data):
    fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextlib.contextmanager
def lock(resources):
    lockfile = resources / '.antigravity-zh-cn.lock'
    try:
        handle = lockfile.open('xb')
    except FileExistsError as error:
        raise PackError('另一个语言包操作正在进行，或上次运行中断。请查看说明中的锁文件处理方法。') from error
    try:
        with handle:
            handle.write(str(os.getpid()).encode('ascii'))
        yield
    finally:
        lockfile.unlink(missing_ok=True)


def read_state(resources):
    path = resources / STATE
    return json.loads(path.read_text('utf-8')) if path.exists() else None


def backup_path(resources, state):
    name = state['backupFile']
    if Path(name).name != name or not name.startswith('app.asar.zh-cn.original.'):
        raise PackError('备份记录路径不合法。')
    candidate = resources / name
    if candidate.resolve().parent != resources.resolve():
        raise PackError('备份文件必须位于当前资源目录内。')
    return candidate


def install(folder):
    resources = folder / 'resources'
    archive = resources / 'app.asar'
    assert_supported_executable(folder)
    with lock(resources):
        current = archive.read_bytes()
        state = read_state(resources)
        if state and digest(current) == state['patchedSha256']:
            print('简体中文语言包已经安装，无需重复操作。')
            return
        if state:
            raise PackError('检测到已有安装记录或应用更新。请运行“恢复英文”处理记录后再安装；不会覆盖更新后的程序。')
        patched, version = build(current)
        backup = resources / ('app.asar.zh-cn.original.' + digest(current)[:16])
        if backup.exists():
            if backup.read_bytes() != current:
                raise PackError('现有备份与原文件不一致，已停止。')
        else:
            # Exclusive creation: never overwrite an existing original backup.
            with backup.open('xb') as stream:
                stream.write(current)
                stream.flush()
                os.fsync(stream.fileno())
        if digest(backup.read_bytes()) != digest(current):
            raise PackError('备份校验失败，未修改程序。')
        state = {
            'packVersion': load_manifest()['version'], 'appVersion': version,
            'originalSha256': digest(current), 'patchedSha256': digest(patched),
            'backupFile': backup.name,
        }
        atomic_write(resources / STATE, json.dumps(state, ensure_ascii=False, indent=2).encode('utf-8'))
        # Recheck immediately before replacing: another updater must not be overwritten.
        assert_closed()
        if archive.read_bytes() != current:
            raise PackError('程序文件在安装期间发生变化，已停止。请运行“恢复英文”整理记录。')
        atomic_write(archive, patched)
        if digest(archive.read_bytes()) != state['patchedSha256']:
            atomic_write(archive, current)
            raise PackError('安装校验失败，已恢复原文件。')
        print('安装完成。重新打开 Antigravity 即可显示简体中文。')
        print('原文件备份：' + str(backup))


def restore(folder):
    resources = folder / 'resources'
    archive = resources / 'app.asar'
    with lock(resources):
        state = read_state(resources)
        if not state:
            print('未找到本语言包的安装记录；没有修改任何文件。')
            return
        current = archive.read_bytes()
        current_hash = digest(current)
        if current_hash == state['originalSha256']:
            (resources / STATE).unlink()
            print('程序已是原版，已整理安装记录。原文件备份保留。')
            return
        if current_hash != state['patchedSha256']:
            # An application update supersedes this patch. Never downgrade it.
            header, payload = parse_archive(current)
            if MARKER in get_file(header, payload, 'dist/preload.js'):
                raise PackError('程序在汉化后又被修改，不能安全覆盖。请保留备份并手动检查。')
            (resources / STATE).unlink()
            print('应用已更新或被其他程序替换。本汉化补丁已不在当前程序中；仅清理旧记录，未覆盖当前版本。')
            return
        backup = backup_path(resources, state)
        if not backup.exists() or digest(backup.read_bytes()) != state['originalSha256']:
            raise PackError('原文件备份缺失或校验不通过，未执行恢复。')
        original = backup.read_bytes()
        assert_closed()
        if archive.read_bytes() != current:
            raise PackError('程序文件在恢复期间发生变化，已停止。')
        atomic_write(archive, original)
        if digest(archive.read_bytes()) != state['originalSha256']:
            raise PackError('恢复后的文件校验失败，请保留备份并重装官方应用。')
        (resources / STATE).unlink()
        print('已恢复原始英文界面。重新打开 Antigravity 即可。原文件备份保留。')


def status(folder):
    resources = folder / 'resources'
    data = (resources / 'app.asar').read_bytes()
    header, payload = parse_archive(data)
    version = json.loads(get_file(header, payload, 'package.json')).get('version')
    preload = get_file(header, payload, 'dist/preload.js')
    state = read_state(resources)
    print('安装位置：' + str(folder))
    print('程序版本：' + str(version))
    print('语言包：' + ('已安装' if MARKER in preload else '未安装'))
    if state:
        print('语言包版本：' + str(state.get('packVersion', '未知')))
        print('安装记录：' + ('与当前程序一致' if digest(data) == state['patchedSha256'] else '程序已变化，请运行恢复英文整理记录'))
    print('支持版本：' + ', '.join(load_manifest()['supportedAppVersions']))


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='Antigravity 桌面版简体中文语言包（离线、可恢复）')
    parser.add_argument('action', choices=['install', 'restore', 'status', 'build'])
    parser.add_argument('--app-dir', help='Antigravity 安装目录')
    parser.add_argument('--output', help='build 模式生成测试资源文件的位置')
    args = parser.parse_args()
    try:
        folder = app_dir(args.app_dir)
        if args.action == 'status':
            status(folder)
        elif args.action == 'build':
            if not args.output:
                raise PackError('build 模式必须指定 --output；该模式不会安装语言包。')
            target = Path(args.output).resolve()
            if folder == target or folder in target.parents:
                raise PackError('build 模式不能写入应用安装目录。')
            assert_supported_executable(folder)
            patched, version = build((folder / 'resources/app.asar').read_bytes())
            atomic_write(target, patched)
            print(f'已生成 {version} 的测试资源文件，未修改已安装的程序：{target}')
        else:
            assert_closed()
            if args.action == 'install':
                install(folder)
            else:
                restore(folder)
        return 0
    except (PackError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('未完成：' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
