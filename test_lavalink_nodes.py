"""
Lavalink node verifier — tests connectivity AND music search on each candidate.
Runs purely via HTTP; no Discord/wavelink needed.

Checks per node:
  1. GET /v4/info   → confirms Lavalink v4 is reachable and returns build info
  2. GET /v4/loadtracks?identifier=ytsearch:never gonna give you up
              → confirms the node can actually search and return tracks
"""

import asyncio
import aiohttp
import json
import time

# ── Candidate nodes ──────────────────────────────────────────────────────────
# Format: (label, base_url, password)
CANDIDATES = [
    # Known public community nodes (July 2026)
    ("lavalink.devamop.in",         "https://lavalink.devamop.in",         "DevamopRocks!"),
    ("lavalink.devamop.in-443",     "https://lavalink.devamop.in:443",     "DevamopRocks!"),
    ("lavalink.jirayu.net",         "http://lavalink.jirayu.net:13592",    "youshallnotpass"),
    ("lavalink.oops.wtf",           "https://lavalink.oops.wtf",           "op"),
    ("lavalink.lexnet.cx",          "https://lavalink.lexnet.cx",          "lexnetcx"),
    ("lavalink.darrennathanael.com","https://lavalink.darrennathanael.com","HeyItsLafar"),
    ("lava.link",                   "http://lava.link:80",                 "dismusic"),
    ("lavalink.clxud.dev",          "https://lavalink.clxud.dev",          "clxud"),
    ("lavalink.alfari.id",          "http://lavalink.alfari.id:2333",      "alfari"),
    ("lavalink.rainandstars.xyz",   "https://lavalink.rainandstars.xyz",   "rainandstars"),
    ("lavalink.alfaarts.cf",        "http://lavalink.alfaarts.cf:2333",    "youshallnotpass"),
    ("lavalink.roboxmedia.nl",      "https://lavalink.roboxmedia.nl",      "roboxmedia"),
    ("lavalink.cosmicnode.eu",      "https://lavalink.cosmicnode.eu",      "cosmicnode"),
    ("lavalink.technocrafter.co",   "https://lavalink.technocrafter.co",   "technocrafter"),
    ("node.lewdhutao.my.eu.org",    "http://node.lewdhutao.my.eu.org:80",  "lewdhutao"),
    ("lavalink.serenetia.com",      "https://lavalink.serenetia.com",      "BatuManaBatu"),
    ("lavalink.taneliisback.fi",    "https://lavalink.taneliisback.fi",    "youshallnotpass"),
    ("lavalink.noauthregion.xyz",   "https://lavalink.noauthregion.xyz",   "noauthregion"),
    ("lavalink.autolycus.xyz",      "https://lavalink.autolycus.xyz",      "autolycus"),
    ("lavalink.oryzen.xyz",         "https://lavalink.oryzen.xyz",         "oryzenpass"),
    ("lavalink.rudidev.xyz",        "https://lavalink.rudidev.xyz",        "rudidevxyz"),
    ("lavalink.deviant.digital",    "https://lavalink.deviant.digital",    "deviantlava"),
    ("lavalink.kaaaaaay.eu.org",    "http://lavalink.kaaaaaay.eu.org:2333","youshallnotpass"),
    ("lavalink.waifubot.gg",        "https://lavalink.waifubot.gg",        "waifubot"),
    ("lavalink.hamsterhub.xyz",     "https://lavalink.hamsterhub.xyz",     "hamsterhub"),
    ("lavalink.ponjo.club",         "https://lavalink.ponjo.club",         "ponjo"),
    ("lavalink.napratica.eu.org",   "https://lavalink.napratica.eu.org",   "youshallnotpass"),
    ("lavalink.natanbc.net",        "https://lavalink.natanbc.net",        "testpassword"),
    ("lavalink.apiraider.com",      "https://lavalink.apiraider.com",      "apiraider"),
    ("lavalink.haruteam.xyz",       "https://lavalink.haruteam.xyz",       "youshallnotpass"),
    ("lavalink.squareweb.app",      "https://lavalink.squareweb.app",      "youshallnotpass"),
    ("lavalink.rekkdal.no",         "https://lavalink.rekkdal.no",         "rekkdalpassword"),
    ("lavalink.moebot.xyz",         "https://lavalink.moebot.xyz",         "moebot"),
    ("lavalink.horizxon.tech",      "https://lavalink.horizxon.tech",      "horizxon.tech"),
    ("lavalink.freelavalink.ga",    "https://lavalink.freelavalink.ga",    "freelavalink"),
    ("lavalink.scathach.id",        "https://lavalink.scathach.id",        "cafebibit"),
    ("lavalink.ayzel.xyz",          "https://lavalink.ayzel.xyz",          "youshallnotpass"),
    ("lavalink.stardust.wtf",       "https://lavalink.stardust.wtf",       "stardustpassword"),
    ("lavalink.nikobot.xyz",        "https://lavalink.nikobot.xyz",        "nikobotpassword"),
    ("lavalink.lunardev.me",        "https://lavalink.lunardev.me",        "lunardevpassword"),
    # Extra well-known tries with youshallnotpass
    ("lavalinkv4.serenetia.com",    "https://lavalinkv4.serenetia.com",    "BatuManaBatu"),
    ("lavalink4.alfari.id",         "https://lavalink4.alfari.id",         "alfari"),
    ("lavalink.danbot.host",        "https://lavalink.danbot.host",        "danbot"),
    ("lavalink.tectone23.ml",       "https://lavalink.tectone23.ml",       "tectone23"),
    ("lavalink.mclaven.xyz",        "https://lavalink.mclaven.xyz",        "youshallnotpass"),
    ("lavalink.namibot.xyz",        "https://lavalink.namibot.xyz",        "youshallnotpass"),
    ("lavalink.pasela.xyz",         "https://lavalink.pasela.xyz",         "youshallnotpass"),
    ("lavalink.zerotwo.xyz",        "https://lavalink.zerotwo.xyz",        "youshallnotpass"),
    ("lavalink.stijnvdklis.nl",     "https://lavalink.stijnvdklis.nl",     "youshallnotpass"),
    ("lavalink.music.io",           "https://lavalink.music.io",           "youshallnotpass"),
]

SEARCH_QUERY = "scsearch:never gonna give you up"   # SoundCloud — less blocked than YT
TIMEOUT      = 10   # seconds per request

# ── Test a single node ────────────────────────────────────────────────────────

async def test_node(session: aiohttp.ClientSession, label: str, base: str, password: str) -> dict:
    result = {
        "label":    label,
        "base":     base,
        "password": password,
        "info_ok":  False,
        "info_ver": "",
        "search_ok": False,
        "tracks":   0,
        "latency_ms": -1,
        "error":    "",
    }

    headers = {"Authorization": password}
    ssl_ctx = False  # disable strict SSL verification for community nodes

    t0 = time.monotonic()

    # 1) /v4/info ──────────────────────────────────────────────────────────────
    try:
        async with session.get(
            f"{base}/v4/info",
            headers=headers,
            ssl=ssl_ctx,
            timeout=aiohttp.ClientTimeout(total=TIMEOUT),
        ) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                result["info_ok"]  = True
                ver = data.get("version", {})
                result["info_ver"] = ver.get("semver", "") if isinstance(ver, dict) else str(ver)
            elif resp.status == 401:
                result["error"] = "wrong password (401)"
                return result
            else:
                result["error"] = f"info HTTP {resp.status}"
                return result
    except asyncio.TimeoutError:
        result["error"] = "timeout on /v4/info"
        return result
    except Exception as e:
        result["error"] = f"connect error: {type(e).__name__}: {e}"
        return result

    # 2) /v4/loadtracks ────────────────────────────────────────────────────────
    try:
        async with session.get(
            f"{base}/v4/loadtracks",
            headers=headers,
            params={"identifier": SEARCH_QUERY},
            ssl=ssl_ctx,
            timeout=aiohttp.ClientTimeout(total=TIMEOUT + 5),
        ) as resp:
            elapsed = (time.monotonic() - t0) * 1000
            result["latency_ms"] = round(elapsed)
            if resp.status == 200:
                data = await resp.json(content_type=None)
                load_type = data.get("loadType", "")
                tracks    = data.get("data", [])
                if not isinstance(tracks, list):
                    tracks = []
                result["search_ok"] = load_type in ("SEARCH_RESULT", "search")
                result["tracks"]    = len(tracks)
            else:
                result["error"] = f"loadtracks HTTP {resp.status}"
    except asyncio.TimeoutError:
        result["error"] = "timeout on /v4/loadtracks"
    except Exception as e:
        result["error"] = f"loadtracks error: {e}"

    return result


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    connector = aiohttp.TCPConnector(ssl=False, limit=20)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            test_node(session, label, base, pw)
            for label, base, pw in CANDIDATES
        ]
        results = await asyncio.gather(*tasks)

    # ── Print results ─────────────────────────────────────────────────────────
    working  = [r for r in results if r["search_ok"]]
    info_only = [r for r in results if r["info_ok"] and not r["search_ok"]]
    dead     = [r for r in results if not r["info_ok"]]

    print("\n" + "=" * 72)
    print(f"  RESULTS  —  {len(CANDIDATES)} nodes tested")
    print("=" * 72)

    print(f"\n✅ FULLY WORKING  ({len(working)} nodes  — info + search OK)\n")
    for r in sorted(working, key=lambda x: x["latency_ms"]):
        print(f"  {'✅':2}  {r['label']:<40}  v{r['info_ver']:<8}  "
              f"{r['tracks']:2} tracks  {r['latency_ms']} ms")
        print(f"        URI: {r['base']}   PW: {r['password']}")

    print(f"\n⚠️  INFO OK, SEARCH FAILED  ({len(info_only)} nodes)\n")
    for r in info_only:
        print(f"  {'⚠️':2}  {r['label']:<40}  {r['error']}")

    print(f"\n❌ UNREACHABLE / DEAD  ({len(dead)} nodes)\n")
    for r in dead:
        short = (r['error'] or 'unknown')[:60]
        print(f"  {'❌':2}  {r['label']:<40}  {short}")

    # ── Env-var snippet ───────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  REPLIT ENV-VAR SNIPPET  (copy these into Secrets)")
    print("=" * 72)
    top = sorted(working, key=lambda x: x["latency_ms"])[:10]
    if top:
        uris = "|".join(r["base"]  for r in top)
        pws  = "|".join(r["password"] for r in top)
        print(f"\n  LAVALINK_URIS      = {uris}")
        print(f"  LAVALINK_PASSWORDS = {pws}")
        print()
        for i, r in enumerate(top, 1):
            print(f"  LAVALINK_URL_{i:<3}      = {r['base']}")
            print(f"  LAVALINK_PASSWORD_{i:<3}  = {r['password']}")
    else:
        print("\n  No fully working nodes found — try different passwords or nodes.")

    print("=" * 72 + "\n")

asyncio.run(main())
