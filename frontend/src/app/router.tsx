import { lazy, Suspense } from 'react'
import { createBrowserRouter } from 'react-router-dom'
import { AppLayout } from '../layouts/AppLayout'
import { LoadingState } from '../components/common/States'

const Overview = lazy(() => import('../pages/OverviewPage'))
const Live = lazy(() => import('../pages/LiveMonitoringPage'))

const WorkerDetail = lazy(() => import('../pages/WorkerDetailPage'))
const Workers = lazy(() => import('../pages/WorkersPage'))
const Settings = lazy(() => import('../pages/SettingsPage'))

const withSuspense = (element: React.ReactNode) => <Suspense fallback={<LoadingState label="Membuka modul..." />}>{element}</Suspense>

export const router = createBrowserRouter([{
  path: '/', element: <AppLayout />, children: [
    { index: true, element: withSuspense(<Overview />) },
    { path: 'live', element: withSuspense(<Live />) },
    { path: 'workers', element: withSuspense(<Workers />) },
    { path: 'workers/:workerId', element: withSuspense(<WorkerDetail />) },
    { path: 'settings', element: withSuspense(<Settings />) },
  ],
}])
