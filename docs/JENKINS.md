# Setup Jenkins dan GitHub Webhook

Target panduan: Jenkins yang sudah berjalan di **http://localhost:8081**, dengan agent pada host Docker yang sama. Aplikasi di **http://localhost:8082**. Jangan menjalankan preview Python dan frontend Compose pada port yang sama.

## 1. Agent dan akses Docker

Gunakan agent bernama/berlabel **team-portfolio**, pada host yang menjalankan Docker Desktop dan menyimpan workspace pipeline. Jenkinsfile berjalan di Windows (`bat`) maupun Linux (`sh`). Agent harus bisa menjalankan `git`, `docker info`, dan `docker compose version` memakai akun OS-nya sendiri. Python dan Node untuk tes disediakan lewat container; tidak wajib di-install pada agent.

Di **Manage Jenkins > Nodes**, tambahkan label `team-portfolio` pada node yang dipakai. Jika node lokal/controller dipakai khusus demonstrasi tugas, pastikan executor aktif. Untuk penggunaan berkelanjutan, gunakan agent terpisah. Jangan memilih agent acak: deployment dan bind mount harus tetap pada host yang sama.

Jika Jenkins berjalan sebagai Windows service dengan akun berbeda, keberhasilan `docker info` pada PowerShell pengguna belum membuktikan service Jenkins punya akses. Jalankan agent sebagai akun lokal yang memang dapat mengakses Docker Desktop. Tidak perlu menonaktifkan authentication Jenkins atau membuka Docker daemon melalui TCP.

Workspace agent dan Docker daemon harus menunjuk filesystem yang sama. Panduan ini mengasumsikan agent native pada host; Jenkins dalam container dengan host Docker socket membutuhkan pemetaan workspace tambahan dan tidak tercakup oleh setup ini.

## 2. Plugin dan credential GitHub

Pastikan plugin **Pipeline**, **Git**, **GitHub**, dan **Timestamper** tersedia di Manage Jenkins > Plugins. Jangan menonaktifkan keamanan Jenkins untuk mengaktifkan pipeline.

Sesuai brief ujian, buat GitHub PAT classic dengan expiry 30/90 hari dan scope `repo` serta `admin:repo_hook`. Masukkan melalui **Manage Jenkins > Credentials > System > Global credentials > Add Credentials**, jenis **Username with password**:

- Username: username GitHub pemilik token.
- Password: PAT. Isi langsung pada Jenkins; jangan taruh token di file, terminal log, atau repository.
- ID: `github-team-portfolio`.

PAT ini untuk akses repository/webhook tugas; fitur tampilan repo publik aplikasi tidak memakai token ini.

## 3. Pipeline from SCM

1. Simpan dan push seluruh file proyek, termasuk Jenkinsfile, tests/, tools/, dan frontend/js/github.js ke branch `main`.
2. **New Item > team-portfolio > Pipeline**.
3. Aktifkan GitHub project, URL `https://github.com/Llovind/Team_Portfolio`.
4. Definition: **Pipeline script from SCM**, SCM: **Git**.
5. Repository URL: `https://github.com/Llovind/Team_Portfolio.git`.
6. Credentials: `github-team-portfolio`; Branch Specifier: `*/main`; Script Path: `Jenkinsfile`.
7. Aktifkan **GitHub hook trigger for GITScm polling**, simpan, lalu jalankan **Build Now** sekali agar definisi trigger dari Jenkinsfile terdaftar.

Lima stage wajib dan perilakunya:

| Stage | Perintah/perilaku |
| --- | --- |
| Checkout | `checkout scm`, tampilkan commit yang dibangun |
| Syntax Check | Docker preflight, validasi Compose, tes Python, syntax dan tes JavaScript |
| Build Image | Build backend dari checkout terbaru, pull frontend Nginx |
| Automated Deployment | Recreate layanan dengan Compose dan tunggu healthy, tanpa menghapus volume |
| Health Check | Periksa semua aset UI dan `/api/health` + `/api/members` melalui `http://frontend` dari backend |

Setelah tes/build berhasil, pipeline menyalin frontend, backend, Nginx, dan Compose ke `.deployments/build-<BUILD_NUMBER>/` di workspace agent. Deployment memakai bind mount dari snapshot rilis itu sehingga checkout build berikutnya tidak menerbitkan frontend yang belum lulus tes. Jangan menghapus workspace atau snapshot yang sedang dipakai layanan. Folder ini diabaikan Git; snapshot lama tetap disimpan untuk pemeriksaan dan dapat dibersihkan manual setelah dipastikan tidak dipakai container. Jangan mengulang stage deployment dengan nomor build yang sama; jalankan build baru agar snapshot aktif tidak tertimpa.

`disableConcurrentBuilds` mencegah job yang sama deploy bersamaan; jangan membuat job lain untuk resource utama yang sama. Deployment yang gagal tidak otomatis rollback; periksa log lalu deploy ulang commit baik melalui build baru. Volume tetap dipertahankan.

## 4. GitHub Webhook

GitHub tidak bisa menghubungi `localhost:8081` pada laptop. Diperlukan URL HTTPS yang dapat dijangkau GitHub, melalui host yang tersedia atau reverse proxy/tunnel milik tim. Tujuan akhir webhook adalah endpoint Jenkins **`/github-webhook/`**, dengan slash penutup. Jangan memasukkan URL aplikasi pada port 8082.

Jika memakai proxy/tunnel untuk demo, batasi routing publik ke endpoint webhook dan pertahankan autentikasi dashboard Jenkins. Catat URL aktif karena URL tunnel sementara dapat berubah. Konfigurasi secret webhook harus konsisten dengan konfigurasi GitHub plugin jika dipakai; jangan commit secret.

Pada repository GitHub > **Settings > Webhooks > Add webhook**:

- Payload URL: `https://<endpoint-yang-bisa-dijangkau>/github-webhook/`.
- Content type: `application/json`.
- Events: **Just the push event**.
- Active: aktif; gunakan SSL verification.

Lakukan push perubahan kecil ke `main`. Periksa **Recent Deliveries**: respons 2xx, lalu verifikasi build baru benar-benar berjalan dengan commit tersebut. Delivery 2xx saja belum membuktikan pipeline ter-trigger; cocokkan SHA di Jenkins dengan commit push.

## 5. Bukti dan troubleshooting

- Simpan screenshot lima stage hijau, console log SHA, dan delivery webhook berhasil. Jangan rekam PAT/password saat membuat video.
- `Cannot connect`/`Access denied` Docker: cek akun agent dan Docker Desktop pada host yang sama.
- Port 8082 dipakai: hentikan preview Python. Untuk port deploy lain, ubah FRONTEND_PORT pada Jenkinsfile dan dokumentasi bersamaan.
- Bind mount tidak ditemukan: cek path workspace pada host daemon; jangan memakai remote Docker daemon dengan path lokal yang berbeda.
- 502 sesaat setelah backend dibuat ulang: Nginx resolver dapat membutuhkan hingga 10 detik untuk alamat backend baru.
- Build berhenti saat health check: lihat `docker compose logs`; file JSON rusak sengaja mengembalikan 503 agar data tidak tertimpa.
- GitHub repo fetch gagal: cek internet pada container backend. Ini berbeda dari webhook GitHub menuju Jenkins.

Referensi: [Jenkins Declarative Pipeline](https://www.jenkins.io/doc/book/pipeline/syntax/), [GitHub plugin](https://plugins.jenkins.io/github/), [Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/).
