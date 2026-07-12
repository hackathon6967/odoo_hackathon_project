import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { Leaf, Lock, Mail, ArrowRight } from 'lucide-react'
import toast from 'react-hot-toast'

export default function LoginPage() {
    const { login } = useAuth()
    const navigate = useNavigate()
    const [email, setEmail] = useState('admin@ecosphere.app')
    const [password, setPassword] = useState('admin123')
    const [loading, setLoading] = useState(false)

    async function submit(e: React.FormEvent) {
        e.preventDefault(); setLoading(true)
        try {
            await login(email, password); navigate('/dashboard')
        } catch (error: any) { toast.error(error.response?.data?.detail || 'Invalid credentials. Please try again.') } finally { setLoading(false) }
    }

    return (
        <main className="min-h-screen flex items-center justify-center relative overflow-hidden px-5 py-10 page-bg">
            <div className="absolute inset-0 opacity-30" style={{ background: 'repeating-conic-gradient(from 0deg at 50% 100%, rgba(21,153,223,.10) 0deg 1deg, transparent 1deg 12deg)' }} />
            <section className="relative z-10 w-full max-w-md deco-reveal">
                <div className="text-center mb-8">
                    <p className="text-[var(--gold)] text-[10px] tracking-[.45em] uppercase mb-4">The EcoSphere Society</p>
                    <div className="flex items-center gap-4 justify-center">
                        <span className="w-16 h-px bg-[var(--gold)]" />
                        <span className="w-2 h-2 bg-[var(--gold)] rotate-45" />
                        <span className="w-16 h-px bg-[var(--gold)]" />
                    </div>
                </div>
                <div className="glass p-8 sm:p-10">
                    <div className="flex flex-col items-center text-center mb-8">
                        <div className="deco-diamond w-14 h-14 border border-[var(--gold)] flex items-center justify-center mb-5">
                            <Leaf size={25} className="text-[var(--gold)]" />
                        </div>
                        <h1 className="text-[var(--champagne)] text-3xl uppercase tracking-[.19em]" style={{ fontFamily: 'var(--font-display)' }}>EcoSphere</h1>
                    </div>
                    <div className="text-center mb-7">
                        <h2 className="text-[var(--gold)] text-lg tracking-[.12em] uppercase" style={{ fontFamily: 'var(--font-display)' }}>Member Entrance</h2>
                        <p className="text-[var(--pewter)] text-sm mt-2">Sustainability, elevated.</p>
                    </div>
                    <form onSubmit={submit} className="space-y-6">
                        <label className="block">
                            <span className="text-[var(--gold)] text-[10px] tracking-[.2em] uppercase block mb-2">Email address</span>
                            <span className="relative block">
                                <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--pewter)]" />
                                <input className="input !pl-10" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
                            </span>
                        </label>
                        <label className="block">
                            <span className="text-[var(--gold)] text-[10px] tracking-[.2em] uppercase block mb-2">Password</span>
                            <span className="relative block">
                                <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--pewter)]" />
                                <input className="input !pl-10" type="password" value={password} onChange={e => setPassword(e.target.value)} required />
                            </span>
                        </label>
                        <button type="submit" disabled={loading} className="btn btn-primary w-full justify-center mt-2">
                            {loading ? 'Authenticating...' : <><span>Enter EcoSphere</span> <ArrowRight size={15} /></>}
                        </button>
                    </form>
                    <p className="text-center text-[var(--pewter)] text-[10px] tracking-wider mt-6">DEMO: ADMIN@ECOSPHERE.APP / ADMIN123</p>
                </div>
            </section>
        </main>
    )
}
