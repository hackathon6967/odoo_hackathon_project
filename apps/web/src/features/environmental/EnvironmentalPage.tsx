import { useEffect, useState } from 'react'
import { Leaf, Plus, TrendingDown, Target, Zap, Upload } from 'lucide-react'
import api from '../../api/client'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import toast from 'react-hot-toast'

export default function EnvironmentalPage() {
    const [dashboard, setDashboard] = useState<any>(null)
    const [goals, setGoals] = useState<any[]>([])
    const [factors, setFactors] = useState<any[]>([])
    const [products, setProducts] = useState<any[]>([])
    const [transactions, setTransactions] = useState<any[]>([])
    const [showForm, setShowForm] = useState(false)
    const [showProductForm, setShowProductForm] = useState(false)
    const [showGoalForm, setShowGoalForm] = useState(false)
    const [txForm, setTxForm] = useState({ department_id: '', source_module: 'purchase', emission_factor_id: '', quantity: 1, notes: '' })
    const [productForm, setProductForm] = useState({ product_ref: '', emission_factor_id: '', sustainability_notes: '' })
    const [goalForm, setGoalForm] = useState({ metric: 'Monthly CO2e target', target_value: 1000, unit: 'kg CO2e', target_date: '' })
    const [departments, setDepartments] = useState<any[]>([])
    const [trendData, setTrendData] = useState<any[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        Promise.all([
            api.get('/environmental/dashboard'),
            api.get('/environmental/goals'),
            api.get('/environmental/emission-factors'),
            api.get('/core/departments'),
            api.get('/environmental/products'),
            api.get('/environmental/trend'),
            api.get('/environmental/carbon-transactions?limit=10')
        ]).then(([d, g, f, dep, p, t, tx]) => {
            setDashboard(d.data); setGoals(g.data); setFactors(f.data); setDepartments(dep.data); setProducts(p.data); setTrendData(t.data); setTransactions(tx.data)
        }).finally(() => setLoading(false))
    }, [])

    async function submitTransaction() {
        try {
            const deptId = departments[0]?.id
            await api.post('/environmental/carbon-transactions', {
                ...txForm,
                department_id: txForm.department_id || deptId,
                emission_factor_id: txForm.emission_factor_id || factors[0]?.id,
                transaction_date: new Date().toISOString(),
            })
            toast.success('Carbon transaction recorded!')
            setShowForm(false)
            const [d, tx] = await Promise.all([
                api.get('/environmental/dashboard'),
                api.get('/environmental/carbon-transactions?limit=10')
            ])
            setDashboard(d.data)
            setTransactions(tx.data)
        } catch { toast.error('Failed to record transaction') }
    }

    async function handleFileUpload(txId: string, file: File) {
        const formData = new FormData()
        formData.append('log_file', file)
        try {
            await api.put(`/environmental/carbon-transactions/${txId}/upload-log`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            })
            toast.success('Log file uploaded successfully')
            const r = await api.get('/environmental/carbon-transactions?limit=10')
            setTransactions(r.data)
        } catch (e: any) {
            toast.error(e.response?.data?.detail || 'Failed to upload log file')
        }
    }

    async function submitProduct() {
        try {
            await api.post('/environmental/products', productForm)
            toast.success('Product ESG Profile created!')
            setShowProductForm(false)
            setProductForm({ product_ref: '', emission_factor_id: '', sustainability_notes: '' })
            const p = await api.get('/environmental/products')
            setProducts(p.data)
        } catch (e: any) { toast.error(e.response?.data?.detail || 'Failed to create product profile') }
    }

    async function submitGoal() {
        try {
            await api.post('/environmental/goals', { ...goalForm, target_date: new Date(goalForm.target_date).toISOString() })
            const [goalResponse, dashboardResponse] = await Promise.all([api.get('/environmental/goals'), api.get('/environmental/dashboard')])
            setGoals(goalResponse.data); setDashboard(dashboardResponse.data); setShowGoalForm(false)
            toast.success('Active goal created')
        } catch (error: any) { toast.error(error.response?.data?.detail || 'Could not create goal') }
    }



    return (
        <div className="theme-environmental min-h-screen p-8 relative overflow-hidden page-bg">
            <div className="relative z-10">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <div className="flex items-center gap-3 mb-1">
                            <div className="w-10 h-10 rounded-xl bg-green-500/20 flex items-center justify-center">
                                <Leaf size={20} className="text-green-400" />
                            </div>
                            <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>Environmental</h1>
                        </div>
                        <p className="text-slate-400 text-sm ml-13">Carbon emissions & sustainability goals</p>
                    </div>
                    <button onClick={() => setShowForm(!showForm)} className="btn btn-primary"
                        style={{ '--accent': '#1599df', '--accent-dim': '#0878b8', '--accent-glow': 'rgba(34,197,94,0.3)' } as any}>
                        <Plus size={16} /> Log Emission
                    </button>
                </div>

                {/* Add Transaction Form */}
                {showForm && (
                    <div className="glass rounded-2xl p-6 mb-6 border border-green-500/20">
                        <h3 className="text-white font-semibold mb-4">Record Carbon Transaction</h3>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div>
                                <label className="text-slate-400 text-xs mb-1 block">Emission Factor</label>
                                <select className="input text-white bg-slate-900/50" value={txForm.emission_factor_id}
                                    onChange={e => setTxForm(f => ({ ...f, emission_factor_id: e.target.value }))}>
                                    <option value="">Select factor</option>
                                    {factors.map(f => <option key={f.id} value={f.id}>{f.source_type} ({f.unit})</option>)}
                                </select>
                            </div>
                            <div>
                                <label className="text-slate-400 text-xs mb-1 block">Source Module</label>
                                <select className="input text-white bg-slate-900/50" value={txForm.source_module}
                                    onChange={e => setTxForm(f => ({ ...f, source_module: e.target.value }))}>
                                    {['purchase', 'manufacturing', 'expense', 'fleet'].map(m => <option key={m} value={m}>{m}</option>)}
                                </select>
                            </div>
                            <div>
                                <label className="text-slate-400 text-xs mb-1 block">Quantity</label>
                                <input className="input" type="number" value={txForm.quantity}
                                    onChange={e => setTxForm(f => ({ ...f, quantity: Number(e.target.value) }))} />
                            </div>
                            <div className="flex items-end">
                                <button onClick={submitTransaction} className="btn btn-primary w-full justify-center"
                                    style={{ '--accent': '#1599df', '--accent-dim': '#0878b8', '--accent-glow': 'rgba(34,197,94,0.3)' } as any}>
                                    Submit
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Stats row */}
                <div className="grid grid-cols-3 gap-4 mb-6">
                    {[
                        { icon: TrendingDown, label: 'CO₂e This Month', value: `${Math.round(dashboard?.total_co2e_this_month || 0).toLocaleString()} kg`, color: '#1599df' },
                        { icon: Zap, label: 'Total CO₂e (All Time)', value: `${Math.round(dashboard?.total_co2e_all_time || 0).toLocaleString()} kg`, color: '#1599df' },
                        { icon: Target, label: 'Active Goals', value: dashboard?.active_goals || 0, color: '#1599df' },
                    ].map(({ icon: Icon, label, value, color }) => (
                        <div key={label} className="stat-card glass" style={{ '--accent-glow': 'rgba(34,197,94,0.2)' } as any}>
                            <div className="flex items-center gap-2 mb-2">
                                <Icon size={16} style={{ color }} />
                                <span className="text-slate-400 text-sm">{label}</span>
                            </div>
                            <div className="text-2xl font-bold text-white">{value}</div>
                        </div>
                    ))}
                </div>

                {/* Charts row */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                    <div className="glass rounded-2xl p-6">
                        <h3 className="text-white font-semibold mb-4">CO₂e Trend (Monthly)</h3>
                        <ResponsiveContainer width="100%" height={200}>
                            <AreaChart data={trendData}>
                                <defs>
                                    <linearGradient id="co2Grad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#1599df" stopOpacity={0.4} />
                                        <stop offset="95%" stopColor="#1599df" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <XAxis dataKey="month" tick={{ fill: '#5f8198', fontSize: 11 }} axisLine={false} tickLine={false} />
                                <YAxis tick={{ fill: '#5f8198', fontSize: 11 }} axisLine={false} tickLine={false} />
                                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #b9dff4', borderRadius: 8, color: '#e2e8f0' }} />
                                <Area type="monotone" dataKey="co2" stroke="#1599df" strokeWidth={2} fill="url(#co2Grad)" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>

                    <div className="glass rounded-2xl p-6">
                        <div className="flex justify-between items-center mb-4"><h3 className="text-white font-semibold flex items-center gap-2"><Target size={16} className="text-[#1599df]" /> Active Goals</h3><button className="btn btn-primary text-xs py-1" style={{ '--accent': '#1599df', '--accent-dim': '#0878b8' } as any} onClick={() => setShowGoalForm(value => !value)}>+ Add Goal</button></div>
                        {showGoalForm && <div className="grid grid-cols-2 gap-2 mb-4"><input className="input col-span-2" placeholder="Goal name" value={goalForm.metric} onChange={e => setGoalForm(value => ({ ...value, metric: e.target.value }))} /><input className="input" type="number" value={goalForm.target_value} onChange={e => setGoalForm(value => ({ ...value, target_value: Number(e.target.value) }))} /><input className="input" placeholder="Unit" value={goalForm.unit} onChange={e => setGoalForm(value => ({ ...value, unit: e.target.value }))} /><input className="input" type="date" value={goalForm.target_date} onChange={e => setGoalForm(value => ({ ...value, target_date: e.target.value }))} /><button className="btn btn-primary justify-center" disabled={!goalForm.metric || !goalForm.target_date} onClick={submitGoal}>Save goal</button></div>}
                        {loading ? <p className="text-slate-400 text-sm">Loading...</p> : goals.length === 0 ? (
                            <p className="text-slate-500 text-sm text-center py-8">No active goals yet</p>
                        ) : goals.map(g => (
                            <div key={g.id} className="mb-4">
                                <div className="flex justify-between text-sm mb-1">
                                    <span className="text-slate-300">{g.metric}</span>
                                    <span className="text-green-400 font-medium">{g.progress_pct}%</span>
                                </div>
                                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                                    <div className="h-full rounded-full transition-all duration-1000"
                                        style={{ width: `${g.progress_pct}%`, background: 'linear-gradient(90deg, #1599df, #1599df)' }} />
                                </div>
                                <p className="text-slate-500 text-xs mt-0.5">{g.current_value} / {g.target_value} {g.unit}</p>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Emission Factors Table */}
                <div className="glass rounded-2xl p-6 mb-6">
                    <h3 className="text-white font-semibold mb-4">Emission Factors</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-slate-500 border-b border-slate-800">
                                    <th className="pb-3 font-medium">Source Type</th>
                                    <th className="pb-3 font-medium">Unit</th>
                                    <th className="pb-3 font-medium">CO₂e / Unit</th>
                                    <th className="pb-3 font-medium">Effective Date</th>
                                </tr>
                            </thead>
                            <tbody>
                                {factors.map(f => (
                                    <tr key={f.id} className="table-row border-b border-slate-800/50">
                                        <td className="py-3 text-white capitalize">{f.source_type}</td>
                                        <td className="py-3 text-slate-400">{f.unit}</td>
                                        <td className="py-3 text-green-400 font-medium">{f.co2e_per_unit}</td>
                                        <td className="py-3 text-slate-400">{f.effective_date?.split('T')[0]}</td>
                                    </tr>
                                ))}
                                {factors.length === 0 && (
                                    <tr><td colSpan={4} className="py-8 text-center text-slate-500">No emission factors configured</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Recent Emissions Table */}
                <div className="glass rounded-2xl p-6 mb-6">
                    <h3 className="text-white font-semibold mb-4">Recent Emissions</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-slate-500 border-b border-slate-800">
                                    <th className="pb-3 font-medium">Source Module</th>
                                    <th className="pb-3 font-medium">Quantity</th>
                                    <th className="pb-3 font-medium">CO₂e (kg)</th>
                                    <th className="pb-3 font-medium">Date</th>
                                    <th className="pb-3 font-medium text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {transactions.map(tx => (
                                    <tr key={tx.id} className="table-row border-b border-slate-800/50">
                                        <td className="py-3 text-white capitalize">{tx.source_module}</td>
                                        <td className="py-3 text-slate-400">{tx.quantity}</td>
                                        <td className="py-3 text-green-400 font-medium">{Math.round(tx.co2e_calculated)}</td>
                                        <td className="py-3 text-slate-400">{tx.transaction_date?.split('T')[0]}</td>
                                        <td className="py-3 text-right">
                                            {tx.file_ref ? (
                                                <span className="text-xs text-green-400">Log attached</span>
                                            ) : (
                                                <label className="cursor-pointer text-xs flex items-center justify-end gap-1 text-indigo-400 hover:text-indigo-300">
                                                    <Upload size={14} /> Upload Log
                                                    <input type="file" className="hidden" onChange={(e) => {
                                                        if (e.target.files && e.target.files[0]) {
                                                            handleFileUpload(tx.id, e.target.files[0])
                                                        }
                                                    }} />
                                                </label>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                                {transactions.length === 0 && (
                                    <tr><td colSpan={5} className="py-8 text-center text-slate-500">No emissions logged yet</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Product ESG Profiles */}
                <div className="glass rounded-2xl p-6">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-white font-semibold">Product ESG Profiles</h3>
                        <button onClick={() => setShowProductForm(!showProductForm)} className="btn btn-ghost text-xs">
                            + New Profile
                        </button>
                    </div>

                    {showProductForm && (
                        <div className="bg-slate-900/50 rounded-xl p-4 mb-4 border border-green-500/20">
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                                <div>
                                    <label className="text-slate-400 text-xs mb-1 block">Product Reference</label>
                                    <input className="input" placeholder="SKU or Name" value={productForm.product_ref}
                                        onChange={e => setProductForm(f => ({ ...f, product_ref: e.target.value }))} />
                                </div>
                                <div>
                                    <label className="text-slate-400 text-xs mb-1 block">Emission Factor</label>
                                    <select className="input text-white bg-slate-900/50" value={productForm.emission_factor_id}
                                        onChange={e => setProductForm(f => ({ ...f, emission_factor_id: e.target.value }))}>
                                        <option value="">None (Custom)</option>
                                        {factors.map(f => <option key={f.id} value={f.id}>{f.source_type} ({f.unit})</option>)}
                                    </select>
                                </div>
                                <div>
                                    <label className="text-slate-400 text-xs mb-1 block">Sustainability Notes</label>
                                    <input className="input" placeholder="Recycled materials..." value={productForm.sustainability_notes}
                                        onChange={e => setProductForm(f => ({ ...f, sustainability_notes: e.target.value }))} />
                                </div>
                            </div>
                            <div className="flex justify-end">
                                <button onClick={submitProduct} className="btn btn-primary text-xs py-1.5"
                                    style={{ '--accent': '#1599df', '--accent-dim': '#0878b8', '--accent-glow': 'rgba(34,197,94,0.3)' } as any}>
                                    Save Profile
                                </button>
                            </div>
                        </div>
                    )}

                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-slate-500 border-b border-slate-800">
                                    <th className="pb-3 font-medium">Product Ref</th>
                                    <th className="pb-3 font-medium">Linked Emission Factor</th>
                                    <th className="pb-3 font-medium">Notes</th>
                                </tr>
                            </thead>
                            <tbody>
                                {products.map(p => (
                                    <tr key={p.id} className="table-row border-b border-slate-800/50">
                                        <td className="py-3 text-white font-medium">{p.product_ref}</td>
                                        <td className="py-3 text-slate-400">
                                            {p.emission_factor_id ? <span className="text-green-400 text-xs border border-green-500/30 px-2 py-0.5 rounded bg-green-500/10">Linked</span> : 'Custom'}
                                        </td>
                                        <td className="py-3 text-slate-400 text-xs max-w-xs truncate">{p.sustainability_notes || '-'}</td>
                                    </tr>
                                ))}
                                {products.length === 0 && (
                                    <tr><td colSpan={3} className="py-8 text-center text-slate-500">No product ESG profiles created yet</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    )
}
