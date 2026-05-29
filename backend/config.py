import os
import ctypes

BASE_DIR= os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "ledger_v2.db")

LEGACY_EXCEL = os.path.join(BASE_DIR, "Laldia", "Laldia港湾微信群台账.xlsx")
LEGACY_WX_JSON_DIR = os.path.join(BASE_DIR, "Laldia", "wx_json")
LEGACY_LEDGER_JSON = os.path.join(BASE_DIR, "Laldia", "Laldia微信群台账.json")
LEGACY_DAILY_SUMMARY = os.path.join(BASE_DIR, "Laldia", "每日摘要")
LEGACY_ARCHIVE_DIR = os.path.join(BASE_DIR, "Laldia", "微信群归档")
LEGACY_ARCHIVE_LEGACY_DIR = os.path.join(BASE_DIR, "Laldia", "微信群归档_legacy")

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

FLASK_HOST = "127.0.0.1"
FLASK_PORT = 8888

# WeChat local data directory (for file:// links)
WX_DATA_DIR = None
_WX_FILE_ROOT = None


def _detect_wx_data_dir():
    global WX_DATA_DIR, _WX_FILE_ROOT
    # Use cached path from wx-cli config instead of calling `wx init`
    wx_config = os.path.expanduser("~/.wx-cli/config.json")
    try:
        import json as _json
        with open(wx_config, "r") as f:
            cfg = _json.load(f)
        WX_DATA_DIR = cfg.get("db_dir", "")
    except Exception:
        pass
    if not WX_DATA_DIR or not os.path.isdir(WX_DATA_DIR):
        WX_DATA_DIR = os.path.expanduser("~/Documents/xwechat_files")
    for search_dir in (WX_DATA_DIR, os.path.dirname(WX_DATA_DIR)):
        if not os.path.isdir(search_dir):
            continue
        # Check if msg/file exists directly under search_dir
        direct = os.path.join(search_dir, "msg", "file")
        if os.path.isdir(direct):
            _WX_FILE_ROOT = direct
            break
        # Check for hash directories (each containing msg/file)
        try:
            for entry in os.listdir(search_dir):
                candidate = os.path.join(search_dir, entry, "msg", "file")
                if os.path.isdir(candidate):
                    _WX_FILE_ROOT = candidate
                    break
        except OSError:
            pass
        if _WX_FILE_ROOT:
            break


def get_wx_file_url(msg_date, filename):
    if not _WX_FILE_ROOT or not msg_date or not filename:
        return None
    yyyy_mm = msg_date[:7]
    file_path = os.path.join(_WX_FILE_ROOT, yyyy_mm, filename)
    if os.path.isfile(file_path):
        return "file:///" + file_path.replace("\\", "/")
    return None


def get_wx_file_path(msg_date, filename):
    if not _WX_FILE_ROOT or not msg_date or not filename:
        return None
    yyyy_mm = msg_date[:7]
    file_path = os.path.normpath(os.path.join(_WX_FILE_ROOT, yyyy_mm, filename))
    if os.path.isfile(file_path):
        return file_path
    return None


_WX_ATTACH_ROOT = None


def _detect_wx_attach_root():
    global _WX_ATTACH_ROOT
    if WX_DATA_DIR and os.path.isdir(WX_DATA_DIR):
        try:
            for entry in os.listdir(WX_DATA_DIR):
                candidate = os.path.join(WX_DATA_DIR, entry)
                if os.path.isdir(candidate) and os.path.isdir(os.path.join(candidate, "msg", "attach")):
                    _WX_ATTACH_ROOT = os.path.join(candidate, "msg", "attach")
                    break
        except OSError:
            pass


def find_image_dat(msg_date, timestamp=None):
    """Find .dat image file(s) for a given message date and optional timestamp."""
    if not _WX_ATTACH_ROOT or not msg_date:
        return []
    yyyy_mm = msg_date[:7]
    results = []
    try:
        for hash_dir in os.listdir(_WX_ATTACH_ROOT):
            img_dir = os.path.join(_WX_ATTACH_ROOT, hash_dir, yyyy_mm, "Img")
            if not os.path.isdir(img_dir):
                continue
            for f in os.listdir(img_dir):
                if not f.endswith('.dat'):
                    continue
                fpath = os.path.join(img_dir, f)
                if '_t.dat' in f or '_h.dat' in f:
                    continue
                if timestamp:
                    # Prefer filename as timestamp (WeChat dat filenames are Unix timestamps)
                    try:
                        file_ts = int(f.replace('.dat', ''))
                        delta = abs(file_ts - timestamp)
                    except ValueError:
                        delta = abs(os.path.getmtime(fpath) - timestamp)
                    results.append((delta, fpath))
                else:
                    results.append((0, fpath))
    except OSError:
        pass
    if timestamp:
        results.sort(key=lambda x: x[0])
    return [r[1] for r in results[:10]]


def decrypt_dat_file(filepath):
    """Try to decrypt a WeChat .dat file. Returns (bytes, extension) or (None, None)."""
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except OSError:
        return None, None

    if len(data) < 15:
        return None, None

    header = data[:6]

    # V1/V2 format: header = 07 08 56 31/32 08 07
    if header[:3] == bytes([0x07, 0x08, 0x56]) and header[5:6] == bytes([0x07]):
        return _decrypt_v2(data, filepath)

    # XOR format (legacy)
    return _decrypt_xor(data)


_cached_xor_key = None


def _derive_xor_key(filepath):
    """Derive XOR key from a V2-format thumbnail file. Result is cached."""
    global _cached_xor_key
    if _cached_xor_key is not None:
        return _cached_xor_key

    thumb_dir = os.path.dirname(filepath)
    main_name = os.path.basename(filepath).replace('.dat', '')
    try:
        for f in os.listdir(thumb_dir):
            if '_t.dat' in f and f.startswith(main_name[:8]):
                thumb_path = os.path.join(thumb_dir, f)
                with open(thumb_path, 'rb') as fp:
                    td = fp.read()
                # Thumbnail also V2, same XOR key. JPEG thumb tails end with FF D9.
                if len(td) > 10:
                    k1 = td[-2] ^ 0xFF
                    k2 = td[-1] ^ 0xD9
                    if k1 == k2:
                        _cached_xor_key = k1
                        return _cached_xor_key
    except OSError:
        pass

    # Fallback: try any thumbnail in same dir
    try:
        for f in os.listdir(thumb_dir):
            if '_t.dat' in f:
                thumb_path = os.path.join(thumb_dir, f)
                with open(thumb_path, 'rb') as fp:
                    td = fp.read()
                if len(td) > 10:
                    k1 = td[-2] ^ 0xFF
                    k2 = td[-1] ^ 0xD9
                    if k1 == k2:
                        _cached_xor_key = k1
                        return _cached_xor_key
    except OSError:
        pass

    return 0x08


_WX_IMAGE_AES_KEY = None


def _load_aes_key():
    global _WX_IMAGE_AES_KEY
    if _WX_IMAGE_AES_KEY:
        return _WX_IMAGE_AES_KEY
    key = os.environ.get('WX_IMAGE_AES_KEY', '')
    if key and len(key) == 16:
        _WX_IMAGE_AES_KEY = key.encode('ascii')
        return _WX_IMAGE_AES_KEY
    key_file = os.path.join(BASE_DIR, '.wx_image_key')
    if os.path.isfile(key_file):
        try:
            with open(key_file, 'r') as f:
                key = f.read().strip()
            if len(key) == 16:
                _WX_IMAGE_AES_KEY = key.encode('ascii')
                return _WX_IMAGE_AES_KEY
        except Exception:
            pass
    return None


_voip_engine_dll = None


class _WxamConfig(ctypes.Structure):
    _fields_ = [('mode', ctypes.c_int)]


def _get_voip_engine():
    global _voip_engine_dll
    if _voip_engine_dll is not None:
        return _voip_engine_dll
    import glob as _glob
    patterns = [
        r'C:\Program Files\Tencent\Weixin\*\VoipEngine.dll',
        r'C:\Program Files (x86)\Tencent\Weixin\*\VoipEngine.dll',
    ]
    for pat in patterns:
        hits = _glob.glob(pat)
        if hits:
            try:
                _voip_engine_dll = ctypes.CDLL(hits[0])
                return _voip_engine_dll
            except Exception:
                pass
    return None


def _heic_to_jpeg(heic_data):
    """Convert HEIC bytes to JPEG bytes. Returns bytes or None."""
    try:
        import io as _io
        import pillow_heif
        pillow_heif.register_heif_opener()
        from PIL import Image
        img = Image.open(_io.BytesIO(heic_data))
        out = _io.BytesIO()
        img.convert('RGB').save(out, 'JPEG', quality=85)
        return out.getvalue()
    except Exception:
        return None


def _decompress_wxam(wxgf_data):
    """Decompress WxAM/wxgf data via VoipEngine.dll. Returns (decompressed_bytes, ext) or (None, None)."""
    dll = _get_voip_engine()
    if not dll:
        return None, None

    func = dll.wxam_dec_wxam2pic_5
    func.restype = ctypes.c_int64
    func.argtypes = [
        ctypes.c_void_p, ctypes.c_int,
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
        ctypes.c_void_p,
    ]

    max_size = 64 * 1024 * 1024
    input_buf = ctypes.create_string_buffer(wxgf_data, len(wxgf_data))
    output_buf = ctypes.create_string_buffer(max_size)
    output_size = ctypes.c_int(max_size)

    # Mode priority: 4 (HEIC, native WeChat format) -> 0 (JPEG) -> 1 (PNG) -> 3 (GIF)
    # Mode 2 intentionally skipped — it crashes VoipEngine.dll on some files and produces same PNG output as mode 1
    for mode in [4, 0, 1, 3]:
        config = _WxamConfig()
        config.mode = mode
        output_size.value = max_size
        try:
            ret = func(
                ctypes.cast(input_buf, ctypes.c_void_p),
                len(wxgf_data),
                ctypes.cast(output_buf, ctypes.c_void_p),
                ctypes.byref(output_size),
                ctypes.cast(ctypes.byref(config), ctypes.c_void_p),
            )
            if ret == 0 and 0 < output_size.value < max_size:
                img_data = output_buf.raw[:output_size.value]
                if b'ftypheic' in img_data[:32]:
                    jpg_data = _heic_to_jpeg(img_data)
                    if jpg_data:
                        return jpg_data, 'jpg'
                if img_data[:2] == bytes([0xFF, 0xD8]):
                    return img_data, 'jpg'
                if img_data[:4] == bytes([0x89, 0x50, 0x4E, 0x47]):
                    return img_data, 'png'
                if img_data[:3] == bytes([0x47, 0x49, 0x46]):
                    return img_data, 'gif'
        except Exception:
            continue
    return None, None


def _decrypt_v2(data, filepath=None):
    import os as _os
    aes_size = int.from_bytes(data[6:10], 'little')
    xor_size = int.from_bytes(data[10:14], 'little')
    header_size = 15

    if aes_size <= 0 or xor_size <= 0:
        return None, None
    if header_size + aes_size > len(data) or xor_size > len(data):
        return None, None

    aes_start = header_size
    aes_end = aes_start + aes_size
    xor_start = len(data) - xor_size
    xor_key = _derive_xor_key(filepath) if filepath else 0x08

    keys_to_try = []
    loaded_key = _load_aes_key()
    if loaded_key:
        keys_to_try.append(loaded_key)
    keys_to_try.append(b'cfcd208495d565ef')
    mem_key = _try_extract_aes_key()
    if mem_key:
        keys_to_try.insert(0, mem_key)

    for key in keys_to_try:
        try:
            from Crypto.Cipher import AES
            cipher = AES.new(key, AES.MODE_ECB)
            aes_data = data[aes_start:aes_end]
            if len(aes_data) % 16 != 0:
                continue
            decrypted = cipher.decrypt(aes_data)

            xor_segment = bytes([b ^ xor_key for b in data[xor_start:]])

            full = bytes(decrypted) + xor_segment

            # Check for WxAM compression (wxgf = 77 78 67 66)
            if full[:4] == bytes([0x77, 0x78, 0x67, 0x66]):
                img_data, img_ext = _decompress_wxam(full)
                if img_data:
                    return img_data, img_ext
                continue

            ext = _detect_image_format(full)
            if ext:
                return full, ext
        except Exception:
            continue

    return None, None


def _decrypt_xor(data):
    # Try common image formats to find XOR key
    magic_list = [
        (bytes([0xFF, 0xD8, 0xFF, 0xE0]), 'jpg'),
        (bytes([0xFF, 0xD8, 0xFF, 0xE1]), 'jpg'),
        (bytes([0x89, 0x50, 0x4E, 0x47]), 'png'),
        (bytes([0x47, 0x49, 0x46, 0x38]), 'gif'),
        (bytes([0x42, 0x4D]), 'bmp'),
    ]
    for magic, ext in magic_list:
        keys = [data[i] ^ magic[i] for i in range(len(magic))]
        if all(k == keys[0] for k in keys):
            key = keys[0]
            decoded = bytes([b ^ key for b in data])
            return decoded, ext
    return None, None


def _detect_image_format(data):
    if data[:2] == bytes([0xFF, 0xD8]):
        return 'jpg'
    if data[:4] == bytes([0x89, 0x50, 0x4E, 0x47]):
        return 'png'
    if data[:3] == bytes([0x47, 0x49, 0x46]):
        return 'gif'
    if data[:2] == bytes([0x42, 0x4D]):
        # Verify BMP header structure to avoid false positives
        if len(data) >= 14:
            bmp_size = int.from_bytes(data[2:6], 'little')
            bmp_reserved = int.from_bytes(data[6:10], 'little')
            bmp_offset = int.from_bytes(data[10:14], 'little')
            if bmp_size == len(data) and bmp_reserved == 0 and 54 <= bmp_offset < bmp_size:
                return 'bmp'
        return None
    if data[:4] == bytes([0x52, 0x49, 0x46, 0x46]):
        return 'webp'
    return None


_cached_aes_key = None
_key_tried_extract = False


def _try_extract_aes_key():
    """Try to extract V2 AES key from running WeChat process memory. Cached after first attempt."""
    global _cached_aes_key, _key_tried_extract
    if _key_tried_extract:
        return _cached_aes_key
    _key_tried_extract = True
    _cached_aes_key = _scan_wechat_memory_for_key()
    return _cached_aes_key


def _scan_wechat_memory_for_key():
    try:
        from pymem import Pymem
        import ctypes
        from ctypes import wintypes
        import re

        pm = Pymem('weixin.exe')
        pattern = bytes([0x07, 0x08, 0x56, 0x32, 0x08, 0x07])

        # Use VirtualQueryEx for memory scanning
        MEM_COMMIT = 0x1000

        class MEMORY_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('BaseAddress', ctypes.c_ulonglong),
                ('AllocationBase', ctypes.c_ulonglong),
                ('AllocationProtect', wintypes.DWORD),
                ('PartitionId', wintypes.WORD),
                ('RegionSize', ctypes.c_ulonglong),
                ('State', wintypes.DWORD),
                ('Protect', wintypes.DWORD),
                ('Type', wintypes.DWORD),
            ]

        kernel32 = ctypes.windll.kernel32
        VirtualQueryEx = kernel32.VirtualQueryEx
        VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_ulonglong,
                                   ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
        VirtualQueryEx.restype = ctypes.c_size_t

        handle = pm.process_handle
        addr = 0x10000
        region_limit = 200000
        scanned = 0

        while scanned < region_limit:
            mbi = MEMORY_BASIC_INFORMATION()
            result = VirtualQueryEx(handle, addr, ctypes.byref(mbi), ctypes.sizeof(mbi))
            if result == 0:
                break

            if mbi.State == MEM_COMMIT and 0 < mbi.RegionSize < 50 * 1024 * 1024:
                try:
                    region_data = pm.read_bytes(mbi.BaseAddress, mbi.RegionSize)
                    idx = 0
                    while True:
                        pos = region_data.find(pattern, idx)
                        if pos == -1:
                            break
                        real_addr = mbi.BaseAddress + pos
                        # Read 256 bytes around match, look for 16-byte ASCII key
                        search_start = max(0, real_addr - 256)
                        nearby = pm.read_bytes(search_start, 512)
                        for m in re.finditer(rb'[\x21-\x7e]{16}', nearby):
                            candidate = m.group()
                            if candidate not in (b'cfcd208495d565ef', b'0000000000000000'):
                                return candidate
                        idx = pos + 1
                except Exception:
                    pass

            addr = mbi.BaseAddress + mbi.RegionSize
            scanned += 1
    except Exception:
        pass
    return None


_detect_wx_data_dir()
_detect_wx_attach_root()


# Sync rate limiting (anti-detection)
# 模拟人类逐群查看节奏，防止被微信检测为外挂
# 可通过同名环境变量覆盖
import os as _os2
SYNC_DELAY_MIN = float(_os2.environ.get("WX_SYNC_DELAY_MIN", "3.0"))
SYNC_DELAY_MAX = float(_os2.environ.get("WX_SYNC_DELAY_MAX", "8.0"))
SYNC_BATCH_LIMIT = int(_os2.environ.get("WX_SYNC_BATCH_LIMIT", "200"))
WX_MIN_INTERVAL = float(_os2.environ.get("WX_MIN_INTERVAL", "1.5"))
WX_DAILY_CALL_LIMIT = int(_os2.environ.get("WX_DAILY_CALL_LIMIT", "200"))
SYNC_API_TOKEN = _os2.environ.get("SYNC_API_TOKEN", "wxdashboard-sync")

# 文件自动下载目录，环境变量 WX_DOWNLOAD_DIR 可覆盖
DOWNLOAD_DIR = _os2.environ.get("WX_DOWNLOAD_DIR", os.path.join(BASE_DIR, ".Download"))

# 本人微信名/邮箱关键词，提取时跳过自己的联系信息
MY_WECHAT_NAME = _os2.environ.get("MY_WECHAT_NAME", "彭康")
MY_EMAIL_KEYWORD = _os2.environ.get("MY_EMAIL_KEYWORD", "pengkang")
