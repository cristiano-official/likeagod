window.LikeGodEffects = (() => {
  const storageEnabledKey = 'likeagod.effects.enabled';
  const storageTypeKey = 'likeagod.effects.type';
  const state = {
    enabled: true,
    type: 'digital_rain',
    raf: null,
    lastFrameAt: 0,
    canvas: null,
    ctx: null,
    rainDrops: [],
    snowFlakes: []
  };

  function ensureCanvas() {
    if (state.canvas) return state.canvas;
    const canvas = document.createElement('canvas');
    canvas.id = 'ambient-effects-canvas';
    canvas.className = 'ambient-effects-canvas';
    document.body.appendChild(canvas);
    state.canvas = canvas;
    state.ctx = canvas.getContext('2d');
    resize();
    window.addEventListener('resize', resize);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stop();
      else start();
    });
    return canvas;
  }

  function resize() {
    if (!state.canvas) return;
    state.canvas.width = window.innerWidth;
    state.canvas.height = window.innerHeight;
    initParticles();
  }

  function initParticles() {
    if (!state.canvas) return;
    const columns = Math.max(8, Math.floor(state.canvas.width / 20));
    state.rainDrops = Array.from({ length: columns }, () => Math.random() * -state.canvas.height);
    state.snowFlakes = Array.from({ length: Math.max(40, Math.floor(state.canvas.width / 18)) }, () => ({
      x: Math.random() * state.canvas.width,
      y: Math.random() * state.canvas.height,
      size: Math.random() * 2.4 + 0.8,
      speed: Math.random() * 0.6 + 0.35,
      drift: (Math.random() - 0.5) * 0.6
    }));
  }

  // Keep rendering at ~30 FPS so the effect stays lightweight.
  function frame(timestamp) {
    if (!state.enabled || !state.ctx || !state.canvas) return;
    if (timestamp - state.lastFrameAt < 33) {
      state.raf = requestAnimationFrame(frame);
      return;
    }
    state.lastFrameAt = timestamp;

    const ctx = state.ctx;
    const { width, height } = state.canvas;
    ctx.clearRect(0, 0, width, height);

    if (state.type === 'snow') {
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
      state.snowFlakes.forEach((flake) => {
        flake.y += flake.speed;
        flake.x += flake.drift;
        if (flake.y > height + 4) {
          flake.y = -4;
          flake.x = Math.random() * width;
        }
        if (flake.x > width + 4) flake.x = -4;
        if (flake.x < -4) flake.x = width + 4;
        ctx.beginPath();
        ctx.arc(flake.x, flake.y, flake.size, 0, Math.PI * 2);
        ctx.fill();
      });
    } else {
      const chars = '01$#@!%&*+-<>'.split('');
      ctx.fillStyle = 'rgba(7, 10, 20, 0.16)';
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = 'rgba(255, 145, 0, 0.65)';
      ctx.font = '16px monospace';
      state.rainDrops.forEach((dropY, index) => {
        const text = chars[Math.floor(Math.random() * chars.length)];
        const x = index * 20;
        ctx.fillText(text, x, dropY);
        if (dropY > height && Math.random() > 0.975) state.rainDrops[index] = Math.random() * -200;
        else state.rainDrops[index] = dropY + 16;
      });
    }

    state.raf = requestAnimationFrame(frame);
  }

  function start() {
    ensureCanvas();
    if (!state.enabled) {
      state.canvas.style.display = 'none';
      stop();
      return;
    }
    state.canvas.style.display = 'block';
    stop();
    state.raf = requestAnimationFrame(frame);
  }

  function stop() {
    if (state.raf) {
      cancelAnimationFrame(state.raf);
      state.raf = null;
    }
    if (state.ctx && state.canvas) state.ctx.clearRect(0, 0, state.canvas.width, state.canvas.height);
  }

  function configure({ enabled, type } = {}) {
    if (enabled !== undefined) {
      state.enabled = Boolean(enabled);
      localStorage.setItem(storageEnabledKey, String(state.enabled));
    }
    if (type) {
      state.type = type;
      localStorage.setItem(storageTypeKey, type);
      initParticles();
    }
    start();
  }

  function resolveInitial(user) {
    const enabledStored = localStorage.getItem(storageEnabledKey);
    const typeStored = localStorage.getItem(storageTypeKey);
    return {
      enabled: enabledStored === null ? Boolean(user?.effects ?? true) : enabledStored === 'true',
      type: typeStored || 'digital_rain'
    };
  }

  function getState() {
    return { enabled: state.enabled, type: state.type };
  }

  return {
    configure,
    resolveInitial,
    getState,
    storageEnabledKey,
    storageTypeKey
  };
})();
