# src/mattersim_dt/pipeline.py
import pandas as pd
import os
import multiprocessing as mp
from pymatgen.core import Composition
import torch

from mattersim_dt.core import SimConfig
from mattersim_dt.builder import RandomAlloyMixer, TernaryAlloyMixer
from mattersim_dt.engine import get_calculator, StructureRelaxer, MDSimulator, BatchStructureRelaxer
from mattersim_dt.analysis import StabilityAnalyzer, MDAnalyzer, MaterialValidator
from mattersim_dt.miner import ExperimentalDataMiner, MaterialMiner, TernaryMaterialMiner
from mattersim_dt.database import db_manager, System, SimulationResult

def md_worker(args):
    """
    별도의 프로세스에서 독립적으로 MD를 실행하는 함수
    """
    formula, atoms, temperature, steps, device = args
    
    # 중요: 각 프로세스 내에서 계산기를 새로 로드해야 GPU 충돌이 없습니다.
    from mattersim_dt.engine import get_calculator, MDSimulator
    import os

    try:
        pid = os.getpid()
        print(f"     [PID {pid}] {formula} MD 시작...")

        calc = get_calculator(device=device)
        md_sim = MDSimulator(calculator=calc)

        # MD 실행
        final_atoms, traj_file = md_sim.run(
            atoms,
            temperature=temperature,
            steps=steps,
            save_interval=50
        )

        print(f"     [PID {pid}] {formula} MD 완료 ✓")
        return formula, traj_file, None

    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()[:200]}"
        print(f"     [PID {pid}] {formula} MD 실패: {str(e)}")
        return formula, None, error_msg

def save_intermediate_csv(csv_filename, detailed_data):
    if not detailed_data:
        return
    df_results = pd.DataFrame(detailed_data)
    df_results.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    print(f"   💾 중간 저장 완료: {csv_filename} ({len(detailed_data)}개 구조)")

def find_latest_result_csv():
    import glob
    csv_files = glob.glob("pipeline_results_*.csv")
    if not csv_files:
        return None
    csv_files.sort(reverse=True)
    return csv_files[0]

def load_completed_systems(csv_path):
    if not csv_path or not os.path.exists(csv_path):
        return set()
    try:
        df = pd.read_csv(csv_path)
        if 'system' not in df.columns:
            return set()
        completed_systems = set(df['system'].unique())
        print(f"   📂 기존 결과 파일 발견: {csv_path}")
        print(f"   ✅ 완료된 시스템: {len(completed_systems)}개")
        return completed_systems
    except Exception as e:
        print(f"   ⚠️  CSV 로드 중 오류: {e}")
        return set()

def load_existing_data(csv_path):
    if not csv_path or not os.path.exists(csv_path):
        return []
    try:
        df = pd.read_csv(csv_path)
        return df.to_dict('records')
    except Exception as e:
        print(f"   ⚠️  기존 데이터 로드 중 오류: {e}")
        return []

def load_element_pairs_from_csv(csv_path, max_systems=None):
    if not os.path.exists(csv_path):
        print(f"⚠️  CSV 파일을 찾을 수 없습니다: {csv_path}")
        return []

    print(f"📂 CSV 파일 로딩 중: {csv_path}")
    df = pd.read_csv(csv_path)

    if 'formula' not in df.columns:
        print("⚠️  CSV 파일에 'formula' 컬럼이 없습니다.")
        return []

    element_pairs = set()

    for formula in df['formula'].dropna():
        try:
            comp = Composition(formula)
            elements = sorted([str(el) for el in comp.elements])
            if len(elements) == 2:
                pair = tuple(elements)
                element_pairs.add(pair)
        except:
            continue

    pairs_list = list(element_pairs)
    if max_systems is not None:
        pairs_list = pairs_list[:max_systems]

    print(f"✅ 총 {len(pairs_list)}개의 2원소 시스템 발견")
    return pairs_list

def load_element_triplets_from_csv(csv_path, max_systems=None):
    if not os.path.exists(csv_path):
        print(f"⚠️  CSV 파일을 찾을 수 없습니다: {csv_path}")
        return []

    print(f"📂 CSV 파일 로딩 중: {csv_path}")
    df = pd.read_csv(csv_path)

    if 'formula' not in df.columns:
        print("⚠️  CSV 파일에 'formula' 컬럼이 없습니다.")
        return []

    element_triplets = set()

    for formula in df['formula'].dropna():
        try:
            comp = Composition(formula)
            elements = sorted([str(el) for el in comp.elements])
            if len(elements) == 3:
                triplet = tuple(elements)
                element_triplets.add(triplet)
        except:
            continue

    triplets_list = list(element_triplets)
    if max_systems is not None:
        triplets_list = triplets_list[:max_systems]

    print(f"✅ 총 {len(triplets_list)}개의 3원소 시스템 발견")
    return triplets_list

class MaterialPipeline:
    def __init__(self):
        print("🔧 파이프라인 초기화 중...")
        
        # Database initialize
        db_manager.init_db()
        
        self.calc = get_calculator(device=SimConfig.DEVICE)
        self.relaxer = StructureRelaxer(calculator=self.calc)
        self.md_sim = MDSimulator(calculator=self.calc)

    def run_pair(self, element_A, element_B):
        """
        하나의 2원소 조합에 대해 전체 파이프라인 실행
        """
        print(f"\n{'='*70}")
        print(f"🎯 Target System: {element_A} - {element_B}")
        print(f"{'='*70}")

        analyzer = StabilityAnalyzer()
        detailed_data = []
        relaxed_structures = {}

        # [Phase 1] 모든 비율에 대해 Mix + Relax
        print("\n=== [Phase 1] 비율별 혼합 및 구조 이완 ===")

        # [Step 1-1] 순수 원소 기준값 계산
        print("   [Reference] 순수 원소 기준 구조 계산 중...")
        for el in [element_A, element_B]:
            print(f"   🔹 {el} 순수 구조 이완 중...")
            try:
                mixer = RandomAlloyMixer(el)
                atoms = mixer.generate_structure(el, ratio=0.0, supercell_size=SimConfig.SUPERCELL_SIZE)
                atoms.calc = self.calc
                relaxed, e_total = self.relaxer.run(atoms, save_traj=SimConfig.SAVE_RELAX_TRAJ)
                analyzer.add_result(relaxed, e_total)
                
                formula_full = relaxed.get_chemical_formula()
                formula_reduced = Composition(formula_full).reduced_formula
                relaxed_structures[formula_reduced] = relaxed.copy()
                
                e_per_atom = e_total / len(atoms)
                print(f"     ✓ 완료: {e_per_atom:.4f} eV/atom")
            except Exception as e:
                print(f"     ❌ 오류 발생: {e}")
                return {"system": f"{element_A}-{element_B}", "error": str(e)}, []

        # [Step 1-2] 비율별 합금 구조 생성 및 이완
        print("\n   [Alloy Mixing] 비율별 합금 구조 생성 및 이완...")
        
        mixing_ratios = self._get_binary_ratios(element_A, element_B)
        print(f"   ℹ️  총 비율 개수: {len(mixing_ratios)}개")

        if SimConfig.PARALLEL_RATIO_CALCULATION and len(mixing_ratios) > 1:
             self._run_parallel_ratio_relaxation(element_A, element_B, mixing_ratios, analyzer, relaxed_structures)
        else:
             self._run_sequential_ratio_relaxation(element_A, element_B, mixing_ratios, analyzer, relaxed_structures)

        # [Phase 2] 안정성 필터링
        print("\n=== [Phase 2] 열역학적 안정성 필터링 ===")
        results = analyzer.analyze()
        
        if not results:
            print("   ❌ 분석 결과가 없습니다.")
            return {"system": f"{element_A}-{element_B}", "stable_count": 0, "md_count": 0}, []

        stable_formulas = self._process_stability_results(results, detailed_data, relaxed_structures, element_A, element_B)
        print(f"\n   📊 필터링 결과: 총 {len(stable_formulas)}개 안정 구조 발견")

        # [Phase 3] MD 시뮬레이션
        print(f"\n=== [Phase 3] MD 시뮬레이션 ===")
        md_count = self._run_md_simulation(stable_formulas, relaxed_structures, detailed_data)

        return {
            "system": f"{element_A}-{element_B}",
            "total_structures": len(relaxed_structures),
            "stable_count": len(stable_formulas),
            "md_count": md_count
        }, detailed_data

    def run_triplet(self, element_A, element_B, element_C):
        """
        하나의 3원소 조합에 대해 전체 파이프라인 실행
        """
        print(f"\n{'='*70}")
        print(f"🎯 Target System: {element_A} - {element_B} - {element_C}")
        print(f"{'='*70}")

        analyzer = StabilityAnalyzer(stability_threshold=SimConfig.TERNARY_STABILITY_THRESHOLD)
        detailed_data = []
        relaxed_structures = {}

        # [Phase 1-1] 순수 원소 기준값 계산
        print("\n=== [Phase 1-1] 순수 원소 기준 구조 계산 ===")
        mixer = TernaryAlloyMixer(element_A, element_B, element_C)

        for elem in [element_A, element_B, element_C]:
            print(f"   🔹 {elem} 순수 구조 이완 중...")
            try:
                atoms = mixer.generate_pure_element_structure(elem, supercell_size=SimConfig.TERNARY_SUPERCELL_SIZE)
                atoms.calc = self.calc
                relaxed, e_total = self.relaxer.run(atoms, save_traj=SimConfig.SAVE_RELAX_TRAJ)
                analyzer.add_result(relaxed, e_total)
                
                formula_full = relaxed.get_chemical_formula()
                formula_reduced = Composition(formula_full).reduced_formula
                relaxed_structures[formula_reduced] = relaxed.copy()
                
                e_per_atom = e_total / len(atoms)
                print(f"     ✓ 완료: {e_per_atom:.4f} eV/atom")
            except Exception as e:
                print(f"     ❌ 오류 발생: {e}")
                return {"system": f"{element_A}-{element_B}-{element_C}", "error": str(e)}, []

        # [Phase 1-2] 조성별 합금 생성 및 이완
        print("\n=== [Phase 1-2] 조성별 합금 구조 생성 및 이완 ===")
        compositions = self._get_ternary_compositions(element_A, element_B, element_C)
        print(f"   ℹ️  총 조성 개수: {len(compositions)}개")

        for idx, ratio_tuple in enumerate(compositions, 1):
             print(f"   [{idx}/{len(compositions)}] 조성 {ratio_tuple}: {element_A}:{element_B}:{element_C}")
             try:
                 atoms = mixer.generate_ternary_structure(ratio_tuple, supercell_size=SimConfig.TERNARY_SUPERCELL_SIZE)
                 atoms.calc = self.calc
                 relaxed, e_total = self.relaxer.run(atoms, save_traj=SimConfig.SAVE_RELAX_TRAJ)
                 analyzer.add_result(relaxed, e_total)
                 
                 formula_full = relaxed.get_chemical_formula()
                 formula_reduced = Composition(formula_full).reduced_formula
                 relaxed_structures[formula_reduced] = relaxed.copy()
                 
                 e_per_atom = e_total / len(atoms)
                 print(f"     ✓ 완료: {formula_reduced} = {e_per_atom:.4f} eV/atom")
             except Exception as e:
                 print(f"     ❌ 오류 발생: {e}")
                 continue

        # [Phase 2] 안정성 필터링
        print("\n=== [Phase 2] 열역학적 안정성 필터링 ===")
        results = analyzer.analyze()
        if not results:
             return {"system": f"{element_A}-{element_B}-{element_C}", "stable_count": 0}, []

        stable_formulas = self._process_stability_results(results, detailed_data, relaxed_structures, element_A, element_B, element_C)
        print(f"\n   📊 필터링 결과: 총 {len(stable_formulas)}개 안정 구조 발견")

        # [Phase 3] MD 시뮬레이션
        print(f"\n=== [Phase 3] MD 시뮬레이션 ===")
        md_count = self._run_md_simulation(stable_formulas, relaxed_structures, detailed_data)

        return {
            "system": f"{element_A}-{element_B}-{element_C}",
            "total_structures": len(relaxed_structures),
            "stable_count": len(stable_formulas),
            "md_count": md_count
        }, detailed_data

    # --- Helper methods ---
    def _get_binary_ratios(self, element_A, element_B):
        if SimConfig.BINARY_COMPOSITION_MODE == "mined":
            print(f"   🔎 조성 모드: Materials Project 마이닝")
            try:
                binary_miner = MaterialMiner(api_key=SimConfig.MP_API_KEY)
                mined_results = binary_miner.search_metal_alloys([element_A, element_B])
                if mined_results:
                    print(f"   ✅ Materials Project에서 {len(mined_results)}개 구조 발견")
                    mixing_ratios = []
                    for item in mined_results:
                        comp = Composition(item['formula'])
                        elem_b_fraction = comp.get_atomic_fraction(element_B)
                        if 0 < elem_b_fraction < 1:
                            mixing_ratios.append(round(elem_b_fraction, 3))
                    mixing_ratios = sorted(list(set(mixing_ratios)))
                    if SimConfig.BINARY_MINING_MAX_RATIOS and len(mixing_ratios) > SimConfig.BINARY_MINING_MAX_RATIOS:
                        mixing_ratios = mixing_ratios[:SimConfig.BINARY_MINING_MAX_RATIOS]
                    return mixing_ratios
            except Exception as e:
                print(f"   ⚠️  마이닝 중 오류: {e}")
        
        # Fallback to generated
        print(f"   🔧 조성 모드: 균등 간격 생성")
        return SimConfig.get_mixing_ratios()

    def _get_ternary_compositions(self, element_A, element_B, element_C):
        if SimConfig.TERNARY_COMPOSITION_MODE == "mined":
             try:
                ternary_miner = TernaryMaterialMiner(api_key=SimConfig.MP_API_KEY)
                mined_results = ternary_miner.search_ternary_alloys(element_A, element_B, element_C)
                if mined_results:
                     compositions = ternary_miner.get_unique_ratios(mined_results)
                     if SimConfig.TERNARY_MINING_MAX_RATIOS and len(compositions) > SimConfig.TERNARY_MINING_MAX_RATIOS:
                         compositions = compositions[:SimConfig.TERNARY_MINING_MAX_RATIOS]
                     return compositions
             except Exception as e:
                 print(f"   ⚠️  마이닝 중 오류: {e}")
        
        return TernaryAlloyMixer.generate_composition_ratios(SimConfig.TERNARY_COMPOSITION_TOTAL)

    def _run_parallel_ratio_relaxation(self, element_A, element_B, mixing_ratios, analyzer, relaxed_structures):
        print(f"   🚀 병렬 모드: 배치 크기 {SimConfig.RATIO_BATCH_SIZE}")
        batch_relaxer = BatchStructureRelaxer(self.calc, batch_size=SimConfig.RATIO_BATCH_SIZE)
        atoms_list = []
        ratio_map = {}
        
        for r in mixing_ratios:
            ratio_percent = int(r * 100)
            print(f"   🔹 {element_A} + {ratio_percent}% {element_B} 구조 생성")
            mixer = RandomAlloyMixer(element_A)
            atoms = mixer.generate_structure(element_B, ratio=r, supercell_size=SimConfig.SUPERCELL_SIZE)
            atoms_list.append(atoms)
            ratio_map[len(atoms_list) - 1] = r
            
        batch_results = batch_relaxer.run_batch(atoms_list, save_traj=SimConfig.SAVE_RELAX_TRAJ)
        
        for idx, (relaxed_atoms, energy_total) in enumerate(batch_results):
            if energy_total != float('inf'):
                analyzer.add_result(relaxed_atoms, energy_total)
                formula_full = relaxed_atoms.get_chemical_formula()
                formula_reduced = Composition(formula_full).reduced_formula
                relaxed_structures[formula_reduced] = relaxed_atoms.copy()
                e_per_atom = energy_total / len(relaxed_atoms)
                ratio_percent = int(ratio_map[idx] * 100)
                print(f"   ✓ {element_A} + {ratio_percent}% {element_B}: {e_per_atom:.4f} eV/atom")

    def _run_sequential_ratio_relaxation(self, element_A, element_B, mixing_ratios, analyzer, relaxed_structures):
         print(f"   ℹ️  순차 모드")
         for r in mixing_ratios:
            ratio_percent = int(r * 100)
            print(f"\n   🔹 {element_A} + {ratio_percent}% {element_B}")
            try:
                mixer = RandomAlloyMixer(element_A)
                atoms = mixer.generate_structure(element_B, ratio=r, supercell_size=SimConfig.SUPERCELL_SIZE)
                atoms.calc = self.calc
                relaxed_atoms, energy_total = self.relaxer.run(atoms, save_traj=SimConfig.SAVE_RELAX_TRAJ)
                analyzer.add_result(relaxed_atoms, energy_total)
                formula_full = relaxed_atoms.get_chemical_formula()
                formula_reduced = Composition(formula_full).reduced_formula
                relaxed_structures[formula_reduced] = relaxed_atoms.copy()
                e_per_atom = energy_total / len(relaxed_atoms)
                print(f"     ✓ 이완 완료: {e_per_atom:.4f} eV/atom")
            except Exception as e:
                print(f"     ❌ 오류 발생: {e}")

    def _process_stability_results(self, results, detailed_data, relaxed_structures, element_A, element_B, element_C=None):
        stable_formulas = []
        print(f"\n   {'Formula':<15} | {'E above hull':<15} | {'Status'}")
        print("   " + "-" * 55)
        
        for res in results:
            formula = res['formula']
            e_hull = res['energy_above_hull']
            is_stable = res['is_stable']
            
            if is_stable:
                status = "✅ 안정 (MD 대상)"
                stable_formulas.append(formula)
            else:
                status = "❌ 불안정 (Skip)"
            
            print(f"   {formula:<15} | {e_hull:.6f} eV/atom | {status}")
            
            atoms_data = relaxed_structures.get(formula)
            if atoms_data:
                comp = Composition(formula)
                if element_C: # Ternary
                     # Logic for ternary data collection might differ slightly in detail if needed, but here simplifying
                     self._add_detailed_data(detailed_data, atoms_data, formula, e_hull, is_stable, f"{element_A}-{element_B}-{element_C}")
                else: # Binary
                     self._add_detailed_data(detailed_data, atoms_data, formula, e_hull, is_stable, f"{element_A}-{element_B}")

        return stable_formulas

    def _add_detailed_data(self, detailed_data, atoms, formula, e_hull, is_stable, system_name):
        lattice = atoms.get_cell()
        lattice_a = lattice[0][0]
        volume = atoms.get_volume()
        mass = sum(atoms.get_masses())
        density = mass / volume * 1.66054
        
        # Simplified ratio logic for general case
        # For strict compatibility with original CSV format, we might need specific column names like 'ratio_A', 'ratio_B'
        # But for general usage, just dumping key props is fine. 
        # Here I will try to match original functionality which parses element A and B ratios.
        
        comp = Composition(formula)
        elements = list(comp.as_dict().keys())
        fractions = list(comp.as_dict().values())
        
        data = {
            'system': system_name,
            'formula': formula,
            'total_atoms': len(atoms),
            'lattice_a': round(lattice_a, 4),
            'density': round(density, 4),
            'energy_per_atom': atoms.get_potential_energy() / len(atoms) if atoms.calc else None,
            'energy_above_hull': e_hull,
            'is_stable': is_stable,
            'md_performed': False,
            'md_avg_temperature': None,
            'md_temp_fluctuation': None,
            'md_avg_energy_per_atom': None,
            'md_volume_change_percent': None,
            'md_thermally_stable': None
        }
        
        # Add ratios if binary (to match original CSV output exactly if possible)
        if len(system_name.split('-')) == 2:
            data['element_A'] = elements[0] if len(elements) > 0 else system_name.split('-')[0]
            data['element_B'] = elements[1] if len(elements) > 1 else system_name.split('-')[1]
            data['ratio_A'] = fractions[0] / sum(fractions) if len(fractions) > 0 else 1.0
            data['ratio_B'] = fractions[1] / sum(fractions) if len(fractions) > 1 else 0.0

        detailed_data.append(data)
        
        # Save to Database
        try:
            session = db_manager.get_session()
            if session:
                # 1. Get or Create System
                sys_q = session.query(System).filter_by(name=system_name).first()
                if not sys_q:
                    parts = system_name.split('-')
                    el_a = parts[0]
                    el_b = parts[1]
                    el_c = parts[2] if len(parts) > 2 else None
                    sys_q = System(name=system_name, element_a=el_a, element_b=el_b, element_c=el_c)
                    session.add(sys_q)
                    session.commit()
                
                # 2. Create SimulationResult
                # Check if exists first to avoid duplicate if re-running without resume check
                existing_res = session.query(SimulationResult).filter_by(system_id=sys_q.id, formula=formula).first()
                if not existing_res:
                    sim_res = SimulationResult(
                        system_id=sys_q.id,
                        formula=formula,
                        total_atoms=data['total_atoms'],
                        lattice_a=data['lattice_a'],
                        density=data['density'],
                        energy_per_atom=data['energy_per_atom'],
                        energy_above_hull=data['energy_above_hull'],
                        is_stable=data['is_stable']
                    )
                    session.add(sim_res)
                    session.commit()
                    # Store DB ID in data for later use if needed, or just query again
                session.close()
        except Exception as e:
            print(f"     ⚠️  DB 저장 실패: {e}")

    def _run_md_simulation(self, stable_formulas, relaxed_structures, detailed_data):
        if not stable_formulas:
            print("   ℹ️  안정한 구조가 없어 MD를 건너뜁니다.")
            return 0
            
        md_count = 0
        tasks = []
        
        # Prepare tasks
        for formula in stable_formulas:
            comp = Composition(formula)
            if len(comp.elements) == 1:
                print(f"   ⏭️  {formula} - 순수 원소이므로 MD 건너뜀")
                continue
                
            atoms = relaxed_structures.get(formula)
            if atoms:
                if len(atoms) < 200:
                    atoms = atoms * (2, 2, 2)
                tasks.append((formula, atoms.copy(), SimConfig.MD_TEMPERATURE, SimConfig.MD_STEPS, SimConfig.DEVICE))

        if SimConfig.PARALLEL_MD_EXECUTION:
             print(f"   🚀 병렬 모드 활성화 (프로세스 수: {SimConfig.MD_NUM_PROCESSES})")
             if not tasks:
                 print("   ℹ️  MD를 수행할 합금 구조가 없습니다.")
                 return 0
             
             with mp.Pool(processes=min(len(tasks), SimConfig.MD_NUM_PROCESSES)) as pool:
                 results = pool.map(md_worker, tasks)
                 
             for formula, traj_file, error in results:
                 if error:
                     print(f"   ❌ {formula} MD 실패: {error[:100]}...")
                 elif traj_file:
                     self._analyze_md_result(formula, traj_file, detailed_data)
                     md_count += 1
        else:
             print(f"   🐢 순차 모드 활성화")
             for idx, (formula, atoms, temp, steps, dev) in enumerate(tasks, 1):
                 print(f"\n   🔹 [{idx}/{len(tasks)}] {formula} - MD 시뮬레이션 시작...")
                 try:
                     final_atoms, traj_file = self.md_sim.run(atoms, temperature=temp, steps=steps, save_interval=50)
                     if traj_file:
                         self._analyze_md_result(formula, traj_file, detailed_data)
                         md_count += 1
                 except Exception as e:
                     print(f"     ❌ MD 실행 중 오류: {e}")

        return md_count

    def _analyze_md_result(self, formula, traj_file, detailed_data):
        md_analyzer = MDAnalyzer(traj_file)
        md_results = md_analyzer.analyze()
        if "error" not in md_results:
             md_analyzer.print_summary(md_results)
             for data in detailed_data:
                 if data['formula'] == formula:
                     data['md_performed'] = True
                     data['md_avg_temperature'] = md_results.get('avg_temperature')
                     data['md_temp_fluctuation'] = md_results.get('temperature_fluctuation_percent')
                     data['md_avg_energy_per_atom'] = md_results.get('avg_energy_per_atom')
                     data['md_volume_change_percent'] = md_results.get('volume_change_percent')
                     data['md_thermally_stable'] = md_results.get('is_thermally_stable')
                     
                     # Update Database
                     try:
                         session = db_manager.get_session()
                         if session:
                             system_name = data['system']
                             sys_q = session.query(System).filter_by(name=system_name).first()
                             if sys_q:
                                 sim_res = session.query(SimulationResult).filter_by(system_id=sys_q.id, formula=formula).first()
                                 if sim_res:
                                     sim_res.md_performed = True
                                     sim_res.md_avg_temperature = md_results.get('avg_temperature')
                                     sim_res.md_temp_fluctuation = md_results.get('temperature_fluctuation_percent')
                                     sim_res.md_avg_energy_per_atom = md_results.get('avg_energy_per_atom')
                                     sim_res.md_volume_change_percent = md_results.get('volume_change_percent')
                                     sim_res.md_thermally_stable = md_results.get('is_thermally_stable')
                                     session.commit()
                             session.close()
                     except Exception as e:
                         print(f"     ⚠️  DB 업데이트 실패: {e}")
                     
                     break
             print(f"     ✅ MD 완료 및 분석 성공")
        else:
             print(f"     ⚠️  MD 분석 오류: {md_results['error']}")
