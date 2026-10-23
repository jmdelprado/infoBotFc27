// Lee por stdin el HTML de fut.gg/evolutions y escribe por stdout el JSON de las evoluciones.
// La web incrusta los datos como scripts ($R = serialización de TanStack Router); se ejecutan en un sandbox.
const vm = require("vm");
let html = "";
process.stdin.on("data", (d) => (html += d));
process.stdin.on("end", () => {
  const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)]
    .map((m) => m[1])
    .filter((s) => s.includes("$R"));
  const noop = () => {};
  const fakeEl = { remove: noop, setAttribute: noop, appendChild: noop };
  const sandbox = {
    console,
    document: { currentScript: fakeEl, createElement: () => fakeEl, querySelector: () => null,
                getElementById: () => null, head: fakeEl, body: fakeEl, addEventListener: noop },
    window: {}, location: { href: "" }, history: { state: {} }, sessionStorage: { getItem: () => null },
    setTimeout: noop, queueMicrotask: noop,
  };
  sandbox.self = sandbox;
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  for (const s of scripts) {
    try { vm.runInContext(s, sandbox, { timeout: 5000 }); } catch (e) { /* scripts de la web que no hacen falta */ }
  }
  // Busca en todo lo deserializado los objetos {evolution: {...}}
  const out = [], seen = new Set(), visited = new WeakSet();
  const walk = (o, depth) => {
    if (!o || typeof o !== "object" || depth > 12 || visited.has(o)) return;
    visited.add(o);
    if (o.evolution && typeof o.evolution === "object" && o.evolution.id && !seen.has(o.evolution.id)) {
      seen.add(o.evolution.id);
      out.push(o.evolution);
    }
    for (const k of Object.keys(o)) walk(o[k], depth + 1);
  };
  walk(sandbox.$R, 0);
  const pick = (e) => ({
    id: e.id, name: e.name, description: e.description, url: e.url,
    coinsCost: e.coinsCost, pointsCost: e.pointsCost, tokenCost: e.tokenCost,
    createdAt: e.createdAt, endTime: e.endTime, endSubmissionTime: e.endSubmissionTime,
    isTimed: e.isTimed, repeatabilityCount: e.repeatabilityCount, numberOfPlayers: e.numberOfPlayers,
    maxOverall: e.requirements && e.requirements.maxOverall, minOverall: e.requirements && e.requirements.minOverall,
    positions: e.requirements && e.requirements.positions, rarities: e.requirements && e.requirements.rarities,
    upgrades: (e.totalUpgradesText || []).map((u) => ({ label: u.label, value: u.value, maxValue: u.maxValue })),
    levels: (e.levels || []).length,
  });
  process.stdout.write(JSON.stringify(out.map(pick)));
});
