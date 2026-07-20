window.LikeGodSlider = (() => {
  function init(root, options = {}) {
    if (!root) return null;
    const track = root.querySelector('[data-carousel-track]');
    const slides = Array.from(root.querySelectorAll('[data-carousel-slide]'));
    const dotsWrap = root.querySelector('[data-carousel-dots]');
    const prev = root.querySelector('[data-carousel-prev]');
    const next = root.querySelector('[data-carousel-next]');
    if (!track || slides.length <= 1) return null;

    let index = 0;
    let timer = null;
    let paused = false;
    let touchStart = 0;

    function goTo(nextIndex) {
      index = (nextIndex + slides.length) % slides.length;
      track.style.transform = `translateX(-${index * 100}%)`;
      if (dotsWrap) {
        dotsWrap.querySelectorAll('button').forEach((dot, dotIndex) => {
          dot.classList.toggle('is-active', dotIndex === index);
          dot.setAttribute('aria-current', dotIndex === index ? 'true' : 'false');
        });
      }
    }

    function startAuto() {
      stopAuto();
      if (!options.auto || slides.length < 2) return;
      timer = setInterval(() => {
        if (!paused) goTo(index + 1);
      }, options.interval || 5200);
    }

    function stopAuto() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    }

    if (dotsWrap) {
      dotsWrap.innerHTML = slides.map((_, dotIndex) => `<button type='button' class='carousel-dot ${dotIndex === 0 ? 'is-active' : ''}' data-dot='${dotIndex}' aria-label='Go to slide ${dotIndex + 1}' ${dotIndex === 0 ? 'aria-current=\"true\"' : ''}></button>`).join('');
      dotsWrap.querySelectorAll('button').forEach((dot) => {
        dot.addEventListener('click', () => goTo(Number(dot.dataset.dot)));
      });
    }

    prev?.addEventListener('click', () => goTo(index - 1));
    next?.addEventListener('click', () => goTo(index + 1));

    root.addEventListener('mouseenter', () => { paused = true; });
    root.addEventListener('mouseleave', () => { paused = false; });

    root.addEventListener('touchstart', (event) => {
      touchStart = event.changedTouches[0].clientX;
      paused = true;
    }, { passive: true });

    root.addEventListener('touchend', (event) => {
      const diff = event.changedTouches[0].clientX - touchStart;
      if (Math.abs(diff) > 40) {
        if (diff < 0) goTo(index + 1);
        else goTo(index - 1);
      }
      paused = false;
    }, { passive: true });

    startAuto();
    return { destroy: stopAuto, goTo };
  }

  return { init };
})();
