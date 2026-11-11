"""SEO pass for index.html: search-friendly title and description, social preview,
structured data (WebSite, WebApplication, FAQPage) and indexable text (FAQ, district
list, a per-group schedule table that scripts/build_site.py fills at publish time).
Applied once: python3 tools/patch_seo.py index.html
"""
import json, sys, html

p = sys.argv[1]
s = open(p).read()

def rep(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

URL = "https://cyber-kyiv.online/"
TITLE = "Відключення світла Київ — графік і карта онлайн | Cyber Kyiv"
DESC = ("Де зараз є світло в Києві: 3D-карта відключень по кожному будинку за графіками YASNO (ДТЕК). "
        "Оновлення кожні 15 хвилин, прогноз на 48 годин, екстрені відключення.")
SHORT = "3D-карта Києва: у яких будинках зараз є світло, а в яких ні, за графіками відключень YASNO (ДТЕК)."

FAQ = [
    ("Як дізнатися свою групу відключень світла в Києві?",
     'Натисніть на свій будинок на карті: підказка покаже групу YASNO, стан зараз і час наступного вмикання чи вимкнення. '
     'Точну групу своєї адреси можна перевірити на <a href="https://www.dtek-kem.com.ua/ua/shutdowns" target="_blank" rel="noopener">сайті ДТЕК Київські електромережі</a>, '
     'на <a href="https://yasno.ua" target="_blank" rel="noopener">yasno.ua</a> або в застосунку «Київ Цифровий».'),
    ("Чому в сусідніх будинках різний графік відключень?",
     "З 12–13 жовтня 2026 року в Києві немає черг: ДТЕК розраховує графік окремо для кожного будинку, "
     "а YASNO відносить кожну адресу до однієї з 60 груп. Тому навіть сусідні будинки можуть мати різний графік."),
    ("Коли дадуть світло?",
     "Натисніть на будинок: підказка покаже, о котрій за графіком увімкнуть або вимкнуть світло. "
     "Повзунок унизу карти показує, як змінюватиметься ситуація в місті протягом 48 годин."),
    ("Що таке екстрені відключення?",
     "Коли енергосистема перевантажена, ДТЕК вводить екстрені відключення, і планові графіки тимчасово не діють. "
     "Тоді карта показує останній відомий графік приглушеним кольором і позначку «екстрені»: світло можуть вимкнути й поза графіком."),
    ("Як часто оновлюється карта?",
     "Графік YASNO перевіряється кожні 15 хвилин, а відкрита сторінка підтягує нові дані кожні 5 хвилин, без перезавантаження."),
    ("Наскільки точна карта?",
     "Карта показує планові графіки, а не фактичний стан мережі. Частина будинків пофарбована за власною адресою, "
     "решта — за найближчим перевіреним будинком у радіусі 150 м. Під час аварій світла може не бути й поза графіком."),
]
DISTRICTS = ["Голосіївський", "Дарницький", "Деснянський", "Дніпровський", "Оболонський",
             "Печерський", "Подільський", "Святошинський", "Солом'янський", "Шевченківський"]

def plain(h):
    import re
    return html.unescape(re.sub(r"<[^>]+>", "", h))

ld = {
    "@context": "https://schema.org",
    "@graph": [
        {"@type": "WebSite", "@id": URL + "#website", "url": URL, "name": "Cyber Kyiv",
         "alternateName": ["Svitlo Kyiv", "Карта відключень світла Київ"], "inLanguage": "uk"},
        {"@type": "WebApplication", "@id": URL + "#app", "name": "Cyber Kyiv — карта відключень світла",
         "url": URL, "description": DESC, "inLanguage": "uk",
         "applicationCategory": "UtilitiesApplication", "operatingSystem": "Any", "browserRequirements": "WebGL",
         "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "UAH"},
         "areaServed": {"@type": "City", "name": "Київ", "sameAs": "https://uk.wikipedia.org/wiki/Київ"},
         "image": URL + "og-image.png", "dateModified": "__MODIFIED__", "isPartOf": {"@id": URL + "#website"}},
        {"@type": "FAQPage", "@id": URL + "#faq", "inLanguage": "uk",
         "mainEntity": [{"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": plain(a)}} for q, a in FAQ]},
    ],
}

# ---- head
a = s.index('<meta name="description"')
b = s.index('<meta name="theme-color"')
s = s[:a] + f'''<meta name="description" content="{DESC}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="{URL}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Cyber Kyiv">
<meta property="og:locale" content="uk_UA">
<meta property="og:url" content="{URL}">
<meta property="og:title" content="Відключення світла Київ — карта онлайн">
<meta property="og:description" content="{SHORT}">
<meta property="og:image" content="{URL}og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Нічна 3D-карта Києва: будинки зі світлом помаранчеві, без світла сині">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Відключення світла Київ — карта онлайн">
<meta name="twitter:description" content="{SHORT}">
<meta name="twitter:image" content="{URL}og-image.png">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False, separators=(",", ":"))}</script>
''' + s[b:]
rep('<title>Світло Києва 3D</title>', f'<title>{TITLE}</title>')

# ---- indexable text inside «Деталі»
faq_html = "\n".join(f'    <h3>{q}</h3>\n    <p class="note">{a}</p>' for q, a in FAQ)
rep('''    <p class="note">Будинки, вулиці, вода й парки взяті з OpenStreetMap''',
    '''    <p class="note">Карта охоплює всі райони Києва: ''' + ", ".join(DISTRICTS) + '''.</p>
    <p class="note">Будинки, вулиці, вода й парки взяті з OpenStreetMap''')
i = s.index('</details>\n  </div>\n  </details>\n</section>')
s = s[:i] + f'''</details>
  <details class="seo">
    <summary>Графік відключень по групах</summary>
    <div id="groupTable"><!--GROUPS--><p class="note">Графік по групах з'явиться після оновлення даних YASNO.</p><!--/GROUPS--></div>
  </details>
  <details class="seo">
    <summary>Часті питання</summary>
    <h2 class="seo-h">Відключення світла в Києві: часті питання</h2>
{faq_html}
  </details>
''' + s[i + len('</details>\n'):]

rep('.more-body{display:flex;flex-direction:column;gap:12px}', '''.more-body{display:flex;flex-direction:column;gap:12px}
.more-body details>summary{cursor:pointer}
.seo h2.seo-h{font:600 13px/1.35 var(--f-body);margin:10px 0 2px;color:var(--ink)}
.seo h3{font:600 12.5px/1.35 var(--f-body);margin:10px 0 2px;color:var(--ink)}
.seo .gt{width:100%;border-collapse:collapse;font-size:11.5px;margin-top:6px}
.seo .gt th,.seo .gt td{text-align:left;padding:3px 4px;border-bottom:1px solid var(--line);vertical-align:top}
.seo .gt th{color:var(--muted);font-weight:500}
.seo .gt td:first-child{white-space:nowrap;font-family:var(--f-mono);font-size:11px}''')

# noscript fallback for crawlers and no-WebGL browsers
rep('<canvas id="scene"', f'''<noscript><p style="position:fixed;bottom:120px;left:16px;right:16px;color:#e8ecf8;z-index:5">{SHORT} Для показу карти увімкніть JavaScript.</p></noscript>
<canvas id="scene"''')
open(p, "w").write(s)
print("ok")
