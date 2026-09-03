const SEAT_XY = [
  [50, 90],
  [14, 78],
  [3, 50],
  [14, 22],
  [50, 9],
  [86, 22],
  [97, 50],
  [86, 78],
];

function visIndex(seat, hero, n) {
  return (seat - hero + n) % n;
}

function cardEl(c, hidden) {
  const d = document.createElement("div");
  if (hidden) {
    d.className = "pcard back";
    d.title = "未亮牌";
    return d;
  }
  d.className = "pcard" + (c.red ? " red" : "");
  d.innerHTML = `<span class="r">${c.rank}</span><span class="s">${{c:"♣",d:"♦",h:"♥",s:"♠"}[c.suit]}</span>`;
  return d;
}

function renderBoard(state) {
  const board = document.getElementById("board");
  board.replaceChildren();
  for (const c of state.board) board.append(cardEl(c));
  document.getElementById("pot-v").textContent = `${state.pot_bb.toFixed(1)}bb`;
  document.getElementById("street").textContent = state.street_zh;
}

function renderSeats(state) {
  const root = document.getElementById("seats");
  root.replaceChildren();
  const n = state.seats.length;
  for (const s of state.seats) {
    const i = visIndex(s.seat, state.hero_seat, n);
    const [x, y] = SEAT_XY[i] || [50, 50];
    const el = document.createElement("article");
    el.className = "seat";
    if (s.folded) el.classList.add("folded");
    if (s.acting) el.classList.add("acting");
    if (s.is_hero) el.classList.add("is-hero");
    el.style.left = x + "%";
    el.style.top = y + "%";
    const hud = s.hud ? `${s.hud.vpip}/${s.hud.pfr}` : "";
    const sub = s.is_hero
      ? s.position
      : [s.position, s.archetype_zh, s.session_zh].filter(Boolean).join(" · ");
    el.innerHTML = `
      <div class="ring">
        ${s.is_button ? '<span class="dealer">D</span>' : ""}
        ${s.is_sb ? '<span class="blind">SB</span>' : ""}
        ${s.is_bb ? '<span class="blind">BB</span>' : ""}
        <span class="stack">${s.stack_bb.toFixed(1)}</span>
        ${s.bet_bb > 0 && !s.folded ? `<span class="bet-chip">${s.bet_bb.toFixed(1)}</span>` : ""}
      </div>
      <p class="name">${s.name}${s.allin ? " · 全下" : ""}</p>
      <p class="meta">${sub}${hud ? " · " + hud : ""}</p>
      <div class="holes"></div>
    `;
    const holes = el.querySelector(".holes");
    if (s.hole) {
      for (const c of s.hole) holes.append(cardEl(c));
    } else if (s.hole_hidden) {
      holes.append(cardEl(null, true), cardEl(null, true));
    }
    root.append(el);
  }
}

function renderLog(state) {
  const ol = document.getElementById("log");
  ol.replaceChildren();
  for (const a of state.log) {
    const li = document.createElement("li");
    const extra = ["bet", "raise", "call"].includes(a.kind) ? ` ${a.to_bb}bb` : "";
    li.innerHTML = `<b>${a.name}</b> ${a.street_zh} ${a.kind_zh}${extra}`;
    ol.append(li);
  }
  ol.scrollTop = ol.scrollHeight;
}

function renderCoach(state) {
  const dl = document.getElementById("coach-dl");
  dl.replaceChildren();
  const c = state.coach;
  const rows = c
    ? [
        ["位置", c.position],
        ["SPR", c.spr],
        ["赔率", c.pot_odds ? Math.round(c.pot_odds * 100) + "%" : "—"],
        ["MDF", c.mdf ? Math.round(c.mdf * 100) + "%" : "—"],
        ["牌力", c.hand_class_zh],
        ["结构", c.texture_zh || "—"],
        ["胜率估", c.equity_est == null ? "—" : Math.round(c.equity_est * 100) + "%"],
        ["对手", c.n_opponents],
      ]
    : [["—", "还没发牌"]];
  for (const [k, v] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = k;
    const dd = document.createElement("dd");
    dd.textContent = v;
    dl.append(dt, dd);
  }
  document.getElementById("tags").textContent = (state.tags || []).join(" · ");
}

function renderMast(state) {
  document.getElementById("mast-meta").textContent =
    `第 ${state.hand_idx + 1} 手 · 已打 ${state.hands_played} · ${state.street_zh} · 底池 ${state.pot_bb}bb`;
}

function renderSlip(state) {
  const slip = document.getElementById("slip");
  if (state.waiting !== "over") {
    slip.hidden = true;
    return;
  }
  slip.hidden = false;
  const ul = document.getElementById("winners");
  ul.replaceChildren();
  for (const w of state.winners) {
    const li = document.createElement("li");
    li.textContent = `${w.name} 收 ${w.bb}bb`;
    ul.append(li);
  }
  if (!state.winners.length) {
    const li = document.createElement("li");
    li.textContent = "无人收池";
    ul.append(li);
  }
}

function renderAll(state) {
  renderMast(state);
  renderBoard(state);
  renderSeats(state);
  renderLog(state);
  renderCoach(state);
  renderSlip(state);
}
