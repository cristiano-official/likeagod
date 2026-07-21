/* effects.js — canvas ambient effects (teal digital rain + snow).
   Renders onto #fx-canvas. FPS capped at 30, pauses on hidden tab.
   Reads persisted preference from localStorage ('likeagod.effects.type':
   'rain' | 'snow' | 'off').
   Public API on window.Effects:
     Effects.start(type)  -> 'rain' | 'snow' | 'off'
     Effects.stop()
     Effects.init()       -> start from saved preference
     Effects.type         -> current type
*/
window.Effects = (() => {
  const TYPE_KEY = 'likeagod.effects.type';
  const FPS = 30;
  const FRAME = 1000 / FPS;

  let canvas = null;
  let ctx = null;
  let type = 'off';
  let raf = null;
  let last = 0;
  let columns = [];
  let flakes = [];
  let W = 0;
  let H = 0;

  function ensureCanvas() {
    if (canvas) return canvas;
    canvas = document.getElementById('fx-canvas');
    if (!canvas) return null;
    ctx = canvas.getContext('2d');
    resize();
    window.addEventListener('resize', resize);
    document.addEventListener('visibilitychange', onVisibility);
    return canvas;
  }

  function resize() {
    if (!canvas) return;
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
    seed();
  }

  function seed() {
    const step = 16;
    columns = [];
    for (let x = 0; x < W; x += step) {
      columns.push({ x, y: Math.random() * H, speed: 4 + Math.random() * 6 });
    }
    flakes = [];
    const count = Math.floor((W * H) / 22000);
    for (let i = 0; i < count; i++) {
      flakes.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: 1 + Math.random() * 2.4,
        sx: -0.4 + Math.random() * 0.8,
        sy: 0.5 + Math.random() * 1.2
      });
    }
  }

  function drawRain() {
    ctx.fillStyle = 'rgba(6, 9, 26, 0.28)';
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = 'rgba(14, 245, 181, 0.75)';
    ctx.font = '14px "JetBrains Mono", monospace';
    for (const col of columns) {
      const ch = String.fromCharCode(0x30a0 + Math.floor(Math.random() * 96));
      ctx.fillText(ch, col.x, col.y);
      col.y += col.speed;
      if (col.y > H) {
        col.y = -20;
        col.speed = 4 + Math.random() * 6;
      }
    }
  }

  function drawSnow() {
    ctx.clearRect(0, 0, W, H);
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    ctx.fillStyle = isLight ? 'rgba(26, 26, 26, 0.75)' : 'rgba(221, 230, 240, 0.7)';
    for (const f of flakes) {
      ctx.beginPath();
      ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2);
      ctx.fill();
      f.x += f.sx;
      f.y += f.sy;
      if (f.y > H) { f.y = -5; f.x = Math.random() * W; }
      if (f.x < 0) f.x = W;
      if (f.x > W) f.x = 0;
    }
  }

  function loop(ts) {
    raf = requestAnimationFrame(loop);
    if (ts - last < FRAME) return;
    last = ts;
    if (type === 'rain') drawRain();
    else if (type === 'snow') drawSnow();
  }

  function onVisibility() {
    if (document.hidden) {
      if (raf) { cancelAnimationFrame(raf); raf = null; }
    } else if (type !== 'off' && !raf) {
      raf = requestAnimationFrame(loop);
    }
  }

  function stop() {
    if (raf) { cancelAnimationFrame(raf); raf = null; }
    if (ctx) ctx.clearRect(0, 0, W, H);
    type = 'off';
    localStorage.setItem(TYPE_KEY, 'off');
  }

  function start(next) {
    const chosen = ['rain', 'snow'].includes(next) ? next : 'off';
    localStorage.setItem(TYPE_KEY, chosen);
    if (chosen === 'off') { stop(); return type; }
    if (!ensureCanvas()) return 'off';
    type = chosen;
    seed();
    if (!raf) { last = 0; raf = requestAnimationFrame(loop); }
    return type;
  }

  function init() {
    const saved = localStorage.getItem(TYPE_KEY) || 'off';
    return start(saved);
  }

  return {
    TYPE_KEY,
    get type() { return type; },
    start,
    stop,
    init
  };
})();
