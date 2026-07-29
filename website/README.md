# PCA9685 Fork — Explainer Site

A tiny Express app that serves a single static page explaining the PCA9685
no-solder wiring approach used in this fork. Purely informational — no build
step, no database, no framework beyond Express serving static files.

## Run locally

```bash
cd website
npm install
npm start
```

Then open http://localhost:3000

## Deploying

Since this is just static HTML/CSS in `public/`, you have two options:

- **Keep it as a Node app**: deploy `website/` as-is to Render, Railway, Fly.io,
  or any Node host. `npm start` runs `server.js`.
- **Skip Node entirely**: just publish the contents of `public/` directly to
  GitHub Pages, Netlify, or Vercel as a static site — the Express server is
  only there for local previewing/serving, the page itself has no server-side
  logic.
