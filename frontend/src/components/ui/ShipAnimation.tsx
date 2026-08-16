/**
 * Hand-built SVG animations used as Lottie fallbacks.
 *
 * These are not placeholders to be replaced — they are complete, themed, and
 * dependency-free, so the app looks finished with an empty `assets/lottie/`
 * folder. Dropping in a Lottie file upgrades the visual; it does not fix a gap.
 */

import { cn } from '@/lib/utils'

/** A vessel riding a swell. Used for loading states and the landing hero. */
export function SailingShip({ className, size = 96 }: { className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 120 100"
      width={size}
      height={size}
      className={cn('overflow-visible', className)}
      role="img"
      aria-label="Sailing vessel animation"
    >
      <defs>
        <linearGradient id="hullGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary)" />
          <stop offset="100%" stopColor="var(--ocean-deep)" />
        </linearGradient>
        <linearGradient id="waveGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.25" />
          <stop offset="50%" stopColor="var(--accent)" stopOpacity="0.6" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.25" />
        </linearGradient>
      </defs>

      {/* Vessel — rocks about its waterline rather than its centre, which is
          what makes the motion read as buoyancy instead of a spin. */}
      <g>
        <animateTransform
          attributeName="transform"
          type="rotate"
          values="-4 60 70; 4 60 70; -4 60 70"
          dur="3.6s"
          repeatCount="indefinite"
          calcMode="spline"
          keySplines="0.45 0 0.55 1; 0.45 0 0.55 1"
        />
        <animateTransform
          attributeName="transform"
          type="translate"
          additive="sum"
          values="0 0; 0 -3.5; 0 0"
          dur="2.4s"
          repeatCount="indefinite"
          calcMode="spline"
          keySplines="0.45 0 0.55 1; 0.45 0 0.55 1"
        />

        <path d="M34 66 L86 66 L78 78 L42 78 Z" fill="url(#hullGrad)" />
        <rect x="56" y="30" width="2.5" height="36" rx="1" fill="var(--foreground)" opacity="0.75" />
        <path d="M59 33 L78 58 L59 58 Z" fill="var(--accent)" opacity="0.9" />
        <path d="M54 36 L38 58 L54 58 Z" fill="var(--primary)" opacity="0.7" />
      </g>

      {/* Two swells at different rates — the offset is what stops it looking
          like a single rigid shape sliding back and forth. */}
      <path
        d="M4 82 Q 22 76, 40 82 T 76 82 T 112 82"
        stroke="url(#waveGrad)"
        strokeWidth="2.5"
        fill="none"
        strokeLinecap="round"
      >
        <animateTransform
          attributeName="transform"
          type="translate"
          values="0 0; -36 0"
          dur="3s"
          repeatCount="indefinite"
        />
      </path>
      <path
        d="M4 89 Q 22 84, 40 89 T 76 89 T 112 89"
        stroke="url(#waveGrad)"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
        opacity="0.55"
      >
        <animateTransform
          attributeName="transform"
          type="translate"
          values="-36 0; 0 0"
          dur="4.4s"
          repeatCount="indefinite"
        />
      </path>
    </svg>
  )
}

/** Compact rolling-wave spinner for inline loading. */
export function WaveLoader({ className, size = 48 }: { className?: string; size?: number }) {
  return (
    <svg viewBox="0 0 64 24" width={size} height={size * 0.375} className={className} role="status" aria-label="Loading">
      {[0, 1, 2, 3, 4].map((i) => (
        <circle key={i} cx={8 + i * 12} cy="12" r="3.5" fill="var(--primary)">
          <animate
            attributeName="cy"
            values="12; 6; 12"
            dur="1.2s"
            begin={`${i * 0.12}s`}
            repeatCount="indefinite"
            calcMode="spline"
            keySplines="0.4 0 0.6 1; 0.4 0 0.6 1"
          />
          <animate
            attributeName="opacity"
            values="0.45; 1; 0.45"
            dur="1.2s"
            begin={`${i * 0.12}s`}
            repeatCount="indefinite"
          />
        </circle>
      ))}
    </svg>
  )
}

/** Radar sweep — used while awaiting live position or route data. */
export function RadarSweep({ className, size = 64 }: { className?: string; size?: number }) {
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} className={className} role="status" aria-label="Scanning">
      <circle cx="50" cy="50" r="44" fill="none" stroke="var(--border)" strokeWidth="1.5" />
      <circle cx="50" cy="50" r="28" fill="none" stroke="var(--border)" strokeWidth="1" opacity="0.6" />
      <circle cx="50" cy="50" r="12" fill="none" stroke="var(--border)" strokeWidth="1" opacity="0.4" />
      <g>
        <animateTransform
          attributeName="transform"
          type="rotate"
          values="0 50 50; 360 50 50"
          dur="2.6s"
          repeatCount="indefinite"
        />
        <path d="M50 50 L50 6 A44 44 0 0 1 88 32 Z" fill="var(--accent)" opacity="0.28" />
        <line x1="50" y1="50" x2="50" y2="6" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
      </g>
      <circle cx="50" cy="50" r="3" fill="var(--accent)" />
    </svg>
  )
}
