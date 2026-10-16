// Sets the theme on <html> before first paint (no flash): the saved choice, else the system preference.
// Loaded as a blocking script from index.html (the CSP forbids inline scripts). Keep in sync with
// src/components/ThemeToggle.tsx.
;(function () {
  var t
  try {
    t = localStorage.getItem('theme')
  } catch {}
  if (t !== 'light' && t !== 'dark') t = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  document.documentElement.dataset.theme = t
})()
