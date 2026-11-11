#!/usr/bin/env python3
# =============================================================
# app.py — Backend REST API "Team Profile Showcase" (Studi Kasus 10)
# Hanya memakai library bawaan Python (tanpa Flask/Django),
# sesuai ketentuan "tanpa framework berat".
#
# Kontrak API (sesuai kesepakatan tim):
#   GET    /members           -> 200 + array member
#   POST   /members           -> 201 + member yang baru ditambah
#                                400 {"error": "..."} kalau JSON rusak / field kurang
#   PUT    /members?index=X   -> 200 + member yang sudah diperbarui (edit profil & kegiatan)
#                                400 kalau data tidak valid / NIM diubah, 404 kalau index tidak ada
#   DELETE /members?index=X   -> 200 {"message": "..."}
#                                400 kalau index bukan angka, 404 kalau index tidak ada
#   POST   /uploads           -> 201 {"url": "/api/uploads/<nama>.jpg"} (unggah foto kegiatan)
#   GET    /uploads/<nama>    -> file foto kegiatan
#   PUT/DELETE juga menerima ?nim=X; If-Match berisi _version untuk menolak perubahan usang.
#   Penyimpanan rusak/tidak tersedia -> 503, tanpa menimpa data lama.
#   Format 1 member: {"name": "...", "nim": "...", "role": "...", "skills": ["...", "..."]}
#   + field opsional dari form frontend: "soft_skills" (array), "bio", "email", "github",
#     "activities" (array kegiatan: category, title, period, description, photo)
# =============================================================

import json
import os
import re
import threading
import uuid
import hashlib
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from functools import wraps
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# ---------- Konfigurasi ----------
# Folder ini nanti "ditempeli" Named Volume team-profile-data,
# jadi file JSON-nya tetap aman walaupun kontainer dihapus.
DATA_DIR = os.environ.get("DATA_DIR", "/var/lib/backend_data")
DATA_FILE = os.path.join(DATA_DIR, "team_members.json")
PORT = int(os.environ.get("PORT", "5000"))

# Foto kegiatan disimpan di subfolder "uploads" di dalam volume yang sama,
# jadi ikut aman saat kontainer backend dihapus (Data Immunity).
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024            # batas ukuran 1 foto: 5 MB
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

# Pola nama file foto: 32 karakter acak (huruf a-f & angka) + ekstensi.
# Dipakai untuk mencegah orang membaca/menghapus file lain (misal "../team_members.json").
PHOTO_URL_RE = re.compile(r"/api/uploads/([a-f0-9]{32}\.(?:jpg|png|webp))")
UPLOAD_PATH_RE = re.compile(r"/uploads/([a-f0-9]{32}\.(?:jpg|png|webp))")

# Kategori kegiatan yang boleh dipakai (harus sama dengan menu di frontend)
ACTIVITY_CATEGORIES = ("project", "organisasi", "eksternal")
MAX_ACTIVITIES = 50                            # batas jumlah kegiatan per anggota

# Lock = "kunci pintu" supaya dua request yang datang bersamaan
# tidak menulis file JSON di waktu yang sama (bisa bikin file rusak).
lock = threading.Lock()
github_cache = {}
github_cache_lock = threading.Lock()
GITHUB_CACHE_SECONDS = 300
GITHUB_PAGE_SIZE = 12


class GithubError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


def github_projects(username, page):
    key = (username.lower(), page)
    with github_cache_lock:
        cached = github_cache.get(key)
        if cached and time.monotonic() - cached[0] < GITHUB_CACHE_SECONDS:
            return cached[1]
    request = Request(
        f"https://api.github.com/users/{quote(username)}/repos?type=owner&sort=pushed&direction=desc&per_page={GITHUB_PAGE_SIZE}&page={page}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Team-Portfolio",
                 "X-GitHub-Api-Version": "2026-03-10"},
    )
    try:
        with urlopen(request, timeout=8) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("Response too large")
            data = json.loads(raw)
            has_next = 'rel="next"' in response.headers.get("Link", "")
        if not isinstance(data, list) or any(not isinstance(repo, dict) for repo in data):
            raise ValueError("Expected repositories")
        repos = []
        for repo in data:
            full_name = repo.get("full_name", "")
            if not isinstance(full_name, str) or not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", full_name):
                raise ValueError("Invalid repository name")
            repos.append({
                "name": full_name.split("/", 1)[1], "full_name": full_name,
                "url": "https://github.com/" + full_name,
                "description": repo.get("description") if isinstance(repo.get("description"), str) else "",
                "language": repo.get("language") if isinstance(repo.get("language"), str) else "",
                "fork": repo.get("fork") is True,
                "archived": repo.get("archived") is True,
            })
    except HTTPError as exc:
        if exc.code == 404:
            raise GithubError(404, "Username GitHub tidak ditemukan") from exc
        if exc.code in (403, 429):
            raise GithubError(429, "GitHub membatasi permintaan. Coba lagi nanti.") from exc
        raise GithubError(502, "GitHub sedang tidak tersedia. Coba lagi nanti.") from exc
    except (URLError, TimeoutError, OSError):
        raise GithubError(502, "Tidak dapat terhubung ke GitHub. Periksa koneksi dan coba lagi.")
    except (ValueError, UnicodeDecodeError):
        raise GithubError(502, "Respons GitHub tidak valid. Coba lagi nanti.")
    result = {"username": username, "repositories": repos, "page": page, "has_next": has_next}
    with github_cache_lock:
        if len(github_cache) >= 128:
            github_cache.pop(next(iter(github_cache)))
        github_cache[key] = (time.monotonic(), result)
    return result


class StorageError(Exception):
    pass


def storage_guard(method):
    @wraps(method)
    def guarded(self):
        try:
            return method(self)
        except (StorageError, OSError):
            self.log_error("Storage operation failed")
            return self.send_json(503, {"error": "Penyimpanan tidak tersedia. Data lama tidak diubah; hubungi pengelola."})
    return guarded


def version_of(member):
    # Legacy records get a deterministic version until their first update.
    return member.get("_version") or hashlib.sha256(
        json.dumps(member, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


# ---------- Fungsi bantu baca/tulis file ----------
def load_members():
    """Only a missing file means a new, empty database."""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        raise StorageError("Cannot read member data") from exc
    if not isinstance(data, list):
        raise StorageError("Member data must be an array")
    seen = set()
    for member in data:
        cleaned, error = build_member(member)
        if error or cleaned["nim"] in seen:
            raise StorageError("Invalid member data")
        if "_version" in member and not isinstance(member["_version"], str):
            raise StorageError("Invalid member version")
        seen.add(cleaned["nim"])
    return data


def save_members(members):
    """Simpan daftar anggota ke team_members.json."""
    os.makedirs(DATA_DIR, exist_ok=True)
    # Tulis ke file sementara dulu, baru diganti -> file asli tidak rusak
    # kalau proses mati di tengah penulisan.
    tmp_file = DATA_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(members, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, DATA_FILE)


def clean_path(raw_path):
    """
    Ambil bagian path saja, lalu buang awalan /api kalau ada.
    Contoh: "/api/members?index=1" -> "/members"
    Gunanya: backend tetap jalan baik Nginx meneruskan "/api/members"
    maupun "/members" (tergantung ada/tidaknya garis miring di proxy_pass).
    """
    path = urlparse(raw_path).path
    if path.startswith("/api/"):
        path = path[len("/api"):]
    # buang garis miring di akhir: "/members/" -> "/members"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path


# ---------- Fungsi bantu foto kegiatan ----------
def looks_like_image(data, ext):
    """
    Cek "tanda tangan" di awal file (magic bytes), supaya yang diunggah
    benar-benar gambar, bukan file lain yang diberi nama .jpg.
    """
    if ext == "jpg":
        return data[:3] == b"\xff\xd8\xff"
    if ext == "png":
        return data[:8] == b"\x89PNG\r\n\x1a\n"
    if ext == "webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def photos_of(member):
    """Kumpulkan semua alamat foto kegiatan milik 1 anggota."""
    photos = set()
    for activity in member.get("activities", []) if isinstance(member, dict) else []:
        if isinstance(activity, dict) and activity.get("photo"):
            photos.add(activity["photo"])
    return photos


def delete_photos(urls):
    """Hapus file foto yang sudah tidak dipakai (misal kegiatannya dihapus)."""
    for url in urls:
        match = PHOTO_URL_RE.fullmatch(url or "")
        if match:
            try:
                os.remove(os.path.join(UPLOAD_DIR, match.group(1)))
            except OSError:
                pass  # file sudah tidak ada -> abaikan


# ---------- Validasi data anggota ----------
def build_activities(raw):
    """
    Cek & rapikan daftar kegiatan.
    Hasil: (daftar_kegiatan, None) kalau valid, atau (None, "pesan error").
    """
    if raw is None:
        return [], None
    if not isinstance(raw, list):
        return None, "Field 'activities' harus berupa array"
    if len(raw) > MAX_ACTIVITIES:
        return None, f"Maksimal {MAX_ACTIVITIES} kegiatan per anggota"

    result = []
    for number, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            return None, f"Kegiatan ke-{number} tidak valid"

        if any(not isinstance(item.get(field, ""), str)
               for field in ("category", "title", "period", "description", "photo")):
            return None, f"Kolom kegiatan ke-{number} harus berupa teks"
        category = item.get("category", "").strip()
        if category not in ACTIVITY_CATEGORIES:
            return None, f"Kategori kegiatan ke-{number} harus project, organisasi, atau eksternal"

        title = str(item.get("title", "") or "").strip()
        if not title:
            return None, f"Judul kegiatan ke-{number} wajib diisi"

        if len(title) > 120 or len(item.get("period", "")) > 60 or len(item.get("description", "")) > 1500:
            return None, f"Kolom kegiatan ke-{number} terlalu panjang"
        activity = {"category": category, "title": title}

        # Kolom opsional: waktu kegiatan & deskripsi (dipotong kalau terlalu panjang)
        period = str(item.get("period", "") or "").strip()
        if period:
            activity["period"] = period[:60]
        description = str(item.get("description", "") or "").strip()
        if description:
            activity["description"] = description[:1500]

        # Foto opsional, tapi kalau ada harus hasil unggahan lewat POST /uploads
        photo = str(item.get("photo", "") or "").strip()
        if photo:
            if not PHOTO_URL_RE.fullmatch(photo):
                return None, f"Foto kegiatan ke-{number} tidak valid"
            activity["photo"] = photo

        result.append(activity)
    return result, None


def build_member(data):
    """
    Cek & rapikan data 1 anggota dari JSON yang dikirim frontend.
    Dipakai bersama oleh POST (tambah) dan PUT (edit), supaya aturannya sama persis.
    Hasil: (member, None) kalau valid, atau (None, "pesan error") kalau tidak valid.
    """
    if not isinstance(data, dict):
        return None, "Body harus berupa objek JSON {...}"

    # a) Field teks wajib: name, nim, role tidak boleh kosong
    member = {}
    for field in ("name", "nim", "role"):
        value = data.get(field)
        if not isinstance(value, str):
            return None, f"Field '{field}' harus berupa teks"
        value = value.strip()
        if not value:
            return None, f"Field '{field}' wajib diisi"
        if len(value) > {"name": 80, "nim": 20, "role": 40}[field]:
            return None, f"Field '{field}' terlalu panjang"
        member[field] = value

    # NIM hanya boleh angka (sama dengan aturan di frontend)
    if not re.fullmatch(r"[0-9]+", member["nim"]):
        return None, "NIM hanya boleh berisi angka"

    # b) Field skills (hard skill): harus array ["...", "..."], minimal 1 skill.
    #    Sebagai cadangan, teks "Python, Docker" juga diterima lalu dipecah jadi array.
    skills = data.get("skills")
    if isinstance(skills, str):
        skills = skills.split(",")
    if not isinstance(skills, list):
        return None, "Field 'skills' wajib berupa array"
    if any(not isinstance(s, str) for s in skills):
        return None, "Setiap skill harus berupa teks"
    skills = [s.strip() for s in skills if s.strip()]
    if len(", ".join(skills)) > 200:
        return None, "Hard skill maksimal 200 karakter"
    if not skills:
        return None, "Field 'skills' minimal berisi 1 skill"
    member["skills"] = skills

    # c) Field OPSIONAL: soft_skills, contoh ["Komunikasi", "Kerja tim"].
    #    Kalau dikirim berupa teks "Komunikasi, Kerja tim" juga diterima lalu dipecah.
    soft = data.get("soft_skills")
    if isinstance(soft, str):
        soft = soft.split(",")
    if soft is not None and (not isinstance(soft, list) or any(not isinstance(s, str) for s in soft)):
        return None, "Field 'soft_skills' harus berupa array teks"
    if isinstance(soft, list):
        soft = [s.strip() for s in soft if s.strip()]
        if len(", ".join(soft)) > 200:
            return None, "Soft skill maksimal 200 karakter"
        if soft:
            member["soft_skills"] = soft

    # d) Field OPSIONAL lain: bio, email, github.
    #    Hanya disimpan kalau diisi (tidak wajib -> tidak ada error kalau kosong).
    for field in ("bio", "email", "github"):
        value = data.get(field, "")
        if not isinstance(value, str):
            return None, f"Field '{field}' harus berupa teks"
        value = value.strip()
        if len(value) > {"bio": 400, "email": 120, "github": 60}[field]:
            return None, f"Field '{field}' terlalu panjang"
        if field == "email" and value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            return None, "Format email tidak valid"
        if field == "github" and value:
            value = re.sub(r"^https?://(?:www\.)?github\.com/", "", value, flags=re.I).lstrip("@").rstrip("/")
            if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", value):
                return None, "Username GitHub tidak valid"
        if value:
            member[field] = value

    # e) Field OPSIONAL: activities (kegiatan/project dengan foto)
    activities, error = build_activities(data.get("activities"))
    if error:
        return None, error
    if activities:
        member["activities"] = activities

    return member, None


# ---------- Pengolah request (inti API) ----------
class Handler(BaseHTTPRequestHandler):

    def resolve_index(self, members):
        query = parse_qs(urlparse(self.path).query)
        if "nim" in query:
            index = next((i for i, m in enumerate(members) if m["nim"] == query["nim"][0]), -1)
        else:
            index, error = self.read_index()
            if error:
                self.send_json(400, {"error": error})
                return None
        if index < 0 or index >= len(members):
            self.send_json(404, {"error": "Profil tidak ditemukan"})
            return None
        expected = self.headers.get("If-Match")
        if expected is not None and expected != '"' + version_of(members[index]) + '"':
            self.send_json(409, {"error": "Profil telah berubah. Muat ulang halaman sebelum menyimpan atau menghapus."})
            return None
        return index

    # --- Fungsi bantu: kirim balasan dalam bentuk JSON ---
    # (Tidak perlu header CORS, karena frontend memanggil lewat Nginx /api/
    #  sehingga browser menganggapnya satu alamat yang sama.)
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)                       # contoh: 200, 201, 400, 404
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # --- Fungsi bantu: baca body request lalu ubah JSON -> dictionary Python ---
    # Hasil: (data, None) kalau berhasil, atau (None, "pesan error") kalau JSON rusak.
    def read_json_body(self):
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return None, "Content-Type harus application/json"
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return None, "Content-Length tidak valid"
        if length <= 0 or length > 256 * 1024:
            self.close_connection = True
            return None, "Body JSON kosong atau melebihi 256 KB"
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            return json.loads(raw.decode("utf-8")), None
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, "Body harus berupa JSON yang valid"

    # --- Fungsi bantu: ambil angka index dari "?index=X" ---
    # Hasil: (index, None) kalau valid, atau (None, "pesan error") kalau tidak ada / bukan angka.
    def read_index(self):
        query = parse_qs(urlparse(self.path).query)   # "index=2" -> {"index": ["2"]}
        if "index" not in query:
            return None, "Parameter 'index' wajib, contoh: /members?index=0"
        try:
            return int(query["index"][0]), None
        except ValueError:
            return None, "Parameter 'index' harus berupa angka"

    # ===================== GET =====================
    @storage_guard
    def do_GET(self):
        path = clean_path(self.path)

        if path == "/github/repos":
            query = parse_qs(urlparse(self.path).query)
            username = query.get("username", [""])[0]
            page_text = query.get("page", ["1"])[0]
            if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", username):
                return self.send_json(400, {"error": "Username GitHub tidak valid"})
            if not re.fullmatch(r"[0-9]{1,4}", page_text) or not 1 <= int(page_text) <= 1000:
                return self.send_json(400, {"error": "Halaman GitHub tidak valid"})
            try:
                return self.send_json(200, github_projects(username, int(page_text)))
            except GithubError as exc:
                return self.send_json(exc.status, {"error": exc.message})

        if path == "/members":
            with lock:
                members = load_members()
            # 200 = OK. Dikirim berupa array member
            return self.send_json(200, [dict(m, _version=version_of(m)) for m in members])

        if path == "/health":
            with lock:
                load_members()
            # Endpoint tambahan untuk stage "Health Check" di Jenkins
            return self.send_json(200, {"status": "ok"})

        # Foto kegiatan: /uploads/<32 karakter>.jpg
        match = UPLOAD_PATH_RE.fullmatch(path)
        if match:
            return self.send_photo(match.group(1))

        # Alamat lain tidak dikenal -> 404 Not Found
        return self.send_json(404, {"error": "Endpoint tidak ditemukan"})

    def send_photo(self, filename):
        file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.isfile(file_path):
            return self.send_json(404, {"error": "Foto tidak ditemukan"})
        with open(file_path, "rb") as f:
            data = f.read()
        ext = filename.rsplit(".", 1)[1]
        content_type = {v: k for k, v in IMAGE_TYPES.items()}[ext]
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        # Nama file tidak pernah berubah isinya, jadi browser boleh menyimpannya lama (cache)
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(data)

    # ===================== POST (TAMBAH) =====================
    @storage_guard
    def do_POST(self):
        path = clean_path(self.path)
        if path == "/uploads":
            return self.handle_upload()
        if path != "/members":
            return self.send_json(404, {"error": "Endpoint tidak ditemukan"})

        # 1) Baca body JSON. Kalau rusak -> 400 Bad Request
        data, error = self.read_json_body()
        if error:
            return self.send_json(400, {"error": error})

        # 2) Cek & rapikan isi data (aturan lengkapnya ada di build_member)
        member, error = build_member(data)
        if error:
            return self.send_json(400, {"error": error})

        # 3) Simpan: baca data lama -> cek NIM kembar -> tambah data baru -> tulis lagi
        with lock:
            members = load_members()
            # Halaman profil mencari anggota berdasarkan NIM, jadi NIM tidak boleh dobel
            if any(str(m.get("nim")) == member["nim"] for m in members if isinstance(m, dict)):
                return self.send_json(400, {"error": "NIM ini sudah terdaftar di tim"})
            member["_version"] = uuid.uuid4().hex
            members.append(member)
            save_members(members)

        # 201 = Created. Sesuai kesepakatan: balas dengan member yang baru ditambah
        return self.send_json(201, member)

    # ===================== POST /uploads (UNGGAH FOTO) =====================
    # Body request = isi file gambar apa adanya (bukan JSON),
    # dengan header Content-Type: image/jpeg, image/png, atau image/webp.
    def handle_upload(self):
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        ext = IMAGE_TYPES.get(content_type)
        if not ext:
            return self.send_json(400, {"error": "Foto harus berformat JPG, PNG, atau WEBP"})

        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0:
            return self.send_json(400, {"error": "File foto kosong"})
        if length > MAX_UPLOAD_BYTES:
            self.close_connection = True   # jangan baca file yang terlalu besar
            return self.send_json(413, {"error": "Ukuran foto maksimal 5 MB"})

        data = self.rfile.read(length)
        if len(data) != length:
            return self.send_json(400, {"error": "Unggahan foto tidak lengkap"})
        if not looks_like_image(data, ext):
            return self.send_json(400, {"error": "File yang diunggah bukan gambar yang valid"})

        # Nama file acak, supaya tidak bisa ditebak dan tidak bentrok
        filename = f"{uuid.uuid4().hex}.{ext}"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
            f.write(data)

        # 201 = Created. Alamat ini yang nanti disimpan di kolom "photo" kegiatan
        return self.send_json(201, {"url": f"/api/uploads/{filename}"})

    # ===================== PUT (EDIT PROFIL & KEGIATAN) =====================
    @storage_guard
    def do_PUT(self):
        if clean_path(self.path) != "/members":
            return self.send_json(404, {"error": "Endpoint tidak ditemukan"})

        # Validate before acquiring the storage lock; resolve identity and version inside it.
        data, error = self.read_json_body()
        if error:
            return self.send_json(400, {"error": error})
        member, error = build_member(data)
        if error:
            return self.send_json(400, {"error": error})

        # 3) Ganti data lama dengan data baru
        with lock:
            members = load_members()
            index = self.resolve_index(members)
            if index is None:
                return
            # NIM dipakai sebagai alamat halaman profil, jadi tidak boleh diubah lewat edit
            if str(members[index].get("nim")) != member["nim"]:
                return self.send_json(400, {"error": "NIM tidak boleh diubah"})
            old_photos = photos_of(members[index])
            member["_version"] = uuid.uuid4().hex
            members[index] = member
            save_members(members)
            # Foto dari kegiatan yang dihapus sudah tidak dipakai -> hapus filenya
            used = set().union(*(photos_of(m) for m in members))
            delete_photos(old_photos - used)

        # 200 = OK. Balas dengan data yang sudah diperbarui
        return self.send_json(200, member)

    # ===================== DELETE =====================
    @storage_guard
    def do_DELETE(self):
        upload = UPLOAD_PATH_RE.fullmatch(clean_path(self.path))
        if upload:
            url = "/api/uploads/" + upload.group(1)
            with lock:
                members = load_members()
                if any(url in photos_of(m) for m in members):
                    return self.send_json(409, {"error": "Foto masih digunakan"})
                delete_photos({url})
            return self.send_json(200, {"message": "Foto dihapus"})
        if clean_path(self.path) != "/members":
            return self.send_json(404, {"error": "Endpoint tidak ditemukan"})

        # Ambil index dari "?index=X". Tidak ada / bukan angka -> 400
        with lock:
            members = load_members()
            # Index di luar jangkauan -> data tidak ada -> 404
            index = self.resolve_index(members)
            if index is None:
                return
            removed = members.pop(index)      # buang data di posisi index
            save_members(members)
            used = set().union(*(photos_of(m) for m in members))
            delete_photos(photos_of(removed) - used)

        # 200 = OK. Sesuai kesepakatan: balas {"message": "..."}
        return self.send_json(200, {"message": f"Anggota '{removed['name']}' berhasil dihapus"})


# ---------- Menyalakan server ----------
if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    # "0.0.0.0" = terima koneksi dari mana saja. WAJIB di Docker!
    # Kalau "127.0.0.1", Nginx/Jenkins tidak bisa mengakses backend.
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Backend jalan di port {PORT}, data disimpan di {DATA_FILE}", flush=True)
    server.serve_forever()
