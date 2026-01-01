# run_pipeline.py - CSV 자동 로드 파이프라인 (src 모듈 활용)
import pandas as pd
import os
from pymatgen.core import Composition

# ============================================================================
# MatterSim 모듈 임포트 (src/mattersim_dt 사용)
# ============================================================================
from mattersim_dt.core import SimConfig
from mattersim_dt.builder import RandomAlloyMixer
from mattersim_dt.engine import get_calculator, StructureRelaxer, MDSimulator
from mattersim_dt.analysis import StabilityAnalyzer, MDAnalyzer, MaterialValidator
from mattersim_dt.miner import ExperimentalDataMiner
import multiprocessing as mp

import torch
print(f"🔍 PyTorch GPU Available: {torch.cuda.is_available()}")
print(f"🔍 Current Device Name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")
# ============================================================================
# MD 멀티프로세싱 Worker 함수
# ============================================================================
def md_worker(args):
    """
    별도의 프로세스에서 독립적으로 MD를 실행하는 함수

    ⚠️ Windows 사용자 주의:
    - config.py에서 PARALLEL_MD_EXECUTION = False로 설정하여 이 기능을 끌 수 있습니다
    - Windows는 'spawn' 방식을 사용하므로 메모리 오버헤드가 큽니다
    - GPU 메모리가 부족하면 프로세스 수를 줄이거나 순차 모드를 사용하세요

    Linux/서버 환경:
    - 'fork' 방식을 사용하여 효율적으로 작동합니다
    - 다중 GPU 환경에서 큰 성능 향상을 기대할 수 있습니다
    """
    formula, atoms, temperature, steps, device = args

    # 중요: 각 프로세스 내에서 계산기를 새로 로드해야 GPU 충돌이 없습니다.
    from mattersim_dt.engine import get_calculator, MDSimulator
    import os

    try:
        # 프로세스 ID 출력 (디버깅용)
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

# ============================================================================
# CSV 중간 저장 함수
# ============================================================================
def save_intermediate_csv(csv_filename, detailed_data):
    """
    중간 결과를 CSV로 저장 (시스템 하나 끝날 때마다 호출)

    :param csv_filename: CSV 파일 경로
    :param detailed_data: 저장할 데이터 리스트
    """
    if not detailed_data:
        return

    df_results = pd.DataFrame(detailed_data)
    df_results.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    print(f"   💾 중간 저장 완료: {csv_filename} ({len(detailed_data)}개 구조)")

# ============================================================================
# Resume 기능: 완료된 시스템 찾기
# ============================================================================
def find_latest_result_csv():
    """
    현재 디렉토리에서 가장 최신 pipeline_results_*.csv 파일을 찾습니다.

    Returns:
        str: CSV 파일 경로 (없으면 None)
    """
    import glob
    csv_files = glob.glob("pipeline_results_*.csv")

    if not csv_files:
        return None

    # 파일명에서 타임스탬프 추출하여 최신 파일 찾기
    csv_files.sort(reverse=True)  # 알파벳 역순 정렬 (타임스탬프 문자열이므로 최신이 앞으로)
    return csv_files[0]

def load_completed_systems(csv_path):
    """
    기존 CSV 파일에서 완료된 시스템 목록을 로드합니다.

    Args:
        csv_path: CSV 파일 경로

    Returns:
        set: 완료된 시스템 집합 (예: {"Cu-Ni", "Al-Mg"})
    """
    if not csv_path or not os.path.exists(csv_path):
        return set()

    try:
        df = pd.read_csv(csv_path)

        if 'system' not in df.columns:
            print(f"   ⚠️  CSV 파일에 'system' 컬럼이 없습니다: {csv_path}")
            return set()

        completed_systems = set(df['system'].unique())
        print(f"   📂 기존 결과 파일 발견: {csv_path}")
        print(f"   ✅ 완료된 시스템: {len(completed_systems)}개")
        print(f"      → {', '.join(sorted(completed_systems))}")

        return completed_systems

    except Exception as e:
        print(f"   ⚠️  CSV 로드 중 오류: {e}")
        return set()

def load_existing_data(csv_path):
    """
    기존 CSV 파일의 상세 데이터를 로드합니다 (이어서 저장하기 위함)

    Args:
        csv_path: CSV 파일 경로

    Returns:
        list: 기존 데이터 리스트
    """
    if not csv_path or not os.path.exists(csv_path):
        return []

    try:
        df = pd.read_csv(csv_path)
        return df.to_dict('records')  # 딕셔너리 리스트로 반환
    except Exception as e:
        print(f"   ⚠️  기존 데이터 로드 중 오류: {e}")
        return []

# ============================================================================
# CSV에서 원소 조합 로드 함수
# ============================================================================
def load_element_pairs_from_csv(csv_path, max_systems=None):
    """
    CSV 파일에서 원소 조합을 추출하는 함수

    Args:
        csv_path: CSV 파일 경로
        max_systems: 최대 시스템 수 (None이면 전체)

    Returns:
        [(elem_A, elem_B), ...] 형태의 리스트
    """
    if not os.path.exists(csv_path):
        print(f"⚠️  CSV 파일을 찾을 수 없습니다: {csv_path}")
        return []

    print(f"📂 CSV 파일 로딩 중: {csv_path}")
    df = pd.read_csv(csv_path)

    if 'formula' not in df.columns:
        print("⚠️  CSV 파일에 'formula' 컬럼이 없습니다.")
        return []

    # 중복 제거를 위한 set
    element_pairs = set()

    for formula in df['formula'].dropna():
        try:
            # Pymatgen으로 화학식 파싱
            comp = Composition(formula)
            elements = sorted([str(el) for el in comp.elements])

            # 2원소 시스템만 추출
            if len(elements) == 2:
                pair = tuple(elements)
                element_pairs.add(pair)
        except:
            continue

    # set -> list 변환
    pairs_list = list(element_pairs)

    # 최대 개수 제한
    if max_systems is not None:
        pairs_list = pairs_list[:max_systems]

    print(f"✅ 총 {len(pairs_list)}개의 2원소 시스템 발견")
    return pairs_list

# ============================================================================
# 하나의 원소 조합에 대해 전체 파이프라인 실행
# ============================================================================
def run_experiment_for_pair(element_A, element_B, calc, relaxer, md_sim):
    """
    하나의 원소 조합에 대해 전체 파이프라인 실행

    Returns:
        dict: 실험 결과 요약
        list: 상세 물성 데이터 (CSV 저장용)
    """
    print(f"\n{'='*70}")
    print(f"🎯 Target System: {element_A} - {element_B}")
    print(f"{'='*70}")

    # StabilityAnalyzer 생성 (config.py의 STABILITY_THRESHOLD 자동 사용)
    analyzer = StabilityAnalyzer()

    # 상세 물성 데이터를 저장할 리스트
    detailed_data = []

    # -------------------------------------------------------------------------
    # [Phase 1] 모든 비율에 대해 Mix + Relax
    # -------------------------------------------------------------------------
    print("\n=== [Phase 1] 비율별 혼합 및 구조 이완 ===")

    # 이완된 구조들을 저장할 딕셔너리 (순수 원소 + 합금 모두 저장)
    relaxed_structures = {}

    # [Step 1-1] 순수 원소 기준값 계산
    print("   [Reference] 순수 원소 기준 구조 계산 중...")

    for el in [element_A, element_B]:
        print(f"   🔹 {el} 순수 구조 이완 중...")
        try:
            # RandomAlloyMixer 사용 (자동으로 격자 상수 선택)
            mixer = RandomAlloyMixer(el)
            # base_atoms 대신 generate_structure를 사용하여 슈퍼셀 확보 (ratio=0)
            atoms = mixer.generate_structure(el, ratio=0.0, supercell_size=SimConfig.SUPERCELL_SIZE)
            atoms.calc = calc

            # StructureRelaxer 사용
            relaxed, e_total = relaxer.run(atoms, save_traj=SimConfig.SAVE_RELAX_TRAJ)

            # StabilityAnalyzer에 등록
            analyzer.add_result(relaxed, e_total)

            # 나중에 MD용으로 저장 (순수 원소도 저장!)
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

    # SimConfig에서 비율 가져오기
    mixing_ratios = SimConfig.get_mixing_ratios()
    print(f"   ℹ️  비율 간격: {SimConfig.MIXING_RATIO_STEP} → 총 {len(mixing_ratios)}개 비율 테스트")

    if SimConfig.PARALLEL_RATIO_CALCULATION and len(mixing_ratios) > 1:
        # 병렬 처리 모드
        print(f"   🚀 병렬 모드: 배치 크기 {SimConfig.RATIO_BATCH_SIZE}")

        from mattersim_dt.engine import BatchStructureRelaxer
        batch_relaxer = BatchStructureRelaxer(calc, batch_size=SimConfig.RATIO_BATCH_SIZE)

        # 모든 비율에 대해 구조 생성
        atoms_list = []
        ratio_map = {}  # 구조 -> 비율 매핑

        for r in mixing_ratios:
            ratio_percent = int(r * 100)
            print(f"   🔹 {element_A} + {ratio_percent}% {element_B} 구조 생성")

            mixer = RandomAlloyMixer(element_A)
            atoms = mixer.generate_structure(
                element_B,
                ratio=r,
                supercell_size=SimConfig.SUPERCELL_SIZE
            )
            atoms_list.append(atoms)
            ratio_map[len(atoms_list) - 1] = r

        # 배치 이완
        batch_results = batch_relaxer.run_batch(atoms_list, save_traj=SimConfig.SAVE_RELAX_TRAJ)

        # 결과 등록
        for idx, (relaxed_atoms, energy_total) in enumerate(batch_results):
            if energy_total != float('inf'):
                analyzer.add_result(relaxed_atoms, energy_total)

                formula_full = relaxed_atoms.get_chemical_formula()
                formula_reduced = Composition(formula_full).reduced_formula
                relaxed_structures[formula_reduced] = relaxed_atoms.copy()

                e_per_atom = energy_total / len(relaxed_atoms)
                r = ratio_map[idx]
                ratio_percent = int(r * 100)
                print(f"   ✓ {element_A} + {ratio_percent}% {element_B}: {e_per_atom:.4f} eV/atom")

    else:
        # 순차 처리 모드 (기존 방식)
        print(f"   ℹ️  순차 모드")

        for r in mixing_ratios:
            ratio_percent = int(r * 100)
            print(f"\n   🔹 {element_A} + {ratio_percent}% {element_B}")

            try:
                # RandomAlloyMixer로 구조 생성
                mixer = RandomAlloyMixer(element_A)
                atoms = mixer.generate_structure(
                    element_B,
                    ratio=r,
                    supercell_size=SimConfig.SUPERCELL_SIZE
                )

                atoms.calc = calc

                # StructureRelaxer로 이완
                relaxed_atoms, energy_total = relaxer.run(atoms, save_traj=SimConfig.SAVE_RELAX_TRAJ)

                # StabilityAnalyzer에 등록
                analyzer.add_result(relaxed_atoms, energy_total)

                # 나중에 MD용으로 저장 (reduced_formula를 키로 사용)
                formula_full = relaxed_atoms.get_chemical_formula()
                formula_reduced = Composition(formula_full).reduced_formula
                relaxed_structures[formula_reduced] = relaxed_atoms.copy()

                e_per_atom = energy_total / len(relaxed_atoms)
                print(f"     ✓ 이완 완료: {e_per_atom:.4f} eV/atom")
            except Exception as e:
                print(f"     ❌ 오류 발생: {e}")
                continue

    # -------------------------------------------------------------------------
    # [Phase 2] 안정성 필터링 (StabilityAnalyzer 사용)
    # -------------------------------------------------------------------------
    print("\n=== [Phase 2] 열역학적 안정성 필터링 ===")
    print(f"   🔍 Pymatgen Convex Hull 분석 중 (임계값: {SimConfig.STABILITY_THRESHOLD} eV/atom)...")

    # StabilityAnalyzer의 analyze() 호출
    results = analyzer.analyze()

    if not results:
        print("   ❌ 분석 결과가 없습니다.")
        return {"system": f"{element_A}-{element_B}", "stable_count": 0, "md_count": 0}, []

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

        # CSV 저장용 상세 데이터 수집
        atoms_data = relaxed_structures.get(formula)
        if atoms_data:
            comp = Composition(formula)
            elements = list(comp.as_dict().keys())
            fractions = list(comp.as_dict().values())

            # 격자 상수 및 밀도 추출 (검증용)
            lattice = atoms_data.get_cell()
            lattice_a = lattice[0][0]  # a 격자 상수 (Angstrom)
            volume = atoms_data.get_volume()  # 부피 (Angstrom^3)
            mass = sum(atoms_data.get_masses())  # 총 질량 (amu)
            density = mass / volume * 1.66054  # 밀도 (g/cm^3) - amu/A^3 -> g/cm^3 변환

            detailed_data.append({
                'system': f"{element_A}-{element_B}",
                'formula': formula,
                'element_A': elements[0] if len(elements) > 0 else element_A,
                'element_B': elements[1] if len(elements) > 1 else element_B,
                'ratio_A': fractions[0] / sum(fractions) if len(fractions) > 0 else 1.0,
                'ratio_B': fractions[1] / sum(fractions) if len(fractions) > 1 else 0.0,
                'total_atoms': len(atoms_data),
                'lattice_a': round(lattice_a, 4),  # 격자 상수 a (검증용)
                'density': round(density, 4),  # 밀도 (검증용)
                'energy_per_atom': atoms_data.get_potential_energy() / len(atoms_data) if atoms_data.calc else None,
                'energy_above_hull': e_hull,
                'is_stable': is_stable,
                'md_performed': False,  # MD는 나중에 업데이트
                # MD 물성 (초기값)
                'md_avg_temperature': None,
                'md_temp_fluctuation': None,
                'md_avg_energy_per_atom': None,
                'md_volume_change_percent': None,
                'md_thermally_stable': None
            })

    print(f"\n   📊 필터링 결과: 총 {len(stable_formulas)}개 안정 구조 발견")

    # -------------------------------------------------------------------------
    # [Phase 3] MD 시뮬레이션 (병렬/순차 선택 가능)
    # -------------------------------------------------------------------------
    print(f"\n=== [Phase 3] MD 시뮬레이션 ===")

    md_count = 0
    if not stable_formulas:
        print("   ℹ️  안정한 구조가 없어 MD를 건너뜁니다.")
    else:
        # =====================================================================
        # 모드 1: 병렬 처리 (서버/Linux 환경 권장)
        # =====================================================================
        if SimConfig.PARALLEL_MD_EXECUTION:
            print(f"   🚀 병렬 모드 활성화 (프로세스 수: {SimConfig.MD_NUM_PROCESSES})")
            print(f"   ⚠️  Windows에서는 메모리 사용량이 높을 수 있습니다")

            # 1. 작업 리스트 준비
            tasks = []
            for formula in stable_formulas:
                atoms = relaxed_structures.get(formula)
                if atoms:
                    if len(atoms) < 200:
                        atoms = atoms * (2, 2, 2)
                    # (화학식, 구조, 온도, 스텝, 디바이스) 튜플로 저장
                    tasks.append((formula, atoms.copy(), SimConfig.MD_TEMPERATURE, SimConfig.MD_STEPS, SimConfig.DEVICE))

            # 2. 프로세스 풀 생성 및 실행
            num_processes = min(len(tasks), SimConfig.MD_NUM_PROCESSES)
            print(f"   📋 총 {len(tasks)}개 구조에 대해 {num_processes}개 프로세스로 병렬 실행...")

            with mp.Pool(processes=num_processes) as pool:
                # 병렬 실행 시작
                results = pool.map(md_worker, tasks)

            # 3. 결과 수집 및 분석
            print("\n   📊 병렬 MD 결과 분석 중...")
            for formula, traj_file, error in results:
                if error:
                    print(f"   ❌ {formula} MD 실패: {error[:100]}...")
                    continue

                if traj_file:
                    print(f"\n   🔹 {formula} - 결과 분석 중...")
                    md_analyzer = MDAnalyzer(traj_file)
                    md_results = md_analyzer.analyze()

                    if "error" not in md_results:
                        md_analyzer.print_summary(md_results)
                        md_count += 1
                        # 상세 데이터 업데이트
                        for data in detailed_data:
                            if data['formula'] == formula:
                                data['md_performed'] = True
                                data['md_avg_temperature'] = md_results.get('avg_temperature')
                                data['md_temp_fluctuation'] = md_results.get('temperature_fluctuation_percent')
                                data['md_avg_energy_per_atom'] = md_results.get('avg_energy_per_atom')
                                data['md_volume_change_percent'] = md_results.get('volume_change_percent')
                                data['md_thermally_stable'] = md_results.get('is_thermally_stable')
                                break
                    else:
                        print(f"     ⚠️  MD 분석 오류 ({formula}): {md_results['error']}")

        # =====================================================================
        # 모드 2: 순차 처리 (Windows/안정성 우선)
        # =====================================================================
        else:
            print(f"   🐢 순차 모드 활성화 (안정적, 메모리 효율적)")
            print(f"   💡 서버 환경에서는 config.py의 PARALLEL_MD_EXECUTION = True로 설정하면 빠릅니다")

            # 순차적으로 MD 실행
            for idx, formula in enumerate(stable_formulas, 1):
                print(f"\n   🔹 [{idx}/{len(stable_formulas)}] {formula} - MD 시뮬레이션 시작...")

                atoms = relaxed_structures.get(formula)
                if not atoms:
                    print(f"     ⚠️  구조를 찾을 수 없습니다. 건너뜁니다.")
                    continue

                try:
                    # 구조 크기 확인 및 확장
                    if len(atoms) < 200:
                        print(f"     ℹ️  구조가 작아서 2x2x2로 확장합니다 ({len(atoms)} -> {len(atoms)*8} atoms)")
                        atoms = atoms * (2, 2, 2)

                    # MD 실행
                    final_atoms, traj_file = md_sim.run(
                        atoms,
                        temperature=SimConfig.MD_TEMPERATURE,
                        steps=SimConfig.MD_STEPS,
                        save_interval=50
                    )

                    if traj_file:
                        # 결과 분석
                        md_analyzer = MDAnalyzer(traj_file)
                        md_results = md_analyzer.analyze()

                        if "error" not in md_results:
                            md_analyzer.print_summary(md_results)
                            md_count += 1

                            # 상세 데이터 업데이트
                            for data in detailed_data:
                                if data['formula'] == formula:
                                    data['md_performed'] = True
                                    data['md_avg_temperature'] = md_results.get('avg_temperature')
                                    data['md_temp_fluctuation'] = md_results.get('temperature_fluctuation_percent')
                                    data['md_avg_energy_per_atom'] = md_results.get('avg_energy_per_atom')
                                    data['md_volume_change_percent'] = md_results.get('volume_change_percent')
                                    data['md_thermally_stable'] = md_results.get('is_thermally_stable')
                                    break

                            print(f"     ✅ MD 완료 및 분석 성공")
                        else:
                            print(f"     ⚠️  MD 분석 오류: {md_results['error']}")
                    else:
                        print(f"     ⚠️  Trajectory 파일이 생성되지 않았습니다.")

                except Exception as e:
                    print(f"     ❌ MD 실행 중 오류: {e}")
                    import traceback
                    print(f"     상세: {traceback.format_exc()[:200]}")
                    continue


    # 결과 요약 반환 (기존과 동일)
    return {
        "system": f"{element_A}-{element_B}",
        "total_structures": len(relaxed_structures),
        "stable_count": len(stable_formulas),
        "md_count": md_count
    }, detailed_data




# ============================================================================
# 메인 함수
# ============================================================================
def main():
    print("="*70)
    print("   🌐 MatterSim Digital Twin: 3-Phase Pipeline")
    print("      Phase 1: Mix + Relax (모든 비율)")
    print("      Phase 2: Stability Filter (안정성 판정)")
    print("      Phase 3: MD Simulation (안정한 구조만)")
    print("="*70)

    # 0. SimConfig 설정
    SimConfig.setup()

    # -------------------------------------------------------------------------
    # Resume 모드 체크 (기존 결과 이어하기)
    # -------------------------------------------------------------------------
    completed_systems = set()
    all_detailed_data = []  # 기존 데이터를 담을 리스트
    resume_csv = None

    if SimConfig.RESUME_MODE:
        print("\n🔄 Resume 모드 활성화: 기존 결과 확인 중...")

        # 사용자가 지정한 CSV 또는 최신 CSV 찾기
        resume_csv = SimConfig.RESUME_CSV_PATH or find_latest_result_csv()

        if resume_csv:
            completed_systems = load_completed_systems(resume_csv)
            all_detailed_data = load_existing_data(resume_csv)

            if completed_systems:
                print(f"   ♻️  기존 결과를 이어서 진행합니다.")
            else:
                print(f"   ℹ️  기존 CSV 파일이 비어있거나 시스템 정보가 없습니다.")
                resume_csv = None
        else:
            print(f"   ℹ️  기존 결과 파일 없음 → 처음부터 시작합니다.")

    # CSV 파일명 결정
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # 항상 생성 (검증용 파일명에 사용)

    if resume_csv and SimConfig.RESUME_MODE and completed_systems:
        # Resume 모드: 기존 파일 계속 사용
        csv_filename = resume_csv
        print(f"\n💾 결과 파일: {csv_filename} (기존 파일에 추가 저장)")
    else:
        # 새 파일 생성
        csv_filename = f"pipeline_results_{timestamp}.csv"
        print(f"\n💾 결과 파일: {csv_filename} (새 파일 생성)")

    print(f"\n⚙️  설정 로딩:")
    print(f"   - 파이프라인 모드: {SimConfig.PIPELINE_MODE}")
    print(f"   - Resume 모드: {'ON (완료된 시스템 건너뛰기)' if SimConfig.RESUME_MODE else 'OFF'}")
    print(f"   - CSV 경로: {SimConfig.MINER_CSV_PATH}")
    print(f"   - 최대 시스템 수: {SimConfig.MAX_SYSTEMS}")
    print(f"   - 혼합 비율 간격: {SimConfig.MIXING_RATIO_STEP} ({len(SimConfig.get_mixing_ratios())}개 비율)")
    print(f"   - 슈퍼셀 크기: {SimConfig.SUPERCELL_SIZE}")
    print(f"   - 안정성 임계값: {SimConfig.STABILITY_THRESHOLD} eV/atom")
    print(f"   - MD 온도: {SimConfig.MD_TEMPERATURE} K")
    print(f"   - 디바이스: {SimConfig.DEVICE}")

    # 1. Calculator, Relaxer, MDSimulator 생성 (src 모듈 사용)
    calc = get_calculator(device=SimConfig.DEVICE)
    relaxer = StructureRelaxer(calculator=calc)
    md_sim = MDSimulator(calculator=calc)

    # -------------------------------------------------------------------------
    # 2. 원소 조합 로딩 (auto 모드 vs manual 모드)
    # -------------------------------------------------------------------------
    if SimConfig.PIPELINE_MODE == "auto":
        print(f"\n📂 AUTO 모드: CSV에서 원소 조합 자동 로드")
        element_pairs = load_element_pairs_from_csv(
            SimConfig.MINER_CSV_PATH,
            max_systems=SimConfig.MAX_SYSTEMS
        )

        if not element_pairs:
            print("❌ 원소 조합을 찾을 수 없습니다. 프로그램을 종료합니다.")
            return

    elif SimConfig.PIPELINE_MODE == "manual":
        print(f"\n✋ MANUAL 모드: 수동 지정 원소 사용")
        element_pairs = [(SimConfig.MANUAL_ELEMENT_A, SimConfig.MANUAL_ELEMENT_B)]
        print(f"   - 원소 조합: {element_pairs[0]}")

    else:
        print(f"❌ 알 수 없는 PIPELINE_MODE: {SimConfig.PIPELINE_MODE}")
        return

    # -------------------------------------------------------------------------
    # 3. 각 원소 조합에 대해 파이프라인 실행
    # -------------------------------------------------------------------------
    print(f"\n🚀 총 {len(element_pairs)}개 시스템에 대해 파이프라인 실행 시작")

    # 병렬처리 설정 출력
    print(f"\n⚙️  병렬처리 설정:")
    print(f"   - 비율별 병렬: {'ON' if SimConfig.PARALLEL_RATIO_CALCULATION else 'OFF'}")
    if SimConfig.PARALLEL_RATIO_CALCULATION:
        print(f"     배치 크기: {SimConfig.RATIO_BATCH_SIZE}")
    print(f"   - 시스템별 병렬: {'ON' if SimConfig.PARALLEL_SYSTEM_CALCULATION else 'OFF'}")
    if SimConfig.PARALLEL_SYSTEM_CALCULATION:
        print(f"     GPU 개수: {SimConfig.NUM_GPUS}")
    print(f"   - MD 다중 온도: {'ON' if SimConfig.PARALLEL_MD_TEMPERATURES else 'OFF'}")
    if SimConfig.PARALLEL_MD_TEMPERATURES:
        print(f"     온도 범위: {SimConfig.MD_TEMPERATURE_RANGE} K")
    print()

    all_results = []
    # all_detailed_data는 이미 위에서 초기화됨 (Resume 모드에서 기존 데이터 로드)

    if SimConfig.PARALLEL_SYSTEM_CALCULATION and SimConfig.NUM_GPUS > 1:
        # 다중 GPU 병렬 처리
        print(f"🚀 다중 GPU 모드: {SimConfig.NUM_GPUS}개 GPU 사용")
        print("⚠️  주의: 이 모드는 복잡하므로 개발 중입니다. 현재는 순차 실행합니다.\n")
        # TODO: 실제 멀티프로세싱 구현 (복잡도가 높아 일단 순차 실행)

        for idx, (elem_A, elem_B) in enumerate(element_pairs, 1):
            system_name = f"{elem_A}-{elem_B}"

            # Resume 모드: 이미 완료된 시스템은 건너뛰기
            if system_name in completed_systems:
                print(f"\n{'#'*70}")
                print(f"# [{idx}/{len(element_pairs)}] {system_name} - ⏭️  이미 완료됨 (건너뛰기)")
                print(f"{'#'*70}")
                continue

            print(f"\n{'#'*70}")
            print(f"# [{idx}/{len(element_pairs)}] 시스템 실행 중")
            print(f"{'#'*70}")

            result, detailed_data = run_experiment_for_pair(elem_A, elem_B, calc, relaxer, md_sim)
            all_results.append(result)
            all_detailed_data.extend(detailed_data)

            print(f"\n   ✅ {result['system']} 완료")
            if 'error' not in result:
                print(f"      - 총 구조: {result['total_structures']}개")
                print(f"      - 안정 구조: {result['stable_count']}개")
                print(f"      - MD 완료: {result['md_count']}개")

            # 중간 저장 (시스템 하나 끝날 때마다)
            save_intermediate_csv(csv_filename, all_detailed_data)

    else:
        # 순차 처리 (기본)
        print(f"ℹ️  순차 모드: 시스템을 하나씩 처리합니다.\n")

        for idx, (elem_A, elem_B) in enumerate(element_pairs, 1):
            system_name = f"{elem_A}-{elem_B}"

            # Resume 모드: 이미 완료된 시스템은 건너뛰기
            if system_name in completed_systems:
                print(f"\n{'#'*70}")
                print(f"# [{idx}/{len(element_pairs)}] {system_name} - ⏭️  이미 완료됨 (건너뛰기)")
                print(f"{'#'*70}")
                continue

            print(f"\n{'#'*70}")
            print(f"# [{idx}/{len(element_pairs)}] 시스템 실행 중")
            print(f"{'#'*70}")

            # 하나의 원소 조합에 대해 전체 파이프라인 실행
            result, detailed_data = run_experiment_for_pair(elem_A, elem_B, calc, relaxer, md_sim)
            all_results.append(result)
            all_detailed_data.extend(detailed_data)  # 상세 데이터 추가

            print(f"\n   ✅ {result['system']} 완료")
            if 'error' not in result:
                print(f"      - 총 구조: {result['total_structures']}개")
                print(f"      - 안정 구조: {result['stable_count']}개")
                print(f"      - MD 완료: {result['md_count']}개")

            # 중간 저장 (시스템 하나 끝날 때마다)
            save_intermediate_csv(csv_filename, all_detailed_data)

    # -------------------------------------------------------------------------
    # 4. [Final Report] 전체 요약
    # -------------------------------------------------------------------------
    print("\n\n" + "="*70)
    print("🎯 전체 파이프라인 실행 완료")
    print("="*70)

    # Resume 통계 출력
    if SimConfig.RESUME_MODE and completed_systems:
        print(f"\n📊 Resume 통계:")
        print(f"   - 기존 완료 시스템: {len(completed_systems)}개 (건너뜀)")
        print(f"   - 신규 계산 시스템: {len(all_results)}개")
        print(f"   - 총 시스템 수: {len(completed_systems) + len(all_results)}개")
        print()

    print(f"\n{'System':<20} | {'Structures':<12} | {'Stable':<10} | {'MD Done':<10}")
    print("-" * 70)

    total_stable = 0
    total_md = 0

    for res in all_results:
        if 'error' in res:
            print(f"{res['system']:<20} | {'ERROR':<12} | {'-':<10} | {'-':<10}")
        else:
            print(f"{res['system']:<20} | {res['total_structures']:<12} | {res['stable_count']:<10} | {res['md_count']:<10}")
            total_stable += res['stable_count']
            total_md += res['md_count']

    print("-" * 70)
    print(f"{'NEW TOTAL':<20} | {'':<12} | {total_stable:<10} | {total_md:<10}")
    print("="*70 + "\n")

    # -------------------------------------------------------------------------
    # 5. 최종 CSV 파일 확인
    # -------------------------------------------------------------------------
    if all_detailed_data:
        # 최종 저장 (마지막으로 한 번 더 저장)
        save_intermediate_csv(csv_filename, all_detailed_data)

        print(f"\n✅ 최종 CSV 저장 완료!")
        print(f"   파일명: {csv_filename}")
        print(f"   파일 위치: {os.path.abspath(csv_filename)}")
        print(f"   총 구조: {len(all_detailed_data)}개")
        print(f"\n📊 저장된 컬럼:")
        print(f"   [구조 정보]")
        print(f"   - system: 원소 조합 (예: Al-Mg)")
        print(f"   - formula: 화학식 (예: Mg49Pd5)")
        print(f"   - element_A, element_B: 개별 원소")
        print(f"   - ratio_A, ratio_B: 원소 비율 (0~1)")
        print(f"   - total_atoms: 총 원자 개수")
        print(f"   - lattice_a: 격자 상수 a (Angstrom)")
        print(f"   - density: 밀도 (g/cm^3)")
        print(f"   [열역학 물성]")
        print(f"   - energy_per_atom: 원자당 에너지 (eV/atom)")
        print(f"   - energy_above_hull: Convex Hull 위 에너지 (eV/atom)")
        print(f"   - is_stable: 열역학 안정성 (True/False)")
        print(f"   [MD 물성]")
        print(f"   - md_performed: MD 수행 여부 (True/False)")
        print(f"   - md_avg_temperature: MD 평균 온도 (K)")
        print(f"   - md_temp_fluctuation: 온도 변동률 (%)")
        print(f"   - md_avg_energy_per_atom: MD 평균 에너지 (eV/atom)")
        print(f"   - md_volume_change_percent: 부피 변화율 (%)")
        print(f"   - md_thermally_stable: 열적 안정성 (True/False)")
        print("="*70 + "\n")

        # -------------------------------------------------------------------------
        # 6. 실험 데이터 가져오기 및 검증 (Validation Phase)
        # -------------------------------------------------------------------------
        print("\n" + "="*70)
        print("📊 시뮬레이션-실험 데이터 검증 및 채점 시작")
        print("="*70 + "\n")

        # 검증 기능이 비활성화된 경우 건너뛰기
        if not SimConfig.ENABLE_VALIDATION:
            print("⏭️  실험 데이터 검증 기능이 비활성화되어 있습니다.")
            print("   (config.py의 ENABLE_VALIDATION = False)")
            print("\n" + "="*70)
            print("✅ 전체 파이프라인 (시뮬레이션) 완료!")
            print("="*70 + "\n")
            return

        try:
            # [Step 6-1] 실험 데이터 가져오기
            exp_miner = ExperimentalDataMiner()

            # 사용자 정의 CSV 사용 모드
            if SimConfig.CUSTOM_EXP_DATA_CSV:
                print(f"📂 사용자 정의 실험 데이터 사용: {SimConfig.CUSTOM_EXP_DATA_CSV}")
                exp_df = exp_miner.load_custom_csv(SimConfig.CUSTOM_EXP_DATA_CSV)

            # Auto 모드: CSV에서 실제 시뮬레이션한 시스템 목록 추출
            elif SimConfig.PIPELINE_MODE == "auto":
                print("⛏️  [Step 1/3] 시뮬레이션된 시스템 목록 확인 중...")
                print(f"   📊 데이터 소스: {SimConfig.VALIDATION_DATA_SOURCE}")
                print(f"   🔬 Theoretical 포함: {SimConfig.VALIDATION_USE_THEORETICAL}")

                sim_df = pd.read_csv(csv_filename)
                unique_systems = sim_df['system'].unique()
                print(f"   📋 발견된 시스템: {', '.join(unique_systems)}")

                # 각 시스템별로 실험 데이터 수집
                all_exp_data = []
                for system in unique_systems:
                    elem_a, elem_b = system.split('-')
                    print(f"\n   🔍 {system} 실험 레퍼런스 가져오는 중...")
                    sys_exp_df = exp_miner.fetch_binary_alloy_references(elem_a, elem_b)
                    if not sys_exp_df.empty:
                        all_exp_data.append(sys_exp_df)

                if all_exp_data:
                    exp_df = pd.concat(all_exp_data, ignore_index=True)
                    exp_df = exp_df.drop_duplicates(subset=['formula'])  # 중복 제거
                else:
                    exp_df = pd.DataFrame()

            # Manual 모드: 단일 시스템만 처리
            else:
                print(f"⛏️  [Step 1/3] {SimConfig.MANUAL_ELEMENT_A}-{SimConfig.MANUAL_ELEMENT_B} 실험 레퍼런스 가져오는 중...")
                print(f"   📊 데이터 소스: {SimConfig.VALIDATION_DATA_SOURCE}")
                print(f"   🔬 Theoretical 포함: {SimConfig.VALIDATION_USE_THEORETICAL}")

                exp_df = exp_miner.fetch_binary_alloy_references(
                    SimConfig.MANUAL_ELEMENT_A,
                    SimConfig.MANUAL_ELEMENT_B
                )

            if not exp_df.empty:
                # 실험 데이터 CSV로 저장 (설정에 따라)
                if SimConfig.VALIDATION_SAVE_EXP_DATA:
                    exp_csv_path = exp_miner.save_to_csv(exp_df, f"experimental_references_{timestamp}.csv")
                    print(f"   💾 실험 데이터 저장: {exp_csv_path}")
                else:
                    print("   ⏭️  실험 데이터 CSV 저장 건너뜀 (VALIDATION_SAVE_EXP_DATA = False)")

                # [Step 6-2] Validator가 읽을 수 있는 딕셔너리 형태로 변환
                print("\n🔄 [Step 2/3] 실험 데이터를 검증용 형식으로 변환 중...")
                experimental_ref = {}

                for _, row in exp_df.iterrows():
                    experimental_ref[row['formula']] = {
                        "lattice_a": row['exp_lattice_a'],
                        "density": row['exp_density']
                    }

                print(f"   ✅ {len(experimental_ref)}개의 실험 레퍼런스 준비 완료")
                print(f"   📋 레퍼런스 화학식: {', '.join(list(experimental_ref.keys())[:5])}...")

                # [Step 6-3] MaterialValidator로 채점 수행
                print("\n🎯 [Step 3/3] 시뮬레이션 결과 채점 중...")
                validator = MaterialValidator(csv_filename)
                report = validator.calculate_score(experimental_ref)

                if not report.empty:
                    # 결과 출력
                    validator.print_summary(report)

                    # 채점 결과 CSV로 저장 (설정에 따라)
                    if SimConfig.VALIDATION_SAVE_REPORT:
                        val_filename = f"validation_report_{timestamp}.csv"
                        report.to_csv(val_filename, index=False, encoding='utf-8-sig')
                        print(f"\n💾 채점 리포트 저장 완료: {val_filename}")
                        print(f"   파일 위치: {os.path.abspath(val_filename)}")
                    else:
                        print("\n⏭️  채점 리포트 CSV 저장 건너뜀 (VALIDATION_SAVE_REPORT = False)")

                    # 상세 통계
                    print(f"\n📈 채점 통계:")
                    print(f"   - 검증된 구조 수: {len(report)}개")
                    print(f"   - 평균 격자 오차: {report['lattice_error_pct'].mean():.2f}%")
                    print(f"   - 평균 밀도 오차: {report['density_error_pct'].mean():.2f}%")
                    print(f"   - 최고 정확도: {report['accuracy_score'].max():.2f}/100")
                    print(f"   - 최저 정확도: {report['accuracy_score'].min():.2f}/100")
                else:
                    print("   ⚠️  채점 결과가 비어있습니다. 시뮬레이션과 실험 데이터의 화학식이 일치하지 않을 수 있습니다.")

            else:
                print("   ⚠️  비교할 실험 데이터를 찾지 못했습니다.")
                print("   💡 Tip: MP API 키가 올바른지, Cu-Ni 실험 데이터가 존재하는지 확인하세요.")

        except Exception as e:
            print(f"\n❌ 채점 과정 중 오류 발생: {e}")
            print(f"   오류 타입: {type(e).__name__}")
            import traceback
            print(f"   상세 정보:\n{traceback.format_exc()}")

        print("\n" + "="*70)
        print("✅ 전체 파이프라인 (시뮬레이션 + 검증) 완료!")
        print("="*70 + "\n")

    else:
        print("⚠️  저장할 상세 데이터가 없습니다.\n")

if __name__ == "__main__":
    # =========================================================================
    # Windows 안전 가드: multiprocessing 사용 시 필수 설정
    # =========================================================================
    # freeze_support: PyInstaller 등으로 패키징할 때 필요
    mp.freeze_support()

    # set_start_method: 프로세스 시작 방식 설정
    # - 'spawn' (Windows 기본): 새 Python 인터프리터 시작 (안전하지만 느림)
    # - 'fork' (Linux 기본): 부모 프로세스 복제 (빠르지만 Windows 미지원)
    # - 'forkserver' (Unix 전용): 서버 프로세스를 통해 fork
    import sys
    if sys.platform == "win32":
        # Windows: spawn 강제 사용
        try:
            mp.set_start_method('spawn', force=True)
        except RuntimeError:
            pass  # 이미 설정된 경우 무시

        # Windows 사용자에게 병렬 처리 경고
        if SimConfig.PARALLEL_MD_EXECUTION:
            print("\n" + "="*70)
            print("⚠️  Windows에서 MD 병렬 처리가 활성화되어 있습니다!")
            print("   - 메모리 사용량이 매우 높을 수 있습니다")
            print("   - GPU 메모리 부족 시 프로그램이 멈출 수 있습니다")
            print("   - 안정성을 위해 config.py에서 PARALLEL_MD_EXECUTION = False 권장")
            print("="*70 + "\n")

            import time
            print("5초 후 실행합니다... (Ctrl+C로 중단 가능)")
            time.sleep(5)
    else:
        # Linux/Mac: fork 사용 가능
        try:
            mp.set_start_method('fork', force=True)
        except RuntimeError:
            pass

    # 메인 함수 실행
    main()
    