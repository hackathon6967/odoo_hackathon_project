import { useEffect, useState } from 'react'
import { Trophy, Zap, Crown } from 'lucide-react'
import api from '../../api/client'
import toast from 'react-hot-toast'
import { useAuth } from '../../context/AuthContext'

function getRankName(xp: number) {
    if (xp < 100) return 'Novice'
    if (xp < 300) return 'Bronze'
    if (xp < 600) return 'Silver'
    if (xp < 1000) return 'Gold'
    return 'Platinum'
}

export default function GamificationPage() {
    const { user, refreshUser } = useAuth()
    const [challenges, setChallenges] = useState<any[]>([])
    const [rewards, setRewards] = useState<any[]>([])
    const [_badges, setBadges] = useState<any[]>([])
    const [leaderboard, setLeaderboard] = useState<any[]>([])
    const [myBadges, setMyBadges] = useState<any[]>([])
    const [activeTab, setActiveTab] = useState<'challenges' | 'rewards' | 'leaderboard' | 'badges'>('challenges')

    useEffect(() => {
        Promise.all([
            api.get('/gamification/challenges'),
            api.get('/gamification/rewards'),
            api.get('/gamification/badges'),
            api.get('/gamification/leaderboard'),
            api.get('/gamification/my-badges'),
        ]).then(([c, r, b, l, mb]) => {
            setChallenges(c.data); setRewards(r.data); setBadges(b.data)
            setLeaderboard(l.data); setMyBadges(mb.data)
        }).catch(() => { })
    }, [])

    async function joinChallenge(id: string) {
        try {
            const formData = new FormData()
            formData.append('proof_file', '')
            await api.post(`/gamification/challenges/${id}/participate`, formData)
            toast.success('🎯 Joined challenge!')
        } catch (e: any) { toast.error(e.response?.data?.detail || 'Failed') }
    }

    async function redeemReward(id: string) {
        try {
            await api.post(`/gamification/rewards/${id}/redeem`)
            toast.success('🎁 Reward redeemed!')
            const r = await api.get('/gamification/rewards')
            setRewards(r.data)
            await refreshUser()
        } catch (e: any) { toast.error(e.response?.data?.detail || 'Not enough points or out of stock') }
    }

    const diffColor: Record<string, string> = { easy: '#1599df', medium: '#1599df', hard: '#ef4444' }

    return (
        <div className="theme-gamification min-h-screen p-8 page-bg">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-[#1599df]/20 flex items-center justify-center">
                        <Trophy size={20} className="text-[#1599df]" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>Gamification</h1>
                        <p className="text-slate-400 text-sm">Challenges, XP, badges & rewards</p>
                    </div>
                </div>
                {/* XP/Points display */}
                <div className="glass rounded-xl px-5 py-3 flex items-center gap-6 border border-[#1599df]/20">
                    <div className="text-center">
                        <div className="text-[#1599df] font-bold text-xl">{user?.xp || 0}</div>
                        <div className="text-slate-500 text-xs">XP</div>
                    </div>
                    <div className="w-px h-8 bg-slate-700" />
                    <div className="text-center">
                        <div className="text-amber-400 font-bold text-xl">{user?.points || 0}</div>
                        <div className="text-slate-500 text-xs">Points</div>
                    </div>
                    <div className="w-px h-8 bg-slate-700" />
                    <div className="text-center">
                        <div className="text-[#56c7ff] font-bold text-xl">{myBadges.length}</div>
                        <div className="text-slate-500 text-xs">Badges</div>
                    </div>
                </div>
            </div>

            {/* XP bar */}
            <div className="glass rounded-2xl p-5 mb-6 border border-[#1599df]/10">
                <div className="flex justify-between text-sm mb-2">
                    <span className="text-slate-400 flex items-center gap-1"><Zap size={14} className="text-[#1599df]" /> XP Progress - <span className="font-bold text-[#56c7ff]">{getRankName(user?.xp || 0)}</span></span>
                    <span className="text-[#1599df] font-medium">{user?.xp || 0} / 1000 XP</span>
                </div>
                <div className="h-3 bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full rounded-full xp-bar-inner"
                        style={{
                            '--xp-pct': `${Math.min(100, ((user?.xp || 0) / 1000) * 100)}%`,
                            background: 'linear-gradient(90deg, #0878b8, #1599df, #56c7ff)'
                        } as React.CSSProperties} />
                </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-2 mb-6">
                {([
                    { key: 'challenges', icon: '⚡', label: 'Challenges' },
                    { key: 'rewards', icon: '🎁', label: 'Rewards' },
                    { key: 'leaderboard', icon: '🏆', label: 'Leaderboard' },
                    { key: 'badges', icon: '🏅', label: 'My Badges' },
                ] as const).map(({ key, icon, label }) => (
                    <button key={key} onClick={() => setActiveTab(key)}
                        className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${activeTab === key
                            ? 'bg-[#1599df]/20 text-[#1599df] border border-[#1599df]/30'
                            : 'text-slate-400 hover:text-white'}`}>
                        {icon} {label}
                    </button>
                ))}
            </div>

            {/* Challenges */}
            {activeTab === 'challenges' && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {challenges.map(c => (
                        <div key={c.id} className="glass rounded-2xl p-5 border border-[#1599df]/10 hover:border-[#1599df]/30 transition-all">
                            <div className="flex items-start justify-between mb-3">
                                <span className="text-xs font-medium capitalize px-2 py-0.5 rounded-full"
                                    style={{ background: `${diffColor[c.difficulty]}22`, color: diffColor[c.difficulty] }}>
                                    {c.difficulty}
                                </span>
                                <span className="status-badge" style={{ background: 'rgba(21,153,223,0.15)', color: '#56c7ff' }}>
                                    {c.status}
                                </span>
                            </div>
                            <h3 className="text-white font-semibold mb-1">{c.title}</h3>
                            {c.deadline && <p className="text-slate-500 text-xs">⏰ Deadline: {c.deadline?.split('T')[0]}</p>}
                            <div className="flex items-center justify-between mt-4">
                                <span className="text-[#1599df] font-bold text-lg">⚡ {c.xp} XP</span>
                                {c.status === 'Active' && (
                                    <button onClick={() => joinChallenge(c.id)}
                                        className="px-4 py-1.5 rounded-xl text-xs font-semibold transition-all"
                                        style={{ background: 'linear-gradient(135deg,#1599df,#0878b8)', color: 'white' }}>
                                        Join Challenge
                                    </button>
                                )}
                            </div>
                        </div>
                    ))}
                    {challenges.length === 0 && (
                        <p className="text-slate-500 py-16 text-center col-span-3">No challenges yet</p>
                    )}
                </div>
            )}

            {/* Rewards */}
            {activeTab === 'rewards' && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {rewards.map(r => (
                        <div key={r.id} className="glass rounded-2xl p-5 border border-amber-500/10 hover:border-amber-500/30 transition-all">
                            <div className="text-4xl text-center mb-3">🎁</div>
                            <h3 className="text-white font-semibold text-center mb-1">{r.name}</h3>
                            <p className="text-slate-500 text-xs text-center mb-3">{r.description}</p>
                            <div className="flex items-center justify-between">
                                <div>
                                    <span className="text-amber-400 font-bold">{r.points_required} pts</span>
                                    <span className="text-slate-600 text-xs ml-2">({r.stock} left)</span>
                                </div>
                                <button onClick={() => redeemReward(r.id)} disabled={r.stock === 0}
                                    className="px-3 py-1.5 rounded-xl text-xs font-semibold transition-all disabled:opacity-40"
                                    style={{ background: r.stock > 0 ? 'linear-gradient(135deg, var(--gold), #0878b8)' : '#374151', color: 'white' }}>
                                    {r.stock > 0 ? 'Redeem' : 'Out of stock'}
                                </button>
                            </div>
                        </div>
                    ))}
                    {rewards.length === 0 && <p className="text-slate-500 py-16 text-center col-span-3">No rewards available</p>}
                </div>
            )}

            {/* Leaderboard */}
            {activeTab === 'leaderboard' && (
                <div className="glass rounded-2xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-white font-semibold flex items-center gap-2"><Crown size={16} className="text-amber-400" /> Top Performers</h3>
                        {(() => {
                            const myRankIndex = leaderboard.findIndex(u => u.user_id === user?.id)
                            return myRankIndex >= 0 ? (
                                <div className="text-sm bg-[#1599df]/10 text-[#56c7ff] px-3 py-1 rounded-lg font-medium border border-[#1599df]/20">
                                    Your Rank: #{leaderboard[myRankIndex].rank} ({getRankName(user?.xp || 0)})
                                </div>
                            ) : null
                        })()}
                    </div>
                    <div className="space-y-2">
                        {leaderboard.map((u, i) => (
                            <div key={u.user_id}
                                className={`flex items-center gap-4 p-3 rounded-xl transition-all ${u.user_id === user?.id ? 'border border-[#1599df]/40 bg-[#1599df]/10' : i < 3 ? 'border' : 'border border-transparent'}
                     ${i === 0 && u.user_id !== user?.id ? 'border-yellow-500/40 bg-yellow-500/5' : i === 1 && u.user_id !== user?.id ? 'border-slate-400/30 bg-slate-400/5' : i === 2 && u.user_id !== user?.id ? 'border-amber-700/30 bg-amber-700/5' : u.user_id !== user?.id ? 'hover:bg-white/4' : ''}`}>
                                <div className="w-8 text-center font-bold text-lg">
                                    {i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : <span className="text-slate-500 text-sm">#{u.rank}</span>}
                                </div>
                                <div className="w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm"
                                    style={{ background: 'linear-gradient(135deg, #1599df, #0878b8)' }}>
                                    {u.full_name?.[0] || 'U'}
                                </div>
                                <div className="flex-1">
                                    <p className="text-white text-sm font-medium">{u.full_name} {u.user_id === user?.id && '(You)'}</p>
                                </div>
                                <div className="text-right">
                                    <p className="text-[#1599df] font-bold">⚡ {u.xp} XP - {getRankName(u.xp)}</p>
                                    <p className="text-amber-400 text-xs">{u.points} pts</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* My Badges */}
            {activeTab === 'badges' && (
                <div>
                    {myBadges.length === 0 ? (
                        <div className="glass rounded-2xl p-12 text-center">
                            <div className="text-6xl mb-4">🏅</div>
                            <p className="text-white font-semibold text-lg mb-2">No badges yet</p>
                            <p className="text-slate-400 text-sm">Complete challenges to earn your first badge!</p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            {myBadges.map(b => (
                                <div key={b.badge_id} className="glass rounded-2xl p-5 text-center border border-pink-500/20">
                                    <div className="text-5xl mb-3 badge-icon" style={{ '--accent': '#1599df' } as any}>{b.icon || '🏅'}</div>
                                    <h3 className="text-white font-semibold text-sm">{b.name}</h3>
                                    <p className="text-slate-500 text-xs mt-1">{b.awarded_at?.split('T')[0]}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
