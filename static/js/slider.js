/* slider.js — lightweight news carousel.
   Autoplay (5s), prev/next arrows, dot indicators, touch/swipe, pause on hover.
   Usage: Slider.create(rootEl) where rootEl contains:
     .slider-track  (flex row of .slide)
     .slider-dots   (dot buttons injected here)
     .slider-arrow.prev / .slider-arrow.next (optional)
*/
window.Slider = (() => {
  function create(root) {
    if (!root) return null;
    const track = root.querySelector('.slider-track');
    const slides = track ? Array.from(track.children) : [];
    const dotsWrap = root.querySelector('.slider-dots');
    const prev = root.querySelector('.slider-arrow.prev');
    const next = root.querySelector('.slider-arrow.next');
    if (!track || slides.length === 0) return null;

    let index = 0;
    let timer = null;
    const AUTOPLAY = 5000;

    const dots = [];
    if (dotsWrap) {
      dotsWrap.innerHTML = '';
      slides.forEach((_, i) => {
        const b = document.createElement('button');
        b.className = 'slider-dot' + (i === 0 ? ' active' : '');
        b.setAttribute('aria-label', `Slide ${i + 1}`);
        b.addEventListener('click', () => go(i, true));
        dotsWrap.appendChild(b);
        dots.push(b);
      });
    }

    function render() {
      track.style.transform = `translateX(-${index * 100}%)`;
      dots.forEach((d, i) => d.classList.toggle('active', i === index));
    }

    function go(i, manual) {
      index = (i + slides.length) % slides.length;
      render();
      if (manual) restart();
    }

    function nextSlide() { go(index + 1); }
    function prevSlide() { go(index - 1); }

    function restart() {
      stop();
      if (slides.length > 1) timer = setInterval(nextSlide, AUTOPLAY);
    }
    function stop() { if (timer) { clearInterval(timer); timer = null; } }

    if (next) next.addEventListener('click', () => go(index + 1, true));
    if (prev) prev.addEventListener('click', () => go(index - 1, true));

    root.addEventListener('mouseenter', stop);
    root.addEventListener('mouseleave', restart);

    // touch / swipe
    let startX = 0;
    let dragging = false;
    root.addEventListener('touchstart', (e) => { startX = e.touches[0].clientX; dragging = true; stop(); }, { passive: true });
    root.addEventListener('touchend', (e) => {
      if (!dragging) return;
      dragging = false;
      const dx = e.changedTouches[0].clientX - startX;
      if (Math.abs(dx) > 40) { dx < 0 ? nextSlide() : prevSlide(); }
      restart();
    });

    // hide controls when single slide
    if (slides.length <= 1) {
      if (prev) prev.style.display = 'none';
      if (next) next.style.display = 'none';
      if (dotsWrap) dotsWrap.style.display = 'none';
    }

    render();
    restart();
    return { go, next: nextSlide, prev: prevSlide, stop, restart };
  }

  return { create };
})();
