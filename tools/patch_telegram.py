"""Telegram Mini App mode for index.html. Active only when the page is opened inside Telegram
(the URL then carries tgWebAppData); the ordinary site is unchanged.

- loads telegram-web-app.js on demand, calls ready()/expand(), dark header and background
- disables Telegram's swipe-down-to-close, so dragging the map down does not close the app
- full screen on phones, panels respect Telegram's safe areas
- external links open outside the app (t.me links inside Telegram), light haptics on buttons
- a "Поділитися" button shares the app link in a Telegram chat
Applied once: python3 tools/patch_telegram.py index.html
"""
import sys

p = sys.argv[1]
s = open(p).read()

def rep(old, new):
    global s
    assert old in s, old[:90]
    s = s.replace(old, new, 1)

BOT_LINK = ""   # e.g. https://t.me/CyberKyivBot/map — filled in once the bot exists

CSS = '''
/* Telegram Mini App: keep clear of Telegram's own controls and the phone's notch */
html.tg .panel{top:calc(16px + var(--tg-safe-area-inset-top,0px) + var(--tg-content-safe-area-inset-top,0px))}
html.tg .dock{bottom:calc(16px + var(--tg-safe-area-inset-bottom,0px) + var(--tg-content-safe-area-inset-bottom,0px))}
html.tg .compass{top:calc(16px + var(--tg-safe-area-inset-top,0px) + var(--tg-content-safe-area-inset-top,0px))}
.tag.share{color:var(--ink);background:none;cursor:pointer;font:inherit;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase}
@media (max-width:640px){
  html.tg .panel{top:0;padding-top:calc(8px + var(--tg-safe-area-inset-top,0px) + var(--tg-content-safe-area-inset-top,0px))}
  html.tg .dock{bottom:0;padding-bottom:calc(6px + var(--tg-safe-area-inset-bottom,0px) + var(--tg-content-safe-area-inset-bottom,0px))}
  html.tg .compass{top:auto}
  .tag.share{font-size:9px}
}
'''

JS = '''<script>
/* ---------- Telegram Mini App ---------- */
(function(){
  const inTg = /tgWebApp/.test(location.hash + location.search) || !!window.TelegramWebviewProxy;
  if (!inTg) return;
  document.documentElement.classList.add("tg");
  const BOT_LINK = "''' + BOT_LINK + '''";
  const s = document.createElement("script");
  s.src = "https://telegram.org/js/telegram-web-app.js"; s.onload = init; document.head.appendChild(s);
  function init(){
    const tg = window.Telegram && Telegram.WebApp; if (!tg) return;
    const v = x => { try { return tg.isVersionAtLeast(x); } catch(e) { return false; } };
    const safe = f => { try { f(); } catch(e) {} };
    safe(()=> tg.ready()); safe(()=> tg.expand());
    if (v("6.1")) safe(()=>{ tg.setHeaderColor("#070b17"); tg.setBackgroundColor("#070b17"); });
    if (v("7.10")) safe(()=> tg.setBottomBarColor("#0a0f20"));
    if (v("7.7")) safe(()=> tg.disableVerticalSwipes());          // dragging the map down must not close the app
    if (v("8.0") && /^(ios|android)$/.test(tg.platform)) safe(()=> tg.requestFullscreen());
    // links leave the app instead of replacing it
    document.addEventListener("click", e=>{
      const a = e.target.closest && e.target.closest("a[href]"); if (!a) return;
      const u = a.href; if (!/^https?:/.test(u) || u.startsWith(location.origin + "/")) return;
      e.preventDefault();
      if (/^https:\\/\\/t\\.me\\//.test(u)) safe(()=> tg.openTelegramLink(u)); else safe(()=> tg.openLink(u));
    }, true);
    // a light tick on every button
    if (tg.HapticFeedback && v("6.1")) document.addEventListener("click", e=>{
      if (e.target.closest && e.target.closest("button")) safe(()=> tg.HapticFeedback.selectionChanged());
    }, true);
    // share the app in a chat
    const sh = document.getElementById("tgShare");
    if (sh){
      sh.hidden = false;
      sh.onclick = ()=> safe(()=> tg.openTelegramLink("https://t.me/share/url?url=" + encodeURIComponent(BOT_LINK || "https://cyber-kyiv.online/") +
        "&text=" + encodeURIComponent("Cyber Kyiv — Ситуація в Києві та Київській області")));
    }
    // Telegram resizes the view and its safe areas: lay the page out again
    const re = ()=> dispatchEvent(new Event("resize"));
    ["viewportChanged","safeAreaChanged","contentSafeAreaChanged","fullscreenChanged"].forEach(ev => safe(()=> tg.onEvent(ev, re)));
    setTimeout(re, 50);
  }
})();
</script>
'''

rep('/* compact phone layout: full-width slim bars top and bottom */', CSS.strip() + '\n/* compact phone layout: full-width slim bars top and bottom */')
rep('<script data-goatcounter=', JS + '<script data-goatcounter=')
rep('<span class="head-r">', '<span class="head-r"><button type="button" class="tag share" id="tgShare" hidden>Поділитися</button>')
open(p, "w").write(s)
print("ok")
