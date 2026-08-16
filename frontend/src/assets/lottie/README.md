# Lottie animations

Drop `.json` Lottie files here using these exact names — the app picks them up
automatically with no code change:

| Filename | Used for |
| :--- | :--- |
| `sailing-ship.json` | Landing hero, plan-voyage placeholder |
| `loading-waves.json` | Route calculation in progress |
| `success-check.json` | Route ready confirmation |
| `error-warning.json` | Hazard alerts, error states |
| `empty-ocean.json` | Empty states |

Until a file is present, `LottiePlayer` renders the hand-built SVG fallback in
`src/components/ui/ShipAnimation.tsx`. Those fallbacks are complete and themed —
the interface does not look unfinished without these files.

**Keep the files local.** Do not hotlink LottieFiles' CDN: a venue with poor wifi
would leave animation slots hanging at exactly the wrong moment.

Free sources: lottiefiles.com/featured (filter to the free licence), or
lordicon.com/icons (free tier). Prefer files under ~100 KB.
