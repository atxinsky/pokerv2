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

const SUIT = { c: "♣", d: "♦", h: "♥", s: "♠" };

function rankShow(r) {
  return r === "T" ? "10" : r;
}

// 花色坐标：像实体扑克，不在中间再堆一个点数
const PIP_XY = {
  1: [[50, 54]],
  2: [[50, 22], [50, 80]],
  3: [[50, 22], [50, 54], [50, 80]],
  4: [[28, 24], [72, 24], [28, 80], [72, 80]],
  5: [[28, 24], [72, 24], [50, 54], [28, 80], [72, 80]],
  6: [[28, 24], [72, 24], [28, 54], [72, 54], [28, 80], [72, 80]],
  7: [[28, 22], [72, 22], [50, 40], [28, 54], [72, 54], [28, 82], [72, 82]],
  8: [[28, 20], [72, 20], [28, 40], [72, 40], [28, 64], [72, 64], [28, 84], [72, 84]],
  9: [[28, 18], [72, 18], [28, 38], [72, 38], [50, 54], [28, 70], [72, 70], [28, 86], [72, 86]],
  10: [[28, 16], [72, 16], [50, 32], [28, 42], [72, 42], [28, 62], [72, 62], [50, 72], [28, 86], [72, 86]],
};

function cardEl(c, hidden) {
  const d = document.createElement("div");
  if (hidden) {
    d.className = "pcard back";
    d.title = "未亮牌";
    return d;
  }
  const su = SUIT[c.suit];
  const rk = c.rank;
  d.className = "pcard " + (c.red ? "red" : "black") + " rank-" + rk;
  let n = 1;
  if (rk === "A") n = 1;
  else if ("JQK".includes(rk)) n = 1;
  else n = rk === "T" ? 10 : Number(rk);
  const pips = PIP_XY[n].map(
    ([x, y]) => `<i class="pip" style="left:${x}%;top:${y}%">${su}</i>`
  ).join("");
  d.innerHTML = `<span class="corner"><b>${rankShow(rk)}</b><i>${su}</i></span>${pips}`;
  d.title = rankShow(rk) + su;
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
      ${s.notes && s.notes.length ? `<p class="notes">${s.notes[0]}</p>` : ""}
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

function logText(a) {
  if (a.kind === "fold" || a.kind === "check") return a.kind_zh;
  if (a.kind === "call") return `跟注 ${a.put_bb}bb`;
  if (a.kind === "bet") return `下注 ${a.put_bb}bb`;
  if (a.kind === "raise") return `加到 ${a.to_bb}bb`;
  return a.kind_zh;
}

function renderLog(state) {
  const ol = document.getElementById("log");
  ol.replaceChildren();
  let street = null;
  for (const a of state.log) {
    if (a.street_zh !== street) {
      street = a.street_zh;
      const h = document.createElement("li");
      h.className = "street-mark";
      h.textContent = street;
      ol.append(h);
    }
    const li = document.createElement("li");
    li.innerHTML = `<b>${a.name}</b> ${logText(a)}`;
    ol.append(li);
  }
  ol.scrollTop = ol.scrollHeight;
}

function renderHud(state) {
  const el = document.getElementById("hero-hud");
  const s = state.hero_stats || {};
  const bb = s.bb || 0;
  const cls = bb > 0 ? "up" : bb < 0 ? "down" : "";
  el.innerHTML = `
    <div><span>手数</span><b>${s.hands || 0}</b></div>
    <div><span>bb/100</span><b class="${cls}">${s.hands >= 8 ? s.bb100 : "—"}</b></div>
    <div><span>VPIP / PFR</span><b>${s.vpip || 0} / ${s.pfr || 0}</b></div>
    <div><span>本场</span><b class="${cls}">${bb > 0 ? "+" : ""}${bb}bb</b></div>
  `;
}

function renderHistory(state) {
  const ol = document.getElementById("hist");
  const tab = document.getElementById("tab-hist");
  const n = (state.history || []).length;
  tab.textContent = n ? `历史 ${n}` : "历史";
  ol.replaceChildren();
  const rows = state.history || [];
  if (!rows.length) {
    const li = document.createElement("li");
    li.textContent = "打完的手会出现在这里";
    ol.append(li);
    return;
  }
  for (const h of rows) {
    const li = document.createElement("li");
    li.className = "hist-item";
    const dlt = h.delta_bb > 0 ? `+${h.delta_bb}` : String(h.delta_bb);
    const cls = h.delta_bb > 0 ? "up" : h.delta_bb < 0 ? "down" : "";
    const hole = document.createElement("div");
    hole.className = "mini";
    for (const c of h.hole || []) hole.append(cardEl(c));
    const board = document.createElement("div");
    board.className = "mini";
    for (const c of h.board || []) board.append(cardEl(c));
    const detail = (h.log || []).map((a) => `${a.name} ${logText(a)}`).join(" · ");
    li.innerHTML = `<div class="row"><b>#${h.hand_idx + 1}</b><span class="delta ${cls}">${dlt}bb</span></div>`;
    li.append(hole, board);
    const rev = h.review || {};
    if (rev.summary) {
      const sm = document.createElement("p");
      sm.className = "hist-sum";
      sm.textContent = rev.summary;
      li.append(sm);
    }
    const d = document.createElement("div");
    d.className = "hist-detail";
    const notes = (rev.notes || []).join(" ");
    d.textContent = [notes, detail].filter(Boolean).join(" · ") || "无行动";
    li.append(d);
    li.addEventListener("click", () => li.classList.toggle("open"));
    ol.append(li);
  }
}

function renderCoach(state) {
  const c = state.coach;
  const eqEl = document.getElementById("eq-big");
  const adv = document.getElementById("advice");
  if (!c) {
    eqEl.textContent = "—";
    adv.textContent = "发牌后给出这个位置该怎么打";
  } else {
    const eq = c.equity != null ? c.equity : c.equity_est;
    eqEl.textContent = eq == null ? "翻前" : `胜率 ${Math.round(eq * 100)}%`;
    const act = c.action_zh ? `建议：${c.action_zh}` : "";
    const size = c.size_hint ? ` ${c.size_hint}。` : "";
    adv.textContent = [act, c.why, size].filter(Boolean).join(" ");
  }
  const dl = document.getElementById("coach-dl");
  dl.replaceChildren();
  const rows = c
    ? [
        ["手牌", c.code || "—"],
        ["位置", c.position],
        ["SPR", c.spr],
        ["赔率", c.pot_odds ? Math.round(c.pot_odds * 100) + "%" : "—"],
        ["MDF", c.mdf ? Math.round(c.mdf * 100) + "%" : "—"],
        ["牌力", c.hand_class_zh],
        ["结构", c.texture_zh || c.texture || "—"],
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
  document.getElementById("chart-title").textContent = (c && c.chart_title) || "范围图";
  renderGrid(c && c.grid);
  const pill = document.getElementById("llm-pill");
  if (state.llm) {
    pill.textContent = state.llm.enabled ? "DeepSeek 接通" : "规则人格";
    pill.classList.toggle("on", !!state.llm.enabled);
    pill.title = state.llm.hint || "";
  }
}

function renderGrid(grid) {
  const el = document.getElementById("gto-grid");
  el.replaceChildren();
  if (!grid) return;
  for (const row of grid) {
    for (const cell of row) {
      const i = document.createElement("i");
      i.textContent = cell.code;
      if (cell.on) i.classList.add("on");
      if (cell.hero) i.classList.add("hero");
      el.append(i);
    }
  }
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
  const rv = document.getElementById("slip-review");
  const last = (state.history || [])[state.history.length - 1];
  rv.textContent = last && last.review ? last.review.summary || "" : "";
}

function renderAll(state) {
  renderMast(state);
  renderBoard(state);
  renderSeats(state);
  renderLog(state);
  renderHud(state);
  renderHistory(state);
  renderCoach(state);
  renderSlip(state);
}
