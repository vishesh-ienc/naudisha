import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/hooks/useTheme'
import { AppLayout } from '@/components/layout/AppLayout'
import { LandingPage } from '@/pages/LandingPage'
import { PlanVoyagePage } from '@/pages/PlanVoyagePage'
import { LiveRoutePage } from '@/pages/LiveRoutePage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<LandingPage />} />
              <Route path="/plan" element={<PlanVoyagePage />} />
              <Route path="/live-route" element={<LiveRoutePage />} />
              <Route path="/track" element={<Navigate to="/live-route" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

