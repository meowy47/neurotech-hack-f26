// Eureka demo: the app consumes Muse LSL frames from scripts/muse-live over SSE.
// It falls back to simulated data only while the local live service is unavailable.

const params = new URLSearchParams(location.search);
const CONFIG = {
  eventUrl: params.get('events') || (location.protocol.startsWith('http') ? `${location.protocol}//${location.host}/events` : 'http://127.0.0.1:8765/events'),
  workStartSeconds: Number(params.get('start') || 0), // e.g. ?start=2832 shows 47:12 on load
  reconnectMs: 3000,
  baselineSeconds: 60,   // alpha-power baseline = mean of the last 60 s of clean work data
  smoothSeconds: 10,     // break reading = mean of the last 10 s of clean data
  enterPct: 15,          // "in state" when alpha power is this % above baseline
  meterMinPct: -20,
  meterMaxPct: 40,
  staleSeconds: 2,       // no headband samples for this long = signal lost
};

// Ranked by sample history; replace with each user's real results.
const ACTIVITIES = [
  { id: 'om', name: 'Open-monitoring meditation', stat: 'Alpha response +31% · best in 4 breaks', mins: 2, sound: 'guided voice',
    prompt: 'Look out a window and count the yellow cars. Let every other thought pass.' },
  { id: 'dt', name: 'Unusual uses', stat: 'Alpha response +24% · 9 ideas on average', mins: 3, sound: 'upbeat instrumental',
    prompt: 'Name every use you can think of for a brick.' },
  { id: 'sk', name: 'Creative sketching', stat: 'Alpha response +18% · 3 breaks', mins: 3, sound: 'café noise',
    prompt: 'Draw a creature that lives inside your backpack.' },
];

const $ = (id) => document.getElementById(id);
const now = () => performance.now() / 1000;

const state = {
  screen: 'work',
  workStart: now() - CONFIG.workStartSeconds,
  breakStart: 0,
  mode: 'connecting',        // 'live' | 'sim' | 'connecting'
  latest: null,              // last frame received
  history: [],               // [{t, ua}] clean upper-alpha values
  baseline: null,
  openId: null,
  openStart: 0,
  done: {},
  inSince: null,
  simAlphaBoost: 0,
};

// ---------- connection ----------

let eventSource = null;
let simTimer = null;

function connect() {
  if (!simTimer) setMode('connecting');
  try {
    eventSource = new EventSource(CONFIG.eventUrl);
  } catch (e) {
    startSim();
    setTimeout(connect, CONFIG.reconnectMs);
    return;
  }
  eventSource.onopen = () => { stopSim(); setMode('connecting'); };
  eventSource.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type === 'eeg_frame') {
      stopSim();
      setMode('live');
      handleLiveFrame(msg);
    }
  };
  eventSource.onerror = () => {
    eventSource.close();
    if (state.mode === 'live') state.history = [];
    startSim();
    setTimeout(connect, CONFIG.reconnectMs);
  };
}

function setMode(mode) {
  state.mode = mode;
  renderChip();
}

// ---------- simulation (same frame format as the bridge) ----------

function startSim() {
  if (simTimer) return;
  state.mode = 'sim';
  renderChip();
  let t = 0;
  simTimer = setInterval(() => {
    t += 0.1;
    const target = state.screen === 'break' && state.openId ? 0.06 : 0;
    state.simAlphaBoost += (target - state.simAlphaBoost) * 0.03;
    const ua = 0.13 + state.simAlphaBoost + 0.006 * Math.sin(t * 0.7) + (Math.random() - 0.5) * 0.008;
    const rate = 64, n = 256, af7 = [], af8 = [];
    for (let i = 0; i < n; i++) {
      const s = t + (i - n) / rate;
      const a = (14 + 120 * state.simAlphaBoost) * Math.sin(2 * Math.PI * 10.5 * s);
      af7.push(a + 7 * Math.sin(2 * Math.PI * 6 * s) + (Math.random() - 0.5) * 9);
      af8.push(0.8 * a + 7 * Math.sin(2 * Math.PI * 6 * s + 1) + (Math.random() - 0.5) * 9);
    }
    handleFrame({
      type: 'frame', source: 'sim', age: 0, ready: true, clean: true,
      bands: { delta: 0.22, theta: 0.19, alpha: ua + 0.09, upper_alpha: ua, beta: 0.27, gamma: 0.05 },
      alpha_index: 100 + state.simAlphaBoost * 600,
      display: { rate, af7, af8 },
    });
  }, 100);
}

function stopSim() {
  clearInterval(simTimer);
  simTimer = null;
  state.history = [];
}

// ---------- data ----------

function average(values) {
  const usable = values.filter((value) => Number.isFinite(value));
  return usable.length ? usable.reduce((sum, value) => sum + value, 0) / usable.length : null;
}

function handleLiveFrame(frame) {
  const channels = frame.clean_channels.length ? frame.clean_channels : frame.channels;
  const bands = Object.fromEntries(Object.entries(frame.bandpower).map(([band, byChannel]) => [
    band,
    average(channels.map((channel) => byChannel[channel])),
  ]));
  handleFrame({
    type: 'frame',
    source: 'lsl',
    age: 0,
    ready: frame.ready,
    clean: frame.clean_channels.length > 0 && !frame.artifact.detected,
    bands: { ...bands, upper_alpha: bands.alpha },
    alpha_index: frame.alpha_index,
    display: frame.display,
    artifact: frame.artifact,
  });
}

function handleFrame(f) {
  state.latest = f;
  if (f.ready && f.clean && f.bands) {
    const t = now();
    state.history.push({ t, ua: f.bands.upper_alpha });
    const cutoff = t - 180;
    while (state.history.length && state.history[0].t < cutoff) state.history.shift();
  }
}

function meanSince(seconds) {
  const cutoff = now() - seconds;
  const vals = state.history.filter((h) => h.t >= cutoff).map((h) => h.ua);
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function signalStatus() {
  const f = state.latest;
  if (!f) return 'waiting';
  if (f.age != null && f.age > CONFIG.staleSeconds) return 'lost';
  if (!f.ready) return 'buffering';
  return f.clean ? 'clean' : 'artifact';
}

// ---------- rendering ----------

function fmtClock(sec) {
  sec = Math.max(0, Math.floor(sec));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  const pad = (n) => String(n).padStart(2, '0');
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

function renderChip() {
  const chip = $('sourceChip');
  chip.classList.remove('live', 'sim', 'lost');
  const status = signalStatus();
  if (state.mode === 'live' && status === 'lost') {
    chip.classList.add('lost');
    $('sourceText').textContent = 'Headband signal lost';
  } else if (state.mode === 'live') {
    chip.classList.add('live');
    $('sourceText').textContent = 'Live · Muse 2';
  } else if (state.mode === 'sim') {
    chip.classList.add('sim');
    $('sourceText').textContent = 'Simulated data';
  } else {
    $('sourceText').textContent = 'Connecting…';
  }
}

const canvas = $('waveCanvas');
const ctx = canvas.getContext('2d');

function sizeCanvas() {
  const dpr = window.devicePixelRatio || 1;
  const r = canvas.getBoundingClientRect();
  canvas.width = Math.round(r.width * dpr);
  canvas.height = Math.round(r.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

let gain = 40;
function drawWaves() {
  const r = canvas.getBoundingClientRect();
  const w = r.width, h = r.height, mid = h / 2;
  ctx.clearRect(0, 0, w, h);
  const d = state.latest && state.latest.display;
  if (!d) {
    ctx.strokeStyle = 'rgba(217,198,210,0.25)';
    ctx.beginPath(); ctx.moveTo(0, mid); ctx.lineTo(w, mid); ctx.stroke();
    return;
  }
  let peak = 1;
  for (const v of d.af7) peak = Math.max(peak, Math.abs(v));
  for (const v of d.af8) peak = Math.max(peak, Math.abs(v));
  gain += (Math.max(peak, 20) - gain) * 0.1;    // smooth auto-scale
  const scale = (h * 0.45) / gain;
  const line = (arr, color, width, alpha) => {
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.globalAlpha = alpha;
    ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.beginPath();
    arr.forEach((v, i) => {
      const x = (i / (arr.length - 1)) * w, y = mid - v * scale;
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.stroke(); ctx.globalAlpha = 1;
  };
  line(d.af8, '#D9C6D2', 1.5, 0.55);
  line(d.af7, '#E0829C', 2.2, 1);
}

function renderBands() {
  const b = state.latest && state.latest.ready && state.latest.bands;
  const power = (v) => Number.isFinite(v) ? v.toExponential(1) : '–';
  $('bTheta').textContent = b ? power(b.theta) : '–';
  $('bAlpha').textContent = b ? power(b.alpha) : '–';
  $('bIndex').textContent = state.latest && state.latest.alpha_index != null ? Math.round(state.latest.alpha_index) : '–';
  $('bBeta').textContent = b ? power(b.beta) : '–';
  const note = $('signalNote');
  const s = signalStatus();
  note.classList.toggle('warn', s === 'artifact' || s === 'lost');
  note.textContent = { clean: 'Live LSL EEG', artifact: 'Blink or movement', lost: 'No signal', buffering: 'Buffering…', waiting: 'Waiting for data' }[s];
}

function renderWork() {
  $('workClock').textContent = fmtClock(now() - state.workStart);
  renderBands();
  drawWaves();
}

// ---------- break screen ----------

function buildCards() {
  const wrap = $('cards');
  wrap.textContent = '';
  ACTIVITIES.forEach((a, i) => {
    const open = state.openId === a.id;
    const card = document.createElement('div');
    card.className = 'card' + (open ? ' open' : '');

    const head = document.createElement('button');
    head.type = 'button';
    head.className = 'card-head';
    head.setAttribute('aria-expanded', String(open));
    head.innerHTML = `<span class="rank">${i + 1}</span><span class="title"><strong></strong><span></span></span><span class="tag"></span>`;
    head.querySelector('strong').textContent = a.name;
    head.querySelector('.title span').textContent = a.stat;
    head.querySelector('.tag').textContent = state.done[a.id] ? 'Done' : open ? 'Now' : `${a.mins} min`;
    head.addEventListener('click', () => {
      if (open) { state.openId = null; } else { state.openId = a.id; state.openStart = now(); state.inSince = null; }
      buildCards();
    });
    card.appendChild(head);

    if (open) {
      const body = document.createElement('div');
      body.className = 'card-body';
      body.innerHTML = `
        <div class="prompt"></div>
        <div class="sound"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E0829C" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M4 10v4"/><path d="M8 7v10"/><path d="M12 4v16"/><path d="M16 8v8"/><path d="M20 11v2"/></svg><span></span></div>
        <div class="run">
          <div class="countdown" id="countdown"></div>
          <div class="meter-wrap">
            <div class="meter"><div class="bar" id="meterBar"></div><div class="target" id="meterTarget"></div></div>
            <div class="reading" id="reading" aria-live="polite"></div>
          </div>
        </div>
        <button type="button" class="btn ghost">Done</button>`;
      body.querySelector('.prompt').textContent = a.prompt;
      body.querySelector('.sound span').textContent = `Playing: ${a.sound}`;
      body.querySelector('button').addEventListener('click', () => {
        state.done[a.id] = true;
        state.openId = null;
        buildCards();
      });
      const tgt = (CONFIG.enterPct - CONFIG.meterMinPct) / (CONFIG.meterMaxPct - CONFIG.meterMinPct) * 100;
      body.querySelector('#meterTarget').style.left = tgt + '%';
      card.appendChild(body);
    }
    wrap.appendChild(card);
  });
}

function renderBreak() {
  $('breakClock').textContent = fmtClock(Math.min(900, now() - state.breakStart));
  $('baselineNote').textContent = state.baseline == null
    ? 'Collecting a baseline: keep the headband on for a minute of work first.'
    : `Your work baseline: alpha power ${state.baseline.toExponential(2)}.`;

  const a = ACTIVITIES.find((x) => x.id === state.openId);
  if (!a) return;
  const left = a.mins * 60 - (now() - state.openStart);
  const cd = $('countdown');
  if (cd) cd.textContent = fmtClock(Math.max(0, left));

  const bar = $('meterBar'), reading = $('reading');
  if (!bar || !reading) return;
  const avg = meanSince(CONFIG.smoothSeconds);
  if (state.baseline == null || avg == null) {
    bar.style.width = '0%';
    reading.className = 'reading';
    reading.textContent = signalStatus() === 'lost' ? 'No headband signal' : 'Waiting for clean data…';
    return;
  }
  const pct = ((avg - state.baseline) / state.baseline) * 100;
  const isIn = pct >= CONFIG.enterPct;
  if (isIn && state.inSince == null) state.inSince = now();
  if (!isIn) state.inSince = null;
  const w = (pct - CONFIG.meterMinPct) / (CONFIG.meterMaxPct - CONFIG.meterMinPct) * 100;
  bar.style.width = Math.max(0, Math.min(100, w)).toFixed(1) + '%';
  bar.classList.toggle('in', isIn);
  reading.classList.toggle('in', isIn);
  const sign = pct >= 0 ? '+' : '−';
  reading.textContent = isIn
    ? `You're in: alpha response ${sign}${Math.abs(pct).toFixed(0)}% for ${fmtClock(now() - state.inSince)}`
    : `Alpha response ${sign}${Math.abs(pct).toFixed(0)}% vs baseline · target +${CONFIG.enterPct}%`;
}

// ---------- screens ----------

function show(screen) {
  state.screen = screen;
  $('work').hidden = screen !== 'work';
  $('break').hidden = screen !== 'break';
  if (screen === 'work') requestAnimationFrame(sizeCanvas);
  window.scrollTo(0, 0);
}

$('takeBreak').addEventListener('click', () => {
  state.baseline = meanSince(CONFIG.baselineSeconds);
  state.breakStart = now();
  state.openId = null;
  state.done = {};
  state.inSince = null;
  buildCards();
  show('break');
});

$('backToWork').addEventListener('click', () => {
  state.workStart = now();
  state.openId = null;
  show('work');
});

// ---------- loop ----------

function frame() {
  renderChip();
  if (state.screen === 'work') renderWork(); else renderBreak();
  requestAnimationFrame(frame);
}

window.addEventListener('resize', sizeCanvas);
sizeCanvas();
connect();
requestAnimationFrame(frame);
