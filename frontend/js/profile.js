// =====================================================================
// profile.js — khusus profile.html
// 1) Membaca NIM dari alamat, misal profile.html?nim=101012330060
// 2) Mengambil data (GET /members) lalu mencari orang dengan NIM itu
// 3) Edit profil (PUT /members?index=X)
// 4) Tombol hapus (DELETE /members?index=X)
// Fungsi apiGetMembers, createAvatar, dll. berasal dari api.js
// =====================================================================

// Ambil parameter dari alamat halaman
const params = new URLSearchParams(location.search);
const wantedNim = params.get("nim");     // cara utama
const wantedIndex = params.get("index"); // cadangan kalau data tidak punya NIM

// Ambil elemen-elemen HTML halaman profil
const note = document.getElementById("profileNote");
const flash = document.getElementById("profileFlash");
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

// Elemen jendela edit
const editBtn = document.getElementById("editBtn");
const editDialog = document.getElementById("editDialog");
const editForm = document.getElementById("editForm");
const cancelEditBtn = document.getElementById("cancelEditBtn");
const saveEditBtn = document.getElementById("saveEditBtn");
const editMsg = document.getElementById("editMsg");
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

let currentMember = null;  // data anggota yang sedang ditampilkan
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

function showFlash(text) {
  flash.textContent = text;
  flash.hidden = false;
}

// ---------------------------------------------------------------------
// MENAMPILKAN PROFIL
// ---------------------------------------------------------------------

// Mengisi halaman dengan data 1 anggota
function renderProfile(member) {
  currentMember = member;
  currentName = member.name || "Tanpa nama";
  document.title = `${currentName} | Profil Tim`;

  avatarSlot.replaceChildren(createAvatar(member, "avatar-large"));
  nameEl.textContent = currentName;
  roleEl.textContent = member.role || "";
  nimEl.textContent = member.nim ? "NIM " + member.nim : "";

  // Tentang
  bioEl.textContent = member.bio || "Belum ada deskripsi.";
  bioEl.classList.toggle("is-empty", !member.bio);

  // Keahlian: dua kelompok, hard skill (titik kuning) & soft skill (titik biru)
  skillsEl.replaceChildren(
    skillGroup("Hard skill", toSkillArray(member.skills), "skill-list"),
    skillGroup("Soft skill", toSkillArray(member.soft_skills), "skill-list is-soft")
  );

  // Kontak: email & GitHub (kalau ada)
  contactEl.replaceChildren();
  contactEl.classList.remove("is-empty");
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

// Satu kelompok keahlian: judul kecil + daftar (satu keahlian per baris)
function skillGroup(title, skills, listClass) {
  const group = document.createElement("div");
  group.className = "skill-group";

  const heading = document.createElement("p");
  heading.className = "skill-group-title";
  heading.textContent = title;
  group.appendChild(heading);

  if (skills.length === 0) {
    const empty = document.createElement("p");
    empty.className = "is-empty";
    empty.textContent = "Belum diisi.";
    group.appendChild(empty);
    return group;
  }

  const list = document.createElement("ul");
  list.className = listClass;
  skills.forEach(skill => {
    const item = document.createElement("li");
    item.textContent = skill;
    list.appendChild(item);
  });
  group.appendChild(list);
  return group;
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

// ---------------------------------------------------------------------
// EDIT PROFIL (PUT /members?index=X)
// ---------------------------------------------------------------------

// Isi form edit dengan data yang sedang tampil
function fillEditForm(member) {
  inputs.name.value = member.name || "";
  inputs.nim.value = member.nim || "";
  inputs.role.value = member.role || "";
  inputs.skills.value = toSkillArray(member.skills).join(", ");
  inputs.softSkills.value = toSkillArray(member.soft_skills).join(", ");
  inputs.bio.value = member.bio || "";
  inputs.email.value = member.email || "";
  inputs.github.value = member.github || "";
}

editBtn.addEventListener("click", () => {
  if (!currentMember) return;
  fillEditForm(currentMember);
  editMsg.textContent = "";
  editDialog.showModal(); // buka jendela edit
});

cancelEditBtn.addEventListener("click", () => editDialog.close());

// Klik di area gelap di luar jendela → tutup
editDialog.addEventListener("click", (event) => {
  if (event.target === editDialog) editDialog.close();
});

editForm.addEventListener("submit", async (event) => {
  event.preventDefault(); // cegah halaman reload (perilaku bawaan form)

  // Ambil isian form
  const name = inputs.name.value.trim();
  const role = inputs.role.value.trim();
  const skills = toSkillArray(inputs.skills.value);           // hard skill (wajib)
  const softSkills = toSkillArray(inputs.softSkills.value);   // soft skill (opsional)
  const bio = inputs.bio.value.trim();
  const email = inputs.email.value.trim();
  const githubRaw = inputs.github.value.trim();
  const github = cleanGithub(githubRaw);

  // Validasi sederhana (aturannya sama dengan form tambah anggota)
  if (!name || !role || skills.length === 0) {
    editMsg.textContent = "Lengkapi nama, peran, dan hard skill.";
    return;
  }
  if (email && !inputs.email.checkValidity()) {
    editMsg.textContent = "Format email belum benar, contoh: nama@student.telkomuniversity.ac.id";
    return;
  }
  if (githubRaw && !github) {
    editMsg.textContent = "Username GitHub hanya boleh berisi huruf, angka, dan tanda minus.";
    return;
  }

  // Data baru lengkap. NIM diambil dari data lama karena memang tidak boleh berubah.
  // Kolom opsional yang dikosongkan tidak dikirim → ikut terhapus dari data.
  const updated = { name, nim: currentMember.nim, role, skills };
  if (softSkills.length) updated.soft_skills = softSkills;
  if (bio) updated.bio = bio;
  if (email) updated.email = email;
  if (github) updated.github = github;

  saveEditBtn.disabled = true;
  saveEditBtn.textContent = "Menyimpan…";
  try {
    // Ambil data terbaru dulu, supaya index yang diedit benar-benar milik orang ini
    const members = await apiGetMembers();
    const index = findMemberIndex(members);
    if (index === -1) throw new Error("profil ini sudah tidak ada");

    const saved = await apiUpdateMember(index, updated);
    editDialog.close();
    renderProfile(saved);                 // tampilkan data baru tanpa refresh halaman
    showFlash("Perubahan profil disimpan.");
  } catch (err) {
    editMsg.textContent = `Gagal menyimpan: ${errorText(err)}`;
  } finally {
    saveEditBtn.disabled = false;
    saveEditBtn.textContent = "Simpan perubahan";
  }
});

// ---------------------------------------------------------------------
// HAPUS PROFIL (DELETE /members?index=X)
// ---------------------------------------------------------------------
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