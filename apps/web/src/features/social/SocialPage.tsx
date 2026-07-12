import { useEffect, useState } from 'react'
import { Users, CheckCircle, Clock, XCircle, PieChart as PieChartIcon } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import api from '../../api/client'
import toast from 'react-hot-toast'

export default function SocialPage() {
    const [activities, setActivities] = useState<any[]>([])
    const [participations, setParticipations] = useState<any[]>([])
    const [trainings, setTrainings] = useState<any[]>([])
    const [diversityMetrics, setDiversityMetrics] = useState<any[]>([])
    const [dashboard, setDashboard] = useState<any>(null)
    const [activeTab, setActiveTab] = useState<'activities' | 'participations' | 'trainings' | 'diversity'>('activities')
    const [_loading, setLoading] = useState(true)
    const [_showForm, setShowForm] = useState(false)


    const loadData = () => {
        Promise.all([
            api.get('/social/activities'),
            api.get('/social/participations'),
            api.get('/social/dashboard'),
            api.get('/social/trainings'),
            api.get('/social/diversity-metrics')
        ]).then(([a, p, d, t, div]) => {
            setActivities(a.data); setParticipations(p.data); setDashboard(d.data);
            setTrainings(t.data); setDiversityMetrics(div.data);
        }).catch(() => { }).finally(() => setLoading(false))
    }

    useEffect(() => { loadData() }, [])

    async function joinActivity(activityId: string) {
        try {
            const formData = new FormData()
            formData.append('proof_file', '')
            await api.post(`/social/activities/${activityId}/participate`, formData)
            toast.success('Joined! Awaiting approval.')
            loadData()
        } catch (e: any) { toast.error(e.response?.data?.detail || 'Failed') }
    }

    async function approveParticipation(id: string) {
        try {
            await api.put(`/social/participations/${id}/approve`)
            toast.success('Participation approved!')
            loadData()
        } catch (e: any) { toast.error(e.response?.data?.detail || 'Failed') }
    }

    const statusIcon: Record<string, React.ReactNode> = {
        Approved: <CheckCircle size={14} className="text-green-400" />,
        Pending: <Clock size={14} className="text-amber-400" />,
        Rejected: <XCircle size={14} className="text-red-400" />,
    }

    async function completeTraining(id: string) {
        try {
            await api.post(`/social/trainings/${id}/complete`)
            toast.success('Training completed!')
            loadData()
        } catch (e: any) { toast.error(e.response?.data?.detail || 'Failed') }
    }

    return (
        <div className="theme-social min-h-screen p-8 page-bg">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center">
                        <Users size={20} className="text-amber-400" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>Social & CSR</h1>
                        <p className="text-slate-400 text-sm">Community initiatives & employee participation</p>
                    </div>
                </div>
                <button onClick={() => setShowForm(v => !v)} className="btn btn-ghost">
                    + New Activity
                </button>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-4 mb-6">
                {[
                    { label: 'Total Participations', value: dashboard?.total_participations || 0, icon: Users, color: '#1599df' },
                    { label: 'Approved', value: dashboard?.approved_participations || 0, icon: CheckCircle, color: '#1599df' },
                    { label: 'Pending Review', value: dashboard?.pending_participations || 0, icon: Clock, color: '#1599df' },
                ].map(({ label, value, icon: Icon, color }) => (
                    <div key={label} className="glass rounded-2xl p-5 border border-amber-500/10">
                        <div className="flex items-center gap-2 mb-2">
                            <Icon size={16} style={{ color }} />
                            <span className="text-slate-400 text-sm">{label}</span>
                        </div>
                        <div className="text-2xl font-bold text-white">{value}</div>
                    </div>
                ))}
            </div>

            {/* Tabs */}
            <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
                {(['activities', 'participations', 'trainings', 'diversity'] as const).map(tab => (
                    <button key={tab} onClick={() => setActiveTab(tab)}
                        className={`px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${activeTab === tab
                            ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                            : 'text-slate-400 hover:text-white'}`}>
                        {tab === 'activities' ? '📋 CSR Activities' :
                         tab === 'participations' ? '👥 Participations' :
                         tab === 'trainings' ? '📚 Training & Development' : '📊 Diversity Metrics'}
                    </button>
                ))}
            </div>

            {/* Activities Tab */}
            {activeTab === 'activities' && (
                <div className="glass rounded-2xl p-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {_loading ? <p className="text-slate-400 col-span-3">Loading...</p> :
                            activities.length === 0 ? <p className="text-slate-500 col-span-3 py-8 text-center">No CSR activities yet</p> :
                                activities.map(a => (
                                    <div key={a.id} className="glass rounded-xl p-4 border border-amber-500/10 hover:border-amber-500/30 transition-all">
                                        <div className="text-amber-400 text-xs font-medium mb-2">📅 {a.date?.split('T')[0]}</div>
                                        <h3 className="text-white font-semibold mb-1">{a.title}</h3>
                                        <div className="flex items-center justify-between mt-3">
                                            <span className="text-amber-400 font-medium text-sm">+{a.points_reward} pts</span>
                                            <button onClick={() => joinActivity(a.id)}
                                                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 transition-all">
                                                Join
                                            </button>
                                        </div>
                                    </div>
                                ))}
                    </div>
                </div>
            )}

            {/* Participations Tab */}
            {activeTab === 'participations' && (
                <div className="glass rounded-2xl p-6">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-left text-slate-500 border-b border-slate-800">
                                <th className="pb-3 font-medium">Employee</th>
                                <th className="pb-3 font-medium">Status</th>
                                <th className="pb-3 font-medium">Points</th>
                                <th className="pb-3 font-medium">Evidence</th>
                                <th className="pb-3 font-medium">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {participations.map(p => (
                                <tr key={p.id} className="table-row border-b border-slate-800/50">
                                    <td className="py-3 text-white text-xs">{p.employee_id?.slice(0, 8)}…</td>
                                    <td className="py-3">
                                        <span className={`status-badge status-${p.approval_status.toLowerCase()} inline-flex items-center gap-1`}>
                                            {statusIcon[p.approval_status]} {p.approval_status}
                                        </span>
                                    </td>
                                    <td className="py-3 text-amber-400">{p.points_earned}</td>
                                    <td className="py-3">{p.proof_file_ref ? <span className="text-green-400 text-xs">✓ Uploaded</span> : <span className="text-slate-500 text-xs">None</span>}</td>
                                    <td className="py-3">
                                        {p.approval_status === 'Pending' && (
                                            <button onClick={() => approveParticipation(p.id)}
                                                className="px-3 py-1 rounded-lg text-xs bg-green-500/20 text-green-400 hover:bg-green-500/30 transition-all">
                                                Approve
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                            {participations.length === 0 && (
                                <tr><td colSpan={5} className="py-8 text-center text-slate-500">No participations yet</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Trainings Tab */}
            {activeTab === 'trainings' && (
                <div className="glass rounded-2xl p-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {_loading ? <p className="text-slate-400 col-span-3">Loading...</p> :
                            trainings.length === 0 ? <p className="text-slate-500 col-span-3 py-8 text-center">No training modules yet</p> :
                                trainings.map(t => (
                                    <div key={t.id} className="glass rounded-xl p-4 border border-amber-500/10 hover:border-amber-500/30 transition-all">
                                        <div className="flex justify-between items-start mb-2">
                                            <div className="text-amber-400 text-xs font-medium bg-amber-500/10 px-2 py-1 rounded">
                                                {t.is_mandatory ? 'Mandatory' : 'Optional'}
                                            </div>
                                            {t.is_completed && <CheckCircle size={16} className="text-green-400" />}
                                        </div>
                                        <h3 className="text-white font-semibold mb-1">{t.title}</h3>
                                        <p className="text-slate-400 text-xs mb-3 line-clamp-2">{t.description}</p>
                                        <div className="flex items-center justify-between mt-auto">
                                            <span className="text-amber-400 font-medium text-sm">+{t.xp_reward} XP</span>
                                            {!t.is_completed ? (
                                                <button onClick={() => completeTraining(t.id)}
                                                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 transition-all">
                                                    Mark Complete
                                                </button>
                                            ) : (
                                                <span className="text-green-400 text-xs font-medium">Completed</span>
                                            )}
                                        </div>
                                    </div>
                                ))}
                    </div>
                </div>
            )}

            {/* Diversity Tab */}
            {activeTab === 'diversity' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="glass rounded-2xl p-6">
                        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                            <PieChartIcon size={16} className="text-amber-400" /> Gender Diversity
                        </h3>
                        <ResponsiveContainer width="100%" height={250}>
                            {diversityMetrics.length > 0 ? (
                                <PieChart>
                                    <Pie
                                        data={[
                                            { name: 'Male', value: diversityMetrics[0].gender_male },
                                            { name: 'Female', value: diversityMetrics[0].gender_female },
                                            { name: 'Other', value: diversityMetrics[0].gender_other }
                                        ]}
                                        cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value"
                                    >
                                        <Cell fill="#3b82f6" />
                                        <Cell fill="#1599df" />
                                        <Cell fill="#1599df" />
                                    </Pie>
                                    <Tooltip contentStyle={{ background: '#ffffff', border: 'none', borderRadius: 8, color: '#fff' }} />
                                </PieChart>
                            ) : (
                                <div className="flex items-center justify-center h-full text-slate-500">No data available</div>
                            )}
                        </ResponsiveContainer>
                    </div>
                    
                    <div className="glass rounded-2xl p-6">
                        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                            <Users size={16} className="text-amber-400" /> Tenure Distribution
                        </h3>
                        <ResponsiveContainer width="100%" height={250}>
                            {diversityMetrics.length > 0 ? (
                                <BarChart data={[
                                    { name: '<1 Year', count: diversityMetrics[0].tenure_0_1 },
                                    { name: '1-3 Years', count: diversityMetrics[0].tenure_1_3 },
                                    { name: '3-5 Years', count: diversityMetrics[0].tenure_3_5 },
                                    { name: '5+ Years', count: diversityMetrics[0].tenure_5_plus },
                                ]}>
                                    <XAxis dataKey="name" tick={{ fill: '#587b92', fontSize: 12 }} axisLine={false} tickLine={false} />
                                    <YAxis tick={{ fill: '#587b92', fontSize: 12 }} axisLine={false} tickLine={false} />
                                    <Tooltip cursor={{ fill: '#b9dff4', opacity: 0.4 }} contentStyle={{ background: '#ffffff', border: 'none', borderRadius: 8, color: '#fff' }} />
                                    <Bar dataKey="count" fill="#1599df" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            ) : (
                                <div className="flex items-center justify-center h-full text-slate-500">No data available</div>
                            )}
                        </ResponsiveContainer>
                    </div>
                </div>
            )}
        </div>
    )
}
