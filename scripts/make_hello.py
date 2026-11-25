#!/usr/bin/env python3
"""Build assets/hello.svg: a looping "typing" header for the README.

Each phrase is typed one character at a time. The newest characters are drawn
bold and brighter, a space shows a small "SP" key box, Enter shows a "↵" box,
then the phrase slides up and fades out before the next one starts.

    python scripts/make_hello.py
"""
from pathlib import Path
from xml.sax.saxutils import escape

PHRASES = ["Hello!", "Welcome to my GitHub!"]

W, H = 760, 96
SIZE = 40            # font size
ADV = 24             # monospace advance used to place every character
BASE = "#238636"     # settled text (dark green)
FRESH = "#2ea043"    # just-typed text
KEY = "#1a5c2a"      # key boxes
FONT = "SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace"

START_GAP = 0.35     # seconds before a phrase starts typing
STEP = 0.16          # seconds per character
FRESH_FOR = 0.45     # how long a character stays highlighted
ENTER_AFTER = 0.45   # pause before the ↵ box
ENTER_FOR = 0.55
FADE = 0.6           # slide-up / fade duration
END_GAP = 0.3

OUT = Path(__file__).resolve().parent.parent / "assets" / "hello.svg"


def build() -> str:
    # timeline in seconds
    plan = []
    t = 0.0
    for phrase in PHRASES:
        t += START_GAP
        typed = [t + i * STEP for i in range(len(phrase))]
        enter = typed[-1] + ENTER_AFTER
        fade_start = enter + ENTER_FOR
        plan.append((phrase, typed, enter, fade_start))
        t = fade_start + FADE + END_GAP
    total = t

    def pct(sec: float) -> str:
        return f"{100 * sec / total:.3f}%"

    css = [
        f"text{{font-family:{FONT};font-size:{SIZE}px;}}",
        f".k text{{font-size:11px;fill:{KEY};font-weight:700}}",
    ]
    body = []
    n = 0
    for p, (phrase, typed, enter, fade_start) in enumerate(plan):
        x0 = (W - len(phrase) * ADV) / 2
        y = H / 2 + SIZE * 0.35
        gid = f"p{p}"
        css.append(
            f"@keyframes {gid}{{0%{{opacity:1;transform:translateY(0)}}"
            f"{pct(fade_start)}{{opacity:1;transform:translateY(0)}}"
            f"{pct(fade_start + FADE)}{{opacity:0;transform:translateY(-16px)}}"
            f"100%{{opacity:0;transform:translateY(-16px)}}}}"
            f"#{gid}{{animation:{gid} {total:.2f}s linear infinite}}"
        )
        body.append(f'<g id="{gid}">')
        for i, ch in enumerate(phrase):
            a, b = typed[i], typed[i] + FRESH_FOR
            cx = x0 + i * ADV
            cid = f"c{n}"
            n += 1
            if ch == " ":
                # "SP" key box, visible only while the space is fresh
                css.append(
                    f"@keyframes {cid}{{0%{{opacity:0}}{pct(a - 0.001)}{{opacity:0}}{pct(a)}{{opacity:1}}"
                    f"{pct(b)}{{opacity:1}}{pct(b + 0.001)}{{opacity:0}}100%{{opacity:0}}}}"
                    f"#{cid}{{animation:{cid} {total:.2f}s step-end infinite}}"
                )
                body.append(
                    f'<g id="{cid}" class="k"><rect x="{cx + 3:.1f}" y="{y - 28:.1f}" width="18" height="28" '
                    f'rx="2" fill="none" stroke="{KEY}" stroke-width="1.5"/>'
                    f'<text x="{cx + 12:.1f}" y="{y - 10:.1f}" text-anchor="middle">SP</text></g>'
                )
                continue
            css.append(
                f"@keyframes {cid}{{0%{{opacity:0}}{pct(a - 0.001)}{{opacity:0}}"
                f"{pct(a)}{{opacity:1;fill:{FRESH};font-weight:700}}"
                f"{pct(b)}{{opacity:1;fill:{FRESH};font-weight:700}}"
                f"{pct(b + 0.001)}{{opacity:1;fill:{BASE};font-weight:400}}"
                f"100%{{opacity:1;fill:{BASE};font-weight:400}}}}"
                f"#{cid}{{animation:{cid} {total:.2f}s step-end infinite}}"
            )
            body.append(f'<text id="{cid}" x="{cx:.1f}" y="{y:.1f}" fill="{BASE}" opacity="0">{escape(ch)}</text>')
        # ↵ key box after the last character
        ex = x0 + len(phrase) * ADV
        cid = f"e{p}"
        css.append(
            f"@keyframes {cid}{{0%{{opacity:0}}{pct(enter - 0.001)}{{opacity:0}}{pct(enter)}{{opacity:1}}"
            f"{pct(fade_start)}{{opacity:1}}{pct(fade_start + 0.001)}{{opacity:0}}100%{{opacity:0}}}}"
            f"#{cid}{{animation:{cid} {total:.2f}s step-end infinite}}"
        )
        body.append(
            f'<g id="{cid}" class="k"><rect x="{ex + 4:.1f}" y="{y - 28:.1f}" width="20" height="28" rx="2" '
            f'fill="none" stroke="{KEY}" stroke-width="1.5"/>'
            f'<text x="{ex + 14:.1f}" y="{y - 9:.1f}" text-anchor="middle" style="font-size:14px">↵</text></g>'
        )
        body.append("</g>")

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{escape(" ".join(PHRASES))}">'
        f"<style>{''.join(css)}</style>" + "".join(body) + "</svg>\n"
    )


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT}")
