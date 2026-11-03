function drawForest(){
  const cv = $("#forest"); if(!cv) return;
  const w = cv.clientWidth, h = cv.clientHeight; if(!w || !h) return;
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
  const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  let seed = 30; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const sky = g.createLinearGradient(0, 0, 0, h);
  sky.addColorStop(0, "#0D221E"); sky.addColorStop(.55, "#1F4238"); sky.addColorStop(1, "#4C7462");
  g.fillStyle = sky; g.fillRect(0, 0, w, h);
  for(let i = 0; i < 70; i++){ g.globalAlpha = .25 + rnd() * .55; g.fillStyle = "#F4EBD2"; g.beginPath(); g.arc(rnd() * w, rnd() * h * .5, rnd() * 1.3 + .3, 0, 7); g.fill(); }
  g.globalAlpha = 1;
  const mx = w * .78, my = h * .26, mr = Math.max(28, Math.min(54, w * .04));
  const glow = g.createRadialGradient(mx, my, mr * .6, mx, my, mr * 4);
  glow.addColorStop(0, "rgba(244,227,181,.35)"); glow.addColorStop(1, "rgba(244,227,181,0)");
  g.fillStyle = glow; g.fillRect(0, 0, w, h);
  g.fillStyle = "#F4E3B5"; g.beginPath(); g.arc(mx, my, mr, 0, 7); g.fill();
  const layers = [["#35604F", .60, .55], ["#26493D", .70, .75], ["#18362C", .80, 1], ["#0C2019", .91, 1.3]];
  layers.forEach(([col, base, sc], li) => {
    const y0 = h * base; g.fillStyle = col;
    g.beginPath(); g.moveTo(0, h); g.lineTo(0, y0);
    for(let x = 0; x <= w; x += 40){ g.lineTo(x, y0 - Math.sin(x / 180 + li) * 10 * sc); }
    g.lineTo(w, h); g.closePath(); g.fill();
    let x = -20 - rnd() * 30;
    while(x < w + 40){
      const th = (50 + rnd() * 70) * sc * (h / 520), tw = th * (.32 + rnd() * .1);
      const yb = y0 - Math.sin(x / 180 + li) * 10 * sc + 4;
      for(let t = 0; t < 3; t++){
        const ty = yb - th * (t * .28), tt = th * (.55 - t * .1), ww = tw * (1 - t * .22);
        g.beginPath(); g.moveTo(x - ww / 2, ty); g.lineTo(x, ty - tt); g.lineTo(x + ww / 2, ty); g.closePath(); g.fill();
      }
      x += tw * (.55 + rnd() * .7);
    }
    if(li < 3){ const m = g.createLinearGradient(0, y0 - 40, 0, h); m.addColorStop(0, "rgba(160,190,170,0)"); m.addColorStop(1, "rgba(160,190,170,.10)"); g.fillStyle = m; g.fillRect(0, y0 - 40, w, h - y0 + 40); }
  });
}
