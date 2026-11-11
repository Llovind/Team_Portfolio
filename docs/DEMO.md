# Rencana video demo UTS (5-8 menit)

Target durasi: sekitar 7 menit. Gunakan hasil nyata pada Docker dan Jenkins; jangan memakai preview Python sebagai bukti containerization. Rekam layar, terminal, dan penjelasan singkat tiap anggota.

| Waktu | Demo | Bukti di layar |
| --- | --- | --- |
| 0:00-0:40 | Perkenalan tiga anggota, NIM, dan studi kasus 10 | README dan diagram arsitektur |
| 0:40-2:00 | UI/API: tambah profil, skill, edit, kegiatan/foto, repo GitHub, hapus entri uji | Browser localhost:8082 dan respons JSON `/api/members` |
| 2:00-2:45 | Docker: service, bridge network, named volume, bind mount | `docker compose ps`, inspect network/volume |
| 2:45-3:45 | Data immunity: hapus backend, buat ulang, profil dan foto tetap ada | Container ID sebelum/sesudah, UI dengan data yang sama |
| 3:45-4:20 | Bind mount: ubah sedikit teks frontend, refresh tanpa rebuild | Editor dan perubahan terlihat di browser |
| 4:20-6:30 | CI/CD: commit/push main, webhook, lima stage, hasil deploy | SHA commit, delivery 2xx, stage hijau, UI terbaru |
| 6:30-7:00 | Ringkasan bukti dan lokasi repository | README, URL repo dan video |

## Pemeriksaan sebelum rekaman

1. Docker Desktop aktif, preview Python pada port 8082 dihentikan, stack Compose healthy.
2. Profil anggota dan foto sudah ada di named volume utama. Simpan backup data bila diperlukan.
3. Uji terisolasi sudah berhasil: `python -B tools/verify_docker.py --github-username Llovind`.
4. Job Jenkins dan webhook aktif, agent punya label `team-portfolio`, sudah ada build manual hijau.
5. Browser GitHub/Jenkins sudah login; sembunyikan token, password, dan layar credentials saat merekam.

## Perintah untuk bukti Docker

```powershell
docker compose ps
docker network inspect app-net
docker volume inspect team-profile-data
docker inspect team-backend --format '{{.Id}}'
docker compose rm -s -f backend
docker compose up -d --no-deps --wait --wait-timeout 120 backend
docker inspect team-backend --format '{{.Id}}'
```

Container ID harus berubah. Tunggu resolver Nginx hingga 10 detik bila perlu, lalu perlihatkan profil dan foto yang tetap ada. Perintah ini menghapus container backend utama untuk demonstrasi tetapi mempertahankan volume. Jangan menambahkan `--volumes` atau menghapus volume.

## Perubahan kecil untuk membuktikan CI/CD

Ubah satu kalimat yang terlihat di `frontend/index.html`, lalu commit dan push ke `main` setelah semua perubahan proyek siap. Tampilkan push di terminal, webhook baru, build otomatis dengan SHA yang sama, dan kalimat yang berubah pada aplikasi Docker. Jangan menekan Build Now untuk bagian yang diklaim sebagai auto-trigger.

## Sebelum pengumpulan

- Pastikan GitHub memiliki app.py, index.html, Dockerfile, docker-compose.yml, Jenkinsfile, README, dan seluruh file pendukung di folder masing-masing.
- Tambahkan URL video sungguhan ke README setelah diunggah dan uji izin aksesnya.
- Perbarui status verifikasi README berdasarkan hasil yang benar-benar diperoleh.
- Kumpulkan URL repository dan video melalui LMS sesuai instruksi dosen.
