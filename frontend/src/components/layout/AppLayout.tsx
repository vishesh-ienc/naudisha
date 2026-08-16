import { Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Header } from './Header'
import { DataSourceConsole } from '@/components/devtools/DataSourceConsole'

export function AppLayout() {
  const location = useLocation()

  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <Header />

      <main className="flex-1">
        {/*
          Keyed on pathname so each route animates in. `mode="wait"` prevents the
          outgoing and incoming pages overlapping, which otherwise causes a
          visible height jump on routes of differing length.
        */}
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="h-full"
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>

      <DataSourceConsole />
    </div>
  )
}
