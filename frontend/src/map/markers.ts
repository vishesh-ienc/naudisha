/**
 * Leaflet marker icons built as inline SVG `divIcon`s.
 *
 * Deliberately not Leaflet's default PNG markers: those resolve their image
 * paths relative to the CSS file and break under bundlers, and they cannot
 * follow the light/dark theme. These use the same CSS custom properties as the
 * rest of the app, so markers recolour with the theme for free.
 */

import L from 'leaflet'

function svgIcon(html: string, size: [number, number], anchor: [number, number], className = '') {
  return L.divIcon({
    html,
    className: `naudisha-marker ${className}`,
    iconSize: size,
    iconAnchor: anchor,
  })
}

const PIN = (fill: string, glyph: string) => `
<svg viewBox="0 0 32 42" width="32" height="42" xmlns="http://www.w3.org/2000/svg">
  <path d="M16 41C16 41 30 25.5 30 15.5A14 14 0 1 0 2 15.5C2 25.5 16 41 16 41Z"
        fill="${fill}" stroke="var(--card)" stroke-width="2.5" stroke-linejoin="round"/>
  <circle cx="16" cy="15.5" r="7" fill="var(--card)" opacity="0.95"/>
  ${glyph}
</svg>`

export const startIcon = svgIcon(
  PIN(
    'var(--success)',
    '<path d="M13 15.5 L15.5 18 L19.5 13" stroke="var(--success)" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  ),
  [32, 42],
  [16, 41],
)

export const destinationIcon = svgIcon(
  PIN(
    'var(--destructive)',
    '<path d="M12.5 11.5 V19.5 M12.5 12 H20 L18 14.5 L20 17 H12.5" stroke="var(--destructive)" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  ),
  [32, 42],
  [16, 41],
)

export const waypointIcon = svgIcon(
  `<svg viewBox="0 0 12 12" width="12" height="12" xmlns="http://www.w3.org/2000/svg">
     <circle cx="6" cy="6" r="4" fill="var(--card)" stroke="var(--route)" stroke-width="2"/>
   </svg>`,
  [12, 12],
  [6, 6],
)

/** Vessel marker — rotates to its course so heading is readable at a glance. */
export function shipIcon(headingDeg = 0, simulated = false) {
  const colour = simulated ? 'var(--accent)' : 'var(--primary)'
  return svgIcon(
    `<div style="transform: rotate(${headingDeg}deg); transform-origin: 50% 50%; width:38px; height:38px;">
       <svg viewBox="0 0 38 38" width="38" height="38" xmlns="http://www.w3.org/2000/svg">
         <circle cx="19" cy="19" r="17" fill="${colour}" opacity="0.16"/>
         <circle cx="19" cy="19" r="11" fill="var(--card)" stroke="${colour}" stroke-width="2"/>
         <path d="M19 9 L24 25 L19 21.5 L14 25 Z" fill="${colour}"/>
       </svg>
     </div>`,
    [38, 38],
    [19, 19],
    'naudisha-ship-marker',
  )
}

export function alertIcon(severity: 'critical' | 'warning' | 'info') {
  const colour =
    severity === 'critical' ? 'var(--destructive)' : severity === 'warning' ? 'var(--warning)' : 'var(--primary)'

  return svgIcon(
    `<div class="naudisha-alert-pulse">
       <svg viewBox="0 0 30 30" width="30" height="30" xmlns="http://www.w3.org/2000/svg">
         <circle cx="15" cy="15" r="13" fill="${colour}" opacity="0.2"/>
         <circle cx="15" cy="15" r="9" fill="var(--card)" stroke="${colour}" stroke-width="2"/>
         <path d="M15 10 V16" stroke="${colour}" stroke-width="2.2" stroke-linecap="round"/>
         <circle cx="15" cy="19.5" r="1.3" fill="${colour}"/>
       </svg>
     </div>`,
    [30, 30],
    [15, 15],
  )
}
