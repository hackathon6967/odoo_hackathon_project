import { useEffect, useState } from 'react'
import { Shield, BookOpen, AlertTriangle, CheckCircle, Upload } from 'lucide-react'
import api from '../../api/client'
import toast from 'react-hot-toast'

export default function GovernancePage() {
    const [policies, setPolicies] = useState<any[]>([])
    const [audits, setAudits] = useState<any[]>([])
    const [issues, setIssues] = useState<any[]>([])
    const [activeTab, setActiveTab] = useState<'policies' | 'audits' | 'issues'>('policies')
    const [_loading, setLoading] = useState(true)
    const [showIssueForm, setShowIssueForm] = useState(false)
    const [issueForm, setIssueForm] = useState({ severity: 'medium', description: '', owner_id: '', due_date: '' })
    const [users, setUsers] = useState<any[]>([])

    useEffect(() => {
        Promise.all([
            api.get('/governance/policies'),
            api.get('/governance/audits'),
            api.get('/governance/compliance-issues'),
            api.get('/core/users'),
        ]).then(([p, a, i, u]) => {
            setPolicies(p.data); setAudits(a.data); setIssues(i.data); setUsers(u.data)
        }).catch(() => { }).finally(() => setLoading(false))
    }, [])

    async function acknowledgePolicy(id: string) {
        try {
            await api.post(`/governance/policies/${id}/acknowledge`)
            toast.success('Policy acknowledged!')
        } catch { toast.error('Failed') }
    }

    async function createIssue() {
        try {
            await api.post('/governance/compliance-issues', {
                ...issueForm,
                due_date: new Date(issueForm.due_date).toISOString(),
            })
            toast.success('Compliance issue created!')
            setShowIssueForm(false)
            const r = await api.get('/governance/compliance-issues')
            setIssues(r.data)
        } catch (e: any) { toast.error(e.response?.data?.detail || 'Failed') }
    }

    async function handleFileUpload(auditId: string, file: File) {
        const formData = new FormData()
        formData.append('log_file', file)
        try {
            await api.put(`/governance/audits/${auditId}/upload-log`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            })
            toast.success('Audit file uploaded successfully')
            const r = await api.get('/governance/audits')
            setAudits(r.data)
        } catch (e: any) {
            toast.error(e.response?.data?.detail || 'Failed to upload audit file')
        }
    }

    const severityColor: Record<string, string> = {
        low: '#1599df', medium: '#1599df', high: '#1599df', critical: '#ef4444'
    }

    const statusClass: Record<string, string> = {
        Open: 'status-open', 'In Progress': 'status-active', Resolved: 'status-resolved', Overdue: 'status-overdue'
    }

    return (
        <div className="theme-governance min-h-screen p-8 relative page-bg">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center shield-pulse">
                        <Shield size={20} className="text-indigo-400" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>Governance</h1>
                        <p className="text-slate-400 text-sm">Policies, audits & compliance management</p>
                    </div>
                </div>
                <button onClick={() => setShowIssueForm(!showIssueForm)} className="btn btn-ghost">
                    <AlertTriangle size={16} className="text-orange-400" /> Report Issue
                </button>
            </div>

            {/* Issue form */}
            {showIssueForm && (
                <div className="glass rounded-2xl p-6 mb-6 border border-indigo-500/20">
                    <h3 className="text-white font-semibold mb-4">New Compliance Issue</h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div>
                            <label className="text-slate-400 text-xs mb-1 block">Severity</label>
                            <select className="input text-white bg-slate-900/50" value={issueForm.severity}
                                onChange={e => setIssueForm(f => ({ ...f, severity: e.target.value }))}>
                                {['low', 'medium', 'high', 'critical'].map(s => <option key={s} value={s}>{s}</option>)}
                            </select>
                        </div>
                        <div>
                            <label className="text-slate-400 text-xs mb-1 block">Owner (required)</label>
                            <select className="input text-white bg-slate-900/50" value={issueForm.owner_id}
                                onChange={e => setIssueForm(f => ({ ...f, owner_id: e.target.value }))}>
                                <option value="">Select owner</option>
                                {users.map(u => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                            </select>
                        </div>
                        <div>
                            <label className="text-slate-400 text-xs mb-1 block">Due Date (required)</label>
                            <input className="input" type="date" value={issueForm.due_date}
                                onChange={e => setIssueForm(f => ({ ...f, due_date: e.target.value }))} />
                        </div>
                        <div className="flex items-end">
                            <button onClick={createIssue} className="btn w-full justify-center"
                                style={{ background: '#1599df', color: 'white' }}>
                                Submit
                            </button>
                        </div>
                    </div>
                    <div className="mt-3">
                        <label className="text-slate-400 text-xs mb-1 block">Description</label>
                        <textarea className="input h-20 resize-none" value={issueForm.description}
                            onChange={e => setIssueForm(f => ({ ...f, description: e.target.value }))}
                            placeholder="Describe the compliance issue..." />
                    </div>
                </div>
            )}

            {/* Tabs */}
            <div className="flex gap-2 mb-6">
                {([
                    { key: 'policies', label: '📜 Policies', count: policies.length },
                    { key: 'audits', label: '🔍 Audits', count: audits.length },
                    { key: 'issues', label: '⚠️ Issues', count: issues.filter(i => i.status === 'Open' || i.status === 'Overdue').length },
                ] as const).map(({ key, label, count }) => (
                    <button key={key} onClick={() => setActiveTab(key)}
                        className={`px-4 py-2 rounded-xl text-sm font-medium transition-all flex items-center gap-2 ${activeTab === key
                            ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                            : 'text-slate-400 hover:text-white'}`}>
                        {label}
                        {count > 0 && (
                            <span className="bg-indigo-500/30 text-indigo-300 px-1.5 py-0.5 rounded-md text-xs">{count}</span>
                        )}
                    </button>
                ))}
            </div>

            {/* Policies */}
            {activeTab === 'policies' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {policies.map(p => (
                        <div key={p.id} className="glass rounded-2xl p-5 border border-indigo-500/10 hover:border-indigo-500/30 transition-all">
                            <div className="flex items-start justify-between">
                                <div>
                                    <div className="flex items-center gap-2 mb-1">
                                        <BookOpen size={14} className="text-indigo-400" />
                                        <span className="text-indigo-400 text-xs">v{p.version}</span>
                                        <span className={`status-badge ${p.status === 'published' ? 'status-approved' : 'status-pending'} text-xs`}>
                                            {p.status}
                                        </span>
                                    </div>
                                    <h3 className="text-white font-semibold">{p.title}</h3>
                                    <p className="text-slate-500 text-xs mt-1">Effective: {p.effective_date?.split('T')[0]}</p>
                                </div>
                                {p.requires_acknowledgement && (
                                    <button onClick={() => acknowledgePolicy(p.id)}
                                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs bg-indigo-500/20 text-indigo-400 hover:bg-indigo-500/30 transition-all">
                                        <CheckCircle size={12} /> Acknowledge
                                    </button>
                                )}
                            </div>
                        </div>
                    ))}
                    {policies.length === 0 && <p className="text-slate-500 py-8 text-center col-span-2">No policies found</p>}
                </div>
            )}

            {/* Audits */}
            {activeTab === 'audits' && (
                <div className="glass rounded-2xl p-6">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-left text-slate-500 border-b border-slate-800">
                                <th className="pb-3 font-medium">Title</th>
                                <th className="pb-3 font-medium">Auditor</th>
                                <th className="pb-3 font-medium">Date</th>
                                <th className="pb-3 font-medium">Status</th>
                                <th className="pb-3 font-medium text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {audits.map(a => (
                                <tr key={a.id} className="table-row border-b border-slate-800/50">
                                    <td className="py-3 text-white">{a.title}</td>
                                    <td className="py-3 text-slate-400">{a.auditor}</td>
                                    <td className="py-3 text-slate-400">{a.scheduled_date?.split('T')[0]}</td>
                                    <td className="py-3"><span className="status-badge status-active">{a.status}</span></td>
                                    <td className="py-3 text-right">
                                        {a.file_ref ? (
                                            <span className="text-xs text-green-400">File attached</span>
                                        ) : (
                                            <label className="cursor-pointer text-xs flex items-center justify-end gap-1 text-indigo-400 hover:text-indigo-300">
                                                <Upload size={14} /> Upload
                                                <input type="file" className="hidden" onChange={(e) => {
                                                    if (e.target.files && e.target.files[0]) {
                                                        handleFileUpload(a.id, e.target.files[0])
                                                    }
                                                }} />
                                            </label>
                                        )}
                                    </td>
                                </tr>
                            ))}
                            {audits.length === 0 && <tr><td colSpan={5} className="py-8 text-center text-slate-500">No audits scheduled</td></tr>}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Compliance Issues */}
            {activeTab === 'issues' && (
                <div className="glass rounded-2xl p-6">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-left text-slate-500 border-b border-slate-800">
                                <th className="pb-3 font-medium">Description</th>
                                <th className="pb-3 font-medium">Severity</th>
                                <th className="pb-3 font-medium">Due Date</th>
                                <th className="pb-3 font-medium">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {issues.map(i => (
                                <tr key={i.id} className="table-row border-b border-slate-800/50">
                                    <td className="py-3 text-white max-w-xs truncate">{i.description}</td>
                                    <td className="py-3">
                                        <span className="text-xs font-medium capitalize" style={{ color: severityColor[i.severity] || '#587b92' }}>
                                            ● {i.severity}
                                        </span>
                                    </td>
                                    <td className="py-3 text-slate-400">{i.due_date?.split('T')[0]}</td>
                                    <td className="py-3"><span className={`status-badge ${statusClass[i.status] || 'status-pending'}`}>{i.status}</span></td>
                                </tr>
                            ))}
                            {issues.length === 0 && <tr><td colSpan={4} className="py-8 text-center text-slate-500">No compliance issues</td></tr>}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    )
}
