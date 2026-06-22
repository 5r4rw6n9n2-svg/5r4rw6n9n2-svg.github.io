#!/usr/bin/env python3
"""Скачивает все страницы shelamov.ru (Google Sites) в локальный кэш tools/cache.
Список страниц: 4 сборника (порядок стихов берётся из страниц сборников),
плюс служебные страницы. Кэш позволяет парсить офлайн без повторных запросов."""
import os, json, time
import requests

BASE = "https://www.shelamov.ru"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
os.makedirs(CACHE, exist_ok=True)

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (site-migration)"


def fetch(path):
    url = BASE + path
    for attempt in range(4):
        try:
            r = S.get(url, timeout=30)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r.text
            print(f"  HTTP {r.status_code} {path}")
        except Exception as e:
            print(f"  retry {path}: {e}")
        time.sleep(2)
    return None


def cache_name(path):
    return path.strip("/").replace("/", "__") or "__home"


def main():
    struct = json.load(open(os.path.join(HERE, "struct.json"), encoding="utf-8"))

    # Служебные страницы + индексы сборников
    pages = ["/", "/st", "/ob-avtore", "/ob-avtore/aleksandr-sytin",
             "/ob-avtore/larisa-kuznecova", "/elektronnye-knigi",
             "/st/other", "/st/na-otchey-storone", "/st/samoe-dorogoe", "/st/strofarii"]
    # Страницы стихов
    for coll, slugs in struct.items():
        for s in slugs:
            pages.append(f"/st/{coll}/{s}")

    print(f"Всего страниц к загрузке: {len(pages)}")
    ok = 0
    for i, path in enumerate(pages, 1):
        dest = os.path.join(CACHE, cache_name(path) + ".html")
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            ok += 1
            continue
        html = fetch(path)
        if html:
            open(dest, "w", encoding="utf-8").write(html)
            ok += 1
        if i % 20 == 0:
            print(f"  {i}/{len(pages)}")
        time.sleep(0.4)  # вежливая задержка
    print(f"Готово: {ok}/{len(pages)} в кэше {CACHE}")


if __name__ == "__main__":
    main()
