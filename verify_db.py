from mattersim_dt.database import db_manager, System, SimulationResult
import pandas as pd

def verify():
    db_manager.init_db()
    session = db_manager.get_session()
    
    if not session:
        print("❌ Could not get DB session")
        return

    systems = session.query(System).all()
    results = session.query(SimulationResult).all()
    
    print(f"✅ Found {len(systems)} systems in DB:")
    for s in systems:
        print(f"   - {s.name} (ID: {s.id})")

    print(f"✅ Found {len(results)} simulation results in DB.")
    if len(results) > 0:
        print("   Sample result:")
        r = results[0]
        print(f"   - {r.formula}: {r.energy_per_atom:.4f} eV/atom (MD: {r.md_performed})")

    session.close()

if __name__ == "__main__":
    verify()
