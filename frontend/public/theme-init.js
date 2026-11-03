// Runs before the app starts: applies the saved light/dark choice to workspace pages, so a reload
// in dark mode never flashes white. Same rules as src/theme/theme.js – keep both in sync.
(function () {
  try {
    var preference = localStorage.getItem('trustshare.theme') || 'light';
    var dark =
      preference === 'dark' ||
      (preference === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    var path = window.location.pathname;
    var isPublic =
      path === '/' ||
      /^\/(login|register|forgot-password|reset-password|verify-email|auth\/google|status|s\/)/.test(
        path,
      );
    if (dark && !isPublic) document.documentElement.classList.add('theme-dark');
  } catch {
    // storage blocked: stay light
  }
})();
