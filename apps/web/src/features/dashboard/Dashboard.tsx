import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Leaf, Users, Shield, Trophy, BarChart3, TrendingUp, Award, ArrowUpRight } from 'lucide-react'
import api from '../../api/client'
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts'

export default function Dashboard() {
    const navigate = useNavigate()
    const [scores, setScores] = useState<any>(null)
    const [trainingStats, setTrainingStats] = useState<any>(null)
    const [loading, setLoading] = useState(true)
    useEffect(() => { api.get('/scoring/overall-esg').then(r => setScores(r.data)).catch(() => {}); api.get('/social/trainings/completion-stats').then(r => setTrainingStats(r.data)).catch(() => {}).finally(() => setLoading(false)) }, [])
    const radarData = scores ? [{ subject: 'ENVIRONMENT', A: scores.environmental_avg || 0 }, { subject: 'SOCIAL', A: scores.social_avg || 0 }, { subject: 'GOVERNANCE', A: scores.governance_avg || 0 }] : []
    const trendData = [{ month: 'JAN', score: 62 }, { month: 'FEB', score: 65 }, { month: 'MAR', score: 68 }, { month: 'APR', score: 71 }, { month: 'MAY', score: 74 }, { month: 'JUN', score: 77 }, { month: 'JUL', score: scores?.overall_esg_score || 80 }]
    const modules = [
        { numeral: 'I', label: 'Environmental', icon: Leaf, to: '/environmental', desc: 'Carbon & goals' },
        { numeral: 'II', label: 'Social', icon: Users, to: '/social', desc: 'People & purpose' },
        { numeral: 'III', label: 'Governance', icon: Shield, to: '/governance', desc: 'Policies & trust' },
        { numeral: 'IV', label: 'Honours', icon: Trophy, to: '/gamification', desc: 'Challenges & rewards' },
        { numeral: 'V', label: 'Scorecard', icon: BarChart3, to: '/scoring', desc: 'Reports & analysis' },
    ]
    const pillars = [{ numeral: 'I', label: 'Environmental', value: scores?.environmental_avg }, { numeral: 'II', label: 'Social', value: scores?.social_avg }, { numeral: 'III', label: 'Governance', value: scores?.governance_avg }]
    return <div className="min-h-full p-5 md:p-9 max-w-[1500px] mx-auto deco-reveal">
        <header className="mb-9 flex flex-wrap items-end justify-between gap-5 border-b border-[#1599df50] pb-6 relative">
            <div><p className="text-[#1599df] text-[10px] tracking-[.32em] uppercase mb-3">The Executive Ledger / {scores?.period || 'Current Period'}</p><h1 className="text-[#12344d] text-3xl md:text-4xl uppercase tracking-[.13em]" style={{ fontFamily: 'var(--font-display)' }}>ESG Scorecard</h1></div>
            <p className="text-[#888] text-xs tracking-wider max-w-xs leading-relaxed">A formal account of the organization&apos;s stewardship and progress.</p>
        </header>
        <section className="glass mb-7 p-7 md:p-9 overflow-hidden" style={{ background: 'radial-gradient(circle at 18% 100%, rgba(21,153,223,.20), transparent 33%), #ffffff' }}>
            <div className="absolute bottom-[-8rem] left-[-4rem] w-72 h-72 rounded-full border border-[#1599df38]" /><div className="relative flex flex-col lg:flex-row gap-8 lg:items-center justify-between">
                <div className="flex items-center gap-7"><div className="deco-diamond h-24 w-24 md:h-28 md:w-28 border-2 border-[#1599df] flex items-center justify-center shrink-0"><div className="text-center"><span className="block text-[#12344d] text-3xl md:text-4xl" style={{ fontFamily: 'var(--font-display)' }}>{loading ? '—' : Math.round(scores?.overall_esg_score || 0)}</span><span className="text-[#1599df] text-[9px] tracking-widest">OF 100</span></div></div><div><p className="text-[#1599df] text-[10px] uppercase tracking-[.22em] mb-2">Overall standing</p><h2 className="text-[#12344d] text-2xl uppercase tracking-wider" style={{ fontFamily: 'var(--font-display)' }}>The Grand Measure</h2><p className="text-[#888] text-xs mt-2">{scores?.departments_count || 0} departments recorded in this ledger.</p></div></div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-7 gap-y-5 border-t lg:border-t-0 lg:border-l border-[#1599df45] pt-6 lg:pt-0 lg:pl-8">{pillars.map(p => <div key={p.label}><span className="block text-[#1599df] text-sm" style={{ fontFamily: 'var(--font-display)' }}>{p.numeral}</span><strong className="block text-[#12344d] text-2xl mt-1">{loading ? '—' : Math.round(p.value || 0)}</strong><span className="text-[#888] text-[9px] tracking-[.12em] uppercase">{p.label}</span></div>)}<div><span className="block text-[#1599df] text-sm" style={{ fontFamily: 'var(--font-display)' }}>IV</span><strong className="block text-[#12344d] text-2xl mt-1">{trainingStats ? `${trainingStats.completion_rate}%` : '—'}</strong><span className="text-[#888] text-[9px] tracking-[.12em] uppercase">Training</span></div></div>
            </div>
        </section>
        <section className="grid grid-cols-1 xl:grid-cols-2 gap-7 mb-7">
            <div className="glass p-6"><div className="flex items-center gap-3 border-b border-[#1599df36] pb-4 mb-3"><Award size={17} className="text-[#1599df]" /><h3 className="text-[#12344d] text-sm uppercase tracking-[.16em]" style={{ fontFamily: 'var(--font-display)' }}>Pillar Balance</h3></div><ResponsiveContainer width="100%" height={250}><RadarChart data={radarData}><PolarGrid stroke="rgba(21,153,223,.28)" /><PolarAngleAxis dataKey="subject" tick={{ fill: '#b8b29e', fontSize: 10 }} /><Radar name="Score" dataKey="A" stroke="#1599df" fill="#1599df" fillOpacity={.18} /></RadarChart></ResponsiveContainer></div>
            <div className="glass p-6"><div className="flex items-center gap-3 border-b border-[#1599df36] pb-4 mb-3"><TrendingUp size={17} className="text-[#1599df]" /><h3 className="text-[#12344d] text-sm uppercase tracking-[.16em]" style={{ fontFamily: 'var(--font-display)' }}>Ascent, Year to Date</h3></div><ResponsiveContainer width="100%" height={250}><AreaChart data={trendData}><defs><linearGradient id="scoreGold" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#1599df" stopOpacity={.4} /><stop offset="95%" stopColor="#1599df" stopOpacity={0} /></linearGradient></defs><XAxis dataKey="month" tick={{ fill: '#888', fontSize: 10 }} axisLine={false} tickLine={false} /><YAxis tick={{ fill: '#888', fontSize: 10 }} axisLine={false} tickLine={false} domain={[0, 100]} /><Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #1599df', borderRadius: 0, color: '#12344d' }} /><Area type="monotone" dataKey="score" stroke="#1599df" strokeWidth={2} fill="url(#scoreGold)" /></AreaChart></ResponsiveContainer></div>
        </section>
        <section><div className="flex items-center gap-4 mb-5"><span className="w-12 h-px bg-[#1599df]" /><h2 className="text-[#1599df] text-xs uppercase tracking-[.25em]" style={{ fontFamily: 'var(--font-display)' }}>The Five Chambers</h2><span className="flex-1 h-px bg-[#1599df40]" /></div><div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">{modules.map(({ numeral, label, icon: Icon, to, desc }, i) => <button key={label} onClick={() => navigate(to)} className="glass p-5 text-left min-h-44 group hover:-translate-y-1 hover:border-[#1599df] transition-all" style={{ animationDelay: `${i * 75}ms` }}><div className="flex justify-between"><span className="text-[#1599df] text-xl" style={{ fontFamily: 'var(--font-display)' }}>{numeral}</span><ArrowUpRight size={16} className="text-[#888] group-hover:text-[#12344d]" /></div><div className="deco-diamond w-9 h-9 border border-[#1599df77] flex items-center justify-center mt-5 mb-5"><Icon size={16} className="text-[#1599df]" /></div><p className="text-[#12344d] text-xs uppercase tracking-[.14em]">{label}</p><p className="text-[#888] text-[11px] mt-2">{desc}</p></button>)}</div></section>
    </div>
}
