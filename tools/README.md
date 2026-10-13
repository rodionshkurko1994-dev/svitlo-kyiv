# Як перебудувати модель міста

Інструменти, якими зібрано `kyiv3d.txt` (будинки, вулиці, вода з OpenStreetMap).

1. Вивантаження OSM для Києва (`.osm.pbf`, область 30.23,50.21 – 30.83,50.59), наприклад з extract.bbbike.org.
2. `pip install osmium shapely numpy`
3. `python3 tools/osm_extract.py <файл.osm.pbf>` → `extract.pkl`
4. `python3 tools/build_city.py` → `kyiv3d.bin` + `meta.json`, потім `base64 -w0 kyiv3d.bin > kyiv3d.txt`.

Шляхи всередині скриптів вказують на робочу папку, де їх створено; перед запуском поправте змінні `OSM`/`RAW` на свої.
