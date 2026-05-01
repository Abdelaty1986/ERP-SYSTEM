(function () {
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.dev-action-card, .dev-metric').forEach(function (el, index) {
      el.style.animationDelay = (index * 35) + 'ms';
      el.classList.add('dev-fade-in');
    });
  });
})();
