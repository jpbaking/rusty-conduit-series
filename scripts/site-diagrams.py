"""Generate the website's SVG diagrams into site/img/.

Usage: python3 scripts/site-diagrams.py [out_dir]   (default: site/img)
Edit the diagrams here, rerun, and commit both this script and the SVGs.
"""
import os
import sys
from html import escape

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "img")

STYLE = """
svg{--text:#e5e9f0;--muted:#9aa5b8;--node:#172033;--line:#3a4864;--zone:#64748b;--acc:#3b82f6;--acc2:#60a5fa;--ssh:#2dd4bf;--bad:#f87171;--ok:#4ade80;--hap:#a78bfa;--onacc:#fff}
@media (prefers-color-scheme:light){svg{--text:#111827;--muted:#4b5568;--node:#f3f6fb;--line:#b8c3d4;--zone:#94a3b8;--acc:#2563eb;--acc2:#2563eb;--ssh:#0d9488;--bad:#dc2626;--ok:#16a34a;--hap:#7c3aed}}
text{font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;fill:var(--text)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.t{font-size:15px;font-weight:600}
.s{font-size:12.5px;fill:var(--muted)}
.c{font-size:13px;fill:var(--muted)}
.zl{font-size:11.5px;font-weight:700;letter-spacing:.08em;fill:var(--zone)}
.bad-t{fill:var(--bad)}.ok-t{fill:var(--ok)}
.pt{fill:var(--onacc);font-size:15px;font-weight:700}
.ps{fill:var(--onacc);opacity:.88;font-size:12.5px}
.node{fill:var(--node);stroke:var(--line);stroke-width:1.5}
.prod{fill:var(--acc)}
.hap{fill:var(--node);stroke:var(--hap);stroke-width:2}
.bad{fill:var(--node);stroke:var(--bad);stroke-width:1.8}
.ok{fill:var(--node);stroke:var(--ok);stroke-width:1.8}
.ghost{fill:none;stroke:var(--line);stroke-width:1.5;stroke-dasharray:5 5}
.zone{fill:none;stroke:var(--zone);stroke-width:1.5;stroke-dasharray:6 6}
.globe{fill:var(--node);stroke:var(--acc2);stroke-width:1.8}
.f{fill:none;stroke-width:2.2;stroke-linecap:round;stroke-dasharray:8 7;animation:flow 1.1s linear infinite}
.f-acc{stroke:var(--acc2)}.f-ssh{stroke:var(--ssh)}.f-bad{stroke:var(--bad)}.f-ok{stroke:var(--ok)}.f-hap{stroke:var(--hap)}
.f-mute{stroke:var(--zone);animation:none;stroke-dasharray:4 5}
.pipe{fill:none;stroke:var(--ssh);stroke-opacity:.2;stroke-width:24;stroke-linecap:round}
.m-acc{fill:var(--acc2)}.m-ssh{fill:var(--ssh)}.m-bad{fill:var(--bad)}.m-ok{fill:var(--ok)}.m-hap{fill:var(--hap)}.m-mute{fill:var(--zone)}
@keyframes flow{to{stroke-dashoffset:-30}}
@media (prefers-reduced-motion:reduce){.f{animation:none}}
"""

KINDS = ["acc", "ssh", "bad", "ok", "hap", "mute"]
DEFS = "<defs>" + "".join(
    f'<marker id="m-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" '
    f'markerWidth="10" markerHeight="10" orient="auto"><path d="M0,0L10,5L0,10z" class="m-{k}"/></marker>'
    for k in KINDS
) + "</defs>"


def svg(name, w, h, title, desc, parts):
    body = "\n".join(parts)
    doc = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-labelledby="title desc">\n'
        f'<title id="title">{escape(title)}</title>\n<desc id="desc">{escape(desc)}</desc>\n'
        f"<style>{STYLE}</style>\n{DEFS}\n{body}\n</svg>\n"
    )
    with open(os.path.join(OUT, name), "w") as f:
        f.write(doc)


def T(x, y, s, cls="t", anchor="middle"):
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{escape(s)}</text>'


def box(x, y, w, h, title, subs=(), kind="node", tcls=None, scls=None, rx=10):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" class="{kind}"/>']
    if kind == "prod":
        tcls = "pt " + (tcls or "")
        scls = "ps " + (scls or "")
    else:
        tcls = tcls or "t"
        scls = "s " + (scls or "")
    lines = [title] + list(subs)
    total = 17 + 17 * len(subs)
    ty = y + h / 2 - total / 2 + 13
    cx = x + w / 2
    out.append(T(cx, round(ty, 1), title, tcls.strip()))
    for i, s in enumerate(subs):
        out.append(T(cx, round(ty + 18 * (i + 1), 1), s, scls.strip()))
    return "\n".join(out)


def stack(x, y, w, h, title, subs=(), kind="node", **kw):
    back = kind if kind != "prod" else "prod"
    op = ' opacity=".45"'
    return "\n".join([
        f'<rect x="{x+10}" y="{y-10}" width="{w}" height="{h}" rx="10" class="{back}"{op}/>',
        f'<rect x="{x+5}" y="{y-5}" width="{w}" height="{h}" rx="10" class="{back}" opacity=".7"/>',
        box(x, y, w, h, title, subs, kind, **kw),
    ])


def arrow(d, kind="acc", marker=True):
    m = f' marker-end="url(#m-{kind})"' if marker else ""
    return f'<path d="{d}" class="f f-{kind}"{m}/>'


def zone(x, y, w, h, label):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" class="zone"/>\n'
            + T(x + 14, y + 22, label, "zl", "start"))


def globe(cx, cy, r=22):
    return (f'<g><circle cx="{cx}" cy="{cy}" r="{r}" class="globe"/>'
            f'<ellipse cx="{cx}" cy="{cy}" rx="{r*0.45:.1f}" ry="{r}" class="globe" fill="none"/>'
            f'<path d="M{cx-r},{cy}H{cx+r}" class="globe"/></g>')


def pipe(d):
    return f'<path d="{d}" class="pipe"/>'


def mark(cx, cy, ok=False):
    k = "ok" if ok else "bad"
    g = "✓" if ok else "✕"
    return (f'<circle cx="{cx}" cy="{cy}" r="11" class="{k}"/>'
            + T(cx, cy + 5, g, f"t {k}-t"))


# ---------------------------------------------------------------- hero
p = [
    T(20, 62, "YOUR APPS", "zl", "start"),
    T(455, 62, "ONE ENGINE · HTTP · HTTPS · SOCKS IN", "zl"),
    T(700, 62, "WHERE IT GOES", "zl", "start"),
]
for y, name in zip([90, 165, 240, 315], ["Browser", "curl & CLIs", "SDKs & agents", "Containers"]):
    p.append(box(20, y, 170, 46, name))
    p.append(arrow(f"M190,{y+23}H250", marker=False))
p.append(arrow("M250,110V338", marker=False))
for y, name, sub in [(80, "rusty-conduit", "direct"), (185, "rusty-conduit-ssh", "through SSH"),
                     (290, "rusty-conduit-switch", "by rules")]:
    p.append(arrow(f"M250,{y+30}H327"))
    p.append(box(330, y, 250, 60, name, [sub], "prod", tcls="mono"))
p += [arrow("M580,110H704"), globe(730, 110), T(762, 115, "Internet", "t", "start")]
p += [pipe("M592,215H690"), arrow("M582,215H696", "ssh"), T(640, 199, "ssh -D", "c mono"),
      box(700, 192, 100, 46, "bastion"), arrow("M800,215H826", "ssh"),
      box(830, 192, 118, 46, "private net"), T(889, 256, "names resolve there", "s")]
for cy, chip, note, kind in [(282, "direct", "→ internet", "acc"), (318, "proxy A", "→ office proxy", "acc"),
                             (354, "proxy B", "→ VPN or SSH", "acc"), (390, "block", "refused", "bad")]:
    p.append(arrow(f"M580,320C650,320 650,{cy} 716,{cy}", kind))
    p.append(box(720, cy - 14, 104, 28, chip, kind="bad" if kind == "bad" else "node", tcls="c mono", rx=14))
    p.append(T(838, cy + 4, note, "s bad-t" if kind == "bad" else "s", "start"))
p.append(T(455, 372, "first matching rule wins · hot reload", "s"))
svg("hero.svg", 960, 410, "How traffic flows through rusty-conduit",
    "Browsers, CLIs, SDKs, agents and containers connect over HTTP, HTTPS or SOCKS to one of three proxies. "
    "rusty-conduit sends traffic straight to the internet. rusty-conduit-ssh sends it through an ssh -D tunnel to a "
    "bastion and on into a private network, where names resolve. rusty-conduit-switch picks direct, an upstream "
    "proxy, or block for each connection, by the first matching rule.", p)

# ---------------------------------------------------------------- flow: direct
p = [zone(20, 30, 560, 320, "YOUR MACHINE OR CONTAINER")]
for y, name in zip([95, 170, 245], ["Browser", "curl & CLIs", "Agents & SDKs"]):
    p.append(box(50, y, 150, 48, name))
    p.append(arrow(f"M200,{y+24}C250,{y+24} 250,160 297,160"))
p.append(box(300, 110, 240, 100, "rusty-conduit", ["HTTP   127.0.0.1:3128", "SOCKS  127.0.0.1:1080"],
             "prod", tcls="mono", scls="mono"))
p.append('<rect x="300" y="214" width="240" height="106" rx="10" class="node"/>')
for i, s in enumerate(["allow and block lists", "an access log per connection", "HTTPS inspection (opt-in)"]):
    p.append(T(318, 243 + i * 27, "✓  " + s, "c", "start"))
p += [arrow("M540,140C620,140 640,115 717,115"), globe(745, 115, 24),
      T(780, 110, "example.com", "t", "start"), T(780, 130, "allowed · logged", "s", "start")]
p += [arrow("M540,185C570,185 555,255 567,255", "bad"), mark(580, 255),
      box(610, 230, 330, 52, "ads.doubleclick.net", ["blocked: 403, never connected"], "ghost")]
svg("flow-direct.svg", 960, 380, "rusty-conduit: a direct proxy",
    "Apps on your machine connect to rusty-conduit on 127.0.0.1 port 3128 for HTTP or port 1080 for SOCKS. "
    "It checks allow and block lists, logs each connection, and can inspect HTTPS when you turn it on. "
    "Allowed traffic such as example.com goes out; a blocked host such as ads.doubleclick.net gets a 403 and is never contacted.", p)

# ---------------------------------------------------------------- flow: ssh
p = [zone(20, 30, 380, 320, "YOUR LAPTOP"), zone(580, 30, 360, 320, "PRIVATE NETWORK"),
     T(490, 62, "INTERNET", "zl")]
p += [box(45, 150, 130, 70, "Your apps", ["browser · curl"]), arrow("M175,185H207"),
      box(210, 120, 170, 130, "rusty-conduit-ssh", [":3128 HTTP", ":1080 SOCKS", "runs your ssh"],
          "prod", tcls="mono")]
p += [pipe("M392,185H598"), arrow("M382,185H606", "ssh"),
      T(495, 165, "ssh -D tunnel", "c mono"), T(495, 216, "encrypted · auto-reconnect", "s")]
p.append(box(610, 150, 110, 70, "bastion", ["sshd"]))
for cy, name in [(92, "nas.home.internal"), (172, "grafana.home.internal"), (252, "db.internal:5432")]:
    p.append(arrow(f"M720,185C738,185 738,{cy} 749,{cy}", "ssh"))
    p.append(box(752, cy - 22, 182, 44, name, tcls="c mono"))
p += [T(210, 320, "uses ~/.ssh/config, ssh-agent, ProxyJump", "s"),
      T(760, 320, "DNS for proxied hosts resolves here", "s")]
svg("flow-ssh.svg", 960, 380, "rusty-conduit-ssh: a proxy through SSH",
    "On your laptop, apps connect to rusty-conduit-ssh on port 3128 for HTTP or 1080 for SOCKS. It runs your own ssh "
    "and opens an encrypted ssh -D tunnel that reconnects on its own to a bastion inside a private network. "
    "From the bastion, traffic reaches hosts such as nas.home.internal, grafana.home.internal and db.internal, "
    "and their names resolve inside the private network.", p)

# ---------------------------------------------------------------- flow: switch
p = [box(20, 170, 130, 60, "Your apps"), arrow("M150,200H197"),
     box(200, 150, 200, 100, "rusty-conduit-switch", [":3128 · :1080"], "prod", tcls="mono", scls="mono"),
     box(200, 30, 200, 56, "config.toml", ["--watch-config: live reload"], tcls="t mono"),
     arrow("M300,86V147", "mute"),
     T(565, 40, "RULES · FIRST MATCH WINS", "zl")]
p += [arrow("M400,200H425", marker=False), arrow("M425,82V298", marker=False)]
rows = [(82, "*.office.example", "acc"), (136, "192.168.1.0/24", "acc"), (190, "*.home.internal", "acc"),
        (244, "*.doubleclick.net", "bad"), (298, "default", "acc")]
for i, (cy, pat, kind) in enumerate(rows):
    p.append(arrow(f"M425,{cy}H447", kind))
    p.append(f'<rect x="450" y="{cy-22}" width="230" height="44" rx="10" class="node"/>')
    p.append(T(466, cy + 4, str(i + 1), "s", "start"))
    p.append(T(490, cy + 4, pat, "c mono", "start"))
    p.append(arrow(f"M680,{cy}H737", kind))
p += [box(740, 60, 200, 44, "office proxy", ["http upstream"]),
      box(740, 114, 200, 98, "homelab", ["socks5 upstream", "e.g. rusty-conduit-ssh"]),
      box(740, 222, 200, 44, "block", ["refused"], "bad"),
      box(740, 276, 200, 44, "direct", ["straight out"])]
p += [T(480, 356, 'Any target can be a failover chain, like ["vpn", "ssh", "direct"].', "s"),
      T(480, 378, "test-route shows which rule and upstream a host would use.", "s")]
svg("flow-switch.svg", 960, 400, "rusty-conduit-switch: routing by rules",
    "Apps connect to rusty-conduit-switch on port 3128 or 1080. It reads config.toml and reloads it live. "
    "Rules run top to bottom and the first match wins: *.office.example goes to the office HTTP proxy; "
    "192.168.1.0/24 and *.home.internal go to a homelab SOCKS5 upstream such as rusty-conduit-ssh; "
    "*.doubleclick.net is blocked; everything else goes direct.", p)

# ---------------------------------------------------------------- use case: failover
p = [box(20, 105, 150, 70, "switch", ["rule target"], "prod", tcls="mono"),
     T(405, 28, 'target = ["vpn", "ssh", "direct"]', "c mono"),
     arrow("M170,125C250,125 250,75 327,75", "bad"),
     arrow("M170,140C250,140 250,150 327,150", "ok"),
     arrow("M170,155C250,155 250,225 327,225", "mute"),
     box(330, 50, 150, 50, "1  vpn", ["✕ connect failed"], "bad"),
     box(330, 125, 150, 50, "2  ssh", ["✓ serves it"], "ok"),
     box(330, 200, 150, 50, "3  direct", ["not tried"], "ghost"),
     arrow("M480,150H549", "ok"), globe(577, 150), T(577, 192, "Internet", "s"),
     T(320, 285, "Next profile only if the connect or handshake fails, never after bytes flow", "s")]
svg("uc-failover.svg", 640, 300, "Failover chain",
    "A switch rule targets the chain vpn, ssh, direct. The vpn connect fails, so the ssh profile is tried and serves "
    "the connection; direct is not tried. The next profile is used only when the connect or handshake fails.", p)

# ---------------------------------------------------------------- use case: mitm
p = [T(320, 30, "OFF BY DEFAULT · NO CA IS EVER CREATED FOR YOU", "zl"),
     box(20, 100, 120, 70, "Client", ["trusts ca.pem"]),
     arrow("M140,135H247"), T(194, 125, "TLS", "c"), T(194, 155, "leaf cert", "s"), T(194, 171, "from your CA", "s"),
     box(250, 90, 140, 90, "rusty-conduit", ["--mitm-ca-cert"], "prod", tcls="mono", scls="mono"),
     arrow("M390,135H497"), T(444, 125, "TLS", "c"), T(444, 155, "upstream cert", "s"), T(444, 171, "verified", "s"),
     box(500, 100, 120, 70, "example.com", ["real cert"]),
     arrow("M320,180V203", "mute"),
     box(150, 205, 340, 56, "access log", ["method · full URL · status · mitm=true"]),
     T(320, 290, "With switch, URL rules can now route HTTPS requests too", "s")]
svg("uc-mitm.svg", 640, 300, "HTTPS inspection with your own CA",
    "A client that trusts your ca.pem connects over TLS to the proxy, which presents a leaf certificate minted from "
    "your CA, then opens its own TLS connection to example.com and verifies the real certificate. The access log "
    "records each request's method, full URL and status. Inspection is off by default and no CA is created for you.", p)

# ---------------------------------------------------------------- use case: reverse
p = [zone(20, 40, 230, 250, "BUILD-BOX · NO EGRESS"), zone(390, 40, 230, 250, "YOUR LAPTOP"),
     box(45, 75, 180, 50, "app", ["proxy env → :8888"]),
     arrow("M135,125V182"),
     box(45, 185, 180, 56, "127.0.0.1:8888", ["opened by ssh -R"], tcls="t mono"),
     pipe("M237,213H403"), arrow("M226,213H412", "ssh"),
     T(320, 197, "ssh -R", "c mono"), T(320, 240, "back to you", "s"),
     box(415, 185, 180, 56, "rusty-conduit-ssh", ["--reverse-block"], "prod", tcls="mono", scls="mono"),
     arrow("M505,185V132"), globe(505, 105, 24), T(540, 110, "Internet", "t", "start"),
     T(320, 312, "Keep --reverse-bind 127.0.0.1 and set GatewayPorts clientspecified on the server", "s")]
svg("uc-reverse.svg", 640, 320, "Give a remote machine internet through yours",
    "On a build box with no egress, an app uses a proxy on 127.0.0.1:8888, which ssh -R opens and carries back to "
    "rusty-conduit-ssh on your laptop. Its traffic leaves to the internet from your machine, with private ranges "
    "blocked by --reverse-block.", p)

# ---------------------------------------------------------------- use case: sandbox
p = [zone(20, 40, 280, 220, "INTERNAL NETWORK · NO GATEWAY"),
     box(40, 110, 140, 60, "agent / CI job"),
     arrow("M180,140H227"),
     box(230, 100, 150, 80, "rusty-conduit", ["--allow list"], "prod", tcls="mono", scls="mono"),
     arrow("M380,130C425,130 425,72 467,72", "ok"), box(470, 50, 150, 44, "github.com", kind="ok"),
     arrow("M380,140H467", "ok"), box(470, 118, 150, 44, "pypi.org", kind="ok"),
     arrow("M380,150C425,150 425,211 467,211", "bad"), box(470, 186, 150, 50, "example.com", ["403 · logged"], "bad"),
     arrow("M110,170V212", "bad"), mark(110, 226), T(130, 231, "no route out", "c bad-t", "start"),
     T(320, 288, "Every attempt is logged, allowed or not", "s")]
svg("uc-sandbox.svg", 640, 300, "An egress sandbox for agents and CI",
    "An agent or CI job sits on an internal network with no gateway, so it has no route out except a rusty-conduit "
    "proxy with an allow list. github.com and pypi.org are allowed; example.com gets a 403. Every attempt is logged.", p)

# ---------------------------------------------------------------- use case: scale-out
p = [box(20, 110, 100, 56, "Clients"), arrow("M120,138H157"),
     box(160, 95, 150, 86, "HAProxy", [":3128 · :1080", "leastconn"], "hap", scls="mono"),
     box(20, 195, 100, 40, ":8404 stats", tcls="c mono")]
for cy, name, kind in [(60, "proxy-1", "acc"), (115, "proxy-2", "acc"), (170, "proxy-3", "acc"), (225, "proxy-N", "mute")]:
    p.append(arrow(f"M310,138C360,138 360,{cy} 397,{cy}", kind))
    p.append(box(400, cy - 20, 120, 40, name, kind="ghost" if kind == "mute" else "node", tcls="t mono"))
p += [T(460, 262, "--scale proxy=N", "s mono"),
      box(160, 228, 150, 48, "Docker DNS", ["127.0.0.11"], "ghost", scls="mono"),
      arrow("M235,228V184", "mute"),
      T(235, 294, "one A record per running replica", "s")]
svg("uc-scaleout.svg", 640, 300, "Scale out with HAProxy and Docker DNS",
    "Clients connect to HAProxy on ports 3128 and 1080, which balances connections by leastconn across proxy "
    "replicas. HAProxy finds replicas through Docker's DNS at 127.0.0.11, which returns one record per running "
    "replica, so docker compose --scale adds or removes them. Stats are on port 8404.", p)

# ---------------------------------------------------------------- use case: homelab stack
p = [box(20, 150, 110, 56, "Clients"), arrow("M130,178H162"),
     box(165, 130, 130, 96, "HAProxy", [":3128 · :1080"], "hap", scls="mono"),
     box(165, 245, 130, 36, ":8404 stats", tcls="c mono"),
     arrow("M295,178H332"),
     stack(335, 138, 140, 80, "switch ×N", ["rules · reload"], "prod"),
     T(595, 28, "RULES", "zl"),
     T(760, 190, "HAPROXY FRONTENDS", "zl")]
for cy, chip, kind in [(60, "direct", "acc"), (130, "block", "bad"), (220, "egress", "acc"), (300, "tunnel", "ssh")]:
    p.append(arrow(f"M485,178C505,178 505,{cy} 527,{cy}", kind))
    p.append(box(530, cy - 20, 130, 40, chip, kind="bad" if kind == "bad" else "node", tcls="c mono"))
p += [arrow("M660,60H719"), globe(745, 60), T(775, 65, "internet", "c", "start"),
      arrow("M595,240V277", "mute"), T(605, 263, "failover", "s", "start"),
      arrow("M660,220H697"), box(700, 200, 120, 40, ":13128", kind="hap", tcls="t mono"),
      arrow("M660,300H697", "ssh"), box(700, 280, 120, 40, ":11080", kind="hap", tcls="t mono"),
      arrow("M820,220H857"), stack(860, 196, 110, 48, "egress ×N"),
      arrow("M820,300H857", "ssh"), stack(860, 276, 110, 48, "tunnel ×N"),
      arrow("M970,220H1026"), globe(1052, 220), T(1052, 260, "internet", "s"),
      pipe("M980,300H1000"), arrow("M970,300H1007", "ssh"),
      box(1010, 280, 80, 40, "lab-lan"), T(990, 340, "ssh", "c mono")]
svg("uc-homelab.svg", 1100, 360, "The homelab stack",
    "Clients connect to one HAProxy on ports 3128 and 1080, which balances across scaled rusty-conduit-switch "
    "replicas. Their rules send each connection direct to the internet, to block, to an egress pool through HAProxy "
    "port 13128, or to an SSH tunnel pool through HAProxy port 11080 that reaches the lab LAN over SSH. "
    "The egress rule fails over to the tunnel pool.", p)

# ---------------------------------------------------------------- use case: jump hosts
p = [T(320, 30, "rusty-conduit-ssh -J jump1,jump2 deploy@inner", "c mono"),
     box(20, 95, 170, 70, "rusty-conduit-ssh", [":3128 · :1080"], "prod", tcls="mono", scls="mono"),
     pipe("M202,130H500"), arrow("M190,130H232", "ssh"), box(235, 108, 90, 44, "jump1"),
     arrow("M325,130H367", "ssh"), box(370, 108, 90, 44, "jump2"),
     arrow("M460,130H497", "ssh"), box(500, 108, 120, 44, "inner"),
     T(300, 186, "ssh hops, each one through the last", "s"),
     box(20, 215, 260, 52, "127.0.0.1:5432", ["-L forward after --"], tcls="t mono", scls="mono"),
     arrow("M280,241H497", "ssh"), T(390, 232, "via the same ssh chain", "s"), box(500, 219, 120, 44, "db.internal", tcls="c mono"),
     T(320, 292, "Or ProxyJump in ~/.ssh/config; the GUI builds chains hop by hop", "s")]
svg("uc-jump.svg", 640, 300, "Jump hosts and port forwards",
    "rusty-conduit-ssh connects through jump1 and jump2 to an inner host, each hop through the last, and serves its "
    "proxy ports from there. An extra -L forward maps 127.0.0.1:5432 on your machine to db.internal.", p)

print("ok")
