// One outline style for the shared navigation and status icons.
const iconPaths = {
  download: 'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5',
  chevronLeft: 'M14 6l-6 6 6 6',
  chevronRight: 'M10 6l6 6-6 6',
  overview: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  audit: 'M12 3l8 4v5c0 5-8 9-8 9s-8-4-8-9V7z M8 12l3 3 5-6',
  clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 7v5l3 2',
  history: 'M3 10a9 9 0 1 1 1 8 M3 4v6h6 M12 7v5l3 2',
  settings: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2',
  search: 'M10.5 3a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15 M16 16l5 5',
  bell: 'M18 8a6 6 0 0 0-12 0v6l-2 3h16l-2-3z M10 21h4',
  menu: 'M4 6h16 M4 12h16 M4 18h16',
  people: 'M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M2 21v-3a7 7 0 0 1 14 0v3 M17 4a4 4 0 0 1 0 8 M19 15a5 5 0 0 1 3 5',
  repo: 'M5 3h14v18H5z M8 6h8 M8 17h8',
  alert: 'M12 3L2 21h20z M12 9v5 M12 17v1',
  check: 'M4 12l5 5L20 6',
  checkCircle: 'M22 11.08V12a10 10 0 1 1-5.93-9.14 M22 4L12 14.01l-3-3',
  declined: 'M6 6l12 12 M6 18L18 6',
  shieldAlert: 'M12 3l8 4v5c0 5-8 9-8 9s-8-4-8-9V7z M12 8v4 M12 16h.01',
  hourglass: 'M5 3h14 M5 21h14 M7 3v4a5 5 0 0 0 5 5 5 5 0 0 0 5-5V3 M7 21v-4a5 5 0 0 1 5-5 5 5 0 0 1 5 5v4',
  userMinus: 'M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M8.5 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M23 11h-6',
  userX: 'M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M8.5 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M18 8l5 5 M23 8l-5 5',
  briefcase: 'M16 4H8a2 2 0 0 0-2 2v2H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2h-2V6a2 2 0 0 0-2-2z M8 6h8v2H8z',
  upload: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M17 8l-5-5-5 5 M12 3v12',
  sparkles: 'M12 3l1.9 4.1L18 9l-4.1 1.9L12 15l-1.9-4.1L6 9l4.1-1.9z M19 16l.9 2.1L22 19l-2.1.9L19 22l-.9-2.1L16 19l2.1-.9z',
  zap: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
  pause: 'M6 4h4v16H6z M14 4h4v16h-4z',
  filter: 'M22 3H2l8 9.46V19l4 2v-8.54L22 3z',
  layers: 'M12 2L2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5',
  fileText: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8',
  scale: 'M12 3v18 M12 3l7 4 M12 3L5 7 M2 13l3-6 3 6a3 3 0 0 1-6 0z M16 13l3-6 3 6a3 3 0 0 1-6 0z',
  bellOff: 'M13.73 21a2 2 0 0 1-3.46 0 M18.63 13A17.89 17.89 0 0 1 18 8 M6.26 6.26A5.86 5.86 0 0 0 6 8v6l-2 3h14.73 M1 1l22 22'
};

function uiIcon(name, size = 18, extraClass = '') {
  const s = size || 18;
  const cls = extraClass ? `ui-icon ${extraClass}` : 'ui-icon';
  const path = iconPaths[name] || iconPaths.audit;
  return `<svg class="${cls}" width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-2px;"><path d="${path}"/></svg>`;
}

function refreshIcons(page) {
  document.querySelectorAll('.main-nav a').forEach(a => {
    a.querySelector('.nav-icon').innerHTML = uiIcon({
      dashboard: 'overview',
      audit: 'audit',
      approvals: 'clock',
      history: 'history',
      settings: 'settings',
      users: 'people'
    }[a.dataset.page] || 'overview');
  });

  const statNames = page === 'approvals'
    ? ['clock', 'check', 'declined', 'alert']
    : (document.querySelector('.governance-stats')
        ? ['people', 'repo', 'overview', 'alert', 'clock']
        : ['people', 'repo', 'alert', 'clock']);

  document.querySelectorAll('.stat-icon').forEach((e, i) => {
    if (statNames[i]) e.innerHTML = uiIcon(statNames[i]);
  });

  const searchOpen = document.querySelector('#search-open');
  if (searchOpen) searchOpen.innerHTML = uiIcon('search') + '<span>Search workspace</span><kbd>/</kbd>';

  const mobileMenu = document.querySelector('#mobile-menu');
  if (mobileMenu) mobileMenu.innerHTML = uiIcon('menu');

  document.querySelectorAll('[data-export]').forEach(button => {
    const label = button.textContent.replace('↧', '').trim();
    button.innerHTML = uiIcon('download') + '<span>' + label + '</span>';
  });

  const toggle = document.querySelector('#sidebar-collapse');
  if (toggle) {
    toggle.innerHTML = uiIcon(document.body.classList.contains('collapsed') ? 'chevronRight' : 'chevronLeft');
    toggle.setAttribute('aria-expanded', String(!document.body.classList.contains('collapsed')));
  }
}
