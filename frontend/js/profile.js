// =====================================================================
// profile.js — khusus profile.html
// 1) Membaca NIM dari alamat, misal profile.html?nim=101012330060
// 2) Mengambil data (GET /members) lalu mencari orang dengan NIM itu
// 3) Edit profil (PUT /members?index=X)
// 4) Kegiatan & project: tab kategori, tambah (dengan foto), hapus
// 5) Tombol hapus profil (DELETE /members?index=X)
// Fungsi apiGetMembers, createAvatar, dll. berasal dari api.js
// =====================================================================

// Ambil parameter dari alamat halaman
const params = new URLSearchParams(location.search);
const wantedNim = params.get("nim");     // cara utama
const wantedIndex = params.get("index"); // cadangan kalau data tidak punya NIM

// Kategori kegiatan: "key" harus sama dengan yang diterima backend
const CATEGORIES = [
  { key: "project", label: "Project" },
  { key: "organisasi", label: "Kegiatan UMKM/Organisasi" },
  { key: "eksternal", label: "Kegiatan Eksternal" },
];

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

// Elemen jendela edit profil
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

// Elemen kegiatan & jendela tambah kegiatan
const activityTabs = document.getElementById("activityTabs");
const activityPanel = document.getElementById("activityPanel");
const addActBtn = document.getElementById("addActBtn");
const actDialog = document.getElementById("actDialog");
const actForm = document.getElementById("actForm");
const actCategory = document.getElementById("actCategory");
const actName = document.getElementById("actName");
const actPeriod = document.getElementById("actPeriod");
const actDesc = document.getElementById("actDesc");
const actPhoto = document.getElementById("actPhoto");
const actPreview = document.getElementById("actPreview");
const actMsg = document.getElementById("actMsg");
const cancelActBtn = document.getElementById("cancelActBtn");
const saveActBtn = document.getElementById("saveActBtn");

let currentMember = null;        // data anggota yang sedang ditampilkan
let currentName = "";
let activeCategory = "project";  // tab kegiatan yang sedang dibuka
let previewUrl = null;           // alamat sementara untuk pratinjau foto

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

// Daftar kegiatan milik anggota (selalu berupa array, walau kosong)
function activitiesOf(member) {
  return Array.isArray(member && member.activities) ? member.activities : [];
}

// ---------------------------------------------------------------------
// MENYIMPAN KE BACKEND (dipakai edit profil DAN kegiatan)
// ---------------------------------------------------------------------

// Menyusun data lengkap 1 anggota untuk dikirim lewat PUT.
// PUT mengganti seluruh data, jadi semua kolom (termasuk kegiatan) harus ikut dikirim.
function buildPayload(member) {
  const payload = {
    name: member.name,
    nim: member.nim,
    role: member.role,
    skills: toSkillArray(member.skills),
  };
  const soft = toSkillArray(member.soft_skills);
  if (soft.length) payload.soft_skills = soft;
  if (member.bio) payload.bio = member.bio;
  if (member.email) payload.email = member.email;
  if (member.github) payload.github = member.github;
  const activities = activitiesOf(member);
  if (activities.length) payload.activities = activities;
  return payload;
}

// PUT /members?index=X dengan index terbaru (dicari ulang berdasarkan NIM)
async function saveMember(member) {
  // Ambil data terbaru dulu, supaya index yang diubah benar-benar milik orang ini
  const members = await apiGetMembers();
  const index = findMemberIndex(members);
  if (index === -1) throw new Error("profil ini sudah tidak ada");
  return apiUpdateMember(index, buildPayload(member));
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

  renderActivities();

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

// ---------------------------------------------------------------------
// KEGIATAN & PROJECT
// ---------------------------------------------------------------------

// Gambar ulang tab kategori + daftar kegiatan pada tab yang aktif
function renderActivities() {
  const all = activitiesOf(currentMember);

  // 1) Tab kategori, lengkap dengan jumlah kegiatannya
  activityTabs.replaceChildren();
  CATEGORIES.forEach(cat => {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "tab";
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", String(cat.key === activeCategory));
    tab.textContent = cat.label;

    const count = document.createElement("span");
    count.className = "tab-count";
    count.textContent = all.filter(a => a.category === cat.key).length;
    tab.appendChild(count);

    tab.addEventListener("click", () => {
      activeCategory = cat.key;
      renderActivities();
    });
    activityTabs.appendChild(tab);
  });

  // 2) Daftar kegiatan di kategori aktif.
  //    Simpan juga posisi aslinya (index) supaya tombol hapus tahu kegiatan mana.
  const items = all
    .map((activity, index) => ({ activity, index }))
    .filter(entry => entry.activity.category === activeCategory);

  activityPanel.replaceChildren();
  if (items.length === 0) {
    const label = CATEGORIES.find(c => c.key === activeCategory).label;
    const empty = document.createElement("p");
    empty.className = "activity-empty";
    empty.textContent = `Belum ada ${label.toLowerCase()}. Tambahkan lewat tombol Tambah kegiatan.`;
    activityPanel.appendChild(empty);
    return;
  }

  const list = document.createElement("ul");
  list.className = "activity-list";
  items.forEach(({ activity, index }) => list.appendChild(createActivityItem(activity, index)));
  activityPanel.appendChild(list);
}

// Membuat 1 baris kegiatan: foto (kalau ada) + judul, waktu, penjelasan, tombol hapus
function createActivityItem(activity, index) {
  const item = document.createElement("li");
  item.className = "activity";

  if (isUploadedPhoto(activity.photo)) {
    // Klik foto → buka ukuran penuh di tab baru
    const photoLink = document.createElement("a");
    photoLink.className = "activity-photo";
    photoLink.href = activity.photo;
    photoLink.target = "_blank";
    photoLink.rel = "noopener";
    const img = document.createElement("img");
    img.src = activity.photo;
    img.alt = "Foto " + (activity.title || "kegiatan");
    img.loading = "lazy";
    photoLink.appendChild(img);
    item.appendChild(photoLink);
  } else {
    item.classList.add("no-photo");
  }

  const text = document.createElement("div");

  const title = document.createElement("h3");
  title.className = "activity-title";
  title.textContent = activity.title || "Tanpa judul";
  text.appendChild(title);

  if (activity.period) {
    const period = document.createElement("p");
    period.className = "activity-period";
    period.textContent = activity.period;
    text.appendChild(period);
  }

  if (activity.description) {
    const desc = document.createElement("p");
    desc.className = "activity-desc";
    desc.textContent = activity.description; // enter/baris baru tetap tampil (lihat CSS)
    text.appendChild(desc);
  }

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "activity-delete";
  removeBtn.textContent = "Hapus kegiatan";
  removeBtn.addEventListener("click", () => deleteActivity(index, removeBtn));
  text.appendChild(removeBtn);

  item.appendChild(text);
  return item;
}

// Hapus 1 kegiatan: kirim ulang data anggota tanpa kegiatan itu (PUT)
async function deleteActivity(index, button) {
  const activity = activitiesOf(currentMember)[index];
  if (!activity || !confirm(`Hapus kegiatan "${activity.title}"?`)) return;

  button.disabled = true;
  try {
    const remaining = activitiesOf(currentMember).filter((_, i) => i !== index);
    const saved = await saveMember({ ...currentMember, activities: remaining });
    renderProfile(saved);
    showFlash("Kegiatan dihapus.");
  } catch (err) {
    button.disabled = false;
    alert(`Gagal menghapus kegiatan: ${errorText(err)}`);
  }
}

// --- Jendela tambah kegiatan ---
function clearPreview() {
  if (previewUrl) URL.revokeObjectURL(previewUrl); // bebaskan memori pratinjau lama
  previewUrl = null;
  actPreview.removeAttribute("src");
  actPreview.hidden = true;
}

addActBtn.addEventListener("click", () => {
  if (!currentMember) return;
  actForm.reset();
  clearPreview();
  actCategory.value = activeCategory; // kategori awal = tab yang sedang dibuka
  actMsg.textContent = "";
  actDialog.showModal();
});

cancelActBtn.addEventListener("click", () => actDialog.close());
actDialog.addEventListener("click", (event) => {
  if (event.target === actDialog) actDialog.close();
});

// Tampilkan pratinjau begitu foto dipilih
actPhoto.addEventListener("change", () => {
  clearPreview();
  const file = actPhoto.files[0];
  if (!file) return;
  previewUrl = URL.createObjectURL(file);
  actPreview.src = previewUrl;
  actPreview.hidden = false;
});

actForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const newActivity = {
    category: actCategory.value,
    title: actName.value.trim(),
  };
  if (!newActivity.title) {
    actMsg.textContent = "Judul kegiatan wajib diisi.";
    return;
  }
  const period = actPeriod.value.trim();
  const description = actDesc.value.trim();
  if (period) newActivity.period = period;
  if (description) newActivity.description = description;

  saveActBtn.disabled = true;
  try {
    // 1) Kalau ada foto: perkecil di browser, lalu unggah → dapat alamat foto
    const file = actPhoto.files[0];
    if (file) {
      saveActBtn.textContent = "Mengunggah foto…";
      let blob;
      try {
        blob = await compressImage(file);
      } catch {
        throw new Error("format foto tidak didukung, gunakan JPG atau PNG");
      }
      newActivity.photo = await apiUploadPhoto(blob);
    }

    // 2) Simpan kegiatan baru bersama data anggota (PUT)
    saveActBtn.textContent = "Menyimpan…";
    const activities = [...activitiesOf(currentMember), newActivity];
    const saved = await saveMember({ ...currentMember, activities });

    actDialog.close();
    activeCategory = newActivity.category; // langsung buka tab kegiatan yang baru ditambah
    renderProfile(saved);
    showFlash("Kegiatan ditambahkan.");
  } catch (err) {
    actMsg.textContent = `Gagal menyimpan: ${errorText(err)}`;
  } finally {
    saveActBtn.disabled = false;
    saveActBtn.textContent = "Simpan kegiatan";
  }
});

// ---------------------------------------------------------------------
// MEMUAT PROFIL (GET /members)
// ---------------------------------------------------------------------
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

  // Data baru. NIM & kegiatan diambil dari data lama (NIM tidak boleh berubah,
  // kegiatan diatur lewat bagian "Kegiatan & project").
  // Kolom opsional yang dikosongkan ikut terhapus dari data.
  const updated = {
    name, role, skills,
    nim: currentMember.nim,
    soft_skills: softSkills,
    bio, email, github,
    activities: activitiesOf(currentMember),
  };

  saveEditBtn.disabled = true;
  saveEditBtn.textContent = "Menyimpan…";
  try {
    const saved = await saveMember(updated);
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