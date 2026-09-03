# Self-hosted fonts

Empty by default. Drop licensed `.woff2` files here and add the family to the
front of `--sans` in `styles.css`.

## What the terminal uses now

**Switzer**, from Fontshare, free for commercial use, loaded as a single
variable file. **Inter** sits behind it as the fallback, from a different CDN so
one outage cannot remove both.

Both are neo-grotesques, which is the genre the comparable products use.
Verified by loading each site and reading the fonts it actually serves:

| Product | Typeface | Available? |
|---|---|---|
| Robinhood | "Capsule Sans", a custom cut of Maison Neue | No, commissioned |
| Kalshi | "Kalshi Sans" in 3 widths, plus Graphik for display | No, proprietary |
| Polymarket | Inter | Yes, free |

## Maison Neue

The `@font-face` rules in `styles.css` name Maison Neue and expect:

    MaisonNeue-Book.woff2       (400)
    MaisonNeue-Medium.woff2     (500)
    MaisonNeue-Demi.woff2       (600)
    MaisonNeue-Bold.woff2       (700)

Then put `"Maison Neue"` ahead of `"Switzer"` in `--sans`.

Maison Neue is licensable from Milieu Grotesque, and a **webfont** licence is a
different purchase from a desktop one, usually priced by monthly pageviews.

## Why not Capsule Sans

Robinhood's Capsule Sans is a custom cut of Maison Neue made for Robinhood. It
is not sold, so there is no licence to buy and nothing to drop in here. Maison
Neue is the drawing underneath it and is the closest a licence can get.

An earlier version of this file described Capsule as a commercial display face
sold for about $25. That was a different typeface of the same name, by Dave
Rowland: reverse-stress, essentially all-caps, and genuinely unsuited to
dense tables. It is unrelated to Robinhood's.
