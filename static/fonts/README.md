# Self-hosted fonts

Drop licensed webfont files here and they take effect with no code change —
`@font-face` rules in `styles.css` already point at these filenames, and
"Capsule Sans" is already first in the `--sans` stack.

## Capsule Sans

Capsule Sans is a **commercial** typeface. It is not on Google Fonts (that URL
returns 400), not on Fontsource, and not on npm — all checked. Using it needs a
purchased *webfont* licence, which is a different licence from a desktop one,
and is usually priced by monthly pageviews.

Buy it, then save the files here with exactly these names:

    CapsuleSans-Regular.woff2     (400)
    CapsuleSans-Medium.woff2      (500)
    CapsuleSans-SemiBold.woff2    (600)
    CapsuleSans-Bold.woff2        (700)

A variable font is better if the licence includes one — save it as:

    CapsuleSans-Variable.woff2

and uncomment the variable `@font-face` block in `styles.css`, which replaces
all four static faces with one file.

Nothing breaks while the files are absent. A `@font-face` whose `src` 404s is
ignored by the browser and the next family in `--sans` is used, so the site
renders in Inter until the day the files appear.

## Why not just link it from a CDN

There is no licensed CDN for it. Copies float around on unofficial mirrors;
serving one from a public domain would be redistributing a commercial font
without a licence.
