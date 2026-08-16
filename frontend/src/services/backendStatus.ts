/**
 * Re-exports for backend availability, kept separate from `resilientApi` so that
 * React hooks can import mode-awareness without pulling the whole service layer
 * into a component's dependency graph.
 */

import { useSyncExternalStore } from 'react'
import { getApiMode, subscribeToMode, type ApiMode } from './resilientApi'

export { probeBackend, type BackendHealth } from './resilientApi'

export function useApiModeAware(): ApiMode {
  return useSyncExternalStore(subscribeToMode, getApiMode, getApiMode)
}
