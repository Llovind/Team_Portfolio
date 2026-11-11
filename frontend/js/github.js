const showcaseRepoCache = new Map();

function createRepoShowcase(username) {
  const section = document.createElement("section");
  section.className = "repo-showcase";
  section.setAttribute("aria-label", `Proyek GitHub ${username}`);
  const title = document.createElement("h4");
  title.textContent = "3 repo terbaru";
  const status = document.createElement("p");
  status.className = "hint";
  status.setAttribute("role", "status");
  const list = document.createElement("ul");
  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "btn btn-outline";
  retry.textContent = "Coba muat repo lagi";
  retry.hidden = true;
  section.append(title, status, list, retry);

  async function load() {
    retry.hidden = true;
    status.textContent = "Memuat proyek GitHub…";
    section.setAttribute("aria-busy", "true");
    const key = username.toLowerCase();
    let entry = showcaseRepoCache.get(key);
    if (!entry || Date.now() - entry.created >= 300000) {
      entry = { created: Date.now(), promise: apiGetGithubRepos(username, 1) };
      if (showcaseRepoCache.size >= 128) showcaseRepoCache.delete(showcaseRepoCache.keys().next().value);
      showcaseRepoCache.set(key, entry);
    }
    try {
      const data = await entry.promise;
      if (!Array.isArray(data.repositories)) throw new Error("format repositori tidak valid");
      const items = data.repositories.slice(0, 3).map(repo => {
        if (!repo || typeof repo.name !== "string" || typeof repo.url !== "string"
            || !/^https:\/\/github\.com\/[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(repo.url)) {
          throw new Error("tautan repositori tidak valid");
        }
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.className = "repo-chip";
        link.textContent = repo.name;
        link.href = repo.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        item.appendChild(link);
        return item;
      });
      list.replaceChildren(...items);
      status.textContent = items.length ? "Berdasarkan push terbaru di GitHub." : "Belum ada repositori publik.";
    } catch (err) {
      if (showcaseRepoCache.get(key) === entry) showcaseRepoCache.delete(key);
      status.textContent = `Repo belum bisa dimuat: ${errorText(err)}`;
      retry.hidden = false;
    } finally {
      section.setAttribute("aria-busy", "false");
    }
  }
  retry.addEventListener("click", load);
  load();
  return section;
}

function createGithubProjects() {
  const section = document.getElementById("githubProjects");
  const status = document.getElementById("githubStatus");
  const list = document.getElementById("githubList");
  const retry = document.getElementById("githubRetry");
  const more = document.getElementById("githubMore");
  let username = null;
  let nextPage = 1;
  let requestId = 0;
  let loading = false;
  let hasNext = false;

  function createRepo(repo) {
    const item = document.createElement("li");
    const title = document.createElement("h4");
    const link = document.createElement("a");
    link.textContent = repo.name;
    link.href = repo.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    title.appendChild(link);
    item.appendChild(title);
    const description = document.createElement("p");
    description.textContent = repo.description || "Belum ada deskripsi di GitHub.";
    item.appendChild(description);
    const details = [repo.language, repo.fork ? "Fork" : "", repo.archived ? "Arsip" : ""].filter(Boolean);
    if (details.length) {
      const meta = document.createElement("p");
      meta.className = "repo-meta";
      meta.textContent = details.join(" · ");
      item.appendChild(meta);
    }
    return item;
  }

  async function load() {
    if (!username || loading) return;
    const id = ++requestId;
    loading = true;
    retry.hidden = true;
    more.disabled = true;
    status.textContent = "Memuat repositori GitHub…";
    section.setAttribute("aria-busy", "true");
    try {
      const data = await apiGetGithubRepos(username, nextPage);
      if (id !== requestId) return;
      // Validate before appending anything; never turn an unexpected response into an empty state.
      if (!Array.isArray(data.repositories) || data.repositories.some(repo =>
        !repo || typeof repo.name !== "string" || typeof repo.url !== "string"
        || !/^https:\/\/github\.com\/[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(repo.url))) {
        throw new Error("format repositori dari server tidak valid");
      }
      data.repositories.forEach(repo => list.appendChild(createRepo(repo)));
      nextPage++;
      hasNext = data.has_next === true;
      more.hidden = !hasNext;
      status.textContent = list.children.length
        ? `${list.children.length} repositori dari @${username}. Data GitHub di-cache hingga 5 menit.`
        : `@${username} belum memiliki repositori publik.`;
    } catch (err) {
      if (id !== requestId) return;
      status.textContent = `Gagal memuat repo: ${errorText(err)}`;
      retry.hidden = false;
      more.hidden = true;
    } finally {
      if (id === requestId) {
        loading = false;
        more.disabled = false;
        section.setAttribute("aria-busy", "false");
      }
    }
  }

  retry.addEventListener("click", load);
  more.addEventListener("click", load);
  return {
    setUsername(value) {
      if (value === username) return;
      username = value;
      requestId++;
      loading = false;
      nextPage = 1;
      hasNext = false;
      list.replaceChildren();
      more.hidden = true;
      retry.hidden = true;
      section.setAttribute("aria-busy", "false");
      status.textContent = "Isi username GitHub lewat tombol Edit profil untuk menampilkan repositori publik.";
      if (username) load();
    },
    setVisible(visible) { section.hidden = !visible; },
  };
}
