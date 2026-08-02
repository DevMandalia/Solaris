# Nebula — an Obsidian theme

A cool, techy theme. Dark mode is cyan + violet on a blue-black canvas;
light mode is the same accents on cool paper. Interface and editor text
use **Sora**; code uses **JetBrains Mono**.

| Dark | Light |
|------|-------|
| ![Dark kanban](screenshots/dark-kanban.png) | ![Light kanban](screenshots/light-kanban.png) |
| ![Dark dashboard](screenshots/dark-dashboard.png) | ![Light dashboard](screenshots/light-dashboard.png) |

## Install (manual)

1. In your vault, open the folder:
   `<your-vault>/.obsidian/themes/Nebula/`
   (create the `Nebula` folder if it doesn't exist).
2. Copy **`manifest.json`** and **`theme.css`** into it.
3. In Obsidian: **Settings → Appearance → Themes** → select **Nebula**.
4. Toggle **Settings → Appearance → Base color scheme** between Dark and
   Light to see both modes.

## Customize

- **Accent / colors:** edit the CSS variables at the top of each
  `.theme-dark` / `.theme-light` block in `theme.css`.
- **Fonts:** change `--font-interface-theme`, `--font-text-theme`, and
  `--font-monospace-theme` near the top of `theme.css`.
- **Reading width:** edit `--file-line-width` (default `640px`).

## Notes

- Fonts load from Google Fonts via `@import`, so they need an internet
  connection. To go fully offline, download the font `.woff2` files into
  this folder and swap the `@import` for `@font-face` rules.
- Published at [DevMandalia/Nebula](https://github.com/DevMandalia/Nebula).
