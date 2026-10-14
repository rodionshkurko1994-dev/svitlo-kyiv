"""One-off probe: what does the DTEK Kyiv outages page expose to a script?"""
import urllib.parse
import re, json, urllib.request, http.cookiejar, pathlib, sys
OUT = pathlib.Path("data/probe"); OUT.mkdir(parents=True, exist_ok=True)
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
report = {}
def fetch(url, data=None, headers=None):
    h = {"User-Agent": UA, "Accept-Language": "uk-UA,uk;q=0.9"}; h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with op.open(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:3000]
    except Exception as e:
        return -1, repr(e)
for url in ["https://www.dtek-kem.com.ua/ua/shutdowns", "https://www.dtek-kem.com.ua/ua/outages"]:
    st, body = fetch(url)
    key = url.rsplit("/", 1)[1]
    report[key] = {"status": st, "len": len(body), "title": (re.search(r"<title>(.*?)</title>", body, re.S) or [None, None])[1] if st == 200 else None,
                   "incapsula": "incapsula" in body.lower() or "_Incapsula_" in body,
                   "csrf": bool(re.search(r'name="csrf-token" content="([^"]+)"', body)),
                   "vars": sorted(set(re.findall(r"(DisconSchedule\.\w+)\s*=", body)))}
    (OUT / f"dtek_{key}.html").write_text(body[:400000])
    # save the inline data blocks, if any
    for m in re.finditer(r"DisconSchedule\.(\w+)\s*=\s*(\{.*?\})\s*(?:;|\n)", body, re.S):
        (OUT / f"dtek_{key}_{m.group(1)}.json").write_text(m.group(2)[:2_000_000])
    tok = re.search(r'name="csrf-token" content="([^"]+)"', body)
    if st == 200 and tok:
        form = "method=getHomeNum&data[0][name]=street&data[0][value]=" + urllib.parse.quote("вул. Хрещатик")
        st2, b2 = fetch("https://www.dtek-kem.com.ua/ua/ajax", form.encode(), {"X-CSRF-Token": tok.group(1), "X-Requested-With": "XMLHttpRequest",
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Referer": url})
        report[key]["ajax_status"] = st2; report[key]["ajax_head"] = b2[:3000]
        (OUT / f"dtek_{key}_ajax.json").write_text(b2[:500000])
import urllib.parse
(OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
print(json.dumps(report, ensure_ascii=False, indent=1)[:4000])
