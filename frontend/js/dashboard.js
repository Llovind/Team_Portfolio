// =====================================================================
// dashboard.js — khusus anggota.html
// 1) Menampilkan daftar profil singkat (GET /members)
// 2) Animasi "kabel" yang teraliri saat halaman di-scroll
// 3) Animasi redup saat membuka profil
// 4) Jendela tambah anggota (POST /members)
// Fungsi apiGetMembers, createAvatar, dll. berasal dari api.js
// =====================================================================

// Jeda auto-refresh daftar anggota (milidetik)
const REFRESH_MS = 5000;

// Ambil elemen-elemen HTML yang sering dipakai, sekali saja di awal
const rosterList = document.getElementById("rosterList");
const rosterNote = document.getElementById("rosterNote");
const rosterCount = document.getElementById("rosterCount");
const statusEl = document.getElementById("status");
const statusText = document.getElementById("statusText");
const flash = document.getElementById("flash");

const dialog = document.getElementById("addDialog");
const form = document.getElementById("addForm");
const openAddBtn = document.getElementById("openAddBtn");
const cancelAddBtn = document.getElementById("cancelAddBtn");
const saveBtn = document.getElementById("saveBtn");
const formMsg = document.getElementById("formMsg");
const inputs = {
  name: document.getElementById("nameInput"),
  nim: document.getElementById("nimInput"),
  role: document.getElementById("roleInput"),
  skills: document.getElementById("skillsInput"),          // hard skill
  softSkills: document.getElementById("softSkillsInput"),  // soft skill
  bio: document.getElementById("bioInput"),
  email: document.getElementById("emailInput"),
  github: document.getElementById("githubInput"),
};

// Apakah pengguna mengaktifkan "kurangi animasi" di sistem operasinya?
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

let currentMembers = [];      // data terakhir dari backend
let lastSnapshot = null;      // versi teks JSON, untuk cek "datanya berubah atau tidak"
let latestRequestId = 0;      // hanya hasil request GET terbaru yang dipakai
let hasLoadedOnce = false;    // sudah pernah berhasil memuat data?
const revealed = new Set();   // anggota yang sudah pernah muncul (animasinya tidak diulang)

// ---------------------------------------------------------------------
// STATUS & PESAN
// ---------------------------------------------------------------------

function setStatus(online) {
  statusEl.classList.toggle("is-online", online);
  statusEl.classList.toggle("is-offline", !online);
  statusText.textContent = online
    ? "Terhubung ke backend"
    : "Backend tidak aktif, mencoba lagi setiap 5 detik";
}

function showNote(text) {
  rosterNote.textContent = text;
  rosterNote.hidden = false;
}

function showFlash(text) {
  flash.textContent = text;
  flash.hidden = false;
}

// ---------------------------------------------------------------------
// MENAMPILKAN DAFTAR ANGGOTA
// ---------------------------------------------------------------------

// Kunci unik tiap anggota (NIM; kalau tidak ada, pakai posisi)
function memberKey(member, index) {
  return member && member.nim ? "nim:" + member.nim : "idx:" + index;
}

// Membuat 1 baris keahlian, misal:  Hard skill   HTML, CSS, Docker
function createSkillLine(label, skills) {
  const line = document.createElement("p");
  line.className = "member-skills";
  const tag = document.createElement("span");
  tag.className = "skill-label";
  tag.textContent = label;
  line.append(tag, document.createTextNode(skills.join(", ")));
  return line;
}

// Membuat 1 baris profil singkat
function createRow(member, index) {
  member = member || {}; // jaga-jaga kalau ada data null
  const key = memberKey(member, index);

  const row = document.createElement("li");
  row.className = "member";
  row.dataset.key = key;
  // Yang sudah pernah muncul langsung tampil tanpa animasi ulang
  if (revealed.has(key) || reduceMotion) row.classList.add("is-visible");

  const link = document.createElement("div");
  link.className = "member-link";

  // Teks dibagi 2 kelompok supaya di layar lebar bisa tampil berdampingan:
  // main   = nama, peran, NIM
  // detail = keahlian & cuplikan bio
  const text = document.createElement("div");
  text.className = "member-text";
  const main = document.createElement("div");
  main.className = "member-main";
  const detail = document.createElement("div");
  detail.className = "member-detail";
  text.append(main, detail);

  const name = document.createElement("h3");
  name.className = "member-name";
  name.textContent = member.name || "Tanpa nama";
  main.appendChild(name);

  // Peran & NIM
  const meta = document.createElement("p");
  meta.className = "member-meta";
  if (member.role) {
    const role = document.createElement("span");
    role.className = "member-role";
    role.textContent = member.role;
    meta.appendChild(role);
  }
  if (member.nim) {
    const nim = document.createElement("span");
    nim.className = "member-nim";
    nim.textContent = "NIM " + member.nim;
    meta.appendChild(nim);
  }
  main.appendChild(meta);
  const actions = document.createElement("div");
  actions.className = "member-actions";
  for (const [label, edit] of [["Lihat profil", false], ["Edit profil", true]]) {
    const action = document.createElement("a");
    action.className = `btn ${edit ? "btn-primary" : "btn-outline"} member-action`;
    action.href = profileUrl(member, index) + (edit ? "&edit=1" : "");
    action.textContent = label;
    action.setAttribute("aria-label", `${label} ${member.name || "anggota"}`);
    actions.appendChild(action);
  }
  main.appendChild(actions);

  // Keahlian: satu baris hard skill, satu baris soft skill (kalau ada)
  const hardSkills = toSkillArray(member.skills);
  const softSkills = toSkillArray(member.soft_skills);
  if (hardSkills.length) detail.appendChild(createSkillLine("Hard skill", hardSkills));
  if (softSkills.length) detail.appendChild(createSkillLine("Soft skill", softSkills));

  // Cuplikan "Tentang" (dipotong 2 baris oleh CSS)
  if (member.bio) {
    const bio = document.createElement("p");
    bio.className = "member-bio";
    bio.textContent = member.bio;
    detail.appendChild(bio);
  }
  const github = cleanGithub(member.github);
  if (github) detail.appendChild(createRepoShowcase(github));

  link.append(createAvatar(member, "avatar-node"), text);
  row.appendChild(link);
  return row;
}

// Menggambar ulang seluruh daftar
function renderRoster(members) {
  rosterList.replaceChildren(); // kosongkan isi lama
  rosterCount.textContent = `${members.length} orang`;

  if (members.length === 0) {
    showNote("Belum ada anggota. Tambahkan profil pertama lewat tombol Tambah anggota.");
  } else {
    rosterNote.hidden = true;
    // Urutan tampilan = urutan array dari backend
    members.forEach((member, index) => rosterList.appendChild(createRow(member, index)));
  }
  updateScrollEffects();
}

// ---------------------------------------------------------------------
// ANIMASI SCROLL: "KABEL" KUNING MENGALIRI TIAP ANGGOTA
// ---------------------------------------------------------------------
// Ada satu garis pemicu di 75% tinggi layar. Saat di-scroll:
// 1) kabel kuning memanjang sampai garis pemicu itu,
// 2) setiap baris yang sudah dilewati kabel → titiknya menyala & teksnya muncul.
function updateScrollEffects() {
  const triggerY = window.innerHeight * 0.75;
  // Sudah mentok di bawah halaman? (berguna kalau daftarnya pendek)
  const atBottom =
    window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;

  // 1) Panjang kabel kuning, dalam angka 0 (kosong) s.d. 1 (penuh)
  const rect = rosterList.getBoundingClientRect();
  let progress = rect.height > 0 ? (triggerY - rect.top) / rect.height : 0;
  if (atBottom) progress = 1;
  progress = Math.min(1, Math.max(0, progress));
  rosterList.style.setProperty("--trace", progress.toFixed(3));

  // 2) Munculkan baris yang sudah dilewati kabel
  rosterList.querySelectorAll(".member:not(.is-visible)").forEach(row => {
    if (atBottom || row.getBoundingClientRect().top < triggerY) {
      row.classList.add("is-visible");
      revealed.add(row.dataset.key);
    }
  });
}

// requestAnimationFrame → perhitungan dilakukan maksimal 1x per frame layar (hemat & halus)
let ticking = false;
function onScroll() {
  if (ticking) return;
  ticking = true;
  requestAnimationFrame(() => {
    updateScrollEffects();
    ticking = false;
  });
}
window.addEventListener("scroll", onScroll, { passive: true });
window.addEventListener("resize", onScroll);

// ---------------------------------------------------------------------
// ANIMASI REDUP SAAT MEMBUKA PROFIL
// ---------------------------------------------------------------------
// Satu listener di daftar (bukan di tiap baris), karena barisnya digambar ulang
// setiap data berubah. event.target.closest() mencari tautan yang diklik.
rosterList.addEventListener("click", (event) => {
  const link = event.target.closest("a.member-action");
  if (!link) return;

  // Biarkan perilaku normal kalau dibuka di tab baru (Ctrl/Cmd/Shift + klik)
  // atau kalau pengguna mematikan animasi di sistem operasinya
  if (event.ctrlKey || event.metaKey || event.shiftKey || reduceMotion) return;

  event.preventDefault();                   // tahan dulu perpindahan halamannya
  document.body.classList.add("is-leaving"); // layar meredup (lihat CSS body::after)
  setTimeout(() => { location.href = link.href; }, 280); // lalu pindah setelah 0,28 detik
});

// Kalau kembali pakai tombol Back, browser kadang menampilkan halaman dari cache
// dalam keadaan terakhir (masih redup). Event "pageshow" dipakai untuk menerangkannya lagi.
window.addEventListener("pageshow", (event) => {
  if (event.persisted) document.body.classList.remove("is-leaving");
});

// ---------------------------------------------------------------------
// MEMUAT DATA DARI BACKEND (GET /members)
// ---------------------------------------------------------------------
async function loadMembers() {
  const requestId = ++latestRequestId;
  try {
    const members = await apiGetMembers();
    if (requestId !== latestRequestId) return; // sudah ada request yang lebih baru

    currentMembers = members;
    hasLoadedOnce = true;

    // Gambar ulang hanya kalau datanya berubah (supaya tampilan tidak "berkedip")
    const snapshot = JSON.stringify(members);
    if (snapshot !== lastSnapshot) {
      lastSnapshot = snapshot;
      renderRoster(members);
    }
    setStatus(true);
  } catch (err) {
    if (requestId !== latestRequestId) return;
    // Data lama tetap ditampilkan; hanya status yang berubah.
    // Berguna saat demo "Data Immunity": backend dihapus → status merah,
    // backend dinyalakan lagi → status hijau dan data tetap ada.
    setStatus(false);
    statusText.textContent = `Gagal memuat anggota: ${errorText(err)}. Mencoba lagi setiap 5 detik.`;
    if (!hasLoadedOnce) showNote("Daftar anggota akan muncul otomatis setelah server tersedia.");
  }
}

// ---------------------------------------------------------------------
// JENDELA TAMBAH ANGGOTA (POST /members)
// ---------------------------------------------------------------------
openAddBtn.addEventListener("click", () => {
  formMsg.textContent = "";
  dialog.showModal(); // buka jendela; kursor otomatis ke kolom pertama
});

cancelAddBtn.addEventListener("click", () => dialog.close());

// Klik di area gelap di luar jendela → tutup
configureDialog(dialog);

form.addEventListener("submit", async (event) => {
  event.preventDefault(); // cegah halaman reload (perilaku bawaan form)

  // Ambil isian form
  const name = inputs.name.value.trim();
  const nim = inputs.nim.value.trim();
  const role = inputs.role.value.trim();
  const skills = toSkillArray(inputs.skills.value);           // hard skill (wajib)
  const softSkills = toSkillArray(inputs.softSkills.value);   // soft skill (opsional)
  const bio = inputs.bio.value.trim();
  const email = inputs.email.value.trim();
  const githubRaw = inputs.github.value.trim();
  const github = cleanGithub(githubRaw);

  // Validasi sederhana di sisi frontend
  if (!name || !nim || !role || skills.length === 0) {
    formMsg.textContent = "Lengkapi nama, NIM, peran, dan hard skill.";
    return;
  }
  if (!/^\d+$/.test(nim)) {
    formMsg.textContent = "NIM hanya boleh berisi angka.";
    return;
  }
  if (currentMembers.some(m => m && String(m.nim) === nim)) {
    formMsg.textContent = "NIM ini sudah terdaftar di tim.";
    return;
  }
  if (email && !inputs.email.checkValidity()) {
    formMsg.textContent = "Format email belum benar, contoh: nama@student.telkomuniversity.ac.id";
    return;
  }
  if (githubRaw && !github) {
    formMsg.textContent = "Username GitHub hanya boleh berisi huruf, angka, dan tanda minus.";
    return;
  }

  // Susun data sesuai kesepakatan dengan backend.
  // Kolom opsional hanya dikirim kalau diisi.
  // "skills" tetap dipakai untuk hard skill supaya sesuai kontrak awal dengan backend
  const newMember = { name, nim, role, skills };
  if (softSkills.length) newMember.soft_skills = softSkills;
  if (bio) newMember.bio = bio;
  if (email) newMember.email = email;
  if (github) newMember.github = github;

  setDialogBusy(dialog, true);
  saveBtn.textContent = "Menyimpan…";
  try {
    await apiAddMember(newMember);
    dialog.close();
    form.reset();
    showFlash(`${name} ditambahkan ke tim.`);
    await loadMembers(); // daftar langsung ter-update tanpa refresh halaman

    // Gulir ke baris anggota baru supaya langsung terlihat
    const newRow = rosterList.querySelector(`[data-key="${CSS.escape("nim:" + nim)}"]`);
    if (newRow) newRow.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
  } catch (err) {
    formMsg.textContent = `Gagal menyimpan: ${errorText(err)}`;
  } finally {
    setDialogBusy(dialog, false);
    saveBtn.textContent = "Simpan anggota";
  }
});

// ---------------------------------------------------------------------
// MULAI
// ---------------------------------------------------------------------

// Kalau baru kembali dari halaman profil setelah menghapus, tampilkan konfirmasinya
const params = new URLSearchParams(location.search);
if (params.has("deleted")) {
  showFlash(`Profil ${params.get("deleted")} sudah dihapus.`);
  history.replaceState(null, "", "anggota.html"); // bersihkan alamat dari ?deleted=...
}

// Muat data pertama kali, lalu ulangi setiap REFRESH_MS.
// Pakai setTimeout berantai (bukan setInterval) supaya request berikutnya
// baru jalan setelah request sebelumnya selesai (tidak menumpuk).
async function autoRefresh() {
  await loadMembers();
  setTimeout(autoRefresh, REFRESH_MS);
}
autoRefresh();
