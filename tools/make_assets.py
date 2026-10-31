#!/usr/bin/env python3
"""Generate the repo's SVG visual layer (banner, flow diagram, flat badges).

Deterministic: the noise strip uses a fixed seed, so re-running produces
byte-identical assets.
"""

import pathlib
import random

OUT = pathlib.Path(__file__).resolve().parent.parent / "assets"
OUT.mkdir(exist_ok=True)

INK = "#0c0d11"
INK2 = "#15171d"
GOLD = "#d4b038"
EMBER = "#c4692a"
PAPER = "#f6f2e9"
DIM = "#8b8f9e"
MONO = "SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"
SERIF = "Georgia, 'Times New Roman', serif"

SERIF_STACK = SERIF


def noise_bars(x, y, w, h, count=72, seed=20260205):
    rnd = random.Random(seed)
    step = w / count
    bars = []
    for i in range(count):
        v = rnd.random()
        bh = max(3, int(v * h))
        op = 0.28 + v * 0.62
        color = GOLD if v > 0.82 else (EMBER if v > 0.66 else "#5d6070")
        bars.append(
            f'<rect x="{x + i * step:.1f}" y="{y + h - bh}" width="{max(1.6, step * 0.52):.1f}" '
            f'height="{bh}" fill="{color}" opacity="{op:.2f}"/>'
        )
    return "\n    ".join(bars)


banner = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="300" viewBox="0 0 1200 300" role="img" aria-label="The Entropy Challenge — QuevaTech">
  <defs>
    <linearGradient id="glow" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{GOLD}" stop-opacity=".16"/>
      <stop offset="1" stop-color="{GOLD}" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{GOLD}" stop-opacity=".22"/>
      <stop offset="1" stop-color="{GOLD}" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <rect width="1200" height="300" fill="{INK}"/>
  <rect width="1200" height="300" fill="url(#glow)"/>
  <g stroke="#ffffff" stroke-opacity=".05">
    {"".join(f'<path d="M{x} 0V300"/>' for x in range(60, 1200, 60))}
  </g>

  <!-- noise strip -->
  <g>
    {noise_bars(700, 54, 440, 120)}
    <path d="M700 196H1140" stroke="#ffffff" stroke-opacity=".12"/>
    <text x="700" y="214" fill="#a8abba" font-family="{MONO}" font-size="11" letter-spacing="1.3">RAW SOURCE · 11.16 MB · 93,620,224 BITS</text>
  </g>

  <!-- text block -->
  <text x="60" y="74" fill="{GOLD}" font-family="{MONO}" font-size="11" letter-spacing="4.2">QUEVATECH RESEARCH · PUBLIC VERIFICATION</text>
  <text x="58" y="150" fill="{PAPER}" font-family="{SERIF_STACK}" font-size="66" letter-spacing="-1.4">The Entropy Challenge</text>
  <text x="60" y="186" fill="{DIM}" font-family="{MONO}" font-size="15">RF noise → neural conditioning → SHA-3.  Prove us wrong.</text>

  <path d="M60 222H1140" stroke="#ffffff" stroke-opacity=".09"/>
  <text x="60" y="254" fill="#a8abba" font-family="{MONO}" font-size="12.5" letter-spacing=".8">SAMPLE sha256 9e78d28e… 3dacd1</text>
  <text x="450" y="254" fill="#a8abba" font-family="{MONO}" font-size="12.5" letter-spacing=".8">NIST SP 800-22 · 180/188</text>
  <text x="740" y="254" fill="#a8abba" font-family="{MONO}" font-size="12.5" letter-spacing=".8">SP 800-90B · 0.9467 bit/bit (min)</text>

  <rect x="0" y="296" width="1200" height="4" fill="url(#fade)"/>
</svg>
'''

flow = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="290" viewBox="0 0 1100 290" role="img" aria-label="Entropy source architecture">
  <rect width="1100" height="290" fill="{INK}"/>
  <g font-family="{MONO}">
    <text x="40" y="46" fill="{DIM}" font-size="10.5" letter-spacing="3.4">ENTROPY SOURCE · THREE LAYERS</text>
    <path d="M40 60H1060" stroke="#ffffff" stroke-opacity=".1"/>
  </g>

  <!-- layer boxes -->
  <g>
    <rect x="40" y="88" width="286" height="122" rx="4" fill="{INK2}" stroke="#ffffff" stroke-opacity=".14"/>
    <text x="60" y="116" fill="{GOLD}" font-family="{MONO}" font-size="9.5" letter-spacing="2.6">LAYER 01</text>
    <text x="60" y="145" fill="{PAPER}" font-family="{SERIF_STACK}" font-size="25">RF noise</text>
    <text x="60" y="170" fill="{DIM}" font-family="{MONO}" font-size="11">physical, non-deterministic</text>
    <text x="60" y="190" fill="{DIM}" font-family="{MONO}" font-size="11">atmospheric stochasticity</text>
  </g>
  <g>
    <rect x="406" y="88" width="286" height="122" rx="4" fill="{INK2}" stroke="#ffffff" stroke-opacity=".14"/>
    <text x="426" y="116" fill="{GOLD}" font-family="{MONO}" font-size="9.5" letter-spacing="2.6">LAYER 02</text>
    <text x="426" y="145" fill="{PAPER}" font-family="{SERIF_STACK}" font-size="25">Neural conditioning</text>
    <text x="426" y="170" fill="{DIM}" font-family="{MONO}" font-size="11">non-linear feature extraction</text>
    <text x="426" y="190" fill="{DIM}" font-family="{MONO}" font-size="11">proprietary architecture</text>
  </g>
  <g>
    <rect x="772" y="88" width="286" height="122" rx="4" fill="{INK2}" stroke="#ffffff" stroke-opacity=".14"/>
    <text x="792" y="116" fill="{GOLD}" font-family="{MONO}" font-size="9.5" letter-spacing="2.6">LAYER 03</text>
    <text x="792" y="145" fill="{PAPER}" font-family="{SERIF_STACK}" font-size="25">SHA-3 / SHAKE-256</text>
    <text x="792" y="170" fill="{DIM}" font-family="{MONO}" font-size="11">conditioning only — not the</text>
    <text x="792" y="190" fill="{DIM}" font-family="{MONO}" font-size="11">entropy source itself</text>
  </g>

  <!-- arrows -->
  <g stroke="{EMBER}" stroke-width="1.4" fill="none">
    <path d="M326 149H398"/><path d="M388 143l8 6-8 6"/>
    <path d="M692 149H764"/><path d="M754 143l8 6-8 6"/>
  </g>

  <!-- output -->
  <g font-family="{MONO}">
    <path d="M915 210v22" stroke="#ffffff" stroke-opacity=".16"/>
    <text x="40" y="252" fill="{PAPER}" font-size="12" letter-spacing=".6">OUTPUT</text>
    <text x="110" y="252" fill="{DIM}" font-size="12" letter-spacing=".6">v2_submission/data/v2_random_sample.bin · 11.16 MB · sha256 9e78d28e…3dacd1</text>
    <text x="40" y="274" fill="{DIM}" font-size="11" letter-spacing=".4">What is published is the OUTPUT and the test reports. The generator itself stays closed.</text>
  </g>
</svg>
'''


def badge(label, value, color, width_label=118, width_value=None, out="badge.svg"):
    fs = 11
    if width_value is None:
        width_value = int(len(value) * 6.35 + 22)
    w = width_label + width_value
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="26" viewBox="0 0 {w} 26" role="img" aria-label="{label}: {value}">
  <rect width="{w}" height="26" rx="3" fill="#22252e"/>
  <rect x="{width_label}" width="{width_value}" height="26" rx="3" fill="{color}"/>
  <rect x="{width_label}" width="6" height="26" fill="{color}"/>
  <text x="{width_label // 2}" y="17" fill="#c9ccd6" font-family="{MONO}" font-size="{fs}" text-anchor="middle">{label}</text>
  <text x="{width_label + width_value // 2}" y="17" fill="#0c0d11" font-family="{MONO}" font-size="{fs}" font-weight="bold" text-anchor="middle">{value}</text>
</svg>
'''
    (OUT / out).write_text(svg)


(OUT / "banner.svg").write_text(banner)
(OUT / "flow.svg").write_text(flow)

badge("NIST SP 800-22", "180/188 pass", "#79d18a", out="badge-sp800-22.svg")
badge("min-entropy", "0.9467 bit/bit", GOLD, out="badge-min-entropy.svg")
badge("sample", "11.16 MB ✓", "#8fb3d9", out="badge-sample.svg")
badge("tests", "CI ✓", "#b9a7d6", out="badge-ci.svg")

for f in sorted(OUT.iterdir()):
    print(f"{f.name:26s} {f.stat().st_size:>7,} B")
