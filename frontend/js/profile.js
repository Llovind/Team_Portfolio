// =====================================================================
// profile.js — khusus profile.html
// 1) Membaca NIM dari alamat, misal profile.html?nim=101012330060
// 2) Mengambil data (GET /members) lalu mencari orang dengan NIM itu
// 3) Tombol hapus (DELETE /members?index=X)
// Fungsi apiGetMembers, createAvatar, dll. berasal dari api.js
// =====================================================================

// Ambil parameter dari alamat halaman
const params = new URLSearchParams(location.search);
const wantedNim = params.get("nim");     // cara utama
const wantedIndex = params.get("index"); // cadangan kalau data tidak punya NIM

// Ambil elemen-elemen HTML
const note = document.getElementById("profileNote");
const body = document.getElementById("profileBody");
const avatarSlot = document.getElementById("profileAvatar");
const nameEl = document.getElementById("profileName");
const roleEl = document.getElementById("profileRole");
const nimEl = document.getElementById("profileNim");
const bioEl = document.getElementById("profileBio");
const skillsEl = document.getElementById("profileSkills");
const contactEl = document.getElementById("profileContact");
const deleteBtn = document.getElementById("deleteBtn");
const deleteMsg = document.getElementById("deleteMsg");

let currentName = "";

// Cari posisi (index) orang yang dimaksud di dalam array anggota. -1 = tidak ketemu
function findMemberIndex(members) {
  if (wantedNim !== null) {
    return members.findIndex(m => m && String(m.nim) === wantedNim);
  }
  const index = Number.parseInt(wantedIndex, 10);
  return Number.isInteger(index) && index >= 0 && index < members.length ? index : -1;
}

function showNote(text) {
  note.textContent = text;
  note.hidden = false;
  body.hidden = true;
}

// Mengisi halaman dengan data 1 anggota
function renderProfile(member) {
  currentName = member.name || "Tanpa nama";
  document.title = `${currentName} | Profil Tim`;

  avatarSlot.replaceChildren(createAvatar(member, "avatar-large"));
  nameEl.textContent = currentName;
  roleEl.textContent = member.role || "";
  nimEl.textContent = member.nim ? "NIM " + member.nim : "";

  // Tentang
  bioEl.textContent = member.bio || "Belum ada deskripsi.";
  bioEl.classList.toggle("is-empty", !member.bio);

  // Keahlian: satu per baris
  skillsEl.replaceChildren();
  toSkillArray(member.skills).forEach(skill => {
    const item = document.createElement("li");
    item.textContent = skill;
    skillsEl.appendChild(item);
  });

  // Kontak: email & GitHub (kalau ada)
  contactEl.replaceChildren();
  if (member.email) {
    const link = document.createElement("a");
    link.href = "mailto:" + member.email;
    link.textContent = member.email;
    contactEl.appendChild(contactRow("Email", link));
  }
  const github = cleanGithub(member.github);
  if (github) {
    const link = document.createElement("a");
    link.href = "https://github.com/" + github;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "github.com/" + github;
    contactEl.appendChild(contactRow("GitHub", link));
  }
  if (!contactEl.hasChildNodes()) {
    contactEl.textContent = "Belum ada kontak.";
    contactEl.classList.add("is-empty");
  }

  note.hidden = true;
  body.hidden = false;
}

// Satu baris kontak: label di kiri, tautan di kanan
function contactRow(label, linkEl) {
  const row = document.createElement("div");
  row.className = "contact-row";
  const labelEl = document.createElement("span");
  labelEl.className = "contact-label";
  labelEl.textContent = label;
  row.append(labelEl, linkEl);
  return row;
}

// GET /members → cari orangnya → tampilkan
async function loadProfile() {
  if (wantedNim === null && wantedIndex === null) {
    showNote("Alamat profil tidak lengkap. Kembali ke daftar tim lalu pilih salah satu nama.");
    return;
  }
  try {
    const members = await apiGetMembers();
    const index = findMemberIndex(members);
    if (index === -1) {
      showNote("Profil ini tidak ditemukan. Mungkin sudah dihapus dari tim.");
      return;
    }
    renderProfile(members[index] || {});
  } catch (err) {
    showNote("Profil belum bisa dimuat karena backend tidak aktif. Halaman mencoba lagi setiap 5 detik.");
    setTimeout(loadProfile, 5000);
  }
}

// DELETE /members?index=X
deleteBtn.addEventListener("click", async () => {
  if (!confirm(`Hapus profil ${currentName}? Data ini tidak bisa dikembalikan.`)) return;

  deleteBtn.disabled = true;
  deleteBtn.textContent = "Menghapus…";
  deleteMsg.textContent = "";
  try {
    // Ambil data terbaru dulu, supaya index yang dihapus benar-benar milik orang ini
    // (index bisa bergeser kalau ada anggota lain yang dihapus sebelumnya)
    const members = await apiGetMembers();
    const index = findMemberIndex(members);
    if (index === -1) throw new Error("profil ini sudah tidak ada");

    await apiDeleteMember(index);
    // Kembali ke daftar tim sambil membawa nama yang dihapus untuk pesan konfirmasi
    location.href = "anggota.html?deleted=" + encodeURIComponent(currentName);
  } catch (err) {
    deleteMsg.textContent = `Gagal menghapus: ${errorText(err)}`;
    deleteBtn.disabled = false;
    deleteBtn.textContent = "Hapus profil ini";
  }
});

loadProfile();