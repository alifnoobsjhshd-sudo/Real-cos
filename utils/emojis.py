"""
Centralized emoji configuration for Zyrox X.

Only emojis uploaded through /upload emojis and saved in
db/emoji_store.db are returned.  This is intentional: custom emoji IDs from
another server must never leak into messages, embeds, selects, or buttons.
"""

from __future__ import annotations
import os
import sqlite3

_DB_STORE_PATH = "db/emoji_store.db"

_FALLBACK: dict[str, str] = {
    # ── Core status ────────────────────────────────────────────────────────────
    "ztick":                "<:ztick:1448951767990796298>",
    "tick":                 "<:tick:1327829594954530896>",
    "Ztick":                "<:Ztick:1222750301233090600>",
    "olympus_tick":         "<:olympus_tick:1227866641027698792>",
    "zcross":               "<:zcross:1448951756372443296>",
    "CrossIcon":            "<:CrossIcon:1327829124894429235>",
    "ml_cross":             "<:ml_cross:1204106928675102770>",
    "Denied":               "<:Denied:1294218790082711553>",
    "zwarning":             "<:zwarning:1448949627712966717>",
    "warning":              "<:warning:1448951779353038949>",
    "icons_warning":        "<:icons_warning:1448949538944716922>",
    "error":                "<:error:1397218903389044776>",
    "Enable":               "<:Enable:1448949527846322296>",
    "Disable":              "<:Disable:1448949515787964417>",
    "New":                  "<:New:1448949337395695616>",
    "info":                 "<:info:1374723970376405113>",
    # ── Navigation ─────────────────────────────────────────────────────────────
    "zArrow":               "<:zArrow:1448951532837015643>",
    "ArrowRed":             "<a:ArrowRed:1448951520077811806>",
    "zback":                "<:zback:1448949305229443124>",
    "forward":              "<:forward:1329361532999569439>",
    "next":                 "<:next:1448949316109733920>",
    "icons_next":           "<:icons_next:1327829470027055184>",
    "max__A":               "<a:max__A:1295014945641201685>",
    "zplus":                "<:zplus:1448951790463615038>",
    "icons_plus":           "<:icons_plus:1328966531140288524>",
    # ── Loading ────────────────────────────────────────────────────────────────
    "loading":              "<a:loading:1448951579603505154>",
    "loadingred":           "<a:loadingred:1448966488865247232>",
    "iconLoad":             "<:iconLoad:1327829324518391824>",
    # ── Interface ──────────────────────────────────────────────────────────────
    "channel":              "<:channel:1448951734096625727>",
    "icons_channel":        "<:icons_channel:1327829380935843941>",
    "icons_home":           "<:icons_home:1337295807430393958>",
    "icon_browser":         "<:icon_browser:1448951659521773598>",
    "lock":                 "<:lock:1448949549455511685>",
    "unlock":               "<:unlock:1448949560457171070>",
    "delete":               "<:delete:1448966413242073088>",
    # ── People ─────────────────────────────────────────────────────────────────
    "zHuman":               "<:zHuman:1448951509235531869>",
    "zpeople":              "<:zpeople:1448951456861519962>",
    "king":                 "<:king:1448951721479901334>",
    "manager":              "<:manager:1394348646803439709>",
    "headmod":              "<:headmod:1274781954482376857>",
    "staff":                "<a:staff:1448949765931925504>",
    "handshake":            "<:handshake:1448949571811282984>",
    # ── Symbols ────────────────────────────────────────────────────────────────
    "zyrox_mention":        "<:zyrox_mention:1448949481776222218>",
    "mention":              "<a:mention:1448966424495390801>",
    "starr":                "<:starr:1448951307707748395>",
    "star":                 "<a:star:1251876754516349059>",
    "Star":                 "<a:Star:1273588820373147803>",
    "heart3":               "<:heart3:1448966390353756200>",
    "zdil":                 "<:zdil:1448949605676093540>",
    "RedHeart":             "<a:RedHeart:1272229548280512547>",
    "heart_em":             "<:heart_em:1274781856406962250>",
    "red_button":           "<:red_button:1401444612874305671>",
    "reddot":               "<a:reddot:1398280090198081578>",
    # ── Actions ────────────────────────────────────────────────────────────────
    "zban":                 "<:zban:1448951424665784373>",
    "zpin":                 "<:zpin:1448949810462855249>",
    "red_pin":              "<:red_pin:1448949326846889994>",
    "zsowrd":               "<:zsowrd:1448951362238021682>",
    "zmsg":                 "<:zmsg:1448964399166394483>",
    "zmodule":              "<:zmodule:1448951340716785744>",
    "zsettings":            "<:zsettings:1448951745706459206>",
    "zwrench":              "<:zwrench:1448951382597177495>",
    "zcast":                "<:zcast:1448951414301655175>",
    "zSafe":                "<:zSafe:1448951403434479626>",
    "zCloud":               "<:zCloud:1448951498213032036>",
    "zrocket":              "<:zrocket:1448951445989888010>",
    "zbot":                 "<:zbot:1448951393216888905>",
    "zwifi":                "<:zwifi:1448951466931912715>",
    # ── Time ───────────────────────────────────────────────────────────────────
    "zyrox_time":           "<:zyrox_time:1448949493012889610>",
    "ztimer":               "<:ztimer:1448949799528173621>",
    "timer":                "<a:timer:1329404677820911697>",
    "uptime":               "<:uptime:1398280366501920829>",
    # ── Tech / Zyrox brand ─────────────────────────────────────────────────────
    "zyrox_global":         "<:zyrox_global:1448949370539217026>",
    "zyroxsys":             "<:zyroxsys:1448949469650620426>",
    "zyrox_system":         "<:zyrox_system:1448949359159939143>",
    "zyroxhammer":          "<:zyroxhammer:1448949447617806458>",
    "zyroxconnection":      "<:zyroxconnection:1448949425828528230>",
    "zyroxlinks":           "<:zyroxlinks:1448949436939239495>",
    "zyrox_search":         "<:zyrox_search:1448949381436014662>",
    "zyroxthunder":         "<:zyroxthunder:1448949415200034907>",
    "codebase":             "<:codebase:1448951697853386826>",
    "coded":                "<:coded:1448966435622752389>",
    "zai":                  "<:zai:1448949821611446302>",
    # ── Features ───────────────────────────────────────────────────────────────
    "boost":                "<:boost:1448966463586041906>",
    "boosts":               "<a:boosts:1448949652547436654>",
    "nitroboost":           "<a:nitroboost:1448949639540899921>",
    "premium":              "<a:premium:1204110058124873889>",
    "TADAA":                "<a:TADAA:1448966368044126249>",
    "ztada":                "<:ztada:1448951329664925717>",
    "games":                "<:games:1448951285498777641>",
    "zticket":              "<:zticket:1448951318713470987>",
    "zcounting":            "<:zcounting:1448949348103749713>",
    "zlevelup":             "<:zlevelup:1448964376504696943>",
    "zseed":                "<:zseed:1448951477640101929>",
    "j2c_wait":             "",  # Generated via generate_emojis.py → uploaded via /upload
    # ── Branch 4 — semantic extras ─────────────────────────────────────────────
    "zpoll":                "",   # bar chart / poll stats   → branch4
    "zimage":               "",   # picture frame            → branch4
    "zbroom":               "",   # broom / clear            → branch4
    "zmood":                "",   # smiley face / mood       → branch4
    "zmask":                "",   # theater mask / roleplay  → branch4
    "zbrain":               "",   # brain / trivia           → branch4
    "zflower":              "",   # flower / memory          → branch4
    "zrefresh":             "",   # circular refresh arrows  → branch4
    "zcoffee":              "",   # coffee cup / Java        → branch4
    "zpickaxe":             "",   # pickaxe / Minecraft      → branch4
    "zplug":                "",   # power plug / proxy       → branch4
    "zclipboard":           "",   # clipboard / placeholders → branch4
    "zvote":                "",   # ballot box / voting      → branch4
    "zbirthday":            "",   # birthday cake            → branch4
    "zenvelope":            "",   # mail envelope            → branch4
    "zvoice":               "",   # speaker / voice          → branch4
    "zbook":                "",   # open book / explanation  → branch4
    "znum1":                "",   # ① poll option 1          → branch4
    "znum2":                "",   # ② poll option 2          → branch4
    "znum3":                "",   # ③ poll option 3          → branch4
    "znum4":                "",   # ④ poll option 4          → branch4
    "znum5":                "",   # ⑤ poll option 5          → branch4
    "znum6":                "",   # ⑥ poll option 6          → branch4
    "znum7":                "",   # ⑦ poll option 7          → branch4
    "znum8":                "",   # ⑧ poll option 8          → branch4
    "znum9":                "",   # ⑨ poll option 9          → branch4
    "znum10":               "",   # ⑩ poll option 10         → branch4
    "zcircle":              "<:zcircle:1448964410155470848>",
    "zcircle2":             "<:zcircle:1448951351601270814>",
    "zmc":                  "<:zmc:1448964387426537474>",
    # ── Music ──────────────────────────────────────────────────────────────────
    "music":                "<a:music:1448966355935301643>",
    "zmusic":               "<:zmusic:1448951372707008533>",
    "icons_music":          "<:icons_music:1327829459729911900>",
    "zmusicpause":          "<:zmusicpause:1448951801931108413>",
    "zplay":                "<:zplay:1448949294412337222>",
    "zpause":               "<:zpause:1448949283423522928>",
    "icons_pause":          "<:icons_pause:1327829480835780609>",
    "musicstop_icons":      "<:musicstop_icons:1327829536053923934>",
    "rewind1":              "<:rewind1:1329360839874056225>",
    "skip":                 "<:skip:1329359900563996754>",
    "shuffle":              "<:shuffle:1329360518367936564>",
    "zmute":                "<:zmute:1448951435478700072>",
    "zunmute":              "<:zunmute:1448951487970414694>",
    "SoundCloud":           "<:SoundCloud:1307002774738829413>",
    "youtube":              "<:youtube:1329365996959567893>",
    "YouTube":              "<:YouTube:1344680847315570841>",
    "jiosaavn":             "<:jiosaavn:1306976886047375430>",
    # Generated locally — fill IDs after /upload emojis branch:music
    "zloop":                "",   # loop/repeat symbol  → generated by generate_emojis / create locally
    "zautoplay":            "",   # autoplay symbol     → generated locally
    "zreplay":              "",   # circular replay arrow (restart current track) → generated locally
    # ── Presence ───────────────────────────────────────────────────────────────
    "online":               "<a:online:1448951591305744427>",
    "offline":              "<:offline:1448951625506099261>",
    "idle":                 "<:idle:1448951603028693042>",
    "dnd":                  "<:dnd:1448951614172954664>",
    "mobile":               "<a:mobile:1448951648490885132>",
    "pc":                   "<:pc:1448951637266665542>",
    # ── Extra ──────────────────────────────────────────────────────────────────
    "RedRulesBook":         "<a:RedRulesBook:1448966523258404955>",
    "emote":                "<a:emote:1448966401887961149>",
    "mingle":               "<a:mingle:1367773396745846895>",
    "happy_panda":          "<:happy_panda:1384576519904559206>",
    "Cute_Cute_Cute":       "<:Cute_Cute_Cute:1384578375221248010>",
    "Heeriye":              "<:Heeriye:1274769360560328846>",
    "racecar64":            "<a:racecar64:1448966449535127623>",
    "blobpart":             "<a:blobpart:1435923345748004969>",
    "sg_rd":                "<a:sg_rd:1273974278433280122>",
    "GIFD":                 "<a:GIFD:1275850452323401789>",
    "GIFN":                 "<a:GIFN:1275850451212042391>",
    # ── Discord badges ─────────────────────────────────────────────────────────
    "Active_Developer":     "<a:Active_Developer:1448949755181793280>",
    "BugHunterLevel1":      "<:BugHunterLevel1:1448949674898620518>",
    "BugHunterLvl2":        "<:BugHunterLvl2:1122549925237375086>",
    "CertifiedDiscordModerator": "<:CertifiedDiscordModerator:1448949742792085516>",
    "EarlySupporter":       "<:EarlySupporter:1448949719752773703>",
    "EarlyVerifiedBotDeveloper": "<a:EarlyVerifiedBotDeveloper:1448949731777839184>",
    "HypesquadEvents":      "<:HypesquadEvents:1448949663821598812>",
    "Hypesquad_Brilliance": "<:Hypesquad_Brilliance:1448949708381749370>",
    "a_Hypesquad_Balance":  "<a:a_Hypesquad_Balance:1448949777067806720>",
    "a_Hypesquad_Bravery":  "<a:a_Hypesquad_Bravery:1448949697577353307>",
    "PartneredServerOwner": "<:PartneredServerOwner:1122549945532297246>",
    "BlackCrown":           "<a:BlackCrown:1448949787842973697>",
    "37496alert":           "<a:37496alert:1273959128490049556>",
    "3d4":                  "<a:3d4:1435923094899523698>",
}

def _load_store() -> dict:
    """Read all uploaded emoji entries from the SQLite DB (synchronous)."""
    try:
        if not os.path.exists(_DB_STORE_PATH):
            return {}
        conn = sqlite3.connect(_DB_STORE_PATH)
        try:
            cur = conn.execute("SELECT name, emoji_str FROM emoji_store")
            return {row[0]: row[1] for row in cur.fetchall()}
        finally:
            conn.close()
    except Exception:
        return {}

_store: dict[str, str] = _load_store()

def reload_store() -> None:
    """Call this to hot-reload the emoji store after /upload emojis completes."""
    global _store
    _store = _load_store()

def get_store() -> dict:
    """Return a snapshot of the current in-memory emoji store."""
    return dict(_store)

def e(name: str) -> str:
    """
    Return the emoji string for *name*.
    Returns an empty string when the emoji has not been uploaded to the
    current bot emoji store.
    """
    return _store.get(name, "")

# ── Convenience aliases (used heavily across the codebase) ────────────────────
TICK        = lambda: e("ztick")
CROSS       = lambda: e("zcross")
WARNING     = lambda: e("zwarning")
ARROW       = lambda: e("ArrowRed")
ZARROW      = lambda: e("zArrow")
NEW         = lambda: e("New")
LOADING     = lambda: e("loadingred")

# ── Branch definitions for /upload emojis ─────────────────────────────────────
# Each branch has ≤45 emojis (Discord limit without boosts is 50 per server).
BRANCHES: dict[str, list[str]] = {
    "core": [
        "ztick", "tick", "Ztick", "olympus_tick",
        "zcross", "CrossIcon", "ml_cross", "Denied",
        "zwarning", "warning", "icons_warning", "error",
        "Enable", "Disable", "New", "info",
        "zArrow", "ArrowRed", "zback", "next", "icons_next", "max__A",
        "zplus", "icons_plus",
        "loading", "loadingred", "iconLoad",
        "channel", "icons_channel", "icons_home", "icon_browser",
        "lock", "unlock", "delete",
        "zHuman", "zpeople", "king", "manager", "headmod",
        "handshake", "zyrox_mention", "mention",
        "starr", "red_button", "reddot",
    ],
    "features": [
        "zban", "zpin", "red_pin", "zsowrd", "zmsg",
        "zmodule", "zsettings", "zwrench", "zcast", "zSafe",
        "zCloud", "zrocket", "zbot", "zwifi",
        "zyrox_time", "ztimer", "timer", "uptime",
        "zyrox_global", "zyroxsys", "zyrox_system", "zyroxhammer",
        "zyroxconnection", "zyroxlinks", "zyrox_search", "zyroxthunder",
        "codebase", "coded", "zai",
        "boost", "boosts", "nitroboost", "TADAA", "ztada",
        "games", "zticket", "zcounting", "zlevelup", "zseed",
        "zcircle", "zcircle2", "zmc", "staff", "zdil", "RedHeart",
        "j2c_wait",
    ],
    "music": [
        "music", "zmusic", "icons_music", "zmusicpause",
        "zplay", "zpause", "icons_pause", "musicstop_icons",
        "rewind1", "skip", "forward", "shuffle",
        "zmute", "zunmute",
        "zloop", "zautoplay", "zreplay",
        "SoundCloud", "youtube", "YouTube", "jiosaavn",
        "online", "offline", "idle", "dnd", "mobile", "pc",
        "RedRulesBook", "emote", "mingle", "happy_panda",
        "Cute_Cute_Cute", "Heeriye", "racecar64", "blobpart",
        "sg_rd", "GIFD", "GIFN",
        "heart3", "heart_em", "star", "Star",
        "zyrox_global", "zyrox_mention", "zplus",
        "zwarning", "zCloud",
    ],
    "badges": [
        "Active_Developer", "BugHunterLevel1", "BugHunterLvl2",
        "CertifiedDiscordModerator", "EarlySupporter",
        "EarlyVerifiedBotDeveloper", "HypesquadEvents",
        "Hypesquad_Brilliance", "a_Hypesquad_Balance", "a_Hypesquad_Bravery",
        "PartneredServerOwner", "BlackCrown", "37496alert", "3d4",
        "premium", "nitroboost", "king",
    ],
    # Branch 4 — new semantic emojis (all generated locally via generate_emojis.py)
    "branch4": [
        "zpoll", "zimage", "zbroom", "zmood", "zmask", "zbrain", "zflower",
        "zrefresh", "zcoffee", "zpickaxe", "zplug", "zclipboard", "zvote",
        "zbirthday", "zenvelope", "zvoice", "zbook",
        "znum1", "znum2", "znum3", "znum4", "znum5",
        "znum6", "znum7", "znum8", "znum9", "znum10",
    ],
}
