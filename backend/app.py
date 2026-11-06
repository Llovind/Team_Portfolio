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
#   DELETE /members?index=X   -> 200 {"message": "..."}
#                                400 kalau index bukan angka, 404 kalau index tidak ada
#   Format 1 member: {"name": "...", "nim": "...", "role": "...", "skills": ["...", "..."]}
#   + field opsional dari form frontend: "soft_skills" (array), "bio", "email", "github"
# =============================================================

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# ---------- Konfigurasi ----------
# Folder ini nanti "ditempeli" Named Volume team-profile-data,
# jadi file JSON-nya tetap aman walaupun kontainer dihapus.
DATA_DIR = os.environ.get("DATA_DIR", "/var/lib/backend_data")
DATA_FILE = os.path.join(DATA_DIR, "team_members.json")
PORT = int(os.environ.get("PORT", "5000"))

# Lock = "kunci pintu" supaya dua request yang datang bersamaan
# tidak menulis file JSON di waktu yang sama (bisa bikin file rusak).
lock = threading.Lock()


# ---------- Fungsi bantu baca/tulis file ----------
def load_members():
    """Baca isi team_members.json. Kalau file belum ada/rusak -> daftar kosong."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_members(members):
    """Simpan daftar anggota ke team_members.json."""
    os.makedirs(DATA_DIR, exist_ok=True)
    # Tulis ke file sementara dulu, baru diganti -> file asli tidak rusak
    # kalau proses mati di tengah penulisan.
    tmp_file = DATA_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(members, f, ensure_ascii=False, indent=2)
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


# ---------- Pengolah request (inti API) ----------
class Handler(BaseHTTPRequestHandler):

    # --- Fungsi bantu: kirim balasan dalam bentuk JSON ---
    # (Tidak perlu header CORS, karena frontend memanggil lewat Nginx /api/
    #  sehingga browser menganggapnya satu alamat yang sama.)
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)                       # contoh: 200, 201, 400, 404
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ===================== GET =====================
    def do_GET(self):
        path = clean_path(self.path)

        if path == "/members":
            with lock:
                members = load_members()
            # 200 = OK. Dikirim berupa array member
            return self.send_json(200, members)

        if path == "/health":
            # Endpoint tambahan untuk stage "Health Check" di Jenkins
            return self.send_json(200, {"status": "ok"})

        # Alamat lain tidak dikenal -> 404 Not Found
        return self.send_json(404, {"error": "Endpoint tidak ditemukan"})

    # ===================== POST =====================
    def do_POST(self):
        if clean_path(self.path) != "/members":
            return self.send_json(404, {"error": "Endpoint tidak ditemukan"})

        # 1) Baca "body" request (data yang dikirim frontend)
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b""

        # 2) Ubah teks JSON -> dictionary Python. Kalau gagal -> 400 Bad Request
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self.send_json(400, {"error": "Body harus berupa JSON yang valid"})
        if not isinstance(data, dict):
            return self.send_json(400, {"error": "Body harus berupa objek JSON {...}"})

        # 3) Cek field teks wajib: name, nim, role tidak boleh kosong
        member = {}
        for field in ("name", "nim", "role"):
            value = str(data.get(field, "")).strip()
            if not value:
                return self.send_json(400, {"error": f"Field '{field}' wajib diisi"})
            member[field] = value

        # NIM hanya boleh angka (sama dengan aturan di frontend)
        if not member["nim"].isdigit():
            return self.send_json(400, {"error": "NIM hanya boleh berisi angka"})

        # 4) Cek field skills: harus array ["...", "..."], minimal 1 skill.
        #    Sebagai cadangan, teks "Python, Docker" juga diterima lalu dipecah jadi array.
        skills = data.get("skills")
        if isinstance(skills, str):
            skills = skills.split(",")
        if not isinstance(skills, list):
            return self.send_json(400, {"error": "Field 'skills' wajib berupa array"})
        skills = [str(s).strip() for s in skills if str(s).strip()]
        if not skills:
            return self.send_json(400, {"error": "Field 'skills' minimal berisi 1 skill"})
        member["skills"] = skills

        # 4b) Field OPSIONAL: soft_skills, contoh ["Komunikasi", "Kerja tim"].
        #     Kalau dikirim berupa teks "Komunikasi, Kerja tim" juga diterima lalu dipecah.
        soft = data.get("soft_skills")
        if isinstance(soft, str):
            soft = soft.split(",")
        if isinstance(soft, list):
            soft = [str(s).strip() for s in soft if str(s).strip()]
            if soft:
                member["soft_skills"] = soft

        # 5) Field OPSIONAL dari form frontend: bio, email, github.
        #    Hanya disimpan kalau diisi (tidak wajib -> tidak ada error kalau kosong).
        for field in ("bio", "email", "github"):
            value = str(data.get(field, "") or "").strip()
            if value:
                member[field] = value

        # 6) Simpan: baca data lama -> cek NIM kembar -> tambah data baru -> tulis lagi
        with lock:
            members = load_members()
            # Halaman profil mencari anggota berdasarkan NIM, jadi NIM tidak boleh dobel
            if any(str(m.get("nim")) == member["nim"] for m in members if isinstance(m, dict)):
                return self.send_json(400, {"error": "NIM ini sudah terdaftar di tim"})
            members.append(member)
            save_members(members)

        # 201 = Created. Sesuai kesepakatan: balas dengan member yang baru ditambah
        return self.send_json(201, member)

    # ===================== DELETE =====================
    def do_DELETE(self):
        if clean_path(self.path) != "/members":
            return self.send_json(404, {"error": "Endpoint tidak ditemukan"})

        # Ambil query string: "index=2" -> {"index": ["2"]}
        query = parse_qs(urlparse(self.path).query)
        if "index" not in query:
            return self.send_json(400, {"error": "Parameter 'index' wajib, contoh: /members?index=0"})

        # Index bukan angka -> 400
        try:
            index = int(query["index"][0])
        except ValueError:
            return self.send_json(400, {"error": "Parameter 'index' harus berupa angka"})

        with lock:
            members = load_members()
            # Index di luar jangkauan -> data tidak ada -> 404
            if index < 0 or index >= len(members):
                return self.send_json(404, {"error": f"Data dengan index {index} tidak ditemukan"})
            removed = members.pop(index)      # buang data di posisi index
            save_members(members)

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