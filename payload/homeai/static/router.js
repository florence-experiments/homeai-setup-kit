/* HomeAI Auto-router: pure functions (no DOM), usable in the browser (window.HomeAIRouter) and in Node tests. */
(function (root, factory) {
  const R = factory();
  if (typeof module === 'object' && module.exports) module.exports = R; else root.HomeAIRouter = R;
})(typeof self !== 'undefined' ? self : this, function () {
'use strict';

const CATEGORIES = ['coding', 'reasoning', 'writing', 'general', 'long', 'vision', 'caption', 'android', 'imageprompt', 'research', 'music'];
const TEXT_CATEGORIES = ['coding', 'reasoning', 'writing', 'general', 'long', 'android', 'imageprompt', 'research', 'music'];
const CATEGORY_LABELS = {
  coding: 'Coding', reasoning: 'Reasoning & maths', writing: 'Writing & creative', general: 'General / quick',
  long: 'Long context', vision: 'Vision (image Q&A, OCR)', caption: 'Image captions (datasets)',
  android: 'App building (Android / mobile)', imageprompt: 'Image & video prompts', research: 'Research (with sources)', music: 'Music (lyrics, tracks)',
};
const RESEARCH_SYSTEM = 'You are a careful research assistant. Cite a source (author/title/URL) for every factual claim you make. ' +
  'Clearly separate established fact, scholarly consensus, minority views and speculation. If you are unsure or no source is available, say so plainly instead of guessing. ' +
  'Prefer primary sources and peer-reviewed scholarship.';

/* Model profiles: one per installed mode (written by setup and '+ Add mode' into data/installed.json, served as
   /installed.js). Each has a short label, the exact router id (as listed by /v1/models) and a fallback match pattern
   used when the exact id is not installed.
   Pattern syntax (case-insensitive substrings):
     "qwen 8b -vision"   -> id must contain "qwen" AND "8b" and must NOT contain "vision"
     "llama | mistral"   -> either alternative
   ctx = context the model is actually started with (tokens; 0 = unknown, never skipped for size).
   Rules list profile keys (= mode names); the first installed one wins, missing ones are skipped. */
const clone = (o) => JSON.parse(JSON.stringify(o));
const INSTALLED = (typeof self !== 'undefined' && self.HOMEAI_INSTALLED) || {};
const DEFAULT_ROUTING = {
  version: 5,
  strategy: 'hybrid',          // 'heuristic' | 'hybrid' (LLM only when heuristics are unsure) | 'llm' (LLM whenever a model is loaded)
  llmMinConfidence: 0.6,       // hybrid: ask the loaded model when heuristic confidence is below this
  llmTimeoutMs: 8000,
  sticky: true,                // prefer the currently loaded model when it is an acceptable choice for the category
  followUp: true,              // keep the chat's routed model for follow-ups unless the category clearly changes
  changeConfidence: 0.7,       // how sure we must be that a follow-up is a different kind of task
  maxQuality: false,           // allow "max quality" models (add them under Settings > Routing) for reasoning / research
  longHardTokens: 48000,       // estimated input above this -> long-context model, always
  longSoftTokens: 24000,       // estimated input above this -> classified as long-context
  profiles: clone(Array.isArray(INSTALLED.profiles) ? INSTALLED.profiles : []),
  rules: {
    coding:      { models: ['coding', 'general'], temperature: 0.6, top_p: 0.95, thinking: 'auto', max_tokens: 0 },
    reasoning:   { models: ['reasoning', 'research', 'general', 'coding'], maxQualityModels: [], temperature: 0.6, top_p: 0.95, thinking: 'on', max_tokens: 0 },
    writing:     { models: ['writing', 'general'], temperature: 0.85, top_p: 0.95, thinking: 'off', max_tokens: 0 },
    general:     { models: ['general', 'coding'], temperature: 0.7, top_p: 0.9, thinking: 'off', max_tokens: 0 },
    long:        { models: ['long', 'general', 'coding'], temperature: 0.5, top_p: 0.9, thinking: 'off', max_tokens: 0 },
    vision:      { models: ['vision', 'caption'], temperature: 0.5, top_p: 0.9, thinking: 'off', max_tokens: 0 },
    caption:     { models: ['caption', 'vision'], temperature: 0.6, top_p: 0.9, thinking: 'off', max_tokens: 512 },
    android:     { models: ['android', 'coding', 'general'], temperature: 0.6, top_p: 0.95, thinking: 'auto', max_tokens: 0 },
    imageprompt: { models: ['imageprompt', 'writing', 'general'], temperature: 0.9, top_p: 0.95, thinking: 'off', max_tokens: 0 },
    research:    { models: ['research', 'reasoning', 'general'], maxQualityModels: [], temperature: 0.6, top_p: 0.95, thinking: 'on', max_tokens: 0, system: RESEARCH_SYSTEM },
    music:       { models: ['music', 'writing', 'general'], temperature: 0.9, top_p: 0.95, thinking: 'off', max_tokens: 0 },
  },
};

function mergeRouting(saved) {
  const d = clone(DEFAULT_ROUTING);
  if (!saved || typeof saved !== 'object') return d;
  const out = Object.assign(d, saved);
  out.profiles = Array.isArray(saved.profiles) && saved.profiles.length ? clone(saved.profiles) : clone(DEFAULT_ROUTING.profiles);
  // profiles installed by setup / '+ Add mode' keep their exact id and context; missing ones are added
  for (const ip of DEFAULT_ROUTING.profiles) {
    const p = out.profiles.find(x => x.key === ip.key);
    if (!p) out.profiles.push(clone(ip));
    else { p.id = ip.id; if (ip.ctx) p.ctx = ip.ctx; if (!p.pattern) p.pattern = ip.pattern; if (p.note == null) p.note = ip.note; }
  }
  out.version = DEFAULT_ROUTING.version;
  const savedRules = clone(saved.rules || {});
  out.rules = {};
  for (const c of CATEGORIES) out.rules[c] = Object.assign(clone(DEFAULT_ROUTING.rules[c]), savedRules[c] || {});
  return out;
}

/* ---------- pattern matching ---------- */
function matchPattern(id, pattern) {
  if (!id || !pattern) return false;
  const s = String(id).toLowerCase();
  return String(pattern).split('|').some(alt => {
    const toks = alt.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (!toks.length) return false;
    return toks.every(t => t.startsWith('-') && t.length > 1 ? !s.includes(t.slice(1)) : s.includes(t));
  });
}
const profileByKey = (cfg, key) => (cfg.profiles || []).find(p => p.key === key);
/* -> installed model id for a profile (prefers a loaded match), or null */
function resolveProfile(profile, models) {
  if (!profile) return null;
  const exact = profile.id && (models || []).find(m => m.id.toLowerCase() === String(profile.id).toLowerCase());
  if (exact) return exact.id;
  const hits = (models || []).filter(m => matchPattern(m.id, profile.pattern));
  if (!hits.length) return null;
  return (hits.find(m => m.status === 'loaded') || hits[0]).id;
}
function profileForModel(cfg, id) {
  const l = String(id || '').toLowerCase();
  return (cfg.profiles || []).find(p => p.id && String(p.id).toLowerCase() === l) || (cfg.profiles || []).find(p => matchPattern(id, p.pattern)) || null;
}
function labelForModel(cfg, id) {
  const p = profileForModel(cfg, id);
  return p ? p.label : String(id || '').replace(/\.gguf$/i, '');
}

/* ---------- heuristic classifier ---------- */
const CODE_EXT = /\.(py|js|mjs|cjs|ts|tsx|jsx|java|kt|go|rs|rb|php|c|h|cpp|hpp|cc|cs|swift|lua|sh|bash|ps1|psm1|bat|cmd|sql|html?|css|scss|vue|svelte|dart|r|ipynb|toml|ya?ml|json|xml|gradle|cmake|dockerfile|makefile)$/i;
const RX = {
  fence: /```/,
  codeLine: /(^|\n)\s*(def |class |function |const |let |var |import |from \S+ import|#include|public |private |static |fn |func |SELECT |INSERT |UPDATE |CREATE TABLE|<\?php|<div|\$\w+\s*=|for \(|while \(|if \(|return )/,
  codeWords: /\b(code|coding|program|programming|script|function|method|class|bug|bugs|debug|error|exception|traceback|stack ?trace|compile|compiler|refactor|implement|unit tests?|regex|api|endpoint|repo|git|github|docker|kubernetes|sql|database|query|json|yaml|html|css|frontend|backend|python|javascript|typescript|java|rust|golang|c\+\+|c#|powershell|bash|shell|batch file|react|vue|node\.?js|npm|pip|cuda|vulkan|rocm|llama\.cpp|segfault|null pointer|syntax ?error|variable|array|loop|recursion|algorithm|library|framework|cli|linux|windows terminal|cmake|makefile|dockerfile|pull request|commit|component|components|hooks?|props|re-?render|render|crash|crashes|build|deploy|install|package|module|config|dependency|dependencies|function call|null|undefined|stdout|stderr|terminal|server|localhost|port)\b/gi,
  camel: /\b[a-z]+[A-Z][A-Za-z]+\b|\b\w+\(\)|\b\w+_\w+\b/,
  reasonWords: /\b(prove|proof|theorem|lemma|derive|derivation|integral|derivative|equation|equations|solve|calculate|compute|probability|statistics|math|maths|mathematics|algebra|geometry|calculus|logic|logical|puzzle|riddle|step[- ]by[- ]step|reasoning|analy[sz]e|analysis|trade-?offs?|optimi[sz]e|complexity|explain why|why does|why do|why is|estimate|physics|chemistry|paradox|hypothesis|deduce|infer|counterexample|game theory|strategy)\b/gi,
  mathy: /(\$[^$\n]+\$|\\frac|\\int|\\sum|\\sqrt|\b\d+\s*[\+\*\/\^×÷]\s*\d+|∫|∑|√|≤|≥)/,
  writeVerb: /\b(write|draft|compose|rewrite|re-write|rephrase|paraphrase|proofread|polish|edit|continue)\b[^.?!\n]{0,60}\b(story|stories|poem|poems|poetry|essay|email|e-mail|letter|article|blog|post|speech|lyrics|song|scene|dialogue|chapter|bio|biography|cover letter|tweet|novel|narrative|haiku|limerick|monologue|eulogy|toast|ad copy|tagline|slogan|description of)\b/i,
  writeWords: /\b(story|poem|poetry|haiku|novel|fiction|fanfic|creative|character|characters|roleplay|role-play|rp|lyrics|limerick|plot|worldbuilding|prose|narrative|metaphor|melancholic|whimsical|tone|in the style of|screenplay|sonnet)\b/gi,
  quick: /^\s*(hi|hello|hey|thanks|thank you|what is|what's|whats|who is|who was|who's|when (is|was|did)|where (is|was)|how many|how much|how old|define|meaning of|translate|is it|can you tell me|quick question|tl;?dr)\b/i,
  summarize: /\b(summari[sz]e|summary|tl;?dr|key points|main points|overview of this)\b/i,
  android: /\b(android|kotlin|jetpack|compose ui|jetpack compose|gradle|play store|google play|play console|firebase|ai studio|google ai studio|apk|aab|android studio|adb|logcat|manifest|viewmodel|room database|material ?3|composable)\b/gi,
  imgPrompt: /\b(comfy ?ui|sdxl|sd ?1\.5|illustrious|pony|flux|wan ?2(\.\d)?|ltx|hunyuan|stable diffusion|negative prompt|positive prompt|image prompt|video prompt|prompt for (an? )?(image|picture|render|video)|lora|checkpoint|ksampler|cfg scale|sampler|workflow json|txt2img|img2img|upscaler?|controlnet|ipadapter|danbooru tags?|booru tags?)\b/gi,
  research: /\b(research|sources?(?![ -]?(code|files?|maps?|tree|control))|cite|citations?|references?(?![ -]?(types?|errors?|counts?))|bibliography|histor(y|ical|ian)|archaeolog\w*|ancient|antiquity|inscriptions?|manuscripts?|scholars?|scholarly|academic|peer[- ]reviewed|primary sources?|literature review|what is known about|competing theories|compare theories|evidence for)\b/gi,
  music: /\b(music|song|songs|track|tracks|lyrics?|bpm|tempo|edm|house music|techno|trance|hip[- ]?hop|rap|jazz|drum and bass|dnb|breakdown|build-?up|riser|bassline|kick drum|hi-?hats?|synth|chord progression|melody|arrangement|ace-?step|stable audio|suno|udio|daw|ableton|fl studio|logic pro|mixdown|mastering|sample pack|stems?|key of [a-g]|[a-g] (minor|major))\b/gi,
};
function countMatches(rx, s) { rx.lastIndex = 0; const m = s.match(rx); return m ? m.length : 0; }

/* -> { category, confidence (0..1), scores, signals } */
function classifyHeuristic(text, files) {
  const t = String(text || '');
  files = files || [];
  const sc = { coding: 0, reasoning: 0, writing: 0, general: 0, android: 0, imageprompt: 0, research: 0, music: 0 };
  const sig = [];
  if (RX.fence.test(t)) { sc.coding += 3; sig.push('code fence'); }
  if (RX.codeLine.test(t)) { sc.coding += 1.5; sig.push('code-like line'); }
  const codeFiles = files.filter(f => CODE_EXT.test(f.name || ''));
  if (codeFiles.length) { sc.coding += 3; sig.push(`code file${codeFiles.length > 1 ? 's' : ''} (${codeFiles.map(f => f.name).slice(0, 3).join(', ')})`); }
  const cw = countMatches(RX.codeWords, t); if (cw) { sc.coding += Math.min(4, cw * 1.2); sig.push(`${cw} coding keyword${cw > 1 ? 's' : ''}`); }
  if (RX.camel.test(t)) { sc.coding += 1; sig.push('identifier-like token'); }
  const rw = countMatches(RX.reasonWords, t); if (rw) { sc.reasoning += Math.min(4, rw * 1.3); sig.push(`${rw} reasoning keyword${rw > 1 ? 's' : ''}`); }
  if (RX.mathy.test(t)) { sc.reasoning += 1.5; sig.push('math notation'); }
  if (RX.writeVerb.test(t)) { sc.writing += 3; sig.push('writing request'); }
  const ww = countMatches(RX.writeWords, t); if (ww) { sc.writing += Math.min(3, ww * 1.2); sig.push(`${ww} creative keyword${ww > 1 ? 's' : ''}`); }
  const an = countMatches(RX.android, t); if (an) { sc.android += Math.min(5, an * 1.8); sc.coding += 0; sig.push(`${an} Android keyword${an > 1 ? 's' : ''}`); }
  const ip = countMatches(RX.imgPrompt, t); if (ip) { sc.imageprompt += Math.min(5, ip * 1.8); sig.push(`${ip} image-prompt keyword${ip > 1 ? 's' : ''}`); }
  const rs = countMatches(RX.research, t); if (rs) { sc.research += Math.min(5, rs * 1.3); sig.push(`${rs} research keyword${rs > 1 ? 's' : ''}`); }
  const mu = countMatches(RX.music, t); if (mu) { sc.music += Math.min(5, mu * 1.4); if (/\blyrics?\b/i.test(t)) sc.writing = Math.max(0, sc.writing - 2); sig.push(`${mu} music keyword${mu > 1 ? 's' : ''}`); }
  if (an && sc.coding) sc.coding *= 0.6;           // Kotlin/Gradle questions are Android first
  if (ip && sc.writing) sc.writing *= 0.5;          // "write a prompt for SDXL" is an image prompt, not prose
  if (RX.quick.test(t)) { sc.general += 1.5; sig.push('quick-question phrasing'); }
  if (RX.summarize.test(t)) { sc.general += 1; sig.push('summarise request'); }
  const nonGeneral = sc.coding + sc.reasoning + sc.writing + sc.android + sc.imageprompt + sc.research + sc.music;
  if (t.trim().length < 90 && !files.length && nonGeneral < 1.5) { sc.general += 1.2; sig.push('short message'); }
  let best = 'general', max = 0, sum = 0;
  for (const [k, v] of Object.entries(sc)) { sum += v; if (v > max) { max = v; best = k; } }
  if (max === 0) return { category: 'general', confidence: 0.3, scores: sc, signals: ['no strong signals'] };
  const confidence = Math.round(Math.min(1, (max / sum) * Math.min(1, max / 3)) * 100) / 100;
  return { category: best, confidence, scores: sc, signals: sig };
}

const CAPTION_RX = /\b(caption|captions|captioning|describe|description|descriptive|tag|tags|tagging|booru|danbooru|dataset|training data|alt[- ]?text|lora|prompt for (sd|sdxl|flux|stable diffusion))\b/i;

/* ---------- LLM classifier helpers ---------- */
const CLASSIFIER_SYSTEM = 'You are a request router. Classify the user\'s request into exactly one category:\n' +
  '- coding: writing, fixing, explaining or reviewing code, scripts, configs, shell commands\n' +
  '- reasoning: maths, logic, proofs, puzzles, careful multi-step analysis, hard technical questions\n' +
  '- writing: creative or long-form writing, stories, poems, emails, rewriting/editing prose, roleplay\n' +
  '- general: everyday questions, quick facts, casual chat, short explanations, recommendations\n' +
  '- long: summarising or analysing a very long document or many files\n' +
  '- android: building apps: Android / Kotlin / Jetpack Compose / Gradle / Firebase / mobile app work\n' +
  '- imageprompt: writing or improving prompts for image/video generators (e.g. Stable Diffusion, SDXL, Flux), tags, ComfyUI workflows\n' +
  '- research: researching a topic with sources: history, science literature, comparing theories and evidence\n' +
  '- music: music making: song/track ideas, lyrics, BPM/key, arrangement, music-generator prompts, DAW/mixing tips\n' +
  'Reply with JSON only, e.g. {"category":"coding","confidence":0.9}.';
function classifierRequest(model, text, files) {
  let t = String(text || '');
  if (t.length > 1600) t = t.slice(0, 1200) + '\n…\n' + t.slice(-300);
  const fl = (files || []).map(f => `${f.name} (${Math.round((f.text || '').length / 3.6)} tokens)`).join(', ');
  const schema = { type: 'object', properties: { category: { type: 'string', enum: TEXT_CATEGORIES }, confidence: { type: 'number' } }, required: ['category'] };
  return {
    model, stream: false, max_tokens: 48, temperature: 0, cache_prompt: false,
    chat_template_kwargs: { enable_thinking: false },
    response_format: { type: 'json_schema', schema, json_schema: { name: 'route', schema } },
    messages: [{ role: 'system', content: CLASSIFIER_SYSTEM }, { role: 'user', content: `Request:\n"""\n${t}\n"""${fl ? `\nAttached files: ${fl}` : ''}\n\nCategory JSON:` }],
  };
}
function parseClassifierResponse(content) {
  let c = String(content || '').replace(/<think>[\s\S]*?<\/think>/g, '').trim();
  const m = c.match(/\{[\s\S]*?\}/);
  if (m) {
    try {
      const j = JSON.parse(m[0]);
      const cat = String(j.category || '').toLowerCase().trim();
      if (TEXT_CATEGORIES.includes(cat)) return { category: cat, confidence: typeof j.confidence === 'number' ? Math.max(0, Math.min(1, j.confidence)) : 0.8 };
    } catch (e) { /* fall through */ }
  }
  const w = c.toLowerCase().match(/\b(coding|reasoning|writing|general|long|android|imageprompt|research|music)\b/);
  return w ? { category: w[1], confidence: 0.6 } : null;
}
/* Which loaded model may be used for LLM classification (never swaps): a loaded text-capable model, not a caption-only one. */
function pickClassifierModel(cfg, models) {
  const loaded = (models || []).filter(m => m.status === 'loaded');
  const joy = profileByKey(cfg, 'caption');
  const ok = loaded.filter(m => !(joy && matchPattern(m.id, joy.pattern)));
  return (ok.find(m => !m.vision) || ok[0] || null)?.id || null;
}
/* Should we ask the LLM? */
function wantsLLM(cfg, heuristic, hardRule) {
  if (hardRule) return false;
  if (cfg.strategy === 'llm') return true;
  if (cfg.strategy === 'hybrid') return heuristic.confidence < (cfg.llmMinConfidence ?? 0.6);
  return false;
}

/* ---------- routing ---------- */
/* input: {
     text, files:[{name,text}], images: number, estTokens: number,
     models: [{id, status, vision}], cfg,
     prev: {category, model} | null        // last routed assistant message in this chat
     llm: {category, confidence} | null     // LLM classification, if one was obtained
     historyHasImages: bool
   }
   -> { model, category, via, reason, kept, alternatives, skipped, heuristic, fallback } */
function route(input) {
  const cfg = input.cfg || DEFAULT_ROUTING;
  const models = input.models || [];
  const est = input.estTokens || 0;
  const text = String(input.text || '');
  const heur = classifyHeuristic(text, input.files);
  const notes = [];
  let category, via, hard = false, confidence;

  // 1) hard rules
  if (input.images > 0) {
    hard = true; via = 'rule';
    category = (!text.trim() || CAPTION_RX.test(text)) ? 'caption' : 'vision';
    notes.push(category === 'caption' ? 'image attached with a caption/description request' : 'image attached');
  } else if (est > (cfg.longHardTokens || 48000)) {
    hard = true; via = 'rule'; category = 'long';
    notes.push(`~${Math.round(est / 1000)}k input tokens > ${Math.round((cfg.longHardTokens || 48000) / 1000)}k`);
  } else if (est > (cfg.longSoftTokens || 24000)) {
    via = 'rule'; category = 'long'; confidence = 0.9;
    notes.push(`~${Math.round(est / 1000)}k input tokens (long input)`);
  } else if (input.llm && input.llm.category) {
    category = input.llm.category; confidence = input.llm.confidence ?? 0.8; via = 'llm';
    notes.push(`classified by loaded model as ${category}`);
  } else {
    category = heur.category; confidence = heur.confidence; via = 'heuristic';
    notes.push(`heuristics: ${heur.signals.slice(0, 3).join(', ')}`);
  }

  // 2) follow-ups keep the chat's model unless the task clearly changed
  const prev = input.prev;
  if (cfg.followUp && prev && prev.model && models.some(m => m.id === prev.model) && !input.force) {
    const clearlyChanged = hard ? category !== prev.category
      : (category !== prev.category && category !== 'general' && (confidence ?? 0) >= (cfg.changeConfidence ?? 0.7));
    const sizeOk = (() => { const p = profileForModel(cfg, prev.model); return !(p && p.ctx && est > p.ctx * 0.9); })();
    if (!clearlyChanged && sizeOk) {
      return finish({ model: prev.model, category: prev.category, via: 'follow-up',
        reason: `follow-up in this chat: kept ${labelForModel(cfg, prev.model)} (${category === prev.category ? 'same kind of task' : `looks like ${category}, not a clear change`})`,
        alternatives: candidatesFor(cfg, prev.category, models, est).map(c => c.id) });
    }
    if (clearlyChanged) notes.push(`task changed from ${prev.category} to ${category}`);
  }

  // 3) candidates for the category
  const cands = candidatesFor(cfg, category, models, est);
  const skipped = cands.skipped;
  let model = null, kept = false, fallback = false;
  if (cands.length) {
    const loaded = cfg.sticky ? cands.find(c => c.status === 'loaded') : null;
    if (loaded) { model = loaded.id; kept = true; if (loaded.id !== cands[0].id) notes.push(`${labelForModel(cfg, loaded.id)} is already loaded and acceptable (avoids a swap)`); }
    else model = cands[0].id;
  } else {
    // nothing from the rule list is installed: any installed model that fits, loaded first, text-capable unless images
    const needVision = category === 'vision' || category === 'caption';
    const pool = models.filter(m => (needVision ? m.vision : true));
    const pick = pool.find(m => m.status === 'loaded') || pool.find(m => !m.vision) || pool[0];
    if (pick) { model = pick.id; fallback = true; notes.push(`no model from the ${category} rule is installed, fell back to ${labelForModel(cfg, pick.id)}`); }
  }
  return finish({ model, category, via, kept, fallback, skipped, reason: notes.join('; '), alternatives: cands.map(c => c.id) });

  function finish(d) {
    d.heuristic = heur;
    d.confidence = confidence ?? null;
    d.estTokens = est;
    const m = models.find(x => x.id === d.model);
    if (d.kept === undefined || d.via === 'follow-up') d.kept = !!(m && m.status === 'loaded');
    d.label = d.model ? labelForModel(cfg, d.model) : null;
    d.skipped = d.skipped || [];
    return d;
  }
}
/* ordered installed candidates for a category; .skipped explains missing/too-small ones */
function candidatesFor(cfg, category, models, est) {
  const rule = (cfg.rules || {})[category] || { models: [] };
  const keys = [...(cfg.maxQuality && rule.maxQualityModels ? rule.maxQualityModels : []), ...(rule.models || [])];
  const out = []; out.skipped = [];
  const seen = new Set();
  for (const key of keys) {
    const p = profileByKey(cfg, key);
    if (!p) { out.skipped.push(`${key}: unknown profile`); continue; }
    const id = resolveProfile(p, models);
    if (!id) { out.skipped.push(`${p.label}: not installed`); continue; }
    if (seen.has(id)) continue;
    if (p.ctx && est > p.ctx * 0.9) { out.skipped.push(`${p.label}: ${Math.round(p.ctx / 1024)}k context too small`); continue; }
    seen.add(id);
    const m = models.find(x => x.id === id);
    out.push({ id, key, status: m.status, label: p.label });
  }
  return out;
}
function samplingFor(cfg, category) {
  const r = (cfg.rules || {})[category] || {};
  return { temperature: r.temperature, top_p: r.top_p, thinking: r.thinking || 'auto', max_tokens: r.max_tokens || 0, system: r.system || '' };
}
/* first-choice categories per installed model, for picker tags */
function rolesForModel(cfg, id, models) {
  const roles = [];
  for (const c of CATEGORIES) { const cands = candidatesFor(cfg, c, models, 0); if (cands[0] && cands[0].id === id) roles.push(c); }
  return roles;
}

return { CATEGORIES, TEXT_CATEGORIES, CATEGORY_LABELS, DEFAULT_ROUTING, mergeRouting, matchPattern, resolveProfile, profileForModel,
  labelForModel, classifyHeuristic, classifierRequest, parseClassifierResponse, pickClassifierModel, wantsLLM, route, candidatesFor,
  samplingFor, rolesForModel, CAPTION_RX, RESEARCH_SYSTEM };
});
