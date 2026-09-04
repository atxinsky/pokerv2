const api = {
  async get(path) {
    const r = await fetch(path, { cache: "no-store" });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "请求失败");
    return data;
  },
  state: () => api.get("/api/state"),
  neu: (seed, mode, wait_llm) => api.post("/api/new", { seed, mode, wait_llm: !!wait_llm }),
  pingLlm: () => api.post("/api/llm-ping", {}),
  hand: () => api.post("/api/hand", {}),
  step: () => api.post("/api/step", {}),
  act: (kind, to_bb) => api.post("/api/action", { kind, to_bb }),
  settings: () => api.get("/api/settings"),
  saveSettings: (body) => api.post("/api/settings", body),
  reviewDetail: () => api.post("/api/review-detail", {}),
  lowerIntensity: () => api.post("/api/usage/lower", {}),
};
