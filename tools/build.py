#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генерация статического сайта shelamov.ru из кэша Google Sites (tools/cache).

- Стихи: каждая строка — <span class="l" style="--i:N"> с отступом «лесенки»
  (N = число ведущих пробелов оригинала). Текст не нормализуется — ударения
  и спец-символы сохраняются дословно.
- Блок стиха центрируется, текст внутри по левому краю (CSS .poem).
- Листание prev/next в пределах сборника.
- SEO: title/description/canonical/OpenGraph/JSON-LD, sitemap.xml, robots.txt.
Результат пишется в корень репозитория (../ относительно tools/)."""

import os, re, json, html, hashlib, shutil
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "cache")
IMG_DIR = os.path.join(ROOT, "assets", "img")

DOMAIN = "https://shelamov.ru"
SITE = "Николай Шеламов"
AUTHOR = "Николай Шеламов"
TAGLINE = "Поэзия"

COLLECTIONS = [   # порядок отображения и человекочитаемые названия
    ("na-otchey-storone", "На отчей стороне"),
    ("samoe-dorogoe",     "Самое дорогое"),
    ("strofarii",         "Строфарии"),
    ("other",             "Вне сборников"),
]
COLL_NAME = dict(COLLECTIONS)

BOOKS = [   # файл в /books → название книги (формат .ibooks / Apple Books)
    ("Naotcheystorone.ibooks", "На отчей стороне"),
    ("Samoe_dorogoe.ibooks",   "Самое дорогое"),
    ("Strofarii.ibooks",       "Строфарии"),
]

AUDIO = {   # slug стиха → mp3-файл в /music (песня на эти стихи)
    "za-klukvoj": "vstali-do-rassveta.mp3",
    "o-materi":   "kvas-varganili.mp3",
}

struct = json.load(open(os.path.join(HERE, "struct.json"), encoding="utf-8"))


# --------------------------------------------------------------------------- #
#  Парсинг кэша                                                                #
# --------------------------------------------------------------------------- #
def cache_name(path):
    return path.strip("/").replace("/", "__") or "__home"


def load(path):
    f = os.path.join(CACHE, cache_name(path) + ".html")
    return BeautifulSoup(open(f, encoding="utf-8").read(), "html.parser")


def main_region(soup):
    # У Google Sites контент стихов лежит ВНЕ [role=main], поэтому работаем
    # по всему документу: выборка p.CDt4Ke и так чистая (без шапки/подвала).
    return soup


def content_paragraphs(soup):
    """Возвращает список <p> основного контентного блока (без заголовка)."""
    m = main_region(soup)
    ps = [p for p in m.select("p.CDt4Ke") if "duRjpb" not in (p.get("class") or [])]
    if not ps:
        return []
    # выбираем родителя с наибольшим числом таких <p> — это блок текста
    from collections import Counter
    cnt = Counter(id(p.parent) for p in ps)
    best = cnt.most_common(1)[0][0]
    parent = next(p.parent for p in ps if id(p.parent) == best)
    return [c for c in parent.children if getattr(c, "name", None) == "p"]


def _fully(p, tags):
    """True, если весь текст абзаца обёрнут в один из тегов tags (em/i/strong/b)."""
    txt = p.get_text().replace("\xa0", " ").strip()
    inner = "".join(e.get_text() for e in p.find_all(tags)).replace("\xa0", " ").strip()
    return bool(txt) and inner == txt


def line_of(p):
    """(текст, число ведущих пробелов, курсив?). '' -> разрыв строфы.
    Курсив (<em>/<i>) в стихах = посвящение/эпиграф."""
    raw = p.get_text().replace("\xa0", " ").replace("\r", "")
    raw = raw.replace("\n", " ").rstrip()
    indent = len(raw) - len(raw.lstrip(" "))
    return raw.strip(), indent, _fully(p, ["em", "i"])


def page_title(soup, fallback):
    h1 = main_region(soup).find(["h1", "h2"])
    if h1 and h1.get_text().strip():
        return h1.get_text().strip()
    t = (soup.title.string or "").strip()
    if " - " in t:
        return t.split(" - ", 1)[1].strip()
    return fallback


def parse_poem(path):
    soup = load(path)
    title = page_title(soup, path)
    lines = [line_of(p) for p in content_paragraphs(soup)]
    # убрать пустые строки в начале/конце
    while lines and lines[0][0] == "":
        lines.pop(0)
    while lines and lines[-1][0] == "":
        lines.pop()
    return title, lines


# --------------------------------------------------------------------------- #
#  Изображения                                                                 #
# --------------------------------------------------------------------------- #
def download_portrait():
    """Скачивает портрет автора с главной в assets/img/portrait.jpg."""
    os.makedirs(IMG_DIR, exist_ok=True)
    dest = os.path.join(IMG_DIR, "portrait.jpg")
    if os.path.exists(dest):
        return "/assets/img/portrait.jpg"
    soup = load("/")
    img = None
    for im in main_region(soup).find_all("img"):
        src = im.get("src", "")
        if "googleusercontent" in src and "sitesv" in src:
            img = src
            break
    if not img:
        return None
    try:
        import requests
        r = requests.get(img, timeout=30, headers={
            "User-Agent": "Mozilla/5.0", "Referer": "https://www.shelamov.ru/"})
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            open(dest, "wb").write(r.content)
            return "/assets/img/portrait.jpg"
    except Exception as e:
        print("  portrait download failed:", e)
    return None


# --------------------------------------------------------------------------- #
#  Шаблон                                                                      #
# --------------------------------------------------------------------------- #
def ru_dashes(s):
    """Типографика: лишние пробелы убрать; дефис/эн-деш, употреблённый как
    тире (окружён пробелами / в начале / в конце строки), → тире «—»
    с неразрывным пробелом перед ним. Внутрисловные дефисы не трогаем."""
    s = re.sub(r" {2,}", " ", s)
    s = re.sub(r"(?<=\S) [-–] (?=\S)", " — ", s)   # середина: сло­во — слово
    s = re.sub(r" [-–](?=\s*$)", " —", s)            # конец строки
    s = re.sub(r"^[-–] ", "— ", s)                        # начало строки
    return s


def esc(s):
    return html.escape(ru_dashes(s), quote=True)


NAV = [
    ("/", "Главная"),
    ("/st/", "Стихи"),
    ("/ob-avtore/", "Об авторе"),
    ("/elektronnye-knigi/", "Электронные книги"),
]


def nav_html(active_prefix):
    out = []
    for href, label in NAV:
        cur = ""
        if href == "/" and active_prefix == "/":
            cur = ' aria-current="page"'
        elif href != "/" and active_prefix.startswith(href):
            cur = ' aria-current="page"'
        out.append(f'<a href="{href}"{cur}>{esc(label)}</a>')
    return '<nav class="nav"><div class="nav__inner">' + "".join(out) + "</div></nav>"


def breadcrumbs(items):
    # items: list of (href|None, label). Последний — текущий.
    parts = []
    for i, (href, label) in enumerate(items):
        if href and i < len(items) - 1:
            parts.append(f'<a href="{href}">{esc(label)}</a>')
        else:
            parts.append(f'<span aria-current="page">{esc(label)}</span>')
    return '<div class="breadcrumbs">' + ' › '.join(parts) + "</div>"


def page(out_path, *, title, description, body, active="/", canonical,
         jsonld=None, og_image=None):
    desc = esc(description[:300])
    head_extra = ""
    if jsonld:
        head_extra += '\n<script type="application/ld+json">' + json.dumps(
            jsonld, ensure_ascii=False) + "</script>"
    og_img_tag = ""
    if og_image:
        og_img_tag = f'\n<meta property="og:image" content="{DOMAIN}{og_image}">'
    doc = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<meta name="author" content="{esc(AUTHOR)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(SITE)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:locale" content="ru_RU">{og_img_tag}
<meta name="twitter:card" content="summary">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/style.css">{head_extra}
</head>
<body>
<header class="site-header"><div class="site-header__inner">
<p class="site-title"><a href="/">{esc(SITE)}</a></p>
<p class="site-tagline">{esc(TAGLINE)}</p>
</div></header>
{nav_html(active)}
<main>
{body}
</main>
<footer class="site-footer">
<p>© {esc(AUTHOR)}. Стихи и материалы сайта.</p>
</footer>
<script defer src="/assets/poem-align.js"></script>
</body>
</html>
"""
    full = os.path.join(ROOT, out_path.lstrip("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w", encoding="utf-8").write(doc)


# --------------------------------------------------------------------------- #
#  Рендер контента                                                            #
# --------------------------------------------------------------------------- #
def poem_body_html(lines):
    """lines: список (текст, отступ, курсив?). Курсивные строки рендерятся
    отдельным блоком посвящения (справа) или эпиграфа (для длинных)."""
    blocks = []
    verse = []

    def flush():
        if verse:
            blocks.append('<div class="poem">' + "\n".join(verse) + "</div>")
            verse.clear()

    i, n = 0, len(lines)
    while i < n:
        text, indent, ital = lines[i]
        if text and ital:
            flush()
            run = []
            while i < n and lines[i][0] and lines[i][2]:
                run.append(lines[i][0]); i += 1
            cls = "epigraph" if any(len(x) > 70 for x in run) else "dedication"
            blocks.append(f'<div class="{cls}">'
                          + "".join(f"<span>{esc(x)}</span>" for x in run) + "</div>")
            continue
        if text == "":
            verse.append('<span class="stanza-break"></span>')
        else:
            attr = f' style="--i:{indent}" data-i="{indent}"' if indent else ""
            verse.append(f'<span class="l"{attr}>{esc(text)}</span>')
        i += 1
    flush()
    return "\n".join(blocks)


QUOTE_CHARS = "«»\"„“”  "
_UPPER = re.compile(r"[А-ЯЁ]{4,}")


def _norm(s):
    s = s.lower().replace("ё", "е")
    s = re.sub(r"[^а-я ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _is_prose(text, indent):
    """Абзац прозы: красная строка (ind 3–6), длинное предложение или строка
    с двоеточием. Иначе — поэтическая строка (цитата)."""
    if indent in (3, 4, 5, 6):
        return True
    if len(text) > 55:
        return True
    if text.endswith(":") and len(text) > 12:
        return True
    return False


def _coll_rank(coll):
    for i, (c, _) in enumerate(COLLECTIONS):
        if c == coll:
            return i
    return 99


def _find_source(qlines, corpus, poemreg, poemconcat):
    """Ищет наш стих-источник цитаты. Возвращает (kind, coll, slug, pidx):
    kind='exact' — дословное непрерывное совпадение (можно воспроизвести точно);
    kind='fuzzy' — стих найден (по подстроке или ≥2 строкам) — только ссылка."""
    nq = [_norm(q) for q in qlines]
    # 1) точное непрерывное совпадение по строкам
    for coll, slug, pidx in corpus.get(nq[0], []):
        seg = poemreg[(coll, slug)][1][pidx:pidx + len(qlines)]
        if [_norm(t) for t, _i, _it in seg] == nq:
            return ("exact", coll, slug, pidx)
    # 2) по склеенному тексту (ловит разную разбивку на строки / лесенку)
    qc = " ".join(x for x in nq if x)
    if len(qc) >= 20:
        hits = [cs for cs, pc in poemconcat.items() if qc in pc]
        if hits:
            hits.sort(key=lambda k: _coll_rank(k[0]))
            return ("fuzzy", hits[0][0], hits[0][1], None)
    # 3) по числу совпавших строк (цитата с пропусками «…»)
    cnt = {}
    for q in nq:
        for coll, slug, _idx in corpus.get(q, []):
            cnt[(coll, slug)] = cnt.get((coll, slug), 0) + 1
    if cnt:
        best = max(cnt.values())
        if best >= 2:
            winners = sorted((k for k, v in cnt.items() if v == best),
                             key=lambda k: _coll_rank(k[0]))
            return ("fuzzy", winners[0][0], winners[0][1], None)
    return None


def render_about(paras, corpus, poemreg, poemconcat):
    """paras: список dict(t, ind, em, strong).
    <strong> → заголовок; <em>/«ёлочки»/короткие строки → цитаты стихов
    (в общем «стиховом» стиле, со ссылкой на полный текст); остальное — проза
    без красных строк. Подпись автора (курсив, ЗАГЛАВНЫМИ в конце) — особый стиль."""
    paras = [p for p in paras if p["t"] != ""]

    def kind_of(p):
        if p["strong"]:
            return "title"
        if p["em"]:
            return "quote"
        if _is_prose(p["t"], p["ind"]):
            return "prose"
        return "quote"

    # сгруппировать подряд идущие цитатные строки
    groups = []
    i, n = 0, len(paras)
    while i < n:
        k = kind_of(paras[i])
        if k == "quote":
            j = i
            while j < n and kind_of(paras[j]) == "quote":
                j += 1
            groups.append(("quote", list(range(i, j)))); i = j
        else:
            groups.append((k, [i])); i += 1

    parts = []
    for gi, (kind, idxs) in enumerate(groups):
        if kind == "prose":
            parts.append(f"<p>{esc(paras[idxs[0]]['t'])}</p>")
            continue
        if kind == "title":
            parts.append(f'<p class="article-heading">{esc(paras[idxs[0]]["t"])}</p>')
            continue
        # quote
        qpairs = [(paras[x]["t"].strip(QUOTE_CHARS), paras[x]["ind"]) for x in idxs]
        qlines = [t for t, _ in qpairs]
        all_em = all(paras[x]["em"] for x in idxs)
        # подпись автора в самом конце (курсив + слово ЗАГЛАВНЫМИ)
        if gi == len(groups) - 1 and all_em and any(_UPPER.search(t) for t in qlines):
            sig = "".join(f"<span>{esc(t)}</span>" for t in qlines)
            parts.append(f'<div class="prose-signature">{sig}</div>')
            continue
        src = _find_source(qlines, corpus, poemreg, poemconcat)
        link = ""
        if src:
            _kind, coll, slug, pidx = src
            title = poemreg[(coll, slug)][0]
            link = (f'<p class="quote-source"><a href="/st/{coll}/{slug}/">'
                    f'полный текст: «{esc(title)}»</a></p>')
        if src and src[0] == "exact":
            _k, coll, slug, pidx = src
            seg = poemreg[(coll, slug)][1][pidx:pidx + len(qlines)]
        else:
            seg = [(t, ind, False) for t, ind in qpairs]
        parts.append(f'<blockquote class="quote">{poem_body_html(seg)}{link}</blockquote>')
    return '<div class="prose">' + "\n".join(parts) + "</div>"


def first_lines(lines, n=2):
    res = [x[0] for x in lines if x[0] and not x[2]][:n]
    return " / ".join(res)


# --------------------------------------------------------------------------- #
#  Генерация                                                                   #
# --------------------------------------------------------------------------- #
def build():
    # 1) разобрать все стихи
    poems = {}   # (coll, slug) -> (title, lines)
    for coll, slugs in struct.items():
        for s in slugs:
            poems[(coll, s)] = parse_poem(f"/st/{coll}/{s}")

    # корпус строк для сопоставления цитат в статьях об авторе
    poemreg = {}     # (coll, slug) -> (title, [(text, indent, ital) непустых строк])
    corpus = {}      # _norm(text) -> [(coll, slug, idx_среди_непустых)]
    poemconcat = {}  # (coll, slug) -> склеенный нормализованный текст стиха
    for (coll, s), (title, lines) in poems.items():
        nonempty = [(t, ind, it) for t, ind, it in lines if t]
        poemreg[(coll, s)] = (title, nonempty)
        poemconcat[(coll, s)] = " ".join(_norm(t) for t, _i, _it in nonempty)
        for idx, (t, _ind, _it) in enumerate(nonempty):
            corpus.setdefault(_norm(t), []).append((coll, s, idx))

    portrait = download_portrait()

    # 2) страницы стихов с prev/next
    for coll, _name in COLLECTIONS:
        slugs = struct.get(coll, [])
        for i, s in enumerate(slugs):
            title, lines = poems[(coll, s)]
            url = f"/st/{coll}/{s}/"
            canonical = DOMAIN + url
            prev_s = slugs[i - 1] if i > 0 else None
            next_s = slugs[i + 1] if i < len(slugs) - 1 else None
            nav = ['<nav class="poem-nav">']
            if prev_s:
                pt = poems[(coll, prev_s)][0]
                nav.append(f'<a class="prev" href="/st/{coll}/{prev_s}/">'
                           f'<span class="dir">← Предыдущее</span>'
                           f'<span class="t">{esc(pt)}</span></a>')
            nav.append(f'<a class="to-collection" href="/st/{coll}/">'
                       f'{esc(COLL_NAME[coll])}</a>')
            if next_s:
                nt = poems[(coll, next_s)][0]
                nav.append(f'<a class="next" href="/st/{coll}/{next_s}/">'
                           f'<span class="dir">Следующее →</span>'
                           f'<span class="t">{esc(nt)}</span></a>')
            nav.append("</nav>")

            audio = ""
            if s in AUDIO:
                audio = (
                    '<figure class="song">'
                    '<figcaption>Песня на эти стихи</figcaption>'
                    f'<audio controls preload="none" src="/music/{AUDIO[s]}"></audio>'
                    '</figure>')
            body = (breadcrumbs([("/", "Главная"), ("/st/", "Стихи"),
                                 (f"/st/{coll}/", COLL_NAME[coll]), (None, title)])
                    + f'<h1 class="page-title">{esc(title)}</h1>'
                    + '<hr class="title-rule">'
                    + poem_body_html(lines)
                    + audio
                    + "\n".join(nav))
            desc = f"{title} — стихотворение. {first_lines(lines)}"
            jsonld = {
                "@context": "https://schema.org",
                "@type": "CreativeWork",
                "name": title,
                "headline": title,
                "inLanguage": "ru",
                "genre": "Поэзия",
                "isPartOf": COLL_NAME[coll],
                "author": {"@type": "Person", "name": AUTHOR},
                "url": canonical,
            }
            page(url + "index.html", title=f"{title} — {SITE}", description=desc,
                 body=body, active="/st/", canonical=canonical, jsonld=jsonld)

    # 3) индексы сборников
    for coll, name in COLLECTIONS:
        slugs = struct.get(coll, [])
        items = []
        for s in slugs:
            t, lines = poems[(coll, s)]
            prev = esc(first_lines(lines, 1))
            items.append(f'<li><a href="/st/{coll}/{s}/">'
                         f'<span class="t">{esc(t)}</span>'
                         f'<span class="preview">{prev}</span></a></li>')
        body = (breadcrumbs([("/", "Главная"), ("/st/", "Стихи"), (None, name)])
                + f'<h1 class="page-title">{esc(name)}</h1>'
                + '<hr class="title-rule">'
                + f'<ul class="poem-list">{"".join(items)}</ul>')
        canonical = f"{DOMAIN}/st/{coll}/"
        page(f"/st/{coll}/index.html", title=f"{name} — {SITE}",
             description=f"Сборник «{name}» — стихи {AUTHOR}а. Всего {len(slugs)}.",
             body=body, active="/st/", canonical=canonical)

    # 4) раздел «Стихи» (список сборников)
    items = []
    for coll, name in COLLECTIONS:
        n = len(struct.get(coll, []))
        items.append(f'<li><a href="/st/{coll}/"><span class="c-title">{esc(name)}</span></a>'
                     f'<span class="c-count">{n} стихотворений</span></li>')
    body = (breadcrumbs([("/", "Главная"), (None, "Стихи")])
            + '<h1 class="page-title">Стихи</h1><hr class="title-rule">'
            + f'<ul class="collection-list">{"".join(items)}</ul>')
    page("/st/index.html", title=f"Стихи — {SITE}",
         description=f"Сборники стихов {AUTHOR}а: " +
                     ", ".join(n for _, n in COLLECTIONS) + ".",
         body=body, active="/st/", canonical=f"{DOMAIN}/st/")

    # 5) главная
    home = load("/")
    hlines = [line_of(p) for p in content_paragraphs(home)]
    date = ""
    if hlines and re.match(r"^\d{2}\.\d{2}\.\d{4}", hlines[0][0]):
        date = hlines[0][0]
        hlines = hlines[1:]
    while hlines and hlines[0][0] == "":
        hlines.pop(0)
    portrait_html = f'<img class="portrait" src="{portrait}" alt="{esc(AUTHOR)}">' if portrait else ""
    body = (
        '<div class="intro">'
        + portrait_html
        + f'<h1 class="page-title">{esc(AUTHOR)}</h1>'
        + '<hr class="title-rule">'
        + '<p class="intro__lead">Стихи о родной земле, природе и памяти.</p>'
        + '</div>'
        + (f'<p class="featured-label">{esc(date)}</p>' if date else "")
        + poem_body_html(hlines)
        + '<p class="center" style="margin-top:2.5rem">'
          '<a class="btn" href="/st/">Все стихи →</a></p>'
    )
    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "name": SITE, "url": DOMAIN, "inLanguage": "ru"},
            {"@type": "Person", "name": AUTHOR, "url": DOMAIN,
             "jobTitle": "Поэт", **({"image": DOMAIN + portrait} if portrait else {})},
        ],
    }
    page("/index.html", title=f"{SITE} — стихи", active="/",
         description="Официальный сайт поэта Николая Шеламова: стихи, сборники, "
                     "биография. На отчей стороне, Самое дорогое, Строфарии.",
         body=body, canonical=DOMAIN + "/", jsonld=jsonld,
         og_image=portrait)

    # 6) Об авторе (хаб)
    body = (breadcrumbs([("/", "Главная"), (None, "Об авторе")])
            + '<h1 class="page-title">Об авторе</h1><hr class="title-rule">'
            + '<ul class="collection-list">'
            + '<li><a href="/ob-avtore/aleksandr-sytin/"><span class="c-title">Александр Сытин</span></a></li>'
            + '<li><a href="/ob-avtore/larisa-kuznecova/"><span class="c-title">Лариса Кузнецова</span></a></li>'
            + '</ul>')
    page("/ob-avtore/index.html", title=f"Об авторе — {SITE}",
         description=f"Об авторе — статьи о поэте {AUTHOR}е.",
         body=body, active="/ob-avtore/", canonical=f"{DOMAIN}/ob-avtore/")

    # 7) статьи об авторе
    for slug, who in [("aleksandr-sytin", "Александр Сытин"),
                      ("larisa-kuznecova", "Лариса Кузнецова")]:
        soup = load(f"/ob-avtore/{slug}")
        title = page_title(soup, who)
        paras = []
        for p in content_paragraphs(soup):
            t, ind, em = line_of(p)
            paras.append({"t": t, "ind": ind, "em": em, "strong": _fully(p, ["strong", "b"])})
        body = (breadcrumbs([("/", "Главная"), ("/ob-avtore/", "Об авторе"),
                             (None, title)])
                + f'<h1 class="page-title">{esc(title)}</h1><hr class="title-rule">'
                + render_about(paras, corpus, poemreg, poemconcat))
        desc = next((p["t"] for p in paras if p["t"] and not p["em"]), title)[:200]
        page(f"/ob-avtore/{slug}/index.html", title=f"{esc(title)} — {SITE}",
             description=desc, body=body, active="/ob-avtore/",
             canonical=f"{DOMAIN}/ob-avtore/{slug}/")

    # 8) электронные книги (.ibooks, размещены в /books)
    cards = []
    for fname, btitle in BOOKS:
        fpath = os.path.join(ROOT, "books", fname)
        size_mb = (os.path.getsize(fpath) / (1024 * 1024)) if os.path.exists(fpath) else 0
        cards.append(
            '<li class="book-card">'
            '<span class="book-card__icon">'
            '<img src="/assets/ibooks-icon.svg" alt="Формат iBooks" width="58" height="58"></span>'
            '<span class="book-card__body">'
            f'<span class="book-card__title">{esc(btitle)}</span>'
            f'<span class="book-card__meta">Формат iBooks (Apple Books) · {size_mb:.1f} МБ</span>'
            '</span>'
            f'<a class="btn book-card__btn" href="/books/{fname}" download>Скачать</a>'
            '</li>')
    body = (breadcrumbs([("/", "Главная"), (None, "Электронные книги")])
            + '<h1 class="page-title">Электронные книги</h1><hr class="title-rule">'
            + '<p class="center">Сборники стихов в формате <strong>iBooks</strong> '
              '— для приложения «Книги» (Apple&nbsp;Books) на Mac, iPad и iPhone.</p>'
            + f'<ul class="books">{"".join(cards)}</ul>')
    page("/elektronnye-knigi/index.html", title=f"Электронные книги — {SITE}",
         description=f"Электронные книги поэта {AUTHOR}а — чтение и скачивание.",
         body=body, active="/elektronnye-knigi/",
         canonical=f"{DOMAIN}/elektronnye-knigi/")

    # 9) служебные файлы
    write_sitemap()
    write_robots()
    write_404()
    write_redirect("/news/index.html", "/")
    open(os.path.join(ROOT, "CNAME"), "w").write("shelamov.ru\n")
    write_favicon()
    write_nojekyll()

    print("Готово. Стихов:", len(poems))


def all_urls():
    urls = ["/", "/st/", "/ob-avtore/", "/ob-avtore/aleksandr-sytin/",
            "/ob-avtore/larisa-kuznecova/", "/elektronnye-knigi/"]
    for coll, _ in COLLECTIONS:
        urls.append(f"/st/{coll}/")
        for s in struct.get(coll, []):
            urls.append(f"/st/{coll}/{s}/")
    return urls


def write_sitemap():
    items = "\n".join(
        f"  <url><loc>{DOMAIN}{u}</loc></url>" for u in all_urls())
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           f"{items}\n</urlset>\n")
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(xml)


def write_robots():
    txt = ("User-agent: *\nAllow: /\n\n"
           f"Sitemap: {DOMAIN}/sitemap.xml\n")
    open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8").write(txt)


def write_404():
    body = ('<div class="center"><h1 class="page-title">Страница не найдена</h1>'
            '<hr class="title-rule">'
            '<p>К сожалению, такой страницы нет. '
            '<a href="/">Вернуться на главную</a> или перейти к '
            '<a href="/st/">стихам</a>.</p></div>')
    page("/404.html", title=f"Страница не найдена — {SITE}",
         description="Страница не найдена.", body=body, active="",
         canonical=f"{DOMAIN}/404.html")


def write_redirect(out_path, target):
    doc = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<title>Переход…</title><link rel="canonical" href="{DOMAIN}{target}">
<meta http-equiv="refresh" content="0; url={target}">
<meta name="robots" content="noindex">
</head><body><p>Страница переехала. <a href="{target}">Перейти</a>.</p>
<script>location.replace("{target}");</script></body></html>"""
    full = os.path.join(ROOT, out_path.lstrip("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w", encoding="utf-8").write(doc)


def write_favicon():
    # простой favicon — монограмма «Ш» на бумажном фоне
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
           '<rect width="64" height="64" rx="8" fill="#faf6ec"/>'
           '<text x="32" y="46" font-family="Georgia,serif" font-size="42" '
           'text-anchor="middle" fill="#7c2d12">Ш</text></svg>')
    open(os.path.join(ROOT, "assets", "favicon.svg"), "w", encoding="utf-8").write(svg)


def write_nojekyll():
    open(os.path.join(ROOT, ".nojekyll"), "w").write("")


if __name__ == "__main__":
    build()
