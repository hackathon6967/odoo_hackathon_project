import { useEffect, useState } from 'react'
import { Users, UserPlus } from 'lucide-react'
import api from '../../api/client'
import toast from 'react-hot-toast'
import { useAuth } from '../../context/AuthContext'

export default function AdminPage() {
    const { user } = useAuth()
    const [employees, setEmployees] = useState<any[]>([])
    const [newEmployee, setNewEmployee] = useState({ full_name: '', email: '', password: '' })

    useEffect(() => {
        if (user?.role === 'admin') {
            api.get('/core/users').then(r => setEmployees(r.data)).catch(() => {})
        }
    }, [user?.role])

    async function createEmployee() {
        try {
            const { data } = await api.post('/core/users', { ...newEmployee, role: 'employee' })
            setEmployees(current => [...current, data])
            setNewEmployee({ full_name: '', email: '', password: '' })
            toast.success('Employee account created')
        } catch (error: any) { toast.error(error.response?.data?.detail || 'Could not create employee') }
    }

    if (user?.role !== 'admin') {
        return <div className="p-8 text-white">Access Denied</div>
    }

    return (
        <div className="min-h-screen p-8 page-bg">
            <div className="max-w-4xl mx-auto">
                <div className="flex items-center gap-3 mb-8">
                    <div className="w-10 h-10 rounded-xl bg-slate-700 flex items-center justify-center">
                        <Users size={20} className="text-slate-300" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-[#12344d]" style={{ fontFamily: 'Outfit' }}>Accounts Management</h1>
                        <p className="text-slate-500 text-sm">Create and manage employee accounts</p>
                    </div>
                </div>

                <section className="glass rounded-2xl p-6 mb-8 border border-[#1599df36]">
                    <h2 className="text-[#12344d] font-semibold mb-4 flex items-center gap-2"><UserPlus size={16} className="text-[#1599df]" /> Create New Account</h2>
                    <div className="grid sm:grid-cols-3 gap-3 mb-5">
                        <input className="input" placeholder="Full name" value={newEmployee.full_name} onChange={e => setNewEmployee(v => ({ ...v, full_name: e.target.value }))} />
                        <input className="input" placeholder="Email" type="email" value={newEmployee.email} onChange={e => setNewEmployee(v => ({ ...v, email: e.target.value }))} />
                        <input className="input" placeholder="Temporary password" type="password" value={newEmployee.password} onChange={e => setNewEmployee(v => ({ ...v, password: e.target.value }))} />
                    </div>
                    <button className="btn btn-primary w-full sm:w-auto" disabled={!newEmployee.full_name || !newEmployee.email || !newEmployee.password} onClick={createEmployee}>
                        Add Employee
                    </button>
                </section>

                <section className="glass rounded-2xl p-6 border border-[#1599df36]">
                    <h2 className="text-[#12344d] font-semibold mb-4">All Employee Accounts</h2>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead>
                                <tr className="border-b border-slate-300 text-slate-500">
                                    <th className="pb-2 font-medium">Name</th>
                                    <th className="pb-2 font-medium">Email</th>
                                    <th className="pb-2 font-medium">Role</th>
                                    <th className="pb-2 text-right font-medium">XP / Points</th>
                                </tr>
                            </thead>
                            <tbody>
                                {employees.map(employee => (
                                    <tr key={employee.id} className="table-row border-b border-slate-200">
                                        <td className="py-3 text-[#12344d] font-medium">{employee.full_name}</td>
                                        <td className="py-3 text-slate-600">{employee.email}</td>
                                        <td className="py-3 capitalize text-slate-500 text-xs">
                                            <span className="bg-[#1599df15] text-[#0878b8] px-2 py-1 rounded">{employee.role}</span>
                                        </td>
                                        <td className="py-3 text-right font-bold text-[#0878b8]">{employee.xp} / {employee.points}</td>
                                    </tr>
                                ))}
                                {employees.length === 0 && <tr><td colSpan={4} className="py-8 text-center text-slate-400">No accounts found</td></tr>}
                            </tbody>
                        </table>
                    </div>
                </section>
            </div>
        </div>
    )
}
