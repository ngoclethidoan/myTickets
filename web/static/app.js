/* myTickets: the small bits of behaviour. Every page still works with JavaScript off. */
(function () {
  'use strict';

  function vnd(n) { return Math.round(n).toLocaleString('en-US') + ' đ'; }
  function two(n) { return (n < 10 ? '0' : '') + n; }

  /* Countdowns: <p data-countdown="seconds"> with an optional .clock child for the digits.
     The seconds come from the database clock, so the visitor's own clock does not matter. */
  document.querySelectorAll('[data-countdown]').forEach(function (el) {
    var end = Date.now() + Number(el.dataset.countdown) * 1000;
    var clock = el.querySelector('.clock') || el;
    function tick() {
      var s = Math.max(0, Math.round((end - Date.now()) / 1000));
      var d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
      clock.textContent = d > 0 ? d + 'd ' + two(h) + 'h ' + two(m) + 'm'
        : h > 0 ? h + ':' + two(m) + ':' + two(s % 60)
        : two(m) + ':' + two(s % 60);
      if (s > 0) return;
      clearInterval(timer);
      if (el.dataset.reload) { location.reload(); return; }
      if (el.dataset.done) { el.textContent = el.dataset.done; el.classList.add('expired'); }
      var card = el.closest('.tk');
      var pay = card && card.querySelector('form[data-pay]');
      if (pay) pay.remove();
    }
    var timer = setInterval(tick, 1000);
    tick();
  });

  /* Forms that ask before they act: <form data-confirm="question"> */
  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  document.querySelectorAll('[data-print]').forEach(function (b) {
    b.addEventListener('click', function () { window.print(); });
  });

  /* Account menu: close on outside click and on Escape */
  var menu = document.querySelector('details.menu');
  if (menu) {
    document.addEventListener('click', function (e) { if (!menu.contains(e.target)) menu.open = false; });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') menu.open = false; });
  }

  /* Event page: the map, the zone list and the order summary stay in step */
  var book = document.getElementById('book');
  if (!book) return;
  var zones = Array.prototype.slice.call(book.querySelectorAll('input[name="zone"]'));
  var qtys = Array.prototype.slice.call(book.querySelectorAll('input[name="qty"]'));
  var shapes = Array.prototype.slice.call(book.querySelectorAll('.map .zn'));
  var what = document.getElementById('sum-what');
  var unit = document.getElementById('sum-unit');
  var total = document.getElementById('sum-total');
  var roomMax = qtys.filter(function (q) { return !q.disabled; }).length;  // limit left for this account

  function picked() { return zones.filter(function (z) { return z.checked; })[0]; }

  function sync() {
    var z = picked();
    shapes.forEach(function (g) {
      g.classList.toggle('sel', !!z && g.dataset.zone === z.value);
      g.setAttribute('aria-checked', !!z && g.dataset.zone === z.value ? 'true' : 'false');
    });
    if (!total) return;
    var max = z ? Math.min(Number(z.dataset.max), roomMax) : roomMax;
    qtys.forEach(function (q) {
      q.disabled = Number(q.value) > max;
      if (q.disabled && q.checked) qtys[0].checked = true;
    });
    var n = Number((qtys.filter(function (q) { return q.checked; })[0] || { value: 1 }).value);
    if (!z) { what.textContent = 'No zone chosen yet'; unit.textContent = ''; total.textContent = vnd(0); return; }
    what.textContent = n + ' × ' + z.dataset.label;
    unit.textContent = vnd(Number(z.dataset.net)) + ' each';
    total.textContent = vnd(Number(z.dataset.net) * n);
  }

  shapes.forEach(function (g) {
    var z = zones.filter(function (r) { return r.value === g.dataset.zone; })[0];
    var usable = z && !z.disabled;
    if (!z || z.hasAttribute('data-soldout') || (!usable && book.querySelector('button[type=submit]'))) g.classList.add('off');
    if (!usable) g.style.cursor = 'default';
    g.setAttribute('tabindex', usable ? '0' : '-1');
    g.setAttribute('role', 'radio');
    g.setAttribute('aria-label', z ? z.dataset.label + ', ' + z.dataset.note : g.dataset.zone);
    var title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = z ? z.dataset.label + ': ' + z.dataset.note : g.dataset.zone;
    g.insertBefore(title, g.firstChild);
    function choose() {
      if (!usable) return;
      z.checked = true;
      sync();
    }
    g.addEventListener('click', choose);
    g.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(); }
    });
  });
  zones.concat(qtys).forEach(function (r) { r.addEventListener('change', sync); });
  sync();
})();
