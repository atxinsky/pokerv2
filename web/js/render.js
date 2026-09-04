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

const SUIT_CHAR = { c: "♣", d: "♦", h: "♥", s: "♠" };

/** SVG suit paths: distinct shapes across fonts. */
const SUIT_SVG = {
  s: '<svg class="suit-svg" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2C12 2 4 11 4 15.5A4.5 4.5 0 0 0 8.5 20c1.4 0 2.6-.6 3.5-1.6V22h.01-.01H12v-3.6c.9 1 2.1 1.6 3.5 1.6A4.5 4.5 0 0 0 20 15.5C20 11 12 2 12 2z"/></svg>',
  h: '<svg class="suit-svg" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 21S2 13.5 2 8.5A5.5 5.5 0 0 1 12 6.1 5.5 5.5 0 0 1 22 8.5C22 13.5 12 21 12 21z"/></svg>',
  d: '<svg class="suit-svg" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2L19 12 12 22 5 12 12 2z"/></svg>',
  c: '<svg class="suit-svg" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a4.2 4.2 0 0 0-1.7 8.1A4.2 4.2 0 1 0 7.5 17H11v3H9v2h6v-2h-2v-3h3.5a4.2 4.2 0 1 0-2.8-6.9A4.2 4.2 0 0 0 12 2z"/></svg>',
};

function suitMarkup(suit) {
  return SUIT_SVG[suit] || SUIT_CHAR[suit] || "?";
}

function rankShow(r) {
  return r === "T" ? "10" : r;
}

// Classic pip layout: corner holds rank+suit; center repeats suit
const PIP_XY = {
  1: [[50, 54]],
  2: [[50, 32], [50, 76]],
  3: [[50, 30], [50, 54], [50, 78]],
  4: [[32, 32], [68, 32], [32, 76], [68, 76]],
  5: [[32, 32], [68, 32], [50, 54], [32, 76], [68, 76]],
  6: [[32, 30], [68, 30], [32, 54], [68, 54], [32, 78], [68, 78]],
  7: [[32, 30], [68, 30], [50, 42], [32, 54], [68, 54], [32, 78], [68, 78]],
  8: [[32, 28], [68, 28], [50, 40], [32, 50], [68, 50], [32, 68], [68, 68], [50, 78]],
  9: [[32, 28], [68, 28], [32, 44], [68, 44], [50, 54], [32, 66], [68, 66], [32, 80], [68, 80]],
  10: [[32, 26], [68, 26], [50, 36], [32, 44], [68, 44], [32, 64], [68, 64], [50, 72], [32, 82], [68, 82]],
};

function cardEl(c, hidden) {
  const d = document.createElement("div");
  if (hidden) {
    d.className = "pcard back";
    d.title = "hidden";
    return d;
  }
  const su = c.suit;
  const rk = c.rank;
  const red = su === "h" || su === "d" || !!c.red;
  d.className = "pcard " + (red ? "red" : "black") + " rank-" + rk;
  let n = 1;
  if (rk === "A") n = 1;
  else if ("JQK".includes(rk)) n = 1;
  else n = rk === "T" ? 10 : Number(rk);
  const mark = suitMarkup(su);
  const pips = PIP_XY[n].map(
    ([x, y]) => `<span class="pip" style="left:${x}%;top:${y}%">${mark}</span>`
  ).join("");
  d.innerHTML = `<span class="corner"><b>${rankShow(rk)}</b><span class="suit">${mark}</span></span>${pips}`;
  d.title = rankShow(rk) + (SUIT_CHAR[su] || "");
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
    if (s.thinking || s.busy) el.classList.add("thinking");
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
    if (s.thinking || s.busy) {
      const th = document.createElement("p");
      th.className = "thinking-badge";
      th.textContent = "思考中…";
      el.append(th);
    } else if (s.say) {
      // 嘴炮气泡：textContent 渲染，LLM 输出不进 innerHTML
      const p = document.createElement("p");
      p.className = "say";
      p.textContent = `「${s.say}」`;
      el.append(p);
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
    if (h.llm_review || (rev && rev.llm)) {
      const sm = document.createElement("p");
      sm.className = "hist-llm";
      sm.textContent = h.llm_review || rev.llm;
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
  const say = document.getElementById("llm-say");
  if (say) {
    if (c && c.llm_comment) {
      say.textContent = "DeepSeek：" + c.llm_comment;
    } else if (state.llm && state.llm.enabled && state.waiting === "hero") {
      say.textContent = "DeepSeek 正在看这手…";
    } else {
      say.textContent = "";
    }
  }
  const feed = document.getElementById("llm-feed");
  if (feed) {
    const rows = (state.llm && state.llm.log) || [];
    feed.textContent = rows.slice(0, 2).map((r) => r.msg).join("  ·  ");
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
    const brain = !!state.llm.brain;
    pill.textContent = !state.llm.enabled
      ? "规则人格"
      : brain
        ? "对手 LLM"
        : "DeepSeek 接通";
    pill.classList.toggle("on", !!state.llm.enabled);
    pill.title = state.llm.hint || "";
  }
  const think = state.thinking;
  if (think && think.busy && think.name) {
    const feed = document.getElementById("llm-feed");
    if (feed && !feed.textContent.includes("思考")) {
      feed.textContent = `${think.name} 正在思考…`;
    }
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
  let meta = `第 ${state.hand_idx + 1} 手 · 已打 ${state.hands_played} · ${state.street_zh} · 底池 ${state.pot_bb}bb`;
  if (state.drill && state.drill.active) {
    meta += ` · 弱项：${state.drill.label || state.drill.id}`;
  }
  document.getElementById("mast-meta").textContent = meta;
  const pill = document.getElementById("drill-pill");
  if (pill) {
    if (state.drill && state.drill.active) {
      pill.hidden = false;
      pill.textContent = state.drill.focus || state.drill.label || "弱项训练";
      pill.title = state.drill.reason || "";
    } else {
      pill.hidden = true;
      pill.textContent = "";
    }
  }
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
  const rows = state.history || [];
  const last = rows.find((h) => h.hand_idx === (state.hand_review && state.hand_review.hand_idx)) || rows[0] || rows[rows.length - 1];
  const hr = state.hand_review;
  rv.textContent = (hr && hr.summary) || (last && last.review ? last.review.summary || "" : "");
  const llmEl = document.getElementById("slip-llm-review");
  const more = document.getElementById("btn-review-more-slip");
  if (llmEl) {
    if (hr && hr.busy && !hr.llm_review) llmEl.textContent = "教练正在复盘…";
    else if (hr && hr.llm_review) llmEl.textContent = hr.llm_review;
    else if (last && last.llm_review) llmEl.textContent = last.llm_review;
    else llmEl.textContent = "";
  }
  if (more) more.hidden = !(hr && (hr.llm_review || hr.summary));
}


function renderCoachPanel(state) {
  const ul = document.getElementById("coach-thoughts");
  const rev = document.getElementById("coach-review");
  const more = document.getElementById("btn-review-more");
  if (!ul || !rev) return;
  const panel = state.coach_panel || {};
  ul.replaceChildren();
  const thinking = panel.thinking || (state.thinking && state.thinking.busy ? state.thinking : null);
  if (thinking && thinking.name) {
    const li = document.createElement("li");
    li.className = "thinking-line";
    li.textContent = thinking.name + " 正在思考…";
    ul.append(li);
  }
  for (const row of panel.says || []) {
    const li = document.createElement("li");
    li.textContent = row.name + "：「" + row.say + "」";
    ul.append(li);
  }
  if (!ul.childElementCount) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = "暂无对手台词";
    ul.append(li);
  }
  const hr = panel.hand_review || state.hand_review;
  if (hr && hr.busy && !hr.llm_review) rev.textContent = "教练正在复盘…";
  else if (hr && hr.llm_review) rev.textContent = hr.llm_review;
  else if (hr && hr.summary) rev.textContent = hr.summary;
  else rev.textContent = "手结束后会出现 LLM 复盘";
  if (more) more.hidden = !(hr && (hr.llm_review || hr.summary));
}

function renderAll(state) {
  renderMast(state);
  renderBoard(state);
  renderSeats(state);
  renderLog(state);
  renderHud(state);
  renderHistory(state);
  renderCoach(state);
  renderCoachPanel(state);
  renderSlip(state);
}
