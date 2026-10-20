import { createBrowserRouter, Navigate } from 'react-router-dom'
import AppLayout from '../components/AppLayout/AppLayout'
import RequireAuth from '../components/Auth/RequireAuth'
import AgentCreater from '../pages/AgentCreater'
import AgentUpdater from '../pages/AgentUpdater'
import CallPage from '../pages/CallPage'
import ChatPage from '../pages/ChatPage'
import CheckinPage from '../pages/CheckinPage'
import Landing from '../pages/Landing'
import Dashboard from '../pages/Dashboard'
import MyAgents from '../pages/MyAgents'
import MyManager from '../pages/MyManager'
import Payment from '../pages/Payment'
import ProfilePage from '../pages/ProfilePage'
import Settings from '../pages/Settings'

export const routes = [
    { path: '/', element: <Navigate to="/home" replace /> },
    { path: '/home', element: <Landing /> },
    { path: '/checkin', element: <CheckinPage /> },
    {
        element: <RequireAuth />,
        children: [
            {
                element: <AppLayout />,
                children: [
                    { path: '/dashboard/:uid', element: <Dashboard /> },
                    { path: '/agents/:uid', element: <MyAgents /> },
                    {
                        path: '/manager/:uid',
                        element: <MyManager />,
                        children: [
                            { index: true, element: <CallPage /> },
                            { path: 'chats/:id', element: <ChatPage /> },
                        ],
                    },
                    { path: '/profile/:uid', element: <ProfilePage /> },
                    { path: '/settings/:uid', element: <Settings /> },
                ],
            },
            { path: '/create_agent/:uid', element: <AgentCreater /> },
            { path: '/create_agent/:uid/:aid', element: <Payment /> },
            { path: '/agents/:uid/update/:aid', element: <AgentUpdater /> },
        ],
    },
    { path: '*', element: <Navigate to="/home" replace /> },
]

export const router = createBrowserRouter(routes)
