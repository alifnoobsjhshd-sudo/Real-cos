---
name: otakugifs broken endpoints
description: Which otakugifs.xyz reaction endpoints return 400 and their working replacements in _OTAKUGIFS
---

## Rule
Ten otakugifs.xyz endpoints return HTTP 400 (not just missing — they actively reject the request).
Map them to the nearest working alternative inside `_OTAKUGIFS` in `fun.py`.

**Broken → replacement used:**
- bonk → pat
- bully → slap
- handholding → cuddle
- highfive → wave
- kick → punch
- shoot (kill/insult) → slap
- think (thinking/thonking) → stare
- throw (yeet) → slap
- triggered → punch
- wag → smile

Working endpoints (confirmed): bite, blush, cry, cuddle, dance, happy, hug, kiss, laugh, lick, nom, pat, poke, pout, punch, shrug, slap, sleep, smile, smug, stare, thumbsup, tickle, wave

**Why:** nekos.best fails with JSON parse error ("Extra data") and waifu.pics has DNS failure from Replit/Render. otakugifs is the only reliable source; broken endpoints must use a working fallback.

**How to apply:** Any new keyword added to fun.py must be verified against the working endpoints list above. Test with `GET https://api.otakugifs.xyz/gif?reaction={endpoint}` — 200 = works, 400 = broken.
