# Hasil verifikasi proyek

## Tes aplikasi

- Python: 26 tes API/release/recovery/webhook proxy lulus pada build Jenkins #4, termasuk stale/simultaneous edits, korupsi storage, kegagalan write, persistence server, foto bersama, GitHub API mock, snapshot release, dan pembatasan proxy webhook.
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

- Video demo 5-8 menit dan URL video yang dapat diakses dosen.

Jangan mengubah status di atas menjadi lulus tanpa bukti baru.

## Pipeline Jenkins aktual

Console output build **#3**, dipicu manual oleh `admin`, menunjukkan **Finished: SUCCESS** untuk commit `274c896ecbb6399b7897c98c7c8d9305e6d02107` (`Remove optional Timestamper dependency`). Lima stage Checkout, Syntax Check, Build Image, Automated Deployment, dan Health Check selesai. Python menjalankan 22 tes dan Node menjalankan 15 tes; semuanya lulus.

Deployment menggunakan snapshot `.deployments/build-3`, dengan bind source pada host Docker di volume `jenkins-data`. `team-backend` dan `team-frontend` healthy. Frontend dipublikasikan pada `127.0.0.1:8082`; health check berhasil untuk seluruh halaman/aset utama, `/api/health`, dan `/api/members` melalui Nginx.

## Webhook dan auto-deployment aktual

Build **#4** menunjukkan pemicu **Started by GitHub push by Llovind**, checkout commit `7b2fd87ae744725e3090196b4c86c18d5f32f85c` (`Verify GitHub webhook deployment`), dan hasil **Finished: SUCCESS**. Seluruh lima stage selesai, 26 tes Python dan 15 tes JavaScript lulus, serta deployment menggunakan snapshot `.deployments/build-4`.

`team-backend` dan `team-frontend` dibuat ulang lalu healthy. Pemeriksaan HTTP ke `http://127.0.0.1:8082/` juga menemukan judul baru `Kenali tim dan proyek kami`, sehingga perubahan commit terlihat pada layanan yang di-deploy. Delivery webhook GitHub dilaporkan berhasil sebelum push pengujian tersebut.

Dengan demikian, jalur **git push main → GitHub Webhook → Jenkins → test/build → deployment → health check** sudah terverifikasi. Nomor build dan SHA di atas mencatat bukti yang benar-benar diperoleh, bukan template hasil.
