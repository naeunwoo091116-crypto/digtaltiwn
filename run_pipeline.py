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
from mattersim_dt.analysis import StabilityAnalyzer, MDAnalyzer

import torch
print(f"🔍 PyTorch GPU Available: {torch.cuda.is_available()}")
print(f"🔍 Current Device Name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")
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

            detailed_data.append({
                'system': f"{element_A}-{element_B}",
                'formula': formula,
                'element_A': elements[0] if len(elements) > 0 else element_A,
                'element_B': elements[1] if len(elements) > 1 else element_B,
                'ratio_A': fractions[0] / sum(fractions) if len(fractions) > 0 else 1.0,
                'ratio_B': fractions[1] / sum(fractions) if len(fractions) > 1 else 0.0,
                'total_atoms': len(atoms_data),
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
    # [Phase 3] MD 시뮬레이션 (MDSimulator 사용)
    # -------------------------------------------------------------------------
    print("\n=== [Phase 3] 분자동역학 시뮬레이션 (안정 구조만 - 배치 처리) ===")

    md_count = 0

    if not stable_formulas:
        print("   ℹ️  안정한 구조가 없어 MD를 건너뜁니다.")
    else:
        print(f"   🔥 {len(stable_formulas)}개 구조에 대해 배치 MD 수행")

        # 1. MD 대상 구조들을 리스트로 모으기
        atoms_to_md = []
        valid_formulas = [] # 분석 시 매칭을 위해 수집된 화학식 리스트
        
        for formula in stable_formulas:
            atoms = relaxed_structures.get(formula)
            if atoms is None:
                continue
            
            # MD를 위해 슈퍼셀 크기 조정 (최소 200개 이상 권장)
            if len(atoms) < 200:
                # (2,2,2) 확장이 너무 크면 (2,2,1) 등으로 조절 가능
                atoms = atoms * (2, 2, 2)
            
            atoms_to_md.append(atoms)
            valid_formulas.append(formula)

        try:
            # 2. BatchMDSimulator 생성 및 실행
            from mattersim_dt.engine import BatchMDSimulator
            # SimConfig에 설정된 RATIO_BATCH_SIZE(예: 4)만큼 GPU에서 동시에 계산합니다.
            batch_md_sim = BatchMDSimulator(calc, batch_size=SimConfig.RATIO_BATCH_SIZE)
            
            traj_files = batch_md_sim.run_batch(
                atoms_to_md,
                temperature=SimConfig.MD_TEMPERATURE,
                steps=SimConfig.MD_STEPS,
                save_interval=50
            )

            # 3. 생성된 Trajectory 파일들을 순회하며 분석
            for formula, traj_file in zip(valid_formulas, traj_files):
                print(f"\n   🔹 {formula} - MD 결과 분석 중...")
                
                md_analyzer = MDAnalyzer(traj_file)
                md_results = md_analyzer.analyze()

                if "error" not in md_results:
                    md_analyzer.print_summary(md_results)
                    md_count += 1

                    # CSV 저장을 위한 detailed_data 업데이트
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

        except Exception as e:
            print(f"     ❌ 배치 MD 실행 중 오류 발생: {e}")

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

    # CSV 파일명 미리 생성 (중간 저장용)
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"pipeline_results_{timestamp}.csv"
    print(f"\n💾 결과 파일: {csv_filename} (진행 중 자동 저장)")

    print(f"\n⚙️  설정 로딩:")
    print(f"   - 파이프라인 모드: {SimConfig.PIPELINE_MODE}")
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
    all_detailed_data = []  # 모든 상세 데이터를 모을 리스트

    if SimConfig.PARALLEL_SYSTEM_CALCULATION and SimConfig.NUM_GPUS > 1:
        # 다중 GPU 병렬 처리
        print(f"🚀 다중 GPU 모드: {SimConfig.NUM_GPUS}개 GPU 사용")
        print("⚠️  주의: 이 모드는 복잡하므로 개발 중입니다. 현재는 순차 실행합니다.\n")
        # TODO: 실제 멀티프로세싱 구현 (복잡도가 높아 일단 순차 실행)

        for idx, (elem_A, elem_B) in enumerate(element_pairs, 1):
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
    print(f"{'TOTAL':<20} | {'':<12} | {total_stable:<10} | {total_md:<10}")
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
    else:
        print("⚠️  저장할 상세 데이터가 없습니다.\n")

if __name__ == "__main__":
    main()