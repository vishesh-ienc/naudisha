/**
 * Leaflet marker icons built as theme-aware SVG `divIcon`s.
 *
 * All markers use CSS custom properties to seamlessly blend with the dark
 * maritime aesthetic, including animated wind and current vectors.
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

const PIN = (fill: string, glyph: string, stroke = 'var(--card)') => `
<svg viewBox="0 0 32 42" width="32" height="42" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="pin-shadow" x="-20%" y="-10%" width="140%" height="130%">
      <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000" flood-opacity="0.45"/>
    </filter>
  </defs>
  <path d="M16 41C16 41 30 25.5 30 15.5A14 14 0 1 0 2 15.5C2 25.5 16 41 16 41Z"
        fill="${fill}" stroke="${stroke}" stroke-width="2.5" stroke-linejoin="round" filter="url(#pin-shadow)"/>
  <circle cx="16" cy="15.5" r="7" fill="var(--card)" opacity="0.95"/>
  ${glyph}
</svg>`

export const startIcon = svgIcon(
  PIN(
    '#10b981',
    '<path d="M13 15.5 L15.5 18 L19.5 13" stroke="#10b981" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  ),
  [32, 42],
  [16, 41],
)

export const destinationIcon = svgIcon(
  PIN(
    '#f43f5e',
    '<path d="M12.5 11.5 V19.5 M12.5 12 H20 L18 14.5 L20 17 H12.5" stroke="#f43f5e" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  ),
  [32, 42],
  [16, 41],
)

export const waypointIcon = svgIcon(
  `<svg viewBox="0 0 14 14" width="14" height="14" xmlns="http://www.w3.org/2000/svg">
     <circle cx="7" cy="7" r="5.5" fill="var(--card)" stroke="#10b981" stroke-width="2.5"/>
     <circle cx="7" cy="7" r="2.5" fill="#10b981"/>
   </svg>`,
  [14, 14],
  [7, 7],
)

/** Real boat marker — rotating vessel with pulsing AIS beacon aura */
export function shipIcon(headingDeg = 0, isSimulated = false) {
  const colour = isSimulated ? '#f59e0b' : '#06b6d4'
  const glow = isSimulated ? 'rgba(245, 158, 11, 0.55)' : 'rgba(6, 182, 212, 0.65)'

  return svgIcon(
    `<div style="width:48px; height:48px; position:relative; display:flex; align-items:center; justify-content:center;">
       <!-- Pulsing AIS beacon ring -->
       <div style="position:absolute; width:44px; height:44px; border-radius:50%; border:2px solid ${colour}; opacity:0.6; animation:pulse-ring 2.2s cubic-bezier(0.24,0.6,0.35,1) infinite;"></div>
       <!-- Rotating Vessel Body -->
       <div style="transform: rotate(${headingDeg}deg); transform-origin: 50% 50%; width:44px; height:44px; filter: drop-shadow(0 0 8px ${glow});">
         <svg viewBox="0 0 44 44" width="44" height="44" xmlns="http://www.w3.org/2000/svg">
           <circle cx="22" cy="22" r="14" fill="#0f172a" stroke="${colour}" stroke-width="2.5"/>
           <!-- Vessel bow arrow -->
           <path d="M22 9 L28 27 L22 23 L16 27 Z" fill="${colour}"/>
           <circle cx="22" cy="22" r="3" fill="#ffffff"/>
         </svg>
       </div>
     </div>`,
    [48, 48],
    [24, 24],
    'naudisha-ship-marker',
  )
}

/** Animated Directional Wind Vector marker with speed label */
export function windVectorIcon(directionDeg = 0, speedKn = 0) {
  return svgIcon(
    `<div class="animate-wind-flow" style="display:flex; flex-direction:column; align-items:center; width:38px; height:38px;" title="Wind: ${Math.round(speedKn)} kn from ${Math.round(directionDeg)}°">
       <div style="transform: rotate(${directionDeg}deg); transform-origin: 50% 50%; width:26px; height:26px;">
         <svg viewBox="0 0 26 26" width="26" height="26" xmlns="http://www.w3.org/2000/svg">
           <circle cx="13" cy="13" r="11" fill="#0284c7" fill-opacity="0.18"/>
           <path d="M13 21 V5 M13 5 L8 10 M13 5 L18 10" stroke="#38bdf8" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
         </svg>
       </div>
       <span style="background:rgba(15,23,42,0.85); color:#7dd3fc; border:1px solid rgba(56,189,248,0.4); border-radius:4px; font-family:monospace; font-size:8px; font-weight:bold; padding:0 3px; margin-top:-2px; white-space:nowrap;">
         ${Math.round(speedKn)}k
       </span>
     </div>`,
    [38, 38],
    [19, 19],
  )
}

/** Animated Ocean Current Vector marker with assist/oppose indicator */
export function currentVectorIcon(directionDeg = 0, speedKn = 0, isAssist = true) {
  const color = isAssist ? '#10b981' : '#f59e0b'
  const bgBadge = isAssist ? 'rgba(16,185,129,0.2)' : 'rgba(245,158,11,0.2)'
  const textBadge = isAssist ? '#34d399' : '#fbbf24'

  return svgIcon(
    `<div class="animate-current-drift" style="display:flex; flex-direction:column; align-items:center; width:36px; height:36px;" title="Current: ${speedKn.toFixed(1)} kn ${isAssist ? '(Assisting)' : '(Opposing)'}">
       <div style="transform: rotate(${directionDeg}deg); transform-origin: 50% 50%; width:24px; height:24px;">
         <svg viewBox="0 0 24 24" width="24" height="24" xmlns="http://www.w3.org/2000/svg">
           <circle cx="12" cy="12" r="10" fill="${color}" fill-opacity="0.2"/>
           <path d="M12 18 V6 M12 6 L8 10 M12 6 L16 10" stroke="${color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
         </svg>
       </div>
       <span style="background:rgba(15,23,42,0.85); color:${textBadge}; border:1px solid ${bgBadge}; border-radius:4px; font-family:monospace; font-size:8px; font-weight:bold; padding:0 3px; margin-top:-2px; white-space:nowrap;">
         ${speedKn.toFixed(1)}kn
       </span>
     </div>`,
    [36, 36],
    [18, 18],
  )
}

export function alertIcon(severity: 'critical' | 'warning' | 'info') {
  const colour =
    severity === 'critical' ? '#f43f5e' : severity === 'warning' ? '#f59e0b' : '#06b6d4'

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
