// =====================================================================
// api.js — semua komunikasi dengan backend dikumpulkan di sini,
// plus fungsi bantu yang dipakai dashboard.js DAN profile.js.
// Dimuat lebih dulu (lihat urutan <script> di HTML), jadi fungsi-fungsi
// di file ini bisa langsung dipanggil dari file JS lain.
// =====================================================================

// Alamat API memakai path RELATIF "/api".
// fetch() dijalankan oleh BROWSER di laptop, dan browser tidak kenal nama
// service Docker "backend". Jadi browser mengirim ke Nginx (alamat yang sama
// dengan halaman ini), lalu Nginx meneruskannya ke container backend lewat
// DNS Docker di jaringan app-net (lihat nginx/default.conf).
const API_BASE = "/api";

// ---------------------------------------------------------------------
// FUNGSI KE BACKEND
// ---------------------------------------------------------------------

// GET /members → mengembalikan array anggota
async function apiGetMembers() {
  // cache: "no-store" → selalu ambil data terbaru, jangan pakai cache browser
  const res = await fetch(`${API_BASE}/members`, { cache: "no-store" });
  if (!res.ok) throw new Error(await readError(res));

  const data = await res.json();
  // Jaga-jaga kalau backend membungkus array, misal {"members": [...]}
  return Array.isArray(data) ? data : (data.members || data.data || []);
}

// POST /members → menambah 1 anggota
async function apiAddMember(member) {
  const res = await fetch(`${API_BASE}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(member),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json().catch(() => ({})); // isi balasan tidak wajib dipakai
}

// DELETE /members?index=X → menghapus anggota di posisi X
async function apiDeleteMember(index) {
  const res = await fetch(`${API_BASE}/members?index=${index}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await readError(res));
}

// ---------------------------------------------------------------------
// FUNGSI BANTU: PESAN ERROR
// ---------------------------------------------------------------------

// Membaca pesan error dari backend, misal {"error": "NIM wajib diisi"}
async function readError(res) {
  // 502/503/504 = Nginx-nya jalan, tapi container backend sedang mati
  if (res.status >= 502 && res.status <= 504) {
    return `backend sedang tidak aktif (HTTP ${res.status})`;
  }
  try {
    const body = await res.json();
    return body.error || body.message || `HTTP ${res.status}`;
  } catch {
    return `HTTP ${res.status}`;
  }
}

// fetch() melempar TypeError kalau server sama sekali tidak bisa dihubungi
function errorText(err) {
  return err instanceof TypeError ? "server tidak bisa dihubungi" : err.message;
}

// ---------------------------------------------------------------------
// FUNGSI BANTU: DATA ANGGOTA
// ---------------------------------------------------------------------

// Skill bisa datang sebagai array ["HTML","CSS"] atau string "HTML, CSS".
// Fungsi ini menyeragamkan keduanya menjadi array.
function toSkillArray(skills) {
  if (Array.isArray(skills)) return skills.map(String).filter(Boolean);
  if (typeof skills === "string") {
    return skills.split(",").map(s => s.trim()).filter(Boolean);
  }
  return [];
}

// Ambil inisial dari nama, misal "Budi Santoso" → "BS"
function getInitials(name) {
  const words = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  return words.slice(0, 2).map(w => w[0].toUpperCase()).join("");
}

// Merapikan input GitHub: "@budi", "budi", atau "https://github.com/budi" → "budi".
// Kalau formatnya tidak valid, hasilnya string kosong.
function cleanGithub(value) {
  if (!value) return "";
  let username = String(value).trim().replace(/^@/, "");
  username = username.replace(/^https?:\/\/(www\.)?github\.com\//i, "").split("/")[0];
  return /^[A-Za-z0-9-]{1,39}$/.test(username) ? username : "";
}

// Alamat halaman profil lengkap seseorang.
// Dicari berdasarkan NIM (bukan index), karena index bisa bergeser kalau ada yang dihapus.
function profileUrl(member, index) {
  if (member && member.nim) return `profile.html?nim=${encodeURIComponent(member.nim)}`;
  return `profile.html?index=${index}`;
}

// ---------------------------------------------------------------------
// FUNGSI BANTU: TAMPILAN
// ---------------------------------------------------------------------

// Membuat elemen avatar. Urutan sumber foto:
//   1) file lokal  assets/foto/<NIM>.jpg   (foto yang kalian taruh sendiri di repo)
//   2) foto akun GitHub                    (kalau kolom github diisi)
//   3) inisial nama                        (kalau semua foto gagal dimuat)
// PENTING: semua teks dimasukkan lewat textContent (bukan innerHTML),
// supaya isian berbahaya seperti <script> tidak ikut dijalankan (aman dari XSS).
function createAvatar(member, extraClass) {
  const box = document.createElement("span");
  box.className = "avatar " + (extraClass || "");
  box.setAttribute("aria-hidden", "true"); // dekorasi; nama sudah tertulis di sebelahnya

  // Inisial selalu ada di lapisan bawah, jadi terlihat selama foto belum/tidak termuat
  const initials = document.createElement("span");
  initials.textContent = getInitials(member.name);
  box.appendChild(initials);

  // Kumpulkan daftar sumber foto yang mungkin
  const sources = [];
  const nim = String(member.nim || "");
  // NIM hanya boleh angka → aman dipakai sebagai nama file (tidak bisa disisipi "../" dsb.)
  if (/^\d+$/.test(nim)) sources.push(`assets/foto/${nim}.jpg`);
  const username = cleanGithub(member.github);
  if (username) sources.push(`https://github.com/${username}.png?size=256`);

  if (sources.length > 0) {
    const img = document.createElement("img");
    img.alt = "";
    img.decoding = "async";
    let current = 0;
    img.src = sources[current];

    // Foto muncul halus setelah benar-benar selesai dimuat
    img.addEventListener("load", () => img.classList.add("is-loaded"));

    // Gagal dimuat → coba sumber berikutnya; kalau habis → hapus <img>, inisial terlihat
    img.addEventListener("error", () => {
      current++;
      if (current < sources.length) img.src = sources[current];
      else img.remove();
    });
    box.appendChild(img);
  }
  return box;
}