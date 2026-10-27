import { lazy, Suspense } from 'react'
import { createBrowserRouter, useRouteError } from 'react-router-dom'
import { AppLayout } from '../layouts/AppLayout'
import { ErrorState, LoadingState } from '../components/common/States'

const Overview = lazy(() => import('../pages/OverviewPage'))
const Live = lazy(() => import('../pages/LiveMonitoringPage'))

const WorkerDetail = lazy(() => import('../pages/WorkerDetailPage'))
const Workers = lazy(() => import('../pages/WorkersPage'))
const NearMisses = lazy(() => import('../pages/NearMissesPage'))
const Settings = lazy(() => import('../pages/SettingsPage'))

const withSuspense = (element: React.ReactNode) => <Suspense fallback={<LoadingState label="Membuka modul..." />}>{element}</Suspense>

function RouterErrorBoundary() {
  const error = useRouteError()
  console.error('Route error boundary caught:', error)
  return (
    <div style={{ padding: '2rem', display: 'flex', justifyContent: 'center' }}>
      <ErrorState retry={() => window.location.reload()} />
    </div>
  )
}

export const router = createBrowserRouter([{
  path: '/',
  element: <AppLayout />,
  errorElement: <RouterErrorBoundary />,
  children: [
    { index: true, element: withSuspense(<Overview />) },
    { path: 'live', element: withSuspense(<Live />) },
    { path: 'near-misses', element: withSuspense(<NearMisses />) },
    { path: 'workers', element: withSuspense(<Workers />) },
    { path: 'workers/:workerId', element: withSuspense(<WorkerDetail />) },
    { path: 'settings', element: withSuspense(<Settings />) },
  ],
}])
