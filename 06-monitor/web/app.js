// The monitor page. Reads /api/snapshot and /api/events from the Studio. Nothing else.
// Every piece of data goes in as text (textContent), never as HTML.
"use strict";

const TABS = [
    { id: "alerts", label: "Alerts" },
    { id: "now", label: "Now" },
    { id: "agents", label: "Agents" },
    { id: "live", label: "Live" },
    { id: "tests", label: "Tests" },
];
const DAYS = [1, 7, 30];

const state = { tab: "alerts", days: 7, snap: null, live: false, fresh: new Map(), lastRow: null };

// ---------- tiny DOM helper: text only ----------
function el(tag, cls, ...kids) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    for (const k of kids.flat()) {
        if (k === null || k === undefined || k === false) continue;
        n.append(k instanceof Node ? k : document.createTextNode(String(k)));
    }
    return n;
}
const $ = (id) => document.getElementById(id);

// ---------- where am I: #tab&d=7, so a link or a refresh keeps the view ----------
function readHash() {
    const h = new URLSearchParams(location.hash.slice(1).replace(/^([a-z]+)/, "tab=$1"));
    if (TABS.some(t => t.id === h.get("tab"))) state.tab = h.get("tab");
    const d = Number(h.get("d"));
    if (DAYS.includes(d)) state.days = d;
}
function writeHash() {
    history.replaceState(null, "", `#${state.tab}&d=${state.days}`);
}

// ---------- the live connection ----------
let source = null;
function connect() {
    if (source) source.close();
    setConn("connecting…", "");
    source = new EventSource(`/api/events?days=${state.days}`);
    source.addEventListener("snapshot", (e) => {
        state.snap = JSON.parse(e.data);
        setConn("live", "live");
        render();
    });
    source.addEventListener("row", (e) => {
        const row = JSON.parse(e.data);
        state.fresh.set(key(row), Date.now());
        state.lastRow = Date.now();
        if (state.snap) state.snap.recent = [...state.snap.recent, row];
        render();
    });
    source.onerror = () => setConn("reconnecting…", "down");   // EventSource retries by itself
}
function setConn(text, cls) {
    state.live = cls === "live";
    $("conn").className = "conn " + cls;
    $("conn-text").textContent = text;
}
const key = (r) => JSON.stringify([r.time, r.agent, r.event, r.run || "", r.tool || "", r.chars || ""]);

// ---------- header ----------
function renderHeader() {
    const alerts = state.snap ? state.snap.alerts : [];
    const reds = alerts.filter(a => a.level === "red").length;
    const ambers = alerts.length - reds;
    const tabs = $("tabs");
    tabs.replaceChildren(...TABS.map(t => {
        const b = el("button", "tab" + (t.id === state.tab ? " on" : ""), t.label);
        if (t.id === "alerts") {
            if (reds) b.append(el("span", "badge red", reds));
            if (ambers) b.append(el("span", "badge amber", ambers));
        }
        b.onclick = () => { state.tab = t.id; writeHash(); render(); };
        return b;
    }));
    const days = $("days");
    days.replaceChildren("Last", ...DAYS.map(d => {
        const b = el("button", "day" + (d === state.days ? " on" : ""), d === 1 ? "day" : `${d} days`);
        b.onclick = () => { state.days = d; writeHash(); connect(); render(); };
        return b;
    }));
    $("updated").textContent = state.snap ? `updated ${state.snap.time.slice(11)}` : "";
}

// ---------- tabs ----------
function alertsView(s) {
    const box = el("div", "grid");
    if (!s.alerts.length) {
        box.append(el("div", "edge green", el("h3", "", "All clear"),
            el("p", "detail", "Constitution unchanged, model server up, nothing blocked or unverified, tests recent.")));
    }
    for (const a of s.alerts) {
        box.append(el("div", "edge " + a.level, el("h3", "", (a.level === "red" ? "✗ " : "! ") + a.what),
            a.detail ? el("p", "detail", a.detail) : null));
    }
    box.style.marginTop = "12px";
    return [el("h2", "", "Alerts"), el("p", "muted", `Red needs a look now. Amber can wait. Last ${s.days === 1 ? "day" : s.days + " days"}.`),
            box,
            el("div", "dark", el("h3", "", "What the monitor can’t see"),
                el("p", "", "It never sees what I asked, only how long the question was. It can’t change anything: it reads, and the agents never know it’s there."))];
}

function nowView(s) {
    const m = s.model_server;
    const c = s.constitution.state;
    const cTone = c === "approved, unchanged" ? "t-green" : (c === "changed" || c === "missing") ? "t-red" : "t-amber";
    const tiles = el("div", "grid g3",
        el("div", "tile " + cTone, el("p", "n", c === "approved, unchanged" ? "✓" : "!"), el("p", "l", "constitution: " + c)),
        el("div", "tile " + (m.up ? "t-green" : "t-red"), el("p", "n", m.up ? "up" : "down"), el("p", "l", m.up ? `model server · Ollama ${m.version}` : "model server")),
        el("div", "tile t-blue", el("p", "n", m.loaded.length), el("p", "l", "models loaded")),
    );
    const models = el("div", "card",
        el("h3", "", "Models"),
        ...(m.installed.length ? m.installed : []).map(x => {
            const loaded = m.loaded.find(l => l.model === x.model);
            return el("div", "row", el("span", "mono", x.model),
                el("span", "", loaded ? el("span", "pill green", `loaded · ${loaded.gb} GB · until ${loaded.until.slice(11, 16)}`)
                    : x.ok ? el("span", "pill gray", "installed") : el("span", "pill red", "missing")));
        }),
        m.up ? null : el("p", "muted", `Not answering at ${m.url}`));
    const machines = el("div", "card",
        el("h3", "", "Machines (Tailscale)"),
        ...(s.machines.length ? s.machines.map(x => el("div", "row",
            el("span", "", el("span", "mdot" + (x.online ? " on" : "")), x.name),
            el("span", "muted", x.online ? (x.seen === "this Mac" ? "this Mac" : "online") : `offline · ${x.seen}`)))
            : [el("p", "muted", "Can’t see Tailscale from here.")]));
    const perms = el("div", "card",
        el("h3", "", "Permissions"),
        ...s.permissions.map(p => el("div", "row", el("span", "", p.what),
            el("span", "", p.mode === null ? el("span", "pill gray", "not there yet")
                : el("span", "pill " + (p.ok ? "green" : "red"), `${p.mode}${p.ok ? "" : " · want " + p.want}`)))));
    return [el("h2", "", "Now"), tiles, el("div", "grid g2", models, machines), el("div", "grid g2", perms)].map(x => {
        if (x.classList && x.classList.contains("g2")) x.style.marginTop = "12px";
        return x;
    });
}

function agentsView(s) {
    if (!s.agents.length) return [el("h2", "", "Agents"), el("p", "muted", "Nothing in the ledger yet. Ask an agent something.")];
    return [el("h2", "", "Agents"), el("p", "muted", `${s.ledger.rows} ledger rows. Last ${s.days === 1 ? "day" : s.days + " days"}.`),
        el("div", "grid", ...s.agents.map(a => el("div", "card",
            el("div", "row", el("h3", "", a.agent),
                el("span", "muted", a.running ? el("span", "pill green", "running now") : `last ${a.last_ago}`)),
            el("div", "grid g3",
                tile(a.runs, `runs (${a.runs_today} today)`, "t-blue"),
                tile(a.tool_calls, `tool calls · ${a.direct} direct`, "t-gray"),
                tile(a.typical_s === null ? "—" : `${a.typical_s} s`, a.slowest_s === null ? "no answers yet" : `typical · slowest ${a.slowest_s} s`, "t-gray"),
                tile(a.blocked, "blocked", a.blocked ? "t-red" : "t-green"),
                tile(a.unverified, "unverified dates", a.unverified ? "t-red" : "t-green"),
                tile(a.unfinished, "no answer", a.unfinished ? "t-amber" : "t-green"),
            ))))];
}
function tile(n, label, tone) {
    return el("div", "tile " + tone, el("p", "n", n), el("p", "l", label));
}

function describe(e) {
    const args = Object.values(e.args || {}).map(v => v.join(" ")).join(" ");
    const hidden = e.hidden ? ` (+${e.hidden} hidden)` : "";
    switch (e.event) {
        case "question": return `${e.chars} chars · ${e.model || ""}`;
        case "tool": return [`${e.tool} ${e.ok ? "ok" : "NOT OK"}`, `${e.seconds} s`, args].filter(Boolean).join(" · ") + hidden;
        case "blocked": return `${e.tool} · ${e.reason}`;
        case "answer": return `${e.tool_calls} calls · ${e.blocked} blocked · ${e.unverified} unverified · ${e.seconds} s`;
        case "direct": return args + hidden;
        default: return "";
    }
}
function tone(e) {
    if (e.event === "blocked" || (e.event === "tool" && !e.ok) || (e.event === "answer" && (e.unverified || e.blocked))) return "red";
    if (e.event === "answer") return "green";
    return "gray";
}

function liveView(s) {
    const rows = [...s.recent].reverse();
    const since = state.lastRow ? `last new row ${Math.round((Date.now() - state.lastRow) / 1000)} s ago` : "waiting for the next row";
    const list = el("div", "list",
        el("div", "li head", el("span", "", "Time"), el("span", "", "Agent"), el("span", "", "Event"), el("span", "", "What")),
        ...rows.map(e => el("div", "li" + (state.fresh.has(key(e)) ? " fresh" : ""),
            el("span", "when", e.time.slice(5)), el("span", "who", e.agent),
            el("span", "ev", el("span", "pill " + tone(e), e.event)), el("span", "what", describe(e)))));
    list.style.marginTop = "12px";
    return [el("h2", "", "Live"),
        el("p", "muted", `${state.live ? "Connected: new rows appear as the agents write them" : "Not connected"} · ${since}. Questions show as length only.`),
        rows.length ? list : el("p", "muted", "No events in this window.")];
}

function testsView(s) {
    const list = el("div", "list tests",
        el("div", "li head", el("span", "", "Test"), el("span", "", "Result"), el("span", "", "When"), el("span", "", "")),
        ...s.tests.map(t => {
            const stale = t.age_days !== null && t.age_days > 14;
            const pill = t.when === null ? el("span", "pill amber", "never run")
                : t.ok === false ? el("span", "pill red", "missed")
                : t.ok === null ? el("span", "pill amber", "look")
                : stale ? el("span", "pill amber", "old") : el("span", "pill green", "ok");
            return el("div", "li", el("span", "who", t.test), el("span", "what", t.result || "—"),
                el("span", "when", t.when ? `${t.when} (${t.age_days} d)` : "—"), el("span", "ev", pill));
        }));
    list.style.marginTop = "12px";
    return [el("h2", "", "Tests"), el("p", "muted", "Score lines only. The answers stay in the vault."), list];
}

// ---------- draw ----------
function render() {
    renderHeader();
    const s = state.snap;
    if (!s) return;
    const view = { alerts: alertsView, now: nowView, agents: agentsView, live: liveView, tests: testsView }[state.tab];
    $("main").replaceChildren(...view(s).filter(Boolean));
}

// forget highlights after a few seconds, and keep the "s ago" honest
setInterval(() => {
    const cut = Date.now() - 4000;
    let changed = false;
    for (const [k, t] of state.fresh) if (t < cut) { state.fresh.delete(k); changed = true; }
    if (changed || state.tab === "live") render();
}, 1000);

window.addEventListener("hashchange", () => {   // links and the back button
    const days = state.days;
    readHash();
    if (state.days !== days) connect();
    render();
});

readHash();
render();
connect();
