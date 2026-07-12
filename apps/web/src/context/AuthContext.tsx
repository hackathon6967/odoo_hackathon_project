import React, { createContext, useContext, useState, useEffect } from 'react'
import api from '../api/client'

interface AuthState {
    token: string | null
    user: { id: string; full_name: string; role: string; xp: number; points: number; department_id: string | null } | null
    login: (email: string, password: string) => Promise<void>
    establishSession: (data: { access_token: string; user_id: string; full_name: string; role: string }) => void
    refreshUser: () => Promise<void>
    logout: () => void
}

const AuthContext = createContext<AuthState>({} as AuthState)

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
    const [user, setUser] = useState<AuthState['user']>(null)

    useEffect(() => {
        if (token) {
            api.defaults.headers.common['Authorization'] = `Bearer ${token}`
            api.get('/core/auth/me').then(r => setUser(r.data)).catch(() => logout())
        }
    }, [token])

    function establishSession(data: { access_token: string; user_id: string; full_name: string; role: string }) {
        localStorage.setItem('token', data.access_token)
        api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`
        setToken(data.access_token)
        setUser({ id: data.user_id, full_name: data.full_name, role: data.role, xp: 0, points: 0, department_id: null })
    }
    async function refreshUser() {
        if (!localStorage.getItem('token')) return
        const { data } = await api.get('/core/auth/me')
        setUser(data)
    }

    async function login(email: string, password: string) {
        const form = new FormData()
        form.append('username', email)
        form.append('password', password)
        const { data } = await api.post('/core/auth/login', form, { headers: { 'Content-Type': 'multipart/form-data' } })
        establishSession(data)
    }

    function logout() {
        localStorage.removeItem('token')
        delete api.defaults.headers.common['Authorization']
        setToken(null)
        setUser(null)
    }

    return <AuthContext.Provider value={{ token, user, login, establishSession, refreshUser, logout }}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
