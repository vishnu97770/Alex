import { createBrowserRouter } from 'react-router-dom'
import Layout from '../components/Layout/Layout'
import CallPage from '../pages/CallPage'
import ChatPage from '../pages/ChatPage'
import RolePage from '../pages/RolePage'
import SettingsPage from '../pages/SettingsPage'

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <RolePage /> },
      { path: '/call', element: <CallPage /> },
      { path: '/chats/:id', element: <ChatPage /> },
      { path: '/settings', element: <SettingsPage /> },
    ],
  },
])
