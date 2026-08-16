/**
 * Lottie playback with a guaranteed visual fallback.
 *
 * Animation JSON files live in `src/assets/lottie/` and are loaded lazily. If a
 * file is absent — which it is until someone downloads one from LottieFiles —
 * the `fallback` renders instead. Nothing ever shows an empty box.
 *
 * Assets are bundled locally rather than hotlinked from a CDN on purpose: a
 * demo must survive a venue with no usable wifi, and a CDN request that hangs
 * would stall the animation slot at exactly the wrong moment.
 *
 * To add one: download the .json into `src/assets/lottie/<name>.json` and add
 * the entry to LOTTIE_SOURCES below. The component picks it up with no other
 * change.
 */

import { Suspense, lazy, useEffect, useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

// lottie-react v3 exports `Lottie` as a named export and takes the animation via
// `src`. React.lazy requires a module with a `default`, hence the remap.
const Lottie = lazy(() => import('lottie-react').then((m) => ({ default: m.Lottie })))

export type LottieName = 'sailing-ship' | 'loading-waves' | 'success-check' | 'error-warning' | 'empty-ocean'

/**
 * Discovers whatever animation files are actually present at build time.
 *
 * `import.meta.glob` is used rather than explicit `import()` calls because a
 * static import of a file that does not exist is a *build error* in Vite. Glob
 * simply yields no key for an absent file, so the folder can be empty, partially
 * filled, or complete — the app builds and runs identically either way.
 */
const LOTTIE_MODULES = import.meta.glob<{ default: unknown }>('@/assets/lottie/*.json')

function loaderFor(name: LottieName): (() => Promise<{ default: unknown }>) | undefined {
  const match = Object.keys(LOTTIE_MODULES).find((path) => path.endsWith(`/${name}.json`))
  return match ? LOTTIE_MODULES[match] : undefined
}

interface LottiePlayerProps {
  name: LottieName
  fallback: ReactNode
  className?: string
  loop?: boolean
  autoplay?: boolean
}

export function LottiePlayer({
  name,
  fallback,
  className,
  loop = true,
  autoplay = true,
}: LottiePlayerProps) {
  const [animationData, setAnimationData] = useState<unknown>(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = loaderFor(name)

    if (!load) {
      // No such file in assets/lottie — the normal state until someone adds one.
      setUnavailable(true)
      return
    }

    setUnavailable(false)
    load()
      .then((mod) => {
        if (!cancelled) setAnimationData(mod.default)
      })
      .catch(() => {
        if (!cancelled) setUnavailable(true)
      })

    return () => {
      cancelled = true
    }
  }, [name])

  // Respect reduced-motion: a static fallback is the accessible choice.
  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  if (unavailable || !animationData || prefersReducedMotion) {
    return <div className={cn('flex items-center justify-center', className)}>{fallback}</div>
  }

  return (
    <Suspense fallback={<div className={cn('flex items-center justify-center', className)}>{fallback}</div>}>
      <Lottie
        src={animationData as object}
        loop={loop}
        autoplay={autoplay}
        className={className}
      />
    </Suspense>
  )
}
