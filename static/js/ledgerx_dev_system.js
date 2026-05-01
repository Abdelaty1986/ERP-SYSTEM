document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.lx-action-card, .lx-stat-card').forEach(function (el, index) {
    el.style.animationDelay = (index * 35) + 'ms';
    el.classList.add('lx-enter');
  });
});
