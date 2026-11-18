import { animate, createDraggable } from 'animejs';

const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
let draggable;
let mountedBall;
let panelAnimation;
let closeAfterAnimation;
let suppressClickUntil = 0;

function fitPanel() {
  const ball = document.querySelector('#assistant-ball');
  const panel = document.querySelector('#assistant-panel');
  if (!ball || !panel?.open) return;
  const anchor = ball.getBoundingClientRect();
  const width = panel.offsetWidth;
  const height = panel.offsetHeight;
  const clamp = (value, max) => Math.max(12, Math.min(value, Math.max(12, max)));
  const left = clamp(anchor.right - width, document.documentElement.clientWidth - width - 12);
  const top = clamp(
    anchor.top >= height + 24 ? anchor.top - height - 12 : anchor.bottom + 12,
    innerHeight - height - 12,
  );
  Object.assign(panel.style, { left: `${left}px`, top: `${top}px`, right: 'auto', bottom: 'auto' });
}

function mountAssistant() {
  const ball = document.querySelector('#assistant-ball');
  if (!ball || ball === mountedBall) return;
  draggable?.revert();
  mountedBall = ball;
  // Anime.js handles pointer capture, thresholds, touch input and viewport constraints.
  draggable = createDraggable(ball, {
    container: document.body,
    containerPadding: () => [12, 12 + innerWidth - document.documentElement.clientWidth, 12, 12],
    containerFriction: 1,
    releaseContainerFriction: 1,
    velocityMultiplier: 0,
    dragThreshold: { mouse: 6, touch: 10 },
    cursor: { onHover: 'grab', onGrab: 'grabbing' },
    onDrag: () => {
      suppressClickUntil = performance.now() + 300;
      fitPanel();
    },
    onUpdate: fitPanel,
    onAfterResize: fitPanel,
  });
  fitPanel();
}

function resetPosition() {
  draggable?.revert();
  draggable = undefined;
  mountedBall = undefined;
  mountAssistant();
  fitPanel();
}

function show(panel) {
  panelAnimation?.cancel();
  closeAfterAnimation = undefined;
  fitPanel();
  if (reducedMotion.matches) {
    Object.assign(panel.style, { opacity: '1', transform: 'none' });
    return;
  }
  panelAnimation = animate(panel, {
    opacity: [0, 1],
    translateY: [8, 0],
    duration: 200,
    ease: 'out(3)',
  });
}

function hide(panel, finish) {
  panelAnimation?.cancel();
  if (reducedMotion.matches) return finish();
  closeAfterAnimation = finish;
  panelAnimation = animate(panel, {
    opacity: 0,
    translateY: 6,
    duration: 140,
    ease: 'out(2)',
    onComplete: () => {
      const done = closeAfterAnimation;
      closeAfterAnimation = undefined;
      done?.();
    },
  });
}

function enter(elements) {
  if (reducedMotion.matches || !elements.length) return;
  animate(elements, { opacity: [0, 1], translateY: [6, 0], duration: 180, ease: 'out(3)' });
}

function refreshPage(animateCards = false) {
  for (const region of document.querySelectorAll('.table-region')) {
    const hint = region.previousElementSibling;
    if (hint?.classList.contains('table-scroll-hint'))
      hint.toggleAttribute('data-overflow', region.scrollWidth > region.clientWidth + 1);
  }
  if (animateCards) enter([...document.querySelectorAll('[data-motion-card]')]);
}

document.addEventListener(
  'click',
  (event) => {
    if (event.target.closest('#assistant-ball') && performance.now() < suppressClickUntil) {
      event.preventDefault();
      event.stopPropagation();
    }
  },
  true,
);
window.addEventListener('resize', resetPosition);
window.addEventListener('resize', () => refreshPage());
reducedMotion.addEventListener('change', () => {
  panelAnimation?.cancel();
  const finish = closeAfterAnimation;
  closeAfterAnimation = undefined;
  finish?.();
  const panel = document.querySelector('#assistant-panel');
  if (panel) Object.assign(panel.style, { opacity: '1', translate: '0 0', transform: 'none' });
});
window.demoMotion = { mountAssistant, resetPosition, show, hide, enter, fitPanel, refreshPage };
mountAssistant();
refreshPage();
