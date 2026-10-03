let allVideos = [];

async function loadData() {
    const res = await fetch("./data/matches.json?" + Date.now());
    const data = await res.json();
    allVideos = data.videos || [];
    document.getElementById("updatedAt").textContent =
        "最終更新: " + new Date(data.updated_at).toLocaleString("ja-JP");

    populateFilters();
    render();
}

function populateFilters() {
    const characters = [...new Set(allVideos.map(v => v.character))].sort();
    const maps = [...new Set(allVideos.flatMap(v => v.matches.map(m => m.map)))].sort();

    const charSelect = document.getElementById("characterFilter");
    const mapSelect = document.getElementById("mapFilter");

    characters.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c;
        opt.textContent = c;
        charSelect.appendChild(opt);
    });

    maps.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        mapSelect.appendChild(opt);
    });
}

function render() {
    const char = document.getElementById("characterFilter").value;
    const map = document.getElementById("mapFilter").value;
    const player = document.getElementById("playerFilter").value.trim().toLowerCase();

    const results = document.getElementById("results");
    results.innerHTML = "";

    let hasResult = false;

    allVideos.forEach(video => {
        if (char && video.character !== char) return;

        const filteredMatches = video.matches.filter(m => {
            if (map && m.map !== map) return false;
            if (player && !m.player.toLowerCase().includes(player)) return false;
            return true;
        });

        if (filteredMatches.length === 0) return;
        hasResult = true;

        const card = document.createElement("div");
        card.className = "video-card";

        const date = new Date(video.published_at).toLocaleDateString("ja-JP");
        card.innerHTML = `
      <h2 class="video-title">${video.character} — ${video.title}</h2>
      <div class="video-meta">${date} ／ <a href="${video.url}" target="_blank">動画を開く</a></div>
      <ul class="match-list">
        ${filteredMatches.map(m => `
          <li class="match-item">
            <a href="https://www.youtube.com/watch?v=${video.video_id}&t=${m.seconds}s" target="_blank">
              ${m.timestamp}
            </a>
            <span class="tag">${m.map}</span>
            <span class="tag">${m.player}</span>
            <span class="tag">${m.rank}</span>
          </li>
        `).join("")}
      </ul>
    `;
        results.appendChild(card);
    });

    if (!hasResult) {
        results.innerHTML = "<p>該当する試合がありません。</p>";
    }
}

document.getElementById("characterFilter").addEventListener("change", render);
document.getElementById("mapFilter").addEventListener("change", render);
document.getElementById("playerFilter").addEventListener("input", render);
document.getElementById("resetBtn").addEventListener("click", () => {
    document.getElementById("characterFilter").value = "";
    document.getElementById("mapFilter").value = "";
    document.getElementById("playerFilter").value = "";
    render();
});

loadData();