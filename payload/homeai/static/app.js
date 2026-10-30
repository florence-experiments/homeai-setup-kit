/* Built by Florence for the community. */
/* HomeAI frontend - vanilla JS, no build step. Talks to server.py (/api/*), which proxies /api/llama/* to llama-server. */
'use strict';
(() => {
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const LLAMA = '/api/llama';
const now = () => Date.now() / 1000;
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (n, d = 0) => (n == null || isNaN(n)) ? '–' : Number(n).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d });
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

/* ---------------- icons (lucide-style) ---------------- */
const P = {
  plus: '<path d="M12 5v14M5 12h14"/>', search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>', pin: '<path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>', trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>', check: '<path d="M20 6 9 17l-5-5"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M8 16H3v5"/>',
  stop: '<rect x="5" y="5" width="14" height="14" rx="2.5" fill="currentColor" stroke="none"/>', send: '<path d="M12 19V5"/><path d="m5 12 7-7 7 7"/>',
  clip: '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
  sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>', sidebar: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>', x: '<path d="M18 6 6 18M6 6l12 12"/>',
  brain: '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/><path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4"/><path d="M12 18V5"/>',
  eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>', code: '<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>',
  sparkles: '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
  file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="m10 13-2 2 2 2M14 17l2-2-2-2"/>',
  cpu: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M15 2v2M15 20v2M2 15h2M2 9h2M20 15h2M20 9h2M9 2v2M9 20v2"/>',
  zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>', upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
  alert: '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>', power: '<path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.77.04"/>',
  arrowDown: '<path d="M12 5v14M19 12l-7 7-7-7"/>', gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>', clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  layers: '<path d="m12 2 10 5-10 5L2 7l10-5z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>', info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
  feather: '<path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z"/><path d="M16 8 2 22M17.5 15H9"/>', globe: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
  terminal: '<path d="m4 17 6-6-6-6M12 19h8"/>',
  mic: '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><path d="M12 19v3"/>',
  volume: '<path d="M11 4.7a.7.7 0 0 0-1.2-.5L6.4 7.6a1.4 1.4 0 0 1-1 .4H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.4a1.4 1.4 0 0 1 1 .4l3.4 3.4a.7.7 0 0 0 1.2-.5z"/><path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.4 18.4a9 9 0 0 0 0-12.8"/>',
  volumeOff: '<path d="M11 4.7a.7.7 0 0 0-1.2-.5L6.4 7.6a1.4 1.4 0 0 1-1 .4H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.4a1.4 1.4 0 0 1 1 .4l3.4 3.4a.7.7 0 0 0 1.2-.5z"/><path d="m22 9-6 6M16 9l6 6"/>',
  chevronUp: '<path d="m18 15-6-6-6 6"/>', play: '<path d="M6 4.5v15a1 1 0 0 0 1.5.86l12.5-7.5a1 1 0 0 0 0-1.72L7.5 3.64A1 1 0 0 0 6 4.5z"/>',
  lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  hand: '<path d="M18 11V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2"/><path d="M14 10V4a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2"/><path d="M10 10.5V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/>',
  external: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>', pen: '<path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/>',
  palette: '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>',
};
const icon = (n) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${P[n] || ''}</svg>`;
const PRESET_ICONS = ['sparkles', 'code', 'image', 'brain', 'feather', 'terminal', 'globe', 'pen', 'zap', 'cpu'];
const PRESET_COLORS = ['#8b5cf6', '#6366f1', '#10b981', '#06b6d4', '#f59e0b', '#ef4444', '#ec4899', '#64748b'];

/* ---------------- defaults ---------------- */
const DEFAULT_PARAMS = { temperature: 0.7, top_p: 0.9, top_k: 40, min_p: 0.05, max_tokens: 0, repeat_penalty: 1.0, seed: -1 };
/* 'Model default' sampling (v1.1.0+modeldefault): for each of these keys, when model_default[key] is not false the field is
   left out of the request so the llama.cpp preset (models.ini) applies. Missing model_default = all ON. */
const SAMPLING_KEYS = ['temperature', 'top_p', 'top_k', 'min_p', 'repeat_penalty'];
const MD_ALL = () => Object.fromEntries(SAMPLING_KEYS.map(k => [k, true]));
const mdOn = (s, k) => !(s && s.model_default && s.model_default[k] === false);
const mdCopy = (s) => Object.fromEntries(SAMPLING_KEYS.map(k => [k, mdOn(s, k)]));
const R = window.HomeAIRouter;
const AUTO = '__auto__';
/* Preset "model" may be: 'auto', '@<routing profile key>' (exact id / pattern from Settings → Routing),
   an exact model id, or a pattern like "qwen 8b -vision | other" (all words must appear, -word must not).
   Several choices separated by commas are tried in order: "@vision, @caption". A fresh install has General and
   Coding; '+ Add mode' (next to the preset buttons) adds more. */
const DEFAULT_PRESETS = [
  {"id": "general", "name": "General", "color": "#6366f1", "icon": "globe", "model": "@general", "thinking": "off", "starter": "", "desc": "Everyday chat, questions, explanations and ideas.", "system": "You are HomeAI, a helpful, knowledgeable and concise assistant running locally. Use Markdown (headings, lists, tables, LaTeX with $...$) when it improves clarity.", "params": {"temperature": 0.7, "top_p": 0.9, "top_k": 40, "min_p": 0.05, "max_tokens": 0, "repeat_penalty": 1.0, "seed": -1, "model_default": {"temperature": false, "top_p": true, "top_k": true, "min_p": true, "repeat_penalty": true}}},
  {"id": "coding", "name": "Coding", "color": "#10b981", "icon": "code", "model": "@coding", "thinking": "auto", "starter": "", "desc": "Code, scripts, refactors and debugging.", "system": "You are an expert software engineer. Write correct, idiomatic, production-quality code. Always use fenced code blocks with a language tag. Briefly explain the approach, then show the code. Point out edge cases and pitfalls.", "params": {"temperature": 0.2, "top_p": 0.9, "top_k": 40, "min_p": 0.05, "max_tokens": 0, "repeat_penalty": 1.05, "seed": -1, "model_default": {"temperature": false, "top_p": true, "top_k": true, "min_p": true, "repeat_penalty": true}}},
];
const DEFAULT_SETTINGS = { sendKey: 'enter', preloadOnSelect: true, returnProgress: true, autoTitle: true, defaultPreset: 'general', collapseThinking: true, presetsVersion: 3 };
const TEXT_EXT = 'txt md markdown py js mjs cjs ts tsx jsx json jsonc yaml yml toml ini cfg conf env c h cpp hpp cc cs java kt go rs rb php pl lua sh bash zsh ps1 psm1 bat cmd sql html htm css scss less xml svg csv tsv log r swift dart vue svelte gradle cmake makefile dockerfile tex rst srt vtt gitignore'.split(' ');
const LANG_BY_EXT = { py: 'python', js: 'javascript', mjs: 'javascript', cjs: 'javascript', ts: 'typescript', tsx: 'tsx', jsx: 'jsx', yml: 'yaml', rs: 'rust', rb: 'ruby', ps1: 'powershell', psm1: 'powershell', bat: 'dos', cmd: 'dos', sh: 'bash', zsh: 'bash', md: 'markdown', htm: 'html', h: 'c', hpp: 'cpp', cc: 'cpp', cs: 'csharp', kt: 'kotlin' };

/* ---------------- state ---------------- */
const S = {
  chats: [], chat: null, models: [], mode: 'router', serverOk: null, router: null,
  presets: [], settings: { ...DEFAULT_SETTINGS }, theme: 'dark',
  att: { images: [], files: [] }, gen: null, nctx: {}, search: '',
  drawerTab: 'chat', editingPreset: null, pollT: null, wanted: null, routing: R.mergeRouting(null),
};

/* ---------------- API ---------------- */
async function api(path, opts = {}) {
  const o = { ...opts };
  if (o.body !== undefined && typeof o.body !== 'string') { o.body = JSON.stringify(o.body); o.headers = { 'Content-Type': 'application/json', ...(o.headers || {}) }; }
  const r = await fetch(path, o);
  const txt = await r.text(); let data = null;
  try { data = txt ? JSON.parse(txt) : null; } catch { data = { raw: txt }; }
  if (!r.ok) { const e = new Error(data?.error?.message || data?.raw || r.statusText || ('HTTP ' + r.status)); e.status = r.status; throw e; }
  return data;
}
const store = {
  get: async (k) => (await api('/api/store/' + k)).value,
  put: (k, v) => api('/api/store/' + k, { method: 'PUT', body: { value: v } }),
};

/* ---------------- markdown ---------------- */
let RENDER_STREAMING = false;
function katexRender(tex, display) {
  try { return katex.renderToString(tex, { displayMode: display, throwOnError: false, output: 'html', strict: 'ignore' }); }
  catch { return `<code>${esc(tex)}</code>`; }
}
marked.use({
  gfm: true, breaks: false,
  extensions: [
    { name: 'mathBlock', level: 'block',
      start(src) { const i = src.search(/\$\$|\\\[/); return i < 0 ? undefined : i; },
      tokenizer(src) { const m = /^\$\$([\s\S]+?)\$\$/.exec(src) || /^\\\[([\s\S]+?)\\\]/.exec(src); if (m) return { type: 'mathBlock', raw: m[0], text: m[1].trim() }; },
      renderer(t) { return `<div class="math-block">${katexRender(t.text, true)}</div>`; } },
    { name: 'mathInline', level: 'inline',
      start(src) { const i = src.search(/\$|\\\(|\\\[/); return i < 0 ? undefined : i; },
      tokenizer(src) {
        let m = /^\$\$([\s\S]+?)\$\$/.exec(src) || /^\\\[([\s\S]+?)\\\]/.exec(src);
        if (m) return { type: 'mathInline', raw: m[0], text: m[1].trim(), display: true };
        m = /^\\\(([\s\S]+?)\\\)/.exec(src) || /^\$(?![\s$])((?:\\.|[^\\$\n])+?)(?<![\s\\])\$(?![\d$])/.exec(src);
        if (m) return { type: 'mathInline', raw: m[0], text: m[1], display: false };
      },
      renderer(t) { return katexRender(t.text, t.display); } },
  ],
  renderer: {
    code({ text, lang }) {
      const l = (lang || '').trim().split(/\s+/)[0].toLowerCase();
      let html;
      try {
        if (l && hljs.getLanguage(l)) html = hljs.highlight(text, { language: l, ignoreIllegals: true }).value;
        else if (!RENDER_STREAMING && text.length < 8000 && !l) html = hljs.highlightAuto(text).value;
        else html = esc(text);
      } catch { html = esc(text); }
      return `<div class="code-block"><div class="code-head"><span class="code-lang">${esc(l || 'text')}</span><button class="code-copy" data-act="copy-code">${icon('copy')}<span>Copy</span></button></div><pre><code class="hljs">${html}</code></pre></div>`;
    },
  },
});
DOMPurify.addHook('afterSanitizeAttributes', (n) => { if (n.tagName === 'A') { n.setAttribute('target', '_blank'); n.setAttribute('rel', 'noopener noreferrer'); } });
function md(src, streaming = false) {
  RENDER_STREAMING = streaming;
  try { return DOMPurify.sanitize(marked.parse(src || '')); }
  catch (e) { return `<p>${esc(src)}</p>`; }
  finally { RENDER_STREAMING = false; }
}
/* Gemma 4 thinks by default whenever a system prompt is sent; HomeAI keeps it OFF unless the user picks Think. */
const isNoThinkDefault = (id) => /gemma-?4/i.test(id || '');
const THINK_LS = 'homeai.think';
/* Gemma 4 reasoning drops its section headings, leaving indented sub-bullets (and sometimes bare '*' lines)
   that render as empty / deeply nested bullets. Flatten list indentation and drop marker-only lines. */
function normReasoning(r) {
  return String(r || '').replace(/<\|channel>thought\n?|<channel\|>/g, '').split('\n')
    .filter(l => !/^\s*(?:[*+-]|\d+[.)])\s*$/.test(l))
    .map(l => l.replace(/^[ \t]+((?:[*+-]|\d+[.)])[ \t]+)/, '$1').replace(/^((?:[*+-]|\d+[.)]))[ \t]{2,}/, '$1 '))
    .join('\n').replace(/\n{3,}/g, '\n\n');
}
function splitThink(c) {
  c = c || '';
  const o = c.indexOf('<think>'), cl = c.indexOf('</think>');
  if (o !== -1 && (cl === -1 || cl > o)) {
    if (cl === -1) return { r: c.slice(o + 7), c: c.slice(0, o), open: true };
    return { r: c.slice(o + 7, cl), c: c.slice(0, o) + c.slice(cl + 8), open: false };
  }
  if (cl !== -1 && o === -1) return { r: c.slice(0, cl), c: c.slice(cl + 8), open: false };
  return { r: '', c, open: false };
}

/* ---------------- models ---------------- */
const isVisionName = (id) => /caption|llava|vision|[-_]vl[-_]|gemma-3|minicpm-v|pixtral|mmproj/i.test(id);
const isThinkName = (id) => /qwen3|gemma-?4|think|deepseek-r1|-r1-|reason|gpt-oss|magistral|qwq/i.test(id);
const isCodeName = (id) => /coder|code/i.test(id);
function splitName(id) {
  const base = String(id).split(/[\\/]/).pop().replace(/\.gguf$/i, '');
  const m = /^(.*?)[-_.]((?:UD-)?(?:I?Q\d[\w]*|F16|BF16|F32|MXFP4\w*))$/i.exec(base);
  return m ? { name: m[1], quant: m[2] } : { name: base, quant: '' };
}
const modelById = (id) => S.models.find(m => m.id === id);
const modelStatus = (id) => modelById(id)?.status || 'unknown';
function resolveModel(pat) {
  if (!pat || pat === 'auto' || pat === AUTO) return null;
  if (pat.includes(',')) { for (const part of pat.split(',')) { const id = resolveModel(part.trim()); if (id) return id; } return null; }
  if (modelById(pat)) return pat;
  if (pat.startsWith('@')) { const prof = S.routing.profiles.find(p => p.key === pat.slice(1)); return prof ? R.resolveProfile(prof, S.models) : null; }
  const hits = S.models.filter(m => R.matchPattern(m.id, pat));
  return (hits.find(m => m.status === 'loaded') || hits[0])?.id || null;
}
function presetModelLabel(p) {
  if (!p.model || p.model === 'auto') return p.model === 'auto' ? 'Auto · picks per message' : 'current model';
  const id = resolveModel(p.model);
  if (id) return R.labelForModel(S.routing, id);
  const first = p.model.split(',')[0].trim();
  if (first.startsWith('@')) { const prof = S.routing.profiles.find(x => x.key === first.slice(1)); return (prof ? prof.label : first) + ' (not installed)'; }
  return p.model + ' (not installed)';
}
const modelLabel = (id) => id ? R.labelForModel(S.routing, id) : '';
const isAuto = () => S.chat?.mode === 'auto';
async function refreshModels() {
  try {
    let d;
    try { d = await api(LLAMA + '/models'); }
    catch (e) { if (e.status === 404) d = await api(LLAMA + '/v1/models'); else throw e; }
    const list = (d?.data || []).map(m => {
      const mods = m.architecture?.input_modalities;
      return {
        id: m.id, status: m.status?.value || 'loaded', failed: !!m.status?.failed,
        vision: mods ? mods.includes('image') : isVisionName(m.id), think: isThinkName(m.id), code: isCodeName(m.id),
        ctxTrain: m.context_length || m.meta?.n_ctx_train || null, args: m.status?.args || null,
      };
    });
    S.mode = (d?.data || []).some(m => m.status) ? 'router' : 'single';
    const prev = S.models; S.models = list;
    setServer(true);
    for (const m of list) {
      const old = prev.find(x => x.id === m.id);
      if (old && old.status === 'loading' && m.status === 'loaded' && S.wanted === m.id) { toast(`${splitName(m.id).name} is ready`, 'ok'); S.wanted = null; }
      if (old && old.status === 'loading' && m.status !== 'loaded' && m.failed) { toast(`Failed to load ${splitName(m.id).name}`, 'err'); if (S.wanted === m.id) S.wanted = null; }
      if (m.status === 'loaded' && S.nctx[m.id] === undefined) fetchNctx(m.id);
      if (m.status !== 'loaded' && S.mode === 'router') delete S.nctx[m.id];
    }
    if (S.wanted && modelStatus(S.wanted) === 'loaded') S.wanted = null;
  } catch (e) { setServer(false, e.message); }
  renderModelPicker(); renderLoadPill(); renderThinkToggle(); renderStats();
  schedulePoll();
}
async function fetchNctx(id) {
  S.nctx[id] = null;
  try {
    const q = S.mode === 'router' ? `?model=${encodeURIComponent(id)}&autoload=false` : '';
    const d = await api(LLAMA + '/props' + q);
    S.nctx[id] = d?.default_generation_settings?.n_ctx || d?.n_ctx || null;
    renderStats(); renderModelPicker(); if (S.drawerTab === 'chat' && isDrawerOpen()) renderDrawer();
  } catch { /* not critical */ }
}
async function fetchRouterProps() {
  try { S.router = await api(LLAMA + '/props'); } catch { S.router = null; }
}
function schedulePoll() {
  clearTimeout(S.pollT);
  const busy = S.models.some(m => m.status === 'loading' || m.status === 'downloading') || (S.gen && S.gen.phase === 'loading') || S.wanted;
  const ms = document.hidden ? 15000 : busy ? 800 : (S.serverOk ? 6000 : 3000);
  S.pollT = setTimeout(refreshModels, ms);
}
function setServer(ok, msg) {
  const was = S.serverOk; S.serverOk = ok;
  const pill = $('#serverPill');
  pill.className = 'server-pill ' + (ok ? 'ok' : 'bad');
  const loaded = S.models.filter(m => m.status === 'loaded').length;
  $('.txt', pill).textContent = ok ? (S.mode === 'router' ? `Router · ${loaded}/${S.models.length} loaded` : 'llama-server · online') : 'llama-server offline';
  pill.title = ok ? 'Connected to llama-server' : ('Cannot reach llama-server: ' + (msg || ''));
  if (was === true && !ok) toast('Lost connection to llama-server', 'err');
}
async function loadModel(id, quiet) {
  if (S.mode !== 'router') return;
  S.wanted = id;
  const m = modelById(id); if (m) m.status = 'loading';
  renderModelPicker(); renderLoadPill();
  try { await api(LLAMA + '/models/load', { method: 'POST', body: { model: id } }); }
  catch (e) { if (!/already/i.test(e.message)) { if (!quiet) toast('Load failed: ' + e.message, 'err'); S.wanted = null; } }
  refreshModels();
}
async function unloadModel(id) {
  try { await api(LLAMA + '/models/unload', { method: 'POST', body: { model: id } }); toast(`Unloaded ${splitName(id).name}`, 'info'); }
  catch (e) { toast('Unload failed: ' + e.message, 'err'); }
  refreshModels();
}
function selectAuto() {
  if (!S.chat) return;
  S.chat.mode = 'auto'; touchChat();
  renderModelPicker(); renderThinkToggle(); renderStats(); renderMaxQuality();
}
function selectModel(id, { noLoad } = {}) {
  if (!S.chat) return;
  S.chat.model = id; S.chat.mode = 'manual'; touchChat(); renderMaxQuality();
  const st = modelStatus(id);
  if (!noLoad && S.settings.preloadOnSelect && S.mode === 'router' && st !== 'loaded' && st !== 'loading' && !S.gen) loadModel(id, true);
  renderModelPicker(); renderLoadPill(); renderThinkToggle(); renderStats();
}

/* ---------------- model picker UI ---------------- */
function renderModelPicker() {
  const cur = S.chat?.model; const m = modelById(cur); const auto = isAuto();
  const dot = $('#mpDot'); dot.className = 'status-dot ' + (auto ? 'auto' : m ? (m.failed ? 'failed' : m.status) : '');
  if (auto) {
    $('#mpName').textContent = 'Auto';
    const last = [...S.chat.messages].reverse().find(x => x.route && x.model);
    $('#mpSub').textContent = last ? `→ ${modelLabel(last.model)}` : (S.routing.maxQuality ? 'max quality' : 'best model per message');
  } else if (cur) { const sn = splitName(cur); $('#mpName').textContent = sn.name; $('#mpSub').textContent = sn.quant; }
  else { $('#mpName').textContent = S.models.length ? 'Select a model' : (S.serverOk === false ? 'llama-server offline' : 'No models'); $('#mpSub').textContent = ''; }
  const menu = $('#mpMenu'); if (menu.hidden) return;
  const stLabel = (x) => x.failed ? 'Failed' : ({ loaded: 'Loaded', loading: 'Loading…', unloaded: 'Unloaded', sleeping: 'Sleeping', downloading: 'Downloading…' }[x.status] || x.status);
  const max = S.router?.max_instances;
  const lastAuto = auto ? [...S.chat.messages].reverse().find(x => x.route && x.model) : null;
  menu.innerHTML = `<div class="mp-title"><span>Models${S.mode === 'router' ? ' · router' : ''}</span><button data-act="mp-reload">${icon('refresh')}Rescan</button></div>` +
    `<div class="mp-item auto ${auto ? 'selected' : ''}" data-act="mp-auto"><div class="mp-icon auto">${icon('sparkles')}</div>
      <div class="mp-info"><div class="n">Auto</div><div class="m"><span class="tag">routes each message to the best installed model</span>${S.routing.maxQuality ? '<span class="tag think">max quality</span>' : ''}${lastAuto ? `<span class="tag">last: ${esc(modelLabel(lastAuto.model))}</span>` : ''}</div></div>
      <button class="mp-act" data-act="open-routing" title="Routing rules">Rules</button></div><div class="mp-sep"></div>` +
    (S.models.length ? S.models.map(x => {
      const sn = splitName(x.id);
      const ic = x.vision ? 'eye' : x.code ? 'code' : x.think ? 'brain' : 'cpu';
      const ctx = x.ctxTrain ? `${x.ctxTrain >= 1024 ? Math.round(x.ctxTrain / 1024) + 'K' : x.ctxTrain} ctx` : '';
      const nctx = S.nctx[x.id] ? ` · n_ctx ${fmt(S.nctx[x.id])}` : '';
      let act = '';
      if (S.mode === 'router') {
        if (x.status === 'loaded' || x.status === 'sleeping') act = `<button class="mp-act" data-act="mp-unload" data-id="${esc(x.id)}" title="Unload from VRAM">Eject</button>`;
        else if (x.status === 'unloaded') act = `<button class="mp-act" data-act="mp-load" data-id="${esc(x.id)}" title="Load now">Load</button>`;
      }
      const roles = R.rolesForModel(S.routing, x.id, S.models).filter(r => !(r === 'vision' && x.vision));
      const prof = R.profileForModel(S.routing, x.id);
      return `<div class="mp-item ${x.id === cur && !auto ? 'selected' : ''}" data-act="mp-select" data-id="${esc(x.id)}" title="${esc(x.id + (prof?.note ? '\n' + prof.note : ''))}">
        <div class="mp-icon">${icon(ic)}</div>
        <div class="mp-info"><div class="n" title="${esc(x.id)}">${esc(prof ? prof.label : sn.name)}</div>
          <div class="m">${sn.quant ? `<span class="tag">${esc(prof ? x.id.replace(/^.*?(?=(I?Q\d|Q\d|F16|BF16|-vision|-MTP))/i, '').replace(/^-/, '') || sn.quant : sn.quant)}</span>` : ''}${x.vision ? `<span class="tag vision">${icon('eye')}vision</span>` : ''}${x.think && !roles.length ? `<span class="tag think">${icon('brain')}reasoning</span>` : ''}${roles.map(r => `<span class="tag role ${r}">${esc(r)}</span>`).join('')}${ctx ? `<span class="tag">${ctx}${nctx}</span>` : ''}</div></div>
        <span class="st ${x.failed ? 'failed' : x.status}">${x.status === 'loading' ? '<span class="spinner"></span>' : `<span class="status-dot ${x.failed ? 'failed' : x.status}"></span>`}${stLabel(x)}</span>
        ${act}</div>`;
    }).join('') : `<div class="mp-item" style="cursor:default;color:var(--text-3)">${S.serverOk === false ? 'Cannot reach llama-server. Is it running?' : 'No models found.'}</div>`) +
    `<div class="mp-foot">${S.mode === 'router' ? `Selecting an unloaded model ${S.settings.preloadOnSelect ? 'starts loading it right away' : 'loads it on first message'}${max ? ` · max ${max} loaded at once (older ones are swapped out)` : ''}.` : 'Single-model llama-server.'}</div>`;
}
function toggleModelMenu(force) {
  const menu = $('#mpMenu'); const open = force ?? menu.hidden;
  menu.hidden = !open; $('#modelPicker').classList.toggle('open', open);
  if (open) { renderModelPicker(); refreshModels(); }
}
function renderLoadPill() {
  const pill = $('#loadPill');
  const loading = S.models.find(m => m.status === 'loading');
  const genLoading = S.gen && S.gen.phase === 'loading';
  if (loading || genLoading) {
    const id = loading?.id || S.gen.msg.model;
    $('.txt', pill).textContent = `Loading ${splitName(id).name}…`;
    pill.hidden = false;
  } else pill.hidden = true;
}

/* ---------------- presets ---------------- */
const presetById = (id) => S.presets.find(p => p.id === id);
function renderPresetChips() {
  $('#presetChips').innerHTML = S.presets.slice(0, 6).map(p =>
    `<button class="chip ${S.chat?.presetId === p.id ? 'active' : ''}" data-act="apply-preset" data-id="${esc(p.id)}" title="${esc(p.desc || p.name || '')}"><span class="pdot" style="background:${esc(p.color)}"></span>${esc(p.name)}</button>`).join('') +
    `<button class="chip add-mode" data-act="add-mode" title="Add a mode: HomeAI finds a model on Hugging Face that fits this computer">+ Add mode</button>`;
}
function applyPreset(id, { silent } = {}) {
  const p = presetById(id); if (!p || !S.chat) return;
  S.chat.presetId = p.id;
  S.chat.settings = { system: p.system || '', ...DEFAULT_PARAMS, ...(p.params || {}), thinking: p.thinking || 'auto' };
  S.chat.settings.model_default = mdCopy(p.params);
  const mid = resolveModel(p.model);
  if (p.model === 'auto') { S.chat.mode = 'auto'; renderMaxQuality(); }
  else if (mid) selectModel(mid, { noLoad: !!silent });
  else if (p.model && S.models.length && !silent) toast(`Preset model “${p.model}” not found on the server`, 'err');
  const inp = $('#input');
  if (p.starter && !inp.value.trim()) { inp.value = p.starter; autoGrow(); }
  touchChat();
  renderPresetChips(); renderModelPicker(); renderThinkToggle(); renderStats();
  if (S.chat.messages.length === 0) renderThread();
  if (isDrawerOpen()) renderDrawer();
  if (!silent) toast(`Preset: ${p.name}`, 'info');
}

/* ---------------- chats ---------------- */
function blankChat() {
  return { id: null, title: 'New chat', pinned: false, created: now(), updated: now(), model: S.chat?.model || null, mode: 'manual', presetId: null,
    settings: { system: '', ...DEFAULT_PARAMS, thinking: (() => { try { return localStorage.getItem(THINK_LS) || 'auto'; } catch { return 'auto'; } })(), model_default: MD_ALL() }, messages: [] };
}
function newChat(presetId) {
  if (S.gen) stopGen();
  S.chat = blankChat();
  const pid = presetId || S.settings.defaultPreset;
  $('#input').value = '';
  if (pid && presetById(pid)) applyPreset(pid, { silent: true });
  if (!S.chat.model && S.models.length) S.chat.model = (S.models.find(m => m.status === 'loaded') || S.models[0]).id;
  clearAttachments();
  history.replaceState(null, '', '#');
  renderAll(); autoGrow(); $('#input').focus();
}
async function refreshChats() {
  try { S.chats = (await api('/api/chats')).chats; } catch (e) { toast('Could not load chats: ' + e.message, 'err'); }
  renderChatList();
}
async function openChat(id) {
  if (S.chat?.id === id) return;
  try {
    const c = await api('/api/chats/' + encodeURIComponent(id));
    c.settings = { system: '', ...DEFAULT_PARAMS, thinking: 'auto', ...(c.settings || {}) };
    c.messages = c.messages || [];
    S.chat = c; history.replaceState(null, '', '#/c/' + id);
    clearAttachments(); renderAll(); scrollBottom(true);
    if (window.innerWidth < 900) $('#app').classList.remove('mobile-open');
  } catch (e) { toast('Could not open chat: ' + e.message, 'err'); }
}
function serializeChat(c) {
  return { ...c, messages: c.messages.map(m => { const o = { ...m }; for (const k of Object.keys(o)) if (k.startsWith('_')) delete o[k]; return o; }) };
}
const DELETED_CHATS = new Set();   // ids deleted this session: never re-save them (secure delete)
async function saveChat(c = S.chat) {
  if (!c) return;
  if (c.id && DELETED_CHATS.has(c.id)) return;
  if (!c.id) { c.id = uid(); if (c === S.chat) history.replaceState(null, '', '#/c/' + c.id); }
  c.updated = now();
  try {
    const r = await api('/api/chats/' + c.id, { method: 'PUT', body: serializeChat(c) });
    const i = S.chats.findIndex(x => x.id === c.id);
    if (i >= 0) S.chats[i] = r.meta; else S.chats.unshift(r.meta);
    renderChatList();
  } catch (e) { toast('Save failed: ' + e.message, 'err'); }
}
const saveSoon = debounce(() => saveChat(), 500);
function touchChat() { if (S.chat?.id) saveSoon(); }
async function patchChat(id, patch) {
  try {
    const r = await api('/api/chats/' + id, { method: 'PATCH', body: patch });
    const i = S.chats.findIndex(x => x.id === id); if (i >= 0) S.chats[i] = r.meta;
    if (S.chat?.id === id) Object.assign(S.chat, patch);
    renderChatList();
  } catch (e) { toast(e.message, 'err'); }
}
async function deleteChat(id) {
  const meta = S.chats.find(c => c.id === id);
  if (!await confirmBox('Delete chat?', `“${meta?.title || 'Untitled'}” will be permanently deleted.`, 'Delete')) return;
  DELETED_CHATS.add(id);
  try { await api('/api/chats/' + id, { method: 'DELETE' }); } catch (e) { DELETED_CHATS.delete(id); return toast(e.message, 'err'); }
  S.chats = S.chats.filter(c => c.id !== id);
  if (S.chat?.id === id) newChat(); else renderChatList();
  toast('Chat deleted', 'info');
}
function renderChatList() {
  const q = S.search.trim().toLowerCase();
  const list = S.chats.filter(c => !q || (c.title + ' ' + (c.excerpt || '')).toLowerCase().includes(q));
  const el = $('#chatList');
  if (!list.length) { el.innerHTML = `<div class="empty">${q ? 'No chats match your search.' : 'No chats yet.<br>Start a conversation!'}</div>`; return; }
  const day = 86400, t0 = new Date(); t0.setHours(0, 0, 0, 0); const today = t0.getTime() / 1000;
  const groups = [['Pinned', c => c.pinned], ['Today', c => c.updated >= today], ['Yesterday', c => c.updated >= today - day], ['Previous 7 days', c => c.updated >= today - 7 * day], ['Previous 30 days', c => c.updated >= today - 30 * day], ['Older', () => true]];
  const used = new Set(); let html = '';
  for (const [label, test] of groups) {
    const items = list.filter(c => !used.has(c.id) && test(c)).sort((a, b) => b.updated - a.updated);
    if (!items.length) continue;
    items.forEach(c => used.add(c.id));
    html += `<div class="group-label">${label === 'Pinned' ? `<span class="ico" style="width:12px;height:12px">${icon('pin')}</span>` : ''}${label}</div>`;
    html += items.map(c => `<div class="chat-item ${S.chat?.id === c.id ? 'active' : ''}" data-act="open-chat" data-id="${c.id}">
      <span class="title" title="${esc(c.title)}">${esc(c.title)}</span>
      <span class="acts"><button data-act="pin-chat" data-id="${c.id}" title="${c.pinned ? 'Unpin' : 'Pin'}">${icon('pin')}</button><button data-act="rename-chat" data-id="${c.id}" title="Rename">${icon('edit')}</button><button class="danger" data-act="delete-chat" data-id="${c.id}" title="Delete">${icon('trash')}</button></span></div>`).join('');
  }
  el.innerHTML = html;
}
function startRename(id) {
  const item = $(`.chat-item[data-id="${CSS.escape(id)}"]`); if (!item) return;
  const meta = S.chats.find(c => c.id === id);
  const t = $('.title', item); t.innerHTML = `<input value="${esc(meta.title)}">`;
  const inp = $('input', t); inp.focus(); inp.select();
  let done = false;
  const finish = (ok) => { if (done) return; done = true; const v = inp.value.trim(); if (ok && v && v !== meta.title) patchChat(id, { title: v }); else renderChatList(); };
  inp.addEventListener('keydown', e => { if (e.key === 'Enter') finish(true); if (e.key === 'Escape') { e.stopPropagation(); finish(false); } });
  inp.addEventListener('blur', () => finish(true));
  inp.addEventListener('click', e => e.stopPropagation());
}
function makeTitle(text) {
  let t = (text || '').replace(/```[\s\S]*?```/g, ' ').replace(/[#*_`>\[\]]/g, '').replace(/\s+/g, ' ').trim();
  if (t.length > 52) t = t.slice(0, 50).replace(/\s+\S*$/, '') + '…';
  return t || 'New chat';
}

/* ---------------- thread rendering ---------------- */
function greeting() { const h = new Date().getHours(); return h < 5 ? 'Up late' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'; }
function renderThread() {
  const th = $('#thread');
  if (!S.chat || !S.chat.messages.length) {
    const sugg = ['Write a Python script that renames photos by EXIF date', 'Explain the math behind softmax with LaTeX', 'Plan a week of easy dinners for two', 'Summarise the pros and cons of solar panels'];
    th.innerHTML = `<div class="hero"><div class="hero-orb"></div><h1>${greeting()}, <span>what shall we make?</span></h1>
      <p>Local, private, fast — running on your own computer via llama.cpp.</p>
      <div class="preset-cards">${S.presets.slice(0, 3).map(p => `<button class="pcard" data-act="apply-preset" data-id="${esc(p.id)}"><div class="pi" style="background:${esc(p.color)}">${icon(p.icon || 'sparkles')}</div><h3>${esc(p.name)}</h3>${p.desc ? `<p>${esc(p.desc)}</p>` : ''}<div class="pm">${esc(presetModelLabel(p))}</div></button>`).join('')}</div>
      <div class="suggests">${sugg.map(s => `<button class="suggest" data-act="suggest">${esc(s)}</button>`).join('')}</div></div>`;
    updateJump();
    $$('.pcard', th).forEach(c => c.addEventListener('pointermove', e => { const r = c.getBoundingClientRect(); c.style.setProperty('--mx', (e.clientX - r.left) + 'px'); c.style.setProperty('--my', (e.clientY - r.top) + 'px'); }));
    return;
  }
  th.innerHTML = '';
  updateJump();
  for (const m of S.chat.messages) {
    if (S.gen && S.gen.msg === m) { S.gen.el = msgEl(m, true); th.appendChild(S.gen.el); }
    else th.appendChild(msgEl(m));
  }
}
function msgEl(m, live) {
  const el = document.createElement('div');
  el.className = `msg ${m.role}`; el.dataset.id = m.id;
  if (m.role === 'user') {
    const imgs = (m.images || []).map((src, i) => `<img class="att-img" src="${src}" data-act="zoom" alt="image ${i + 1}">`).join('');
    const files = (m.files || []).map(f => `<span class="file-chip">${icon('file')}<span>${esc(f.name)}</span><small>${fmtSize(f.size)}</small></span>`).join('');
    el.innerHTML = `<div class="body">${imgs || files ? `<div class="att-row">${imgs}${files}</div>` : ''}${m.content ? `<div class="bubble">${esc(m.content)}</div>` : ''}
      <div class="msg-actions"><button data-act="copy-msg" title="Copy">${icon('copy')}</button><button data-act="edit-msg" title="Edit & resend">${icon('edit')}</button><button data-act="oh-msg" title="Send this request to OpenHands">${icon('hand')}</button></div></div>`;
  } else {
    el.innerHTML = `<div class="avatar"></div><div class="body"><div class="who">HomeAI <span class="mname">${esc(splitName(m.model || '').name)}</span><span class="route-slot"></span></div>
      <div class="slot-phase"></div><div class="slot-think"></div><div class="md slot-content"></div><div class="slot-err"></div><div class="slot-web"></div>
      <div class="msg-actions"><button data-act="copy-msg" title="Copy">${icon('copy')}</button><button data-act="regen" title="Regenerate">${icon('refresh')}</button><button data-act="speak-msg" title="Read aloud">${icon('volume')}</button><button data-act="scene-msg" title="Scene to prompt: turn this reply into a ComfyUI prompt">${icon('palette')}</button><button data-act="oh-msg" title="Send this reply + the original request to OpenHands">${icon('hand')}</button><span class="msg-meta"></span></div></div>`;
    updateAssistant(el, m, !!live);
  }
  return el;
}
function thinkLabel(m, live) {
  if (live) return `<span class="shimmer">Thinking…</span>`;
  return m.thinkMs ? `Thought for ${(m.thinkMs / 1000).toFixed(1)}s` : 'Reasoning';
}
function updateAssistant(el, m, live) {
  const g = live ? S.gen : null;
  const sp = splitThink(m.content);
  const reasoning = (m.reasoning || '') + sp.r;
  const content = sp.c.replace(/^\s+/, '');
  const thinkingNow = live && (sp.open || (!!reasoning && !content));
  el.classList.toggle('streaming', !!live);
  // phase (before any token)
  const ph = $('.slot-phase', el);
  $('.mname', el).textContent = m.route ? '' : splitName(m.model || '').name;
  $('.route-slot', el).innerHTML = m.route ? routeChip(m, live) : '';
  if (live && !reasoning && !content) {
    if (g.phase === 'routing') {
      ph.innerHTML = `<div class="phase"><span class="ico" style="color:var(--accent-1)">${icon('sparkles')}</span><div class="grow"><span class="shimmer">Choosing the best model…</span>${g.routeNote ? ` <small>${esc(g.routeNote)}</small>` : ''}</div></div>`;
    } else if (g.phase === 'loading') {
      const others = S.models.filter(x => x.status === 'loaded' && x.id !== m.model).map(x => splitName(x.id).name);
      ph.innerHTML = `<div class="phase"><span class="spinner" style="color:var(--warn)"></span><div class="grow">Loading <b>${esc(m.route ? modelLabel(m.model) : splitName(m.model).name)}</b>${others.length ? ` <small>· swapping out ${esc(others.join(', '))}</small>` : ''}<div class="pbar indet"><i></i></div></div></div>`;
    } else if (g.phase === 'prompt' && g.progress) {
      const p = g.progress; const tot = Math.max(1, p.total - (p.cache || 0)); const pct = Math.max(0, Math.min(100, Math.round(((p.processed - (p.cache || 0)) / tot) * 100)));
      ph.innerHTML = `<div class="phase"><span class="ico" style="color:var(--accent-3)">${icon('gauge')}</span><div class="grow">Processing prompt <small>${fmt(p.processed)} / ${fmt(p.total)} tokens${p.cache ? ` · ${fmt(p.cache)} cached` : ''}</small><div class="pbar"><i style="width:${pct}%"></i></div></div><b>${pct}%</b></div>`;
    } else if (m.web?.state === 'searching') {
      ph.innerHTML = `<div class="phase"><span class="ico" style="color:var(--accent-3)">${icon('globe')}</span><div class="grow"><span class="shimmer">Searching the web…</span> <small>${esc(m.web.query)}</small></div></div>`;
    } else ph.innerHTML = `<div class="typing"><i></i><i></i><i></i></div>`;
  } else ph.innerHTML = '';
  // thinking
  const ts = $('.slot-think', el);
  if (reasoning) {
    if (m._thinkOpen === undefined) m._thinkOpen = !!live;
    if (live && !m._thinkUser) m._thinkOpen = thinkingNow || !S.settings.collapseThinking;
    let box = $('.think', ts);
    if (!box) {
      ts.innerHTML = `<div class="think"><button class="think-head" data-act="toggle-think"><span class="ico">${icon('brain')}</span><span class="lbl"></span><span class="ico chev">${icon('chevron')}</span></button><div class="think-body"><div><div class="think-content md"></div></div></div></div>`;
      box = $('.think', ts);
    }
    box.classList.toggle('open', !!m._thinkOpen);
    $('.lbl', box).innerHTML = thinkLabel(m, thinkingNow);
    const tc = $('.think-content', box);
    const stick = tc.scrollHeight - tc.scrollTop - tc.clientHeight < 30;
    if (tc._src !== reasoning) { tc.innerHTML = md(normReasoning(reasoning), live); tc._src = reasoning; }
    if (thinkingNow && stick) tc.scrollTop = tc.scrollHeight;
  } else ts.innerHTML = '';
  // content
  const cs = $('.slot-content', el);
  if (cs._src !== content || cs._live !== !!live) { cs.innerHTML = md(content, live); cs._src = content; cs._live = !!live; }
  $$('.caret', cs).forEach(x => x.classList.remove('caret')); cs.classList.remove('caret');
  if (live && !thinkingNow && content) {
    const last = cs.lastElementChild;
    if (last && !last.classList.contains('code-block') && !last.querySelector('.katex') && last.tagName !== 'TABLE') (last.tagName === 'UL' || last.tagName === 'OL' ? (last.lastElementChild || last) : last).classList.add('caret');
    else cs.classList.add('caret');
  }
  // error / stop
  const es = $('.slot-err', el);
  es.innerHTML = m.error ? `<div class="err-box">${esc(m.error)}</div>` : (m.stopped && !live ? `<div class="stopped-note">■ Stopped</div>` : '');
  const ws = $('.slot-web', el); const wk = m.web && m.web.state !== 'searching' ? JSON.stringify(m.web) : '';
  if (ws._k !== wk) { ws.innerHTML = wk ? webSources(m.web) : ''; ws._k = wk; }   // only on change: keeps <details> open while streaming
  // meta
  const meta = $('.msg-actions .msg-meta', el);
  if (!live && m.timings) {
    const t = m.timings;
    meta.innerHTML = `<span><b>${fmt(t.predicted_per_second, 1)}</b> t/s</span><span>${fmt(t.predicted_n)} tokens</span><span>${fmt(((t.predicted_ms || 0) + (t.prompt_ms || 0)) / 1000, 1)}s</span>${m.finish === 'length' ? '<span style="color:var(--warn)">hit max tokens</span>' : ''}`;
  } else meta.innerHTML = '';
  $('.msg-actions', el).style.display = live ? 'none' : '';
}

/* ---------------- stats bar ---------------- */
function renderStats() {
  const el = $('#statsbar');
  if (!S.chat) { el.innerHTML = ''; return; }
  const g = S.gen && S.gen.chat === S.chat ? S.gen : null;
  const nctx = S.nctx[S.chat.model];
  let html = '';
  if (g) {
    const el2 = (performance.now() - (g.tFirst || performance.now())) / 1000;
    const tps = g.tFirst && el2 > 0.3 ? g.nTok / el2 : null;
    const ph = g.msg.web?.state === 'searching' && g.phase === 'waiting' ? 'Searching the web' : { routing: 'Routing', loading: 'Loading model', waiting: 'Waiting for first token', prompt: 'Processing prompt', thinking: 'Thinking', answer: 'Generating' }[g.phase] || 'Generating';
    html += `<span class="s live">${icon('zap')}<span>${ph}</span>${tps ? `<b>${fmt(tps, 1)} t/s</b>` : ''}</span>`;
    if (g.nTok) html += `<span class="s">${fmt(g.nTok)} tokens</span>`;
    html += `<span class="s">${icon('clock')}${fmt((performance.now() - g.t0) / 1000, 1)}s</span>`;
    html += `<span class="s right"><kbd>Esc</kbd> stop</span>`;
  } else {
    const last = [...S.chat.messages].reverse().find(m => m.role === 'assistant' && m.timings);
    if (last) {
      const t = last.timings;
      if (t.prompt_n != null) html += `<span class="s" title="Prompt processing (prefill)">${icon('layers')}Prompt <b>${fmt(t.prompt_n)}</b> tok · <b>${fmt(t.prompt_per_second, 1)}</b> t/s${t.cache_n ? ` · ${fmt(t.cache_n)} cached` : ''}</span>`;
      html += `<span class="s" title="Generation (decode)">${icon('zap')}Gen <b>${fmt(t.predicted_n)}</b> tok · <b>${fmt(t.predicted_per_second, 1)}</b> t/s${t.approx ? ' (approx.)' : ''}</span>`;
      const used = (t.prompt_n || 0) + (t.cache_n || 0) + (t.predicted_n || 0);
      if (nctx) {
        const pct = Math.min(100, used / nctx * 100);
        html += `<span class="s" title="Context used (prompt + cached + generated) / n_ctx">Context <span class="ctxbar ${pct > 90 ? 'full' : pct > 70 ? 'warn' : ''}"><i style="width:${pct}%"></i></span><b>${fmt(used)}</b> / ${fmt(nctx)}</span>`;
      } else html += `<span class="s" title="Tokens in context">Context <b>${fmt(used)}</b> tok</span>`;
    } else {
      const m = modelById(S.chat.model);
      if (isAuto()) { const ld = S.models.filter(x => x.status === 'loaded'); html += `<span class="s"><span class="status-dot auto"></span>Auto · ${S.models.length} models${ld.length ? ` · loaded: ${esc(ld.map(x => modelLabel(x.id)).join(', '))}` : ' · none loaded'}${S.routing.maxQuality ? ' · max quality' : ''}</span>`; }
      else if (m) html += `<span class="s"><span class="status-dot ${m.failed ? 'failed' : m.status}"></span>${esc(splitName(m.id).name)} · ${m.status}${nctx ? ` · n_ctx ${fmt(nctx)}` : ''}</span>`;
    }
    html += `<span class="s right"><kbd>Ctrl K</kbd> search · <kbd>${S.settings.sendKey === 'enter' ? 'Enter' : 'Ctrl Enter'}</kbd> send</span>`;
  }
  el.innerHTML = html;
}

/* ---------------- generation ---------------- */
function userContent(m) {
  let text = '';
  for (const f of (m.files || [])) text += `File: ${f.name}\n\`\`\`${f.lang || ''}\n${f.text}\n\`\`\`\n\n`;
  text += m.content || '';
  if (!(m.images || []).length) return text;
  const parts = [];
  for (const url of m.images) parts.push({ type: 'image_url', image_url: { url } });
  if (text) parts.push({ type: 'text', text });
  return parts;
}
/* ov: { model, params:{temperature,top_p,max_tokens,thinking}, vision:boolean } — Auto mode overrides */
function buildPayload(chat, msgs, ov = {}) {
  const s = { ...chat.settings }; const messages = [];
  const rp = ov.params || {};
  if (rp.temperature != null && rp.temperature !== '') s.temperature = rp.temperature;
  if (rp.top_p != null && rp.top_p !== '') s.top_p = rp.top_p;
  if (rp.max_tokens > 0 && !(+s.max_tokens > 0)) s.max_tokens = rp.max_tokens;
  if ((s.thinking || 'auto') === 'auto' && rp.thinking) s.thinking = rp.thinking;   // explicit user toggle wins
  const model = ov.model || chat.model;
  if (isNoThinkDefault(model) && chat.settings.thinking !== 'on') s.thinking = 'off';   // Gemma 4: think only when the user turns Think on
  const vision = ov.vision != null ? ov.vision : (modelById(model)?.vision ?? true);
  const sys = [(s.system || '').trim(), (rp.system || '').trim()].filter(Boolean).join('\n\n');
  if (sys) messages.push({ role: 'system', content: sys });
  const webAt = ov.web ? msgs.map(m => m.role).lastIndexOf('user') : -1;
  for (const m of msgs) {
    if (m.role === 'user') {
      let c = userContent(m);
      if (!vision && Array.isArray(c)) { const t = c.filter(x => x.type === 'text').map(x => x.text).join('\n'); c = `[${c.length - (t ? 1 : 0)} image(s) attached earlier — not visible to this model]` + (t ? '\n' + t : ''); }
      if (webAt >= 0 && m === msgs[webAt]) c = withWebContext(c, ov.web);
      messages.push({ role: 'user', content: c });
    }
    else if (m.role === 'assistant' && m.content && !m.error) messages.push({ role: 'assistant', content: splitThink(m.content).c.trim() });
  }
  const num = (v, d) => (v === '' || v == null || isNaN(+v)) ? d : +v;
  const p = { model, messages, stream: true, stream_options: { include_usage: true }, cache_prompt: true };
  // 'Model default' ON -> omit the field entirely so the llama.cpp preset's tuned sampling applies
  for (const k of SAMPLING_KEYS) if (!mdOn(s, k)) p[k] = num(s[k], DEFAULT_PARAMS[k]);
  if (num(s.max_tokens, 0) > 0) p.max_tokens = num(s.max_tokens, 0);
  if (num(s.seed, -1) >= 0) p.seed = num(s.seed, -1);
  if (S.settings.returnProgress) p.return_progress = true;
  if (s.thinking === 'on') p.chat_template_kwargs = { enable_thinking: true };
  if (s.thinking === 'off') p.chat_template_kwargs = { enable_thinking: false };
  return p;
}
function estTokens(chat) {
  let chars = (chat.settings.system || '').length;
  for (const m of chat.messages) { chars += (m.content || '').length; for (const f of m.files || []) chars += f.text.length; chars += (m.images || []).length * 2400; }
  return Math.round(chars / 3.6);
}
async function send() {
  if (S.gen) return;
  const inp = $('#input'); const text = inp.value.trim();
  const { images, files } = S.att;
  if (!text && !images.length && !files.length) return;
  const chat = S.chat; const auto = chat.mode === 'auto';
  if (auto && !S.models.length) { toast('No models found on llama-server', 'err'); return; }
  if (!auto && !chat.model) { toast('Pick a model first', 'err'); toggleModelMenu(true); return; }
  const m = modelById(chat.model);
  if (!auto && images.length && m && !m.vision) {
    const v = S.models.find(x => x.vision);
    toast(`${splitName(m.id).name} can't see images.`, 'err', v ? { label: `Switch to ${splitName(v.id).name}`, fn: () => selectModel(v.id) } : null);
    return;
  }
  const um = { id: uid(), role: 'user', content: text, created: now() };
  if (images.length) um.images = images.map(i => i.url);
  if (files.length) um.files = files.map(f => ({ name: f.name, size: f.size, lang: f.lang, text: f.text }));
  if (!chat.messages.length && S.settings.autoTitle) chat.title = makeTitle(text || files[0]?.name || 'Image caption');
  if (!chat.messages.length) $('#thread').innerHTML = '';
  chat.messages.push(um);
  $('#thread').appendChild(msgEl(um));
  inp.value = ''; autoGrow(); clearAttachments();
  const n = S.nctx[chat.model]; const est = estTokens(chat);
  if (!auto && n && est > n * 0.9) toast(`This chat is ~${fmt(est)} tokens, close to the context size (${fmt(n)}). Consider a new chat.`, 'info');
  await genFor(um);
}
function genFor(um) {
  const chat = S.chat;
  if (chat.mode === 'auto') return generate({ routeFn: (signal, g) => decideRoute(chat, um, signal, g) });
  return generate();
}

/* ---------------- Auto routing ---------------- */
async function classifyWithLLM(model, text, files, signal) {
  const ctrl = new AbortController();
  const kill = () => ctrl.abort(); signal.addEventListener('abort', kill);
  const timer = setTimeout(kill, S.routing.llmTimeoutMs || 8000);
  const t0 = performance.now();
  try {
    // ?autoload=false: never load (or swap) a model just to classify
    const r = await fetch(LLAMA + '/v1/chat/completions?autoload=false', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(R.classifierRequest(model, text, files)), signal: ctrl.signal });
    if (!r.ok) return { ok: false, model, why: 'HTTP ' + r.status };
    const j = await r.json(); const msg = j.choices?.[0]?.message || {};
    const res = R.parseClassifierResponse((msg.content || '') + ' ' + (msg.content ? '' : (msg.reasoning_content || '')));
    return res ? { ok: true, model, ms: Math.round(performance.now() - t0), ...res } : { ok: false, model, why: 'unparseable' };
  } catch (e) { return { ok: false, model, why: signal.aborted ? 'stopped' : 'timeout' }; }
  finally { clearTimeout(timer); signal.removeEventListener('abort', kill); }
}
function lastRouted(chat, exclude) {
  return [...chat.messages].reverse().find(m => m.role === 'assistant' && m !== exclude && m.route && m.model && !m.error);
}
async function decideRoute(chat, um, signal, g) {
  const cfg = S.routing;
  if (S.mode === 'router' || !S.models.length) await refreshModels();
  const pm = lastRouted(chat, g?.msg);
  const prev = pm ? { category: pm.route.category, model: pm.model } : null;
  const est = estTokens(chat);
  const base = { text: um.content || '', files: um.files || [], images: (um.images || []).length, estTokens: est, models: S.models, cfg, prev,
    historyHasImages: chat.messages.some(m => m !== um && (m.images || []).length) };
  const heur = R.classifyHeuristic(base.text, base.files);
  const hard = base.images > 0 || est > cfg.longSoftTokens;
  const followSame = prev && cfg.followUp && heur.category === prev.category;
  let llm = null; let clsInfo = null;
  const cm = R.pickClassifierModel(cfg, S.models);
  if (!hard && !followSame && R.wantsLLM(cfg, heur, hard)) {
    if (cm) {
      if (g) { g.routeNote = `asking ${modelLabel(cm)}`; if (g.el.isConnected) updateAssistant(g.el, g.msg, true); }
      const res = await classifyWithLLM(cm, base.text, base.files, signal);
      if (signal.aborted) throw Object.assign(new Error('stopped'), { name: 'AbortError' });
      clsInfo = { model: cm, ok: res.ok, ms: res.ms, why: res.why, category: res.category, confidence: res.confidence };
      if (res.ok) llm = { category: res.category, confidence: res.confidence ?? 0.8 };
    } else clsInfo = { ok: false, why: 'no model loaded' };
  }
  const d = R.route({ ...base, llm });
  const mdl = modelById(d.model);
  return { model: d.model, vision: !!mdl?.vision, params: R.samplingFor(cfg, d.category),
    route: { category: d.category, via: d.via, kept: !!d.kept, fallback: !!d.fallback, reason: d.reason, skipped: d.skipped || [], label: d.label || modelLabel(d.model),
      confidence: d.confidence != null ? Math.round(d.confidence * 100) / 100 : null, est, classifier: clsInfo, heuristic: d.heuristic ? { category: d.heuristic.category, confidence: Math.round(d.heuristic.confidence * 100) / 100, signals: d.heuristic.signals } : null,
      alternatives: d.alternatives || [], maxQuality: !!cfg.maxQuality } };
}
const VIA_TEXT = { rule: 'hard rule', heuristic: 'heuristics', llm: 'LLM classifier', 'follow-up': 'kept for follow-up', override: 'manual override', fallback: 'fallback' };
function routeTooltip(m) {
  const r = m.route; const L = [];
  L.push(`${r.override ? 'Manual override' : 'Auto'} → ${r.label} (${m.model})`);
  L.push(`Task: ${R.CATEGORY_LABELS[r.category] || r.category}${r.confidence != null ? ` · confidence ${Math.round(r.confidence * 100)}%` : ''} · decided by ${VIA_TEXT[r.via] || r.via}`);
  if (r.reason) L.push(r.reason);
  if (r.classifier) L.push(r.classifier.ok ? `LLM classifier (${modelLabel(r.classifier.model)}): ${r.classifier.category}${r.classifier.ms ? ` in ${r.classifier.ms} ms` : ''}` : `LLM classifier skipped: ${r.classifier.why}`);
  if (r.heuristic && r.via !== 'heuristic') L.push(`Heuristics said: ${r.heuristic.category} (${Math.round(r.heuristic.confidence * 100)}%)`);
  if (r.heuristic?.signals?.length) L.push(`Signals: ${r.heuristic.signals.slice(0, 5).join(', ')}`);
  if (r.skipped?.length) L.push(`Skipped: ${r.skipped.join('; ')}`);
  if (r.est) L.push(`Input ≈ ${fmt(r.est)} tokens`);
  L.push('Click to re-run with another model');
  return L.join('\n');
}
function routeChip(m, live) {
  const r = m.route; const cat = R.CATEGORY_LABELS[r.category] || r.category;
  const extra = r.override ? 'override' : r.via === 'follow-up' ? 'follow-up' : r.kept ? 'kept loaded' : r.fallback ? 'fallback' : '';
  return `<button class="route-chip ${r.override ? 'override' : ''} ${r.fallback ? 'fallback' : ''}" data-act="route-menu" title="${esc(routeTooltip(m))}"><span class="ico">${icon(r.override ? 'edit' : 'sparkles')}</span><span class="rc-a">${r.override ? 'Manual' : 'Auto'}</span><span class="rc-arrow">→</span><b>${esc(r.label)}</b><span class="rc-sep">·</span><span class="rc-cat cat-${esc(r.category)}">${esc(cat.toLowerCase())}</span>${extra ? `<span class="rc-x">(${esc(extra)})</span>` : ''}<span class="ico chev">${icon('chevron')}</span></button>`;
}
function closeRouteMenu() { $('#routeMenu')?.remove(); }
function openRouteMenu(btn) {
  closeRouteMenu();
  const el = btn.closest('.msg'); const m = S.chat.messages.find(x => x.id === el.dataset.id); if (!m?.route) return;
  const i = S.chat.messages.indexOf(m); const um = [...S.chat.messages.slice(0, i)].reverse().find(x => x.role === 'user');
  const needVision = !!(um?.images || []).length;
  const alts = new Set(m.route.alternatives || []);
  const list = [...S.models].sort((a, b) => (alts.has(b.id) - alts.has(a.id)));
  const menu = document.createElement('div'); menu.id = 'routeMenu'; menu.className = 'pop route-menu';
  menu.innerHTML = `<div class="rm-why"><div class="rm-h">${icon('sparkles')}Why ${esc(m.route.label)}?</div><div class="rm-reason">${esc(m.route.reason || '')}</div>
    <div class="rm-tags"><span class="tag">${esc(R.CATEGORY_LABELS[m.route.category] || m.route.category)}</span><span class="tag">${esc(VIA_TEXT[m.route.via] || m.route.via)}</span>${m.route.kept ? '<span class="tag">kept loaded</span>' : ''}${m.route.skipped?.length ? `<span class="tag warn" title="${esc(m.route.skipped.join('\n'))}">${m.route.skipped.length} skipped</span>` : ''}</div></div>
    <div class="mp-title"><span>Re-run with…</span></div>` +
    list.map(x => { const dis = needVision && !x.vision; return `<button class="rm-item ${x.id === m.model ? 'cur' : ''}" data-act="route-override" data-id="${esc(x.id)}" ${dis ? 'disabled title="This message has images; model has no vision"' : `title="${esc(x.id)}"`}><span class="status-dot ${x.status}"></span><span class="grow">${esc(modelLabel(x.id))}</span>${alts.has(x.id) ? `<small>suggested</small>` : ''}${x.id === m.model ? '<small>current</small>' : ''}</button>`; }).join('') +
    `<button class="rm-item reroute" data-act="route-reroute">${icon('refresh')}<span class="grow">Re-route automatically</span></button>`;
  menu.dataset.msg = m.id; menu.dataset.t = String(performance.now());
  document.body.appendChild(menu);
  const r = btn.getBoundingClientRect(); const mh = menu.offsetHeight; const mw = menu.offsetWidth;
  menu.style.left = Math.max(8, Math.min(window.innerWidth - mw - 8, r.left)) + 'px';
  menu.style.top = (r.bottom + mh + 8 < window.innerHeight ? r.bottom + 6 : Math.max(8, r.top - mh - 6)) + 'px';
}
/* opts: { routeFn(signal,g) -> {model, route, params, vision} } for Auto, or { model, route, params } for overrides */
async function generate(opts = {}) {
  const chat = S.chat;
  voiceStop();   // a new message (or regenerate) interrupts anything being read aloud
  const am = { id: uid(), role: 'assistant', content: '', reasoning: '', model: opts.model || chat.model, created: now() };
  if (opts.route) am.route = opts.route;
  const hist = chat.messages.slice();
  chat.messages.push(am);
  const ctrl = new AbortController();
  const phaseFor = (id) => (S.mode === 'router' && modelStatus(id) !== 'loaded') ? 'loading' : 'waiting';
  const g = S.gen = { chat, msg: am, el: null, ctrl, phase: opts.routeFn ? 'routing' : phaseFor(am.model), t0: performance.now(), tFirst: null, nTok: 0, tThink0: null, tThink1: null, progress: null, voice: !!V.cfg.readAloud, vPos: 0 };
  g.el = msgEl(am, true); $('#thread').appendChild(g.el);
  setBusy(true); stuck = true; scrollBottom(true);
  saveChat(chat);
  renderLoadPill(); renderStats(); schedulePoll();
  const statsTimer = setInterval(() => { if (S.chat === chat) renderStats(); if (S.gen === g && g.phase === 'loading' && g.el.isConnected) updateAssistant(g.el, am, true); }, 250);
  let renderQueued = false, lastRender = 0;
  const queueRender = () => {
    if (renderQueued) return; renderQueued = true;
    const wait = Math.max(0, 45 - (performance.now() - lastRender));
    setTimeout(() => requestAnimationFrame(() => { renderQueued = false; lastRender = performance.now(); if (S.gen === g && g.el.isConnected) { updateAssistant(g.el, am, true); stickScroll(); } if (S.gen === g) voiceFeed(g, false); }), wait);
  };
  try {
    let ov = { model: am.model, params: opts.params, vision: opts.vision };
    const webP = W.cfg.on ? webSearch(am, [...hist].reverse().find(x => x.role === 'user'), ctrl.signal) : null;
    if (webP) { webP.then(() => { if (S.gen === g && g.el.isConnected) updateAssistant(g.el, am, true); }, () => { }); if (g.el.isConnected) updateAssistant(g.el, am, true); }
    if (opts.routeFn) {
      const d = await opts.routeFn(ctrl.signal, g);
      if (ctrl.signal.aborted) throw Object.assign(new Error('stopped'), { name: 'AbortError' });
      if (!d.model) throw new Error('Auto could not find any installed model to use.');
      am.model = d.model; am.route = d.route; ov = { model: d.model, params: d.params, vision: d.vision };
      g.phase = phaseFor(d.model);
      if (g.el.isConnected) updateAssistant(g.el, am, true);
    }
    if (ov.vision == null) ov.vision = modelById(am.model)?.vision ?? true;
    if (webP) ov.web = await webP;
    if (chat.mode === 'auto' || !chat.model) chat.model = am.model;   // follow-ups, stats and n_ctx track the routed model
    renderModelPicker(); renderThinkToggle();
    const payload = buildPayload(chat, hist, ov);
    am.params = { temperature: payload.temperature ?? 'model', top_p: payload.top_p ?? 'model', thinking: payload.chat_template_kwargs ? (payload.chat_template_kwargs.enable_thinking ? 'on' : 'off') : 'auto' };
    const r = await fetch(LLAMA + '/v1/chat/completions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: ctrl.signal });
    if (!r.ok) {
      const txt = await r.text(); let msg = txt;
      try { msg = JSON.parse(txt).error?.message || txt; } catch { }
      throw new Error(`${r.status} · ${msg || r.statusText}`);
    }
    if (g.phase === 'loading') { g.phase = 'waiting'; refreshModels(); }
    const ctype = r.headers.get('content-type') || '';
    if (ctype.includes('application/json')) onChunk(g, await r.json(), true);
    else await readSSE(r, (j) => { onChunk(g, j); queueRender(); });
  } catch (e) {
    if (e.name === 'AbortError') am.stopped = true;
    else am.error = /Failed to fetch|NetworkError|network error/i.test(e.message) ? 'Connection to the HomeAI server was lost.' : e.message;
  } finally {
    clearInterval(statsTimer);
    if (ctrl.signal.aborted) { am.stopped = true; delete am.error; }
    const sp = splitThink(am.content);
    if (sp.r) { am.reasoning = (am.reasoning || '') + sp.r; am.content = sp.c.replace(/^\s+/, ''); }
    if (g.tThink0) am.thinkMs = Math.round((g.tThink1 || performance.now()) - g.tThink0);
    if (!am.timings && g.nTok && g.tFirst) { const ms = performance.now() - g.tFirst; am.timings = { predicted_n: g.nTok, predicted_ms: ms, predicted_per_second: g.nTok / (ms / 1000), approx: true }; }
    S.gen = null; setBusy(false);
    if (g.voice && !am.stopped) voiceFeed(g, true);   // read whatever is left of the reply
    if (g.el.isConnected) updateAssistant(g.el, am, false);
    renderVoiceUI();
    await saveChat(chat);
    renderStats(); renderLoadPill(); refreshModels(); renderModelPicker();
  }
}
async function readSSE(r, cb) {
  const reader = r.body.getReader(); const dec = new TextDecoder(); let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i).replace(/\r$/, ''); buf = buf.slice(i + 1);
      if (line.startsWith('data:')) {
        const data = line.slice(5).trim();
        if (data === '[DONE]') return;
        if (!data) continue;
        let j; try { j = JSON.parse(data); } catch { continue; }
        if (j.error) throw new Error(j.error.message || JSON.stringify(j.error));
        cb(j);
      } else if (line.startsWith('error:')) {
        let msg = line.slice(6).trim(); try { msg = JSON.parse(msg).message || msg; } catch { }
        throw new Error(msg);
      }
    }
  }
}
function onChunk(g, j, whole) {
  const am = g.msg; const t = performance.now();
  if (g.phase === 'loading') g.phase = 'waiting';
  if (j.prompt_progress) { g.progress = j.prompt_progress; if (!g.tFirst) g.phase = 'prompt'; }
  const ch = (j.choices || [])[0];
  if (ch) {
    const d = whole ? (ch.message || {}) : (ch.delta || {});
    const rc = d.reasoning_content ?? d.reasoning;
    if (rc) { am.reasoning += rc; if (!g.tThink0) g.tThink0 = t; g.phase = 'thinking'; g.nTok++; if (!g.tFirst) g.tFirst = t; }
    if (d.content) {
      am.content += d.content; g.nTok++; if (!g.tFirst) g.tFirst = t;
      const sp = splitThink(am.content);
      if (sp.open) { if (!g.tThink0) g.tThink0 = t; g.phase = 'thinking'; }
      else { if (g.tThink0 && !g.tThink1) g.tThink1 = t; g.phase = 'answer'; }
    }
    if (ch.finish_reason) am.finish = ch.finish_reason;
  }
  if (j.timings) am.timings = j.timings;
  if (j.usage) am.usage = j.usage;
}
function stopGen() { if (S.gen) { S.gen.ctrl.abort(); voiceStop(); } }
function setBusy(b) {
  const btn = $('#btnSend');
  btn.classList.toggle('stop', b); btn.innerHTML = icon(b ? 'stop' : 'send'); btn.title = b ? 'Stop (Esc)' : 'Send';
  updateSendState();
}
function updateSendState() {
  const has = $('#input').value.trim() || S.att.images.length || S.att.files.length;
  $('#btnSend').disabled = !S.gen && !has;
}
function regenerate(id, how) {
  if (S.gen) return;
  const i = S.chat.messages.findIndex(m => m.id === id); if (i < 0) return;
  const old = S.chat.messages[i];
  const um = [...S.chat.messages.slice(0, i)].reverse().find(x => x.role === 'user');
  S.chat.messages.splice(i);
  renderThread();
  if (how && how.model) {   // one-click "Re-run with…"
    const cat = old.route?.category;
    const mdl = modelById(how.model);
    return generate({ model: how.model, vision: !!mdl?.vision, params: cat ? R.samplingFor(S.routing, cat) : null,
      route: { category: cat || 'general', via: 'override', override: true, kept: mdl?.status === 'loaded', label: modelLabel(how.model), skipped: [],
        reason: `You re-ran this with ${modelLabel(how.model)}${old.model ? ` instead of ${modelLabel(old.model)}` : ''}.`, alternatives: old.route?.alternatives || [] } });
  }
  if (S.chat.mode === 'auto' && um && (how?.reroute || !old.route)) return genFor(um);
  if (old.route && S.chat.mode === 'auto' && modelById(old.model)) {
    const mdl = modelById(old.model);
    return generate({ model: old.model, vision: !!mdl.vision, params: old.route.override ? null : R.samplingFor(S.routing, old.route.category), route: { ...old.route, kept: mdl.status === 'loaded' } });
  }
  generate();
}
function editMessage(id) {
  if (S.gen) return;
  const m = S.chat.messages.find(x => x.id === id); const el = $(`.msg[data-id="${CSS.escape(id)}"]`);
  let bubble = $('.bubble', el);
  if (!bubble) { bubble = document.createElement('div'); bubble.className = 'bubble'; $('.body', el).insertBefore(bubble, $('.msg-actions', el)); }
  const box = document.createElement('div'); box.className = 'edit-box';
  box.innerHTML = `<textarea></textarea><div class="row"><button class="btn" data-x="cancel">Cancel</button><button class="btn primary" data-x="save">${icon('send')}Save & send</button></div>`;
  const ta = $('textarea', box); ta.value = m.content || '';
  bubble.replaceWith(box); $('.msg-actions', el).style.display = 'none';
  ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length);
  const cancel = () => renderThread();
  const save = () => {
    const v = ta.value.trim(); if (!v && !(m.images || []).length && !(m.files || []).length) return;
    m.content = v; const i = S.chat.messages.indexOf(m); S.chat.messages.splice(i + 1);
    if (i === 0 && S.settings.autoTitle) S.chat.title = makeTitle(v);
    renderThread(); genFor(m);
  };
  $('[data-x=cancel]', box).onclick = cancel; $('[data-x=save]', box).onclick = save;
  ta.addEventListener('keydown', e => { if (e.key === 'Escape') { e.stopPropagation(); cancel(); } if (e.key === 'Enter' && (e.ctrlKey || e.metaKey || (!e.shiftKey && S.settings.sendKey === 'enter'))) { e.preventDefault(); save(); } });
}

/* ---------------- attachments ---------------- */
const fmtSize = (b) => b < 1024 ? b + ' B' : b < 1048576 ? (b / 1024).toFixed(1) + ' KB' : (b / 1048576).toFixed(1) + ' MB';
function clearAttachments() { S.att = { images: [], files: [] }; renderAttachments(); }
function renderAttachments() {
  const el = $('#attachments');
  el.innerHTML = S.att.images.map((im, i) => `<div class="att"><img src="${im.url}" alt="${esc(im.name)}" title="${esc(im.name)}"><button class="x" data-act="rm-img" data-i="${i}">${icon('x')}</button></div>`).join('') +
    S.att.files.map((f, i) => `<div class="att"><span class="file-chip" title="${esc(f.name)}">${icon('file')}<span>${esc(f.name)}</span><small>${fmtSize(f.size)}</small></span><button class="x" data-act="rm-file" data-i="${i}">${icon('x')}</button></div>`).join('');
  updateSendState();
}
function readAs(file, how) { return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = () => rej(r.error); r[how](file); }); }
async function processImage(file) {
  const url = await readAs(file, 'readAsDataURL');
  const img = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = url; });
  const MAX = 2048; const big = Math.max(img.width, img.height);
  if (big <= MAX && file.size < 6e6 && /^data:image\/(png|jpe?g|webp|gif|bmp)/.test(url)) return url;
  const k = Math.min(1, MAX / big); const c = document.createElement('canvas');
  c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
  c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL('image/jpeg', 0.92);
}
async function addFiles(fileList) {
  for (const f of [...fileList]) {
    const ext = (f.name.split('.').pop() || '').toLowerCase();
    try {
      if (f.type.startsWith('image/')) {
        S.att.images.push({ name: f.name || 'pasted-image.png', url: await processImage(f) });
      } else if (f.type.startsWith('text/') || TEXT_EXT.includes(ext) || /json|xml|javascript|x-sh|yaml|toml/.test(f.type) || !f.name.includes('.')) {
        if (f.size > 2 * 1048576) { toast(`${f.name} is too large (max 2 MB)`, 'err'); continue; }
        const text = await readAs(f, 'readAsText');
        if (/\u0000/.test(text.slice(0, 2000))) { toast(`${f.name} looks binary — skipped`, 'err'); continue; }
        S.att.files.push({ name: f.name, size: f.size, text, lang: LANG_BY_EXT[ext] || (hljs.getLanguage(ext) ? ext : '') });
      } else toast(`Unsupported file: ${f.name}`, 'err');
    } catch (e) { toast(`Could not read ${f.name}`, 'err'); }
  }
  renderAttachments();
  if (S.att.images.length && S.chat && !isAuto()) {
    const m = modelById(S.chat.model);
    if (m && !m.vision) {
      const v = S.models.find(x => x.vision);
      if (v) toast('Images need a vision model.', 'info', { label: `Use ${splitName(v.id).name}`, fn: () => { const cap = S.presets.find(p => resolveModel(p.model) === v.id); if (cap) { const keep = $('#input').value; applyPreset(cap.id); if (keep.trim()) { $('#input').value = keep; autoGrow(); } } else selectModel(v.id); } });
    }
  }
  $('#input').focus();
}

/* ---------------- thinking toggle ---------------- */
function renderThinkToggle() {
  const el = $('#thinkToggle'); if (!S.chat) { el.innerHTML = ''; return; }
  const m = modelById(S.chat.model); const v = S.chat.settings.thinking || 'auto';
  if (!(m?.think) && v === 'auto' && !isAuto()) { el.style.display = 'none'; return; }
  el.style.display = '';
  el.innerHTML = [['auto', isAuto() ? 'Think: per task' : 'Auto'], ['on', '\u{1F9E0} Think'], ['off', 'No think']].map(([k, l]) => `<button class="${v === k ? 'on' : ''}" data-act="think-mode" data-v="${k}" title="${k === 'on' ? 'Deep thinking ON for the next messages (slower, shows reasoning)' : k === 'off' ? 'No thinking (fast)' : isNoThinkDefault(m?.id) ? 'Default: Gemma 4 does not think' : 'Model / task default'}">${l}</button>`).join('');
}

function renderMaxQuality() {
  const b = $('#mqChip'); if (!b) return;
  b.hidden = !isAuto();
  b.classList.toggle('on', !!S.routing.maxQuality);
  b.title = S.routing.maxQuality ? 'Max quality ON: hard reasoning goes to the strongest (slow) model' : 'Max quality OFF: click to route hard reasoning problems to the strongest (slow) model';
}
/* ---------------- drawer ---------------- */
const isDrawerOpen = () => $('#drawer').classList.contains('open');
function openDrawer(tab) { if (tab) S.drawerTab = tab; $('#drawer').classList.add('open'); $('#scrim').classList.add('show'); $('#drawer').setAttribute('aria-hidden', 'false'); renderDrawer(); }
function closeDrawer() { $('#drawer').classList.remove('open'); $('#scrim').classList.remove('show'); $('#drawer').setAttribute('aria-hidden', 'true'); S.editingPreset = null; }
function slider(key, label, min, max, step, val, hint, md) {
  const p = ((val - min) / (max - min)) * 100;
  const mdBox = md === undefined ? '' : `<label class="md-toggle" title="Leave this out of the request so the model's own preset (models.ini) applies"><input type="checkbox" data-md="${key}" ${md ? 'checked' : ''}>Model default</label>`;
  return `<div class="field ${md ? 'md-on' : ''}"><label>${label}<span class="lbl-r">${mdBox}<span class="val">${md ? 'model' : val}</span></span></label><input type="range" data-k="${key}" min="${min}" max="${max}" step="${step}" value="${val}" style="--p:${p}%" ${md ? 'disabled' : ''}>${hint ? `<small>${hint}</small>` : ''}</div>`;
}
function paramFields(s, prefix = '') {
  return slider(prefix + 'temperature', 'Temperature', 0, 2, 0.05, s.temperature, 'Lower = focused & deterministic, higher = creative. “Model default” = use the model’s preset.', mdOn(s, 'temperature')) +
    slider(prefix + 'top_p', 'Top P', 0, 1, 0.01, s.top_p, '', mdOn(s, 'top_p')) +
    `<div class="row2">${slider(prefix + 'top_k', 'Top K', 0, 200, 1, s.top_k, '', mdOn(s, 'top_k'))}${slider(prefix + 'min_p', 'Min P', 0, 1, 0.01, s.min_p, '', mdOn(s, 'min_p'))}</div>` +
    slider(prefix + 'repeat_penalty', 'Repeat penalty', 0.8, 1.5, 0.01, s.repeat_penalty, '', mdOn(s, 'repeat_penalty')) +
    `<div class="row2"><div class="field"><label>Max tokens</label><input class="input" type="number" min="0" data-k="${prefix}max_tokens" value="${s.max_tokens}"><small>0 = until done</small></div>
     <div class="field"><label>Seed</label><input class="input" type="number" min="-1" data-k="${prefix}seed" value="${s.seed}"><small>-1 = random</small></div></div>`;
}
function renderDrawer() {
  $$('#drawerTabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === S.drawerTab));
  const body = $('#drawerBody'); const c = S.chat; const s = c.settings;
  if (S.drawerTab === 'chat') {
    const m = modelById(c.model); const n = S.nctx[c.model]; const est = estTokens(c);
    body.innerHTML = `
      <div class="sec"><h4>Preset & model</h4>
        <div class="field"><label>Preset</label><select class="select" data-k="presetId"><option value="">Custom</option>${S.presets.map(p => `<option value="${esc(p.id)}" ${c.presetId === p.id ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}</select></div>
        <div class="field"><label>Model</label><select class="select" data-k="model"><option value="${AUTO}" ${c.mode === 'auto' ? 'selected' : ''}>Auto — best model per message</option>${S.models.map(x => `<option value="${esc(x.id)}" ${x.id === c.model && c.mode !== 'auto' ? 'selected' : ''}>${esc(x.id)} — ${x.status}</option>`).join('')}</select></div></div>
      <div class="sec"><h4>System prompt</h4><textarea class="textarea" data-k="system" placeholder="You are a helpful assistant…">${esc(s.system)}</textarea></div>
      <div class="sec"><h4>Sampling</h4>${c.mode === 'auto' ? `<div class="field"><small>Auto mode: thinking (and temperature / top-p when their “Model default” box is unticked) come from the per-task defaults in <a href="#" data-act="open-routing">Routing</a>; the values below are used for everything else. A ticked “Model default” always leaves that field to the model’s preset. An explicit Think / No think choice always wins.</small></div>` : ''}${paramFields(s)}</div>
      <div class="sec"><h4>Reasoning</h4><div class="seg" data-seg="thinking">${[['auto', 'Model default'], ['on', 'Think'], ['off', 'No think']].map(([k, l]) => `<button class="${(s.thinking || 'auto') === k ? 'on' : ''}" data-v="${k}">${l}</button>`).join('')}</div>
        <div class="field"><small>Sends <code>chat_template_kwargs.enable_thinking</code> for reasoning-capable templates (e.g. Qwen3.x). Reasoning arrives as <code>reasoning_content</code> or inline <code>&lt;think&gt;</code> tags; both are shown in the collapsible Thinking panel and never sent back to the model.</small></div></div>
      <div class="sec"><h4>Context</h4><div class="ctx-card">
        Model trained context: <b>${m?.ctxTrain ? fmt(m.ctxTrain) : 'unknown'}</b><br>
        Loaded context (n_ctx): <b>${n ? fmt(n) : (m?.status === 'loaded' ? '…' : 'load model to see')}</b><br>
        This chat ≈ <b>${fmt(est)}</b> tokens (estimate)${n ? ` · ${Math.round(est / n * 100)}% of n_ctx` : ''}</div>
        <div class="field"><small>n_ctx is fixed when llama-server starts the model (<code>-c</code> on the router command line or <code>c = …</code> in a <code>--models-preset</code> INI). If a chat outgrows it, start a new chat or raise it there.</small></div></div>
      <div class="sec" style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" data-act="save-as-preset">${icon('layers')}Save as preset</button>${c.presetId ? `<button class="btn" data-act="reset-to-preset">${icon('refresh')}Reset to preset</button>` : ''}</div>`;
  } else if (S.drawerTab === 'presets') {
    body.innerHTML = `<div class="sec"><h4>Presets <button class="btn" data-act="new-preset" style="height:28px">${icon('plus')}New</button></h4>
      ${S.presets.map(p => `<div class="preset-row ${S.editingPreset === p.id ? 'editing' : ''}" data-act="edit-preset" data-id="${esc(p.id)}"><div class="pi" style="background:${esc(p.color)}">${icon(p.icon || 'sparkles')}</div><div class="info"><b>${esc(p.name)}</b><small>${esc(presetModelLabel(p))} · temp ${mdOn(p.params, 'temperature') ? 'model' : (p.params?.temperature ?? '–')}${p.thinking && p.thinking !== 'auto' ? ' · think ' + p.thinking : ''}</small></div><button class="btn" data-act="apply-preset" data-id="${esc(p.id)}" style="height:28px">Use</button></div>${S.editingPreset === p.id ? presetEditor(p) : ''}`).join('')}
      <div style="margin-top:14px;display:flex;gap:8px"><button class="btn" data-act="reset-presets">${icon('refresh')}Restore defaults</button></div></div>`;
  } else if (S.drawerTab === 'routing') {
    body.innerHTML = routingPanel();
    updateRouteTest();
  } else {
    const r = S.router;
    body.innerHTML = `<div class="sec"><h4>Appearance</h4><div class="seg" data-seg="theme">${[['dark', 'Dark'], ['light', 'Light']].map(([k, l]) => `<button class="${S.theme === k ? 'on' : ''}" data-v="${k}">${l}</button>`).join('')}</div></div>
      <div class="sec"><h4>Behaviour</h4>
        <div class="field"><label>Send with</label><div class="seg" data-seg="sendKey"><button class="${S.settings.sendKey === 'enter' ? 'on' : ''}" data-v="enter">Enter</button><button class="${S.settings.sendKey === 'ctrl' ? 'on' : ''}" data-v="ctrl">Ctrl + Enter</button></div></div>
        ${[['preloadOnSelect', 'Load model as soon as it is selected'], ['returnProgress', 'Show prompt-processing progress'], ['collapseThinking', 'Auto-collapse thinking when the answer starts'], ['autoTitle', 'Auto-title chats from first message']].map(([k, l]) => `<div class="toggle-row"><span>${l}</span><button class="switch ${S.settings[k] ? 'on' : ''}" data-act="toggle-setting" data-k="${k}"></button></div>`).join('')}
        <div class="field"><label>Default preset for new chats</label><select class="select" data-k="defaultPreset">${S.presets.map(p => `<option value="${esc(p.id)}" ${S.settings.defaultPreset === p.id ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}</select></div></div>
      <div class="sec"><h4>Server</h4><div class="ctx-card">
        llama-server: <b>${esc(S.info?.llama_url || '')}</b> · ${S.serverOk ? '<span style="color:var(--ok)">online</span>' : '<span style="color:var(--err)">offline</span>'}<br>
        Mode: <b>${S.mode}</b>${r?.max_instances != null ? ` · models-max <b>${r.max_instances}</b>` : ''}${r?.models_autoload != null ? ` · autoload <b>${r.models_autoload ? 'on' : 'off'}</b>` : ''}<br>
        Build: <b>${esc(r?.build_info || 'unknown')}</b><br>Data folder: <b style="word-break:break-all">${esc(S.info?.data_dir || '')}</b></div></div>
      <div class="sec"><h4>Keyboard shortcuts</h4><div class="kbd-list">
        <span>Send message</span><span><kbd>${S.settings.sendKey === 'enter' ? 'Enter' : 'Ctrl Enter'}</kbd></span><span>New line</span><span><kbd>Shift Enter</kbd></span>
        <span>Stop generation</span><span><kbd>Esc</kbd></span><span>Search chats</span><span><kbd>Ctrl K</kbd></span><span>New chat</span><span><kbd>Ctrl Shift O</kbd></span>
        <span>Toggle sidebar</span><span><kbd>Ctrl B</kbd></span><span>Chat settings</span><span><kbd>Ctrl ,</kbd></span>
        <span>Stop speaking / cancel recording</span><span><kbd>Esc</kbd></span></div></div>
      <div class="sec"><h4>About</h4><div class="ctx-card">HomeAI ${esc(S.info?.version || '')} · a tiny local UI for llama.cpp. Markdown by marked, sanitising by DOMPurify, highlighting by highlight.js, math by KaTeX — all bundled offline.</div></div>`;
  }
}
/* ---------------- routing rules panel ---------------- */
const saveRouting = () => { S.settings.routing = S.routing; saveSettings(); renderModelPicker(); renderMaxQuality(); };
function routingPanel() {
  const C = S.routing;
  const profOpts = (exclude) => C.profiles.filter(p => !exclude.includes(p.key)).map(p => `<option value="${esc(p.key)}">${esc(p.label)}${R.resolveProfile(p, S.models) ? '' : ' (not installed)'}</option>`).join('');
  const chipList = (cat, list, field) => `<div class="rr-list" data-c="${cat}" data-f="${field}">${list.map((key, i) => {
      const p = C.profiles.find(x => x.key === key); const id = p && R.resolveProfile(p, S.models);
      return `<span class="rr-chip ${id ? '' : 'missing'}" title="${esc(id || 'not installed — skipped')}"><span class="rr-n">${i + 1}</span>${esc(p ? p.label : key)}${id ? (S.models.find(m => m.id === id)?.status === 'loaded' ? '<span class="status-dot loaded"></span>' : '') : '<small>missing</small>'}
        <button data-act="rr-move" data-c="${cat}" data-f="${field}" data-i="${i}" data-d="-1" title="Earlier" ${i === 0 ? 'disabled' : ''}>‹</button><button data-act="rr-move" data-c="${cat}" data-f="${field}" data-i="${i}" data-d="1" title="Later" ${i === list.length - 1 ? 'disabled' : ''}>›</button><button data-act="rr-rm" data-c="${cat}" data-f="${field}" data-i="${i}" title="Remove">×</button></span>`; }).join('')}
      <select class="select rr-add" data-radd="${cat}" data-f="${field}"><option value="">+ add</option>${profOpts(list)}</select></div>`;
  const num = (attr, v, step, min, max, w) => `<input class="input num" type="number" ${attr} value="${v ?? ''}" step="${step}" ${min != null ? `min="${min}"` : ''} ${max != null ? `max="${max}"` : ''} style="width:${w || 74}px">`;
  const cats = R.CATEGORIES;
  return `
  <div class="sec"><h4>Auto mode</h4>
    <div class="field"><label>Task detection</label><div class="seg" data-seg="rt-strategy">${[['heuristic', 'Heuristics'], ['hybrid', 'Hybrid'], ['llm', 'LLM']].map(([k, l]) => `<button class="${C.strategy === k ? 'on' : ''}" data-v="${k}">${l}</button>`).join('')}</div>
      <small>${{ heuristic: 'Instant keyword / code detection only.', hybrid: 'Heuristics first; when unsure, asks the <b>already-loaded</b> model for a one-word classification (never loads or swaps a model).', llm: 'Always asks the already-loaded model (falls back to heuristics when nothing is loaded).' }[C.strategy]}</small></div>
    ${[['sticky', 'Prefer the loaded model when it is acceptable for the task', 'Avoids a model swap (~10-30 s) when the loaded model is anywhere in the task’s list.'], ['followUp', 'Keep the chat’s model for follow-ups', 'Only re-routes when the task clearly changes (e.g. an image is attached).'], ['maxQuality', 'Max quality', 'Hard reasoning problems go to the slow, smartest model first.']].map(([k, l, h]) => `<div class="toggle-row"><span>${l}<small>${h}</small></span><button class="switch ${C[k] ? 'on' : ''}" data-act="rt-toggle" data-k="${k}"></button></div>`).join('')}
    <div class="rr-grid">
      <label>Long-context hard limit<small>tokens → always long-context model</small></label>${num('data-rk="longHardTokens"', C.longHardTokens, 1000, 1000)}
      <label>Long-context soft limit<small>tokens → long-context model unless follow-up</small></label>${num('data-rk="longSoftTokens"', C.longSoftTokens, 1000, 1000)}
      <label>Ask LLM below confidence<small>hybrid mode, 0-1</small></label>${num('data-rk="llmMinConfidence"', C.llmMinConfidence, 0.05, 0, 1)}
      <label>Re-route follow-up at confidence<small>0-1, higher = stickier chats</small></label>${num('data-rk="changeConfidence"', C.changeConfidence, 0.05, 0, 1)}
      <label>Classifier timeout<small>ms</small></label>${num('data-rk="llmTimeoutMs"', C.llmTimeoutMs, 500, 500)}
    </div></div>
  <div class="sec"><h4>Try the router</h4>
    <textarea class="textarea" id="rtTest" data-rtest="1" rows="2" placeholder="Type a prompt to see where Auto would send it…">${esc(S._rtTest || 'Refactor this function to use async/await')}</textarea>
    <div class="rr-test-opts"><label><input type="checkbox" id="rtImg" ${S._rtImg ? 'checked' : ''}> with image</label><label>+ <input class="input num" type="number" id="rtTok" value="${S._rtTok || 0}" step="1000" min="0" style="width:90px"> tokens of files/history</label></div>
    <div class="rr-test" id="rtOut"></div></div>
  <div class="sec"><h4>Routing rules</h4><p class="h-note">First installed model in each list wins; missing ones are skipped. Reorder with ‹ ›.</p>
    ${cats.map(cat => { const r = C.rules[cat] || { models: [] };
      return `<div class="rr-card"><div class="rr-head"><span class="rc-cat cat-${cat}">${esc(R.CATEGORY_LABELS[cat])}</span><small>${esc({ coding: 'code, debugging, scripts, files', reasoning: 'math, logic, proofs, analysis', writing: 'stories, emails, essays, rewrites', general: 'quick questions & chat', long: 'large documents / codebases', vision: 'questions about images, OCR', caption: 'image + empty prompt or caption/tag request', android: 'Android / mobile apps: Kotlin, Compose, Gradle', imageprompt: 'prompts & workflows for image / video generators', research: 'topics with sources (adds a cite-everything system prompt)', music: 'lyrics, BPM/key, arrangement, music-generator prompts' }[cat] || '')}</small></div>
        ${chipList(cat, r.models || [], 'models')}
        ${(cat === 'reasoning' || cat === 'research') ? `<div class="rr-sub">With Max quality, try first:</div>${chipList(cat, r.maxQualityModels || [], 'maxQualityModels')}` : ''}
        <div class="rr-params"><label>temp ${num(`data-rc="${cat}" data-rf="temperature"`, r.temperature, 0.05, 0, 2, 64)}</label><label>top-p ${num(`data-rc="${cat}" data-rf="top_p"`, r.top_p, 0.05, 0, 1, 64)}</label><label>max tok ${num(`data-rc="${cat}" data-rf="max_tokens"`, r.max_tokens || 0, 64, 0, null, 70)}</label>
          <label>think <select class="select mini" data-rc="${cat}" data-rf="thinking">${[['auto', 'default'], ['on', 'on'], ['off', 'off']].map(([k, l]) => `<option value="${k}" ${(r.thinking || 'auto') === k ? 'selected' : ''}>${l}</option>`).join('')}</select></label></div></div>`; }).join('')}
  </div>
  <div class="sec"><h4>Model profiles</h4><p class="h-note">Matched by exact router id first, else by pattern: all words must appear · <code>-word</code> excludes · <code>|</code> = or.</p><datalist id="pfIds">${S.models.map(m => `<option value="${esc(m.id)}">`).join('')}</datalist>
    ${C.profiles.map((p, i) => { const id = R.resolveProfile(p, S.models);
      return `<div class="pf-row ${id ? 'ok' : 'missing'}"><div class="pf-top"><input class="input" data-pf="label" data-i="${i}" value="${esc(p.label)}"><label>ctx ${num(`data-pf="ctx" data-i="${i}"`, p.ctx || 0, 1024, 0, null, 86)}</label></div>
        <div class="pf-kv"><span>id</span><input class="input mono" data-pf="id" data-i="${i}" value="${esc(p.id || '')}" placeholder="exact router id" spellcheck="false" list="pfIds"></div>
        <div class="pf-kv"><span>pattern</span><input class="input mono" data-pf="pattern" data-i="${i}" value="${esc(p.pattern)}" placeholder="fallback match" spellcheck="false"></div>
        ${p.note ? `<small class="pf-note">${esc(p.note)}</small>` : ''}
        <div class="pf-match">${id ? `${icon('check')}<code>${esc(id)}</code>${p.id && id.toLowerCase() !== String(p.id).toLowerCase() ? '<small>(via pattern)</small>' : ''}` : `${icon('alert')}not installed — rules skip it`}</div></div>`; }).join('')}
    <small style="display:block;margin-top:6px;color:var(--text-3)">ctx is what you load the model with (<code>-c</code>); requests that would not fit are routed elsewhere. 0 = unknown.</small>
  </div>
  <div class="sec" style="display:flex;gap:8px"><button class="btn" data-act="rt-reset">${icon('refresh')}Restore routing defaults</button></div>`;
}
function updateRouteTest() {
  const out = $('#rtOut'); if (!out) return;
  const text = $('#rtTest').value; const img = $('#rtImg').checked; const extra = +$('#rtTok').value || 0;
  S._rtTest = text; S._rtImg = img; S._rtTok = extra;
  const d = R.route({ text, files: [], images: img ? 1 : 0, estTokens: Math.round(text.length / 3.6) + extra, models: S.models, cfg: S.routing });
  const sp = R.samplingFor(S.routing, d.category);
  out.innerHTML = d.model ? `<div class="rr-res"><span class="rc-cat cat-${d.category}">${esc(R.CATEGORY_LABELS[d.category])}</span>→ <b>${esc(d.label)}</b>${d.kept ? ' <small>(kept loaded)</small>' : ''}${d.fallback ? ' <small>(fallback)</small>' : ''}</div>
    <small>${esc(d.reason)}${d.confidence != null ? ` · confidence ${Math.round(d.confidence * 100)}%` : ''} · temp ${sp.temperature} · think ${sp.thinking}${d.skipped.length ? `<br>skipped: ${esc(d.skipped.join('; '))}` : ''}</small>` : '<small>No models installed.</small>';
}
function onRoutingInput(e) {
  const t = e.target; const C = S.routing;
  if (t.closest('.rr-test-opts') || t.dataset.rtest) { updateRouteTest(); return true; }
  if (t.dataset.rk) { if (t.value !== '') { C[t.dataset.rk] = +t.value; saveRouting(); updateRouteTest(); } return true; }
  if (t.dataset.rc && t.dataset.rf) {
    const r = C.rules[t.dataset.rc]; r[t.dataset.rf] = t.dataset.rf === 'thinking' ? t.value : (t.value === '' ? (t.dataset.rf === 'max_tokens' ? 0 : r[t.dataset.rf]) : +t.value);
    saveRouting(); updateRouteTest(); return true;
  }
  if (t.dataset.pf) {
    const p = C.profiles[+t.dataset.i]; p[t.dataset.pf] = t.dataset.pf === 'ctx' ? (+t.value || 0) : t.value; saveRouting();
    if (t.dataset.pf === 'pattern' || t.dataset.pf === 'id') { const row = t.closest('.pf-row'); const id = R.resolveProfile(p, S.models); row.classList.toggle('ok', !!id); row.classList.toggle('missing', !id); $('.pf-match', row).innerHTML = id ? `${icon('check')}<code>${esc(id)}</code>` : `${icon('alert')}not installed — rules skip it`; }
    updateRouteTest();
    if (e.type === 'change') { const y = $('#drawerBody').scrollTop; renderDrawer(); $('#drawerBody').scrollTop = y; }
    return true;
  }
  if (t.dataset.radd && e.type === 'change' && t.value) {
    const r = C.rules[t.dataset.radd]; const f = t.dataset.f; r[f] = [...(r[f] || []), t.value]; saveRouting();
    const y = $('#drawerBody').scrollTop; renderDrawer(); $('#drawerBody').scrollTop = y; return true;
  }
  return !!(t.dataset.radd);
}
function presetEditor(p) {
  const s = { ...DEFAULT_PARAMS, ...(p.params || {}) };
  return `<div class="preset-edit" data-preset="${esc(p.id)}">
    <div class="row2"><div class="field"><label>Name</label><input class="input" data-pk="name" value="${esc(p.name)}"></div>
    <div class="field"><label>Icon</label><select class="select" data-pk="icon">${PRESET_ICONS.map(i => `<option ${p.icon === i ? 'selected' : ''}>${i}</option>`).join('')}</select></div></div>
    <div class="field"><label>Colour</label><div class="color-pick">${PRESET_COLORS.map(c => `<button data-pcolor="${c}" class="${p.color === c ? 'on' : ''}" style="background:${c}"></button>`).join('')}</div></div>
    <div class="field"><label>Model <small style="display:inline;margin:0">auto, @profile, exact id or name pattern</small></label><input class="input" data-pk="model" list="modelIds" value="${esc(p.model || '')}"><datalist id="modelIds"><option value="auto">${S.routing.profiles.map(x => `<option value="@${esc(x.key)}">${esc(x.label)}</option>`).join('')}${S.models.map(m => `<option value="${esc(m.id)}">`).join('')}</datalist><small>→ ${esc(presetModelLabel(p))}</small></div>
    <div class="field"><label>Description</label><input class="input" data-pk="desc" value="${esc(p.desc || '')}"></div>
    <div class="field"><label>System prompt</label><textarea class="textarea" data-pk="system">${esc(p.system || '')}</textarea></div>
    <div class="field"><label>Starter prompt <small style="display:inline;margin:0">pre-fills the composer</small></label><input class="input" data-pk="starter" value="${esc(p.starter || '')}"></div>
    <div class="field"><label>Reasoning</label><select class="select" data-pk="thinking">${[['auto', 'Model default'], ['on', 'Think'], ['off', 'No think']].map(([k, l]) => `<option value="${k}" ${(p.thinking || 'auto') === k ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
    ${paramFields(s, 'p.')}
    <div style="display:flex;gap:8px;justify-content:space-between"><button class="btn danger" data-act="delete-preset" data-id="${esc(p.id)}">${icon('trash')}Delete</button><button class="btn primary" data-act="apply-preset" data-id="${esc(p.id)}">Apply to chat</button></div></div>`;
}
const savePresets = debounce(() => store.put('presets', S.presets).catch(e => toast('Saving presets failed: ' + e.message, 'err')), 400);
const saveSettings = debounce(() => store.put('settings', S.settings).catch(() => { }), 300);
function onDrawerInput(e) {
  if (S.drawerTab === 'routing' && onRoutingInput(e)) return;
  const t = e.target; const k = t.dataset.k; const pk = t.dataset.pk;
  if (t.dataset.md) {   // 'Model default' checkbox (fires input + change; idempotent)
    const mk = t.dataset.md; const isP = mk.startsWith('p.'); const key = isP ? mk.slice(2) : mk; const on = t.checked;
    const f = t.closest('.field'); const rg = f.querySelector('input[type=range]'); const v = f.querySelector('.val');
    f.classList.toggle('md-on', on); if (rg) rg.disabled = on; if (v) v.textContent = on ? 'model' : rg.value;
    if (isP) {
      const p = presetById(t.closest('.preset-edit')?.dataset.preset); if (!p) return;
      p.params = { ...DEFAULT_PARAMS, ...(p.params || {}) }; p.params.model_default = { ...mdCopy(p.params), [key]: on };
      savePresets(); if (e.type === 'change') { const y = $('#drawerBody').scrollTop; renderDrawer(); $('#drawerBody').scrollTop = y; }
    } else { S.chat.settings.model_default = { ...mdCopy(S.chat.settings), [key]: on }; touchChat(); }
    return;
  }
  if (t.type === 'range') { const min = +t.min, max = +t.max; t.style.setProperty('--p', ((t.value - min) / (max - min) * 100) + '%'); const v = t.closest('.field').querySelector('.val'); if (v) v.textContent = t.value; }
  const editor = t.closest('.preset-edit');
  if (editor) {
    const p = presetById(editor.dataset.preset); if (!p) return;
    if (pk) p[pk] = t.value;
    if (k && k.startsWith('p.')) { p.params = { ...DEFAULT_PARAMS, ...(p.params || {}) }; p.params[k.slice(2)] = t.value === '' ? '' : +t.value; }
    savePresets(); renderPresetChips();
    if (e.type === 'change' && (pk === 'name' || pk === 'model' || pk === 'icon')) renderDrawer();
    return;
  }
  if (!k) return;
  if (e.type === 'input' && t.tagName === 'SELECT') return;
  if (k === 'presetId') { if (t.value) applyPreset(t.value); else { S.chat.presetId = null; renderPresetChips(); touchChat(); } return; }
  if (k === 'model') { if (t.value === AUTO) selectAuto(); else selectModel(t.value); renderDrawer(); return; }
  if (k === 'defaultPreset') { S.settings.defaultPreset = t.value; saveSettings(); return; }
  if (k === 'system') S.chat.settings.system = t.value;
  else S.chat.settings[k] = t.value === '' ? '' : +t.value;
  touchChat();
}

/* ---------------- export ---------------- */
function exportMarkdown() {
  const c = S.chat; if (!c || !c.messages.length) return toast('Nothing to export yet', 'info');
  let out = `# ${c.title}\n\n_Exported from HomeAI · ${new Date().toLocaleString()} · model: \`${c.model || '?'}\`_\n\n`;
  if ((c.settings.system || '').trim()) out += `> **System prompt:** ${c.settings.system.replace(/\n/g, '\n> ')}\n\n`;
  out += '---\n\n';
  for (const m of c.messages) {
    if (m.role === 'user') {
      out += `### 🧑 You\n\n`;
      for (const f of m.files || []) out += `<details><summary>📎 ${f.name}</summary>\n\n\`\`\`${f.lang || ''}\n${f.text}\n\`\`\`\n\n</details>\n\n`;
      (m.images || []).forEach((_, i) => out += `_[image ${i + 1} attached]_\n\n`);
      out += `${m.content || ''}\n\n`;
    } else {
      out += `### 🤖 Assistant · \`${m.model || ''}\`\n\n`;
      if (m.reasoning) out += `<details><summary>💭 Thinking${m.thinkMs ? ` (${(m.thinkMs / 1000).toFixed(1)}s)` : ''}</summary>\n\n${normReasoning(m.reasoning).trim()}\n\n</details>\n\n`;
      out += `${m.content || ''}\n\n`;
      if (m.web?.sources?.length) out += `**Sources**\n\n${m.web.sources.map((x, i) => `${i + 1}. [${x.title}](${x.url})`).join('\n')}\n\n`;
      if (m.timings) out += `<sub>${fmt(m.timings.predicted_n)} tokens · ${fmt(m.timings.predicted_per_second, 1)} t/s</sub>\n\n`;
      if (m.error) out += `> ⚠️ Error: ${m.error}\n\n`;
    }
  }
  const blob = new Blob([out], { type: 'text/markdown;charset=utf-8' });
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: (c.title.replace(/[\\/:*?"<>|]+/g, '').slice(0, 60) || 'chat') + '.md' });
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  toast('Exported as Markdown', 'ok');
  return out;
}

/* ---------------- toasts / modal ---------------- */
function toast(msg, type = 'info', action) {
  const el = document.createElement('div'); el.className = `toast ${type}`;
  el.innerHTML = `<span class="ico">${icon(type === 'err' ? 'alert' : type === 'ok' ? 'check' : 'info')}</span><span>${esc(msg)}</span>${action ? `<button>${esc(action.label)}</button>` : ''}`;
  const dismiss = () => { el.classList.add('out'); setTimeout(() => el.remove(), 260); };
  if (action) $('button', el).onclick = () => { action.fn(); dismiss(); };
  $('#toasts').appendChild(el);
  setTimeout(dismiss, action ? 7000 : 3200);
}
function confirmBox(title, text, okLabel = 'OK') {
  return new Promise(res => {
    const root = $('#modalRoot');
    root.innerHTML = `<div class="modal-back"><div class="confirm"><h3>${esc(title)}</h3><p>${esc(text)}</p><div class="row"><button class="btn" data-x="no">Cancel</button><button class="btn ${okLabel === 'Delete' ? 'danger' : 'primary'}" data-x="yes">${esc(okLabel)}</button></div></div></div>`;
    const close = (v) => { root.innerHTML = ''; document.removeEventListener('keydown', key, true); res(v); };
    const key = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(false); } if (e.key === 'Enter') { e.preventDefault(); close(true); } };
    document.addEventListener('keydown', key, true);
    root.querySelector('[data-x=yes]').onclick = () => close(true);
    root.querySelector('[data-x=no]').onclick = () => close(false);
    root.querySelector('.modal-back').onclick = (e) => { if (e.target.classList.contains('modal-back')) close(false); };
    root.querySelector('[data-x=yes]').focus();
  });
}
/* ---------------- Send to OpenHands (Agent Canvas) ---------------- */
const filesAsText = (files) => (files || []).filter(f => f.text).map(f => `\n\nFile: ${f.name}\n\`\`\`${f.lang || ''}\n${f.text}\n\`\`\``).join('');
function ohFromComposer() {
  const text = $('#input').value.trim();
  const task = (text + filesAsText(S.att.files)).trim();
  if (!task) { toast('Type a task in the message box first (or use the hand button on a message)', 'info'); $('#input').focus(); return; }
  openOHModal(task, 'Current prompt');
}
function ohFromMessage(msgId) {
  const msgs = S.chat?.messages || []; const i = msgs.findIndex(x => x.id === msgId); const m = msgs[i];
  if (!m) return;
  if (m.role === 'user') return openOHModal(((m.content || '') + filesAsText(m.files)).trim(), 'Your message');
  let u = null; for (let j = i - 1; j >= 0; j--) if (msgs[j].role === 'user') { u = msgs[j]; break; }
  const req = u ? ((u.content || '') + filesAsText(u.files)).trim() : '';
  const task = (req ? `Original request:\n${req}\n\n` : '') + `Proposed answer / plan from HomeAI (${splitName(m.model || '').name || 'assistant'}):\n${m.content || ''}\n\nPlease implement this in the workspace.`;
  openOHModal(task, 'Reply + original request');
}
async function openOHModal(task, source) {
  const root = $('#modalRoot');
  root.innerHTML = `<div class="modal-back"><div class="confirm oh-modal">
    <h3><span class="oh-ico">${icon('hand')}</span>Send to OpenHands</h3>
    <div class="oh-status" id="ohStatus"><span class="status-dot loading"></span><span>Checking OpenHands…</span></div>
    <label class="oh-lbl">Task <small>${esc(source)} · editable</small></label>
    <textarea class="textarea oh-task" id="ohTask" spellcheck="true"></textarea>
    <div class="oh-note">${icon('info')}<span>OpenHands uses the same llama.cpp router (one model slot). While it works, HomeAI chats will wait or swap the model, which also slows OpenHands down. Best to let it finish first.</span></div>
    <div class="oh-result" id="ohResult" hidden></div>
    <div class="row"><button class="btn" data-x="no">Close</button><button class="btn primary" data-x="yes" id="ohSend">${icon('hand')}Send</button></div></div></div>`;
  const ta = $('#ohTask'); ta.value = task;
  let closed = false, pollT = null;
  const close = () => { closed = true; clearTimeout(pollT); root.innerHTML = ''; document.removeEventListener('keydown', key, true); };
  const key = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); doSend(); } };
  document.addEventListener('keydown', key, true);
  root.querySelector('[data-x=no]').onclick = close;
  root.querySelector('.modal-back').onclick = (e) => { if (e.target.classList.contains('modal-back')) close(); };
  const st = $('#ohStatus'); const sendBtn = $('#ohSend');
  const setStatus = (s) => {
    if (closed) return;
    if (s.running) { st.className = 'oh-status ok'; st.innerHTML = `<span class="status-dot loaded"></span><span>OpenHands is running</span><a href="${esc(s.ui_url)}" target="_blank" rel="noopener">Open UI ${icon('external')}</a>`; sendBtn.disabled = false; }
    else if (s.starting) { st.className = 'oh-status warn'; st.innerHTML = `<span class="spinner"></span><span>Starting OpenHands (Docker + container)… this can take a minute.</span>`; sendBtn.disabled = true; }
    else { st.className = 'oh-status err'; st.innerHTML = `<span class="status-dot failed"></span><span>OpenHands is not running.</span>${s.can_start ? `<button class="btn" id="ohStart">${icon('power')}Start OpenHands</button>` : '<small>Start it with the Start OpenHands shortcut (optional extra)</small>'}`; sendBtn.disabled = true;
      const b = $('#ohStart'); if (b) b.onclick = async () => { b.disabled = true; try { await api('/api/openhands/start', { method: 'POST' }); setStatus({ starting: true }); poll(); } catch (e) { toast('Could not start OpenHands: ' + e.message, 'err'); b.disabled = false; } }; }
  };
  const poll = async () => { if (closed) return; let s; try { s = await api('/api/openhands/status'); } catch (e) { s = { running: false }; } setStatus(s); if (!s.running && s.starting) pollT = setTimeout(poll, 3000); };
  const doSend = async () => {
    if (sendBtn.disabled) return;
    const t = ta.value.trim(); if (!t) { ta.focus(); return; }
    sendBtn.disabled = true; sendBtn.innerHTML = `<span class="spinner"></span>Sending…`;
    try {
      const r = await api('/api/openhands/send', { method: 'POST', body: { task: t } });
      const res = $('#ohResult'); res.hidden = false;
      res.innerHTML = `<div class="ok-line">${icon('check')}<b>Conversation started</b></div>
        <a class="btn primary oh-open" href="${esc(r.url)}" target="_blank" rel="noopener">${icon('external')}Open conversation in OpenHands</a>
        <div class="oh-folder">${icon('folder')}<span>Files: <code>${esc(r.files_dir)}</code></span><button class="btn" data-act="oh-copy">${icon('copy')}Copy path</button></div>
        <small>${r.model ? 'Model: ' + esc(splitName(r.model.replace(/^openai\//, '')).name) + ' · ' : ''}id ${esc(r.conversation_id)}</small>`;
      res.querySelector('[data-act=oh-copy]').onclick = (e) => { e.stopPropagation(); copyText(r.files_dir); toast('Folder path copied', 'ok'); };
      sendBtn.innerHTML = `${icon('check')}Sent`; ta.readOnly = true;
      toast('Sent to OpenHands', 'ok', { label: 'Open', fn: () => window.open(r.url, '_blank', 'noopener') });
    } catch (e) {
      sendBtn.innerHTML = `${icon('hand')}Send`;
      if (e.status === 503) { await poll(); toast('OpenHands is not running — start it first', 'err'); }
      else { sendBtn.disabled = false; toast(e.message, 'err'); }
    }
  };
  sendBtn.onclick = doSend;
  sendBtn.disabled = true; ta.focus(); ta.setSelectionRange(0, 0); ta.scrollTop = 0;
  poll();
}
function zoomImage(src) {
  const root = $('#modalRoot'); root.innerHTML = `<div class="modal-back"><img src="${src}"></div>`;
  root.firstChild.onclick = () => root.innerHTML = '';
}

/* ---------------- Scene to prompt (story scene -> text-to-image prompt) ----------------
   A whole reply (🎨 under it), a highlighted part of a reply (floating "🎨 Make prompt") or pasted text (🎨 in the
   composer) goes to a local model (the Image prompts mode if installed, else Writing, else General) with its own
   system prompt. The result opens in a modal with Positive / Negative boxes; the chat history is never touched.
   The model output is then checked here: BREAK layout, adult tags, quality / score tags in the right place, and a
   block-list (minor-coded tags, mirror / reflection). */
/* SCENE-CORE-START */
const SCENE_KEY = 'homeai.scene';
const SCENE_DEFAULTS = { model: '@imageprompt, @writing, @general', family: 'illustrious' };
const SCENE_MODELS = [['@imageprompt, @writing, @general', 'Image prompts mode · default'], ['@writing, @general', 'Writing mode'], ['@general', 'General mode']];
const SCENE_MAX_CHARS = 16000;   // keep room for the system prompt + answer in an 8k-32k context
const SC_QUALITY = ['masterpiece', 'best quality', 'amazing quality', 'very awa', 'absurdres', 'newest'];
const SC_SCORE = ['score_9', 'score_8_up', 'score_7_up', 'score_6_up', 'score_5_up', 'score_4_up'];
const SC_SKIN = ['natural skin texture'];
const SC_NEG_BASE = { illustrious: ['bad quality', 'worst quality', 'worst detail', 'sketch', 'censor'], pony: ['score_4', 'score_5', 'score_6'] };
const SC_NEG_TASTE = ['extra person', 'child', 'loli'];
const SC_DROP_QUALITY = /^(masterpiece|best quality|amazing quality|great quality|good quality|high quality|highest quality|very awa|very aware|very aesthetic|absurdres|highres|newest|score_\d+(_up)?|source_\w+|rating_\w+)$/;
// never in a positive: anything that could read as a minor (the hard rule), plus tags that tend to break images
const SC_MINOR = /\b(lolis?|lolicon|shotas?|shotacon|child|children|childlike|child-like|kids?|toddlers?|infants?|pre-?teens?|teens?|teenaged?|teenagers?|underage|minors?|young|younger|youthful|aged down|little (girl|boy)s?|elementary|middle school|grade school|kindergarten|schoolgirls?|schoolboys?|school uniform|serafuku|randoseru|baby ?face)\b/i;
const SC_AVOID = /\b(mirrors?|reflections?|reflective)\b/i;
const SC_SEX = /\b(sex|vaginal|anal|fellatio|irrumatio|cunnilingus|handjob|footjob|paizuri|titjob|masturbation|fingering|penis|pussy|cum|ejaculation|orgasm|penetration|missionary|cowgirl position|doggystyle|69|threesome|group sex|sex toy|dildo|vibrator|erection|testicles|clitoris)\b/i;
const SC_NUDE = /\b(nude|naked|topless|bottomless|nipples|areolae|breasts out|no panties|no bra|exposed)\b/i;
const SC_COUNT = /^(\d+)(girl|boy|other)s?$/;
const scKey = (t) => t.toLowerCase().replace(/^\(+/, '').replace(/(:\s*[\d.]+)?\)+$/, '').trim();
const scIsPerson = (sec) => { const f = scKey(sec[0] || ''); return /^(adult )?(woman|man|girl|boy|female|male|person|futanari|lady|guy|husband|wife)\b/.test(f) || /\b(on (the )?(left|right|top)|in (front|back|the middle|the cent(er|re))|behind|underneath)\b/.test(f); };
function scTags(s) {
  return String(s || '').split(/,|\n/).map(t => t.trim().replace(/^[-*•]+\s*/, '').replace(/^\d+[.)]\s+/, '').replace(/[.;]+$/, '').replace(/^["'`]+|["'`]+$/g, '').trim())
    .filter(Boolean).map(t => {
      let x = t.toLowerCase();
      if (!/^(score|source|rating)_/.test(x) && !/[\^>]_[\^<]/.test(x)) x = x.replace(/_/g, ' ');
      return x.replace(/\s+/g, ' ');
    });
}
function sceneSystem(family) {
  const pony = family === 'pony';
  return `You are Scene-to-Prompt, an expert ComfyUI prompt writer and Danbooru tagger for private, adults-only image generation on the user's own computer. You read a scene from an adult erotic story and turn it into ONE ready-to-paste text-to-image prompt for ${pony ? 'a Pony Diffusion based SDXL model' : 'an Illustrious-based SDXL model'} in a ComfyUI workflow whose prompt node understands BREAK. Explicit sexual content between consenting adults is allowed and expected: tag nudity, genitals and sex acts plainly with real Danbooru tags. You never refuse, warn, moralise, add disclaimers or comment. You output only the format at the end.

HARD RULE (never broken): every character is an adult aged 18 or over. Always put \`adult\` in the shared section and in each person's section, and give everyone adult body proportions (e.g. tall, curvy, toned, wide hips, adult woman / adult man build). Never write tags that sexualise minors or look young: no loli, shota, child, kid, teen, young, petite child, aged down, school uniform, serafuku, schoolgirl, randoseru. If the scene is vague about age or anything hints at youth, make every character a clearly adult woman or man and carry on without refusing or lecturing.

READ THE SCENE: pick its single most vivid moment. Use the characters' described appearance (hair colour, length and style, eye colour, skin tone, build, breast and hip size), clothing or its absence (with colours and state: open shirt, lifted skirt, panties aside, completely nude), the exact pose and sex act, expressions, setting, time of day, lighting, mood, and a fitting camera angle (pov, from above, from below, from side, from behind, close-up). Invent plausible, consistent details only where the scene says nothing.

TAG RULES: lowercase Danbooru tags, comma-separated, spaces instead of underscores (except score_/source_/rating_ tags). Only real tags, about 25-50 in total; compound tags for objects (holding sex toy, purple dildo, red lace bra). Order inside a section: count, hair, eyes, face/expression, body, clothing top-down, pose/action, sex act/position (sex, vaginal, missionary, cowgirl position, doggystyle, fellatio, cunnilingus, hetero...), composition/camera, background, lighting. One framing tag only (full body, cowboy shot, upper body or close-up; for sex scenes pick full body or cowboy shot so the action is visible); never write portrait or landscape as tags. No contradictions (closed eyes + eye colour). Weights like (tag:1.2) only for 1-2 features the model may drop. No sentences, no names, no "by" artists.

ONE PERSON: count tag first (1girl or 1boy, solo), then \`adult\`, then the person, action, camera, setting; then a line with only BREAK and a final section with lighting, skin and ${pony ? 'style tags' : 'quality tags'}.
TWO OR MORE PEOPLE: write sections separated by a line containing only BREAK:
1. Shared section: ${pony ? 'the score/source/rating prefix, then ' : ''}the head count (1girl, 1boy / 2girls / 2boys / 1boy, 2girls ...), adult, hetero / yuri / yaoi as fitting, the shared action or sex position, setting, camera and framing.
2. One section per person, main person first (or left to right), each starting with who it is (woman on left, man on right, woman on top, man behind), then adult, then ONLY that person's hair, eyes, body, clothes, expression, pose and role. Give each person clearly different hair colours; never repeat another person's colours.
3. Final shared section: lighting, skin tags, style${pony ? '' : ', then the quality tags'}.
BREAK is always in capitals, alone on its own line, and never in the negative.

STYLE: natural, realistic skin (natural skin texture). Use mature female / mature male only if a character is clearly middle-aged, at most once. Never use mirror or reflection (they add extra people): describe the room another way.

${pony
    ? `PONY FORMAT: the positive starts with exactly: score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up, source_anime, rating_explicit (rating_questionable if there is no sex or nudity). No masterpiece / best quality tags. Negative (one line): score_4, score_5, score_6, extra person, child, loli, plus 1-4 scene-specific unwanted things (bad hands, extra fingers, extra person).`
    : `ILLUSTRIOUS FORMAT: put the rating tag explicit (sex or genitals shown) or nsfw (nudity only) in the shared section. No quality tags at the start: the very end of the whole prompt is exactly: masterpiece, best quality, amazing quality, very awa, absurdres, newest. Negative (one short line, 10-16 tags): bad quality, worst quality, worst detail, sketch, censor, extra person, child, loli, plus 1-4 scene-specific unwanted things (bad hands, extra fingers, extra person). Never put in the negative anything the positive needs, and never write "no X".`}

OUTPUT exactly this and nothing else:
POSITIVE:
<the positive prompt: tag lines with BREAK lines between sections>
NEGATIVE:
<one line>
ORIENTATION: vertical or horizontal or square`;
}
function sceneUser(text, family, tweak) {
  let t = String(text || '').trim();
  if (t.length > SCENE_MAX_CHARS) t = '…' + t.slice(-SCENE_MAX_CHARS);
  return `Scene:\n<<<\n${t}\n>>>\n\nWrite the ${family === 'pony' ? 'Pony' : 'Illustrious (WAI)'} prompt for this scene. All characters are adults.${tweak ? `\nAlso: ${tweak}` : ''}`;
}
function sceneParse(raw) {
  const txt = String(raw || '').replace(/<think>[\s\S]*?<\/think>/gi, '').replace(/```[a-z]*\s*/gi, '').replace(/\*\*|__(?=\s*(positive|negative|frame|orientation))/gi, '');
  const re = /(^|\n|\s)[ \t>#*-]*(positive|negative|frame|orientation)(?: prompt)?[ \t]*[:：]/gi;
  const marks = []; let m;
  while ((m = re.exec(txt))) marks.push({ k: m[2].toLowerCase(), at: m.index + m[0].length, from: m.index });
  const out = { positive: '', negative: '', frame: '', orientation: '' };
  if (!marks.length) { out.positive = txt.trim(); return out; }
  if (!marks.some(x => x.k === 'positive')) out.positive = txt.slice(0, marks[0].from).trim();
  marks.forEach((x, i) => { const end = i + 1 < marks.length ? marks[i + 1].from : txt.length; if (!out[x.k]) out[x.k] = txt.slice(x.at, end).trim(); });
  return out;
}
function sceneFix(raw, family = 'illustrious', scene = '') {
  const olderF = /\b(milf|cougar|mature (woman|lady)|older woman|middle-aged (woman|lady|wife|mother|mom|mum)|in her (forties|fifties|sixties))\b/i.test(scene);
  const olderM = /\b(dilf|mature man|older man|middle-aged (man|husband|father|dad)|in his (forties|fifties|sixties))\b/i.test(scene);
  const pony = family === 'pony';
  const p = sceneParse(raw);
  const refusal = /\b(i can(not|'t|’t)|i'm sorry|i am sorry|i won'?t|as an ai|cannot (help|assist|comply|create|provide)|unable to (help|assist|create)|against my|not appropriate)\b/i.test(raw) && (p.positive.match(/,/g) || []).length < 6;
  let sections = p.positive.split(/\s*\bBREAK\b\s*/).map(scTags).filter(s => s.length);
  let srcTag = null, ratTag = null;
  const seen = new Set(); let matureUsed = false;
  sections = sections.map(sec => {
    const local = new Set(); const keep = [];
    for (const t of sec) {
      const k = scKey(t);
      if (/^source_/.test(k)) { srcTag = srcTag || k; continue; }
      if (/^rating_/.test(k)) { ratTag = ratTag || k; continue; }
      if (SC_DROP_QUALITY.test(k) || SC_MINOR.test(k) || SC_AVOID.test(k) || /^no /.test(k)) continue;
      if (pony && /^(explicit|nsfw|sensitive|general)$/.test(k)) continue;
      if (/^(portrait|landscape|blonde)$/.test(k)) { if (k === 'blonde') keep.push('blonde hair'); continue; }
      if (/^mature (female|male|wom[ae]n|lady|m[ae]n)$/.test(k)) { const fem = /female|wom|lady/.test(k); if (matureUsed || !(fem ? olderF : olderM)) continue; matureUsed = true; keep.push(fem ? 'mature female' : 'mature male'); continue; }
      if (local.has(k)) continue;
      local.add(k); keep.push(t); seen.add(k);
    }
    return keep;
  }).filter(s => s.length);
  if (!sections.length) sections = [[]];
  // one framing tag only; when the model gives several, keep the widest
  { const FR = ['full body', 'cowboy shot', 'upper body', 'close-up']; const got = FR.filter(f => sections.some(sec => sec.some(t => scKey(t) === f)));
    if (got.length > 1) sections = sections.map(sec => sec.filter(t => { const k = scKey(t); return !FR.includes(k) || k === got[0]; }));
    if (got.length > 1 && !sections[0].some(t => scKey(t) === got[0])) sections[0].push(got[0]); }
  // head count (from count tags anywhere in the first section)
  let people = 0;
  for (const t of sections[0]) { const c = scKey(t).match(SC_COUNT); if (c) people += +c[1]; else if (/^multiple (girls|boys)$/.test(scKey(t))) people = Math.max(people, 2); }
  if (!people && sections[0].includes('solo')) people = 1;
  // one person: "woman on left" makes no sense, keep just "woman"
  if (people === 1) sections.forEach((sec, i) => { if (i > 0 && sec.length) sec[0] = sec[0].replace(/^((adult )?(woman|man|girl|boy|female|male))\s+(on|in) (the )?(left|right|top|bottom|front|back|middle|cent(er|re))$/, '$1'); });
  // adult tags: shared section (after the count tags) and every person's section (after "who it is")
  const first = sections[0];
  if (!first.some(t => scKey(t) === 'adult')) { let i = 0; while (i < first.length && (SC_COUNT.test(scKey(first[i])) || /^(solo|solo focus|multiple (girls|boys))$/.test(scKey(first[i])))) i++; first.splice(i, 0, 'adult'); }
  sections.forEach((sec, i) => { if (i > 0 && scIsPerson(sec) && !sec.some(t => scKey(t) === 'adult')) sec.splice(1, 0, 'adult'); });
  const all = () => sections.flat().map(scKey).join(', ');
  // rating
  const explicit = SC_SEX.test(all()), nude = SC_NUDE.test(all());
  if (!pony && !first.some(t => /^(explicit|nsfw|sensitive|general)$/.test(scKey(t)))) first.splice(first.findIndex(t => scKey(t) === 'adult') + 1, 0, explicit ? 'explicit' : nude ? 'nsfw' : 'sensitive');
  // final shared section: skin tags + quality tags (Illustrious) at the very end
  const personSecs = sections.filter((s, i) => i > 0 && scIsPerson(s)).length;
  if (sections.length > 1 && scIsPerson(sections[sections.length - 1])) sections.push([]);
  if (sections.length === 1 && sections[0].length > 6) sections.push([]);
  const last = sections[sections.length - 1];
  for (const s of SC_SKIN) if (!sections.flat().some(t => scKey(t) === s)) last.push(s);
  if (!pony) last.push(...SC_QUALITY);
  else first.unshift(...SC_SCORE, srcTag || 'source_anime', explicit ? 'rating_explicit' : (ratTag && ratTag !== 'rating_safe' ? ratTag : 'rating_questionable'));
  const positive = sections.filter(s => s.length).map(s => s.join(', ')).join('\nBREAK\n');
  // negative: base + a few scene-specific extras + the safety list, nothing the positive needs
  const posKeys = new Set(sections.flat().map(scKey));
  const extras = scTags(p.negative.replace(/\bBREAK\b/g, ',')).map(t => t.replace(/^no /, '')).filter(t => {
    const k = scKey(t); return k && !posKeys.has(k) && !(pony && SC_DROP_QUALITY.test(k) && !/^score_[456]$/.test(k)) && !/^(adult|mature (female|male)|explicit|nsfw|nude|sex)$/.test(k);
  });
  const neg = []; const nk = new Set();
  const addNeg = (t) => { const k = scKey(t); if (!nk.has(k) && !posKeys.has(k)) { nk.add(k); neg.push(t); } };
  SC_NEG_BASE[pony ? 'pony' : 'illustrious'].forEach(addNeg);
  extras.filter(t => !SC_NEG_TASTE.includes(scKey(t)) && !SC_NEG_BASE.illustrious.includes(scKey(t)) && !SC_NEG_BASE.pony.includes(scKey(t))).slice(0, 6).forEach(addNeg);
  SC_NEG_TASTE.forEach(addNeg);
  const o = ((p.orientation || p.frame).match(/vertical|portrait|horizontal|landscape|wide|square/i) || ['vertical'])[0].toLowerCase();
  const fr = /horizontal|landscape|wide/.test(o) ? 'landscape' : o === 'square' ? 'square' : 'portrait';
  const size = { portrait: '832x1216', landscape: '1216x832', square: '1024x1024' }[fr];
  const breaks = sections.filter(s => s.length).length - 1;
  const warn = refusal ? 'The model did not write a prompt. Press Regenerate or pick another model.'
    : sections.flat().length < 12 ? 'Very short result — press Regenerate for a fuller prompt.'
    : people >= 2 && personSecs < 2 ? `${people} people but not one BREAK section per person — Regenerate usually fixes it.` : '';
  return { positive, negative: neg.join(', '), frame: fr, size, people, personSecs, breaks, refusal, warn, raw };
}
function sceneNote(family, size) {
  return family === 'pony'
    ? `Paste into your ComfyUI workflow (use a prompt node that understands BREAK) with a Pony-based checkpoint · ${size} · Euler a, 25 steps, CFG 7, clip skip 2.`
    : `Paste into your ComfyUI workflow (use a prompt node that understands BREAK) with an Illustrious-based checkpoint · ${size} · Euler a, 25 steps, CFG 5-7.`;
}
/* SCENE-CORE-END */
const sceneCfg = () => { try { return { ...SCENE_DEFAULTS, ...JSON.parse(localStorage.getItem(SCENE_KEY) || '{}') }; } catch { return { ...SCENE_DEFAULTS }; } };
const sceneSave = (c) => { try { localStorage.setItem(SCENE_KEY, JSON.stringify(c)); } catch { } };
function sceneFromMessage(msgId) {
  const m = S.chat?.messages.find(x => x.id === msgId); if (!m) return;
  const t = splitThink(m.content || '').c.trim();
  if (!t) { toast('This reply is empty', 'info'); return; }
  openSceneModal(t, 'Whole reply');
}
function sceneFromComposer() {
  const t = $('#input').value.trim();
  openSceneModal(t, t ? 'Message box' : 'Paste a scene');
}
function openSceneModal(text, source) {
  hideSelScene();
  const cfg = sceneCfg();
  const root = $('#modalRoot');
  const profs = SCENE_MODELS.map(([k, l]) => { const id = resolveModel(k); return `<option value="${k}" ${cfg.model === k ? 'selected' : ''}>${esc(l)}${id ? '' : ' (not installed)'}</option>`; }).join('');
  root.innerHTML = `<div class="modal-back"><div class="confirm oh-modal scene-modal">
    <h3><span class="scene-ico">${icon('palette')}</span>Scene to prompt<small class="scene-src">${esc(source)}</small></h3>
    <textarea class="textarea scene-text" id="scText" spellcheck="true" placeholder="Paste or type a scene from a story…"></textarea>
    <div class="scene-opts">
      <div class="field"><label>Model</label><select class="select" id="scModel">${profs}</select></div>
      <div class="field"><label>Format</label><div class="seg" id="scFam">${[['illustrious', 'Illustrious'], ['pony', 'Pony']].map(([k, l]) => `<button class="${cfg.family === k ? 'on' : ''}" data-v="${k}">${l}</button>`).join('')}</div></div>
      <div class="field grow"><label>Tweak <small>optional</small></label><input class="input" id="scTweak" placeholder="e.g. pov, close-up, she has red hair" autocomplete="off"></div>
    </div>
    <div class="oh-status" id="scStatus"><span class="status-dot"></span><span>Ready</span></div>
    <div class="scene-box"><div class="scene-lbl"><b>Positive</b><button class="btn" data-x="copy-pos">${icon('copy')}Copy</button></div><textarea class="textarea scene-out" id="scPos" spellcheck="false"></textarea></div>
    <div class="scene-box"><div class="scene-lbl"><b>Negative</b><button class="btn" data-x="copy-neg">${icon('copy')}Copy</button></div><textarea class="textarea scene-out neg" id="scNeg" spellcheck="false"></textarea></div>
    <div class="oh-note scene-note" id="scNote">${icon('info')}<span>${esc(sceneNote(cfg.family, '832x1216'))}</span></div>
    <div class="row"><button class="btn" data-x="no">Close</button><button class="btn primary" id="scGo">${icon('palette')}Generate</button></div></div></div>`;
  const ta = $('#scText'); ta.value = text || '';
  let closed = false, ctrl = null, done = false;
  const st = $('#scStatus'), go = $('#scGo'), pos = $('#scPos'), neg = $('#scNeg');
  const setStatus = (cls, dot, msg) => { if (closed) return; st.className = 'oh-status ' + cls; st.innerHTML = (dot === 'spin' ? '<span class="spinner"></span>' : `<span class="status-dot ${dot}"></span>`) + `<span>${esc(msg)}</span>`; };
  const setGo = (busy) => { go.innerHTML = busy ? `${icon('stop')}Stop` : `${icon(done ? 'refresh' : 'palette')}${done ? 'Regenerate' : 'Generate'}`; };
  const close = () => { closed = true; if (ctrl) ctrl.abort(); root.innerHTML = ''; document.removeEventListener('keydown', key, true); };
  const key = (e) => { if (e.key === 'Escape') { e.stopPropagation(); e.preventDefault(); close(); } if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run(); } };
  document.addEventListener('keydown', key, true);
  root.querySelector('[data-x=no]').onclick = close;
  root.querySelector('.modal-back').onclick = (e) => { if (e.target.classList.contains('modal-back')) close(); };
  const copyBtn = (sel, box, what) => { const b = root.querySelector(sel); b.onclick = async () => { const v = box.value.trim(); if (!v) return; await copyText(v); b.innerHTML = icon('check') + 'Copied'; toast(what + ' prompt copied', 'ok'); setTimeout(() => { if (!closed) b.innerHTML = icon('copy') + 'Copy'; }, 1400); }; };
  copyBtn('[data-x=copy-pos]', pos, 'Positive'); copyBtn('[data-x=copy-neg]', neg, 'Negative');
  $('#scModel').onchange = (e) => { cfg.model = e.target.value; sceneSave(cfg); };
  $('#scFam').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; cfg.family = b.dataset.v; sceneSave(cfg); $$('#scFam button').forEach(x => x.classList.toggle('on', x === b)); $('#scNote span').textContent = sceneNote(cfg.family, '832x1216'); if (done && !ctrl) run(); };
  async function run() {
    if (ctrl) { ctrl.abort(); return; }
    const scene = ta.value.trim(); if (!scene) { ta.focus(); setStatus('warn', 'loading', 'Paste or type a scene first'); return; }
    if (S.gen) { setStatus('warn', 'loading', 'A chat reply is still being written — wait for it (or press Esc in the chat), then Generate.'); return; }
    const model = resolveModel(cfg.model);
    if (!model) { setStatus('err', 'failed', `${cfg.model} is not installed on the llama router`); return; }
    const name = R.labelForModel(S.routing, model) || splitName(model).name;
    const fam = cfg.family; const tweak = $('#scTweak').value.trim();
    ctrl = new AbortController(); setGo(true); const t0 = performance.now();
    let raw = '', tries = 0, res = null;
    try {
      while (tries < 2) {
        tries++; raw = '';
        setStatus('warn', 'spin', (S.mode === 'router' && modelStatus(model) !== 'loaded') ? `Loading ${name}… (the router swaps models, ~10-30 s)` : `${name} is writing the prompt…`);
        const body = { model, stream: true, cache_prompt: true, max_tokens: 900, temperature: (done || tries > 1) ? 0.85 : 0.6, top_p: 0.92, min_p: 0.05, repeat_penalty: 1.05,
          seed: Math.floor(Math.random() * 1e9), chat_template_kwargs: { enable_thinking: false },
          messages: [{ role: 'system', content: sceneSystem(fam) }, { role: 'user', content: sceneUser(scene, fam, tweak) }] };
        const r = await fetch(LLAMA + '/v1/chat/completions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctrl.signal });
        if (!r.ok) { const txt = await r.text(); let msg = txt; try { msg = JSON.parse(txt).error?.message || txt; } catch { } throw new Error(`${r.status} · ${msg || r.statusText}`); }
        refreshModels();
        let n = 0;
        await readSSE(r, (j) => { const d = (j.choices || [])[0]?.delta || {}; if (d.content) { raw += d.content; n++; if (!closed) { pos.value = raw; pos.scrollTop = pos.scrollHeight; if (n === 1) setStatus('warn', 'spin', `${name} is writing the prompt…`); } } });
        res = sceneFix(raw, fam, scene);
        if (!res.refusal) break;
      }
      if (closed) return;
      done = true;
      pos.value = res.positive; neg.value = res.negative;
      $('#scNote span').textContent = sceneNote(fam, res.size);
      const secs = ((performance.now() - t0) / 1000).toFixed(1);
      if (res.warn) setStatus('warn', 'loading', res.warn);
      else setStatus('ok', 'loaded', `Done in ${secs} s · ${name} · ${fam === 'pony' ? 'Pony' : 'Illustrious'} · ${res.people || 1} ${res.people === 1 || !res.people ? 'person' : 'people'} · ${res.breaks} BREAK${res.breaks === 1 ? '' : 's'}`);
    } catch (e) {
      if (e.name === 'AbortError') { if (!closed) setStatus('', '', 'Stopped'); }
      else setStatus('err', 'failed', /Failed to fetch|NetworkError/i.test(e.message) ? 'Connection to the HomeAI server was lost.' : e.message);
    } finally {
      ctrl = null; if (!closed) setGo(false); refreshModels();
    }
  }
  go.onclick = run;
  setGo(false);
  if (ta.value.trim()) run(); else ta.focus();
}
/* floating "🎨 Make prompt" button for a text selection inside an assistant reply */
function selSceneText() {
  const sel = window.getSelection(); if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
  const r = sel.getRangeAt(0); const n = r.commonAncestorContainer; const el = n.nodeType === 1 ? n : n.parentElement;
  if (!el || !el.closest('.msg.assistant .slot-content')) return null;
  const text = sel.toString().trim(); if (text.length < 3) return null;
  return { text, rect: r.getBoundingClientRect() };
}
function hideSelScene() { const b = $('#selScene'); if (b) b.hidden = true; }
function updateSelScene() {
  const b = $('#selScene'); if (!b) return;
  const s = $('#modalRoot').innerHTML ? null : selSceneText();
  if (!s || (!s.rect.width && !s.rect.height)) { b.hidden = true; return; }
  b.hidden = false;
  const w = b.offsetWidth || 130, h = b.offsetHeight || 32;
  let top = s.rect.top - h - 8; if (top < 70) top = s.rect.bottom + 8;
  const left = Math.max(8, Math.min(window.innerWidth - w - 8, s.rect.left + s.rect.width / 2 - w / 2));
  b.style.top = Math.round(top) + 'px'; b.style.left = Math.round(left) + 'px';
}
function bindScene() {
  $('#btnScene').innerHTML = icon('palette'); $('#btnScene').onclick = sceneFromComposer;
  const b = document.createElement('button');
  b.id = 'selScene'; b.className = 'sel-scene'; b.hidden = true; b.type = 'button'; b.title = 'Turn the highlighted text into a ComfyUI prompt';
  b.textContent = '🎨 Make prompt';
  b.addEventListener('mousedown', (e) => e.preventDefault());   // keep the selection
  b.onclick = () => { const s = selSceneText(); if (!s) { hideSelScene(); return; } window.getSelection().removeAllRanges(); openSceneModal(s.text, 'Highlighted text'); };
  document.body.appendChild(b);
  document.addEventListener('selectionchange', debounce(updateSelScene, 120));
  scroller().addEventListener('scroll', debounce(updateSelScene, 60), { passive: true });
  window.addEventListener('resize', hideSelScene);
}

/* ---------------- scrolling ---------------- */
const scroller = () => $('#scroller');
let stuck = true;
function nearBottom() { const s = scroller(); return s.scrollHeight - s.scrollTop - s.clientHeight < 120; }
function scrollBottom(force) { const s = scroller(); if (force || stuck) s.scrollTop = s.scrollHeight; updateJump(); }
function stickScroll() { if (stuck) scroller().scrollTop = scroller().scrollHeight; updateJump(); }
function updateJump() { requestAnimationFrame(() => { stuck = nearBottom(); $('#btnJump').hidden = stuck; }); }

/* ---------------- misc UI ---------------- */
function autoGrow() { const t = $('#input'); t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 260) + 'px'; updateSendState(); }
function setTheme(t) {
  S.theme = t; document.documentElement.dataset.theme = t; localStorage.setItem('homeai.theme', JSON.stringify(t));
  $('#btnTheme').innerHTML = icon(t === 'dark' ? 'sun' : 'moon');
  $('#btnTheme').title = t === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
}
function renderAll() {
  renderChatList(); renderModelPicker(); renderPresetChips(); renderThread(); renderThinkToggle(); renderStats(); renderLoadPill(); renderMaxQuality();
  $('#sendHint').textContent = S.settings.sendKey === 'enter' ? 'Enter to send · Shift+Enter for newline' : 'Ctrl+Enter to send';
  if (isDrawerOpen()) renderDrawer();
}
async function copyText(t) {
  try { await Promise.race([navigator.clipboard.writeText(t), new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 800))]); }
  catch { const ta = Object.assign(document.createElement('textarea'), { value: t }); document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); }
}

/* ---------------- voice: local speech-to-text (mic) + text-to-speech (read aloud) ----------------
   Everything stays on this PC: audio is posted to /api/voice/* (server.py -> voice sidecar running faster-whisper
   and Kokoro on the CPU, 127.0.0.1 only). The browser Web Speech API is deliberately NOT used (Chrome/Edge send
   that audio to the cloud). If the local engine is down, replies can still be read by speechSynthesis, but only
   with voices that are installed locally (localService === true). Settings live in localStorage. */
const VOICE_KEY = 'homeai.voice';
const VOICE_DEFAULTS = { readAloud: false, voice: 'bf_emma', speed: 1.0, autoSend: false, autoStop: true, sttModel: 'small.en' };
const VOICE_FALLBACK_LIST = [['bf_emma', 'Emma', 'British'], ['bf_isabella', 'Isabella', 'British'], ['bf_alice', 'Alice', 'British'], ['bf_lily', 'Lily', 'British'], ['af_heart', 'Heart', 'American'], ['af_bella', 'Bella', 'American'], ['af_nicole', 'Nicole', 'American'], ['af_sarah', 'Sarah', 'American'], ['af_aoede', 'Aoede', 'American'], ['af_kore', 'Kore', 'American'], ['af_sky', 'Sky', 'American'], ['af_nova', 'Nova', 'American']].map(([id, name, accent]) => ({ id, name, accent }));
const V = { cfg: { ...VOICE_DEFAULTS }, voices: VOICE_FALLBACK_LIST, engine: null, health: null, rec: null, busy: false,
  q: [], audio: null, playing: false, ctrl: null, msgId: null, warned: false };
function voiceLoadCfg() {
  try { V.cfg = { ...VOICE_DEFAULTS, ...(JSON.parse(localStorage.getItem(VOICE_KEY) || '{}') || {}) }; } catch { V.cfg = { ...VOICE_DEFAULTS }; }
  V.cfg.speed = Math.min(1.5, Math.max(0.7, +V.cfg.speed || 1));
}
const voiceSaveCfg = () => { try { localStorage.setItem(VOICE_KEY, JSON.stringify(V.cfg)); } catch { } };
async function voiceCheck() {
  try {
    const [h, v] = await Promise.all([api('/api/voice/health'), api('/api/voice/voices')]);
    V.health = h; V.engine = !h.load_error;
    if (v?.voices?.length) V.voices = v.voices;
  } catch (e) { V.engine = false; V.health = { error: e.message }; }
  renderVoiceUI();
  const m = $('#voiceMenu'); if (m && !m.hidden && !m.contains(document.activeElement)) renderVoiceMenu();
  return V.engine;
}

/* --- markdown -> plain speakable text (no code blocks, no markdown symbols) --- */
function speakable(src) {
  let s = String(src || '');
  s = s.replace(/<think>[\s\S]*?(<\/think>|$)/gi, ' ');
  s = s.replace(/^[ \t]*(```|~~~)[\s\S]*?(^[ \t]*\1[^\n]*$|(?![\s\S]))/gm, ' ');   // fenced code (also unterminated)
  s = s.replace(/\$\$[\s\S]*?\$\$/g, ' ').replace(/\\\[[\s\S]*?\\\]/g, ' ');           // display math
  s = s.replace(/!\[[^\]]*\]\([^)]*\)/g, ' ');                                         // images
  s = s.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1');                                       // links -> their text
  s = s.replace(/<\/?[a-z][^>]*>/gi, ' ');                                             // html tags
  s = s.replace(/https?:\/\/[^\s)>\]]+/g, ' a link ');
  s = s.replace(/`+([^`\n]*)`+/g, '$1');                                               // inline code -> text
  s = s.replace(/\$([^$\n]{1,80})\$/g, '$1');                                          // inline math
  s = s.replace(/^[ \t]*#{1,6}[ \t]+(.*)$/gm, (m, h) => h.trim() + (/[.!?:]$/.test(h.trim()) ? '' : '.'));
  s = s.replace(/^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(\|[ \t]*:?-{2,}:?[ \t]*)*\|?[ \t]*$/gm, '');  // table separators
  s = s.replace(/^[ \t]*([-*_][ \t]*){3,}$/gm, ' ');                                    // horizontal rules
  s = s.replace(/^[ \t]*>+[ \t]?/gm, '');                                              // quotes
  s = s.replace(/^[ \t]*(?:[-*+•]|\d{1,3}[.)])[ \t]+/gm, '');                          // list markers
  s = s.replace(/^[ \t]*\[[ xX]\][ \t]+/gm, '');                                       // task boxes
  s = s.replace(/^[ \t]*\|(.*)\|[ \t]*$/gm, (m, row) => row.split('|').map(c => c.trim()).filter(Boolean).join(', ') + '.');
  s = s.replace(/(\*\*|__|~~)(?=\S)([\s\S]*?\S)\1/g, '$2').replace(/(^|[^\w*])[*_](?=\S)([^*_\n]*?\S)[*_](?!\w)/g, '$1$2');
  s = s.replace(/[*#~`|]+/g, ' ');
  s = s.replace(/\p{Extended_Pictographic}|\u{FE0F}|\u{200D}/gu, '');
  s = s.replace(/[ \t]*\n[ \t]*\n+/g, '\n').replace(/([^.!?:;,\s])[ \t]*\n/g, '$1.\n');   // a line break = a pause
  return s.replace(/\s+/g, ' ').trim();
}
/* split into chunks for TTS: the first sentence alone (fast start), then ~240-char groups of whole sentences */
function speechChunks(text, first) {
  const sents = text.split(/(?<=[.!?…]["'”’)\]]*)\s+/).map(x => x.trim()).filter(x => /[\p{L}\p{N}]/u.test(x));
  const out = []; let cur = '';
  for (let s of sents) {
    while (s.length > 400) { const i = Math.max(s.lastIndexOf(', ', 360), s.lastIndexOf(' ', 360)); const k = i > 80 ? i + 1 : 360; out.push(...(cur ? [cur] : []), s.slice(0, k).trim()); cur = ''; s = s.slice(k).trim(); }
    if (!cur) cur = s;
    else if ((first && !out.length) || cur.length + s.length > 240) { out.push(cur); cur = s; }
    else cur += ' ' + s;
    if (first && !out.length && cur.length > 25) { out.push(cur); cur = ''; }
  }
  if (cur) out.push(cur);
  return out;
}

/* --- playback queue: fetch WAVs from the local engine (prefetching the next chunk) and play them in order --- */
function voiceSpeak(md, { msgId = null, fresh = true } = {}) {
  if (fresh) voiceStop();
  const text = speakable(md); if (!text) return;
  if (!V.ctrl) V.ctrl = new AbortController();
  if (msgId) V.msgId = msgId;
  for (const c of speechChunks(text, !V.q.length && !V.playing)) {
    const last = V.q[V.q.length - 1];   // merge short streamed sentences into a chunk not fetched yet (smoother prosody)
    if (!fresh && last && !last.p && last.text.length + c.length < 240) last.text += ' ' + c;
    else V.q.push({ text: c, p: null });
  }
  voicePump();
}
function voiceFetch(item) {
  const sig = V.ctrl.signal; const cfg = V.cfg;
  item.p = (async () => {
    if (V.engine === false && localVoice()) return { local: true };
    const r = await fetch('/api/voice/tts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: item.text, voice: cfg.voice, speed: cfg.speed }), signal: sig });
    if (!r.ok) { let m = 'HTTP ' + r.status; try { m = (await r.json()).error.message; } catch { } const e = new Error(m); e.status = r.status; throw e; }
    return { url: URL.createObjectURL(await r.blob()) };
  })();
  item.p.catch(() => { });
}
async function voicePump() {
  if (V.playing) return;
  const ctrl = V.ctrl; const item = V.q[0];
  if (!item || !ctrl) { if (!V.q.length) { V.msgId = null; renderVoiceUI(); } return; }
  for (const it of V.q.slice(0, 2)) if (!it.p) voiceFetch(it);
  V.playing = true; renderVoiceUI();
  let res;
  try { res = await item.p; }
  catch (e) {
    if (ctrl.signal.aborted) return;
    V.engine = false;
    if (!localVoice()) { V.playing = false; voiceStop(); toast('Voice engine unavailable: ' + e.message, 'err'); return; }
    if (!V.warned) { V.warned = true; toast('Local voice engine is offline — using a Windows voice for now', 'info'); }
    res = { local: true };
  }
  if (ctrl !== V.ctrl || ctrl.signal.aborted) { if (res?.url) URL.revokeObjectURL(res.url); return; }
  const next = () => { if (res?.url) URL.revokeObjectURL(res.url); if (ctrl !== V.ctrl) return; V.q.shift(); V.playing = false; V.audio = null; voicePump(); };
  if (V.q[1] && !V.q[1].p) voiceFetch(V.q[1]);
  if (res.local) {
    const u = new SpeechSynthesisUtterance(item.text); const lv = localVoice();
    u.voice = lv; u.lang = lv.lang; u.rate = V.cfg.speed; u.onend = next; u.onerror = next;
    V.audio = { pause: () => speechSynthesis.cancel() }; speechSynthesis.speak(u);
  } else {
    const a = V.audio = new Audio(res.url);
    a.onended = next; a.onerror = next;
    a.play().catch(e => { if (e.name === 'NotAllowedError') { toast('Click anywhere on the page once so the browser allows audio, then try again', 'info'); voiceStop(); } else next(); });
  }
}
function voiceStop() {
  if (V.ctrl) V.ctrl.abort();
  V.ctrl = null;
  for (const it of V.q) it.p?.then(r => r?.url && URL.revokeObjectURL(r.url), () => { });
  V.q = []; V.msgId = null;
  if (V.audio) { try { V.audio.pause(); } catch { } V.audio = null; }
  try { if (window.speechSynthesis) speechSynthesis.cancel(); } catch { }
  V.playing = false; renderVoiceUI();
  if (S.gen) S.gen.voice = false;   // don't keep reading the reply that is still streaming
}
const voiceSpeaking = () => V.playing || V.q.length > 0;
/* fallback only: a voice that is installed on this PC (never an online/cloud voice); prefer a female English one */
function localVoice() {
  if (!window.speechSynthesis) return null;
  const vs = speechSynthesis.getVoices().filter(v => v.localService && /^en/i.test(v.lang));
  const fem = /hazel|susan|libby|sonia|maisie|zira|aria|jenny|eva|female|woman/i;
  return vs.find(v => /en-GB/i.test(v.lang) && fem.test(v.name)) || vs.find(v => fem.test(v.name)) || vs.find(v => /en-GB/i.test(v.lang)) || vs[0] || null;
}
/* called while a reply streams: speak every finished sentence that is not inside a code block */
function voiceFeed(g, final) {
  if (!g.voice) return;
  const sp = splitThink(g.msg.content || '');
  if (sp.open && !final) return;
  const txt = sp.c; const from = g.vPos || 0;
  let end = txt.length;
  if (!final) {
    const fences = txt.match(/^[ \t]*(```|~~~)/gm) || [];
    if (fences.length % 2) { const re = /^[ \t]*(```|~~~)/gm; let m, last = 0; while ((m = re.exec(txt))) last = m.index; end = last; }
    const part = txt.slice(from, end); const re = /[^\s\d][.!?…]["'”’)\]*_]*(?=\s)|\n/g; let m, cut = -1;
    while ((m = re.exec(part))) cut = m.index + m[0].length;
    if (cut < 0) return;
    end = from + cut;
  }
  if (end <= from) return;
  g.vPos = end;
  voiceSpeak(txt.slice(from, end), { msgId: g.msg.id, fresh: false });
}

/* --- microphone -> local Whisper --- */
async function micToggle() {
  if (V.rec) return micStop();
  if (V.busy) return;
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { toast('This browser cannot record audio here', 'err'); return; }
  voiceStop();
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } }); }
  catch (e) { toast(e.name === 'NotAllowedError' ? 'Microphone blocked — allow it in the address bar (padlock icon) for 127.0.0.1' : 'No microphone: ' + e.message, 'err'); return; }
  const mime = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/webm', 'audio/mp4'].find(t => MediaRecorder.isTypeSupported(t)) || '';
  const mr = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
  const rec = V.rec = { mr, stream, chunks: [], t0: performance.now(), heard: false, cancel: false };
  mr.ondataavailable = (e) => { if (e.data && e.data.size) rec.chunks.push(e.data); };
  mr.onstop = () => micDone(rec);
  try {   // level meter + stop after silence
    const ac = rec.ac = new (window.AudioContext || window.webkitAudioContext)();
    const an = ac.createAnalyser(); an.fftSize = 1024; ac.createMediaStreamSource(stream).connect(an);
    const buf = new Float32Array(an.fftSize); let floor = 0.004, quiet = performance.now();
    rec.timer = setInterval(() => {
      an.getFloatTimeDomainData(buf); let sum = 0; for (const x of buf) sum += x * x; const rms = Math.sqrt(sum / buf.length);
      const t = performance.now(); const speech = rms > Math.max(0.012, floor * 3);
      if (speech) { rec.heard = true; quiet = t; } else floor = floor * 0.97 + rms * 0.03;
      const b = $('#btnMic'); if (b) { b.style.setProperty('--lvl', Math.min(1, rms * 12).toFixed(2)); const tl = $('.mic-time', b.parentElement); if (tl) tl.textContent = fmtDur((t - rec.t0) / 1000); }
      if (V.cfg.autoStop && rec.heard && t - quiet > 1700) micStop();
      else if (V.cfg.autoStop && !rec.heard && t - rec.t0 > 12000) { toast('No speech heard — recording cancelled', 'info'); micStop(true); }
      else if (t - rec.t0 > 180000) micStop();
    }, 80);
  } catch { }
  mr.start(250);
  renderVoiceUI();
}
const fmtDur = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
function micStop(cancel) {
  const rec = V.rec; if (!rec) return;
  rec.cancel = !!cancel; clearInterval(rec.timer);
  try { if (rec.mr.state !== 'inactive') rec.mr.stop(); else micDone(rec); } catch { micDone(rec); }
}
async function micDone(rec) {
  if (rec.done) return; rec.done = true;
  clearInterval(rec.timer);
  rec.stream.getTracks().forEach(t => t.stop());
  try { rec.ac?.close(); } catch { }
  if (V.rec === rec) V.rec = null;
  const blob = new Blob(rec.chunks, { type: rec.mr.mimeType || 'audio/webm' });
  if (rec.cancel || !blob.size || (performance.now() - rec.t0) < 400) { renderVoiceUI(); return; }
  V.busy = true; renderVoiceUI();
  try {
    const r = await fetch('/api/voice/stt?model=' + encodeURIComponent(V.cfg.sttModel), { method: 'POST', headers: { 'Content-Type': blob.type || 'application/octet-stream' }, body: blob });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j?.error?.message || 'HTTP ' + r.status);
    V.engine = true;
    const text = (j.text || '').trim();
    if (!text) { toast("Didn't catch that — try again", 'info'); return; }
    const inp = $('#input'); const cur = inp.value;
    inp.value = cur && !/\s$/.test(cur) ? cur + ' ' + text : cur + text;
    autoGrow();
    if (V.cfg.autoSend && !S.gen) send();
    else { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
  } catch (e) { toast('Speech-to-text failed: ' + e.message, 'err'); if (/starting/i.test(e.message)) setTimeout(voiceCheck, 4000); }
  finally { V.busy = false; renderVoiceUI(); }
}

/* --- UI --- */
function renderVoiceUI() {
  const mic = $('#btnMic'), spk = $('#btnSpeak'); if (!mic || !spk) return;
  const recOn = !!V.rec;
  mic.classList.toggle('rec', recOn); mic.classList.toggle('busy', V.busy);
  mic.innerHTML = V.busy ? '<span class="spinner"></span>' : icon(recOn ? 'stop' : 'mic');
  mic.title = V.busy ? 'Transcribing on this PC…' : recOn ? 'Stop recording and transcribe' + (V.cfg.autoStop ? ' (also stops by itself after a pause)' : '') : 'Speak instead of typing (local speech-to-text)';
  $('#micTime').hidden = !recOn; if (!recOn) $('#micTime').textContent = '';
  const talking = voiceSpeaking();
  spk.classList.toggle('on', !!V.cfg.readAloud); spk.classList.toggle('speaking', talking);
  spk.innerHTML = icon(V.cfg.readAloud || talking ? 'volume' : 'volumeOff') + '<span class="eq"><i></i><i></i><i></i></span>';
  spk.title = talking ? 'Stop speaking' : V.cfg.readAloud ? 'Read replies aloud: ON (click to turn off)' : 'Read replies aloud: OFF (click to turn on)';
  $$('.msg [data-act="speak-msg"]').forEach(b => { const on = V.msgId && b.closest('.msg')?.dataset.id === V.msgId; b.classList.toggle('on', !!on); b.title = on ? 'Stop reading' : 'Read aloud'; b.innerHTML = icon(on ? 'stop' : 'volume'); });
}
function renderVoiceMenu() {
  const m = $('#voiceMenu'); const c = V.cfg; const h = V.health || {};
  const st = V.engine === null ? ['', 'Checking…'] : V.engine ? ['ok', 'Local · CPU · ready'] : ['err', h.error && /starting/i.test(h.error) ? 'Starting…' : 'Offline'];
  const groups = ['British', 'American'].map(a => { const vs = V.voices.filter(v => v.accent === a); return vs.length ? `<optgroup label="${a} female">${vs.map(v => `<option value="${esc(v.id)}" ${v.id === c.voice ? 'selected' : ''}>${esc(v.name)}${v.id === 'bf_emma' ? ' (default)' : ''}</option>`).join('')}</optgroup>` : ''; }).join('');
  const hasTurbo = !h.stt_models || h.stt_models.includes('large-v3-turbo');
  const p = ((c.speed - 0.7) / 0.8) * 100;
  m.innerHTML = `<div class="vm-head"><span class="ico">${icon('volume')}</span><b>Voice</b><span class="vm-status ${st[0]}"><span class="dot"></span>${st[1]}</span></div>
    <div class="field"><label>Voice</label><div class="vm-row"><select class="select" data-vk="voice">${groups}</select><button class="btn" data-act="voice-test" title="Play a sample (click again to stop)">${icon('play')}</button></div></div>
    <div class="field"><label>Speed<span class="val">${(+c.speed).toFixed(2)}×</span></label><input type="range" data-vk="speed" min="0.7" max="1.5" step="0.05" value="${c.speed}" style="--p:${p}%"></div>
    ${[['readAloud', 'Read replies aloud', 'Speaks each finished sentence; skips code'], ['autoSend', 'Auto-send after dictation', 'Send as soon as the transcript is ready'], ['autoStop', 'Stop recording on silence', 'Ends the recording after a short pause']].map(([k, l, d]) => `<div class="toggle-row"><span>${l}<small>${d}</small></span><button class="switch ${c[k] ? 'on' : ''}" data-act="voice-toggle" data-k="${k}"></button></div>`).join('')}
    <div class="field"><label>Speech recognition</label><div class="seg" data-seg="voice-stt"><button class="${c.sttModel !== 'large-v3-turbo' ? 'on' : ''}" data-v="small.en">Fast</button>${hasTurbo ? `<button class="${c.sttModel === 'large-v3-turbo' ? 'on' : ''}" data-v="large-v3-turbo">Most accurate</button>` : ''}</div><small>Fast = Whisper small.en (~1 s) · Most accurate = Whisper large-v3-turbo (~3 s)</small></div>
    <div class="vm-foot">${icon('lock')}<span>Runs entirely on this PC — your voice and text never leave it.</span></div>`;
}
function toggleVoiceMenu(force) {
  const m = $('#voiceMenu'); const show = force ?? m.hidden;
  m.hidden = !show; $('#btnVoiceCfg').classList.toggle('open', show);
  if (show) { renderVoiceMenu(); voiceCheck(); }
}
function onVoiceMenuInput(e) {
  const t = e.target; const k = t.dataset.vk; if (!k) return;
  if (k === 'speed') { V.cfg.speed = +t.value; t.style.setProperty('--p', ((t.value - 0.7) / 0.8 * 100) + '%'); const v = t.closest('.field').querySelector('.val'); if (v) v.textContent = (+t.value).toFixed(2) + '×'; }
  if (k === 'voice') { V.cfg.voice = t.value; if (e.type === 'change') voiceSpeak(`Hi, I'm ${V.voices.find(v => v.id === t.value)?.name || 'your assistant'}. This is how I sound.`); }
  voiceSaveCfg();
}
function onSpeakBtn() {
  if (voiceSpeaking()) { voiceStop(); return; }
  V.cfg.readAloud = !V.cfg.readAloud; voiceSaveCfg(); renderVoiceUI();
  if (S.gen) { S.gen.voice = V.cfg.readAloud; if (V.cfg.readAloud) voiceFeed(S.gen, false); }
  const tg = $('#voiceMenu [data-k="readAloud"]'); if (tg) tg.classList.toggle('on', V.cfg.readAloud);
  toast(V.cfg.readAloud ? 'Read replies aloud: on' : 'Read replies aloud: off', 'info');
}
function bindVoice() {
  voiceLoadCfg();
  $('#btnMic').onclick = micToggle;
  $('#btnSpeak').onclick = onSpeakBtn;
  $('#btnVoiceCfg').innerHTML = icon('chevronUp');
  $('#btnVoiceCfg').onclick = (e) => { e.stopPropagation(); toggleVoiceMenu(); };
  $('#voiceMenu').addEventListener('input', onVoiceMenuInput);
  $('#voiceMenu').addEventListener('change', onVoiceMenuInput);
  if (window.speechSynthesis) speechSynthesis.onvoiceschanged = () => { };   // load the local voice list early
  window.addEventListener('pagehide', () => { voiceStop(); if (V.rec) micStop(true); });
  renderVoiceUI();
  const retry = (n) => voiceCheck().then(ok => { if (!ok && n > 0) setTimeout(() => retry(n - 1), 5000); });
  retry(12);   // the engine may still be loading right after HomeAI starts
}

/* ---------------- web search: private, through the local SearXNG (server.py /api/websearch) ----------------
   Off by default; state lives in localStorage. The query is the message text itself (trimmed to ~200 chars):
   a model-written query would cost an extra generation (and in router mode possibly a model swap) per message.
   'Fetch pages' makes server.py (python.exe) download the top pages itself, so it is off by default. */
const WEB_KEY = 'homeai.web';
const WEB_DEFAULTS = { on: false, fetch: false, n: 6 };
const W = { cfg: { ...WEB_DEFAULTS }, alive: null };
const WEB_FETCH_TIP = 'Also reads the text of the top 3 result pages (8 s, 1 MB each). The pages are downloaded by HomeAI itself (python.exe), so HomeAI must be allowed in the security watcher, otherwise it closes HomeAI. Searching alone only talks to SearXNG on 127.0.0.1.';
function webLoadCfg() { try { W.cfg = { ...WEB_DEFAULTS, ...(JSON.parse(localStorage.getItem(WEB_KEY) || '{}') || {}) }; } catch { W.cfg = { ...WEB_DEFAULTS }; } }
const webSaveCfg = () => { try { localStorage.setItem(WEB_KEY, JSON.stringify(W.cfg)); } catch { } };
function webQuery(um) {
  const t = String(um?.content || '').replace(/\s+/g, ' ').trim();
  if (t.length <= 200) return t;
  const cut = t.slice(0, 200); const i = cut.lastIndexOf(' ');
  return i > 120 ? cut.slice(0, i) : cut;
}
/* resolves to the context block (or null: no query / no results / SearXNG down); rejects only when stopped */
async function webSearch(am, um, signal) {
  const q = webQuery(um); if (!q) return null;
  am.web = { query: q, state: 'searching' };
  try {
    const r = await fetch('/api/websearch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ q, n: W.cfg.n, fetch: !!W.cfg.fetch }), signal });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j?.error?.message || 'HTTP ' + r.status);
    W.alive = true;
    am.web = { query: j.query || q, sources: (j.results || []).map(x => ({ title: x.title, url: x.url })), fetched: j.fetched || 0 };
    return j.context || null;
  } catch (e) {
    if (e.name === 'AbortError') { delete am.web; throw e; }
    W.alive = false;
    am.web = { query: q, sources: [], error: /Failed to fetch|NetworkError/i.test(e.message) ? 'Connection to the HomeAI server was lost.' : e.message };
    return null;
  }
}
function withWebContext(c, ctx) {
  const wrap = (t) => `${ctx}\n\n---\n\nUser message:\n${t}`;
  if (!Array.isArray(c)) return wrap(c);
  const i = c.findIndex(x => x.type === 'text');
  return i < 0 ? [...c, { type: 'text', text: wrap('') }] : c.map((x, k) => k === i ? { ...x, text: wrap(x.text) } : x);
}
const webHost = (u) => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return ''; } };
function webSources(w) {
  if (w.error) return `<div class="web-note warn" title="${esc(w.error)}">${icon('globe')}<span>Web search unavailable — answered without web results.</span><small>${esc(w.error)}</small></div>`;
  if (!w.sources?.length) return `<div class="web-note">${icon('globe')}<span>No web results for “${esc(w.query)}” — answered without them.</span></div>`;
  return `<details class="web-src"><summary>${icon('globe')}<span>Sources</span><b>${w.sources.length}</b>${w.fetched ? `<small>${w.fetched} page${w.fetched === 1 ? '' : 's'} read</small>` : ''}<span class="ico chev">${icon('chevron')}</span></summary>
    <ol>${w.sources.map((x, i) => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" title="${esc(x.url)}"><span class="n">${i + 1}</span><span class="t">${esc(x.title)}</span><small>${esc(webHost(x.url))}</small></a></li>`).join('')}</ol></details>`;
}
async function webCheck() {
  try { W.alive = !!(await api('/api/websearch')).alive; } catch { W.alive = false; }
  const m = $('#webMenu'); if (m && !m.hidden) renderWebMenu();
}
function renderWebUI() {
  const b = $('#btnWeb'); if (!b) return;
  b.classList.toggle('on', !!W.cfg.on); b.innerHTML = icon('globe');
  b.title = W.cfg.on ? 'Web search: ON — each message is searched with SearXNG first (click to turn off)' : 'Web search: OFF (click to search the web with SearXNG before replying)';
}
function renderWebMenu() {
  const m = $('#webMenu'); const c = W.cfg;
  const st = W.alive === null ? ['', 'Checking…'] : W.alive ? ['ok', 'SearXNG · ready'] : ['err', 'Offline'];
  m.innerHTML = `<div class="vm-head"><span class="ico">${icon('globe')}</span><b>Web search</b><span class="vm-status ${st[0]}"><span class="dot"></span>${st[1]}</span></div>
    <div class="toggle-row"><span>Search the web before replying<small>Top results are added to your message; the reply cites them as [1], [2]…</small></span><button class="switch ${c.on ? 'on' : ''}" data-act="web-toggle" data-k="on"></button></div>
    <div class="toggle-row" title="${esc(WEB_FETCH_TIP)}"><span>Fetch pages ${icon('info')}<small>Reads the top 3 pages too. Needs HomeAI allowed in the security watcher.</small></span><button class="switch ${c.fetch ? 'on' : ''}" data-act="web-toggle" data-k="fetch" title="${esc(WEB_FETCH_TIP)}"></button></div>
    <div class="field"><label>Results</label><div class="seg" data-seg="web-n">${[5, 6, 8].map(n => `<button class="${+c.n === n ? 'on' : ''}" data-v="${n}">${n}</button>`).join('')}</div></div>
    <div class="vm-foot">${icon('lock')}<span>Searches go through your own SearXNG${S.info?.searxng_url ? ` (${esc(S.info.searxng_url.replace(/^https?:\/\//, ''))})` : ''} — no accounts, no tracking. Safe search off · en-GB.</span></div>`;
}
function toggleWebMenu(force) {
  const m = $('#webMenu'); const show = force ?? m.hidden;
  m.hidden = !show; $('#btnWebCfg').classList.toggle('open', show);
  if (show) { renderWebMenu(); webCheck(); }
}
function onWebBtn() {
  W.cfg.on = !W.cfg.on; webSaveCfg(); renderWebUI();
  const tg = $('#webMenu [data-k="on"]'); if (tg) tg.classList.toggle('on', W.cfg.on);
  toast(W.cfg.on ? 'Web search: on — messages are searched with SearXNG first' : 'Web search: off', 'info');
}
function bindWeb() {
  webLoadCfg();
  $('#btnWeb').onclick = onWebBtn;
  $('#btnWebCfg').innerHTML = icon('chevronUp');
  $('#btnWebCfg').onclick = (e) => { e.stopPropagation(); toggleWebMenu(); };
  renderWebUI();
}

/* ---------------- events ---------------- */
function bind() {
  const set = (sel, ic) => { $(sel).innerHTML = icon(ic); };
  set('#btnCollapse', 'sidebar'); set('#btnExpand', 'sidebar'); set('#btnAppSettings', 'sliders'); set('#btnChatSettings', 'sliders');
  set('#btnExport', 'download'); set('#btnAttach', 'clip'); set('#btnCloseDrawer', 'x'); set('#btnJump', 'arrowDown'); set('#btnSend', 'send');
  $('#btnAppSettings').innerHTML = icon('cpu');
  $$('[data-icon]').forEach(e => e.innerHTML = icon(e.dataset.icon));

  const toggleSidebar = () => { if (window.innerWidth < 900) $('#app').classList.toggle('mobile-open'); else $('#app').classList.toggle('collapsed'); };
  $('#btnCollapse').onclick = toggleSidebar; $('#btnExpand').onclick = toggleSidebar;
  $('#btnNew').onclick = () => newChat();
  $('#btnTheme').onclick = () => setTheme(S.theme === 'dark' ? 'light' : 'dark');
  $('#btnAppSettings').onclick = () => openDrawer('app');
  $('#btnChatSettings').onclick = () => isDrawerOpen() ? closeDrawer() : openDrawer('chat');
  $('#btnCloseDrawer').onclick = closeDrawer; $('#scrim').onclick = closeDrawer;
  $('#btnExport').onclick = exportMarkdown;
  $('#mpBtn').onclick = (e) => { e.stopPropagation(); toggleModelMenu(); };
  $('#btnSend').onclick = () => S.gen ? stopGen() : send();
  $('#btnAttach').onclick = () => $('#fileInput').click();
  $('#btnOH').innerHTML = icon('hand'); $('#btnOH').onclick = ohFromComposer;
  bindScene();
  bindVoice();
  bindWeb();
  $('#fileInput').onchange = (e) => { addFiles(e.target.files); e.target.value = ''; };
  $('#btnJump').onclick = () => { stuck = true; scrollBottom(true); };
  $('#search').addEventListener('input', e => { S.search = e.target.value; renderChatList(); });
  $('#search').addEventListener('keydown', e => { if (e.key === 'Escape') { e.target.value = ''; S.search = ''; renderChatList(); e.target.blur(); } if (e.key === 'Enter') { const f = $('.chat-item'); if (f) openChat(f.dataset.id); } });
  $$('#drawerTabs button').forEach(b => b.onclick = () => { S.drawerTab = b.dataset.tab; S.editingPreset = null; renderDrawer(); });
  scroller().addEventListener('scroll', () => { stuck = nearBottom(); $('#btnJump').hidden = stuck; }, { passive: true });

  const inp = $('#input');
  inp.addEventListener('input', autoGrow);
  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.isComposing && (e.ctrlKey || e.metaKey || (S.settings.sendKey === 'enter' && !e.shiftKey))) { e.preventDefault(); if (!S.gen) send(); }
  });
  inp.addEventListener('paste', e => {
    const files = [...(e.clipboardData?.files || [])];
    if (files.length) { e.preventDefault(); addFiles(files); }
  });

  // drag & drop anywhere
  let dragDepth = 0; const ov = $('#dropOverlay');
  const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes('Files');
  window.addEventListener('dragenter', e => { if (!hasFiles(e)) return; e.preventDefault(); dragDepth++; ov.classList.add('show'); });
  window.addEventListener('dragover', e => { if (hasFiles(e)) e.preventDefault(); });
  window.addEventListener('dragleave', e => { if (!hasFiles(e)) return; dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) ov.classList.remove('show'); });
  window.addEventListener('drop', e => { if (!hasFiles(e)) return; e.preventDefault(); dragDepth = 0; ov.classList.remove('show'); addFiles(e.dataTransfer.files); });

  // delegated clicks
  document.addEventListener('click', async (e) => {
    const t = e.target.closest('[data-act]');
    if (!$('#mpMenu').hidden && !e.target.closest('#modelPicker')) toggleModelMenu(false);
    if ($('#routeMenu') && !e.target.closest('#routeMenu') && !e.target.closest('.route-chip')) closeRouteMenu();
    if (!$('#voiceMenu').hidden && !e.target.closest('.voice-wrap')) toggleVoiceMenu(false);
    if (!$('#webMenu').hidden && !e.target.closest('.web-wrap')) toggleWebMenu(false);
    const segBtn = e.target.closest('.seg button');
    if (segBtn) {
      const seg = segBtn.parentElement.dataset.seg; const v = segBtn.dataset.v;
      $$('button', segBtn.parentElement).forEach(x => x.classList.toggle('on', x === segBtn));
      if (seg === 'theme') setTheme(v);
      else if (seg === 'sendKey') { S.settings.sendKey = v; saveSettings(); renderAll(); }
      else if (seg === 'thinking') { S.chat.settings.thinking = v; touchChat(); renderThinkToggle(); }
      else if (seg === 'rt-strategy') { S.routing.strategy = v; saveRouting(); renderDrawer(); }
      else if (seg === 'voice-stt') { V.cfg.sttModel = v; voiceSaveCfg(); }
      else if (seg === 'web-n') { W.cfg.n = +v; webSaveCfg(); }
      return;
    }
    const pc = e.target.closest('[data-pcolor]');
    if (pc) { const p = presetById(pc.closest('.preset-edit').dataset.preset); p.color = pc.dataset.pcolor; savePresets(); renderDrawer(); renderPresetChips(); return; }
    if (!t) return;
    const act = t.dataset.act, id = t.dataset.id;
    const msgId = t.closest('.msg')?.dataset.id;
    switch (act) {
      case 'open-chat': if (!e.target.closest('.acts') && !e.target.closest('input')) openChat(id); break;
      case 'pin-chat': e.stopPropagation(); { const m = S.chats.find(c => c.id === id); patchChat(id, { pinned: !m.pinned }); } break;
      case 'rename-chat': e.stopPropagation(); startRename(id); break;
      case 'delete-chat': e.stopPropagation(); deleteChat(id); break;
      case 'mp-auto': if (!e.target.closest('.mp-act')) { selectAuto(); toggleModelMenu(false); } break;
      case 'open-routing': e.preventDefault(); e.stopPropagation(); toggleModelMenu(false); openDrawer('routing'); break;
      case 'route-menu': e.stopPropagation(); if ($('#routeMenu')?.dataset.msg === msgId) closeRouteMenu(); else if (!S.gen) openRouteMenu(t); else toast('Wait for the reply to finish (or press Esc)', 'info'); break;
      case 'route-override': { const mid = $('#routeMenu').dataset.msg; closeRouteMenu(); regenerate(mid, { model: id }); } break;
      case 'route-reroute': { const mid = $('#routeMenu').dataset.msg; closeRouteMenu(); regenerate(mid, { reroute: true }); } break;
      case 'toggle-mq': S.routing.maxQuality = !S.routing.maxQuality; saveRouting(); toast(S.routing.maxQuality ? 'Max quality on — hard reasoning goes to the strongest model' : 'Max quality off', 'info'); if (isDrawerOpen() && S.drawerTab === 'routing') renderDrawer(); break;
      case 'rt-toggle': { const k = t.dataset.k; S.routing[k] = !S.routing[k]; t.classList.toggle('on', S.routing[k]); saveRouting(); updateRouteTest(); } break;
      case 'rr-move': case 'rr-rm': { const r = S.routing.rules[t.dataset.c]; const f = t.dataset.f; const arr = [...(r[f] || [])]; const i = +t.dataset.i;
        if (act === 'rr-rm') arr.splice(i, 1); else { const j = i + (+t.dataset.d); if (j >= 0 && j < arr.length) [arr[i], arr[j]] = [arr[j], arr[i]]; }
        r[f] = arr; saveRouting(); const y = $('#drawerBody').scrollTop; renderDrawer(); $('#drawerBody').scrollTop = y; } break;
      case 'rt-reset': if (await confirmBox('Restore routing defaults?', 'Profiles, rules and per-task defaults go back to the built-in values.', 'Restore')) { S.routing = R.mergeRouting(null); saveRouting(); renderDrawer(); } break;
      case 'mp-select': if (!e.target.closest('.mp-act')) { selectModel(id); toggleModelMenu(false); } break;
      case 'mp-load': e.stopPropagation(); loadModel(id); break;
      case 'mp-unload': e.stopPropagation(); unloadModel(id); break;
      case 'mp-reload': e.stopPropagation(); try { await api(LLAMA + '/models?reload=1'); } catch { } refreshModels(); toast('Model list refreshed', 'info'); break;
      case 'add-mode': e.stopPropagation(); openAddMode(); break;
      case 'apply-preset': e.stopPropagation(); applyPreset(id); if (S.drawerTab === 'presets' && isDrawerOpen()) renderDrawer(); break;
      case 'suggest': $('#input').value = t.textContent; autoGrow(); $('#input').focus(); break;
      case 'copy-code': { const code = t.closest('.code-block').querySelector('code').innerText; await copyText(code); t.classList.add('done'); t.innerHTML = icon('check') + '<span>Copied</span>'; setTimeout(() => { t.classList.remove('done'); t.innerHTML = icon('copy') + '<span>Copy</span>'; }, 1500); } break;
      case 'copy-msg': { const m = S.chat.messages.find(x => x.id === msgId); await copyText(m.content || ''); t.innerHTML = icon('check'); setTimeout(() => t.innerHTML = icon('copy'), 1200); } break;
      case 'regen': regenerate(msgId); break;
      case 'speak-msg': if (V.msgId && V.msgId === msgId) voiceStop(); else { const m = S.chat.messages.find(x => x.id === msgId); if (m) voiceSpeak(splitThink(m.content).c, { msgId }); } break;
      case 'voice-toggle': { const k = t.dataset.k; V.cfg[k] = !V.cfg[k]; t.classList.toggle('on', V.cfg[k]); voiceSaveCfg(); if (k === 'readAloud' && S.gen) S.gen.voice = V.cfg.readAloud; renderVoiceUI(); } break;
      case 'web-toggle': { const k = t.dataset.k; W.cfg[k] = !W.cfg[k]; t.classList.toggle('on', W.cfg[k]); webSaveCfg(); renderWebUI(); if (k === 'fetch' && W.cfg.fetch) toast('Fetch pages on — HomeAI (python.exe) will connect to the result sites itself. Allow it in the security watcher.', 'info'); } break;
      case 'voice-test': if (voiceSpeaking()) voiceStop(); else voiceSpeak(`Hi, I'm ${V.voices.find(v => v.id === V.cfg.voice)?.name || 'your assistant'}. This is how I sound at this speed.`); break;
      case 'edit-msg': editMessage(msgId); break;
      case 'oh-msg': ohFromMessage(msgId); break;
      case 'scene-msg': sceneFromMessage(msgId); break;
      case 'toggle-think': { const m = S.chat.messages.find(x => x.id === msgId); m._thinkOpen = !m._thinkOpen; m._thinkUser = true; t.closest('.think').classList.toggle('open', m._thinkOpen); } break;
      case 'zoom': zoomImage(t.src); break;
      case 'rm-img': S.att.images.splice(+t.dataset.i, 1); renderAttachments(); break;
      case 'rm-file': S.att.files.splice(+t.dataset.i, 1); renderAttachments(); break;
      case 'think-mode': S.chat.settings.thinking = t.dataset.v; try { localStorage.setItem(THINK_LS, t.dataset.v); } catch {} touchChat(); renderThinkToggle(); if (isDrawerOpen()) renderDrawer(); break;
      case 'toggle-setting': S.settings[t.dataset.k] = !S.settings[t.dataset.k]; t.classList.toggle('on', S.settings[t.dataset.k]); saveSettings(); break;
      case 'edit-preset': if (e.target.closest('button')) break; S.editingPreset = S.editingPreset === id ? null : id; renderDrawer(); break;
      case 'new-preset': { const p = { id: uid(), name: 'New preset', color: PRESET_COLORS[S.presets.length % PRESET_COLORS.length], icon: 'sparkles', model: S.chat.model || '', system: '', thinking: 'auto', starter: '', desc: '', params: { ...DEFAULT_PARAMS, model_default: MD_ALL() } }; S.presets.push(p); S.editingPreset = p.id; savePresets(); renderDrawer(); renderPresetChips(); } break;
      case 'delete-preset': if (await confirmBox('Delete preset?', `“${presetById(id)?.name}” will be removed.`, 'Delete')) { S.presets = S.presets.filter(p => p.id !== id); S.editingPreset = null; savePresets(); renderDrawer(); renderPresetChips(); } break;
      case 'reset-presets': if (await confirmBox('Restore default presets?', 'Your custom presets will be replaced by General and Coding. Modes you added come back after a reload.', 'Restore')) { S.presets = structuredClone(DEFAULT_PRESETS); savePresets(); renderDrawer(); renderPresetChips(); } break;
      case 'save-as-preset': { const s = S.chat.settings; const p = { id: uid(), name: 'Preset ' + (S.presets.length + 1), color: PRESET_COLORS[S.presets.length % PRESET_COLORS.length], icon: 'sparkles', model: S.chat.model || '', system: s.system, thinking: s.thinking || 'auto', starter: '', desc: '', params: { temperature: s.temperature, top_p: s.top_p, top_k: s.top_k, min_p: s.min_p, max_tokens: s.max_tokens, repeat_penalty: s.repeat_penalty, seed: s.seed, model_default: mdCopy(s) } }; S.presets.push(p); S.chat.presetId = p.id; savePresets(); S.drawerTab = 'presets'; S.editingPreset = p.id; renderDrawer(); renderPresetChips(); toast('Preset created — give it a name', 'ok'); } break;
      case 'reset-to-preset': applyPreset(S.chat.presetId); break;
    }
  });
  $('#drawerBody').addEventListener('input', onDrawerInput);
  $('#drawerBody').addEventListener('change', onDrawerInput);

  // global shortcuts
  document.addEventListener('keydown', e => {
    const k = (e.key || '').toLowerCase();
    if (e.key === 'Escape') {
      if (S.gen) { e.preventDefault(); stopGen(); voiceStop(); return; }
      if (V.rec) { e.preventDefault(); micStop(true); toast('Recording cancelled', 'info'); return; }
      if (voiceSpeaking()) { e.preventDefault(); voiceStop(); return; }
      if (!$('#voiceMenu').hidden) { toggleVoiceMenu(false); return; }
      if (!$('#webMenu').hidden) { toggleWebMenu(false); return; }
      if ($('#routeMenu')) { closeRouteMenu(); return; }
      if ($('#modalRoot').innerHTML) { $('#modalRoot').innerHTML = ''; return; }
      if (!$('#mpMenu').hidden) { toggleModelMenu(false); return; }
      if (isDrawerOpen()) { closeDrawer(); return; }
    }
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && k === 'k') { e.preventDefault(); $('#app').classList.remove('collapsed'); $('#search').focus(); $('#search').select(); }
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && k === 'o') { e.preventDefault(); newChat(); }
    if ((e.ctrlKey || e.metaKey) && k === 'b') { e.preventDefault(); toggleSidebar(); }
    if ((e.ctrlKey || e.metaKey) && k === ',') { e.preventDefault(); isDrawerOpen() ? closeDrawer() : openDrawer('chat'); }
  });
  const closeIfStale = () => { const m = $('#routeMenu'); if (m && performance.now() - (+m.dataset.t || 0) > 400) closeRouteMenu(); };
  window.addEventListener('resize', closeRouteMenu); scroller().addEventListener('scroll', closeIfStale, { passive: true });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshModels(); });
}

/* ---------------- + Add mode (search Hugging Face, download after typing yes, wire up a preset) ---------------- */
async function openAddMode() {
  const root = $('#modalRoot');
  let info;
  try { info = await api('/api/modes'); } catch (e) { toast('Add mode is not available: ' + e.message, 'err'); return; }
  const avail = info.catalog.filter(m => !info.installed.includes(m.key));
  root.innerHTML = `<div class="modal-back"><div class="confirm oh-modal am-modal">
    <h3><span class="oh-ico">${icon('sparkles')}</span>Add a mode</h3>
    <p class="am-note">HomeAI searches Hugging Face for a model that suits this mode and fits your computer. Nothing is downloaded until you type <b>yes</b>.</p>
    <label class="oh-lbl">Mode</label>
    <select class="select" id="amMode">${avail.map(m => `<option value="${esc(m.key)}">${esc(m.label)} - ${esc(m.desc)}</option>`).join('')}${info.installed.length ? `<optgroup label="Already installed (pick to change its model)">${info.catalog.filter(m => info.installed.includes(m.key)).map(m => `<option value="${esc(m.key)}">${esc(m.label)}</option>`).join('')}</optgroup>` : ''}</select>
    <details class="am-tok"><summary>Hugging Face token (optional)</summary><input class="input" id="amTok" type="password" autocomplete="off" placeholder="hf_… only for gated models; used for this search only, never saved"></details>
    <div class="am-body" id="amBody"></div>
    <div class="row"><button class="btn" data-x="no">Close</button><button class="btn primary" id="amGo">${icon('zap')}Search</button></div></div></div>`;
  let closed = false, pollT = null, job = null;
  const close = () => { closed = true; clearTimeout(pollT); root.innerHTML = ''; document.removeEventListener('keydown', key, true); };
  const key = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
  document.addEventListener('keydown', key, true);
  root.querySelector('[data-x=no]').onclick = close;
  root.querySelector('.modal-back').onclick = (e) => { if (e.target.classList.contains('modal-back') && !(job && job.kind === 'add' && job.state === 'running')) close(); };
  const body = $('#amBody'), go = $('#amGo');
  if (info.busy) body.innerHTML = '<p class="am-warn">Another mode is being added right now. Wait for it to finish.</p>';
  const gib = (n) => (n / 1073741824).toFixed(2);
  const logHtml = (j) => `<pre class="am-log">${esc((j.log || []).slice(-8).join('\n'))}</pre>`;
  const poll = async () => {
    if (closed || !job) return;
    try { job = await api('/api/modes/jobs/' + job.id); } catch (e) { body.innerHTML = `<p class="am-warn">${esc(e.message)}</p>`; return; }
    if (job.state === 'running') {
      const p = job.progress; const pct = p && p.total ? Math.round(100 * p.done / p.total) : null;
      body.innerHTML = `<div class="am-run"><span class="spinner"></span>${job.kind === 'search' ? 'Searching Hugging Face and checking which models fit…' : 'Downloading and checking (SHA-256)…'}</div>` +
        (pct != null ? `<div class="am-bar"><i style="width:${pct}%"></i></div><small>${gib(p.done)} / ${gib(p.total)} GiB (${pct}%)</small>` : '') + logHtml(job);
      pollT = setTimeout(poll, 1500); return;
    }
    if (job.state === 'error') { body.innerHTML = `<p class="am-warn">${esc(job.error || 'failed')}</p>` + logHtml(job); go.disabled = false; return; }
    if (job.kind === 'search') return showChoices();
    body.innerHTML = `<p class="am-ok">${icon('check')} Mode added (model: ${esc(job.result.section)}). Reloading HomeAI…</p>` + logHtml(job);
    setTimeout(() => location.reload(), 1600);
  };
  const showChoices = () => {
    const r = job.result || {}; const ch = r.choices || [], ex = r.existing || [];
    if (!ch.length && !ex.length) { body.innerHTML = `<p class="am-warn">No suitable model was found${(r.errors || []).length ? ' (' + esc(r.errors.join('; ')) + ')' : ''}. Try again later or choose fewer memory-hungry settings.</p>`; go.disabled = false; return; }
    body.innerHTML = `<div class="am-list">${ch.map((c, i) => `<label class="am-choice"><input type="radio" name="amPick" value="${i}" ${i === 0 ? 'checked' : ''}>
        <div><div class="am-t">${esc(c.repo)} <span class="tag">${esc(c.quant)}</span> <span class="tag">${c.download_gib} GiB</span></div>
        <ul>${(c.reasons || []).slice(0, 4).map(x => `<li>${esc(x)}</li>`).join('')}${(c.warnings || []).slice(0, 3).map(x => `<li class="w">${esc(x)}</li>`).join('')}</ul>
        <a href="${esc(c.url)}" target="_blank" rel="noopener">model page ${icon('external')}</a></div></label>`).join('')}
      ${ex.map(e => `<label class="am-choice"><input type="radio" name="amPick" value="existing:${esc(e.section)}" ${!ch.length && e === ex[0] ? 'checked' : ''}><div><div class="am-t">Use a model you already have: ${esc(e.section)}</div></div></label>`).join('')}</div>
      <label class="oh-lbl">Type <b>yes</b> to download the selected model</label><input class="input" id="amYes" autocomplete="off" placeholder="yes">`;
    go.innerHTML = `${icon('download')}Add mode`; go.disabled = false; go.dataset.step = 'add';
  };
  go.onclick = async () => {
    if (go.dataset.step === 'add') {
      const pick = (root.querySelector('input[name=amPick]:checked') || {}).value;
      if (pick == null) return;
      const isEx = String(pick).startsWith('existing:');
      const yes = ($('#amYes')?.value || '').trim();
      if (!isEx && yes.toLowerCase() !== 'yes') { toast('Type yes to confirm the download', 'info'); $('#amYes')?.focus(); return; }
      go.disabled = true;
      try { job = await api('/api/modes/add', { method: 'POST', body: { job_id: job.id, pick: isEx ? pick : +pick, confirm: yes, hf_token: $('#amTok').value } }); }
      catch (e) { toast(e.message, 'err'); go.disabled = false; return; }
      return poll();
    }
    go.disabled = true;
    try { job = await api('/api/modes/search', { method: 'POST', body: { mode: $('#amMode').value, hf_token: $('#amTok').value } }); }
    catch (e) { toast(e.message, 'err'); go.disabled = false; return; }
    poll();
  };
}

/* ---------------- init ---------------- */
async function init() {
  bind();
  setTheme(JSON.parse(localStorage.getItem('homeai.theme') || '"dark"'));
  try { S.info = await api('/api/info'); } catch { }
  const [presets, settings] = await Promise.all([store.get('presets').catch(() => null), store.get('settings').catch(() => null)]);
  S.presets = Array.isArray(presets) && presets.length ? presets : structuredClone(DEFAULT_PRESETS);
  S.settings = { ...DEFAULT_SETTINGS, ...(settings || {}) };
  S.routing = S.settings.routing = R.mergeRouting(S.settings.routing);
  if (!(S.settings.samplingVersion >= 1)) {   // 'Model default' sampling: switch every saved preset to model default (values kept)
    for (const p of S.presets) p.params = { ...DEFAULT_PARAMS, ...(p.params || {}), model_default: MD_ALL() };
    S.settings.samplingVersion = 1;
    store.put('presets', S.presets).catch(() => { }); store.put('settings', S.settings).catch(() => { });
  }
  await Promise.all([refreshModels(), refreshChats(), fetchRouterProps()]);
  const m = /^#\/c\/([\w-]+)/.exec(location.hash);
  if (m && S.chats.some(c => c.id === m[1])) await openChat(m[1]); else newChat();
  renderMaxQuality();
  window.HomeAI = { S, R, buildPayload, exportMarkdown, ready: true }; // debug / test hook
}
init();
})();
