import { useEffect, useState } from 'react'
import { Settings, Sliders, Bell, Save } from 'lucide-react'
import api from '../../api/client'
import toast from 'react-hot-toast'
import { useAuth } from '../../context/AuthContext'

export default function SettingsPage() {
    const { user } = useAuth()
    const [config, setConfig] = useState({
        weight_environmental: 0.40, weight_social: 0.30, weight_governance: 0.30,
        auto_emission_calc: true, evidence_required: true, badge_auto_award: true,
    })
    const [saving, setSaving] = useState(false)

    useEffect(() => {
        api.get('/core/settings/esg-config').then(r => setConfig(r.data)).catch(() => toast.error('Could not load settings'))
    }, [])

    const totalWeight = config.weight_environmental + config.weight_social + config.weight_governance

    async function saveConfig() {
        if (Math.abs(totalWeight - 1.0) > 0.01) {
            toast.error('Weights must sum to 1.0')
            return
        }
        setSaving(true)
        try {
            await api.put('/core/settings/esg-config', config)
            toast.success('Settings saved!')
        } catch { toast.error('Failed to save settings') } finally { setSaving(false) }
    }

    return (
        <div className="min-h-screen p-8 page-bg">
            <div className="max-w-2xl mx-auto">
                {/* Header */}
                <div className="flex items-center gap-3 mb-8">
                    <div className="w-10 h-10 rounded-xl bg-slate-700 flex items-center justify-center">
                        <Settings size={20} className="text-slate-300" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>Settings</h1>
                        <p className="text-slate-400 text-sm">ESG scoring configuration</p>
                    </div>
                </div>

                {/* Scoring Weights */}
                <div className="glass rounded-2xl p-6 mb-4">
                    <h2 className="text-white font-semibold mb-1 flex items-center gap-2">
                        <Sliders size={16} className="text-indigo-400" /> Scoring Weights
                    </h2>
                    <p className="text-slate-500 text-sm mb-6">Must sum to 1.0 · Currently: {totalWeight.toFixed(2)}</p>

                    {[
                        { key: 'weight_environmental', label: 'Environmental', color: '#1599df', emoji: '🌿' },
                        { key: 'weight_social', label: 'Social', color: '#1599df', emoji: '👥' },
                        { key: 'weight_governance', label: 'Governance', color: '#1599df', emoji: '🛡️' },
                    ].map(({ key, label, color, emoji }) => (
                        <div key={key} className="mb-5">
                            <div className="flex justify-between mb-2">
                                <label className="text-slate-300 text-sm">{emoji} {label}</label>
                                <span className="font-bold" style={{ color }}>{(config[key as keyof typeof config] as number * 100).toFixed(0)}%</span>
                            </div>
                            <input type="range" min={0} max={1} step={0.05}
                                value={config[key as keyof typeof config] as number}
                                onChange={e => setConfig(c => ({ ...c, [key]: parseFloat(e.target.value) }))}
                                className="w-full h-2 rounded-full appearance-none cursor-pointer"
                                style={{ accentColor: color }} />
                            <div className="h-2 rounded-full mt-1.5"
                                style={{
                                    background: `linear-gradient(90deg, ${color}, transparent)`,
                                    width: `${(config[key as keyof typeof config] as number) * 100}%`, transition: 'width 0.2s'
                                }} />
                        </div>
                    ))}

                    {Math.abs(totalWeight - 1.0) > 0.01 && (
                        <div className="bg-red-900/30 border border-red-500/30 rounded-xl p-3 mb-4">
                            <p className="text-red-400 text-sm">⚠️ Weights must sum to exactly 1.0 (currently {totalWeight.toFixed(2)})</p>
                        </div>
                    )}

                    {user?.role !== 'admin' && user?.role !== 'manager' && (
                        <div className="bg-amber-900/30 border border-amber-500/30 rounded-xl p-3 mb-4">
                            <p className="text-amber-400 text-sm">⚠️ Read-Only: Settings can only be modified by managers and admins.</p>
                        </div>
                    )}
                </div>

                {/* Feature flags */}
                <div className="glass rounded-2xl p-6 mb-4">
                    <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
                        <Bell size={16} className="text-amber-400" /> Feature Flags
                    </h2>
                    {[
                        { key: 'auto_emission_calc', label: 'Auto Emission Calculation', desc: 'Automatically calculate CO₂e from emission factors' },
                        { key: 'evidence_required', label: 'Evidence Required', desc: 'Require proof file for CSR participation approval' },
                        { key: 'badge_auto_award', label: 'Auto Badge Award', desc: 'Automatically award badges when unlock criteria are met' },
                    ].map(({ key, label, desc }) => (
                        <div key={key} className="flex items-center justify-between py-3 border-b border-slate-800 last:border-0">
                            <div>
                                <p className="text-white text-sm font-medium">{label}</p>
                                <p className="text-slate-500 text-xs mt-0.5">{desc}</p>
                            </div>
                            <button onClick={() => (user?.role === 'admin' || user?.role === 'manager') && setConfig(c => ({ ...c, [key]: !c[key as keyof typeof c] }))}
                                className={`relative w-12 h-6 rounded-full transition-all ${(user?.role !== 'admin' && user?.role !== 'manager') ? 'opacity-50 cursor-not-allowed' : ''}`}
                                style={{ background: config[key as keyof typeof config] ? '#1599df' : '#b9dff4' }}>
                                <div className="absolute top-1 w-4 h-4 bg-white rounded-full transition-all shadow-sm"
                                    style={{ left: config[key as keyof typeof config] ? '26px' : '4px' }} />
                            </button>
                        </div>
                    ))}
                </div>

                <button onClick={saveConfig} disabled={saving || (user?.role !== 'admin' && user?.role !== 'manager')} className="btn btn-primary w-full justify-center"
                    style={{ '--accent': '#1599df', '--accent-dim': '#4f46e5', '--accent-glow': 'rgba(99,102,241,0.3)' } as any}>
                    <Save size={16} /> {saving ? 'Saving…' : 'Save Settings'}
                </button>
            </div>
        </div>
    )
}
