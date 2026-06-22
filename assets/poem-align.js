/* Точное выравнивание «лесенки»: каждая сдвинутая строка начинается ровно
   там, где заканчивается предыдущая, плюс ширина одного символа.
   Работает для многоступенчатых лесенок. CSS-отступ (--i в ch) — запасной
   вариант до выполнения скрипта. */
(function () {
  function charWidth(ref) {
    var s = document.createElement("span");
    s.textContent = "о";
    s.style.cssText = "visibility:hidden;position:absolute;white-space:pre;";
    ref.appendChild(s);
    var w = s.getBoundingClientRect().width;
    s.remove();
    return w;
  }

  function align() {
    document.querySelectorAll(".poem").forEach(function (poem) {
      var poemLeft = poem.getBoundingClientRect().left;
      var gap = charWidth(poem);
      var prev = null;
      poem.querySelectorAll(".l, .stanza-break").forEach(function (el) {
        if (!el.classList.contains("l")) return; // разрыв строфы пропускаем
        var di = parseInt(el.getAttribute("data-i") || "0", 10);
        if (di > 0 && prev) {
          var r = document.createRange();
          r.selectNodeContents(prev);
          var right = r.getBoundingClientRect().right;
          el.style.paddingLeft = Math.max(0, right - poemLeft + gap) + "px";
        } else {
          el.style.paddingLeft = "";
        }
        prev = el;
      });
    });
  }

  function run() { try { align(); } catch (e) {} }

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(run);
  }
  if (document.readyState === "complete") { run(); }
  else { window.addEventListener("load", run); }

  var t;
  window.addEventListener("resize", function () {
    clearTimeout(t);
    t = setTimeout(run, 150);
  });
})();
