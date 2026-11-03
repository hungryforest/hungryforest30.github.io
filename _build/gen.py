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
def cat(p): return CATS.get(p['cat'], {'key': '', 'name': '未分類', 'desc': '', 'parent': '', 'children': []})

esc = lambda s: html.escape(str(s or ''), quote=True)

def fmt(ms):
    if not ms: return ''
    d = datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone(datetime.timedelta(hours=8)))
    return d.strftime('%Y.%m.%d')
def iso(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone(datetime.timedelta(hours=8))).isoformat()

def plain(md):
    s = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', md or '')
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
def mini(pre): return f'<div class="mini">{esc(initial())}</div>'
def thumb(p, pre):
    c = cat(p); t = tones.get(p['cat'], 'c-t3'); u = src(p.get('cover'), pre)
    inner = f'<img src="{u}" alt="" loading="lazy">' if u else f'<div class="ph"><b>{esc(c["name"])}</b>{TREE}</div>'
    return f'<div class="thumb {t}">{inner}</div>'
def byline(p, pre):
    return f'<div class="by">{mini(pre)}<b>{esc(NAME)}</b><span>{fmt(p.get("publishedAt"))}</span><span>閱讀 {read_min(p)} 分鐘</span></div>'
def post_url(p, pre): return f'{pre}posts/{p["id"]}/'
def card(p, pre):
    return (f'<a class="card" href="{post_url(p, pre)}" data-cat="{esc(p["cat"])}" data-text="{esc((p["title"] + " " + plain(p.get("body")))[:600].lower())}">'
            f'{thumb(p, pre)}<span class="cat">{esc(cat(p)["name"])}</span><h3>{esc(p["title"])}</h3><p>{esc(excerpt(p))}</p>{byline(p, pre)}</a>')

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
    return (f'<header class="bar"><div class="wrap"><a class="wordmark" href="{pre}">{esc(NAME)}</a>'
            f'<nav class="menu" aria-label="主選單"><a href="{pre}"{on("home")}>首頁</a><a href="{pre}#about-sec">關於我</a>{"".join(links)}<a href="{pre}tools/"{on("tools")}>工具</a></nav>'
            f'<button class="burger" id="burger" type="button" aria-label="開啟選單" aria-expanded="false" aria-controls="mpanel"><span></span><span></span><span></span></button></div>'
            f'<nav class="mpanel" id="mpanel" hidden aria-label="手機選單"><div class="wrap"><a href="{pre}">首頁</a><a href="{pre}#about-sec">關於我</a>{mob}<a href="{pre}tools/">工具</a></div></nav></header>')

def footer():
    y = datetime.date.today().year
    hd = f'（{esc(site["handle"])}）' if site.get('handle') else ''
    return f'<footer><div class="wrap"><span>© {y} {esc(NAME)}{hd}</span><span><a href="https://www.instagram.com/hungry_forest_30/" style="color:inherit">Instagram</a>　<a href="https://www.dcard.tw/@hungryforest30" style="color:inherit">Dcard</a></span></div></footer>'

SCRIPT = """<script>
(function(){var b=document.getElementById('burger'),m=document.getElementById('mpanel');if(b&&m)b.onclick=function(){m.hidden=!m.hidden;b.setAttribute('aria-expanded',String(!m.hidden));};
var $=function(s){return document.querySelector(s)};
%s
try{drawForest();window.addEventListener('resize',function(){clearTimeout(window.__rz);window.__rz=setTimeout(drawForest,150)});}catch(e){}
var g=document.getElementById('grid');if(g){var f='all',q='';var cards=[].slice.call(g.querySelectorAll('.card'));var groups=%s;
function apply(){var n=0;cards.forEach(function(c){var ok=(f==='all'||(groups[f]||[f]).indexOf(c.dataset.cat)>=0)&&(!q||c.dataset.text.indexOf(q)>=0);c.hidden=!ok;if(ok)n++;});var e=document.getElementById('noresult');if(e)e.hidden=n>0;}
[].forEach.call(document.querySelectorAll('[data-filter]'),function(b){b.onclick=function(){f=b.dataset.filter;[].forEach.call(document.querySelectorAll('[data-filter]'),function(x){x.classList.toggle('on',x===b)});apply();}});
var qi=document.getElementById('q');if(qi)qi.oninput=function(){q=qi.value.trim().toLowerCase();apply();};}
})();
</script>"""

EXTRA_CSS = """
.card[hidden]{display:none!important}
.prose figure img{max-width:100%;max-height:min(80vh,820px);width:auto;height:auto;margin:0 auto;display:block}
.post .cover img{max-height:70vh;width:auto;margin:0 auto}
.srclink{max-width:700px;margin:28px auto 0;font-size:14px;color:var(--muted)}
.srclink a{color:var(--moss)}
"""

def page(title, desc, body, pre, canonical, image='', jsonld=None, active=''):
    og_img = (BASE + '/' + image) if image else ''
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ''
    groups = json.dumps({k: keys_under(k) for k in TOP}, ensure_ascii=False)
    return f'''<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
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
for d in ('posts', 'category', 'tools', 'img'):
    shutil.rmtree(os.path.join(OUT, d), ignore_errors=True)
os.makedirs(os.path.join(OUT, 'img'))
used = set()
for p in posts:
    for r in re.findall(r'f:img/([a-z0-9]+\.jpg)', (p.get('body') or '') + ' ' + (p.get('cover') or '')): used.add(r)
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
        f'<h1>{esc(NAME)}</h1><p class="tag">{esc(tagline)}</p><div class="row"><a class="btn light" href="#posts-sec">看文章</a><a class="btn ghost" href="#about-sec">關於我</a></div></div></section>')
tags = ''.join(f'<a href="category/{k}/">{esc(CATS[k]["name"])}</a>' for k in TOP) + '<a href="tools/">工具</a>'
about = (f'<section class="section" id="about-sec"><div class="wrap about"><div class="avatar">{esc(initial())}</div><div>'
         f'<h2>嗨，我是 {esc(NAME)}</h2>' + (f'<div class="role">{esc(site["role"])}</div>' if site.get('role') else '<div style="height:14px"></div>')
         + (f'<p class="bio">{esc(site["about"])}</p>' if site.get('about') else f'<p class="bio">{esc(tagline)}</p>')
         + f'<div class="tags">{tags}</div></div></div></section>')
feat = next((p for p in posts if p.get('featured')), posts[0] if posts else None)
featured = ''
if feat:
    featured = (f'<section class="section soft"><div class="wrap"><div class="sh"><h2>精選文章</h2></div><a class="feature" href="{post_url(feat, pre)}">{thumb(feat, pre)}'
                f'<div><span class="cat">{esc(cat(feat)["name"])}</span><h3>{esc(feat["title"])}</h3><p>{esc(excerpt(feat, 150))}</p>{byline(feat, pre)}</div></a></div></section>')
tabs = '<button type="button" data-filter="all" class="on">全部</button>' + ''.join(f'<button type="button" data-filter="{k}">{esc(CATS[k]["name"])}</button>' for k in TOP)
grid = (f'<section class="section" id="posts-sec"><div class="wrap"><div class="sh"><div><h2>所有文章</h2><p>共 <span class="num">{len(posts)}</span> 篇</p></div></div>'
        f'<div class="filters"><div class="ftabs" role="tablist">{tabs}</div><label class="search">{SEARCH}<input type="text" id="q" placeholder="搜尋文章" aria-label="搜尋文章"></label></div>'
        f'<div class="grid" id="grid">{"".join(card(p, pre) for p in posts)}</div><div class="empty" id="noresult" hidden><b>找不到符合的文章</b><span>換個關鍵字試試看。</span></div></div></section>')
toolsec = f'<section class="section soft"><div class="wrap"><div class="sh"><div><h2>工具</h2><p>自己做的小工具，點「開始使用」會在新分頁打開。</p></div><a class="link" href="tools/">全部工具</a></div><div class="tools">{"".join(tool_card(t) for t in tools)}</div></div></section>'
home_desc = f'{NAME}（{site.get("handle","")}）的部落格：{tagline} 美食食記、旅遊、兒科與復健科的醫院大小事。'
write('index.html', page(f'{NAME}｜{site.get("handle","")} 的美食、旅遊與醫院大小事', home_desc, hero + about + featured + grid + toolsec, pre, BASE + '/',
                         image=src(feat.get('cover'), '') if feat else '', jsonld={'@context': 'https://schema.org', '@type': 'Blog', 'name': NAME, 'alternateName': [site.get('handle', ''), 'hungryforest30', 'Hungryforest'], 'url': BASE + '/', 'description': home_desc}, active='home'))

# categories
for k, c in CATS.items():
    pre = '../../'
    lst = [p for p in posts if p['cat'] in keys_under(k)]
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
    body = (f'<article class="post"><div class="wrap"><div class="head"><div class="crumb">{crumb}</div><h1>{esc(p["title"])}</h1>{byline(p, pre)}</div>'
            + (f'<div class="cover"><img src="{cover}" alt="{esc(p["title"])}"></div>' if cover else '')
            + f'<div class="prose">{md(p.get("body"), pre)}</div>'
            + f'<div class="authorbox"><div class="avatar">{esc(initial())}</div><div><b>{esc(NAME)}</b><p>{esc(site.get("role") or tagline)}</p></div></div>'
            + pn + '</div></article>'
            + (f'<section class="section soft"><div class="wrap"><div class="sh"><h2>更多{esc(c["name"])}</h2><a class="link" href="{pre}category/{p["cat"]}/">看全部</a></div><div class="grid">{"".join(card(x, pre) for x in more)}</div></div></section>' if more else ''))
    url = f'{BASE}/posts/{p["id"]}/'
    ld = {'@context': 'https://schema.org', '@type': 'BlogPosting', 'headline': p['title'], 'datePublished': iso(p['publishedAt']),
          'dateModified': iso(p.get('updatedAt') or p['publishedAt']), 'author': {'@type': 'Person', 'name': NAME, 'alternateName': site.get('handle', '')},
          'mainEntityOfPage': url, 'articleSection': c['name']}
    if p.get('cover'): ld['image'] = BASE + '/' + src(p['cover'], '')
    write(f'posts/{p["id"]}/index.html', page(f'{p["title"]}｜{c["name"]}｜{NAME}', excerpt(p, 140), body, pre, url, image=src(p.get('cover'), ''), jsonld=ld, active=c.get('parent') or p['cat']))

# tools
pre = '../'
write('tools/index.html', page(f'工具｜{NAME}', f'{NAME} 自己做的小工具：兒科專科刷題等。',
      f'<section class="phead"><div class="wrap"><div class="crumb"><a href="{pre}">首頁</a> / 工具</div><h1>工具</h1><p>自己做的小工具，點「開始使用」會在新分頁打開。</p></div></section><section class="section"><div class="wrap"><div class="tools">{"".join(tool_card(t) for t in tools)}</div></div></section>',
      pre, f'{BASE}/tools/', active='tools'))

# 404, robots, sitemap
write('404.html', page(f'找不到頁面｜{NAME}', '找不到這個頁面', '<div class="wrap pagehead"><h1>找不到這個頁面</h1><p><a class="link" href="/">回首頁</a></p></div>', '/', BASE + '/'))
urls = [(BASE + '/', None)] + [(f'{BASE}/category/{k}/', None) for k in CATS] + [(f'{BASE}/tools/', None)] + [(f'{BASE}/posts/{p["id"]}/', p) for p in posts]
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
