let state = null;
let busy = false;
let botTimer = 0;
let lastWaiting = null;
let betTo = null;
let tapeTab = "live";

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

function clampBet(v) {
  const b = state && state.bet;
  if (!b) return v;
  const x = Math.round(Number(v) * 2) / 2;
  return Math.min(b.max_to_bb, Math.max(b.min_to_bb, x));
}

function putAmount() {
  const b = state && state.bet;
  if (!b || betTo == null) return 0;
  return Math.max(0, Math.round((betTo - b.already_bb) * 100) / 100);
}

function refreshBetRead() {
  const b = state && state.bet;
  const input = $("bet-amount");
  const btn = $("bet-confirm");
  if (!b || betTo == null || !input || !btn) {
    const r = $("bet-read");
    if (r) r.textContent = "";
    return;
  }
  input.value = String(betTo);
  const add = putAmount();
  const potAfter = Math.round((b.pot_bb + add) * 10) / 10;
  const frac = b.pot_bb > 0 ? Math.round((add / b.pot_bb) * 100) : 0;
  const verb = b.kind === "raise" ? "加到" : "下注到";
  $("bet-read").textContent = `${verb} ${betTo}bb · 投入 ${add}bb · 底池→${potAfter}bb（${frac}%）`;
  btn.textContent = `打出 ${betTo}bb`;
  btn.disabled = add <= 0;
}

function setBetTo(v, fromUser) {
  betTo = clampBet(v);
  refreshBetRead();
  if (fromUser) $("bet-amount").focus();
}

function paintBetbox(reset) {
  const sizes = $("sizes");
  const custom = $("betbox");
  const b = state && state.bet;
  if (!b || state.waiting !== "hero") {
    sizes.hidden = true;
    custom.hidden = true;
    return;
  }
  sizes.hidden = false;
  custom.hidden = false;
  sizes.replaceChildren();
  for (const s of b.presets) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.innerHTML = `${s.label}<small>投入 ${s.add_bb}bb</small>`;
    btn.addEventListener("click", () => onAction(b.kind, s.to_bb));
    sizes.append(btn);
  }
  const input = $("bet-amount");
  input.min = b.min_to_bb;
  input.max = b.max_to_bb;
  input.step = b.step_bb;
  if (reset || betTo == null) betTo = b.default_to_bb;
  betTo = clampBet(betTo);
  refreshBetRead();
}

function paintLegal() {
  const root = $("legal");
  root.replaceChildren();
  if (!state || state.waiting !== "hero") return;
  const by = Object.fromEntries((state.legal || []).map((x) => [x.kind, x]));
  for (const k of ["fold", "check", "call"]) {
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
  const justHero = state && state.waiting === "hero" && lastWaiting !== "hero";
  lastWaiting = state ? state.waiting : null;
  if (state.waiting === "hero") {
    const b = state.bet;
    setHint(
      b
        ? "弃/跟一键生效。点 1/3、1/2、底池、全下直接下注。自定义填「加到」再点打出。"
        : "轮到你。F 弃 · X 过 · C 跟 · 空格 过/跟"
    );
  } else if (state.waiting === "bot") {
    setHint("对面在想。");
  } else if (state.waiting === "over") {
    setHint("这手结束。回车或点「下一手」。");
  } else {
    setHint("还没开局。");
  }
  paintLegal();
  paintBetbox(justHero);
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

async function onAction(kind, to) {
  if (busy || !state || state.waiting !== "hero") return;
  let to_bb = to;
  if (to_bb == null && kind === "call") {
    const c = state.legal.find((x) => x.kind === "call");
    to_bb = c ? c.to_bb : null;
  }
  busy = true;
  try {
    await apply(await api.act(kind, to_bb));
  } catch (e) {
    setHint(String(e.message || e));
  } finally {
    busy = false;
  }
}

function confirmBet() {
  if (!state || !state.bet || state.waiting !== "hero") return;
  onAction(state.bet.kind, clampBet(betTo));
}

function nudge(dir) {
  if (!state || !state.bet) return;
  const step = betTo >= 20 ? 1 : 0.5;
  setBetTo((betTo || state.bet.default_to_bb) + dir * step, true);
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

function setTape(tab) {
  tapeTab = tab;
  $("tab-live").classList.toggle("on", tab === "live");
  $("tab-hist").classList.toggle("on", tab === "hist");
  $("log").hidden = tab !== "live";
  $("hist").hidden = tab !== "hist";
}

function onKey(ev) {
  if (ev.target && ev.target.id === "bet-amount") {
    if (ev.key === "Enter") {
      ev.preventDefault();
      confirmBet();
    }
    return;
  }
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
  else if (k === " ") {
    ev.preventDefault();
    if (kinds.has("check")) onAction("check");
    else if (kinds.has("call")) onAction("call");
  } else if (k === "a" && state.bet) {
    const allin = state.bet.presets.find((s) => s.label === "全下");
    if (allin) onAction(state.bet.kind, allin.to_bb);
  } else if (k === "enter" && state.bet) {
    ev.preventDefault();
    confirmBet();
  } else if ((k === "+" || k === "=") && state.bet) {
    ev.preventDefault();
    nudge(1);
  } else if (k === "-" && state.bet) {
    ev.preventDefault();
    nudge(-1);
  } else if (state.bet && k >= "1" && k <= "4") {
    const p = state.bet.presets[Number(k) - 1];
    if (p) onAction(state.bet.kind, p.to_bb);
  }
}

$("bet-minus").addEventListener("click", () => nudge(-1));
$("bet-plus").addEventListener("click", () => nudge(1));
$("bet-confirm").addEventListener("click", confirmBet);
$("bet-amount").addEventListener("change", () => setBetTo($("bet-amount").value));
$("bet-amount").addEventListener("input", () => {
  const v = Number($("bet-amount").value);
  if (!Number.isNaN(v)) betTo = v;
  refreshBetRead();
});
$("btn-next").addEventListener("click", nextHand);
$("btn-new").addEventListener("click", newTable);
$("mode").addEventListener("change", newTable);
$("tab-live").addEventListener("click", () => setTape("live"));
$("tab-hist").addEventListener("click", () => setTape("hist"));
document.addEventListener("keydown", onKey);

(async function boot() {
  try {
    await apply(await api.state());
  } catch (e) {
    setHint("连不上引擎：" + e.message);
  }
})();
