let state = null;
let busy = false;
let botTimer = 0;
let pendingKind = null;

function $(id) {
  return document.getElementById(id);
}

function setHint(text) {
  $("hint").textContent = text;
}

function clearBotTimer() {
  if (botTimer) {
    clearTimeout(botTimer);
    botTimer = 0;
  }
}

function betKind() {
  const kinds = new Set((state.legal || []).map((x) => x.kind));
  if (kinds.has("raise")) return "raise";
  if (kinds.has("bet")) return "bet";
  return null;
}

function minMaxTo() {
  const kind = betKind();
  const sizes = (state.sizings || []).filter((s) => s.kind === kind);
  if (!sizes.length) return [0, 0];
  const vals = sizes.map((s) => s.to_bb);
  return [Math.min(...vals), Math.max(...vals)];
}

function paintBetbox() {
  const box = $("betbox");
  const kind = betKind();
  if (!kind || state.waiting !== "hero") {
    box.hidden = true;
    pendingKind = null;
    return;
  }
  box.hidden = false;
  pendingKind = kind;
  const [lo, hi] = minMaxTo();
  const range = $("bet-range");
  range.min = String(lo);
  range.max = String(hi);
  range.step = "0.5";
  if (Number(range.value) < lo || Number(range.value) > hi) range.value = String(lo);
  $("bet-read").textContent = Number(range.value).toFixed(1) + "bb";
  const ticks = $("ticks");
  ticks.replaceChildren();
  for (const s of state.sizings.filter((x) => x.kind === kind)) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = s.label;
    b.addEventListener("click", () => {
      range.value = String(s.to_bb);
      $("bet-read").textContent = s.to_bb.toFixed(1) + "bb";
    });
    ticks.append(b);
  }
}

function paintLegal() {
  const root = $("legal");
  root.replaceChildren();
  if (state.waiting !== "hero") return;
  const order = ["fold", "check", "call", "bet", "raise"];
  const by = Object.fromEntries((state.legal || []).map((x) => [x.kind, x]));
  for (const k of order) {
    if (!by[k]) continue;
    const b = document.createElement("button");
    b.type = "button";
    b.className = k;
    b.textContent = by[k].label;
    b.addEventListener("click", () => onAction(k));
    root.append(b);
  }
}

function syncTray() {
  if (state.waiting === "hero") {
    setHint("轮到你。F 弃 · X 过 · C 跟 · 空格 过/跟 · A 全下 · 回车 确认尺度");
  } else if (state.waiting === "bot") {
    setHint("对面在想。");
  } else if (state.waiting === "over") {
    setHint("这手结束。回车或点「下一手」。");
  } else {
    setHint("还没开局。");
  }
  paintLegal();
  paintBetbox();
}

async function apply(next) {
  state = next;
  renderAll(state);
  syncTray();
  scheduleBot();
}

function scheduleBot() {
  clearBotTimer();
  if (!state || state.waiting !== "bot") return;
  botTimer = setTimeout(async () => {
    if (busy) {
      scheduleBot();
      return;
    }
    try {
      busy = true;
      await apply(await api.step());
    } catch (e) {
      setHint(String(e.message || e));
    } finally {
      busy = false;
    }
  }, 420);
}

async function onAction(kind) {
  if (busy || !state || state.waiting !== "hero") return;
  let to = null;
  if (kind === "bet" || kind === "raise") {
    to = Number($("bet-range").value);
  } else if (kind === "call") {
    const c = state.legal.find((x) => x.kind === "call");
    to = c ? c.to_bb : null;
  }
  busy = true;
  try {
    await apply(await api.act(kind, to));
  } catch (e) {
    setHint(String(e.message || e));
  } finally {
    busy = false;
  }
}

async function nextHand() {
  if (busy) return;
  busy = true;
  try {
    await apply(await api.hand());
  } catch (e) {
    setHint(String(e.message || e));
  } finally {
    busy = false;
  }
}

async function newTable() {
  if (busy) return;
  const mode = $("mode").value;
  const seed = Math.floor(Math.random() * 1e9);
  busy = true;
  try {
    await apply(await api.neu(seed, mode));
  } catch (e) {
    setHint(String(e.message || e));
  } finally {
    busy = false;
  }
}

function onKey(ev) {
  if (ev.target && ["INPUT", "SELECT", "TEXTAREA"].includes(ev.target.tagName)) return;
  const k = ev.key.toLowerCase();
  if (state && state.waiting === "over" && (k === "enter" || k === "n")) {
    ev.preventDefault();
    nextHand();
    return;
  }
  if (!state || state.waiting !== "hero") return;
  const kinds = new Set(state.legal.map((x) => x.kind));
  if (k === "f" && kinds.has("fold")) onAction("fold");
  else if (k === "x" && kinds.has("check")) onAction("check");
  else if (k === "c" && kinds.has("call")) onAction("call");
  else if (k === " " ) {
    ev.preventDefault();
    if (kinds.has("check")) onAction("check");
    else if (kinds.has("call")) onAction("call");
  } else if (k === "a") {
    const sizes = state.sizings || [];
    const allin = sizes.find((s) => s.label === "全下");
    if (allin) {
      $("bet-range").value = String(allin.to_bb);
      onAction(allin.kind);
    }
  } else if (k === "enter" && (kinds.has("bet") || kinds.has("raise"))) {
    onAction(betKind());
  }
}

$("bet-range").addEventListener("input", () => {
  $("bet-read").textContent = Number($("bet-range").value).toFixed(1) + "bb";
});
$("btn-next").addEventListener("click", nextHand);
$("btn-new").addEventListener("click", newTable);
$("mode").addEventListener("change", newTable);
document.addEventListener("keydown", onKey);

(async function boot() {
  try {
    await apply(await api.state());
  } catch (e) {
    setHint("连不上引擎：" + e.message);
  }
})();
