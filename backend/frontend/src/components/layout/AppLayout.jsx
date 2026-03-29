import React from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function AppLayout() {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar />
      <main style={{
        marginLeft: 'var(--sidebar-width)',
        flex: 1,
        minHeight: '100vh',
        background: 'var(--color-base)',
        padding: '32px',
        overflowY: 'auto',
      }}>
        <Outlet />
      </main>
    </div>
  )
}