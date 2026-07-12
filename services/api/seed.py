#!/usr/bin/env python
"""
Seed script: creates admin user, sample departments, emission factors,
an ESG config, challenges, rewards, badges, CSR activities, audits,
policies, trainings, diversity metrics, and carbon transactions.
Run once after migrations: python seed.py
"""
import os, uuid, asyncio, random
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://ecosphere:ecosphere_pass@localhost:5432/ecosphere_db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
pwd = CryptContext(schemes=["bcrypt"])


async def seed():
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        # Clear all existing data
        await db.execute(text("""
            TRUNCATE TABLE users, departments, categories, esg_config, emission_factors,
            badges, rewards, challenges, csr_activities, employee_participations,
            carbon_transactions, compliance_issues, audits, esg_policies,
            policy_acknowledgements, department_scores, training_modules, training_completions,
            diversity_metrics, environmental_goals, challenge_participations,
            employee_badges, reward_redemptions, report_jobs,
            notifications, notification_settings
            CASCADE
        """))

        now = datetime.now(timezone.utc)
        hashed_pw = pwd.hash("admin123")

        # ── Departments ───────────────────────────────────────────
        dept_ops = str(uuid.uuid4())
        dept_tech = str(uuid.uuid4())
        dept_hr = str(uuid.uuid4())
        dept_fin = str(uuid.uuid4())

        await db.execute(text("""
            INSERT INTO departments (id, name, code, employee_count) VALUES
            (:d1, 'Operations', 'OPS', 35),
            (:d2, 'Technology', 'TECH', 22),
            (:d3, 'Human Resources', 'HR', 12),
            (:d4, 'Finance', 'FIN', 18)
        """), {"d1": dept_ops, "d2": dept_tech, "d3": dept_hr, "d4": dept_fin})

        # ── Users ─────────────────────────────────────────────────
        admin_id = str(uuid.uuid4())
        manager_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        emp2_id = str(uuid.uuid4())
        emp3_id = str(uuid.uuid4())
        emp4_id = str(uuid.uuid4())
        emp5_id = str(uuid.uuid4())

        await db.execute(text("""
            INSERT INTO users (id, email, full_name, hashed_password, role, department_id, xp, points) VALUES
            (:a, 'admin@ecosphere.app', 'Admin User', :pw, 'admin', :d1, 720, 1500),
            (:m, 'manager@ecosphere.app', 'Manager User', :pw, 'manager', :d2, 480, 800),
            (:e1, 'employee@ecosphere.app', 'Employee User', :pw, 'employee', :d1, 210, 450),
            (:e2, 'sarah.chen@ecosphere.app', 'Sarah Chen', :pw, 'employee', :d2, 350, 600),
            (:e3, 'james.wilson@ecosphere.app', 'James Wilson', :pw, 'employee', :d3, 150, 200),
            (:e4, 'priya.sharma@ecosphere.app', 'Priya Sharma', :pw, 'employee', :d4, 90, 150),
            (:e5, 'alex.rodriguez@ecosphere.app', 'Alex Rodriguez', :pw, 'employee', :d1, 560, 900)
        """), {"a": admin_id, "m": manager_id, "e1": emp_id, "e2": emp2_id,
               "e3": emp3_id, "e4": emp4_id, "e5": emp5_id,
               "pw": hashed_pw, "d1": dept_ops, "d2": dept_tech, "d3": dept_hr, "d4": dept_fin})

        # ── Categories ────────────────────────────────────────────
        cat_env = str(uuid.uuid4())
        cat_social = str(uuid.uuid4())
        cat_gov = str(uuid.uuid4())
        cat_community = str(uuid.uuid4())

        await db.execute(text("""
            INSERT INTO categories (id, name, type) VALUES
            (:c1, 'Sustainability', 'environmental'),
            (:c2, 'Social Impact', 'social'),
            (:c3, 'Compliance', 'governance'),
            (:c4, 'Community Service', 'social')
        """), {"c1": cat_env, "c2": cat_social, "c3": cat_gov, "c4": cat_community})

        # ── ESG Config ────────────────────────────────────────────
        await db.execute(text("""
            INSERT INTO esg_config (id, weight_environmental, weight_social, weight_governance,
              auto_emission_calc, evidence_required, badge_auto_award)
            VALUES (:id, 0.40, 0.30, 0.30, true, true, true)
        """), {"id": str(uuid.uuid4())})

        # ── Emission Factors ──────────────────────────────────────
        ef_elec = str(uuid.uuid4())
        ef_gas = str(uuid.uuid4())
        ef_diesel = str(uuid.uuid4())
        ef_air = str(uuid.uuid4())

        for ef_data in [
            (ef_elec, "electricity", "kWh", 0.233),
            (ef_gas, "natural_gas", "m3", 1.9),
            (ef_diesel, "diesel", "litre", 2.68),
            (ef_air, "air_travel", "km", 0.255),
        ]:
            await db.execute(text("""
                INSERT INTO emission_factors (id, source_type, unit, co2e_per_unit, effective_date)
                VALUES (:id, :st, :u, :c, :d)
            """), {"id": ef_data[0], "st": ef_data[1], "u": ef_data[2], "c": ef_data[3],
                   "d": datetime(2025,1,1,tzinfo=timezone.utc)})

        # ── Badges ────────────────────────────────────────────────
        for b in [
            (str(uuid.uuid4()), "🌱 Green Starter", {"metric": "xp", "threshold": 100}, "🌱"),
            (str(uuid.uuid4()), "⚡ XP Champion", {"metric": "xp", "threshold": 500}, "⚡"),
            (str(uuid.uuid4()), "🏆 Challenge Master", {"metric": "challenges_completed", "threshold": 5}, "🏆"),
            (str(uuid.uuid4()), "🌍 Eco Warrior", {"metric": "xp", "threshold": 300}, "🌍"),
            (str(uuid.uuid4()), "💎 Platinum Leader", {"metric": "xp", "threshold": 1000}, "💎"),
        ]:
            await db.execute(text("""
                INSERT INTO badges (id, name, unlock_rule, icon) VALUES (:id, :n, CAST(:r AS jsonb), :i)
            """), {"id": b[0], "n": b[1], "r": str(b[2]).replace("'", '"'), "i": b[3]})

        # ── Rewards ───────────────────────────────────────────────
        for r in [
            (str(uuid.uuid4()), "☕ Coffee Voucher", "Premium coffee from the office café", 100, 50),
            (str(uuid.uuid4()), "📚 Learning Subscription", "1-month Coursera/Udemy access", 300, 20),
            (str(uuid.uuid4()), "🌴 Extra Day Off", "One additional paid day off", 800, 8),
            (str(uuid.uuid4()), "🎧 Noise-Cancelling Headphones", "Sony WH-1000XM5", 1500, 3),
            (str(uuid.uuid4()), "🌿 Plant a Tree", "We plant a tree in your name", 50, 100),
        ]:
            await db.execute(text("""
                INSERT INTO rewards (id, name, description, points_required, stock) VALUES (:id, :n, :desc, :p, :s)
            """), {"id": r[0], "n": r[1], "desc": r[2], "p": r[3], "s": r[4]})

        # ── Challenges ────────────────────────────────────────────
        for c in [
            (str(uuid.uuid4()), "Reduce Office Energy by 10%", "Track and reduce your department's monthly electricity usage", "hard", 200),
            (str(uuid.uuid4()), "Complete a CSR Activity", "Participate in any community service event", "easy", 50),
            (str(uuid.uuid4()), "Submit ESG Training Certificate", "Complete an ESG-related online course", "medium", 100),
            (str(uuid.uuid4()), "Zero Waste Week", "Go one full work week without generating non-recyclable waste", "hard", 150),
            (str(uuid.uuid4()), "Carpool Champion", "Organize carpooling for your team for a month", "medium", 120),
            (str(uuid.uuid4()), "Green Innovation Pitch", "Submit a sustainability improvement proposal", "easy", 80),
        ]:
            await db.execute(text("""
                INSERT INTO challenges (id, title, description, difficulty, xp, status, created_by_id, deadline)
                VALUES (:id, :t, :desc, :d, :x, 'Active', :by, :deadline)
            """), {"id": c[0], "t": c[1], "desc": c[2], "d": c[3], "x": c[4], "by": admin_id,
                   "deadline": now + timedelta(days=random.randint(14, 60))})

        # ── CSR Activities (8 varied) ─────────────────────────────
        csr_activities = [
            (str(uuid.uuid4()), "Community Tree Planting Drive", cat_social, dept_ops, 100, now + timedelta(days=7)),
            (str(uuid.uuid4()), "Beach Cleanup Campaign", cat_community, dept_tech, 80, now + timedelta(days=14)),
            (str(uuid.uuid4()), "Food Bank Volunteer Day", cat_community, dept_hr, 90, now + timedelta(days=10)),
            (str(uuid.uuid4()), "STEM Mentorship Program", cat_social, dept_tech, 120, now + timedelta(days=21)),
            (str(uuid.uuid4()), "Carbon Offset Fundraiser", cat_env, dept_fin, 110, now + timedelta(days=30)),
            (str(uuid.uuid4()), "Blood Donation Camp", cat_community, dept_ops, 75, now + timedelta(days=5)),
            (str(uuid.uuid4()), "Elderly Care Visit", cat_social, dept_hr, 85, now + timedelta(days=12)),
            (str(uuid.uuid4()), "Recycling Workshop", cat_env, dept_ops, 60, now + timedelta(days=18)),
        ]
        for csr in csr_activities:
            await db.execute(text("""
                INSERT INTO csr_activities (id, title, category_id, department_id, date, points_reward)
                VALUES (:id, :title, :cat, :dept, :d, :pts)
            """), {"id": csr[0], "title": csr[1], "cat": csr[2], "dept": csr[3], "pts": csr[4], "d": csr[5]})

        # ── Carbon Transactions (spread across depts and months) ──
        ef_ids = [ef_elec, ef_gas, ef_diesel, ef_air]
        modules = ["electricity", "transport", "heating", "purchase", "manufacturing"]
        dept_ids_list = [dept_ops, dept_tech, dept_hr, dept_fin]

        for dept in dept_ids_list:
            for month_offset in range(6):
                for _ in range(random.randint(3, 7)):
                    ef = random.choice(ef_ids)
                    qty = round(random.uniform(20, 800), 2)
                    dept_factor = {dept_ops: 1.2, dept_tech: 0.6, dept_hr: 0.3, dept_fin: 0.8}[dept]
                    co2e = round(qty * random.uniform(0.1, 0.5) * dept_factor, 2)
                    tx_date = now - timedelta(days=month_offset * 30 + random.randint(0, 29))
                    await db.execute(text("""
                        INSERT INTO carbon_transactions (id, department_id, source_module, emission_factor_id, quantity, co2e_calculated, transaction_date, notes, created_by_id)
                        VALUES (:id, :dept, :mod, :ef, :qty, :co2e, :dt, :notes, :by)
                    """), {
                        "id": str(uuid.uuid4()), "dept": dept, "mod": random.choice(modules), "ef": ef,
                        "qty": qty, "co2e": co2e, "dt": tx_date,
                        "notes": "Auto-generated emission log", "by": admin_id
                    })

        # ── Compliance Issues ─────────────────────────────────────
        severities = ["low", "medium", "high", "critical"]
        issue_descriptions = [
            "Missing fire safety inspection report",
            "Data privacy policy not updated for GDPR",
            "Waste disposal permit expired",
            "Employee safety training overdue",
            "Chemical storage labeling non-compliant",
            "Air quality monitoring gap detected",
            "Supplier code of conduct not signed",
            "Emergency evacuation drill not conducted",
        ]
        all_users = [admin_id, manager_id, emp_id, emp2_id, emp3_id]
        for i, desc in enumerate(issue_descriptions):
            status = random.choice(["Resolved", "Resolved", "Open", "Open", "Overdue"])
            await db.execute(text("""
                INSERT INTO compliance_issues (id, severity, description, status, due_date, owner_id,
                    resolution_notes, created_at)
                VALUES (:id, :sev, :desc, :status, :due, :owner, :notes, :created)
            """), {
                "id": str(uuid.uuid4()), "sev": severities[i % len(severities)],
                "desc": desc, "status": status,
                "due": now + timedelta(days=random.randint(-10, 30)),
                "owner": all_users[i % len(all_users)],
                "notes": "Resolved and documented" if status == "Resolved" else None,
                "created": now - timedelta(days=random.randint(5, 60))
            })

        # ── ESG Policies ──────────────────────────────────────────
        policies = [
            ("Environmental Protection Policy", "2.1", "Active"),
            ("Diversity & Inclusion Charter", "1.3", "Active"),
            ("Anti-Corruption Guidelines", "3.0", "Active"),
            ("Sustainable Procurement Policy", "1.0", "Draft"),
        ]
        for title, version, status in policies:
            await db.execute(text("""
                INSERT INTO esg_policies (id, title, version, status, effective_date, requires_acknowledgement)
                VALUES (:id, :title, :ver, :status, :eff, true)
            """), {"id": str(uuid.uuid4()), "title": title, "ver": version, "status": status,
                   "eff": now - timedelta(days=random.randint(30, 365))})

        # ── Audits ────────────────────────────────────────────────
        audit_data = [
            ("Q2 2025 Environmental Audit", dept_ops, "Deloitte ESG", "completed"),
            ("Annual Safety Compliance", dept_tech, "SGS Auditing", "scheduled"),
            ("ISO 14001 Recertification", dept_ops, "Bureau Veritas", "in_progress"),
            ("Social Impact Assessment", dept_hr, "KPMG Advisory", "scheduled"),
        ]
        for title, dept, auditor, status in audit_data:
            await db.execute(text("""
                INSERT INTO audits (id, title, department_id, auditor, scheduled_date, status)
                VALUES (:id, :title, :dept, :auditor, :date, :status)
            """), {"id": str(uuid.uuid4()), "title": title, "dept": dept, "auditor": auditor,
                   "date": now + timedelta(days=random.randint(-30, 60)), "status": status})

        # ── Trainings ─────────────────────────────────────────────
        training_modules = [
            ("ESG Fundamentals", "Core concepts of Environmental, Social, and Governance reporting", True, 50),
            ("Carbon Footprint Calculation", "Learn to measure and report organizational carbon emissions", True, 75),
            ("Diversity & Inclusion Workshop", "Building inclusive workplace cultures", False, 40),
            ("Ethical Supply Chain", "Ensuring sustainability across the supply chain", False, 60),
            ("Waste Management Best Practices", "Strategies for reducing organizational waste", True, 45),
        ]
        for title, desc, mandatory, xp in training_modules:
            await db.execute(text("""
                INSERT INTO training_modules (id, title, description, is_mandatory, xp_reward)
                VALUES (:id, :title, :desc, :mandatory, :xp)
            """), {"id": str(uuid.uuid4()), "title": title, "desc": desc, "mandatory": mandatory, "xp": xp})

        # ── Diversity Metrics ─────────────────────────────────────
        await db.execute(text("""
            INSERT INTO diversity_metrics (id, department_id, period,
                gender_male, gender_female, gender_other,
                tenure_0_1, tenure_1_3, tenure_3_5, tenure_5_plus)
            VALUES
            (:id1, :d1, '2025-07', 18, 14, 3, 5, 12, 10, 8),
            (:id2, :d2, '2025-07', 12, 8, 2, 4, 8, 6, 4),
            (:id3, :d3, '2025-07', 4, 7, 1, 2, 4, 3, 3),
            (:id4, :d4, '2025-07', 9, 8, 1, 3, 6, 5, 4)
        """), {"id1": str(uuid.uuid4()), "id2": str(uuid.uuid4()),
               "id3": str(uuid.uuid4()), "id4": str(uuid.uuid4()),
               "d1": dept_ops, "d2": dept_tech, "d3": dept_hr, "d4": dept_fin})

        # ── Environmental Goals ───────────────────────────────────
        goals = [
            ("Reduce CO2 Emissions", "co2e_reduction", 5000, 3200, "kg", dept_ops),
            ("Energy Efficiency Target", "energy_efficiency", 100, 72, "kWh saved/month", dept_tech),
            ("Zero Waste by 2026", "waste_reduction", 100, 45, "% reduction", dept_hr),
        ]
        for title, metric, target, current, unit, dept in goals:
            await db.execute(text("""
                INSERT INTO environmental_goals (id, department_id, metric, target_value, current_value, unit, target_date)
                VALUES (:id, :dept, :metric, :target, :current, :unit, :target_date)
            """), {"id": str(uuid.uuid4()), "dept": dept, "metric": title,
                   "target": target, "current": current, "unit": unit,
                   "target_date": now + timedelta(days=180)})

        # ── Sample Employee Participations (for scoring) ──────────
        csr_ids = [c[0] for c in csr_activities]
        participation_users = [emp_id, emp2_id, emp3_id, emp4_id, emp5_id, manager_id]
        for user_id in participation_users[:4]:
            activity = random.choice(csr_ids)
            await db.execute(text("""
                INSERT INTO employee_participations (id, activity_id, employee_id, approval_status, points_earned, completion_date)
                VALUES (:id, :act, :emp, 'Approved', :pts, :date)
            """), {"id": str(uuid.uuid4()), "act": activity, "emp": user_id,
                   "pts": random.randint(60, 120), "date": now - timedelta(days=random.randint(1, 30))})

        await db.commit()
        print("✅ Database seeded successfully!")
        print("   Admin:    admin@ecosphere.app / admin123 (1500 pts)")
        print("   Manager:  manager@ecosphere.app / admin123 (800 pts)")
        print("   Employee: employee@ecosphere.app / admin123 (450 pts)")
        print("   + 4 additional employee accounts")

        # Run compute_scores synchronously to populate scorecard
        print("⏳ Computing ESG scores...")
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), "..", "worker"))
        try:
            from worker import compute_scores
            compute_scores(now.strftime("%Y-%m"))
            print("✅ Scores computed successfully!")
        except Exception as e:
            print("⚠️ Could not compute scores automatically during seed:", e)


if __name__ == "__main__":
    asyncio.run(seed())
