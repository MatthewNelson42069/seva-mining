import { Outlet } from 'react-router-dom'
import { TabNav } from './TabNav'

export function TabbedDashboard() {
  return (
    <>
      <TabNav />
      <Outlet />
    </>
  )
}
