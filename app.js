let allVideos = [];
let filteredVideos = [];
let displayedCount = 0;
const PAGE_SIZE = 50;

const WATCHED_VIDEOS_KEY = "watched_videos";
const WATCHED_MATCHES_KEY = "watched_matches";

function getWatchedVideos() {
  try {
    return JSON.parse(localStorage.getItem(WATCHED_VIDEOS_KEY) || "[]");
  } catch {
    return [];
  }
}

function getWatchedMatches() {
  try {
    return JSON.parse(localStorage.getItem(WATCHED_MATCHES_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveWatchedVideos(list) {
  localStorage.setItem(WATCHED_VIDEOS_KEY, JSON.stringify(list));
}

function saveWatchedMatches(list) {
  localStorage.setItem(WATCHED_MATCHES_KEY, JSON.stringify(list));
}

function matchKey(videoId, seconds) {
  return `${videoId}_${seconds}`;
}

async function loadData() {
  const res = await fetch("./data/matches.json?" + Date.now());
  const data = await res.json();
  allVideos = data.videos || [];

  document.getElementById("updatedAt").textContent =
    "最終更新: " + new Date(data.updated_at).toLocaleString("ja-JP");

  populateFilters();
  applyFilter();
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

function applyFilter() {
  const char = document.getElementById("characterFilter").value;
  const map = document.getElementById("mapFilter").value;
  const player = document.getElementById("playerFilter").value.trim().toLowerCase();

  filteredVideos = allVideos.filter(video => {
    if (char && video.character !== char) return false;

    if (map || player) {
      return video.matches.some(m => {
        if (map && m.map !== map) return false;
        if (player && !m.player.toLowerCase().includes(player)) return false;
        return true;
      });
    }
    return true;
  });

  displayedCount = 0;
  document.getElementById("results").innerHTML = "";
  document.getElementById("noMore").style.display = "none";
  loadMore();
}

function loadMore() {
  const results = document.getElementById("results");
  const loading = document.getElementById("loading");
  const noMore = document.getElementById("noMore");

  if (displayedCount >= filteredVideos.length) {
    noMore.style.display = filteredVideos.length > 0 ? "block" : "none";
    return;
  }

  loading.style.display = "block";

  const nextVideos = filteredVideos.slice(displayedCount, displayedCount + PAGE_SIZE);
  const watchedVideos = getWatchedVideos();
  const watchedMatches = getWatchedMatches();

  const map = document.getElementById("mapFilter").value;
  const player = document.getElementById("playerFilter").value.trim().toLowerCase();

  nextVideos.forEach(video => {
    const visibleMatches = video.matches.filter(m => {
      if (map && m.map !== map) return false;
      if (player && !m.player.toLowerCase().includes(player)) return false;
      return true;
    });

    if (visibleMatches.length === 0 && (map || player)) return;

    const isVideoWatched = watchedVideos.includes(video.video_id);
    const isLive = video.is_live_archive !== false;

    const card = document.createElement("div");
    card.className = "video-card" + (isVideoWatched ? " watched" : "");
    card.dataset.videoId = video.video_id;

    const date = new Date(video.published_at).toLocaleDateString("ja-JP");

    if (!isLive) {
      // ===== 通常動画：フラット表示 =====
      const m = visibleMatches[0] || video.matches[0];
      card.innerHTML = `
        <div class="video-header">
          <input type="checkbox" class="video-checkbox" data-video-id="${video.video_id}" ${isVideoWatched ? "checked" : ""}>
          <div class="video-title-area">
            <h2 class="video-title">${video.character} — ${video.title}</h2>
            <div class="video-meta">
              ${date} ／
              <span class="tag">${m.map}</span>
              <span class="tag">${m.player}</span>
              ${m.rank ? `<span class="tag">${m.rank}</span>` : ""}
              ／ <a href="${video.url}" target="_blank">動画を開く</a>
            </div>
          </div>
        </div>
      `;
    } else {
      // ===== 配信：親子構造 =====
      card.innerHTML = `
        <div class="video-header">
          <input type="checkbox" class="video-checkbox" data-video-id="${video.video_id}" ${isVideoWatched ? "checked" : ""}>
          <h2 class="video-title">${video.character} — ${video.title}</h2>
        </div>
        <div class="video-meta">${date} ／ <a href="${video.url}" target="_blank">動画を開く</a></div>
        <ul class="match-list">
          ${visibleMatches.map(m => {
            const key = matchKey(video.video_id, m.seconds);
            const isMatchWatched = watchedMatches.includes(key);
            return `
              <li class="match-item${isMatchWatched ? " watched" : ""}">
                <input type="checkbox" class="match-checkbox" data-key="${key}" ${isMatchWatched ? "checked" : ""}>
                <a href="https://www.youtube.com/watch?v=${video.video_id}&t=${m.seconds}s" target="_blank">
                  ${m.timestamp}
                </a>
                <span class="tag">${m.map}</span>
                <span class="tag">${m.player}</span>
                <span class="tag">${m.rank}</span>
              </li>
            `;
          }).join("")}
        </ul>
      `;
    }

    results.appendChild(card);
  });

  displayedCount += nextVideos.length;
  loading.style.display = "none";

  if (displayedCount >= filteredVideos.length) {
    noMore.style.display = "block";
  }
}

window.addEventListener("scroll", () => {
  if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 400) {
    loadMore();
  }
});

document.getElementById("results").addEventListener("change", (e) => {
  if (e.target.classList.contains("video-checkbox")) {
    const videoId = e.target.dataset.videoId;
    let watched = getWatchedVideos();

    if (e.target.checked) {
      if (!watched.includes(videoId)) watched.push(videoId);
      e.target.closest(".video-card").classList.add("watched");
    } else {
      watched = watched.filter(id => id !== videoId);
      e.target.closest(".video-card").classList.remove("watched");
    }
    saveWatchedVideos(watched);
  }

  if (e.target.classList.contains("match-checkbox")) {
    const key = e.target.dataset.key;
    let watched = getWatchedMatches();

    if (e.target.checked) {
      if (!watched.includes(key)) watched.push(key);
      e.target.closest(".match-item").classList.add("watched");
    } else {
      watched = watched.filter(k => k !== key);
      e.target.closest(".match-item").classList.remove("watched");
    }
    saveWatchedMatches(watched);
  }
});

document.getElementById("characterFilter").addEventListener("change", applyFilter);
document.getElementById("mapFilter").addEventListener("change", applyFilter);
document.getElementById("playerFilter").addEventListener("input", applyFilter);

document.getElementById("resetBtn").addEventListener("click", () => {
  document.getElementById("characterFilter").value = "";
  document.getElementById("mapFilter").value = "";
  document.getElementById("playerFilter").value = "";
  applyFilter();
});

loadData();