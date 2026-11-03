#!/usr/bin/env python3
"""Static site generator for Hungryforest 30 (public, search-friendly copy of the blog).
Usage: gen.py OUT_DIR BASE_URL
Reads data/{site,cats,posts,tools}.json and img/ from /home/claude/blog/img.
"""
import json, os, re, sys, shutil, html, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
BASE = sys.argv[2].rstrip('/')
IMG_SRC = os.environ.get('IMG_SRC') or ('/home/claude/blog/img' if os.path.isdir('/home/claude/blog/img') else os.path.join(OUT, '_img_keep'))

site = json.load(open(f'{HERE}/data/site.json'))
cats_list = json.load(open(f'{HERE}/data/cats.json'))
posts = json.load(open(f'{HERE}/data/posts.json'))
tools = json.load(open(f'{HERE}/data/tools.json'))
authors = json.load(open(f'{HERE}/data/authors.json')) if os.path.isfile(f'{HERE}/data/authors.json') else []
authors.sort(key=lambda a: a.get('order') or 0)
css = open(f'{HERE}/base.css').read()
forest = open(f'{HERE}/forest.js').read()

posts = [p for p in posts if p.get('title')]
posts.sort(key=lambda p: p.get('publishedAt') or 0, reverse=True)
NAME = site.get('name') or 'Hungryforest 30'

CATS = {c['key']: dict(c, children=[]) for c in cats_list}
TOP = []
for c in cats_list:
    if c['parent'] and c['parent'] in CATS: CATS[c['parent']]['children'].append(c['key'])
    else: TOP.append(c['key'])
tones = {}
for i, k in enumerate(TOP):
    tones[k] = f'c-t{i % 5 + 1}'
    for ch in CATS[k]['children']: tones[ch] = tones[k]
def keys_under(k): return [k] + CATS[k]['children'] if k in CATS else []
AUTO_ALSO = {'peds': ['student'], 'rehab': ['student']}
FEAT_CAT = 'student'
def also_of(p):
    a = p['also'] if isinstance(p.get('also'), list) else AUTO_ALSO.get(p['cat'], [])
    return [k for k in a if isinstance(k, str) and k != p['cat']]
def in_cats(p, keys): return p['cat'] in keys or any(k in keys for k in also_of(p))
def cats_of(p): return [p['cat']] + also_of(p)
def cat(p): return CATS.get(p['cat'], {'key': '', 'name': '未分類', 'desc': '', 'parent': '', 'children': []})

esc = lambda s: html.escape(str(s or ''), quote=True)

def fmt(ms):
    if not ms: return ''
    d = datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone(datetime.timedelta(hours=8)))
    return d.strftime('%Y.%m.%d')
def iso(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone(datetime.timedelta(hours=8))).isoformat()

def plain(md):
    s = re.sub(r'!v?\[[^\]]*\]\([^)]*\)', '', md or '')
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)
    s = re.sub(r'[#>*_`-]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()
INTRO = re.compile(r'^\s*嗨囉\S*\s*我們是\s*Hungry\s*forest\S*\s*(?:(?:今天|這次|這是)[^。！!]*?(?:分享的是|分享|文章\S*))?\s*')
def excerpt(p, n=110):
    if p.get('excerpt'): return p['excerpt']
    t = INTRO.sub('', plain(p.get('body')), count=1) or plain(p.get('body'))
    return t[:n] + '…' if len(t) > n else t
def read_min(p): return max(1, round(len(plain(p.get('body'))) / 450))

def src(ref, pre):
    if not ref: return ''
    if ref.startswith('f:img/'): return pre + ref[2:]
    return ''

def vid_src(ref, pre):
    # backend video asset:<id> -> vid/<id>.mp4 (file committed in the repo's vid/ folder)
    if ref.startswith('asset:'): f = ref[6:] + '.mp4'
    elif ref.startswith('f:vid/'): f = ref[6:]
    else: return ''
    return pre + 'vid/' + f if os.path.isfile(os.path.join(OUT, 'vid', f)) else ''
def yt_id(u):
    m = re.search(r'(?:youtube\.com/(?:watch\?(?:[^#]*&)?v=|shorts/|embed/|live/)|youtu\.be/)([A-Za-z0-9_-]{6,15})', u)
    return m.group(1) if m else ''
def video_html(ref, cap, pre):
    fc = f'<figcaption>{esc(cap)}</figcaption>' if cap.strip() else ''
    u = vid_src(ref, pre)
    if u: return f'<figure><video controls playsinline preload="metadata" src="{u}"></video>{fc}</figure>'
    y = yt_id(ref) if ref.startswith('https://') else ''
    if y: return f'<figure><div class="yt"><iframe src="https://www.youtube-nocookie.com/embed/{y}" title="{esc(cap or "YouTube 影片")}" allow="accelerometer; encrypted-media; gyroscope; picture-in-picture" allowfullscreen loading="lazy"></iframe></div>{fc}</figure>'
    if ref.startswith('https://'): return f'<p><a href="{esc(ref)}" target="_blank" rel="noopener">{esc(cap or "觀看影片")}</a></p>'
    return ''

# ---------- markdown (mirror of the blog's renderer) ----------
def inline(s, pre):
    def img(m):
        r = m.group(2); u = src(r, pre)
        return f'<img src="{u}" alt="{m.group(1)}" loading="lazy">' if u else ''
    s = re.sub(r'!\[([^\]]*)\]\((f:img/[a-z0-9]+\.jpg|asset:[^)]+)\)', img, s)
    s = re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(^|[^*])\*([^*\n]+)\*', r'\1<em>\2</em>', s)
    return s
def md(text, pre):
    out, para, quote, lst = [], [], [], None
    def fp():
        nonlocal para
        if para: out.append('<p>' + '<br>'.join(inline(esc(l), pre) for l in para) + '</p>'); para = []
    def fq():
        nonlocal quote
        if quote: out.append('<blockquote>' + '<br>'.join(inline(esc(l), pre) for l in quote) + '</blockquote>'); quote = []
    def fl():
        nonlocal lst
        if lst: out.append(f'<{lst[0]}>' + ''.join('<li>' + inline(esc(i), pre) + '</li>' for i in lst[1]) + f'</{lst[0]}>'); lst = None
    def flush(): fp(); fq(); fl()
    for raw in (text or '').replace('\r', '').split('\n'):
        l = raw.rstrip()
        if not l.strip(): flush(); continue
        m = re.match(r'^(#{1,3})\s+(.*)$', l)
        if m: flush(); n = len(m.group(1)) + 1; out.append(f'<h{n}>{inline(esc(m.group(2)), pre)}</h{n}>'); continue
        if re.match(r'^\s*(-{3,}|\*{3,})\s*$', l): flush(); out.append('<hr>'); continue
        m = re.match(r'^>\s?(.*)$', l)
        if m: fp(); fl(); quote.append(m.group(1)); continue
        m = re.match(r'^\s*[-*]\s+(.*)$', l)
        if m:
            fp(); fq()
            if not lst or lst[0] != 'ul': fl(); lst = ['ul', []]
            lst[1].append(m.group(1)); continue
        m = re.match(r'^\s*\d+[.)]\s+(.*)$', l)
        if m:
            fp(); fq()
            if not lst or lst[0] != 'ol': fl(); lst = ['ol', []]
            lst[1].append(m.group(1)); continue
        m = re.match(r'^!v\[([^\]]*)\]\((asset:[A-Za-z0-9_\-.~:@+]+|f:vid/[A-Za-z0-9_\-.]+|https://[^\s)]+)\)$', l.strip())
        if m: flush(); out.append(video_html(m.group(2), m.group(1), pre)); continue
        m = re.match(r'^!\[([^\]]*)\]\((f:img/[a-z0-9]+\.jpg)\)$', l.strip())
        if m:
            flush(); u = src(m.group(2), pre)
            cap = f'<figcaption>{esc(m.group(1))}</figcaption>' if m.group(1).strip() else ''
            out.append(f'<figure><img src="{u}" alt="{esc(m.group(1))}" loading="lazy">{cap}</figure>'); continue
        fq(); fl(); para.append(l)
    flush()
    return ''.join(out)

# ---------- page pieces ----------
TREE = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2 5.5 11H9l-4.5 6.5H11V22h2v-4.5h6.5L15 11h3.5z"/></svg>'
SEARCH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>'
TOOLI = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M9 11l3 3 8-8"/><path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9"/></svg>'

def initial(): return (NAME.strip()[:1] or 'H').upper()
def avatar(pre, cls='avatar'):
    u = src(site.get('avatar'), pre)
    return f'<div class="{cls}">' + (f'<img src="{u}" alt="{esc(NAME)}">' if u else esc(initial())) + '</div>'
def mini(pre): return avatar(pre, 'mini')
def author_by(i): return next((a for a in authors if a['id'] == i), None) if i else None
def au_initial(a):
    n = re.sub(r'\s*醫師\s*$', '', (a or {}).get('name') or '').strip()
    return n[-1:] or '?'
def au_photo(a, cls, pre):
    u = src((a or {}).get('photo'), pre)
    return f'<div class="{cls}">' + (f'<img src="{u}" alt="{esc(a["name"])}">' if u else esc(au_initial(a))) + '</div>'
def lines(t): return [x.strip() for x in str(t or '').split('\n') if x.strip()]
AU_TITLE = site.get('authorsTitle') or '小編是誰'
HEART = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M12 20.5s-7.5-4.6-9.2-9.4C1.6 7.6 3.9 4.5 7.2 4.5c2 0 3.6 1.1 4.8 2.8 1.2-1.7 2.8-2.8 4.8-2.8 3.3 0 5.6 3.1 4.4 6.6-1.7 4.8-9.2 9.4-9.2 9.4z"/></svg>'
def fav_btn(i, big=False):
    if big: return f'<button type="button" class="btn favpill" data-fav="{esc(i)}" aria-pressed="false">{HEART}<span>加入我的最愛</span></button>'
    return f'<button type="button" class="fav" data-fav="{esc(i)}" aria-pressed="false" aria-label="加入我的最愛" title="加入我的最愛">{HEART}</button>'
def thumb(p, pre):
    c = cat(p); t = tones.get(p['cat'], 'c-t3'); u = src(p.get('cover'), pre)
    inner = f'<img src="{u}" alt="" loading="lazy">' if u else f'<div class="ph"><b>{esc(c["name"])}</b>{TREE}</div>'
    return f'<div class="thumb {t}">{inner}</div>'
def byline(p, pre):
    a = author_by(p.get('author'))
    return f'<div class="by">{au_photo(a, "mini", pre) if a else mini(pre)}<b>{esc(a["name"] if a else NAME)}</b><span>{fmt(p.get("publishedAt"))}</span><span>閱讀 {read_min(p)} 分鐘</span></div>'
def post_url(p, pre): return f'{pre}posts/{p["id"]}/'
def card(p, pre, hidden=False):
    return (f'<div class="cw" data-id="{esc(p["id"])}" data-cats="{esc(" ".join(cats_of(p)))}" data-text="{esc((p["title"] + " " + plain(p.get("body")))[:600].lower())}"{" hidden" if hidden else ""}>'
            f'<a class="card" href="{post_url(p, pre)}">{thumb(p, pre)}<span class="cat">{esc(cat(p)["name"])}</span><h3>{esc(p["title"])}</h3><p>{esc(excerpt(p))}</p>{byline(p, pre)}</a>{fav_btn(p["id"])}</div>')

def header(pre, active=''):
    def on(k): return ' class="on"' if active == k else ''
    links = []
    for k in TOP:
        c = CATS[k]
        if c['children']:
            sub = ''.join(f'<a href="{pre}category/{ch}/">{esc(CATS[ch]["name"])}</a>' for ch in c['children'])
            links.append(f'<div class="dd"><a href="{pre}category/{k}/"{on(k)}>{esc(c["name"])}</a><div class="sub">{sub}</div></div>')
        else:
            links.append(f'<a href="{pre}category/{k}/"{on(k)}>{esc(c["name"])}</a>')
    mob = ''.join(f'<a href="{pre}category/{k}/">{esc(CATS[k]["name"])}</a>' + ''.join(f'<a class="indent" href="{pre}category/{ch}/">{esc(CATS[ch]["name"])}</a>' for ch in CATS[k]['children']) for k in TOP)
    fav = f'<a class="favnav" href="{pre}favorites/"{on("favorites")}>{HEART}<span>我的最愛</span><span class="cnt num" hidden></span></a>'
    return (f'<header class="bar"><div class="wrap"><a class="wordmark" href="{pre}">{esc(NAME)}</a>'
            f'<nav class="menu" aria-label="主選單"><a href="{pre}"{on("home")}>首頁</a><a href="{pre}about/"{on("about")}>關於我們</a><a href="{pre}authors/"{on("authors")}>{esc(AU_TITLE)}</a>{"".join(links)}<a href="{pre}tools/"{on("tools")}>工具</a>{fav}</nav>'
            f'<button class="burger" id="burger" type="button" aria-label="開啟選單" aria-expanded="false" aria-controls="mpanel"><span></span><span></span><span></span></button></div>'
            f'<nav class="mpanel" id="mpanel" hidden aria-label="手機選單"><div class="wrap"><a href="{pre}">首頁</a><a href="{pre}about/">關於我們</a><a href="{pre}authors/">{esc(AU_TITLE)}</a>{mob}<a href="{pre}tools/">工具</a>{fav}</div></nav></header>')

def footer():
    y = datetime.date.today().year
    hd = f'（{esc(site["handle"])}）' if site.get('handle') else ''
    return f'<footer><div class="wrap"><span>© {y} {esc(NAME)}{hd}</span><span><a href="https://www.instagram.com/hungry_forest_30/" style="color:inherit">Instagram</a>　<a href="https://www.dcard.tw/@hungryforest30" style="color:inherit">Dcard</a></span></div></footer>'

SCRIPT = """<script>
(function(){var b=document.getElementById('burger'),m=document.getElementById('mpanel');if(b&&m)b.onclick=function(){m.hidden=!m.hidden;b.setAttribute('aria-expanded',String(!m.hidden));};
var $=function(s){return document.querySelector(s)};
%s
try{drawForest();window.addEventListener('resize',function(){clearTimeout(window.__rz);window.__rz=setTimeout(drawForest,150)});}catch(e){}
var K='hf-favs',favs=[];try{favs=JSON.parse(localStorage.getItem(K)||'[]')||[];}catch(e){}
function favUI(){[].forEach.call(document.querySelectorAll('[data-fav]'),function(b){var on=favs.indexOf(b.dataset.fav)>=0;b.setAttribute('aria-pressed',String(on));var s=b.querySelector('span');if(b.classList.contains('favpill')){if(s)s.textContent=on?'已加入我的最愛':'加入我的最愛';}else{b.title=on?'從我的最愛移除':'加入我的最愛';b.setAttribute('aria-label',b.title);}});
[].forEach.call(document.querySelectorAll('.favnav .cnt'),function(c){c.textContent=favs.length;c.hidden=!favs.length;});
var fl=document.getElementById('favlist');if(fl){var n=0;[].forEach.call(fl.querySelectorAll('.cw'),function(c){var i=favs.indexOf(c.dataset.id);c.hidden=i<0;c.style.order=i;if(i>=0)n++;});var fe=document.getElementById('favempty');if(fe)fe.hidden=n>0;var fc=document.getElementById('favcount');if(fc)fc.textContent=n;}}
document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-fav]');if(!b)return;e.preventDefault();e.stopPropagation();var i=favs.indexOf(b.dataset.fav);if(i>=0)favs.splice(i,1);else favs.unshift(b.dataset.fav);try{localStorage.setItem(K,JSON.stringify(favs));}catch(x){}favUI();});
favUI();
var g=document.getElementById('grid');if(g){var f='all',q='';var cards=[].slice.call(g.querySelectorAll('.cw'));var groups=%s;
function apply(){var n=0;cards.forEach(function(c){var cs=c.dataset.cats.split(' '),ks=groups[f]||[f];var ok=(f==='all'||cs.some(function(k){return ks.indexOf(k)>=0}))&&(!q||c.dataset.text.indexOf(q)>=0);c.hidden=!ok;if(ok)n++;});var e=document.getElementById('noresult');if(e)e.hidden=n>0;}
[].forEach.call(document.querySelectorAll('[data-filter]'),function(b){b.onclick=function(){f=b.dataset.filter;[].forEach.call(document.querySelectorAll('[data-filter]'),function(x){x.classList.toggle('on',x===b)});apply();}});
var qi=document.getElementById('q');if(qi)qi.oninput=function(){q=qi.value.trim().toLowerCase();apply();};}
})();
</script>"""

EXTRA_CSS = """
.prose video{width:100%;max-height:78vh;border-radius:14px;background:#000;display:block}
.prose .yt{position:relative;aspect-ratio:16/9;border-radius:14px;overflow:hidden;background:#000}
.prose .yt iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.cw[hidden]{display:none!important}
.prose figure img{max-width:100%;max-height:min(80vh,820px);width:auto;height:auto;margin:0 auto;display:block}
.post .cover img{max-height:70vh;width:auto;margin:0 auto}
.srclink{max-width:700px;margin:28px auto 0;font-size:14px;color:var(--muted)}
.srclink a{color:var(--moss)}
"""

def page(title, desc, body, pre, canonical, image='', jsonld=None, active='', noindex=False):
    og_img = BASE + '/' + (image or 'share/og-image.jpg')
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ''
    groups = json.dumps({k: keys_under(k) for k in TOP}, ensure_ascii=False)
    return f'''<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">{'<meta name="robots" content="noindex">' if noindex else ''}
<meta property="og:type" content="{'article' if jsonld and jsonld.get('@type') == 'BlogPosting' else 'website'}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:site_name" content="{esc(NAME)}">
{f'<meta property="og:image" content="{esc(og_img)}">' if og_img else ''}
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Noto+Serif+TC:wght@600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap">
<link rel="stylesheet" href="{pre}style.css">
{ld}
</head>
<body>
{header(pre, active)}
<main>{body}</main>
{footer()}
{SCRIPT % (forest, groups)}
</body>
</html>'''

def write(path, content):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, 'w').write(content)

# ---------- build ----------
os.makedirs(OUT, exist_ok=True)
if IMG_SRC.endswith('_img_keep') and os.path.isdir(os.path.join(OUT, 'img')):
    shutil.rmtree(IMG_SRC, ignore_errors=True); shutil.copytree(os.path.join(OUT, 'img'), IMG_SRC)
for d in ('posts', 'category', 'tools', 'img', 'about', 'authors', 'favorites'):
    shutil.rmtree(os.path.join(OUT, d), ignore_errors=True)
os.makedirs(os.path.join(OUT, 'img'))
used = set()
for p in posts:
    for r in re.findall(r'f:img/([a-z0-9]+\.jpg)', (p.get('body') or '') + ' ' + (p.get('cover') or '')): used.add(r)
for r in [site.get('avatar') or ''] + [a.get('photo') or '' for a in authors]:
    m = re.match(r'f:img/([a-z0-9]+\.jpg)$', r)
    if m: used.add(m.group(1))
for f in used: shutil.copy(os.path.join(IMG_SRC, f), os.path.join(OUT, 'img', f))
open(os.path.join(OUT, 'style.css'), 'w').write(css + EXTRA_CSS)

def tool_card(t):
    return (f'<div class="tool"><div class="ico">{TOOLI}</div><span class="cat">{esc(t.get("tag") or "工具")}</span><h3>{esc(t["title"])}</h3><p>{esc(t["desc"])}</p>'
            f'<div class="row"><a class="btn primary" href="{esc(t["url"])}" target="_blank" rel="noopener">開始使用</a></div></div>')

# home
pre = ''
tagline = site.get('tagline') or ''
hero = (f'<section class="hero"><canvas id="forest" aria-hidden="true"></canvas><div class="shade"></div><div class="wrap">'
        + (f'<p class="alias">{esc(site["handle"])}</p>' if site.get('handle') else '') +
        f'<h1>{esc(NAME)}</h1><p class="tag">{esc(tagline)}</p><div class="row"><a class="btn light" href="#posts-sec">看文章</a><a class="btn ghost" href="about/">關於我們</a></div></div></section>')
tags = ''.join(f'<a href="category/{k}/">{esc(CATS[k]["name"])}</a>' for k in TOP) + '<a href="tools/">工具</a>'
about = (f'<section class="section" id="about-sec"><div class="wrap about">{avatar(pre)}<div>'
         f'<h2>嗨，我們是 {esc(NAME)}</h2>' + (f'<div class="role">{esc(site["role"])}</div>' if site.get('role') else '<div style="height:14px"></div>')
         + (f'<p class="bio">{esc(site["about"])}</p>' if site.get('about') else f'<p class="bio">{esc(tagline)}</p>')
         + f'<div class="row" style="margin-bottom:20px"><a class="btn primary" href="about/">關於我們</a><a class="btn" href="authors/">{esc(AU_TITLE)}</a></div>'
         + f'<div class="tags">{tags}</div></div></div></section>')
fl = [p for p in posts if p.get('featured') or in_cats(p, [FEAT_CAT])]
feat = fl[0] if fl else None
featured = ''
if feat:
    fname = CATS[FEAT_CAT]['name'] if FEAT_CAT in CATS else '醫學生專欄'
    featured = (f'<section class="section soft"><div class="wrap"><div class="sh"><div><h2>精選文章</h2><p>來自{esc(fname)}，寫給正在學醫路上的你。</p></div>'
                + (f'<a class="link" href="category/{FEAT_CAT}/">看全部</a>' if FEAT_CAT in CATS else '') + '</div>'
                f'<div class="feature-wrap"><div class="cw"><a class="feature" href="{post_url(feat, pre)}" tabindex="-1" aria-hidden="true">{thumb(feat, pre)}</a>{fav_btn(feat["id"])}</div>'
                f'<a class="ft" href="{post_url(feat, pre)}"><span class="cat">{esc(cat(feat)["name"])}</span><h3 style="font-size:clamp(26px,3.4vw,36px);margin:8px 0 12px">{esc(feat["title"])}</h3><p class="muted" style="margin:0 0 18px;font-size:17px">{esc(excerpt(feat, 150))}</p>{byline(feat, pre)}</a></div>'
                + (f'<div class="grid" style="margin-top:56px">{"".join(card(p, pre) for p in fl[1:])}</div>' if len(fl) > 1 else '') + '</div></section>')
tabs = '<button type="button" data-filter="all" class="on">全部</button>' + ''.join(f'<button type="button" data-filter="{k}">{esc(CATS[k]["name"])}</button>' for k in TOP)
grid = (f'<section class="section" id="posts-sec"><div class="wrap"><div class="sh"><div><h2>所有文章</h2><p>共 <span class="num">{len(posts)}</span> 篇</p></div></div>'
        f'<div class="filters"><div class="ftabs" role="tablist">{tabs}</div><label class="search">{SEARCH}<input type="text" id="q" placeholder="搜尋文章" aria-label="搜尋文章"></label></div>'
        f'<div class="grid" id="grid">{"".join(card(p, pre) for p in posts)}</div><div class="empty" id="noresult" hidden><b>找不到符合的文章</b><span>換個關鍵字試試看。</span></div></div></section>')
toolsec = f'<section class="section soft"><div class="wrap"><div class="sh"><div><h2>工具</h2><p>自己做的小工具，點「開始使用」會在新分頁打開。</p></div><a class="link" href="tools/">全部工具</a></div><div class="tools">{"".join(tool_card(t) for t in tools)}</div></div></section>'
home_desc = f'{NAME}（{site.get("handle","")}）的部落格：{tagline} 美食食記、旅遊、兒科與復健科的醫院大小事。'
write('index.html', page(f'{NAME}｜{site.get("handle","")} 的美食、旅遊與醫院大小事', home_desc, hero + about + featured + grid + toolsec, pre, BASE + '/',
                         jsonld={'@context': 'https://schema.org', '@type': 'Blog', 'name': NAME, 'alternateName': [site.get('handle', ''), 'hungryforest30', 'Hungryforest'], 'url': BASE + '/', 'description': home_desc}, active='home'))

# categories
for k, c in CATS.items():
    pre = '../../'
    lst = [p for p in posts if in_cats(p, keys_under(k))]
    top = c['parent'] or k
    crumb = f'<div class="crumb"><a href="{pre}">首頁</a> / ' + (f'<a href="{pre}category/{top}/">{esc(CATS[top]["name"])}</a> / ' if c['parent'] else '') + esc(c['name']) + '</div>'
    sub = ''
    if CATS[top]['children']:
        sub = f'<div class="subtabs"><a href="{pre}category/{top}/" class="{"on" if k == top else ""}">全部{esc(CATS[top]["name"])}</a>' + ''.join(f'<a href="{pre}category/{ch}/" class="{"on" if k == ch else ""}">{esc(CATS[ch]["name"])}</a>' for ch in CATS[top]['children']) + '</div>'
    body = (f'<section class="phead"><div class="wrap">{crumb}<h1>{esc(c["name"])}</h1><p>{esc(c["desc"]) + "，" if c["desc"] else ""}共 <span class="num">{len(lst)}</span> 篇。</p>{sub}</div></section>'
            f'<section class="section"><div class="wrap">' + (f'<div class="grid">{"".join(card(p, pre) for p in lst)}</div>' if lst else '<div class="empty"><b>這裡還沒有文章</b></div>') + '</div></section>')
    write(f'category/{k}/index.html', page(f'{c["name"]}｜{NAME}', f'{NAME} 的{c["name"]}文章：{c["desc"]}', body, pre, f'{BASE}/category/{k}/', active=top))

# posts
for i, p in enumerate(posts):
    pre = '../../'
    c = cat(p)
    same = [x for x in posts if x['cat'] == p['cat']]
    j = same.index(p)
    newer = same[j - 1] if j > 0 else None
    older = same[j + 1] if j + 1 < len(same) else None
    more = [x for x in same if x is not p][:3]
    crumb = (f'<a href="{pre}category/{c["parent"]}/">{esc(CATS[c["parent"]]["name"])}</a> / ' if c.get('parent') else '') + f'<a href="{pre}category/{p["cat"]}/">{esc(c["name"])}</a>'
    cover = src(p.get('cover'), pre)
    first = re.search(r'f:img/[a-z0-9]+\.jpg', p.get('body') or '')
    if first and p.get('cover') and first.group(0) == p['cover']: cover = ''
    pn = ''
    if older or newer:
        pn = '<nav class="pn">' + (f'<a href="{post_url(older, pre)}"><small>上一篇</small>{esc(older["title"])}</a>' if older else '<span></span>') + (f'<a href="{post_url(newer, pre)}" style="text-align:right"><small>下一篇</small>{esc(newer["title"])}</a>' if newer else '') + '</nav>'
    a = author_by(p.get('author'))
    if a: abox = f'<a class="authorbox" href="{pre}authors/#au-{esc(a["id"])}">{au_photo(a, "avatar", pre)}<div><small>作者</small><b>{esc(a["name"])}</b><p>{esc((lines(a.get("title")) or ["認識作者"])[0])}</p></div></a>'
    elif len(authors) >= 2: abox = f'<a class="authorbox" href="{pre}authors/">{avatar(pre)}<div><small>兩人共筆</small><b>{esc("、".join(x["name"] for x in authors[:2]))}</b><p>{esc(site.get("role") or "認識小編")}</p></div></a>'
    else: abox = f'<div class="authorbox">{avatar(pre)}<div><b>{esc(NAME)}</b><p>{esc(site.get("role") or tagline)}</p></div></div>'
    body = (f'<article class="post"><div class="wrap"><div class="head"><div class="crumb">{crumb}</div><h1>{esc(p["title"])}</h1>{byline(p, pre)}'
            f'<div class="row" style="justify-content:center;margin-top:18px">{fav_btn(p["id"], True)}</div></div>'
            + (f'<div class="cover"><img src="{cover}" alt="{esc(p["title"])}"></div>' if cover else '')
            + f'<div class="prose">{md(p.get("body"), pre)}</div>'
            + abox
            + pn + '</div></article>'
            + (f'<section class="section soft"><div class="wrap"><div class="sh"><h2>更多{esc(c["name"])}</h2><a class="link" href="{pre}category/{p["cat"]}/">看全部</a></div><div class="grid">{"".join(card(x, pre) for x in more)}</div></div></section>' if more else ''))
    url = f'{BASE}/posts/{p["id"]}/'
    ld = {'@context': 'https://schema.org', '@type': 'BlogPosting', 'headline': p['title'], 'datePublished': iso(p['publishedAt']),
          'dateModified': iso(p.get('updatedAt') or p['publishedAt']), 'author': {'@type': 'Person', 'name': NAME, 'alternateName': site.get('handle', '')},
          'mainEntityOfPage': url, 'articleSection': c['name']}
    if p.get('cover'): ld['image'] = BASE + '/' + src(p['cover'], '')
    if a: ld['author'] = {'@type': 'Person', 'name': a['name']}
    elif len(authors) >= 2: ld['author'] = [{'@type': 'Person', 'name': x['name']} for x in authors[:2]]
    write(f'posts/{p["id"]}/index.html', page(f'{p["title"]}｜{c["name"]}｜{NAME}', excerpt(p, 140), body, pre, url, image=src(p.get('cover'), ''), jsonld=ld, active=c.get('parent') or p['cat']))

# about us, authors, favorites
pre = '../'
counts = [(k, len([p for p in posts if in_cats(p, keys_under(k))])) for k in TOP]
side = ('<aside class="usside">'
        + (f'<div class="panel"><h3>{esc(AU_TITLE)}</h3>' + ''.join(f'<a class="aumini" href="{pre}authors/#au-{esc(a["id"])}">{au_photo(a, "mini", pre)}<span><b>{esc(a["name"])}</b><small>{esc((lines(a.get("title")) or [""])[0])}</small></span></a>' for a in authors) + f'<p style="margin:8px 0 0"><a class="link" href="{pre}authors/">看完整介紹</a></p></div>' if authors else '')
        + '<div class="panel"><h3>這裡寫了什麼</h3><ul class="stat">' + ''.join(f'<li><a href="{pre}category/{k}/">{esc(CATS[k]["name"])}</a><span class="num muted">{n} 篇</span></li>' for k, n in counts if n) + '</ul></div></aside>')
us = md(site['usBody'], pre) if site.get('usBody') else f'<p>{esc(site.get("about") or tagline)}</p>'
write('about/index.html', page(f'關於我們｜{NAME}', f'{NAME}（{site.get("handle","")}）是兩位醫師一起經營的部落格：{tagline}',
      f'<section class="phead"><div class="wrap"><div class="crumb"><a href="{pre}">首頁</a> / 關於我們</div><h1>關於我們</h1><p>{esc(tagline)}</p></div></section>'
      f'<section class="section"><div class="wrap usgrid"><div class="prose">{us}</div>{side}</div></section>', pre, f'{BASE}/about/', active='about'))

def au_block(a):
    edu, exp = lines(a.get('edu')), lines(a.get('exp'))
    mine = [p for p in posts if p.get('author') == a['id']]
    return (f'<section class="au" id="au-{esc(a["id"])}"><div class="pw">{au_photo(a, "photo", pre)}</div><div><div class="kicker">AUTHOR</div><h2>{esc(a["name"])}</h2>'
            + (f'<div class="ttl">{esc(a["title"])}</div>' if a.get('title') else '<div style="height:16px"></div>')
            + (f'<p class="bio">{esc(a["bio"])}</p>' if a.get('bio') else '')
            + ('<div class="cv">' + (f'<div><h3>學歷</h3><ul>{"".join(f"<li>{esc(x)}</li>" for x in edu)}</ul></div>' if edu else '') + (f'<div><h3>經歷</h3><ul>{"".join(f"<li>{esc(x)}</li>" for x in exp)}</ul></div>' if exp else '') + '</div>' if edu or exp else '')
            + (f'<div class="auposts"><h3>{esc(re.sub(r"\s*醫師\s*$", "", a["name"]))} 寫的文章</h3>' + ''.join(f'<a href="{post_url(p, pre)}"><span>{esc(p["title"])}</span><small class="num">{fmt(p.get("publishedAt"))}</small></a>' for p in mine[:5]) + '</div>' if mine else '')
            + '</div></section>')
write('authors/index.html', page(f'{AU_TITLE}｜{NAME}', f'{NAME} 的作者：' + '、'.join(a['name'] for a in authors) + '。' + (site.get('authorsSub') or ''),
      f'<section class="phead"><div class="wrap"><div class="crumb"><a href="{pre}">首頁</a> / {esc(AU_TITLE)}</div><h1>{esc(AU_TITLE)}</h1><p>{esc(site.get("authorsSub") or "")}</p></div></section>'
      f'<div class="wrap"><div class="authors">{"".join(au_block(a) for a in authors)}</div></div>', pre, f'{BASE}/authors/', active='authors'))

write('favorites/index.html', page(f'我的最愛｜{NAME}', f'你在 {NAME} 收藏的文章。',
      f'<section class="phead"><div class="wrap"><div class="crumb"><a href="{pre}">首頁</a> / 我的最愛</div><h1>我的最愛</h1><p>你收藏的文章，共 <span class="num" id="favcount">0</span> 篇。收藏存在這個瀏覽器裡。</p></div></section>'
      f'<section class="section"><div class="wrap"><div class="grid" id="favlist">{"".join(card(p, pre, hidden=True) for p in posts)}</div>'
      f'<div class="empty" id="favempty"><b>還沒有收藏的文章</b><span>看到喜歡的文章，點封面右上角的愛心，就會收進這裡。</span><div class="row"><a class="btn primary" href="{pre}#posts-sec">去逛逛文章</a></div></div></div></section>',
      pre, f'{BASE}/favorites/', active='favorites', noindex=True))

# tools
pre = '../'
write('tools/index.html', page(f'工具｜{NAME}', f'{NAME} 自己做的小工具：兒科專科刷題等。',
      f'<section class="phead"><div class="wrap"><div class="crumb"><a href="{pre}">首頁</a> / 工具</div><h1>工具</h1><p>自己做的小工具，點「開始使用」會在新分頁打開。</p></div></section><section class="section"><div class="wrap"><div class="tools">{"".join(tool_card(t) for t in tools)}</div></div></section>',
      pre, f'{BASE}/tools/', active='tools'))

# 404, robots, sitemap
write('404.html', page(f'找不到頁面｜{NAME}', '找不到這個頁面', '<div class="wrap pagehead"><h1>找不到這個頁面</h1><p><a class="link" href="/">回首頁</a></p></div>', '/', BASE + '/'))
urls = [(BASE + '/', None), (f'{BASE}/about/', None), (f'{BASE}/authors/', None)] + [(f'{BASE}/category/{k}/', None) for k in CATS] + [(f'{BASE}/tools/', None)] + [(f'{BASE}/posts/{p["id"]}/', p) for p in posts]
sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for u, p in urls:
    lm = f'<lastmod>{iso((p or {}).get("updatedAt") or (p or {}).get("publishedAt") or (posts[0]["publishedAt"] if posts else 0))[:10]}</lastmod>'
    sm.append(f'<url><loc>{esc(u)}</loc>{lm}</url>')
sm.append('</urlset>')
write('sitemap.xml', '\n'.join(sm))
write('robots.txt', f'User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n')
write('.nojekyll', '')
if IMG_SRC.endswith('_img_keep'): shutil.rmtree(IMG_SRC, ignore_errors=True)
print('built', len(posts), 'posts,', len(CATS), 'categories,', len(used), 'images ->', OUT)
