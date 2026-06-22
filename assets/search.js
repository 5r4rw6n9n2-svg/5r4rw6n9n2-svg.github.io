/* Клиентский поиск по сайту: грузит /search-index.json и фильтрует на лету.
   Работает на статическом хостинге (GitHub Pages) без сервера. */
(function () {
  var input = document.getElementById("q");
  var out = document.getElementById("results");
  if (!input || !out) return;

  var index = [];
  var ready = false;

  function norm(s) { return s.toLowerCase().replace(/ё/g, "е").replace(/ /g, " "); }
  function esc(s) {
    return s.replace(/[&<>]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c];
    });
  }
  function highlight(text, q) {
    var i = norm(text).indexOf(q);
    if (i < 0) return esc(text);
    return esc(text.slice(0, i)) + "<mark>" + esc(text.slice(i, i + q.length)) +
      "</mark>" + esc(text.slice(i + q.length));
  }

  function render() {
    var q = norm(input.value.trim());
    if (q.length < 2) {
      out.innerHTML = '<p class="search-hint">Введите хотя бы две буквы.</p>';
      return;
    }
    if (!ready) {
      out.innerHTML = '<p class="search-hint">Загрузка…</p>';
      return;
    }
    var res = [];
    for (var k = 0; k < index.length; k++) {
      var e = index[k];
      var inT = norm(e.t).indexOf(q) >= 0;
      var inB = norm(e.b).indexOf(q) >= 0;
      if (!inT && !inB) continue;
      var snip = "";
      var lines = e.b.split("\n");
      for (var j = 0; j < lines.length; j++) {
        if (norm(lines[j]).indexOf(q) >= 0) { snip = lines[j]; break; }
      }
      res.push({ e: e, inT: inT, snip: snip });
    }
    res.sort(function (a, b) { return (b.inT ? 1 : 0) - (a.inT ? 1 : 0); });
    if (!res.length) {
      out.innerHTML = '<p class="search-hint">Ничего не найдено.</p>';
      return;
    }
    var html = '<p class="search-count">Найдено: ' + res.length + "</p>";
    html += res.slice(0, 100).map(function (r) {
      return '<a class="search-result" href="' + r.e.u + '">' +
        '<span class="sr-title">' + highlight(r.e.t, q) + "</span>" +
        '<span class="sr-coll">' + esc(r.e.c) + "</span>" +
        (r.snip ? '<span class="sr-snip">' + highlight(r.snip, q) + "</span>" : "") +
        "</a>";
    }).join("");
    out.innerHTML = html;
  }

  fetch("/search-index.json")
    .then(function (r) { return r.json(); })
    .then(function (data) { index = data; ready = true; render(); })
    .catch(function () { out.innerHTML = '<p class="search-hint">Не удалось загрузить индекс поиска.</p>'; });

  input.addEventListener("input", render);
  var pq = new URLSearchParams(location.search).get("q");
  if (pq) input.value = pq;
  render();
  input.focus();
})();
