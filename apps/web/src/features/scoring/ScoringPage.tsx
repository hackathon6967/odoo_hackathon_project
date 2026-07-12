import { useEffect, useState } from 'react'
import { BarChart3, Download, RefreshCw, FileText } from 'lucide-react'
import api from '../../api/client'
import toast from 'react-hot-toast'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from 'recharts'

export default function ScoringPage() {
    const [scores, setScores] = useState<any[]>([])
    const [overall, setOverall] = useState<any>(null)
    const [reports, setReports] = useState<any[]>([])
    const [leaderboard, setLeaderboard] = useState<any[]>([])
    const [activeTab, setActiveTab] = useState<'scores' | 'reports' | 'leaderboard'>('scores')
    const [_loading, setLoading] = useState(true)
    const [generating, setGenerating] = useState<string | null>(null)
    const [filterDept, setFilterDept] = useState('')
    const [filterStart, setFilterStart] = useState('')
    const [filterEnd, setFilterEnd] = useState('')

    const loadData = () => {
        Promise.all([
            api.get('/scoring/scores'),
            api.get('/scoring/overall-esg'),
            api.get('/scoring/reports'),
            api.get('/scoring/leaderboard')
        ]).then(([s, o, r, l]) => {
            setScores(s.data); setOverall(o.data); setReports(r.data); setLeaderboard(l.data)
        }).catch(() => { }).finally(() => setLoading(false))
    }

    useEffect(() => { loadData() }, [])

    async function triggerScoring() {
        try {
            await api.post('/scoring/scores/trigger')
            toast.success('🔄 Scoring job queued!')
            setTimeout(loadData, 3000)
        } catch { toast.error('Failed to trigger scoring') }
    }

    async function requestReport(type: string, format: string) {
        setGenerating(`${type}-${format}`)
        try {
            const filters: Record<string, string> = {}
            if (filterDept) filters.department_id = filterDept
            if (filterStart) filters.start_date = filterStart
            if (filterEnd) filters.end_date = filterEnd
            
            const { data } = await api.post('/scoring/reports', { report_type: type, format, filters })
            toast.success(`📄 Report queued: ${data.report_job_id.slice(0, 8)}…`)
            setTimeout(() => { loadData(); setGenerating(null) }, 2000)
        } catch { toast.error('Failed'); setGenerating(null) }
    }

    const chartData = scores.slice(0, 8).map(s => ({
        dept: s.department_id?.slice(0, 6) + '…',
        Environmental: Math.round(s.environmental_score),
        Social: Math.round(s.social_score),
        Governance: Math.round(s.governance_score),
        Total: Math.round(s.total_score),
    }))

    return (
        <div className="theme-scoring min-h-screen p-8 page-bg">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center">
                        <BarChart3 size={20} className="text-cyan-400" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>Scoring & Reports</h1>
                        <p className="text-slate-400 text-sm">ESG performance analytics & report generation</p>
                    </div>
                </div>
                <button onClick={triggerScoring} className="btn btn-ghost flex items-center gap-2">
                    <RefreshCw size={16} className="text-cyan-400" /> Recompute Scores
                </button>
            </div>

            {/* Overall Score */}
            <div className="glass rounded-2xl p-6 mb-6 border border-cyan-500/20"
                style={{ background: 'linear-gradient(135deg, rgba(6,182,212,0.08), rgba(6,182,212,0.02))' }}>
                <div className="grid grid-cols-4 gap-6">
                    {[
                        { label: 'Overall ESG', value: Math.round(overall?.overall_esg_score || 0), color: '#1599df' },
                        { label: 'Environmental', value: Math.round(overall?.environmental_avg || 0), color: '#1599df' },
                        { label: 'Social', value: Math.round(overall?.social_avg || 0), color: '#1599df' },
                        { label: 'Governance', value: Math.round(overall?.governance_avg || 0), color: '#1599df' },
                    ].map(({ label, value, color }) => (
                        <div key={label} className="text-center">
                            <div className="text-5xl font-bold mb-1" style={{ color, fontFamily: 'Outfit' }}>{value}</div>
                            <div className="text-slate-400 text-sm">{label}</div>
                            <div className="text-slate-600 text-xs mt-0.5">/100</div>
                        </div>
                    ))}
                </div>
                <div className="text-center text-slate-500 text-xs mt-4">
                    Period: {overall?.period} · {overall?.departments_count} departments
                    {overall?.weights && ` · Weights: E${overall.weights.environmental} S${overall.weights.social} G${overall.weights.governance}`}
                </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-2 mb-6">
                {([
                    { key: 'scores', label: '📊 Department Scores' },
                    { key: 'leaderboard', label: '🏆 Leaderboard' },
                    { key: 'reports', label: '📄 Reports' },
                ] as const).map(({ key, label }) => (
                    <button key={key} onClick={() => setActiveTab(key)}
                        className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${activeTab === key
                            ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                            : 'text-slate-400 hover:text-white'}`}>
                        {label}
                    </button>
                ))}
            </div>

            {/* Scores Tab */}
            {activeTab === 'scores' && (
                <div>
                    {chartData.length > 0 && (
                        <div className="glass rounded-2xl p-6 mb-6">
                            <h3 className="text-white font-semibold mb-4">Department ESG Scores</h3>
                            <ResponsiveContainer width="100%" height={250}>
                                <BarChart data={chartData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff" />
                                    <XAxis dataKey="dept" tick={{ fill: '#5f8198', fontSize: 11 }} />
                                    <YAxis tick={{ fill: '#5f8198', fontSize: 11 }} domain={[0, 100]} />
                                    <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #b9dff4', borderRadius: 8, color: '#e2e8f0' }} />
                                    <Legend wrapperStyle={{ color: '#587b92' }} />
                                    <Bar dataKey="Environmental" fill="#4ade80" radius={[4, 4, 0, 0]} />
                                    <Bar dataKey="Social" fill="#fbbf24" radius={[4, 4, 0, 0]} />
                                    <Bar dataKey="Governance" fill="#818cf8" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                    <div className="glass rounded-2xl p-6">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-slate-500 border-b border-slate-800">
                                    <th className="pb-3 font-medium">Department</th>
                                    <th className="pb-3 font-medium">Period</th>
                                    <th className="pb-3 font-medium">Environmental</th>
                                    <th className="pb-3 font-medium">Social</th>
                                    <th className="pb-3 font-medium">Governance</th>
                                    <th className="pb-3 font-medium">Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                {scores.map(s => (
                                    <tr key={s.department_id + s.period} className="table-row border-b border-slate-800/50">
                                        <td className="py-3 text-white text-xs">{s.department_id?.slice(0, 8)}…</td>
                                        <td className="py-3 text-slate-400">{s.period}</td>
                                        <td className="py-3 text-green-400 font-medium">{Math.round(s.environmental_score)}</td>
                                        <td className="py-3 text-amber-400 font-medium">{Math.round(s.social_score)}</td>
                                        <td className="py-3 text-indigo-400 font-medium">{Math.round(s.governance_score)}</td>
                                        <td className="py-3 text-cyan-400 font-bold">{Math.round(s.total_score)}</td>
                                    </tr>
                                ))}
                                {scores.length === 0 && <tr><td colSpan={6} className="py-8 text-center text-slate-500">No scores computed yet. Click "Recompute Scores" to generate.</td></tr>}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Reports Tab */}
            {activeTab === 'reports' && (
                <div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        {[
                            { type: 'summary', label: '📊 Summary Report', formats: ['pdf', 'xlsx', 'csv'] },
                            { type: 'environmental', label: '🌿 Environmental', formats: ['pdf', 'csv'] },
                            { type: 'social', label: '👥 Social', formats: ['pdf', 'csv'] },
                            { type: 'governance', label: '🛡️ Governance', formats: ['pdf', 'xlsx'] },
                        ].map(({ type, label, formats }) => (
                            <div key={type} className="glass rounded-2xl p-4 border border-cyan-500/10">
                                <h4 className="text-white text-sm font-medium mb-3">{label}</h4>
                                <div className="flex flex-wrap gap-2">
                                    {formats.map(f => (
                                        <button key={f} onClick={() => requestReport(type, f)}
                                            disabled={generating === `${type}-${f}`}
                                            className="px-2.5 py-1 rounded-lg text-xs font-medium transition-all disabled:opacity-50"
                                            style={{ background: 'rgba(6,182,212,0.15)', color: '#1599df', border: '1px solid rgba(6,182,212,0.2)' }}>
                                            {generating === `${type}-${f}` ? '⏳' : <FileText size={12} className="inline mr-1" />}
                                            {f.toUpperCase()}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="glass rounded-2xl p-6 mb-6 border border-cyan-500/10">
                        <h3 className="text-white font-semibold mb-4">🛠️ Custom Report Builder</h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                            <div>
                                <label className="block text-xs text-slate-400 mb-1">Department ID</label>
                                <input type="text" value={filterDept} onChange={e => setFilterDept(e.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500" placeholder="Optional UUID..." />
                            </div>
                            <div>
                                <label className="block text-xs text-slate-400 mb-1">Start Date</label>
                                <input type="date" value={filterStart} onChange={e => setFilterStart(e.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500" />
                            </div>
                            <div>
                                <label className="block text-xs text-slate-400 mb-1">End Date</label>
                                <input type="date" value={filterEnd} onChange={e => setFilterEnd(e.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500" />
                            </div>
                        </div>
                        <div className="flex gap-2">
                            {['pdf', 'xlsx', 'csv'].map(f => (
                                <button key={`custom-${f}`} onClick={() => requestReport('custom', f)}
                                    disabled={generating === `custom-${f}`}
                                    className="px-3 py-1.5 rounded-lg text-sm font-medium transition-all disabled:opacity-50"
                                    style={{ background: 'rgba(6,182,212,0.15)', color: '#1599df', border: '1px solid rgba(6,182,212,0.2)' }}>
                                    {generating === `custom-${f}` ? '⏳' : <FileText size={14} className="inline mr-1.5" />}
                                    Generate {f.toUpperCase()}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="glass rounded-2xl p-6">
                        <h3 className="text-white font-semibold mb-4">Recent Reports</h3>
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-slate-500 border-b border-slate-800">
                                    <th className="pb-3 font-medium">Type</th>
                                    <th className="pb-3 font-medium">Format</th>
                                    <th className="pb-3 font-medium">Status</th>
                                    <th className="pb-3 font-medium">Requested</th>
                                    <th className="pb-3 font-medium">Download</th>
                                </tr>
                            </thead>
                            <tbody>
                                {reports.map(r => (
                                    <tr key={r.id} className="table-row border-b border-slate-800/50">
                                        <td className="py-3 text-white capitalize">{r.report_type}</td>
                                        <td className="py-3 text-slate-400 uppercase text-xs">{r.format}</td>
                                        <td className="py-3"><span className={`status-badge ${statusClass(r.status)}`}>{r.status}</span></td>
                                        <td className="py-3 text-slate-500 text-xs">{r.created_at?.split('T')[0]}</td>
                                        <td className="py-3">
                                            {r.status === 'ready' && r.download_url ? (
                                                <a href={r.download_url} target="_blank" rel="noreferrer"
                                                    className="flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300 transition-colors">
                                                    <Download size={12} /> Download
                                                </a>
                                            ) : <span className="text-slate-600 text-xs">-</span>}
                                        </td>
                                    </tr>
                                ))}
                                {reports.length === 0 && <tr><td colSpan={5} className="py-8 text-center text-slate-500">No reports generated yet</td></tr>}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Leaderboard Tab */}
            {activeTab === 'leaderboard' && (
                <div className="glass rounded-2xl p-6">
                    <h3 className="text-white font-semibold mb-4 text-center">🏆 Department ESG Leaderboard</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-slate-500 border-b border-slate-800">
                                    <th className="pb-3 font-medium w-16 text-center">Rank</th>
                                    <th className="pb-3 font-medium">Department</th>
                                    <th className="pb-3 font-medium">Environmental</th>
                                    <th className="pb-3 font-medium">Social</th>
                                    <th className="pb-3 font-medium">Governance</th>
                                    <th className="pb-3 font-medium text-right pr-4">Total Score</th>
                                </tr>
                            </thead>
                            <tbody>
                                {leaderboard.map(l => (
                                    <tr key={l.department_id} className="table-row border-b border-slate-800/50">
                                        <td className="py-4 text-center">
                                            <div className={`inline-flex items-center justify-center w-8 h-8 rounded-full font-bold ${
                                                l.rank === 1 ? 'bg-amber-500/20 text-amber-400' :
                                                l.rank === 2 ? 'bg-slate-300/20 text-slate-300' :
                                                l.rank === 3 ? 'bg-amber-700/20 text-amber-600' :
                                                'bg-slate-800 text-slate-400'
                                            }`}>{l.rank}</div>
                                        </td>
                                        <td className="py-4 text-white font-medium">{l.department_name}</td>
                                        <td className="py-4 text-green-400">{l.environmental_score}</td>
                                        <td className="py-4 text-amber-400">{l.social_score}</td>
                                        <td className="py-4 text-indigo-400">{l.governance_score}</td>
                                        <td className="py-4 text-cyan-400 font-bold text-lg text-right pr-4">{l.total_score}</td>
                                    </tr>
                                ))}
                                {leaderboard.length === 0 && (
                                    <tr><td colSpan={6} className="py-8 text-center text-slate-500">No leaderboard data available</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    )
}

function statusClass(status: string) {
    const m: Record<string, string> = { pending: 'status-pending', generating: 'status-active', ready: 'status-approved', failed: 'status-rejected' }
    return m[status] || 'status-pending'
}
