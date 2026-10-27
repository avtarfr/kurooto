/* The being (0.8.9): the dashboard's board as one organism. Every light in it is something Kurooto is doing, from the
   live stream: sparks fire in the region of the brain that does that kind of work, blood carries work from the heart to the
   organ (and back when it reports), nerves carry what is heard and said, the notes are its memory, each feature is a point
   of light on the organ that does its work. Nothing moves for show.
   At rest (0.8.11, look.being_resting_sparks) the brain keeps a low trickle of sparks, each from something it really
   does all the time: every reading of its body (the vitals on the live stream, every 2 s, more the busier the
   processor) in the insula, its own processes' processor use in the thalamus, a scheduler timer that fired in its
   feature's region, notes that changed in the hippocampus, sound heard in the auditory cortex.
   The vessels and nerves are joined to the organs and stay joined as they turn; the nerves leave the brainstem as the
   spinal cord and split at a plexus behind the heart, fibre bundles with nerve cells along them.

   While the microphone's levels come (0.8.13, look.being_live_waveform) the YOU lane is a live trace of them; both
   lanes are smooth mirrored waveforms.

   Brain's status (0.8.14, mind/status.py, enums and numbers only; status(m)): with look.being_status its eyes shut while
   focus time is on or it's asleep, a small count of held messages sits by the heart, and a slow glow marks the one
   deadline or promise it's uneasy about (a tap opens it: opts.openItem, else that feature's panel). With
   look.being_mood its own mood tints the fluid round the brain and sets the heart's rhythm (low is only quieter: dimmer
   and softer, never a sad face), arousal quickens the pulse, and the pupil follows how much it explores (mood) and
   narrows a little while its beliefs are no better than a guess.

   beingMount(host, {api, token, theme, openItem}) -> {update(body), event(ev), graph(g), voice(m), status(m), stop()}
   Needs vendor/three (three.js r128 and its bloom passes) and body/anatomy.bin, body/cerebrum.vol (tools/gen_body_meshes.py).
   Turn and zoom: drag, wheel; right-drag pans. Click an organ to look into it, a part of it for its settings, a point of
   light for its feature, a note for its preview; Esc or empty space goes back. */
(function () {
"use strict";
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const NOISE = `float h3(vec3 q){return fract(sin(dot(q,vec3(127.1,311.7,74.7)))*43758.5453);}float n3(vec3 x){vec3 i=floor(x),f=fract(x);f=f*f*(3.-2.*f);return mix(mix(mix(h3(i),h3(i+vec3(1,0,0)),f.x),mix(h3(i+vec3(0,1,0)),h3(i+vec3(1,1,0)),f.x),f.y),mix(mix(h3(i+vec3(0,0,1)),h3(i+vec3(1,0,1)),f.x),mix(h3(i+vec3(0,1,1)),h3(i+vec3(1,1,1)),f.x),f.y),f.z);}
float fbm(vec3 p){float s=0.,a=.5;for(int i=0;i<5;i++){s+=a*n3(p);p*=2.03;a*=.5;}return s;}`;

/* --- what each kind of event is, its colour and where in the brain it happens (brain-local: x right, y up, z front) --- */
const PROC = {
  think: { c: 0xf2c46d, at: [.22, .28, .55], name: "AI requests" }, hold: { c: 0xb9a37a, at: [.22, .28, .55], name: "held at its limit" },
  plan: { c: 0xf0a77e, at: [-.22, .36, .46], name: "plans, calendar" }, attend: { c: 0xf4f1e8, at: [0, .02, -.08], name: "attention" },
  conscience: { c: 0xe98fa6, at: [0, -.14, .52], name: "the gate" }, act: { c: 0xd6a8e8, at: [.24, .44, .1], name: "acting" },
  memory: { c: 0xa99bf0, at: [.27, -.22, .04], name: "notes, sync" }, speak: { c: 0x8fd3e8, at: [-.44, -.02, .32], name: "speaking" },
  hear: { c: 0x7fe0c4, at: [.48, -.08, -.04], name: "hearing" }, touch: { c: 0x9fe3a8, at: [.28, .42, -.06], name: "touch, phone" },
  see: { c: 0xc6e88f, at: [.12, .1, -.72], name: "sight" }, feel: { c: 0xf09090, at: [.34, -.02, .12], name: "its body" },
};
const KIND = {
  job_queued: "think", job_done: "think", job_failed: "think", job_held: "hold", notes_synced: "memory", gbrain_sync: "memory",
  file_sent: "memory", hw_pull: "memory", profile_saved: "memory", integrate_batch: "memory", sorter_moved: "memory",
  calendar_synced: "plan", calendar_failed: "plan", deadline_added: "plan", deadline_done: "plan", deadline_moved: "plan",
  notified: "speak", notify_queued: "speak", notify_delayed: "speak", notify_failed: "speak", telegram_error: "speak", reminder_fired: "speak",
  message_in: "hear", calls_link: "hear", call_rang: "hear", call_answered: "hear", phone_views_pushed: "touch", phone_today_pushed: "touch",
  senses_phone: "touch", lidsafe_pushed: "touch", power_mode: "feel", awake_holding: "feel", awake_released: "feel",
  night_performance_on: "feel", night_performance_left: "feel", local_models_rest: "feel", helper_online: "feel", helper_offline: "feel",
  mind_gate_held: "conscience", mind_program: "conscience", study_timer: "attend", study_session_start: "attend", study_session_end: "attend",
  action: "act", setting_changed: "act",
  face_arrived: "see", face_left: "see", face_watch: "see", face_greeted: "see",
};
const RETURNS = new Set(["job_done", "calendar_synced", "gbrain_sync", "notes_synced", "message_in", "profile_saved", "hw_pull", "phone_views_pushed"]);
const EV_FEATURE = {
  job_done: "chat", job_queued: "chat", job_held: "chat", action: "chat", notes_synced: "notes_sync", notes_sync_failed: "notes_sync",
  gbrain_sync: "gbrain", file_sent: "files", hw_pull: "hw_pull", profile_saved: "profile", calendar_synced: "calendar", calendar_failed: "calendar",
  notified: "telegram", notify_queued: "telegram", notify_failed: "telegram", message_in: "telegram", telegram_error: "telegram",
  phone_views_pushed: "calls", phone_today_pushed: "calls", calls_link: "calls", lidsafe_pushed: "lidsafe", awake_holding: "awake",
  awake_released: "awake", night_performance_on: "night_performance", night_performance_left: "night_performance",
  local_models_rest: "local_models", helper_online: "local_models", helper_offline: "local_models", mind_gate_held: "mind",
  mind_program: "mind", study_timer: "study", study_session_start: "study", study_session_end: "study", deadline_added: "deadlines",
  deadline_done: "deadlines", reminder_fired: "reminders", integrate_batch: "integrate", sorter_moved: "sorter",
  face_arrived: "face", face_left: "face", face_watch: "face", face_greeted: "face",
};
/* the brain's regions, each with the parts of Brain that live there (core/brainview.py ids) and the features homed there */
const REGIONS = {
  reason: { name: "Prefrontal cortex", sub: "reasoning · AI requests", at: [.22, .28, .55], parts: [], feats: ["chat", "doubts", "hints", "drafts", "cases", "projects", "curious"] },
  plan: { name: "Dorsolateral prefrontal", sub: "plans, the calendar, forecasts", at: [-.22, .36, .46], parts: ["read", "forecast", "plans", "harness"], feats: ["deadlines", "startby", "commitments", "agent_plan", "calendar", "google_calendar", "google_plan", "exam_season", "weekly", "quests", "recurring", "daily"] },
  conscience: { name: "Orbitofrontal cortex", sub: "the gate · what may reach you", at: [0, -.14, .52], parts: ["promises", "gate", "autonomy", "stops", "precedents"], feats: ["mind", "retro", "habits", "friends"] },
  act: { name: "Motor strip", sub: "acting", at: [.24, .44, .1], parts: [], feats: ["terminals", "terminal", "desktop", "desktop_helpers", "files", "finder"] },
  touch: { name: "Somatosensory strip", sub: "touch · the phone", at: [.28, .42, -.06], parts: ["phone"], feats: [] },
  broca: { name: "Broca's area", sub: "speaking (left)", at: [-.44, -.02, .32], parts: [], feats: ["telegram", "reminders", "checkins", "alarm", "reply_drafts", "digest_email", "text"] },
  auditory: { name: "Auditory cortex", sub: "hearing", at: [.48, -.08, -.04], parts: [], feats: ["voice"] },
  visual: { name: "Visual cortex", sub: "sight · your activity", at: [.12, .1, -.72], parts: ["activity"], feats: [] },
  tpj: { name: "Temporoparietal junction", sub: "a model of you", at: [.42, .22, -.3], parts: ["tom", "tone", "deep"], feats: [] },
  thal: { name: "Thalamus", sub: "what's on its mind now", at: [0, .02, -.08], parts: ["workspace", "attention", "beliefs"], feats: ["subjects", "classpacks", "capture", "termnote"] },
  hippo: { name: "Hippocampus", sub: "memory", at: [.27, -.22, .04], parts: ["log", "journal", "story", "forget", "history"], feats: ["remember", "dreaming", "learning", "gbrain", "consolidate", "fold"] },
  insula: { name: "Insula", sub: "its body", at: [.34, -.02, .12], parts: ["budget", "feelings", "heartbeat", "intero"], feats: [] },
  cereb: { name: "Cerebellum", sub: "skills, the lab", at: [.22, -.5, -.58], parts: ["lab", "improve", "skills", "finetune", "play"], feats: ["skills", "local_models", "laya", "library", "prompt_harvest", "overlay"] },
};
const HEART_PARTS = {
  pacemaker: { name: "Pacemaker", sub: "the scheduler: what runs next", at: [-.3, .4, 0], sections: ["power"], feats: [] },
  ventricles: { name: "Ventricles", sub: "work pushed out: AI requests running and waiting", at: [.1, -.35, .15], sections: ["jobs"], feats: [] },
  atria: { name: "Atria", sub: "what comes back: answers", at: [.05, .42, -.1], sections: [], feats: [] },
  aorta: { name: "Aorta", sub: "the call line to your phone", at: [.2, .85, -.2], sections: ["calls"], feats: ["calls"] },
  coronaries: { name: "Coronaries", sub: "its upkeep: backups, updates, sync", at: [-.05, -.1, .45], sections: ["updates", "backups", "profile"], feats: ["backups", "restic", "profile", "repo_sync", "space"] },
};
const SENSES = {
  sight: { name: "Sight", sub: "the screen, light, what you're working on", parts: ["activity"], feats: ["study", "research", "research_addon", "face"], sections: ["study"] },
  hearing: { name: "Hearing", sub: "calls, voice, messages in", parts: [], feats: ["calls", "voice", "google", "google_mail", "google_confidential", "mailin", "mail_digest", "voice_notes"], sections: ["voice", "calls"], panel: "ear" },
  touch: { name: "Touch", sub: "your phone in your hand", parts: ["phone"], feats: ["lidsafe"], sections: [] },
  balance: { name: "Balance", sub: "your phone's motion and steps", parts: ["phone"], feats: ["campus", "awake"], sections: [] },
  heat: { name: "Its own body", sub: "this computer: processor, memory, graphics, heat", parts: ["intero"], feats: ["night_performance", "space"], sections: ["power"], panel: "pc" },
};
const MEMORY_FEATS = ["books", "classroom_notes", "drive_upload", "integrate", "sorter", "handwritten", "handwritten_links", "hw_pull", "quiz", "quiz_links", "notes_sync", "google_drive", "google_classroom", "coursepack", "coursepages", "revision", "latex_tracker", "photodates", "zotero"];
// a hue for each neighbourhood of notes: clear colours, not pastels (0.8.11: they read as grey from afar), spaced round
// the wheel so neighbours differ; on a light page they're made darker (hoodCols), on a theme leaned to its accent
const HOOD_COLS = [0xf5b041, 0x4fb3f0, 0x9d7cf4, 0x3fd69a, 0xf2685c, 0xe36cc9, 0xa9d94b, 0x38c9d9, 0xf58c3a, 0x6f8ff5, 0xf27ea0, 0x34b89f];

function homeOf(id) {
  for (const [k, r] of Object.entries(REGIONS)) if (r.feats.includes(id)) return ["mind", k];
  for (const [k, r] of Object.entries(SENSES)) if (r.feats.includes(id)) return ["senses", k];
  if (MEMORY_FEATS.includes(id)) return ["memory", null];
  for (const [k, r] of Object.entries(HEART_PARTS)) if (r.feats.includes(id)) return ["heart", k];
  return ["heart", "coronaries"];
}

window.beingMount = async function (host, opts) {
  opts = opts || {};
  const api = opts.api;
  // phone: the Android app's Views → Being (0.8.10) passes opts.mode "phone"; static/being-phone.js then owns the touch,
  // the panel as a bottom sheet and the words drawn over the canvas. Every hook is marked "phone:"; with PH null (the
  // dashboard) each one does exactly what it did before.
  const PH = opts.mode === "phone" && window.beingPhone ? window.beingPhone : null, UI = PH ? PH.ui : null;
  // organ pages: the phone app's Views pages Brain, Heart, Senses, Memory (0.8.10) pass opts.only, the page's name; then
  // that one organ is drawn alone, framed, with nothing over it (the app lists its parts), and only(name) switches it.
  // Every change for them is behind OM; without opts.only the being is as it was. still: Remove animations is on.
  const PAGE_ORGAN = { brain: "mind", heart: "heart", senses: "senses", memory: "memory" };
  let ONLY = PAGE_ORGAN[opts.only] || null;
  const OM = !!ONLY, STILL = OM && !!opts.still;
  const THEME = opts.theme === "theme" && opts.pal ? "theme" : "void";
  const PAL = THEME === "theme" ? opts.pal : null;
  const P = THEME === "void"
    ? { bg: "#000000", ink: "#f2f2ef", mute: "#7a7a76", a: 0xffffff, flesh: 0xe9e4de, vein: 0xcfb2ad, nerve: 0xb8ab8c, back: 0x9aa3c4,
        // faint, organic tints: never saturated, the being stays a pale thing in the dark (the heart's muscle a little
        // fainter since 0.8.11); what flows is tinted: the blood arterial red, the fluid round the brain a pale clear aqua
        cortex: 0xe3c1b8, sulci: 0xb498b9, cereb: 0xdfbcae, stem: 0xe2cfbb, thal: 0xdcb49c, hippo: 0xc7a9c9, caudate: 0xd9c19a,
        callosum: 0xeee5d4, muscle: 0xc88a80, fat: 0xe2c793, artery: 0xd58378, iris: [.62, .5, .34], coch: 0xe2bdb6,
        coil: 0xd2a17c, canal: 0xe6dac4, tip: 0xe0d29a, fog: 0xb0d9e6, blood: 0xe0483a }
    : { bg: PAL.bg, ink: PAL.fg, mute: PAL.dim || PAL.mute || "#8d9a84", a: new THREE.Color(PAL.fg).getHex(), flesh: new THREE.Color(PAL.fg).getHex(), vein: new THREE.Color(PAL.rose || PAL.bad || "#d0706a").getHex(), nerve: new THREE.Color(PAL.accent || "#9ccf5e").getHex(),
        blood: new THREE.Color(PAL.bad || PAL.rose || "#d0706a").getHex(), muscle: new THREE.Color(PAL.fg).lerp(new THREE.Color(PAL.bg), .15).getHex() };
  // a light page: light added to it (additive blending) would vanish, so what glows is laid over it instead
  const LIGHT = new THREE.Color(P.bg).getHSL({}).l > .5, BL = LIGHT ? THREE.NormalBlending : THREE.AdditiveBlending;
  const hoodCols = HOOD_COLS.map((h) => { const c = new THREE.Color(h); if (PAL && PAL.accent) c.lerp(new THREE.Color(PAL.accent), .15); if (LIGHT) c.offsetHSL(0, .05, -.2); return c; });

  /* --- the page: the 3D canvas, a 2D layer for labels and the voice, a panel for what you click --- */
  host.innerHTML = "";
  host.classList.add("being");
  const css = document.createElement("style");
  css.textContent = `.being{position:relative;overflow:hidden;background:${P.bg};color:${P.ink};font:12px/1.45 Inter,"Segoe UI",system-ui,sans-serif}
  .being canvas{position:absolute;left:0;top:0;display:block}.being .ov{pointer-events:none}
  .being .bp{position:absolute;right:14px;top:50px;bottom:${opts.talkRoom || 150}px;width:340px;overflow:auto;background:${P.bg}e6;border:1px solid ${P.mute}66;border-radius:12px;padding:14px 16px;display:none;z-index:4}
  .being .bp h2{font-size:14px;font-weight:600;margin:0 0 2px}.being .bp .s{color:${P.mute};margin-bottom:10px}.being .bp h3{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:${P.mute};font-weight:600;margin:14px 0 6px}
  .being .bp .grow{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:5px 0;border-bottom:1px solid ${P.mute}26}
  .being .bp .grow span:first-child{color:${P.mute}}.being .bp input,.being .bp select,.being .bp textarea{background:transparent;color:${P.ink};border:1px solid ${P.mute}66;border-radius:6px;padding:3px 6px;font:inherit;max-width:160px}
  .being .bp textarea{width:100%;max-width:none;min-height:46px;font-family:ui-monospace,monospace;font-size:11px}
  .being .tg{width:34px;height:18px;border-radius:99px;background:${P.mute}55;position:relative;cursor:pointer;flex:none;border:0}.being .tg:after{content:"";position:absolute;left:2px;top:2px;width:14px;height:14px;border-radius:50%;background:${P.ink};transition:left .15s}
  .being .tg.on{background:${P.ink}55}.being .tg.on:after{left:18px}.being .bp .x{position:absolute;right:10px;top:8px;cursor:pointer;color:${P.mute};border:0;background:none;font-size:16px}
  .being .bp .gbars{font-family:ui-monospace,monospace;font-size:10.5px}.being .bp .gbar{display:flex;gap:6px;align-items:center;margin:0;padding:0;height:15px;line-height:15px}.being .bp .gbar>*{margin:0;padding:0;line-height:15px;font-size:10.5px}.being .bp .gbar i{display:block;height:7px!important;flex:1;background:${P.mute}33;border-radius:2px;overflow:hidden}
  .being .bp .gbar i b{display:block;height:100%;background:${P.ink}}.being .bp .gbar span{width:92px;text-align:right}.being .bp .gbar em{width:30px;color:${P.mute};font-style:normal}
  .being .bp details{border-bottom:1px solid ${P.mute}26;padding:4px 0}.being .bp summary{cursor:pointer;list-style:none;display:flex;justify-content:space-between;align-items:center}
  .being .bp pre{white-space:pre-wrap;font:11px/1.5 ui-monospace,monospace;color:${P.ink};max-height:52vh;overflow:auto}.being .bp button.b{background:transparent;color:${P.ink};border:1px solid ${P.mute}66;border-radius:99px;padding:4px 12px;cursor:pointer;font:inherit}
  .being .tip{position:absolute;z-index:5;pointer-events:none;background:${P.bg}e6;border:1px solid ${P.mute}55;border-radius:8px;padding:4px 8px;display:none;max-width:280px}
  .being .hints{right:118px!important}.being .bmode{position:absolute;left:50%;top:14px;transform:translateX(-50%);z-index:4;display:none;border:1px solid ${P.mute}88;border-radius:99px;overflow:hidden;background:${P.bg}cc}
  .being .bmode button{background:transparent;color:${P.mute};border:0;padding:5px 14px;font:500 11px Inter,sans-serif;cursor:pointer}.being .bmode button.on{background:${P.ink};color:${P.bg}}.being .mute{position:absolute;right:14px;top:14px;z-index:4;background:${P.bg};color:${P.ink};border:1px solid ${P.mute}88;border-radius:99px;padding:5px 14px;cursor:pointer;font:500 11px Inter,sans-serif}
  .being .mute.on{background:${P.ink};color:${P.bg}}`;
  if (PH) css.textContent += PH.css(P); // phone: the bottom sheet, bigger buttons
  host.appendChild(css);
  const gl = document.createElement("canvas"), ov = document.createElement("canvas");
  ov.className = "ov";
  const panel = document.createElement("div"); panel.className = "bp";
  const tip = document.createElement("div"); tip.className = "tip";
  const muteB = document.createElement("button"); muteB.className = "mute"; muteB.textContent = "● MUTE";
  const modeB = document.createElement("div"); modeB.className = "bmode"; modeB.innerHTML = ["solid", "cut", "xray"].map((m) => `<button data-mode="${m}">${{ solid: "Solid", cut: "Cutaway", xray: "X-ray" }[m]}</button>`).join("");
  const hintsB = document.createElement("button"); hintsB.className = "mute hints"; hintsB.title = "the hints on the being: what to click, what each part is (H; look.being_hints)";
  host.append(gl, ov, panel, tip, muteB, hintsB, modeB);
  if (OM) for (const el of [muteB, hintsB, modeB]) el.style.visibility = "hidden"; // the app has its own controls
  // the hints (look.being_hints, H): the lines under each name, how to turn it, the colours' key, the rings on features
  let HINTS = opts.hints !== false;
  function setHints(v, save) {
    HINTS = !!v; hintsB.textContent = HINTS ? "HINTS ON" : "HINTS OFF"; hintsB.classList.toggle("on", HINTS);
    if (save) api("settings", { key: "look.being_hints", value: HINTS }).catch(() => {});
  }
  hintsB.onclick = () => setHints(!HINTS, true);
  modeB.onclick = (e) => { const b = e.target.closest("[data-mode]"); if (b) setMode(b.dataset.mode); };
  function setMode(m) { mind.mode = m; for (const b of modeB.querySelectorAll("button")) b.classList.toggle("on", b.dataset.mode === m); }
  setHints(HINTS);
  let W = 2, H = 2, DPR = Math.min(window.devicePixelRatio || 1, PH ? PH.dpr : 1.5); // phone: its own cap
  const R = new THREE.WebGLRenderer({ canvas: gl, antialias: true });
  R.setClearColor(new THREE.Color(P.bg), 1); R.toneMapping = THREE.ACESFilmicToneMapping; R.localClippingEnabled = true;
  const scene = new THREE.Scene(), cam = new THREE.PerspectiveCamera(30, 1, .05, 80);
  const composer = new THREE.EffectComposer(R);
  composer.addPass(new THREE.RenderPass(scene, cam));
  const bloom = new THREE.UnrealBloomPass(new THREE.Vector2(256, 256), .7, .5, .5); composer.addPass(bloom);
  bloom.enabled = !LIGHT; // on a light page the page itself would bloom, and wash the being out to white
  // the phone's Memory page draws at the screen's own density (up to 3): its notes are fine points and threads that the
  // usual 1.5 cap blurred into blobs; the other organs keep the cap (heavier to draw)
  const FULL = Math.min(window.devicePixelRatio || 1, 3), GLR = () => (OM && ONLY === "memory" ? FULL : DPR);
  const size = () => {
    const r = host.getBoundingClientRect(); W = Math.max(2, r.width | 0); H = Math.max(2, r.height | 0);
    R.setPixelRatio(GLR()); R.setSize(W, H, false); composer.setPixelRatio(GLR()); composer.setSize(W, H); bloom.setSize(W / 2, H / 2);
    gl.style.width = W + "px"; gl.style.height = H + "px"; ov.width = W * DPR; ov.height = H * DPR; ov.style.width = W + "px"; ov.style.height = H + "px";
    cam.aspect = W / H; if (PH) cam.fov = PH.fov(W / H); cam.updateProjectionMatrix(); // phone: the dashboard's width of view
  };
  const ro = new ResizeObserver(size); ro.observe(host); size();

  /* --- the anatomy --- */
  const G = {};
  {
    const buf = await (await fetch("/static/body/anatomy.bin")).arrayBuffer(), dv = new DataView(buf), hl = dv.getUint32(4, true);
    const Hd = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 8, hl))), base = 8 + hl;
    for (const m of Hd.meshes) {
      let o = base + m.off; const q = new Int16Array(buf, o, m.verts * 3); o += m.verts * 6; const idx = new Uint32Array(buf.slice(o, o + m.tris * 12));
      const pos = new Float32Array(m.verts * 3); for (let i = 0; i < pos.length; i++) pos[i] = q[i] * m.scale;
      const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(pos, 3)); g.setIndex(new THREE.BufferAttribute(idx, 1)); g.computeVertexNormals(); G[m.name] = g;
    }
  }
  const VOL = await (async () => { const vb = await (await fetch("/static/body/cerebrum.vol")).arrayBuffer(), vh = new DataView(vb).getUint32(4, true); return { h: JSON.parse(new TextDecoder().decode(new Uint8Array(vb, 8, vh))), d: new Uint8Array(vb, 8 + vh) }; })();

  let seed = 11; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647, gauss = () => { let u = 0; for (let i = 0; i < 6; i++) u += rnd(); return u - 3; };
  const add = (o) => (scene.add(o), o), ticks = [];
  let DOT; const dot = () => { if (DOT) return DOT; const c = document.createElement("canvas"); c.width = c.height = 64; const g = c.getContext("2d"), r = g.createRadialGradient(32, 32, 0, 32, 32, 32); r.addColorStop(0, "#fff"); r.addColorStop(.2, "#ffff"); r.addColorStop(.45, "#fff6"); r.addColorStop(1, "#fff0"); g.fillStyle = r; g.fillRect(0, 0, 64, 64); return DOT = new THREE.CanvasTexture(c); };
  function flesh(col, o) {
    o = o || {};
    const m = new THREE.ShaderMaterial({
      defines: o.solid ? { SOLID: "" } : {},
      uniforms: { c: { value: new THREE.Color(col) }, c2: { value: new THREE.Color(o.col2 ?? col) }, t: { value: 0 }, k: { value: 0 }, op: { value: o.op ?? 1 }, va: { value: 0 }, vv: { value: 0 }, ao: { value: 0 }, hl: { value: 0 }, dm: { value: 1 }, fp: { value: V(0, 0, 0) }, fr: { value: .25 }, fk: { value: 0 }, fc: { value: new THREE.Color(0xffffff) }, gh: { value: 0 } },
      transparent: !!o.op, depthWrite: !o.op, clipping: true, side: THREE.DoubleSide,
      vertexShader: `#include <clipping_planes_pars_vertex>
      uniform float va,vv,ao;${o.deform || "vec3 deform(vec3 p){return p;}"}
      varying vec3 n;varying vec3 v;varying vec3 w;void main(){w=position;vec3 q=deform(position);vec4 mvPosition=modelViewMatrix*vec4(q,1.);n=normalize(normalMatrix*normal);v=-mvPosition.xyz;gl_Position=projectionMatrix*mvPosition;
      #include <clipping_planes_vertex>
      }`,
      fragmentShader: `#include <clipping_planes_pars_fragment>
      uniform vec3 c,c2,fp,fc;uniform float t,k,op,hl,dm,fr,fk,gh;varying vec3 n;varying vec3 v;varying vec3 w;${NOISE}
      void main(){
      #include <clipping_planes_fragment>
      vec3 N=normalize(n);if(!gl_FrontFacing)N=-N;vec3 Vv=normalize(v);vec3 L=normalize(vec3(.4,.8,.6));float ndl=max(0.,dot(N,L));float f=pow(1.-max(0.,dot(N,Vv)),2.2);
      float vein=0.;vec3 q=w*9.;for(int i=0;i<3;i++){vein+=abs(n3(q)-.5);q*=2.1;}vein=smoothstep(.36,.0,vein);float mot=fbm(w*14.)*.25;
      float sc=${(o.scale || 1).toFixed(2)};float e1=abs(fract(dot(w*sc,vec3(.31,.94,.12))*150.+fbm(w*sc*4.)*2.)-.5),e2=abs(fract(dot(w*sc,vec3(-.62,.33,.71))*120.)-.5);
      float etch=smoothstep(.07,.0,e1)*clamp(.85-ndl,0.,1.)+smoothstep(.06,.0,e2)*clamp(.45-ndl,0.,1.);float cont=smoothstep(.035,.0,abs(fract(w.y*sc*34.+fbm(w*sc*2.5)*2.)-.5));
      ${o.fibre ? "float fib=smoothstep(.12,.0,abs(fract((w.y*1.3+atan(w.z,w.x)*.22+fbm(w*3.)*.4)*55.)-.5));" : "float fib=0.;"}
      vec3 cc=mix(c,c2,smoothstep(.3,.78,fbm(w*${(o.mottle || 6).toFixed(1)}+3.1))); // a second tint, mottled like living tissue
      vec3 base=cc*(.07+.30*ndl+mot*.6);vec3 col=base*(1.-.35*vein)*(1.-.55*etch)*(1.-.3*fib)+cc*vein*.25*(1.+2.*k)+cc*cont*.07+cc*f*(.45+.8*hl)+pow(max(0.,dot(reflect(-L,N),Vv)),40.)*.18;
      float inS=fr<=0.?0.:fr>8.?1.:smoothstep(fr,fr*.3,distance(w,fp));float foc=mix(1.,mix(.4,1.16,inS),fk);
      vec3 sel=fc*fk*inS*(.08+.42*f)*(.85+.15*sin(t*2.6));vec3 outc=col*dm*foc+sel*dm;
      #ifdef SOLID
      if(inS<.5||gh<.01)discard;gl_FragColor=vec4(outc,1.);
      #else
      float a=op;if(gh>.001){float inside=step(.5,inS)*${o.twin ? "1." : "0."};a=mix(op,(1.-inside)*(.02+.16*f),gh);if(a<.004)discard;outc=mix(outc,c*(.18+.45*f),gh*(1.-step(.5,inS)));}
      gl_FragColor=vec4(outc,a);
      #endif
      }`,
    });
    m.userData.o = { ...o, col }; GHOSTS.push(m); return m;
  }
  // every flesh material: while it's a ghost it's drawn as glass (transparent, no depth), else as it was
  const GHOSTS = [];
  // a mesh whose selected part stays solid while the rest of it is glass: its twin draws that part (same uniforms)
  function twin(mesh) {
    const o = mesh.material.userData.o, tm = flesh(o.col, { ...o, solid: true });
    tm.uniforms = mesh.material.uniforms; tm.clippingPlanes = mesh.material.clippingPlanes;
    const t2 = new THREE.Mesh(mesh.geometry, tm); t2.position.copy(mesh.position); t2.visible = false; mesh.parent.add(t2); mesh.userData.twin = t2; return t2;
  }

  /* --- the heartbeat: its rate follows how busy Kurooto has been in the last ten minutes --- */
  const recent = [];
  let phase = 0, BPM = 56;
  /* --- Brain's status (0.8.14): what the glance and the mood in the drawing read; neutral until a status comes --- */
  const ST = { on: false, focus: false, asleep: false, held: 0, uneasy: null, item: null, mood: "mid", arousal: 0, knobs: {}, look: { status: true, mood: true }, moodK: 1, fogK: 1, warm: 0, dil: 0 };
  const glance = () => ST.on && ST.look.status !== false, moodOn = () => ST.on && ST.look.mood !== false;
  const shutEyes = () => glance() && (ST.focus || ST.asleep);
  const WARM = new THREE.Color(0xf0dcb4);
  const beat = (ph) => { const u = ((ph % 1) + 1) % 1; return Math.exp(-(((u - .06) / .035) ** 2)) * .45 + Math.exp(-(((u - .2) / .045) ** 2)); };
  const cycle = (ph) => { const u = ((ph % 1) + 1) % 1, sm = (a, b, x) => { const k = Math.min(1, Math.max(0, (x - a) / (b - a))); return k * k * (3 - 2 * k); }; return { va: Math.exp(-(((u - .06) / .04) ** 2)), vv: sm(.12, .2, u) * (1 - sm(.34, .5, u)), ao: sm(.15, .24, u) * (1 - sm(.36, .6, u)) }; };
  const PATHS = {}, SPEED = 3.6;

  /* ===================== the mind ===================== */
  const BRAIN_C = V(0, 1.35, 0), BS = 1.1, OFF = V(0, .12, .05), FIB = [];
  const inside = (x, y, z) => { const a = (Math.abs(x) - .30) / .29, b = (y - .10) / .40, c = (z + .04) / .78; return a * a + b * b + c * c < 1 && y > -.30; };
  function tracts(n) {
    const pos = [], col = [];
    const field = (px, py, pz) => { const mid = Math.exp(-((px / .16) ** 2)) * (py > -.02 && py < .32 ? 1 : 0), proj = Math.exp(-(((Math.abs(px) - .18) / .12) ** 2)) * (Math.abs(pz + .05) < .35 ? 1 : .2); return [mid * 2.4 * Math.sign(px || 1) + .45 * Math.sin(py * 5.1 + pz * 3.3), proj * 1.8 + .35 * Math.sin(pz * 4.7 + px * 6.1), 1.1 * (1 - mid) * (1 - proj * .7) + .45 * Math.cos(px * 5.3 + py * 4.1)]; };
    for (let k = 0; k < n; k++) {
      const x = (rnd() - .5) * 1.2, y = (rnd() - .4) * .8, z = (rnd() - .5) * 1.6; if (!inside(x, y, z)) { k--; continue; }
      const line = [];
      for (const sgn of [1, -1]) {
        let px = x, py = y, pz = z, dir = null; const len = 30 + ((rnd() * 45) | 0), seg = [];
        for (let i = 0; i < len; i++) {
          let [vx, vy, vz] = field(px, py, pz); vx *= sgn; vy *= sgn; vz *= sgn; const L = Math.hypot(vx, vy, vz) || 1; let dx = vx / L, dy = vy / L, dz = vz / L;
          if (dir && dx * dir[0] + dy * dir[1] + dz * dir[2] < 0) { dx = -dx; dy = -dy; dz = -dz; } dir = [dx, dy, dz];
          const nx = px + dx * .014, ny = py + dy * .014, nz = pz + dz * .014; if (!inside(nx, ny, nz)) break; seg.push([nx, ny, nz]);
          // the fibres coloured by their direction, as tract maps are (left-right red, front-back green, up-down blue),
          // softened towards white by w
          const f = (Math.sin(Math.PI * Math.min(1, i / len)) * .85 + .15) * .8, w = .3;
          const r = f * (w + (1 - w) * Math.abs(dx)), gg = f * (w + (1 - w) * Math.abs(dz)), bb = f * (w + (1 - w) * Math.abs(dy));
          pos.push(px, py, pz, nx, ny, nz); col.push(r, gg, bb, r, gg, bb); px = nx; py = ny; pz = nz;
        }
        if (sgn === 1) line.push(...seg.reverse()); else line.push([x, y, z], ...seg);
      }
      if (line.length > 12) FIB.push(line);
    }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
    return new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: P.a, vertexColors: true, transparent: true, opacity: .09, blending: THREE.AdditiveBlending, depthWrite: false }));
  }
  const mind = { g: new THREE.Group(), b: new THREE.Group(), cut: 0 };
  {
    const M = mind.g, B = mind.b; M.position.copy(BRAIN_C); add(M); B.scale.setScalar(BS); M.add(B);
    const below = new THREE.Plane(V(0, -1, 0), 0), above = new THREE.Plane(V(0, 1, 0), 0);
    const cortex = new THREE.Mesh(G.grey, flesh(P.cortex ?? P.flesh, { twin: 1, col2: P.sulci, mottle: 9 })); cortex.material.clippingPlanes = [below]; cortex.position.copy(OFF); B.add(cortex); mind.cortex = cortex; twin(cortex);
    mind.mats = [cortex.material]; mind.part = { grey: cortex };
    for (const nm of ["cerebellum", "brainstem"]) { const m = new THREE.Mesh(G[nm], flesh((nm === "cerebellum" ? P.cereb : P.stem) ?? P.flesh, { col2: P.sulci, mottle: 7 })); m.position.copy(OFF); B.add(m); mind.mats.push(m.material); mind.part[nm] = m; }
    // the deep structures (in the anatomy file all along): seen in X-ray, through a selection, or below the cut
    mind.deep = [];
    for (const nm of ["thalamus", "hippocampus", "caudate", "callosum"]) { if (!G[nm]) continue; const tint = { thalamus: P.thal, hippocampus: P.hippo, caudate: P.caudate, callosum: P.callosum }[nm]; const m = new THREE.Mesh(G[nm], flesh(tint ?? new THREE.Color(P.flesh).multiplyScalar(.92).getHex())); m.position.copy(OFF); B.add(m); mind.mats.push(m.material); mind.part[nm] = m; mind.deep.push(m); }
    mind.mode = "solid"; mind.cutK = 0;
    const [nx, ny, nz] = VOL.h.shape, tex = new THREE.DataTexture3D(VOL.d, nx, ny, nz); tex.format = THREE.RedFormat; tex.minFilter = tex.magFilter = THREE.LinearFilter; tex.unpackAlignment = 1; tex.needsUpdate = true;
    const capM = new THREE.ShaderMaterial({
      uniforms: { vol: { value: tex }, lo: { value: V(...VOL.h.lo) }, size: { value: V(nx * VOL.h.step, ny * VOL.h.step, nz * VOL.h.step) }, range: { value: VOL.h.range }, wm: { value: VOL.h.white }, y: { value: .2 } }, side: THREE.DoubleSide,
      vertexShader: `varying vec3 p;void main(){p=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
      fragmentShader: `precision highp sampler3D;uniform sampler3D vol;uniform vec3 lo,size;uniform float range,wm,y;varying vec3 p;${NOISE}
      float D(vec3 q){vec3 u=(q-lo)/size;if(any(lessThan(u,vec3(0.)))||any(greaterThan(u,vec3(1.))))return 1.;return (texture(vol,u).r*255.-128.)/127.5*range;}
      void main(){vec3 q=vec3(p.x,y,-p.y);float d=D(q);if(d>0.)discard;float g=fbm(q*60.)*.12;vec3 grey=vec3(.50,.47,.47)+g,white=vec3(.88,.86,.82)+g*.4;float inG=smoothstep(-wm-.004,-wm+.004,d);vec3 col=mix(white,grey,inG);
      col*=1.-.4*smoothstep(.006,0.,-d);col+=vec3(1.)*smoothstep(.004,0.,abs(d+wm))*.18;gl_FragColor=vec4(col*.42,1.);}`,
    });
    const cap = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 2.0), capM); cap.rotation.x = -Math.PI / 2; B.add(cap);
    const lid = new THREE.Group(); B.add(lid); const tr = tracts(1500); tr.position.copy(OFF); tr.material.clippingPlanes = [above]; lid.add(tr);
    const fogs = [], FOG = new THREE.Color(P.fog ?? P.a); // its tint (until 0.8.11 each frame set it grey)
    for (let i = 0; i < 4; i++) {
      const m = new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, uniforms: { t: { value: 0 }, s: { value: i }, c: { value: new THREE.Color(P.fog ?? P.a) }, k: { value: 0 } },
        vertexShader: `varying vec3 w;varying vec3 n;varying vec3 v;void main(){w=position;vec4 m=modelViewMatrix*vec4(position,1.);n=normalize(normalMatrix*normal);v=-m.xyz;gl_Position=projectionMatrix*m;}`,
        fragmentShader: `uniform float t,s,k;uniform vec3 c;varying vec3 w;varying vec3 n;varying vec3 v;${NOISE}void main(){float f=pow(1.-abs(dot(normalize(n),normalize(v))),1.4);float d=fbm(w*3.+vec3(0.,t*.05,t*.03)+s*7.);gl_FragColor=vec4(c,smoothstep(.45,.85,d)*(.035+.045*f)*(1.+.8*k));}` });
      const fm = new THREE.Mesh(G.grey, m); fm.position.copy(OFF); fm.scale.setScalar(1.06 + i * .07); B.add(fm); fogs.push(m);
    }
    // sparks: a real event lights its process's region, in its colour. They run on fibres inside the brain, so until
    // 0.8.11 the solid cortex hid every one (depth test) and the few seen in X-ray were added onto pale tissue, white:
    // now they're drawn through the cortex, laid over it in their own colour, the ones behind the middle fainter
    const NF = 220, fp = new Float32Array(NF * 3), fa = new Float32Array(NF), fc = new Float32Array(NF * 3), fg = new THREE.BufferGeometry();
    fg.setAttribute("position", new THREE.BufferAttribute(fp, 3)); fg.setAttribute("a", new THREE.BufferAttribute(fa, 1)); fg.setAttribute("col", new THREE.BufferAttribute(fc, 3));
    const fire = new THREE.Points(fg, new THREE.ShaderMaterial({ transparent: true, depthWrite: false, depthTest: false, blending: THREE.NormalBlending, uniforms: { map: { value: dot() }, cz: { value: 0 } },
      vertexShader: `uniform float cz;attribute float a;attribute vec3 col;varying float va;varying vec3 vc;varying float fd;void main(){va=a;vc=col;vec4 m=modelViewMatrix*vec4(position,1.);fd=1.-.6*smoothstep(-.25,.5,cz-m.z);gl_PointSize=(2.5+12.*a)*(6./-m.z)*${DPR.toFixed(2)};gl_Position=projectionMatrix*m;}`,
      fragmentShader: `uniform sampler2D map;varying float va;varying vec3 vc;varying float fd;void main(){float t=texture2D(map,gl_PointCoord).r;if(t<.01)discard;vec3 c=mix(vec3(dot(vc,vec3(.3,.59,.11))),vc,1.7);gl_FragColor=vec4(clamp(c,0.,1.)*(.7+.35*t),t*va*fd);}` }));
    fire.position.copy(OFF); fire.renderOrder = 3; B.add(fire);
    const near = {};
    for (const k in PROC) { const a = PROC[k].at; near[k] = FIB.map((f) => [f, Math.min(...f.filter((_, j) => j % 6 === 0).map((p) => Math.hypot(p[0] - a[0], p[1] - a[1], p[2] - a[2])))]).sort((x, y) => x[1] - y[1]).slice(0, 60).map((x) => x[0]); }
    mind.sparks = []; mind.fire = (k, t, n) => { for (let i = 0; i < n; i++) { const f = near[k][(rnd() * near[k].length) | 0]; mind.sparks.push({ f, t0: t + rnd() * .25, dur: .5 + rnd() * .6, c: new THREE.Color(PROC[k].c) }); } };
    ticks.push((t) => {
      let n = 0;
      for (let i = mind.sparks.length - 1; i >= 0; i--) { const s = mind.sparks[i], u = (t - s.t0) / s.dur; if (u > 1) { mind.sparks.splice(i, 1); continue; } if (u < 0 || n >= NF) continue; fp.set(s.f[Math.min(s.f.length - 1, (u * s.f.length) | 0)], n * 3); fc[n * 3] = s.c.r; fc[n * 3 + 1] = s.c.g; fc[n * 3 + 2] = s.c.b; fa[n] = Math.sin(Math.PI * u); n++; }
      for (let i = n; i < NF; i++) fa[i] = 0; fg.attributes.position.needsUpdate = fg.attributes.a.needsUpdate = fg.attributes.col.needsUpdate = true;
      fire.material.uniforms.cz.value = M.getWorldPosition(V(0, 0, 0)).applyMatrix4(cam.matrixWorldInverse).z; // the brain's middle, seen from here
      const k = Math.min(1, mind.sparks.length / 70), FM = FOG.clone().lerp(WARM, ST.warm).multiplyScalar(ST.fogK); for (const f of fogs) { f.uniforms.t.value = t; f.uniforms.k.value = k; f.uniforms.c.value.copy(FM).multiplyScalar((1 - .75 * cortex.material.uniforms.gh.value) * (1 - .55 * (OPEN.mind || 0))); } cortex.material.uniforms.t.value = t;
      mind.cutK += ((FOCUS === "mind" && mind.mode === "cut" ? 1 : 0) - mind.cutK) * .1; const om = mind.cutK, cy = om > .03 ? .22 - om * .12 : 9; cap.visible = om > .03; capM.uniforms.y.value = cy; cap.position.y = cy + OFF.y; lid.position.y = om * .55;
      B.updateMatrixWorld(true); const wp = V(0, cy + OFF.y, 0).applyMatrix4(B.matrixWorld), wn = V(0, 1, 0).transformDirection(B.matrixWorld);
      below.setFromNormalAndCoplanarPoint(wn.clone().negate(), wp);
      const glass = Math.max(cortex.material.uniforms.gh.value, 0); // X-ray or a selection: the fibres show through the glass
      above.setFromNormalAndCoplanarPoint(wn, V(0, glass > .3 && om < .03 ? -9 : cy + OFF.y + lid.position.y, 0).applyMatrix4(B.matrixWorld));
      cortex.material.uniforms.hl.value = HOVER === "mind" ? .6 : 0;
    });
  }

  /* ===================== the heart ===================== */
  const HEART_C = V(0, -.62, .25);
  const HEART_DEF = `vec3 deform(vec3 p){float A=.55;float xr=p.x*cos(A)-p.y*sin(A),yr=p.x*sin(A)+p.y*cos(A);
  float ven=smoothstep(.2,.02,yr),atr=smoothstep(.06,.2,yr)*smoothstep(.6,.42,yr),gv=smoothstep(.45,.62,yr);
  float tw=.24*vv*ven*(.2-yr),cs=cos(tw),sn=sin(tw);float x2=xr*cs-p.z*sn,z2=xr*sn+p.z*cs;float sq=1.-.12*vv*ven-.09*va*atr+.06*ao*gv;x2*=sq;z2*=sq;
  float y2=yr+(.18-yr)*.08*vv*ven;return vec3(x2*cos(A)+y2*sin(A),-x2*sin(A)+y2*cos(A),z2);}`;
  const hp = (xr, yr, z) => { const A = .55; return V(xr * Math.cos(A) + yr * Math.sin(A), -xr * Math.sin(A) + yr * Math.cos(A), z); };
  const heart = { g: new THREE.Group() };
  {
    const g = heart.g; g.position.copy(HEART_C); g.scale.setScalar(.62); g.rotation.z = -.3; add(g);
    const mat = flesh(P.muscle ?? P.flesh, { deform: HEART_DEF, fibre: 1, scale: 1.4, twin: 1, col2: P.fat, mottle: 4 }); const hm = new THREE.Mesh(G.heart, mat); g.add(hm); heart.mesh = hm; twin(hm);
    const pa = G.heart.attributes.position.array, na = G.heart.attributes.normal.array, nv = pa.length / 3;
    const snap = (pts) => pts.map((T3) => { let b = 0, bd = 1e9; for (let i = 0; i < nv; i += 2) { const dx = pa[i * 3] - T3.x, dy = pa[i * 3 + 1] - T3.y, dz = pa[i * 3 + 2] - T3.z, d = dx * dx + dy * dy + dz * dz; if (d < bd) { bd = d; b = i; } } return V(pa[b * 3] + na[b * 3] * .012, pa[b * 3 + 1] + na[b * 3 + 1] * .012, pa[b * 3 + 2] + na[b * 3 + 2] * .012); });
    const cmat = flesh(P.artery ?? P.vein, { deform: HEART_DEF, scale: 2, col2: P.fat, mottle: 12 }), LAD = [], CX = [], RCA = [], paths = [];
    for (let i = 0; i <= 26; i++) { const u = i / 26; LAD.push(hp(-.04 - .05 * u, .2 - .85 * u, .6)); }
    for (let i = 0; i <= 22; i++) { const a = Math.PI / 2 - i / 22 * 2.2; CX.push(hp(.5 * Math.cos(a), .13, .5 * Math.sin(a))); }
    for (let i = 0; i <= 22; i++) { const a = Math.PI / 2 + i / 22 * 2.3; RCA.push(hp(.5 * Math.cos(a), .12, .5 * Math.sin(a))); }
    paths.push([LAD, .022], [CX, .018], [RCA, .018]);
    for (let k = 0; k < 7; k++) { const s = LAD[4 + k * 3], d = k % 2 ? 1 : -1, br = []; for (let i = 0; i < 8; i++) br.push(s.clone().add(hp(d * .05 * i, -.04 * i, .15))); paths.push([br, .009]); }
    for (let k = 0; k < 5; k++) { const s = (k % 2 ? CX : RCA)[5 + k * 3], br = []; for (let i = 0; i < 8; i++) br.push(s.clone().add(hp((k % 2 ? 1 : -1) * .01 * i, -.07 * i, 0))); paths.push([br, .009]); }
    for (const [pts, r] of paths) { const sp = snap(pts); g.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(sp), sp.length * 6, r, 6, false), cmat)); }
    heart.mats = [mat, cmat];
    ticks.push((t) => { const { va, vv, ao } = cycle(phase), mk = ST.moodK; for (const m of [mat, cmat]) { m.uniforms.va.value = va * mk; m.uniforms.vv.value = vv * mk; m.uniforms.ao.value = ao; m.uniforms.t.value = t; m.uniforms.k.value = vv; } mat.uniforms.hl.value = HOVER === "heart" ? .6 : 0; });
  }

  /* ===================== vessels, nerves, blood ===================== */
  const FLOW = [], LINKS = []; // LINKS: the vessels, nerves and blood between the organs (hidden on an organ page)
  // What a vessel or nerve is joined to: a point on an organ (in its own frame), followed as the organ turns by itself
  // or is dragged. Each tube is built once; every frame only its two ends' offsets (d) change and its shader bends the
  // last stretch to them (bendAt does the same for what travels on it), so nothing comes apart and no geometry is remade.
  const ENDS = [];
  function end(obj, p, local) { obj.updateWorldMatrix(true, false); const l = local ? p.clone() : obj.worldToLocal(p.clone()), e = { obj, l, w: l.clone().applyMatrix4(obj.matrixWorld), d: V(0, 0, 0) }; ENDS.push(e); return e; }
  ticks.push(() => { for (const e of ENDS) { e.obj.updateWorldMatrix(true, false); e.d.copy(e.l).applyMatrix4(e.obj.matrixWorld).sub(e.w); } });
  // s: how far along the tube; each end's offset fades out over rc from that end (by length, so tubes that share a
  // stretch, the nerves' trunk, bend the same)
  const BEND = `uniform vec3 d0,d1;uniform float len,rc;vec3 bend(vec3 p,float s){return p+d0*(1.-smoothstep(0.,rc,s))+d1*(1.-smoothstep(0.,rc,len-s));}`;
  const joined = (cu, a, b) => { const len = cu.getLength(); cu.userData = { a, b, len, rc: Math.min(1.4, len * .5) }; return len; };
  const fall = (x, rc) => { const v = Math.min(1, Math.max(0, x / rc)); return 1 - v * v * (3 - 2 * v); };
  const bendAt = (cu, u, p) => { const j = cu.userData; if (!j || !j.a) return p; const s = u * j.len; return p.addScaledVector(j.a.d, fall(s, j.rc)).addScaledVector(j.b.d, fall(j.len - s, j.rc)); };
  function vessel(name, ea, eb, nStr, bend, width) {
    const a = ea.w.clone(), to = eb.w.clone(), mid = a.clone().lerp(to, .5).add(V(gauss() * bend, gauss() * bend * .6 + .2, gauss() * bend * .4));
    const cu = new THREE.CatmullRomCurve3([a, a.clone().lerp(mid, .45).add(V(0, 0, .2)), mid, mid.clone().lerp(to, .6).add(V(0, 0, -.1)), to]); const len = joined(cu, ea, eb); PATHS[name] = { cu, len };
    const mats = [];
    for (let s = 0; s < nStr; s++) {
      const off = V(gauss(), gauss(), gauss()).multiplyScalar(width); const pts = cu.getPoints(100).map((p, i) => p.clone().add(off.clone().multiplyScalar(Math.sin(i / 100 * Math.PI))));
      const geo = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 100, s === 0 ? .012 : .005, 6, false), u = new Float32Array(geo.attributes.position.count); for (let i = 0; i < u.length; i++) u[i] = Math.floor(i / 7) / 100; geo.setAttribute("u", new THREE.BufferAttribute(u, 1));
      // the blood is tinted (0.8.11): arterial red in the main vessel, a little paler in the small ones
      const m = new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: BL, uniforms: { ph: { value: 0 }, len: { value: len }, bpm: { value: 60 }, fade: { value: 1 }, c: { value: new THREE.Color(P.blood ?? P.vein).lerp(new THREE.Color(P.vein), s === 0 ? 0 : .35) }, d0: { value: ea.d }, d1: { value: eb.d }, rc: { value: cu.userData.rc } },
        vertexShader: `attribute float u;varying float vu;${BEND}void main(){vu=u;gl_Position=projectionMatrix*modelViewMatrix*vec4(bend(position,u*len),1.);}`,
        fragmentShader: `uniform float ph,len,bpm,fade;uniform vec3 c;varying float vu;void main(){float u=fract(ph-vu*len/${SPEED.toFixed(1)}*bpm/60.);float p=exp(-pow((u-.18)/.05,2.))+.5*exp(-pow((u-.05)/.035,2.));gl_FragColor=vec4(c,(.13+p*.75)*fade);}` });
      LINKS.push(add(new THREE.Mesh(geo, m))); mats.push(m);
    }
    ticks.push(() => { const f = 1 - .88 * Math.max(0, ...Object.values(OPEN)); for (const m of mats) { m.uniforms.ph.value = phase; m.uniforms.bpm.value = BPM; m.uniforms.fade.value = f; } }); // faded while you look into an organ
    return cu;
  }
  // The nerves (0.8.11): the spinal cord leaves the brainstem's lower end, runs down behind the heart to a plexus and
  // splits into three nerves, to the heart, the senses and memory, each a bundle of fibres (myelin, with the gaps
  // between its sheaths) with nerve cells along it. A signal on a nerve (FLOW on NERVES) lights its own fibres and
  // cells in the event's colour as it passes; nothing else moves on them.
  const NERVES = {}, NS = 200;
  const NSIG = `uniform vec3 c;uniform float fade;uniform vec4 sg[4];uniform vec3 sc[4];
  vec3 lit(vec3 col,float s,out float g){g=0.;for(int i=0;i<4;i++){float k=sg[i].y*exp(-pow((s-sg[i].x)/.16,2.));col=mix(col,clamp(mix(vec3(dot(sc[i],vec3(.3,.59,.11))),sc[i],1.6)*1.2,0.,1.),min(1.,k));g+=k;}return col;}`;
  function nerve(name, ea, eb, via) { // via: from the organ to the brainstem, the plexus second to last
    const pts = [ea.w.clone(), ...via, eb.w.clone()], cu = new THREE.CatmullRomCurve3(pts, false, "centripetal"), len = joined(cu, ea, eb); NERVES[name] = cu;
    const C = cu.getSpacedPoints(NS), up = V(0, 0, 1), fr = C.map((p, i) => { const T = cu.getTangentAt(i / NS), N = T.clone().cross(up).normalize(), Bn = T.clone().cross(N); return [N, Bn]; });
    let ip = 0, bd = 9; C.forEach((p, i) => { const d = p.distanceTo(via[via.length - 2]); if (d < bd) { bd = d; ip = i; } }); // the plexus
    const pos = [], sa = [], idx = [];
    for (let f = 0; f < 7; f++) {
      const ph0 = rnd() * 6.283, rf = .55 + .45 * rnd(), fp = C.map((p, i) => { const s = i / NS * len, r = (.018 + .03 * Math.exp(-s / .2)) * (i > ip ? .65 : 1) * rf, a = ph0 + s * 3; return p.clone().addScaledVector(fr[i][0], Math.cos(a) * r).addScaledVector(fr[i][1], Math.sin(a) * r); });
      const g = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(fp), NS, f === 0 ? .0045 : .003, 4, false), gp = g.attributes.position.array, base = pos.length / 3;
      for (let i = 0; i < gp.length; i++) pos.push(gp[i]); for (let v = 0; v < gp.length / 3; v++) sa.push(Math.floor(v / 5) / NS * len); for (const x of g.index.array) idx.push(base + x); g.dispose();
    }
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); geo.setAttribute("s", new THREE.Float32BufferAttribute(sa, 1)); geo.setIndex(idx);
    const U = { c: { value: new THREE.Color(P.nerve) }, fade: { value: 1 }, len: { value: len }, rc: { value: cu.userData.rc }, d0: { value: ea.d }, d1: { value: eb.d }, map: { value: dot() },
      sg: { value: [0, 1, 2, 3].map(() => new THREE.Vector4()) }, sc: { value: [0, 1, 2, 3].map(() => V(0, 0, 0)) } };
    const fib = new THREE.Mesh(geo, new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: BL, uniforms: U,
      vertexShader: `attribute float s;varying float vs;${BEND}void main(){vs=s;gl_Position=projectionMatrix*modelViewMatrix*vec4(bend(position,s),1.);}`,
      fragmentShader: `${NSIG}varying float vs;void main(){float nd=smoothstep(0.,.07,abs(fract(vs*16.)-.5)),g;vec3 col=lit(c*(.6+.4*nd),vs,g);gl_FragColor=vec4(col,min(1.,.2*(.6+.4*nd)+g*.7)*fade);}` }));
    // the cells: at the organ's end, along the nerve, a ganglion at the plexus, and the nuclei by the brainstem
    const cs = [], ca = [], cz = [], put = (i, r) => { const p = C[i].clone().add(V(gauss(), gauss(), gauss()).multiplyScalar(r)); cs.push(p.x, p.y, p.z); ca.push(i / NS * len); cz.push(rnd()); };
    for (let k = 0; k < 3; k++) put(2 + ((rnd() * 10) | 0), .02);
    for (let k = 0; k < 4; k++) put(Math.round(ip * (.2 + .6 * (k + rnd()) / 4)), .012);
    for (let k = 0; k < 4; k++) put(Math.max(0, Math.min(NS, ip + ((gauss() * 4) | 0))), .022);
    for (let k = 0; k < 2; k++) put(NS - 2 - ((rnd() * 6) | 0), .01);
    const sg = new THREE.BufferGeometry(); sg.setAttribute("position", new THREE.Float32BufferAttribute(cs, 3)); sg.setAttribute("s", new THREE.Float32BufferAttribute(ca, 1)); sg.setAttribute("z", new THREE.Float32BufferAttribute(cz, 1));
    fib.add(new THREE.Points(sg, new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: BL, uniforms: U,
      vertexShader: `attribute float s;attribute float z;varying float vs;${BEND}void main(){vs=s;vec4 m=modelViewMatrix*vec4(bend(position,s),1.);gl_PointSize=(2.2+2.*z)*(6./-m.z)*${DPR.toFixed(2)};gl_Position=projectionMatrix*m;}`,
      fragmentShader: `uniform sampler2D map;${NSIG}varying float vs;void main(){float t=texture2D(map,gl_PointCoord).r,g;if(t<.02)discard;vec3 col=lit(mix(c,vec3(1.),.15),vs,g);gl_FragColor=vec4(col,t*min(1.,.5+g)*fade);}` })));
    LINKS.push(add(fib)); // (the cells are its child: hidden with it on an organ page)
    ticks.push((t) => {
      U.fade.value = 1 - .9 * Math.max(0, ...Object.values(OPEN)); let n = 0;
      for (const [fc, t0, dur, col, rev] of FLOW) { if (fc !== cu || n >= 4) continue; const u = (t - t0) / dur; if (u < 0 || u > 1) continue; U.sg.value[n].set((rev ? 1 - u : u) * len, Math.sin(Math.PI * u) * .9 + .1, 0, 0); U.sc.value[n].set(col.r, col.g, col.b); n++; }
      for (; n < 4; n++) U.sg.value[n].y = 0;
    });
  }
  const CN = 300, cp = new Float32Array(CN * 3), cc = new Float32Array(CN * 3), ca = new Float32Array(CN), cellG = new THREE.BufferGeometry();
  cellG.setAttribute("position", new THREE.BufferAttribute(cp, 3)); cellG.setAttribute("col", new THREE.BufferAttribute(cc, 3)); cellG.setAttribute("a", new THREE.BufferAttribute(ca, 1));
  LINKS.push(add(new THREE.Points(cellG, new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: BL, uniforms: { map: { value: dot() } },
    vertexShader: `attribute float a;attribute vec3 col;varying float va;varying vec3 vc;void main(){va=a;vc=col;vec4 m=modelViewMatrix*vec4(position,1.);gl_PointSize=(3.+9.*a)*(6./-m.z)*${DPR.toFixed(2)};gl_Position=projectionMatrix*m;}`,
    fragmentShader: `uniform sampler2D map;varying float va;varying vec3 vc;void main(){gl_FragColor=vec4(vc,1.)*texture2D(map,gl_PointCoord)*va;}` }))));
  ticks.push((t) => {
    let n = 0;
    for (let i = FLOW.length - 1; i >= 0; i--) { const [cu, t0, dur, col, rev] = FLOW[i], u = (t - t0) / dur; if (u > 1) { FLOW.splice(i, 1); continue; } if (u < 0 || n >= CN) continue; const uu = rev ? 1 - u : u, p = bendAt(cu, uu, cu.getPointAt(uu)); cp.set([p.x, p.y, p.z], n * 3); cc.set([col.r, col.g, col.b], n * 3); ca[n] = Math.sin(Math.PI * u) * .9 + .1; n++; }
    for (let i = n; i < CN; i++) ca[i] = 0; cellG.attributes.position.needsUpdate = cellG.attributes.col.needsUpdate = cellG.attributes.a.needsUpdate = true;
  });

  /* ===================== the senses ===================== */
  const DEEP_OF = { thal: "thalamus", hippo: "hippocampus", cereb: "cerebellum" }; // regions that are a structure of their own
  const SENSE_C = V(-3.15, .15, -.3), senses = { g: new THREE.Group(), organs: {}, hit: {}, mats: {} };
  // where each organ sits in the senses (left to right under the eye: the coil, the cilia, the cochlea, the canals)
  const SPOS = { sight: [0, .85, 0], heat: [-1.02, -.42, .05], touch: [-.24, -.6, .25], hearing: [.62, -.42, .2], balance: [1.24, -.62, .1] };
  function eyeMat() {
    return new THREE.ShaderMaterial({ transparent: true, uniforms: { dil: { value: .32 }, dm: { value: 1 }, al: { value: 1 } },
      vertexShader: `varying vec3 n;varying vec3 lp;varying vec3 v;void main(){lp=position;vec4 m=modelViewMatrix*vec4(position,1.);n=normalize(normalMatrix*normal);v=-m.xyz;gl_Position=projectionMatrix*m;}`,
      fragmentShader: `uniform float dil,dm,al;varying vec3 n;varying vec3 lp;varying vec3 v;${NOISE}void main(){vec3 d=normalize(lp);float r=acos(clamp(d.z,-1.,1.))/.6;float a=atan(d.y,d.x);
      vec3 scl=vec3(.84,.80,.76)*(.8+.2*n3(d*6.));float vein=smoothstep(.9,1.,n3(vec3(a*6.,r*14.,1.))+n3(vec3(a*20.,r*30.,2.))*.4)*smoothstep(.9,2.4,r);scl=mix(scl,vec3(.45,.1,.12),vein*.75);
      float fib=.5+.5*sin(a*110.+n3(vec3(a*12.,r*20.,3.))*7.);vec3 iris=vec3(${(P.iris || [.62, .6, .56]).map((x) => x.toFixed(2)).join(",")})*(.35+.65*fib)*(1.-.5*smoothstep(.55,.85,n3(vec3(a*14.,r*9.,4.))));iris=mix(iris*1.5,iris*.3,smoothstep(.25,1.,r));
      vec3 col=mix(iris,scl,smoothstep(.96,1.04,r));col*=1.-.8*smoothstep(.85,1.,r)*(1.-smoothstep(1.,1.1,r));float slit=abs(d.x)/(dil*.6)+abs(d.y)/(dil*1.6);col=mix(vec3(0.),col,smoothstep(.95,1.05,slit));
      vec3 N=normalize(n),Vv=normalize(v),L=normalize(vec3(.4,.7,.6));gl_FragColor=vec4((col*(.35+.65*max(0.,dot(N,L)))+pow(max(0.,dot(reflect(-L,N),Vv)),140.)*1.6)*dm,al);}` });
  }
  function eyeWithLids(r) {
    const e = new THREE.Group(), ball = new THREE.Mesh(new THREE.SphereGeometry(r, 40, 28), eyeMat()); e.add(ball);
    const lidM = flesh(P.flesh), up = new THREE.Mesh(new THREE.SphereGeometry(r * 1.06, 32, 20, 0, Math.PI * 2, 0, Math.PI * .5), lidM), lo = up.clone(); lo.rotation.x = Math.PI; e.add(up, lo);
    const segs = []; for (let i = 0; i < 24; i++) { const a = -1.25 + 2.5 * i / 23, x = Math.sin(a) * r * 1.06, z = Math.cos(a) * r * 1.06; segs.push(x, 0, z, x * 1.25, r * .5 * (1 + .3 * Math.sin(i * 7)), z * 1.25 + r * .3); }
    const lg = new THREE.BufferGeometry(); lg.setAttribute("position", new THREE.Float32BufferAttribute(segs, 3)); up.add(new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: 0x111111 })));
    e.userData = { ball, blink: -9, set(o) { up.rotation.x = -(Math.PI / 2) * .92 * o - .06; lo.rotation.x = Math.PI + (Math.PI / 2) * .6 * o + .1; } }; e.userData.set(1); return e;
  }
  const ptsMat = (col) => new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { map: { value: dot() }, c: { value: new THREE.Color(col) }, dm: { value: 1 } },
    vertexShader: `attribute float a;varying float va;void main(){va=a;vec4 m=modelViewMatrix*vec4(position,1.);gl_PointSize=(1.5+6.*a)*(6./-m.z)*${DPR.toFixed(2)};gl_Position=projectionMatrix*m;}`,
    fragmentShader: `uniform sampler2D map;uniform vec3 c;uniform float dm;varying float va;void main(){gl_FragColor=vec4(c,1.)*texture2D(map,gl_PointCoord)*(.25+va)*dm;}` });
  const eyes = [], GAZE = { x: 0, y: 0, tx: 0, ty: 0, at: 0, fast: 0 };
  // attention over every face in view (0.8.12, Face presence's "faces": a track id, place, owner flag, micro-movement
  // m): it looks at one face and moves on to another every 3-8 s, sooner when someone new appears or another face
  // moves clearly more; alone, one face is followed closely, with a quick small saccade when it moves. The owner gets
  // no priority. Remove animations or the system's reduced motion: no saccades, a slower smooth gaze.
  const ATT = { faces: new Map(), at: 0, on: null, since: 0, until: 0, fresh: null, known: new Set(), spike: 0 };
  const RM = window.matchMedia ? matchMedia("(prefers-reduced-motion: reduce)") : null, calmEye = () => STILL || !!(RM && RM.matches);
  function attend(now, calm) { // the face looked at now, or null; face_seen alone (tracking off) as before
    if (!(ATT.faces.size && now - ATT.at < 2000)) return GAZE.at && now - GAZE.at < 3000 ? { x: GAZE.x, y: GAZE.y } : null;
    const fs = [...ATT.faces.values()]; let cur = ATT.faces.get(ATT.on), to = null;
    const pick = (not) => { const c = fs.filter((f) => f.id !== not); let tot = 0; const w = c.map((f) => (tot += .4 + f.m)), r = Math.random() * tot; return c[w.findIndex((x) => x >= r)] || c[0] || null; };
    if (!cur) to = (ATT.fresh && ATT.faces.get(ATT.fresh)) || pick(null);
    else if (fs.length > 1) {
      const dwell = now - ATT.since, lively = fs.reduce((a, f) => (f.id !== cur.id && f.m > (a ? a.m : 0) ? f : a), null), fresh = ATT.fresh && ATT.faces.get(ATT.fresh);
      if (fresh && fresh !== cur && dwell > 700) to = fresh; // someone new
      else if (lively && lively.m > .3 && lively.m > cur.m + .25 && dwell > 1000) to = lively; // someone moving more
      else if (now >= ATT.until) to = pick(cur.id);
    }
    if (to) { if (ATT.on != null && !calm) GAZE.fast = now + 140; cur = to; ATT.on = to.id; ATT.since = now; ATT.until = now + 3000 + Math.random() * 5000; ATT.fresh = null; }
    if (fs.length === 1 && !calm && now < GAZE.fast) return { x: cur.x + (cur.x - cur.px) * .5, y: cur.y + (cur.y - cur.py) * .5 }; // a saccade lands a little ahead
    return cur;
  }
  {
    const S = senses.g; S.position.copy(SENSE_C); add(S); const O = senses.organs, hit = senses.hit;
    const sight = new THREE.Group(); sight.position.set(...SPOS.sight); S.add(sight); const big = eyeWithLids(.3); sight.add(big); eyes.push(big); const rings = [];
    for (let k = 0; k < 2; k++) { const ring = new THREE.Group(), R0 = .55 + k * .2; ring.add(new THREE.Mesh(new THREE.TorusGeometry(R0, .025, 10, 140), flesh(P.flesh))); for (let i = 0; i < 7 + k * 3; i++) { const a = i / (7 + k * 3) * 6.283, e = eyeWithLids(.075); e.position.set(Math.cos(a) * R0, Math.sin(a) * R0, 0); ring.add(e); eyes.push(e); } ring.rotation.set(.4 + k * .6, k * .5, 0); sight.add(ring); rings.push(ring); }
    const coch = new THREE.Group(); coch.position.set(...SPOS.hearing); S.add(coch); const pts = []; for (let i = 0; i < 220; i++) { const u = i / 219, a = u * 6.283 * 2.6, r = .32 * (1 - u * .85); pts.push(V(Math.cos(a) * r, Math.sin(a) * r, u * .18)); }
    const cm = flesh(P.coch ?? P.flesh, { col2: P.sulci, mottle: 10 }); coch.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 260, .045, 12, false), cm)); coch.rotation.set(.5, .4, 0);
    for (let i = 6; i < pts.length - 6; i += 7) { const ring = new THREE.Mesh(new THREE.TorusGeometry(.05 * (1 - i / pts.length * .4), .005, 6, 24), cm); ring.position.copy(pts[i]); ring.lookAt(pts[i + 1]); coch.add(ring); }
    const hcN = 520, hcp = new Float32Array(hcN * 3), hca = new Float32Array(hcN); for (let i = 0; i < hcN; i++) { const u = i / hcN, a = u * 6.283 * 2.6, r = .32 * (1 - u * .85) - .05; hcp.set([Math.cos(a) * r, Math.sin(a) * r, u * .18 + .04], i * 3); }
    const hcg = new THREE.BufferGeometry(); hcg.setAttribute("position", new THREE.BufferAttribute(hcp, 3)); hcg.setAttribute("a", new THREE.BufferAttribute(hca, 1)); coch.add(new THREE.Points(hcg, ptsMat(PROC.hear.c)));
    const touch = new THREE.Group(); touch.position.set(...SPOS.touch); S.add(touch); const cil = []; for (let i = 0; i < 360; i++) { const a = rnd() * 6.283, r = Math.sqrt(rnd()) * .38; cil.push([Math.cos(a) * r, Math.sin(a) * r * .5, rnd()]); }
    const cgeo = new THREE.BufferGeometry(), cpos = new Float32Array(cil.length * 6); cgeo.setAttribute("position", new THREE.BufferAttribute(cpos, 3)); touch.add(new THREE.LineSegments(cgeo, new THREE.LineBasicMaterial({ color: P.flesh, transparent: true, opacity: .35 })));
    touch.add(new THREE.Mesh(new THREE.CircleGeometry(.4, 48).scale(1, .5, 1).rotateX(-Math.PI / 2), flesh(new THREE.Color(P.flesh).multiplyScalar(.45).getHex())));
    const tipP = new Float32Array(cil.length * 3), tipA = new Float32Array(cil.length).fill(.2), tipG = new THREE.BufferGeometry(); tipG.setAttribute("position", new THREE.BufferAttribute(tipP, 3)); tipG.setAttribute("a", new THREE.BufferAttribute(tipA, 1)); touch.add(new THREE.Points(tipG, ptsMat(P.tip ?? PROC.touch.c)));
    const bal = new THREE.Group(); bal.position.set(...SPOS.balance); S.add(bal); for (let k = 0; k < 3; k++) { const t2 = new THREE.Mesh(new THREE.TorusGeometry(.2, .022, 10, 80, Math.PI * 1.6), flesh(P.canal ?? P.flesh)); t2.rotation.set(k === 0 ? Math.PI / 2 : 0, k === 1 ? Math.PI / 2 : 0, k * .7); bal.add(t2); }
    bal.add(new THREE.Mesh(new THREE.SphereGeometry(.09, 24, 16), flesh(P.flesh, { op: .35 }))); for (let k = 0; k < 3; k++) { const am = new THREE.Mesh(new THREE.SphereGeometry(.045, 16, 12), flesh(P.flesh)); am.position.set(k === 0 ? .2 : k === 1 ? 0 : -.14, k === 2 ? .14 : 0, k === 1 ? .2 : 0); bal.add(am); }
    const otN = 90, otp = new Float32Array(otN * 3), ota = new Float32Array(otN).fill(.3), ot0 = []; for (let i = 0; i < otN; i++) { const v = V(gauss(), gauss(), gauss()).normalize().multiplyScalar(.06 * rnd()); ot0.push(v); otp.set([v.x, v.y, v.z], i * 3); }
    const otg = new THREE.BufferGeometry(); otg.setAttribute("position", new THREE.BufferAttribute(otp, 3)); otg.setAttribute("a", new THREE.BufferAttribute(ota, 1)); bal.add(new THREE.Points(otg, ptsMat(0xffffff)));
    const heat = new THREE.Group(); heat.position.set(...SPOS.heat); S.add(heat); const hpts = []; for (let i = 0; i < 160; i++) { const u = i / 159; hpts.push(V(Math.sin(u * 31) * .13 * (1 - u * .3), u * .75 - .37, Math.cos(u * 31) * .13 * (1 - u * .3))); }
    const hm = flesh(P.coil ?? P.flesh, { col2: P.fat, mottle: 14 }); heat.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(hpts), 260, .022, 8, false), hm)); for (let i = 8; i < hpts.length - 4; i += 10) { const ring = new THREE.Mesh(new THREE.TorusGeometry(.034, .004, 6, 20), hm); ring.position.copy(hpts[i]); ring.lookAt(hpts[i + 1]); heat.add(ring); }
    Object.assign(O, { sight, hearing: coch, touch, balance: bal, heat });
    for (const [k, o] of Object.entries(O)) { const list = []; o.traverse((x) => { const ms = x.material ? [].concat(x.material) : []; for (const m of ms) { if (m.uniforms && m.uniforms.dm) list.push(m); else if (m.isLineBasicMaterial) { m.userData.base = m.opacity; list.push(m); } } }); senses.mats[k] = [...new Set(list)]; }
    const sizes = { sight: .95, hearing: .4, touch: .45, balance: .3, heat: .45 };
    for (const [k, o] of Object.entries(O)) { const px = new THREE.Mesh(new THREE.SphereGeometry(sizes[k], 12, 8), new THREE.MeshBasicMaterial({ visible: false })); px.userData.pick = { organ: "senses", part: k }; o.add(px); }
    ticks.push((t, dt) => {
      rings[0].rotation.y += dt * .3; rings[1].rotation.x += dt * .22; const mot = Math.max(Math.min(1, (SENSE.motion || 0) / 15), Math.min(1, (fc("sway") || 0) / 3)), scr = Math.min(1, (SENSE.screen || 0) / 15);
      // another device (FAR): its light sets the pupil over your phone's band, its screen off shuts the lids
      const glow = fc("brightness"), shut = shutEyes(), lids = shut ? .05 : fc("eyes") === 0 ? .12 : null, dil0 = ST.dil + (glow != null ? .42 - .22 * Math.min(1, glow / 4) : SENSE.light == null ? .32 : [.42, .32, .2][Math.min(2, Math.max(0, SENSE.light | 0))]);
      const pn = performance.now(), calm = calmEye(), at = attend(pn, calm), right = V(1, 0, 0).applyQuaternion(cam.quaternion), upv = V(0, 1, 0).applyQuaternion(cam.quaternion);
      // the camera faces you and isn't mirrored: your right is the frame's left, so x and y turn round; a saccade is
      // quick, a lone face is followed closely, several are watched a little more slowly, calm is slow and smooth
      const gk = Math.min(1, dt * (calm ? 1.5 : pn < GAZE.fast ? 22 : ATT.faces.size === 1 ? 9 : 5));
      GAZE.tx += ((at ? -at.x : 0) - GAZE.tx) * gk; GAZE.ty += ((at ? -at.y : 0) - GAZE.ty) * gk;
      const look = cam.position.clone().add(right.multiplyScalar(GAZE.tx * view.d * .45)).add(upv.multiplyScalar(GAZE.ty * view.d * .3));
      for (const e of eyes) { const u = e.userData; if (!shut && (Math.abs(t - (hit.sight ?? -9)) < .02 || rnd() < .002)) u.blink = t; const bk = Math.max(0, 1 - Math.abs(t - u.blink) / .12); u.set(Math.max(.05, (lids ?? (OPEN.senses ? 1 : .82)) - bk)); e.lookAt(look); u.ball.material.uniforms.dil.value = dil0 + (SENSE.face ? .06 : 0); }
      senses.level = (senses.level || 0) * Math.exp(-dt * 3); const loud = fc("loudness"); if (loud != null) senses.level = Math.max(senses.level, .6 * Math.min(1, Math.max(0, (loud - 35) / 50))); const hh = Math.max(Math.min(1, senses.level * 1.5), 1 - (t - (hit.hearing ?? -9)) / 1.2); for (let i = 0; i < hcN; i++) hca[i] = .15 + hh * Math.max(0, Math.sin(i / hcN * 30 - t * 14)); hcg.attributes.a.needsUpdate = true; cm.uniforms.k.value = hh;
      const th = Math.max(scr * .5, 1 - (t - (hit.touch ?? -9)) / 1.4, .8 * (fc("closeness") || 0)); for (let i = 0; i < cil.length; i++) { const [x, z, ph] = cil[i], bend = .05 * Math.sin(t * 2 + ph * 6) + th * .18 * Math.sin(t * 9 - Math.hypot(x, z) * 20); cpos.set([x, 0, z, x + bend, .22 + ph * .08, z + bend * .4], i * 6); tipP.set([x + bend, .22 + ph * .08, z + bend * .4], i * 3); }
      tipA.fill(.04 + th * .7); cgeo.attributes.position.needsUpdate = tipG.attributes.position.needsUpdate = tipG.attributes.a.needsUpdate = true;
      // the otoliths: shaken by motion, settled the way gravity pulls (tilt), swirled round by turning (the canals')
      const tl = (fc("tilt") || 0) * Math.PI / 180; senses.swirl = (senses.swirl || 0) + dt * Math.min(6, fc("turning") || 0); const sc = Math.cos(senses.swirl), sn = Math.sin(senses.swirl);
      for (let i = 0; i < otN; i++) { const v = ot0[i], x0 = v.x * sc - v.z * sn, z0 = v.x * sn + v.z * sc; otp.set([x0 + Math.sin(t * 6 + i) * .03 * mot + Math.sin(tl) * .035, v.y - .02 + Math.cos(t * 4 + i * 1.7) * .03 * mot - (1 - Math.cos(tl)) * .015, z0], i * 3); } otg.attributes.position.needsUpdate = true;
      const temp = SYS && SYS.temps ? Math.max(0, ...Object.values(SYS.temps).flat().map(Number).filter(isFinite)) : 50; const ft = fc("temperature"); hm.uniforms.k.value = Math.min(1, Math.max(0, (temp - 40) / 50, ft != null ? (ft - 25) / 25 : 0)); for (const m of [cm, hm]) m.uniforms.t.value = t;
    });
  }

  /* ===================== memory: your notes ===================== */
  const MEM_C = V(3.15, .3, -.4), memory = { g: new THREE.Group(), nodes: [], ids: [], hoods: [] };
  add(memory.g); memory.g.position.copy(MEM_C); memory.g.scale.setScalar(.55);
  {
    const px = new THREE.Mesh(new THREE.SphereGeometry(1.5, 12, 8), new THREE.MeshBasicMaterial({ visible: false })); px.userData.pick = { organ: "memory" }; memory.g.add(px);
  }
  // where each note sat, so a new graph (a note changed) settles from there instead of starting over
  const POS = new Map();
  // the layout runs in a worker (being-layout.js: a 3D force layout, as the NOTES map's in 2D); one at a time
  let LAYOUT = null;
  memory.build = (g) => {
    for (const o of [...memory.g.children]) if (!o.userData.pick) memory.g.remove(o);
    const nodes = (g.nodes || []).slice(0, 4000), label = new Map(); // neighbourhoods: the NOTES map's own (home.js)
    const hoodOfN = (n) => { const h = opts.hoodOf && opts.hoodOf(n.id); if (h) { label.set(h.key, h.label); return h.key; } const k = n.group || n.id.split("/")[0] || "notes"; label.set(k, k); return k; };
    for (const n of nodes) n._hood = hoodOfN(n);
    const counts = new Map(); for (const n of nodes) counts.set(n._hood, (counts.get(n._hood) || 0) + 1);
    const names = [...counts.keys()].sort((x, y) => counts.get(y) - counts.get(x)); const hi = new Map(names.map((h, i) => [h, i]));
    const N = nodes.length, p = new Float32Array(N * 3), a = new Float32Array(N), col = new Float32Array(N * 3), deg = new Uint16Array(N), hood = new Int32Array(N), idx = new Map(nodes.map((n, i) => [n.id, i]));
    const ctr = names.map((h, k) => { const ang = k * 2.4, r = k === 0 ? 0 : .7 + .55 * Math.sqrt(k / names.length); return V(Math.cos(ang) * r, Math.sin(ang) * r * .8, Math.sin(ang * 2) * r * .45); });
    let fresh = 0;
    for (let i = 0; i < N; i++) {
      const k = hi.get(nodes[i]._hood); hood[i] = k; const old = POS.get(nodes[i].id);
      if (old) p.set(old, i * 3); else { fresh++; const q = ctr[k].clone().add(V(gauss(), gauss(), gauss()).multiplyScalar(.045 * Math.cbrt(counts.get(nodes[i]._hood)))); p.set([q.x, q.y, q.z], i * 3); }
      const c = hoodCols[k % hoodCols.length]; col.set([c.r, c.g, c.b], i * 3); a[i] = .55 + rnd() * .35; // as bright as the first being
    }
    // every link, as the NOTES map has them: one through a "Seen in" or a reading list (via) drawn a little fainter
    const L = [], LW = [];
    for (const l of (g.links || [])) { const x = idx.get(l[0]), y = idx.get(l[1]); if (x == null || y == null || x === y) continue; deg[x]++; deg[y]++; L.push(x, y); LW.push(l[2] ? .5 : 1); }
    const LI = Int32Array.from(L);
    const lp = new Float32Array(LI.length * 3), lc = new Float32Array(LI.length * 3);
    const placeLinks = () => { for (let l = 0; l < LI.length; l++) lp.set(p.subarray(LI[l] * 3, LI[l] * 3 + 3), l * 3); };
    for (let l = 0; l < LI.length; l++) { const j = LI[l - (l % 2)], w = LW[l >> 1]; lc[l * 3] = col[j * 3] * w; lc[l * 3 + 1] = col[j * 3 + 1] * w; lc[l * 3 + 2] = col[j * 3 + 2] * w; }
    placeLinks();
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(p, 3)); geo.setAttribute("a", new THREE.BufferAttribute(a, 1)); geo.setAttribute("col", new THREE.BufferAttribute(col, 3));
    const pts = new THREE.Points(geo, new THREE.ShaderMaterial({ transparent: true, depthWrite: false, uniforms: { map: { value: dot() } },
      vertexShader: `attribute float a;attribute vec3 col;varying float va;varying vec3 vc;void main(){va=a;vc=col;vec4 m=modelViewMatrix*vec4(position,1.);gl_PointSize=((1.1+2.6*max(0.,min(a,1.)-.5))*(4./-m.z)+1.)*${(OM ? FULL : DPR).toFixed(2)};gl_Position=projectionMatrix*m;}`, // an organ page: the dashboard's size, at full density
      // dimmed by alpha, not by darkening: a darkened hue reads as grey (0.8.11)
      fragmentShader: `uniform sampler2D map;varying float va;varying vec3 vc;void main(){float t=texture2D(map,gl_PointCoord).r;if(t<.02)discard;gl_FragColor=vec4(vc*(.68+.22*min(2.5,va)),t*min(1.,.25+va*1.1));}` }));
    pts.userData.notes = true; memory.g.add(pts);
    if (!memory.ring) memory.ring = new THREE.Mesh(new THREE.RingGeometry(.8, 1, 32), new THREE.MeshBasicMaterial({ color: P.ink, transparent: true, opacity: .8, depthTest: false }));
    memory.ring.visible = false; memory.g.add(memory.ring);
    const lg = new THREE.BufferGeometry(); lg.setAttribute("position", new THREE.BufferAttribute(lp, 3)); lg.setAttribute("color", new THREE.BufferAttribute(lc, 3));
    const lines = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: Math.max(.05, Math.min(.16, 1500 / Math.max(1, LI.length / 2))), blending: THREE.AdditiveBlending, depthWrite: false }));
    lines.material.userData.base = lines.material.opacity; memory.g.add(lines);
    const nb = Array.from({ length: N }, () => []); for (let l = 0; l < LI.length; l += 2) { nb[LI[l]].push(LI[l + 1]); nb[LI[l + 1]].push(LI[l]); }
    memory.nodes = nodes; memory.pts = pts; memory.lines = lines; memory.a = a; memory.base = a.slice(); memory.deg = deg; memory.hood = hood; memory.nb = nb; memory.p = p;
    const hoodsNow = () => names.map((h, k) => {
      let b = -1, bd = -1, n = 0; const m = V(0, 0, 0);
      for (let i = 0; i < N; i++) if (hood[i] === k) { n++; m.x += p[i * 3]; m.y += p[i * 3 + 1]; m.z += p[i * 3 + 2]; if (deg[i] > bd) { bd = deg[i]; b = i; } }
      m.multiplyScalar(1 / Math.max(1, n));
      return { key: k, name: label.get(h) || h, at: b < 0 ? [0, 0, 0] : [p[b * 3], p[b * 3 + 1], p[b * 3 + 2]], centre: m, hub: b < 0 ? "" : nodes[b].title || nodes[b].id, links: bd, n };
    });
    memory.hoods = hoodsNow(); memFit();
    // settle in the worker; each step it sends moves the notes and their links, so you see them pull together
    if (LAYOUT) LAYOUT.terminate();
    try {
      const w = (LAYOUT = new Worker("/static/being-layout.js"));
      const flat = new Float32Array(ctr.length * 3); ctr.forEach((c, k) => flat.set([c.x, c.y, c.z], k * 3));
      w.onmessage = (e) => {
        if (memory.p !== p) return; p.set(e.data.p); placeLinks(); geo.attributes.position.needsUpdate = true; lg.attributes.position.needsUpdate = true;
        if (e.data.done) { w.terminate(); if (LAYOUT === w) LAYOUT = null; memory.hoods = hoodsNow(); for (let i = 0; i < N; i++) POS.set(nodes[i].id, [p[i * 3], p[i * 3 + 1], p[i * 3 + 2]]); memFit(); }
      };
      w.postMessage({ p: p.slice(), li: LI, lw: Float32Array.from(LW), hood, ctr: flat, iters: fresh > N * .2 ? 220 : 50 });
    } catch (err) { console.error("the notes' layout", err); }
  };
  // the Memory page (an organ page, 0.8.13): framed on where the notes really are (a few dozen settle into a small knot,
  // thousands into a wide cloud), between the app's bars, with the features' lights on a ring just outside them, never
  // off the screen; it was framed on a fixed ring of lights, so a small vault sat tiny in the middle
  const MEM_FIT = { c: V(0, 0, 0), r: .5 };
  function memFit() {
    const p = memory.p, n = p ? p.length / 3 : 0; if (!OM || !n) return;
    const c = V(0, 0, 0); for (let i = 0; i < n; i++) { c.x += p[i * 3]; c.y += p[i * 3 + 1]; c.z += p[i * 3 + 2]; } c.multiplyScalar(1 / n);
    const d = new Float32Array(n); for (let i = 0; i < n; i++) d[i] = Math.hypot(p[i * 3] - c.x, p[i * 3 + 1] - c.y, p[i * 3 + 2] - c.z); d.sort();
    MEM_FIT.c.copy(c); MEM_FIT.r = Math.max(.12, d[Math.min(n - 1, Math.floor(n * .95))]); // a stray note or two may sit outside
    memRing(); memFrame();
  }
  const memRingR = () => MEM_FIT.r * 1.3 + .12;
  function memRing() { // the features' lights round the notes (their lines from the cloud's edge)
    const ids = Object.keys(ORG).filter((id) => ORG[id].org === "memory"), c = MEM_FIT.c, R = memRingR();
    ids.forEach((id, k) => {
      const o = ORG[id], ang = k / ids.length * 6.283 + .4, dir = V(Math.cos(ang), Math.sin(ang) * .8, 0), pos = c.clone().add(dir.clone().multiplyScalar(R)).add(V(0, 0, .1));
      o.g.position.copy(pos); if (o.g.parent !== memory.g) memory.g.add(o.g); // a new graph took the old lights off
      if (o.line) { const a = c.clone().add(dir.multiplyScalar(MEM_FIT.r * .95)); o.line.geometry.setFromPoints([a, pos]); if (o.line.parent !== memory.g) memory.g.add(o.line); }
    });
  }
  function memFrame() { // the whole cloud and its ring in what the bars leave of the screen
    if (!OM || ONLY !== "memory" || FOCUS !== "memory" || SUB) return;
    memory.g.updateMatrixWorld(); const w = MEM_FIT.c.clone().applyMatrix4(memory.g.matrixWorld), rw = (memRingR() + .12) * memory.g.scale.x;
    const t = Math.tan(cam.fov * Math.PI / 360), room = PH && PH.room ? PH.room(H) : 1;
    goal.tx = w.x; goal.ty = w.y; goal.tz = w.z; goal.d = Math.max(.4, rw / Math.min(t * room, t * cam.aspect) * 1.05);
  }
  let MEM_ROOM = 0; // the app's bars measured (or turned sideways) after the notes came: framed again
  if (OM && PH && PH.room) ticks.push(() => { const r = PH.room(H) + cam.aspect; if (Math.abs(r - MEM_ROOM) > .01) { MEM_ROOM = r; memFrame(); } });
  const fires = [];
  ticks.push((t) => {
    if (!memory.a) return; const a = memory.a, n = a.length, far = .3 + .7 * (OPEN.memory || 0); // seen from afar, the packed notes are dimmer
    for (let i = 0; i < n; i++) a[i] = memory.base[i] * far;
    for (let i = fires.length - 1; i >= 0; i--) { const [j, t0] = fires[i], u = (t - t0) / .7; if (u > 1) { fires.splice(i, 1); continue; } if (u > 0 && j < n) a[j] = Math.max(a[j], .7 + 1.3 * Math.sin(Math.PI * u)); }
    if (SUB && SUB.kind === "hood") for (let i = 0; i < n; i++) a[i] *= memory.hood[i] === SUB.key ? 1.05 : .16;
    if (SUB && SUB.kind === "note") { for (let i = 0; i < n; i++) a[i] *= .25; for (const j of memory.nb[SUB.key] || []) a[j] = 1.05; a[SUB.key] = 1.9; }
    if (HOVER_NOTE != null && HOVER_NOTE < n) a[HOVER_NOTE] = 2.2; memory.pts.geometry.attributes.a.needsUpdate = true;
    // the selector: a fine ring round the note you point at (or the one in focus), the size of a few dots
    const j = HOVER_NOTE != null ? HOVER_NOTE : SUB && SUB.kind === "note" ? SUB.key : null;
    memory.ring.visible = j != null && j < n;
    if (memory.ring.visible) { memory.ring.position.set(memory.p[j * 3], memory.p[j * 3 + 1], memory.p[j * 3 + 2]); memory.ring.quaternion.copy(cam.quaternion); const d = memory.ring.getWorldPosition(V(0, 0, 0)).distanceTo(cam.position); memory.ring.scale.setScalar(d * .012 / .55); }
  });

  /* ===================== the features: points of light ===================== */
  const ORG = {};
  function lightPoint(on, col) {
    const g = new THREE.Group(), c = new THREE.Color(P.a).lerp(new THREE.Color(col), .4);
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: dot(), color: c, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: on ? .9 : .25 })); sp.scale.setScalar(on ? .09 : .045);
    const ring = new THREE.Mesh(new THREE.RingGeometry(.034, .037, 40), new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide }));
    const hitbox = new THREE.Mesh(new THREE.SphereGeometry(.07, 8, 6), new THREE.MeshBasicMaterial({ visible: false }));
    g.add(sp, ring, hitbox); g.userData = { sp, ring, hitbox, base: on ? .09 : .045 }; return g;
  }
  function placeFeatures(cells) {
    const groups = {};
    for (const c of cells) { const [org, part] = homeOf(c.id); const key = `${org}:${part}`; (groups[key] = groups[key] || []).push(c); }
    for (const [key, list] of Object.entries(groups)) {
      const [org, part] = key.split(":");
      list.forEach((c, k) => {
        if (ORG[c.id]) { ORG[c.id].on = c.on; ORG[c.id].act = c.act || 0; return; }
        let parent, pos, anchor, col = 0xffffff;
        if (org === "mind") { const a = V(...REGIONS[part].at).add(OFF), d = a.clone().sub(V(0, .1, 0)).normalize(), tan = V(-d.z, 0, d.x).normalize(), up = d.clone().cross(tan).normalize(), ang = k / list.length * 6.283; pos = a.clone().add(d.clone().multiplyScalar(.55)).add(tan.multiplyScalar(Math.cos(ang) * .13)).add(up.multiplyScalar(Math.sin(ang) * .13)); parent = mind.b; anchor = a; const pk = Object.keys(PROC).find((x) => PROC[x].at.join() === REGIONS[part].at.join()); col = pk ? PROC[pk].c : 0x9fe3c8; }
        else if (org === "senses") { const o = senses.organs[part], ang = k / list.length * 6.283 + .6; pos = o.position.clone().add(V(Math.cos(ang) * .42, Math.sin(ang) * .42, .1)); parent = senses.g; anchor = o.position.clone(); col = 0x9fe3c8; }
        else if (org === "memory") { const ang = k / list.length * 6.283; pos = V(Math.cos(ang) * 1.7, Math.sin(ang) * 1.3, .3); parent = memory.g; anchor = V(0, 0, 0); col = PROC.memory.c; }
        else { const ang = k / list.length * 6.283 + .3; pos = V(Math.cos(ang) * 1.15, Math.sin(ang) * .9, .3); parent = heart.g; anchor = V(0, 0, 0); col = 0xf0a0a0; }
        const g = lightPoint(c.on, col); g.position.copy(pos); parent.add(g); g.userData.hitbox.userData.pick = { feature: c.id };
        const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(new THREE.CatmullRomCurve3([anchor, anchor.clone().lerp(pos, .5).add(V(0, .05, 0)), pos]).getPoints(16)), new THREE.LineBasicMaterial({ color: P.vein, transparent: true, opacity: c.on ? .22 : .06, blending: THREE.AdditiveBlending, depthWrite: false }));
        parent.add(line);
        ORG[c.id] = { g, line, flash: -9, title: c.title, org, part, on: c.on, act: c.act || 0, col };
      });
    }
    if (OM) { memRing(); memFrame(); }
  }
  ticks.push((t) => {
    for (const id in ORG) { const o = ORG[id], u = o.g.userData, fl = Math.max(0, 1 - (t - o.flash) / 1.6), tw = o.on ? .75 + .25 * Math.sin(t * (1 + 3 * o.act) + o.g.id) : 1; const mine = SUB && SUB.kind === "feature" && SUB.key === id, other = SUB && SUB.kind === "feature" && !mine;
      u.sp.material.opacity = mine ? 1 : (o.on ? (.45 + .55 * Math.max(fl, o.act)) * tw : .2) * (other ? .3 : 1); u.sp.scale.setScalar(u.base * (1 + 1.4 * fl + (HOVER_FEATURE === id ? .8 : 0) + (mine ? .9 : 0))); u.ring.material.opacity = Math.max(HINT, HOVER_FEATURE === id || mine ? 1 : 0) * (o.on ? .7 : .35); u.ring.lookAt(cam.position); }
  });

  ticks.push(() => {
    const s = SUB, ease = (u, to) => { u.value += (to - u.value) * .12; };
    const selCol = (k) => { const pk = Object.keys(PROC).find((x) => PROC[x].at.join() === REGIONS[k].at.join()); return pk ? PROC[pk].c : 0x9fe3c8; };
    // the mind: a region of the cortex stays solid (the cortex's twin draws it), or a whole deep structure; X-ray: the
    // cortex is glass and the deep structures solid
    const reg = s && s.kind === "region" ? s.key : null, home = reg ? DEEP_OF[reg] || "grey" : null, xray = FOCUS === "mind" && mind.mode === "xray";
    for (const [nm, mesh] of Object.entries(mind.part)) {
      const u = mesh.material.uniforms, deep = mind.deep.includes(mesh);
      const ghost = reg ? (nm === home && nm !== "grey" ? 0 : 1) : xray ? (deep ? 0 : 1) : 0;
      ease(u.gh, ghost); ease(u.fk, reg && nm === home ? 1 : 0);
      u.fr.value = reg && nm === home ? (nm === "grey" ? .26 : 99) : 0;
      if (reg) { u.fp.value.set(...REGIONS[reg].at); u.fc.value.setHex(selCol(reg)); }
    }
    // the heart: the part stays solid (the coronaries: the vessels whole), the rest is glass
    const hp = s && s.kind === "heart" ? s.key : null;
    { const u = heart.mesh.material.uniforms; ease(u.gh, hp ? 1 : 0); ease(u.fk, hp && hp !== "coronaries" ? 1 : 0); u.fr.value = hp && hp !== "coronaries" ? .38 : 0; if (hp) { u.fp.value.set(...HEART_PARTS[hp].at); u.fc.value.setHex(0xf0a0a0); } }
    { const u = heart.mats[1].uniforms; ease(u.gh, hp && hp !== "coronaries" ? 1 : 0); ease(u.fk, hp === "coronaries" ? 1 : 0); u.fr.value = hp === "coronaries" ? 99 : 0; u.fc.value.setHex(0xf0a0a0); }
    for (const [k, list] of Object.entries(senses.mats)) {
      const sel = s && s.kind === "sense", mine = sel && s.key === k, glass = sel && !mine ? 1 : 0;
      for (const m of list) {
        if (!m.uniforms) { m.opacity = m.userData.base * (glass ? .12 : 1); continue; }
        if (m.uniforms.gh) { ease(m.uniforms.gh, glass); m.uniforms.fr.value = 0; ease(m.uniforms.hl, mine ? 1 : 0); }
        else if (m.uniforms.al) ease(m.uniforms.al, glass ? .1 : 1);
        else ease(m.uniforms.dm, glass ? .15 : 1);
      }
    }
    for (const m of GHOSTS) { if (m.defines.SOLID !== undefined) continue; const g = m.uniforms.gh.value > .01; m.transparent = g || !!m.userData.o.op; m.depthWrite = !g && !m.userData.o.op; }
    for (const mesh of [mind.cortex, heart.mesh]) mesh.userData.twin.visible = mesh.material.uniforms.gh.value > .01 && mesh.material.uniforms.fr.value > 0;
    if (memory.lines) memory.lines.material.opacity = memory.lines.material.userData.base * (s && (s.kind === "hood" || s.kind === "note") ? .45 : 1) * (.15 + .85 * (OPEN.memory || 0)); // from afar 24k links would add up to white
  });

  /* --- the links between the organs --- */
  // each vessel and nerve is joined to its organ (end): the brain's arteries at the front of the pons, on the axis it
  // turns about (where the real basilar artery runs), the spinal cord at the brainstem's lower end (brain-local: OFF in)
  const HEART_E = end(heart.g, HEART_C.clone());
  vessel("mind", HEART_E, end(mind.b, V(0, -.23, .01), true), 5, .25, .04); vessel("senses", HEART_E, end(senses.g, SENSE_C.clone().add(V(.15, .35, 0))), 5, .4, .05);
  for (const [nm, k, dy] of [["s_hear", "hearing", 0], ["s_touch", "touch", .05], ["s_bal", "balance", 0], ["s_heat", "heat", -.36]]) vessel(nm, HEART_E, end(senses.organs[k], V(0, dy, 0), true), 2, .3, .02);
  vessel("memory", HEART_E, end(memory.g, V(-.45, -.15, 0), true), 5, .4, .05); // into the notes, near the axis they turn on
  { const stem = end(mind.b, V(0, -1.05, -.31), true), PLEX = V(0, .0, -.5), cord = (x) => [PLEX.clone().add(x), V(0, .1, -.44).add(x.clone().multiplyScalar(.6))];
    const sx = V(-.02, 0, 0), mx = V(.02, 0, 0), hx = V(0, 0, .02), sE = SENSE_C.clone().add(V(.2, .6, 0)), mE = MEM_C.clone().add(V(-.22, .25, 0));
    nerve("senses", end(senses.g, sE), stem, [sE.clone().add(V(.3, -.28, -.1)), V(-1.45, -.12, -.62), ...cord(sx)]);
    nerve("memory", end(memory.g, mE), stem, [mE.clone().add(V(-.3, -.28, -.1)), V(1.4, -.15, -.64), ...cord(mx)]);
    nerve("heart", end(heart.g, HEART_C.clone().add(V(.06, .28, -.12))), stem, [HEART_C.clone().add(V(.04, .5, -.4)), ...cord(hx)]); }

  /* ===================== the camera: you turn it ===================== */
  const view = { th: 0, ph: 1.42, d: 10.4, tx: 0, ty: .2, tz: 0 }, goal = { ...view }, HOME = { ...view };
  const TARGETS = { mind: { c: BRAIN_C, d: 4.4 }, heart: { c: HEART_C, d: 2.8 }, senses: { c: SENSE_C.clone().add(V(.1, .15, 0)), d: 5.4 }, memory: { c: MEM_C, d: 2.4 } };
  let FOCUS = null, OPEN = {}, HOVER = null, HOVER_NOTE = null, HOVER_FEATURE = null, HINT = 1, hintUntil = 0, NOW = 0, SYS = null, SENSE = {}, FAR = null, CELLS = [];
  function focusOn(name) {
    FOCUS = name; SUB = null; hintUntil = NOW + 3;
    if (!name) Object.assign(goal, HOME);
    else { const T = TARGETS[name]; goal.tx = T.c.x; goal.ty = T.c.y; goal.tz = T.c.z; goal.d = OM ? ONLY_D[name] : T.d; }
    if (OM && name === "memory") memFrame(); // the Memory page: on the notes as they lie
  }
  // an organ page: the organ fills the phone's width (the dashboard's distances frame it among the others); a part
  // picked comes nearer than the dashboard brings it, for the same reason
  const ONLY_D = { mind: 2.6, heart: 1.45, senses: 3.6, memory: 2.3 }, ONLY_SUB = .7;
  const ONLY_TH = { mind: -.95, heart: .35 }; // seen from three-quarters (the brain from the front shows only its two halves)
  // One part of an organ in focus (SUB): a brain region, a heart part, a sense, a neighbourhood of notes, one note, one
  // feature. The camera flies to it from the side it faces and stays on it while it moves; it brightens and the rest of
  // its organ dims. Esc or a click on empty space goes back to the whole organ.
  let SUB = null;
  function subFocus(s) {
    if (FOCUS !== s.org) FOCUS = s.org;
    SUB = s; hintUntil = NOW + 3; spinning.obj = null;
    const q = s.pos(); goal.tx = q.x; goal.ty = q.y; goal.tz = q.z; goal.d = OM ? s.d * ONLY_SUB : s.d;
    if (s.from) {
      const dir = q.clone().sub(s.from());
      if (dir.lengthSq() > 1e-6) { dir.normalize(); const th = Math.atan2(dir.x, dir.z); goal.th += ((th - goal.th) % 6.2832 + 9.4248) % 6.2832 - 3.1416; goal.ph = Math.max(.45, Math.min(2.7, Math.acos(Math.max(-1, Math.min(1, dir.y))))); }
    }
  }
  function back() { const org = SUB ? SUB.org : FOCUS; if (!org) return; if (OM) PICKED = null; focusOn(org); showOrgan(org); } // an organ page: no part named after it
  const wpos = (obj) => obj.getWorldPosition(V(0, 0, 0));
  const spinning = { obj: null, vx: 0, vy: 0 };
  let drag = null;
  gl.addEventListener("contextmenu", (e) => e.preventDefault());
  // phone: one finger turns an organ (the view where there's none), pinch zooms, two fingers pan, a tap picks
  if (PH) PH.touch({ gl, goal, spinning, pickAt, click, focus: () => FOCUS, cam, size: () => [W, H], setDrag: (d) => (drag = d), organ: (on) => (OM ? held() : on ? (on.organ === "senses" && on.part ? senses.organs[on.part] : ORGAN_OBJ[on.organ]) : null), only: () => OM });
  // an organ page: a finger anywhere turns the organ (a sense picked: that sense), not the view
  const held = () => (SUB && SUB.kind === "sense" ? senses.organs[SUB.key] : ORGAN_OBJ[ONLY]);
  if (!PH) gl.addEventListener("pointerdown", (e) => { gl.setPointerCapture(e.pointerId); drag = { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, b: e.button, moved: false, on: pickAt(e, true) }; });
  if (!PH) gl.addEventListener("pointermove", (e) => {
    if (drag) {
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y; drag.x = e.clientX; drag.y = e.clientY;
      if (Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) > 4) drag.moved = true; if (!drag.moved) return;
      if (drag.b === 2) { const s = goal.d * .0012, r = V(Math.cos(goal.th), 0, -Math.sin(goal.th)); goal.tx -= r.x * dx * s; goal.tz -= r.z * dx * s; goal.ty += dy * s; return; }
      const on = drag.on, org = on ? (on.organ === "senses" && on.part ? senses.organs[on.part] : ORGAN_OBJ[on.organ]) : null;
      if (org) { org.rotation.y += dx * .008; org.rotation.x += dy * .008; spinning.obj = org; spinning.vx = dx * .008; spinning.vy = dy * .008; }
      return;
    }
    hover(e);
  });
  if (!PH) gl.addEventListener("pointerup", (e) => { const d = drag; drag = null; if (d && !d.moved) click(e); });
  if (!PH) gl.addEventListener("wheel", (e) => { e.preventDefault(); goal.d = Math.max(1.2, Math.min(22, goal.d * (1 + e.deltaY * .0011))); }, { passive: false });
  const typing = () => ["INPUT", "TEXTAREA", "SELECT"].includes((document.activeElement || {}).tagName);
  const onKey = (e) => {
    if (e.key === "Escape") { if (SUB) back(); else if (FOCUS || panel.style.display === "block") { closePanel(); focusOn(null); } }
    else if ((e.key === "h" || e.key === "H") && !e.ctrlKey && !e.altKey && !e.metaKey && !typing() && host.offsetWidth) setHints(!HINTS, true);
  };
  addEventListener("keydown", onKey);
  const ORGAN_OBJ = { mind: mind.g, heart: heart.g, senses: senses.g, memory: memory.g };

  /* --- picking: invisible stand-ins, so a hover costs nothing; the cortex itself only on a click into the mind --- */
  const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
  const proxies = [];
  { const pm = new THREE.Mesh(new THREE.SphereGeometry(.9, 12, 8), new THREE.MeshBasicMaterial({ visible: false })); pm.scale.set(.9, .75, 1.2); pm.userData.pick = { organ: "mind" }; mind.g.add(pm); proxies.push(pm);
    const ph = new THREE.Mesh(new THREE.SphereGeometry(.55, 12, 8), new THREE.MeshBasicMaterial({ visible: false })); ph.userData.pick = { organ: "heart" }; heart.g.add(ph); }
  const shown = (o) => { for (let x = o; x; x = x.parent) if (x.visible === false) return false; return true; }; // an organ page hides the others
  function pickAt(e, organOnly) {
    const r = gl.getBoundingClientRect(); mouse.set((e.clientX - r.left) / W * 2 - 1, -((e.clientY - r.top) / H) * 2 + 1); ray.setFromCamera(mouse, cam);
    const list = []; scene.traverse((o) => { if (o.userData.pick && o.parent && o.parent.visible !== false && (!OM || shown(o))) list.push(o); });
    const hits = ray.intersectObjects(list, false);
    if (!organOnly) for (const h of hits) if (h.object.userData.pick.feature) return h.object.userData.pick;
    if (!organOnly && FOCUS === "memory" && memory.pts) { ray.params.Points.threshold = .025; const nh = ray.intersectObject(memory.pts, false); if (nh.length) return { note: nh[0].index }; }
    for (const h of hits) { const p = h.object.userData.pick; if (p.organ) return p; }
    return null;
  }
  let lastHover = 0;
  function hover(e) {
    const now = performance.now(); if (now - lastHover < 40) return; lastHover = now;
    const p = pickAt(e); HOVER = p && p.organ && !FOCUS ? p.organ : null; HOVER_FEATURE = p && p.feature || null; HOVER_NOTE = p && p.note != null ? p.note : null;
    gl.style.cursor = p ? "pointer" : (drag ? "grabbing" : "grab");
    let txt = "";
    if (p && p.feature && ORG[p.feature]) txt = `${ORG[p.feature].title} · ${ORG[p.feature].on ? "on" : "off"}`;
    else if (p && p.note != null && memory.nodes[p.note]) txt = memory.nodes[p.note].title || memory.nodes[p.note].id;
    else if (p && p.organ && !FOCUS) txt = { mind: "the mind", heart: "the heart", senses: "the senses", memory: "memory: your notes" }[p.organ];
    else if (p && p.part && FOCUS === "senses") txt = SENSES[p.part].name;
    if (txt) { tip.textContent = txt; tip.style.display = "block"; const r = host.getBoundingClientRect(); tip.style.left = (e.clientX - r.left + 14) + "px"; tip.style.top = (e.clientY - r.top + 10) + "px"; } else tip.style.display = "none";
  }
  function click(e) {
    const p = pickAt(e);
    if (!p) { if (SUB) back(); else if (!OM) { closePanel(); focusOn(null); } return; } // an organ page stays on its organ
    if (p.feature) { showFeature(p.feature); return; }
    if (p.note != null) { showNote(memory.nodes[p.note]); return; }
    if (p.organ && p.organ !== FOCUS) { if (p.organ === "mind") setMode("solid"); focusOn(p.organ); showOrgan(p.organ); return; }
    if (p.organ === "senses" && p.part) { showSense(p.part); return; }
    if (FOCUS === "mind") { // which region of the cortex: the nearest region to the point clicked
      const glassy = mind.mode === "xray" || (SUB && SUB.kind === "region");
      const dh = glassy ? ray.intersectObjects(mind.deep.concat(mind.part.cerebellum), false)[0] : null;
      if (dh) { const nm = Object.keys(mind.part).find((k) => mind.part[k] === dh.object), r = Object.keys(DEEP_OF).find((k) => DEEP_OF[k] === nm); if (r) { showRegion(r); return; } }
      const h = ray.intersectObject(mind.cortex, false)[0] || ray.intersectObject(proxies[0], false)[0]; if (!h) return;
      const lp = mind.b.worldToLocal(h.point.clone()).sub(OFF); let best = null, bd = 9;
      for (const [k, r] of Object.entries(REGIONS)) { const d = lp.distanceTo(V(...r.at)); if (d < bd) { bd = d; best = k; } } if (best) showRegion(best); return;
    }
    if (FOCUS === "heart") { const h = ray.intersectObject(heart.mesh, false)[0]; if (!h) return; const lp = heart.g.worldToLocal(h.point.clone()); let best = null, bd = 9; for (const [k, r] of Object.entries(HEART_PARTS)) { const d = lp.distanceTo(V(...r.at)); if (d < bd) { bd = d; best = k; } } showHeartPart(best); return; }
    if (FOCUS === "memory") { // the neighbourhood nearest the ray
      let best = null, bd = .35; for (const h of memory.hoods) { if (h.n < 2) continue; const d = ray.ray.distanceToPoint(h.centre.clone().applyMatrix4(memory.g.matrixWorld)); if (d < bd) { bd = d; best = h; } }
      if (best) showHood(best.key); else showOrgan("memory");
    }
  }

  /* ===================== the panel: what you clicked, live, with its settings ===================== */
  let SETTINGS = null, SET_AT = 0, PANEL = null;
  const getSettings = async () => { if (!SETTINGS || performance.now() - SET_AT > 8000) { SETTINGS = await api("settings"); SET_AT = performance.now(); } return SETTINGS; };
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  function say2(text) { let el = panel.querySelector(".said"); if (!el) { el = document.createElement("div"); el.className = "s said"; panel.appendChild(el); } el.textContent = text; }
  function closePanel() { PICKED = null; panel.style.display = "none"; panel.innerHTML = ""; PANEL = null; if (OM) organDirty(); else if (PH) PH.sheet(panel, false); }
  function openPanel(html, kind) { if (OM) { PANEL = kind; organDirty(); return; } panel.innerHTML = `<button class="x" title="close (Esc)">×</button>${html}`; panel.style.display = "block"; PANEL = kind; panel.querySelector(".x").onclick = closePanel; if (PH) PH.sheet(panel, true, closePanel, kind); } // phone: a bottom sheet
  async function settingsHTML(sections) {
    if (!sections.length) return "";
    const S = await getSettings().catch(() => null); if (!S) return "";
    let out = "";
    for (const sec of sections) {
      const s = (S.sections || []).find((x) => x.section === sec); if (!s) continue;
      out += `<details${sections.length === 1 ? " open" : ""}><summary><b>${esc(s.title)}</b><span class="s">settings</span></summary>`;
      const flat = []; const walk = (o, pre) => { for (const [k, v] of Object.entries(o)) { if (v && typeof v === "object" && !Array.isArray(v) && Object.keys(v).length && pre.split(".").length < 3) walk(v, pre ? `${pre}.${k}` : k); else flat.push([pre ? `${pre}.${k}` : k, v]); } }; walk(s.values, "");
      for (const [k, v] of flat) {
        const key = `${sec}.${k}`, ch = (s.choices || {})[k], tipT = esc((s.tips || {})[k] || (s.tips || {})[k.split(".")[0]] || "");
        let input;
        if (typeof v === "boolean") input = `<button class="tg${v ? " on" : ""}" data-key="${key}" data-kind="bool" title="${tipT}"></button>`;
        else if (ch) input = `<select data-key="${key}" data-kind="choice">${ch.map(([val, lab]) => `<option value="${esc(val)}"${String(val) === String(v) ? " selected" : ""}>${esc(lab)}</option>`).join("")}</select>`;
        else if (typeof v === "number") input = `<input type="number" step="any" value="${v}" data-key="${key}" data-kind="num">`;
        else if (typeof v === "string") input = `<input value="${esc(v)}" data-key="${key}" data-kind="str">`;
        else input = `<textarea data-key="${key}" data-kind="json">${esc(JSON.stringify(v))}</textarea>`;
        out += `<div class="grow" title="${tipT}"><span>${esc(k)}</span>${input}</div>`;
      }
      out += "</details>";
    }
    return out;
  }
  panel.addEventListener("click", async (e) => {
    const b = e.target.closest(".tg[data-key]"); if (b) { const on = !b.classList.contains("on"); const r = await api("settings", { key: b.dataset.key, value: on }).catch(() => null); if (r && r.ok) b.classList.toggle("on", on); else say2((r && r.error) || "That didn't change."); SETTINGS = null; B3 = null; return; }
    const m = e.target.closest("[data-module]"); if (m) { const id = m.dataset.module, on = m.classList.contains("on"); const r = await api(on ? "modules/disable" : "modules/enable", on ? { id } : { ids: [id] }).catch(() => null);
      const ok = r && (on ? r.ok : r.results && r.results[id] && r.results[id].ok), msg = r && (on ? r.message : r.results && r.results[id] && r.results[id].message);
      if (ok) { m.classList.toggle("on", !on); if (ORG[id]) ORG[id].on = !on; SETTINGS = null; if (PANEL === "feature") showFeature(id); } else say2(msg || "That didn't work."); return; }
    const o = e.target.closest("[data-open]"); if (o) { api("open-note", { id: o.dataset.open }).catch(() => {}); return; }
    const f = e.target.closest("[data-feature]"); if (f) { showFeature(f.dataset.feature); }
  });
  panel.addEventListener("change", async (e) => {
    const el = e.target.closest("[data-key]"); if (!el || el.dataset.kind === "bool") return; let v = el.value;
    if (el.dataset.kind === "num") v = Number(v); else if (el.dataset.kind === "json") { try { v = JSON.parse(v); } catch { el.style.borderColor = "#e98f8f"; return; } }
    const r = await api("settings", { key: el.dataset.key, value: v }).catch(() => null); el.style.borderColor = r && r.ok ? P.ink : "#e98f8f"; if (!(r && r.ok)) say2((r && r.error) || "That didn't change."); SETTINGS = null;
  });
  const featureRows = (ids) => ids.filter((id) => ORG[id]).map((id) => `<div class="grow"><span data-feature="${id}" style="cursor:pointer;color:${P.ink}">${esc(ORG[id].title)} ›</span><button class="tg${ORG[id].on ? " on" : ""}" data-module="${id}" title="turn the feature ${ORG[id].on ? "off" : "on"}"></button></div>`).join("");
  let B3 = null; const brain3 = async () => { try { B3 = await api("brain3d"); } catch { B3 = null; } return B3; };
  const partRows = async (ids) => {
    if (!ids.length) return ""; const d = B3 || await brain3(); if (!d) return ""; const comps = {}; for (const isl of d.islands) for (const c of isl.comps) comps[c[0]] = c;
    return ids.filter((id) => comps[id]).map((id) => { const c = comps[id], key = c[5]; const sw = /^mind\.[a-z_.]+$/.test(key) ? `<button class="tg${c[2] ? " on" : ""}" data-key="${key}" title="${esc(c[6])}"></button>` : `<span class="s">${c[2] ? c[3] : "off"}</span>`; return `<div class="grow" title="${esc(c[6])}"><span>${esc(c[1])}</span>${sw}</div>`; }).join("");
  };
  let PICKED = null; // the region, heart part or sense whose features are named on the model
  async function showRegion(k) {
    PICKED = k; const r = REGIONS[k];
    subFocus({ kind: "region", key: k, org: "mind", d: 2.1, pos: () => V(...REGIONS[k].at).add(OFF).applyMatrix4(mind.b.matrixWorld), from: () => wpos(mind.g) }); const pk = Object.keys(PROC).find((x) => PROC[x].at.join() === r.at.join());
    openPanel(`<h2>${esc(r.name)}</h2><div class="s">${esc(r.sub)}${pk ? ` · its sparks are <span style="color:#${new THREE.Color(PROC[pk].c).getHexString()}">${esc(PROC[pk].name)}</span>` : ""}</div>
      ${r.parts.length ? `<h3>Brain parts here</h3>${await partRows(r.parts)}` : ""}${r.feats.some((f) => ORG[f]) ? `<h3>Features here</h3>${featureRows(r.feats)}` : ""}`, "region");
  }
  async function showHeartPart(k) {
    PICKED = k; const r = HEART_PARTS[k];
    subFocus({ kind: "heart", key: k, org: "heart", d: 1.35, pos: () => V(...HEART_PARTS[k].at).applyMatrix4(heart.g.matrixWorld), from: () => wpos(heart.g) }); let live = "";
    if (k === "pacemaker") live = `<div class="grow"><span>rate</span><span>${Math.round(BPM)} a minute (faster when it's busier)</span></div>` + (BODY && BODY.schedule ? BODY.schedule.slice(0, 8).map((s) => `<div class="grow"><span>${new Date(s.when * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span><span>${esc(s.what || s.key || "")}</span></div>`).join("") : "");
    if (k === "ventricles" || k === "atria") { const jobs = (BODY && BODY.jobs || []).filter((j) => k === "ventricles" ? /running|queued/.test(j.status) : /ok|failed/.test(j.status)).slice(0, 10); live = jobs.length ? jobs.map((j) => `<div class="grow"><span>${esc(j.status)}</span><span>${esc((j.title || "").slice(0, 46))}</span></div>`).join("") : `<div class="s">nothing ${k === "ventricles" ? "running or waiting" : "answered lately"}</div>`; }
    if (k === "aorta") live = callRows();
    openPanel(`<h2>${esc(r.name)}</h2><div class="s">${esc(r.sub)}</div>${live ? `<h3>Now</h3>${live}` : ""}${r.feats.some((f) => ORG[f]) ? `<h3>Features</h3>${featureRows(r.feats)}` : ""}${await settingsHTML(r.sections)}`, "heart");
  }
  function callRows() { const L = (BODY && BODY.link) || { off: true }; if (L.off) return `<div class="grow"><span>call line</span><span>Phone calls is off</span></div>`; const calls = (BODY && BODY.calls) || []; return `<div class="grow"><span>call line</span><span>${L.connected ? "connected" : "not connected"}</span></div>${L.beat != null ? `<div class="grow"><span>heartbeat</span><span>${Number(L.beat).toFixed(1)} s ago</span></div>` : ""}<div class="grow"><span>calls booked</span><span>${calls.length ? calls.map((c) => `${new Date(c.when * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} ${esc(c.what)}`).join("<br>") : "none"}</span></div>`; }
  function bars(rows) { return `<div class="gbars">${rows.map(([n, v, txt]) => `<div class="gbar"><em>${esc(n)}</em><i><b style="width:${Math.round(Math.max(0, Math.min(1, v)) * 100)}%;${v > .85 ? "background:#e98f8f" : ""}"></b></i><span>${esc(txt)}</span></div>`).join("")}</div>`; }
  function pcHTML() {
    const s = SYS; if (!s) return `<div class="s">waiting for the first reading</div>`;
    const pct = (v) => `${Math.round((v || 0) * 100)}%`, gb = (b) => ((b || 0) / 1e9).toFixed(1), g = s.gpu && !s.gpu.asleep ? s.gpu : null;
    const rows = [["cpu", s.cpu || 0, pct(s.cpu)], ...(s.cores || []).map((v, i) => [`c${String(i).padStart(2, "0")}`, v, pct(v)]),
      ["mem", s.mem || 0, `${gb(s.mem_used)}/${gb(s.mem_total)} GB`], ["swap", s.swap || 0, pct(s.swap)]];
    if (g) rows.push(["gpu", g.util || 0, `${pct(g.util)}${g.temp != null ? ` ${Math.round(g.temp)}°C` : ""}`]);
    if (g && g.mem_total) rows.push(["vram", (g.mem_used || 0) / g.mem_total, `${gb(g.mem_used)}/${gb(g.mem_total)} GB`]);
    for (const d of (s.disks || []).slice(0, 3)) rows.push([d.mount.length > 5 ? d.mount.slice(-5) : d.mount, d.pct || 0, `${(d.free / 1e9).toFixed(0)} GB free`]);
    if (s.battery) rows.push(["batt", (s.battery.percent || 0) / 100, `${Math.round(s.battery.percent || 0)}%${s.battery.ac ? " charging" : ""}`]);
    const temps = s.temps ? Object.entries(s.temps).slice(0, 4).map(([k, v]) => `${k} ${Math.round(Array.isArray(v) ? Math.max(...v) : v)}°C`).join(" · ") : "";
    return `<div class="pc">${bars(rows)}<div class="s" style="margin-top:8px">${esc(s.cpu_name || "")}${s.load ? ` · load ${s.load.map((x) => Number(x).toFixed(2)).join(" ")}` : ""}${temps ? ` · ${esc(temps)}` : ""}</div></div>`;
  }
  let VOICE = null;
  async function voiceRows() {
    try { VOICE = await api("voice"); } catch { VOICE = null; }
    if (!VOICE || VOICE.error) return `<div class="s">Voice isn't on this install yet (Features → Voice).</div>`;
    const v = VOICE; return `<div class="grow"><span>voice</span><span>${v.on ? esc(v.state || (v.listening ? "listening" : "on")) : "off"}</span></div><div class="grow"><span>listening</span><span>${v.listening ? "yes" : "no"}${v.why ? ` (${esc(v.why)})` : ""}</span></div><div class="grow"><span>portal</span><span>${v.portal ? "open: it's talking with you" : "closed"}</span></div><div class="grow"><span>muted</span><span>${v.muted ? "yes" : "no"}</span></div>${v.speak ? `<div class="grow"><span>speaks with</span><span>${esc(v.speak.engine || "")} ${esc(v.speak.voice || "")}</span></div>` : ""}${v.line ? `<div class="s">${esc(v.line)}</div>` : ""}`;
  }
  async function showSense(k) {
    PICKED = k; const r = SENSES[k];
    subFocus({ kind: "sense", key: k, org: "senses", d: { sight: 2.7, heat: 2.3, touch: 1.9, hearing: 1.8, balance: 1.5 }[k], pos: () => wpos(senses.organs[k]), from: () => wpos(senses.organs[k]).sub(V(0, .25, 1)) }); let live = "";
    if (r.panel === "pc") live = pcHTML();
    if (r.panel === "ear") live = callRows() + await voiceRows();
    if (k === "balance" || k === "touch") live = `<div class="grow"><span>moving</span><span>${SENSE.motion != null ? `${Math.round(SENSE.motion)} min of the last 15` : "no reading"}</span></div><div class="grow"><span>steps</span><span>${SENSE.steps != null ? SENSE.steps : "no reading"}</span></div><div class="grow"><span>screen on</span><span>${SENSE.screen != null ? `${Math.round(SENSE.screen)} min` : "no reading"}</span></div>`;
    live += farRows(k).map(([a, b]) => `<div class="grow"><span>${esc(a)}</span><span>${esc(b)}</span></div>`).join("");
    openPanel(`<h2>${esc(r.name)}</h2><div class="s">${esc(r.sub)}</div>${live ? `<h3>Now</h3>${live}` : ""}${r.parts.length ? `<h3>Brain parts</h3>${await partRows(r.parts)}` : ""}${r.feats.some((f) => ORG[f]) ? `<h3>Features</h3>${featureRows(r.feats)}` : ""}${await settingsHTML(r.sections)}`, r.panel || "sense");
    PANEL_SENSE = k;
  }
  let PANEL_SENSE = null;
  function showHood(k) {
    const h = memory.hoods[k]; if (!h) return; PICKED = null;
    subFocus({ kind: "hood", key: k, org: "memory", d: .75 + 1.6 * Math.sqrt(h.n / Math.max(1, memory.nodes.length)), pos: () => h.centre.clone().applyMatrix4(memory.g.matrixWorld), from: () => wpos(memory.g) });
    const top = memory.nodes.map((n, i) => [n, i]).filter(([, i]) => memory.hood[i] === k).sort((x, y) => memory.deg[y[1]] - memory.deg[x[1]]).slice(0, 12);
    openPanel(`<h2>${esc(h.name)}</h2><div class="s">${h.n} notes · its most linked note is ${esc(h.hub)} (${h.links} links)</div><h3>Most linked</h3>${top.map(([n, i]) => `<div class="grow" data-note="${i}" style="cursor:pointer"><span>${esc(n.title || n.id)}</span><span>${memory.deg[i]} links</span></div>`).join("")}`, "hood");
  }
  async function showOrgan(o) {
    if (o === "mind") openPanel(`<h2>The mind</h2><div class="s">Click a part of the brain to see what it does and its switches; drag the brain to turn it.</div><h3>Regions</h3>${Object.entries(REGIONS).map(([k, r]) => `<div class="grow" data-region="${k}" style="cursor:pointer"><span>${esc(r.name)}</span><span>${esc(r.sub)}</span></div>`).join("")}`, "organ");
    if (o === "heart") openPanel(`<h2>The heart</h2><div class="s">${Math.round(BPM)} a minute. Click a part of it.</div>${Object.entries(HEART_PARTS).map(([k, r]) => `<div class="grow" data-heart="${k}" style="cursor:pointer"><span>${esc(r.name)}</span><span>${esc(r.sub)}</span></div>`).join("")}`, "organ");
    if (o === "senses") openPanel(`<h2>The senses</h2><div class="s">Click an organ: the coil is this computer, the cochlea is hearing (calls, voice).</div>${Object.entries(SENSES).map(([k, r]) => `<div class="grow" data-sense="${k}" style="cursor:pointer"><span>${esc(r.name)}</span><span>${esc(r.sub)}</span></div>`).join("")}`, "organ");
    if (o === "memory") openPanel(`<h2>Memory</h2><div class="s">${memory.nodes.length} notes. Hover a note for its title, click it for a preview.</div><h3>Neighbourhoods</h3>${memory.hoods.map((h) => `<div class="grow" data-hood="${h.key}" style="cursor:pointer"><span>${esc(h.name)}</span><span>${h.n} notes</span></div>`).join("")}<h3>Features</h3>${featureRows(MEMORY_FEATS)}${await settingsHTML(["integrate", "sorter"])}`, "organ");
  }
  panel.addEventListener("click", (e) => { const r = e.target.closest("[data-region]"); if (r) showRegion(r.dataset.region); const h = e.target.closest("[data-heart]"); if (h) showHeartPart(h.dataset.heart); const s = e.target.closest("[data-sense]"); if (s) showSense(s.dataset.sense); const hd = e.target.closest("[data-hood]"); if (hd) showHood(+hd.dataset.hood); const nt = e.target.closest("[data-note]"); if (nt) showNote(memory.nodes[+nt.dataset.note]); });
  async function showFeature(id) {
    const o = ORG[id]; if (!o) return;
    subFocus({ kind: "feature", key: id, org: o.org, d: .85, pos: () => wpos(o.g), from: () => wpos(o.g.parent) }); const c = CELLS.find((x) => x.id === id) || {};
    openPanel(`<h2>${esc(o.title)}</h2><div class="s">${o.org === "mind" ? `in the ${esc(REGIONS[o.part].name.toLowerCase())}` : o.org === "senses" ? `a sense: ${esc(SENSES[o.part].name.toLowerCase())}` : o.org === "memory" ? "memory" : "the heart's upkeep"}${c.events != null ? ` · ${c.events} events lately` : ""}</div>
      <div class="grow"><span>on</span><button class="tg${o.on ? " on" : ""}" data-module="${id}"></button></div>${o.on ? (await settingsHTML([id])) || `<div class="s">It has no settings of its own.</div>` : `<div class="s">Turn it on to change its settings. A feature that needs setting up (an account, a key) opens its steps on the Features page (Alt+F).</div>`}`, "feature");
  }
  async function showNote(n) {
    if (!n) return; const i = memory.nodes.indexOf(n);
    if (i >= 0) subFocus({ kind: "note", key: i, org: "memory", d: .35, pos: () => V(memory.p[i * 3], memory.p[i * 3 + 1], memory.p[i * 3 + 2]).applyMatrix4(memory.g.matrixWorld), from: () => wpos(memory.g) }); openPanel(`<h2>${esc(n.title || n.id)}</h2><div class="s">${esc(n.id)}</div><pre>loading…</pre>${PH ? "" : `<button class="b" data-open="${esc(n.id)}">open it</button>`}`, "note"); // phone: nothing to open it in
    try { const r = await api(`note?id=${encodeURIComponent(n.id)}`); const pre = panel.querySelector("pre"); if (pre) pre.textContent = r.text || ""; } catch { const pre = panel.querySelector("pre"); if (pre) pre.textContent = "(couldn't read it)"; }
  }

  /* ===================== mute, and what you say ===================== */
  async function muteState() { try { const v = await api("voice"); if (v.error) throw 0; VOICE = v; muteB.classList.toggle("on", !!v.muted); muteB.textContent = v.muted ? "● MUTED" : "● MUTE"; muteB.title = v.listening ? "it's listening; mute stops it hearing and speaking" : "Voice isn't listening"; } catch { muteB.title = "Voice isn't on this install yet (Features → Voice)"; muteB.style.opacity = .5; } }
  muteB.onclick = async () => { let r = null; try { r = await api("voice/mute", {}); } catch { /* below */ } if (!r || r.error) { muteB.textContent = "● Voice isn't on this install"; setTimeout(() => (muteB.textContent = "● MUTE"), 2500); return; } muteB.classList.toggle("on", !!r.muted); muteB.textContent = r.muted ? "● MUTED" : "● MUTE"; muteB.title = r.message || ""; };
  muteState();
  async function typed(text, who) { LANES[who === "kurooto" ? "me" : "you"] = { text, s: await shape(text), t: NOW, typed: true }; if (who === "kurooto") mind.fire("speak", NOW, 8); else { senses.hit.hearing = NOW; LIVE.settled = NOW; } } // the talk box (home.js)
  const LANES = { you: null, me: null };
  async function shape(text) { try { const r = await api("voice/shape", { text }); if (r && r.samples) return r.samples; } catch { /* the estimate below */ }
    const out = []; for (const ch of text.toLowerCase()) { const v = "aeiou".includes(ch) ? .85 : "lmnryw".includes(ch) ? .5 : "szfhxc".includes(ch) ? .25 : "pbtdkgq".includes(ch) ? .9 : ch === " " ? .03 : /[.,!?;:]/.test(ch) ? 0 : .3; const n = /[.!?]/.test(ch) ? 12 : 3; for (let i = 0; i < n; i++) out.push(v * (.6 + .4 * Math.sin(Math.PI * (i + .5) / n))); } return out; }
  // the lanes' waveform (0.8.13): a smooth mirrored shape, not bars. A Catmull-Rom curve through the samples, taken
  // every 2 px or so, so a short utterance is a soft shape rather than a few wide blocks; filled with the ink, its top
  // edge stroked a little brighter. Older samples are dimmer, as the bars were: a gradient along x from .3 to 1.
  const INK = (() => { const k = new THREE.Color(P.ink).getHex(); return `${(k >> 16) & 255},${(k >> 8) & 255},${k & 255}`; })();
  const WX = new Float32Array(1600), WY = new Float32Array(1600); // the top edge's points, reused every frame
  const cr = (a, b, p, q, t) => b + .5 * t * (p - a + t * (2 * a - 5 * b + 4 * p - q + t * (3 * (b - p) + q - a)));
  // n samples of src from o (wrapping, so a ring works), the first at xa and the last at xb; the alpha is d at xn (the
  // newest) and falls to .3 of it span px before, holding beyond that
  function wave(c, y, h, src, o, n, xa, xb, xn, span, d) {
    if (n < 1 || d <= 0) return; if (xb - xa < 3) xb = xa + 3; // one sample: a small soft mark, not nothing
    const at = (i) => +src[(o + i) % src.length] || 0, dx = n > 1 ? (xb - xa) / (n - 1) : 0, step = Math.max(2, (xb - xa) / (WX.length - 2));
    let m = 0, u0 = 0;
    for (let x = xa; m < WX.length; x += step) {
      const xe = Math.min(x, xb), u = dx > 0 ? (xe - xa) / dx : 0; let v;
      if (n < 2) v = at(0); else if (dx >= step) { const i = Math.min(n - 2, Math.floor(u)); v = cr(at(Math.max(0, i - 1)), at(i), at(i + 1), at(Math.min(n - 1, i + 2)), Math.min(1, u - i)); }
      else { v = at(Math.min(n - 1, Math.round(u))); for (let k = Math.ceil(u0); k < u; k++) v = Math.max(v, at(k)); } // several samples a step: their loudest
      WX[m] = xe; WY[m++] = Math.max(.5, Math.min(1, v) * h / 2); u0 = u; if (xe >= xb) break;
    }
    const g = c.createLinearGradient(xn - Math.max(1, span), 0, xn, 0), e = c.createLinearGradient(xn - Math.max(1, span), 0, xn, 0);
    g.addColorStop(0, `rgba(${INK},${.3 * d})`); g.addColorStop(1, `rgba(${INK},${d})`); e.addColorStop(0, `rgba(${INK},${Math.min(1, .3 * d + .3)})`); e.addColorStop(1, `rgba(${INK},${Math.min(1, d + .3)})`);
    c.beginPath(); c.moveTo(WX[0], y - WY[0]); for (let k = 1; k < m; k++) c.lineTo(WX[k], y - WY[k]); for (let k = m - 1; k >= 0; k--) c.lineTo(WX[k], y + WY[k]); c.closePath(); c.fillStyle = g; c.fill();
    c.beginPath(); c.moveTo(WX[0], y - WY[0]); for (let k = 1; k < m; k++) c.lineTo(WX[k], y - WY[k]); c.lineWidth = 1; c.lineJoin = "round"; c.strokeStyle = e; c.stroke();
  }
  // the YOU lane, live (look.being_live_waveform, 0.8.13): the microphone's levels as they come (voice_level, five every
  // 100 ms, 50 a second) in a fixed ring, the last 6 seconds across the lane, newest at the right. Each batch is let in
  // over the next 100 ms so the trace scrolls smoothly rather than in steps. When the turn ends (voice_text, voice_heard,
  // or typing) the lane settles into its outline until sound comes again; with no level for 1.5 s the trace fades out.
  // Reduced motion (or Remove animations): it doesn't scroll but sweeps, each value staying where it was drawn.
  const LIVE = { on: opts.liveWave !== false, ring: new Float32Array(320), n: 0, batch: 5, rate: 50, at: -9, loud: -9, settled: -9 }, LIVE_WIN = 300;
  function liveIn(m) {
    if (!LIVE.on || !Array.isArray(m.levels)) return; const r = LIVE.ring; let k = 0;
    for (const x of m.levels) { const v = +x; if (!isFinite(v)) continue; r[LIVE.n++ % r.length] = Math.max(0, Math.min(1, v)); k++; if (v > .4) LIVE.loud = NOW; } // .4: about -36 dB, speech rather than the room
    if (k) { LIVE.batch = Math.min(15, k); LIVE.rate = +m.rate || 50; LIVE.at = NOW; }
  }
  const liveShow = () => { if (!LIVE.on || !LIVE.n) return 0; const age = NOW - LIVE.at; if (age > 1.5 || (LANES.you && LIVE.loud <= LIVE.settled)) return 0; return Math.min(1, (1.5 - age) / .5); };
  const setLive = (v) => { LIVE.on = v !== false; if (!LIVE.on) { LIVE.n = 0; LIVE.ring.fill(0); } };
  function liveWave(c, y, h, x0, x1, d) {
    const R = LIVE.ring, n = LIVE.n, dx = (x1 - x0) / (LIVE_WIN - 1), span = (x1 - x0) / 1.4;
    if (calmEye()) { // a sweep: this pass from the left, the last pass's rest beyond a small gap
      const s = Math.floor((n - 1) / LIVE_WIN) * LIVE_WIN, cur = n - s, gap = 8, old = LIVE_WIN - cur - gap;
      wave(c, y, h, R, s, cur, x0, x0 + (cur - 1) * dx, x0 + cur * dx, span, d);
      if (s > 0 && old > 1) wave(c, y, h, R, n - LIVE_WIN + gap, old, x0 + (cur + gap) * dx, x1, x1 + cur * dx, span, d);
      return;
    }
    const vis = Math.min(n - 1, n - 1 - LIVE.batch + (NOW - LIVE.at) * LIVE.rate), top = Math.floor(vis); // the head, let in over 100 ms
    if (top < 0) return; const first = Math.max(0, top - (LIVE_WIN - 2)), xb = x1 - (vis - top) * dx;
    wave(c, y, h, R, first, top - first + 1, xb - (top - first) * dx, xb, x1, span, d);
  }
  function lane(c, y, h, L, lab, sub, live) {
    const x0 = UI ? UI.x0 : 40, x1 = W - (UI ? UI.x0 : opts.talkWidth || 190); /* phone: edge to edge */ c.font = "600 10px Inter,sans-serif"; c.fillStyle = P.mute; c.fillText(lab, x0, y - h / 2 - 8); c.font = "400 10px Inter,sans-serif"; c.fillText(sub, x0 + 74, y - h / 2 - 8);
    c.globalAlpha = .15; c.fillStyle = P.ink; c.fillRect(x0, y, x1 - x0, 1); c.globalAlpha = 1;
    if (live > 0) { liveWave(c, y, h, x0, x1, live); return; } if (!L) return;
    const S = L.s, N = S.length, prog = Math.min(1, (NOW - L.t) / Math.max(1.2, N / 50)), shown = Math.floor(N * prog), dx = (x1 - x0) / Math.max(N, 120);
    const dim = L.heard ? .45 : 1; // heard, not to Kurooto: fainter
    if (shown) wave(c, y, h, S, 0, shown, x0, x0 + (shown - 1) * dx, x0 + shown * dx, N * dx / 1.4, dim);
  }

  /* ===================== the live stream ===================== */
  let BODY = null, built = false;
  // Resting activity (look.being_resting_sparks, 0.8.11): a low trickle of sparks from what Kurooto does all the time,
  // never made up: each reading of its body (the live stream's vitals, every 2 s) is a spark in the insula, and one more
  // for each quarter of the processor in use; its own processes' processor use keeps the thalamus going in proportion; a
  // scheduler timer that fired lights the region of its feature; notes that changed the hippocampus; sound heard the
  // auditory cortex. Off with Remove animations or the system's reduced motion.
  const REST = { on: false, own: 0, acc: 0, heard: 0, when: new Map() };
  const setRest = (v) => { REST.on = v !== false && !STILL && !(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches); };
  setRest(opts.restSparks);
  const procOfFeature = (id) => { const [org, part] = homeOf(id || ""); if (org === "mind") return procOf(part) || "think"; if (org === "memory") return "memory"; if (org === "senses") return { hearing: "hear", sight: "see", heat: "feel" }[part] || "touch"; return "plan"; };
  function resting(m) {
    if (!REST.on) return;
    mind.fire("feel", NOW, 1 + Math.round(4 * Math.min(1, (m.sys && +m.sys.cpu) || 0)));
    const cores = (m.sys && m.sys.cores && m.sys.cores.length) || 1; // procs' cpu is a share of the whole machine
    if (m.procs) REST.own = m.procs.filter((p) => p.own).reduce((a, p) => a + (+p.cpu || 0), 0) * cores;
    const now = Date.now() / 1000;
    for (const s of m.schedule || []) { const k = s.key || s.what, was = REST.when.get(k); if (was != null && s.when > was && was <= now + 2) mind.fire(procOfFeature(s.module), NOW, 3); REST.when.set(k, s.when); }
  }
  ticks.push((t, dt) => { if (!REST.on) return; REST.acc += dt * Math.min(3, REST.own * 3); while (REST.acc >= 1) { REST.acc--; mind.fire("attend", t, 1); } }); // a whole core busy: 3 a second
  // Brain's status (0.8.14): what's pushed ({t:"mind", kind:"status"}, GET /api/mind/status, the phone's "mind" block)
  const UNEASY = document.createElement("button"); UNEASY.type = "button"; UNEASY.className = "uneasy";
  UNEASY.style.cssText = "position:absolute;z-index:3;display:none;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;border:0;background:transparent;cursor:pointer;padding:0";
  host.append(UNEASY);
  UNEASY.addEventListener("click", (e) => { e.stopPropagation(); const it = ST.item; if (opts.openItem && it) opts.openItem(it); else if (ST.uneasy && ST.uneasy.startsWith("deadline:") && ORG.deadlines) showFeature("deadlines"); });
  function status(m) {
    if (!m) return;
    const was = ST.uneasy;
    for (const k of ["focus", "asleep", "held", "uneasy", "mood", "arousal"]) if (k in m) ST[k] = m[k];
    if (m.knobs) ST.knobs = m.knobs;
    if (m.look) ST.look = m.look;
    ST.on = m.on !== false;
    if ("uneasy_item" in m) ST.item = m.uneasy_item || null; else if ("uneasy_title" in m) ST.item = m.uneasy_title ? { title: m.uneasy_title } : null; else if (ST.uneasy !== was) ST.item = null;
    ST.arousal = Math.max(0, Math.min(1, +ST.arousal || 0)); ST.held = Math.max(0, ST.held | 0);
    const title = ST.item && ST.item.title ? ` (${ST.item.title})` : "";
    UNEASY.title = `uneasy about this${title}: tap to open it`; UNEASY.setAttribute("aria-label", UNEASY.title);
    if (OM) organDirty();
  }
  // where the uneasy glow sits: the deadline's point of light, the conscience for a promise, a note in memory
  function uneasyAt() {
    const u = ST.uneasy; if (!glance() || !u) return null;
    const [kind, key] = [u.slice(0, u.indexOf(":")), u.slice(u.indexOf(":") + 1)];
    if (kind === "deadline" && ORG.deadlines) return ORG.deadlines.g.getWorldPosition(V(0, 0, 0));
    if (kind === "note") { const i = memory.nodes.findIndex((n) => n.id === key); if (i >= 0 && memory.p) return V(memory.p[i * 3], memory.p[i * 3 + 1], memory.p[i * 3 + 2]).applyMatrix4(memory.g.matrixWorld); }
    return V(...REGIONS.conscience.at).add(OFF).applyMatrix4(mind.b.matrixWorld);
  }
  // the mood in the drawing eases in over a few seconds: low only dims and softens, high warms a little
  ticks.push((t, dt) => {
    const on = moodOn(), low = on && ST.mood === "low", high = on && ST.mood === "high", e = STILL ? 1 : Math.min(1, dt * .6);
    ST.fogK += ((low ? .7 : high ? 1.08 : 1) - ST.fogK) * e; ST.warm += ((high ? .18 : 0) - ST.warm) * e; ST.moodK += ((low ? .75 : 1) - ST.moodK) * e;
    const ex = on && ST.knobs.explore != null ? +ST.knobs.explore : 1, unsure = on && ST.knobs.uncertainty != null && ST.knobs.uncertainty >= .25;
    ST.dil += ((on ? (ex - 1) * .08 - (unsure ? .03 : 0) : 0) - ST.dil) * e;
  });
  // the glance, over the drawing: the held count by the heart, the uneasy glow (its button follows it for the tap)
  function glanceDraw(c) {
    const show = (org) => !OM ? !FOCUS || FOCUS === org : ONLY === org;
    if (glance() && ST.held > 0 && show("heart")) {
      const [x, y, z] = proj(HEART_C.clone().add(V(.55, -.45, 0))); if (z < 1) {
        c.save(); c.globalAlpha = .9; c.fillStyle = P.bg; c.strokeStyle = P.mute; c.lineWidth = 1; c.beginPath(); c.arc(x, y, 9, 0, 6.2832); c.fill(); c.stroke();
        c.fillStyle = P.ink; c.font = "600 10px Inter,sans-serif"; c.textAlign = "center"; c.fillText(String(Math.min(99, ST.held)), x, y + 3.5);
        c.textAlign = "left"; c.fillStyle = P.mute; c.font = "400 9.5px Inter,sans-serif"; c.fillText("held", x + 13, y + 3); c.restore();
      }
    }
    const q = uneasyAt(), org = ST.uneasy && ST.uneasy.startsWith("note:") ? "memory" : ST.uneasy && ST.uneasy.startsWith("deadline:") ? (ORG.deadlines ? ORG.deadlines.org : "heart") : "mind";
    if (!q || !show(org)) { UNEASY.style.display = "none"; return; }
    const [x, y, z] = proj(q); if (z > 1) { UNEASY.style.display = "none"; return; }
    const k = STILL ? .7 : .55 + .35 * Math.sin(NOW * 1.3); // slow: about one breath in five seconds
    const g = c.createRadialGradient(x, y, 0, x, y, 18); g.addColorStop(0, `rgba(240,200,140,${(.55 * k).toFixed(3)})`); g.addColorStop(1, "rgba(240,200,140,0)");
    c.save(); c.fillStyle = g; c.beginPath(); c.arc(x, y, 18, 0, 6.2832); c.fill(); c.restore();
    UNEASY.style.display = "block"; UNEASY.style.left = `${x}px`; UNEASY.style.top = `${y}px`;
  }
  function update(m) {
    BODY = m; SYS = m.sys || SYS; CELLS = m.cells || CELLS; placeFeatures(CELLS); resting(m);
    if (PANEL === "pc" && PANEL_SENSE === "heat") { const live = panel.querySelector(".pc"); if (live) live.outerHTML = pcHTML(); }
  }
  function event(e) {
    const t = NOW, k = KIND[e.kind]; recent.push(performance.now()); if (OM && k) KREC.push([performance.now(), k]); const col = k ? new THREE.Color(PROC[k].c) : new THREE.Color(P.a);
    if (k) {
      mind.fire(k, t, ["memory", "speak", "hear", "touch", "feel", "see"].includes(k) ? 3 : k === "hold" ? 3 : 10);
      const ven = col.clone().lerp(new THREE.Color(P.back ?? P.a), .5).multiplyScalar(.55); // returning blood leans blue
      if (k === "think" || k === "plan" || k === "conscience" || k === "act") FLOW.push([PATHS.mind.cu, t, 1.1, col, 0]);
      if (k === "memory") { FLOW.push([PATHS.memory.cu, t, 1.1, col, 0], [PATHS.memory.cu, t + 1.2, 1.1, ven, 1], [NERVES.memory, t + .2, .5, col, 1], [NERVES.memory, t + .9, .5, col, 0]); if (memory.a) { const n = memory.a.length, c = (rnd() * n) | 0; for (let i = 0; i < 28; i++) fires.push([(c + ((gauss() * 30) | 0) + n * 4) % n, t + rnd() * .35]); } }
      if (k === "hear" || k === "touch") { FLOW.push([NERVES.senses, t, .5, col, 0], [PATHS.senses.cu, t + .4, 1, ven, 1]); senses.hit[k === "hear" ? "hearing" : "touch"] = t; }
      if (k === "feel") { FLOW.push([PATHS.s_heat.cu, t, 1, col, 0]); senses.hit.heat = t; }
      if (k === "attend" || k === "act" || k === "see") senses.hit.sight = t;
      if (k === "see") FLOW.push([NERVES.senses, t, .5, col, 0], [PATHS.senses.cu, t + .4, 1, ven, 1]); // Face presence: sight's nerve
      if (e.kind === "job_done") FLOW.push([PATHS.mind.cu, t + .2, 1.1, ven, 1], [NERVES.heart, t, .45, col, 1]);
    }
    if (e.kind === "face_watch") SENSE.face = !!e.on; // the camera open: the eye's pupil a little wider
    if (e.kind === "senses_phone" && e.sensor) SENSE[String(e.sensor).replace("phone:", "")] = e.value;
    const id = EV_FEATURE[e.kind], o = id && ORG[id];
    if (o) { o.flash = t; const w = o.g.getWorldPosition(V(0, 0, 0)), mid = HEART_C.clone().lerp(w, .5).add(V(gauss() * .3, .3, .2)), cv = new THREE.CatmullRomCurve3([HEART_C.clone(), mid, w]); FLOW.push([cv, t, .9, new THREE.Color(o.col), 0]); if (RETURNS.has(e.kind)) FLOW.push([cv, t + 1.1, .9, new THREE.Color(o.col).lerp(new THREE.Color(P.back ?? P.a), .5).multiplyScalar(.55), 1]); }
  }
  function graph(g) { if (memory.nodes.length && REST.on) mind.fire("memory", NOW, 3); memory.build(g); } // a note changed
  async function voice(m) {
    if (m.kind === "voice_text") { const s = await shape(m.text || ""); LANES[m.who === "you" ? "you" : "me"] = { text: m.text, s, t: NOW }; if (m.who === "you") { senses.hit.hearing = NOW; LIVE.settled = NOW; } else { mind.fire("speak", NOW, 8); } }
    if (m.kind === "voice_speak" && m.samples) LANES.me = { text: "", s: m.samples, t: NOW };
    // speech heard that wasn't a turn (chatter, or not to it): only its loudness, never words; drawn dimmer
    if (m.kind === "voice_heard" && Array.isArray(m.samples) && m.samples.length) { LANES.you = { text: "", s: m.samples.slice(0, 120).map((x) => Math.max(0, Math.min(1, +x || 0))), t: NOW, heard: true }; senses.hit.hearing = NOW; LIVE.settled = NOW; }
    if (m.kind === "voice_state") muteState();
    if (m.kind === "voice_level" && m.levels) { liveIn(m); senses.level = Math.max(senses.level || 0, ...m.levels.map(Number).filter(isFinite)); if (REST.on && senses.level > .15 && NOW - REST.heard > .4) { REST.heard = NOW; mind.fire("hear", NOW, 1); } }
  }
  function face(m) { // Face presence (t:"face"): where faces are in the camera's frame (places, an owner flag), nothing else
    if (!m) return;
    const cl = (v) => Math.max(-1, Math.min(1, +v)), now = performance.now();
    if (m.kind === "face_seen" && m.owner && Number.isFinite(+m.x) && Number.isFinite(+m.y)) { GAZE.x = cl(m.x); GAZE.y = cl(m.y); GAZE.at = now; }
    if (m.kind === "camera" && !m.on) { ATT.faces.clear(); ATT.at = 0; }
    if (m.kind !== "faces" || !Array.isArray(m.faces)) return;
    const next = new Map(), had = ATT.faces.size;
    for (const f of m.faces.slice(0, 16)) {
      if (!f || !Number.isFinite(+f.x) || !Number.isFinite(+f.y)) continue;
      const id = String(f.id), old = ATT.faces.get(id), o = { id, x: cl(f.x), y: cl(f.y), m: Math.max(0, Math.min(1, +f.m || 0)), owner: !!f.owner };
      o.px = old ? old.x : o.x; o.py = old ? old.y : o.y; o.m0 = old ? old.m : 0; next.set(id, o);
      if (!ATT.known.has(id)) { ATT.known.add(id); if (had) ATT.fresh = id; }
    }
    if (ATT.known.size > 500) ATT.known = new Set(next.keys());
    if (next.size === 1) { const o = [...next.values()][0]; if (o.m - o.m0 > .12 || (o.m > .35 && now - ATT.spike > 300)) { ATT.spike = now; GAZE.fast = now + 120; } } // a quick small saccade toward a movement
    ATT.faces = next; ATT.at = now;
  }
  // Another device an add-on reports for (t:"senses", mind/stimulation.py feed): its numbers, kept apart from your
  // phone's SENSE; each message may carry a few readings, so they're merged over the last ones from the same device,
  // and all let go 30 s after its last message. Being picked up flinches the cilia.
  function far(m) {
    if (!m || !m.channels || typeof m.channels !== "object") return; const src = String(m.source || "another device").slice(0, 30);
    const was = FAR && FAR.src === src && farOn() ? FAR : { r: {}, c: {} };
    FAR = { src, r: { ...was.r, ...(m.readings || {}) }, c: { ...was.c, ...m.channels }, at: performance.now() };
    if ((+m.channels.handled || 0) > (+was.c.handled || 0)) senses.hit.touch = NOW;
  }
  const farOn = () => !!FAR && performance.now() - FAR.at < 30000;
  function fc(k) { if (!farOn()) return null; const v = +FAR.c[k]; return FAR.c[k] != null && Number.isFinite(v) ? v : null; }
  function farRows(k) { // [name, words] for the senses' panels
    if (!farOn()) return []; const r = FAR.r, c = FAR.c, n = (v, d = 0) => Number(v).toFixed(d), rows = [];
    if (k === "sight") { if (r.light_lux != null) rows.push(["light", `${n(r.light_lux)} lux`]); if (c.eyes != null) rows.push(["its eyes", c.eyes ? "open" : "shut (screen off)"]); }
    if (k === "touch") { if (c.closeness != null) rows.push(["something near", c.closeness > .5 ? "yes" : "no"]); if (c.handled != null) rows.push(["picked up", c.handled ? "yes" : "no"]); }
    if (k === "balance") { if (c.sway != null) rows.push(["moved", `${n(c.sway, 2)} m/s²`]); if (c.tilt != null) rows.push(["tilt", `${n(c.tilt)}°`]); if (c.turning != null) rows.push(["turning", `${n(c.turning, 2)} rad/s`]); if (r.heading_deg != null) rows.push(["heading", `${n(((+r.heading_deg % 360) + 360) % 360)}°`]); }
    if (k === "hearing" && c.loudness != null) rows.push(["the room", `${n(c.loudness)} dB`]);
    if (k === "heat") { if (c.temperature != null) rows.push(["its temperature", `${n(c.temperature, 1)}°C`]); if (r.battery_pct != null) rows.push(["its battery", `${n(r.battery_pct)}%${r.charging ? ", charging" : ""}`]); }
    return rows.map(([a, b]) => [`${FAR.src}: ${a}`, b]);
  }
  async function body(b) { // GET /api/body (0.8.8 stimulation): the phone's latest readings for the senses
    const ch = (b && b.regions && b.regions.hands && b.regions.hands.channels) || {}; if (ch.motion) SENSE.motion = 15 * ch.motion.intensity;
  }

  /* ===================== the phone's organ pages (opts.only, 0.8.10) ===================== */
  // The app (ViewsTab) lists the organ's parts natively, each with its live state, and the part picked in full: state()
  // is that as plain data (made again each second, and at once when something is picked), rev() says when it changed.
  // What the app calls back: pick(kind, key), setting(key, value), feature(id, on), mode(m), only(page).
  const PAGE_OF = { mind: "brain", heart: "heart", senses: "senses", memory: "memory" };
  const KREC = [], NOTE_TXT = new Map(); let OSTATE = "{}", OREV = 0, ODIRTY = true, OBUSY = false, OTICK = 0, SAID = "", OTIMER = 0;
  function organDirty() { ODIRTY = true; }
  const procOf = (k) => Object.keys(PROC).find((x) => PROC[x].at.join() === REGIONS[k].at.join());
  const hhmm = (s) => new Date(s * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const pctOf = (v) => `${Math.round((v || 0) * 100)}%`;
  // the features whose light is on this part (as placeFeatures put them: the ones with no home are the coronaries')
  const featsAt = (org, part) => Object.keys(ORG).filter((id) => ORG[id].org === org && String(ORG[id].part) === String(part)).map((id) => ({ id, title: ORG[id].title, on: !!ORG[id].on }));
  async function brainParts(ids) {
    if (!ids.length) return []; const d = B3 || await brain3(); if (!d) return []; const comps = {}; for (const isl of d.islands) for (const c of isl.comps) comps[c[0]] = c;
    return ids.filter((id) => comps[id]).map((id) => { const c = comps[id]; return { name: c[1], on: !!c[2], state: c[2] ? String(c[3] || "on") : "off", key: /^mind\.[a-z_.]+$/.test(c[5]) ? c[5] : "" }; });
  }
  async function settingRows(sections) { // as settingsHTML walks them: a switch for each yes or no, the rest as words
    const S = sections.length ? await getSettings().catch(() => null) : null; if (!S) return [];
    const out = [];
    for (const sec of sections) {
      const s = (S.sections || []).find((x) => x.section === sec); if (!s) continue;
      const flat = []; const walk = (o, pre) => { for (const [k, v] of Object.entries(o)) { if (v && typeof v === "object" && !Array.isArray(v) && Object.keys(v).length && pre.split(".").length < 3) walk(v, pre ? `${pre}.${k}` : k); else flat.push([pre ? `${pre}.${k}` : k, v]); } }; walk(s.values, "");
      for (const [k, v] of flat) {
        const ch = (s.choices || {})[k], lab = ch && ch.find((c) => String(c[0]) === String(v));
        out.push({ key: `${sec}.${k}`, group: s.title, name: k, bool: typeof v === "boolean", on: v === true, value: typeof v === "boolean" ? "" : lab ? String(lab[1]) : v && typeof v === "object" ? JSON.stringify(v) : String(v ?? "") });
      }
    }
    return out;
  }
  const jobsOf = (k) => ((BODY && BODY.jobs) || []).filter((j) => (k === "ventricles" ? /running|queued/ : /ok|failed/).test(j.status));
  const linkOf = () => (BODY && BODY.link) || { off: true };
  const voiceNow = () => { const v = VOICE; return !v || v.error ? "Voice isn't on" : !v.on ? "off" : v.muted ? "muted" : v.state || (v.listening ? "listening" : "on"); };
  const hottest = () => { const t = SYS && SYS.temps ? Object.values(SYS.temps).flat().map(Number).filter(isFinite) : []; return t.length ? Math.round(Math.max(...t)) : null; };
  function partLive(kind, k) {
    if (kind === "region") {
      const r = REGIONS[k], pk = procOf(k), n = pk ? KREC.filter((x) => x[1] === pk).length : 0, f = featsAt("mind", k), on = f.filter((x) => x.on).length;
      return [n ? `${n} sparks lately` : "", f.length ? `${on} of ${f.length} features on` : "", r.parts.length ? `${r.parts.length} Brain parts` : ""].filter(Boolean).join(" · ") || "quiet";
    }
    if (kind === "heart") {
      if (k === "pacemaker") return `${Math.round(BPM)} a minute`;
      if (k === "ventricles") { const n = jobsOf(k).length; return n ? `${n} running or waiting` : "nothing running"; }
      if (k === "atria") { const n = jobsOf(k).length; return n ? `${n} answered lately` : "nothing answered lately"; }
      if (k === "aorta") { const L = linkOf(); return L.off ? "Phone calls is off" : L.connected ? "call line connected" : "call line not connected"; }
      const f = featsAt("heart", k), on = f.filter((x) => x.on).length; return f.length ? `${on} of ${f.length} features on` : "quiet";
    }
    if (k === "hearing") return voiceNow();
    if (k === "touch") return SENSE.screen != null ? `screen on ${Math.round(SENSE.screen)} min` : "no reading from your phone";
    if (k === "balance") return SENSE.motion != null ? `moving ${Math.round(SENSE.motion)} min of the last 15` : "no reading from your phone";
    if (k === "heat") { const t = hottest(); return SYS ? `processor ${pctOf(SYS.cpu)}${t != null ? ` · ${t}°C` : ""}` : "waiting for the first reading"; }
    const f = featsAt("senses", k), on = f.filter((x) => x.on).length; return SENSE.face ? "watching for your face" : f.length ? `${on} of ${f.length} features on` : "quiet";
  }
  function heartRows(k) {
    if (k === "pacemaker") return [["rate", `${Math.round(BPM)} a minute (faster when it's busier)`]].concat(((BODY && BODY.schedule) || []).slice(0, 8).map((s) => [hhmm(s.when), String(s.what || s.key || "")]));
    if (k === "ventricles" || k === "atria") { const j = jobsOf(k).slice(0, 10); return j.length ? j.map((x) => [String(x.status), String(x.title || "").slice(0, 60)]) : [["now", k === "ventricles" ? "nothing running or waiting" : "nothing answered lately"]]; }
    if (k === "aorta") return callRowsOf();
    return [];
  }
  function callRowsOf() {
    const L = linkOf(); if (L.off) return [["call line", "Phone calls is off"]];
    const calls = (BODY && BODY.calls) || [];
    return [["call line", L.connected ? "connected" : "not connected"]].concat(L.beat != null ? [["heartbeat", `${Number(L.beat).toFixed(1)} s ago`]] : [], [["calls booked", calls.length ? calls.map((c) => `${hhmm(c.when)} ${c.what}`).join(", ") : "none"]]);
  }
  async function senseRows(k) {
    if (k === "hearing") {
      try { VOICE = await api("voice"); } catch { VOICE = null; }
      const v = VOICE, rows = callRowsOf();
      if (!v || v.error) return rows.concat([["voice", "Voice isn't on this install yet"]]);
      return rows.concat([["voice", v.on ? String(v.state || (v.listening ? "listening" : "on")) : "off"], ["listening", `${v.listening ? "yes" : "no"}${v.why ? ` (${v.why})` : ""}`], ["portal", v.portal ? "open: it's talking with you" : "closed"], ["muted", v.muted ? "yes" : "no"]], v.speak ? [["speaks with", `${v.speak.engine || ""} ${v.speak.voice || ""}`.trim()]] : []);
    }
    if (k === "touch" || k === "balance") return [["moving", SENSE.motion != null ? `${Math.round(SENSE.motion)} min of the last 15` : "no reading"], ["steps", SENSE.steps != null ? String(SENSE.steps) : "no reading"], ["screen on", SENSE.screen != null ? `${Math.round(SENSE.screen)} min` : "no reading"]];
    if (k === "heat") { const s = SYS; if (!s) return [["now", "waiting for the first reading"]]; const t = hottest(); return [["processor", String(s.cpu_name || "")], ["load", s.load ? s.load.map((x) => Number(x).toFixed(2)).join(" ") : ""]].concat(t != null ? [["hottest", `${t}°C`]] : []).filter((r) => r[1]); }
    return SENSE.face != null ? [["your face", SENSE.face ? "the camera is watching for it" : "not watching"]] : [];
  }
  function sysBars() { // the coil's bars, as pcHTML draws them: [name, 0..1, words]
    const s = SYS; if (!s) return []; const gb = (b) => ((b || 0) / 1e9).toFixed(1), g = s.gpu && !s.gpu.asleep ? s.gpu : null;
    const rows = [["cpu", s.cpu || 0, pctOf(s.cpu)], ["mem", s.mem || 0, `${gb(s.mem_used)}/${gb(s.mem_total)} GB`], ["swap", s.swap || 0, pctOf(s.swap)]];
    if (g) rows.push(["gpu", g.util || 0, `${pctOf(g.util)}${g.temp != null ? ` ${Math.round(g.temp)}°C` : ""}`]);
    if (g && g.mem_total) rows.push(["vram", (g.mem_used || 0) / g.mem_total, `${gb(g.mem_used)}/${gb(g.mem_total)} GB`]);
    for (const d of (s.disks || []).slice(0, 3)) rows.push([d.mount, d.pct || 0, `${(d.free / 1e9).toFixed(0)} GB free`]);
    if (s.battery) rows.push(["battery", (s.battery.percent || 0) / 100, `${Math.round(s.battery.percent || 0)}%${s.battery.ac ? " charging" : ""}`]);
    return rows.map(([n, v, w]) => ({ name: String(n), v: Math.max(0, Math.min(1, +v || 0)), text: w }));
  }
  function noteText(id) {
    if (NOTE_TXT.has(id)) return NOTE_TXT.get(id);
    NOTE_TXT.set(id, "loading…");
    api(`note?id=${encodeURIComponent(id)}`).then((r) => NOTE_TXT.set(id, (r && r.text) || "")).catch(() => NOTE_TXT.set(id, "(couldn't read it)")).finally(organDirty);
    return "loading…";
  }
  async function detail(s) {
    const k = s.key;
    if (s.kind === "region") { const r = REGIONS[k], pk = procOf(k); return { title: r.name, sub: r.sub + (pk ? ` · its sparks are ${PROC[pk].name}` : ""), rows: [], parts: await brainParts(r.parts), feats: featsAt("mind", k), settings: [] }; }
    if (s.kind === "heart") { const r = HEART_PARTS[k]; return { title: r.name, sub: r.sub, rows: heartRows(k), parts: [], feats: featsAt("heart", k), settings: await settingRows(r.sections) }; }
    if (s.kind === "sense") { const r = SENSES[k]; return { title: r.name, sub: r.sub, rows: (await senseRows(k)).concat(farRows(k)), bars: k === "heat" ? sysBars() : [], parts: await brainParts(r.parts), feats: featsAt("senses", k), settings: await settingRows(r.sections) }; }
    if (s.kind === "hood") {
      const h = memory.hoods[k]; if (!h) return null;
      const top = memory.nodes.map((n, i) => [n, i]).filter(([, i]) => memory.hood[i] === k).sort((x, y) => memory.deg[y[1]] - memory.deg[x[1]]).slice(0, 12);
      return { title: h.name, sub: `${h.n} notes · its most linked note is ${h.hub} (${h.links} links)`, notes: top.map(([n, i]) => ({ key: String(i), title: n.title || n.id, links: memory.deg[i] })) };
    }
    if (s.kind === "note") { const n = memory.nodes[k]; return n ? { title: n.title || n.id, sub: n.id, text: noteText(n.id) } : null; }
    if (s.kind === "feature") {
      const f = ORG[k]; if (!f) return null; const c = CELLS.find((x) => x.id === k) || {};
      const where = f.org === "mind" ? `in the ${REGIONS[f.part].name.toLowerCase()}` : f.org === "senses" ? `a sense: ${SENSES[f.part].name.toLowerCase()}` : f.org === "memory" ? "memory" : "the heart's upkeep";
      return { title: f.title, sub: where + (c.events != null ? ` · ${c.events} events lately` : ""), feature: { id: k, on: !!f.on }, settings: f.on ? await settingRows([k]) : [] };
    }
    return null;
  }
  // the organ pages' status line (the app shows it under the organ's name): enums in words, never how you are
  function mindLine() {
    if (!glance()) return "";
    const bits = [];
    if (ST.asleep) bits.push("asleep, eyes shut"); else if (ST.focus) bits.push("eyes shut: focus time");
    if (ST.held) bits.push(`${ST.held} held`);
    if (ST.uneasy) bits.push(`uneasy about ${(ST.item && ST.item.title) || (ST.uneasy.startsWith("deadline:") ? "a deadline" : ST.uneasy.startsWith("note:") ? "a note" : "a promise")}`);
    if (moodOn() && ST.mood !== "mid") bits.push(ST.mood === "low" ? "quieter today" : "bright today");
    return bits.join(" · ");
  }
  async function describe() {
    const o = ONLY; while (KREC.length && performance.now() - KREC[0][0] > 600000) KREC.shift();
    let parts = [];
    if (o === "mind") parts = Object.entries(REGIONS).map(([k, r]) => ({ kind: "region", key: k, name: r.name, sub: r.sub, live: partLive("region", k) }));
    if (o === "heart") parts = Object.entries(HEART_PARTS).map(([k, r]) => ({ kind: "heart", key: k, name: r.name, sub: r.sub, live: partLive("heart", k) }));
    if (o === "senses") parts = Object.entries(SENSES).map(([k, r]) => ({ kind: "sense", key: k, name: r.name, sub: r.sub, live: partLive("sense", k) }));
    if (o === "memory") parts = memory.hoods.filter((h) => h.n > 0).sort((x, y) => y.n - x.n).slice(0, 40).map((h) => ({ kind: "hood", key: String(h.key), name: h.name, sub: `most linked: ${h.hub}`, live: `${h.n} notes` }));
    const head = { mind: `${recent.length} ${recent.length === 1 ? "event" : "events"} in 10 minutes · ${Math.round(BPM)} a minute`, heart: `${Math.round(BPM)} a minute: faster when it's busier`, senses: "sight, hearing, touch, balance, its own body", memory: `${memory.nodes.length} notes · they light up as they link` }[o];
    const sel = SUB ? { kind: SUB.kind, key: String(SUB.key) } : null;
    return { page: PAGE_OF[o], head, mode: mind.mode, sel, parts, detail: SUB ? await detail(SUB) : null, feats: o === "memory" && !SUB ? featsAt("memory", null) : [], said: SAID, mind: mindLine(), uneasy: glance() && ST.uneasy ? { id: ST.uneasy, title: (ST.item && ST.item.title) || "" } : null };
  }
  async function organTick() {
    if (OBUSY) return; OBUSY = true; ODIRTY = false;
    try { const j = JSON.stringify(await describe()); if (j !== OSTATE) { OSTATE = j; OREV++; } } catch (err) { console.error("the organ page", err); } finally { OBUSY = false; }
  }
  if (OM) OTIMER = setInterval(() => { if (ODIRTY || ++OTICK % 4 === 0) organTick(); }, 250);
  function pick(kind, key) {
    SAID = "";
    if (kind === "region" && REGIONS[key]) showRegion(key);
    else if (kind === "heart" && HEART_PARTS[key]) showHeartPart(key);
    else if (kind === "sense" && SENSES[key]) showSense(key);
    else if (kind === "hood" && memory.hoods[+key]) showHood(+key);
    else if (kind === "note" && memory.nodes[+key]) { NOTE_TXT.delete(memory.nodes[+key].id); showNote(memory.nodes[+key]); }
    else if (kind === "feature" && ORG[key] && ORG[key].org === ONLY) showFeature(key);
    else if (SUB) back();
    organDirty(); return true;
  }
  async function setting(key, value) {
    const r = await api("settings", { key, value }).catch(() => null);
    SAID = r && r.ok ? "" : (r && r.error) || "That didn't change."; SETTINGS = null; B3 = null; organDirty(); return !!(r && r.ok);
  }
  async function feature(id, on) {
    const r = await api(on ? "modules/enable" : "modules/disable", on ? { ids: [id] } : { id }).catch(() => null);
    const ok = r && (on ? r.results && r.results[id] && r.results[id].ok : r.ok), msg = r && (on ? r.results && r.results[id] && r.results[id].message : r.message);
    if (ok && ORG[id]) ORG[id].on = on; SAID = ok ? "" : msg || "That didn't work."; SETTINGS = null; organDirty(); return !!ok;
  }
  function only(page) {
    const o = PAGE_ORGAN[page]; if (!o) return false;
    const was = ONLY; ONLY = o; PICKED = null; PANEL = null; spinning.obj = null; SAID = "";
    if ((was === "memory") !== (o === "memory")) size(); // the Memory page's own density
    for (const [k, g] of Object.entries(ORGAN_OBJ)) g.visible = k === o;
    for (const l of LINKS) l.visible = false;
    if (o === "mind") setMode("solid");
    if (o === "mind") mind.g.rotation.set(0, 0, 0); // it turned by itself while another page showed
    focusOn(o); goal.th = HOME.th + (ONLY_TH[o] || 0); goal.ph = HOME.ph;
    Object.assign(view, goal); if (!STILL) view.d = goal.d * 1.35; // it settles in from a little further off, never across the body
    for (const k of Object.keys(TARGETS)) OPEN[k] = k === o ? 1 : 0;
    organDirty(); return true;
  }
  if (OM) only(opts.only);

  /* ===================== the loop ===================== */
  const c2 = ov.getContext("2d"); let last = performance.now(), dead = false, t0 = performance.now();
  const proj = (v) => { const p = v.clone().project(cam); return [(p.x + 1) / 2 * W, (1 - p.y) / 2 * H, p.z]; };
  function tag(v, dx, dy, title, sub, alpha, mine) {
    if (!HINTS) sub = "";
    const [x, y, z] = proj(v); if (z > 1) return;
    if (UI) return UI.tag(c2, x, y, dx, dy, title, sub, alpha ?? 1, mine, W, H, P); // phone: shorter leads, larger words
    const lx = x + dx, ly = y + dy; c2.save(); c2.globalAlpha = alpha ?? 1; c2.strokeStyle = P.mute; c2.beginPath(); c2.moveTo(x, y); c2.lineTo(x + dx * .35, ly); c2.lineTo(lx, ly); c2.stroke(); c2.fillStyle = P.ink; c2.beginPath(); c2.arc(x, y, 2, 0, 6.3); c2.fill();
    c2.textAlign = dx < 0 ? "right" : "left"; c2.lineJoin = "round"; c2.lineWidth = 4; c2.strokeStyle = P.bg; const tx = lx + (dx < 0 ? -6 : 6);
    c2.font = "600 10px Inter,sans-serif"; c2.strokeText(title.toUpperCase(), tx, ly - 4); c2.fillText(title.toUpperCase(), tx, ly - 4);
    if (sub) { c2.font = "400 10.5px Inter,sans-serif"; c2.fillStyle = P.mute; c2.strokeText(sub, tx, ly + 11); c2.fillText(sub, tx, ly + 11); } c2.restore();
  }
  function frame() {
    if (dead) return; requestAnimationFrame(frame);
    if (document.hidden || !host.isConnected || host.offsetWidth === 0) return;
    const now = performance.now(), dt = Math.min(.1, (now - last) / 1000); last = now; const t = (now - t0) / 1000; NOW = t;
    while (recent.length && now - recent[0] > 600000) recent.shift(); BPM = 52 + Math.min(48, recent.length * 1.2) + (moodOn() ? (ST.mood === "low" ? -4 : 0) + 10 * ST.arousal : 0); phase += dt * BPM / 60;
    HINT = HINTS ? Math.max(0, 1 - t / 6, Math.min(1, (hintUntil - t) / 3)) : 0;
    // the camera, eased; a turned organ keeps a little of its spin; unfocused, the mind turns by itself
    if (STILL && !drag) spinning.obj = null; // Remove animations: a turned organ stops where the finger left it
    if (!drag && spinning.obj) { if (spinning.obj === "cam") goal.th += spinning.vx; else { spinning.obj.rotation.y += spinning.vx; spinning.obj.rotation.x += spinning.vy; } spinning.vx *= .93; spinning.vy *= .93; if (Math.abs(spinning.vx) + Math.abs(spinning.vy) < 1e-4) spinning.obj = null; }
    if (FOCUS !== "mind" && !(spinning.obj === mind.g)) mind.g.rotation.y += dt * .25;
    if (SUB && !(drag && drag.b === 2)) { const q = SUB.pos(); goal.tx = q.x; goal.ty = q.y; goal.tz = q.z; }
    modeB.style.display = FOCUS === "mind" ? "flex" : "none";
    for (const k of ["th", "ph", "d", "tx", "ty", "tz"]) view[k] += (goal[k] - view[k]) * (STILL ? 1 : Math.min(1, dt * 6));
    const tg = V(view.tx, view.ty, view.tz); cam.position.set(tg.x + view.d * Math.sin(view.ph) * Math.sin(view.th), tg.y + view.d * Math.cos(view.ph), tg.z + view.d * Math.sin(view.ph) * Math.cos(view.th)); cam.lookAt(tg);
    for (const k of Object.keys(TARGETS)) OPEN[k] = (OPEN[k] || 0) + ((FOCUS === k ? 1 : 0) - (OPEN[k] || 0)) * Math.min(1, dt * 4);
    for (const f of ticks) f(t, dt);
    bloom.strength = .7 - .45 * (OPEN.memory || 0) - .25 * (OPEN.mind || 0); // thousands of notes would bloom into one white cloud
    bloom.radius = OM && ONLY === "memory" ? .1 : .5; // the Memory page: the widest blur showed as a pale box round the notes
    composer.render();
    const c = c2; c.setTransform(DPR, 0, 0, DPR, 0, 0); c.clearRect(0, 0, W, H);
    if (OM) { /* an organ page: the app shows its name and parts */ } else if (UI) UI.header(c, { W, H, BPM, n: recent.length, HINTS, PROC, P, focus: FOCUS }); // phone: its own header and key
    else {
    c.font = "300 11px Inter,sans-serif"; c.fillStyle = P.mute; c.fillText("KUROOTO", 40, 34); c.font = "300 19px Inter,sans-serif"; c.fillStyle = P.ink; c.fillText("the being", 40, 58);
    c.font = "400 10px ui-monospace,monospace"; c.fillStyle = P.mute; c.fillText(`${Math.round(BPM)} / min · ${recent.length} ${recent.length === 1 ? "event" : "events"} in 10 min${HINTS ? " · drag an organ to turn it, wheel to zoom, right-drag to pan, click a part to look at it, Esc goes back, H hides these" : ""}`, 40, 76);
    let ly = 104; c.font = "400 10px Inter,sans-serif"; if (HINTS) for (const k of Object.keys(PROC)) { c.fillStyle = "#" + new THREE.Color(PROC[k].c).getHexString(); c.beginPath(); c.arc(46, ly - 3, 3, 0, 6.3); c.fill(); c.fillStyle = P.mute; c.fillText(PROC[k].name, 56, ly); ly += 14; }
    }
    c.font = "400 10px Inter,sans-serif";
    if (!FOCUS) {
      tag(BRAIN_C.clone().add(V(.9, .8, 0)), 150, -20, "Mind", "click to look inside · sparks are its work");
      tag(HEART_C.clone().add(V(.4, .1, 0)), 220, 20, "Core", `${Math.round(BPM)} a minute: faster when it's busier`);
      tag(SENSE_C.clone().add(V(.1, 1.45, 0)), 60, -40, "Senses", "sight, hearing, touch, balance, its own body");
      tag(MEM_C.clone().add(V(-.12, .4, 0)), -40, -50, "Memory", `${memory.nodes.length} notes · they light up as they link`);
    }
    if (FOCUS === "mind") for (const [k, r] of Object.entries(REGIONS)) { if (OM && PICKED !== k) continue; const v = V(...r.at).add(OFF).applyMatrix4(mind.b.matrixWorld); const [x] = proj(v); tag(v, x > W / 2 ? 110 : -110, -16, r.name, r.sub, OPEN.mind * (PICKED && PICKED !== k ? .35 : 1), PICKED === k); }
    if (FOCUS === "heart") for (const [k, r] of Object.entries(HEART_PARTS)) { if (OM && PICKED !== k) continue; const v = V(...r.at).applyMatrix4(heart.g.matrixWorld); const [x] = proj(v); tag(v, x > W / 2 ? 110 : -110, -16, r.name, r.sub, OPEN.heart * (PICKED && PICKED !== k ? .35 : 1), PICKED === k); }
    if (FOCUS === "senses") for (const [k, o] of Object.entries(senses.organs)) { if (OM && PICKED !== k) continue; const v = o.getWorldPosition(V(0, 0, 0)); const [x, y] = proj(v); tag(v, x > W / 2 ? 130 : -130, y > H / 2 ? 40 : -40, SENSES[k].name, SENSES[k].sub, OPEN.senses * (PICKED && PICKED !== k ? .35 : 1), PICKED === k); }
    if (FOCUS === "memory") for (const h of memory.hoods.filter((x) => x.n >= 5).slice(0, 10)) { if (OM && !(SUB && SUB.kind === "hood" && SUB.key === h.key)) continue; const v = V(...h.at).applyMatrix4(memory.g.matrixWorld); const [x] = proj(v); tag(v, x > W / 2 ? 90 : -90, -16, h.name, `${h.n} notes · most linked: ${String(h.hub).slice(0, 28)}`, OPEN.memory * (SUB && SUB.kind === "hood" && SUB.key !== h.key ? .25 : 1), !!(SUB && SUB.kind === "hood" && SUB.key === h.key)); }
    glanceDraw(c);
    if (SUB) {
      const q = SUB.pos(), [sx, sy, sz] = proj(q);
      if (sz < 1) {
        const px = (r) => { const e = q.clone().add(V(0, r, 0).applyQuaternion(cam.quaternion)); const [, ey] = proj(e); return Math.abs(ey - sy); };
        const R = Math.max(10, Math.min(Math.min(W, H) * .3, px({ region: .2, heart: .2, sense: .35, hood: .3, note: .02, feature: .05 }[SUB.kind] || .1)));
        c.save(); c.globalAlpha = .55 + .2 * Math.sin(NOW * 2.6); c.strokeStyle = P.ink; c.lineWidth = 1.2; c.beginPath(); c.arc(sx, sy, R, 0, 6.2832); c.stroke();
        c.globalAlpha *= .35; c.lineWidth = 5; c.beginPath(); c.arc(sx, sy, R + 3, 0, 6.2832); c.stroke(); c.restore();
      }
    }
    if (FOCUS && (OPEN[FOCUS] || 0) > .3) for (const id in ORG) { const o = ORG[id]; if (o.org !== FOCUS || (o.part !== PICKED && FOCUS !== "memory")) continue; const [x, y, z] = proj(o.g.getWorldPosition(V(0, 0, 0))); if (z > 1) continue; c.save(); c.globalAlpha = OPEN[FOCUS] * (o.on ? .85 : .4); c.font = UI ? UI.small : "400 9px Inter,sans-serif"; c.lineJoin = "round"; c.lineWidth = 3.5; c.strokeStyle = P.bg; c.strokeText(o.title, x + 8, y + 3); c.fillStyle = o.on ? P.ink : P.mute; c.fillText(o.title, x + 8, y + 3); c.restore(); }
    if (OM) { /* an organ page: no voice lanes */ } else if (UI) UI.lanes(c, lane, LANES, W, H); // phone: lower and thinner, no talk box
    else {
    const lv = liveShow(); // the YOU lane live while the microphone's levels come
    lane(c, H - 100, 34, LANES.you, "YOU", lv ? (NOW - LIVE.loud < 2 ? "hearing you, live" : "listening") : LANES.you ? (LANES.you.typed ? "typed to Kurooto" : LANES.you.heard ? "heard, not to Kurooto" : "heard, and said to Kurooto") : "say its name, or type in the talk box", lv);
    lane(c, H - 48, 44, LANES.me, "KUROOTO", LANES.me ? (LANES.me.typed ? "answered" : "speaking") : "");
    }
  }
  frame();
  return {
    update, event, graph, voice, body, typed, setHints, face, setRest, setLive, senses: far, status,
    // phone: the back button goes up one level (as Esc), and how deep you are (0: the whole being)
    escape() { if (OM) { if (!SUB) return false; back(); return true; } if (SUB) back(); else if (FOCUS || panel.style.display === "block") { closePanel(); focusOn(null); } else return false; return true; },
    depth() { if (OM) return SUB ? 1 : 0; return SUB ? 2 : FOCUS || panel.style.display === "block" ? 1 : 0; },
    // organ pages (opts.only): what the app reads and calls
    ...(OM ? { only, pick, setting, feature, mode: (m) => { if (["solid", "cut", "xray"].includes(m)) { setMode(m); organDirty(); } }, state: () => OSTATE, rev: () => OREV } : {}),
    // the organ pages' status line: a tap on its uneasy part focuses the glow's place (the app calls it)
    uneasy() { const u = ST.uneasy; if (!u) return false; if (u.startsWith("deadline:") && ORG.deadlines) { if (OM && ORG.deadlines.org === ONLY) { pick("feature", "deadlines"); return true; } if (!OM) { showFeature("deadlines"); return true; } } return false; },
    stop() { dead = true; if (OM) clearInterval(OTIMER); if (LAYOUT) LAYOUT.terminate(); ro.disconnect(); removeEventListener("keydown", onKey); R.dispose(); host.innerHTML = ""; host.classList.remove("being"); },
  };
};
})();
