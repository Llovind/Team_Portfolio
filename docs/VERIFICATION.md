# Hasil verifikasi proyek

## Tes aplikasi

- Python: 17 tes API/release lulus, termasuk stale/simultaneous edits, korupsi storage, kegagalan write, persistence server, foto bersama, GitHub API mock, dan snapshot release.
- JavaScript: 15 tes frontend lulus, termasuk header versi, timeout/retry, dialog, pagination, pergantian akun GitHub, dan showcase maksimal tiga repo.
- Syntax Python diperiksa untuk backend, tools, dan tests; konfigurasi Compose valid.

## Uji integrasi Docker aktual

Dijalankan pengguna dari PowerShell lokal pada 12 November 2026:

```powershell
python -B tools/verify_docker.py --github-username Llovind
```

Laporan lokal `artifacts/docker-verification.json` menunjukkan project sementara `team-test-302a5f6c8e`, status `passed`, dan cleanup exit code `0`. Folder artifacts diabaikan Git karena berisi hasil lokal; ringkasan ini mencatat bukti yang sudah diperiksa.

| Pemeriksaan | Hasil |
| --- | --- |
| Resource test terpisah dari stack utama | PASS |
| Nginx UI dan proxy ke backend melalui service DNS | PASS |
| Named volume terpasang pada `/var/lib/backend_data` | PASS |
| Custom bridge network | PASS |
| Bind mount langsung memperlihatkan perubahan tanpa rebuild | PASS |
| Profil dan foto bertahan setelah container backend dihapus/dibuat ulang | PASS |
| Fetch GitHub sungguhan melalui backend | PASS |
| Container, network, dan volume test dibersihkan | PASS |

## Belum diverifikasi

- Eksekusi Jenkinsfile oleh Jenkins dan lima stage hijau.
- Webhook GitHub yang benar-benar memicu build untuk commit `main`.
- Deployment dari snapshot Jenkins; tes lokal membuktikan isolasi salinan rilis, bukan eksekusi pipeline.
- Video demo 5-8 menit dan URL video yang dapat diakses dosen.

Jangan mengubah status di atas menjadi lulus tanpa bukti baru.
