# run_ternary_pipeline.py - 3원소 합금 파이프라인
import pandas as pd
import os
from datetime import datetime
from pymatgen.core import Composition

# ============================================================================
# MatterSim 모듈 임포트
# ============================================================================
from mattersim_dt.core import SimConfig
from mattersim_dt.builder import TernaryAlloyMixer
from mattersim_dt.engine import get_calculator, StructureRelaxer, MDSimulator
from mattersim_dt.analysis import StabilityAnalyzer, MDAnalyzer
from mattersim_dt.miner import TernaryMaterialMiner

import torch
print(f"🔍 PyTorch GPU Available: {torch.cuda.is_available()}")
print(f"🔍 Current Device Name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")

# ============================================================================
# CSV에서 3원소 조합 로드 함수
# ============================================================================
def load_element_triplets_from_csv(csv_path, max_systems=None):
    """
    CSV 파일에서 3원소 조합을 추출하는 함수

    Args:
        csv_path: CSV 파일 경로
        max_systems: 최대 시스템 수 (None이면 전체)

    Returns:
        [(elem_A, elem_B, elem_C), ...] 형태의 리스트
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
    element_triplets = set()

    for formula in df['formula'].dropna():
        try:
            # Pymatgen으로 화학식 파싱
            comp = Composition(formula)
            elements = sorted([str(el) for el in comp.elements])

            # 3원소 시스템만 추출
            if len(elements) == 3:
                triplet = tuple(elements)
                element_triplets.add(triplet)
        except:
            continue

    # set -> list 변환
    triplets_list = list(element_triplets)

    # 최대 개수 제한
    if max_systems is not None:
        triplets_list = triplets_list[:max_systems]

    print(f"✅ 총 {len(triplets_list)}개의 3원소 시스템 발견")
    return triplets_list

# ============================================================================
# CSV 저장 함수
# ============================================================================
def save_ternary_results(results_df, element_A, element_B, element_C, detailed_data):
    """
    3원소 합금 실험 결과를 CSV로 저장

    Args:
        results_df: StabilityAnalyzer의 분석 결과 DataFrame
        element_A, element_B, element_C: 원소 기호
        detailed_data: 상세 물성 데이터 리스트
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    system_name = f"{element_A}-{element_B}-{element_C}"

    # 1. 안정성 분석 결과 저장
    stability_csv = f"ternary_stability_{system_name}_{timestamp}.csv"
    results_df.to_csv(stability_csv, index=False, encoding='utf-8-sig')
    print(f"   💾 안정성 결과 저장: {stability_csv}")

    # 2. 상세 물성 데이터 저장
    if detailed_data:
        detail_csv = f"ternary_details_{system_name}_{timestamp}.csv"
        df_details = pd.DataFrame(detailed_data)
        df_details.to_csv(detail_csv, index=False, encoding='utf-8-sig')
        print(f"   💾 상세 데이터 저장: {detail_csv}")

# ============================================================================
# 하나의 3원소 조합에 대해 전체 파이프라인 실행
# ============================================================================
def run_ternary_experiment(element_A, element_B, element_C, calc, relaxer, md_sim):
    """
    하나의 3원소 조합에 대해 전체 파이프라인 실행

    Args:
        element_A, element_B, element_C: 원소 기호
        calc: MatterSim 계산기
        relaxer: StructureRelaxer
        md_sim: MDSimulator

    Returns:
        dict: 실험 결과 요약
    """
    print(f"\n{'='*70}")
    print(f"🎯 Target System: {element_A} - {element_B} - {element_C}")
    print(f"{'='*70}")

    # StabilityAnalyzer 생성
    analyzer = StabilityAnalyzer(threshold=SimConfig.TERNARY_STABILITY_THRESHOLD)

    # 상세 물성 데이터 저장용 리스트
    detailed_data = []

    # 이완된 구조 저장용 딕셔너리
    relaxed_structures = {}

    # =========================================================================
    # Phase 1-1: 순수 원소 기준값 계산 (3개)
    # =========================================================================
    print("\n=== [Phase 1-1] 순수 원소 기준 구조 계산 ===")

    mixer = TernaryAlloyMixer(element_A, element_B, element_C)

    for elem in [element_A, element_B, element_C]:
        print(f"   🔹 {elem} 순수 구조 이완 중...")
        try:
            # 순수 원소 구조 생성
            atoms = mixer.generate_pure_element_structure(
                elem,
                supercell_size=SimConfig.TERNARY_SUPERCELL_SIZE
            )
            atoms.calc = calc

            # 구조 이완
            relaxed, e_total = relaxer.run(atoms, save_traj=SimConfig.SAVE_RELAX_TRAJ)

            # StabilityAnalyzer에 등록
            analyzer.add_result(relaxed, e_total)

            # 저장
            formula_full = relaxed.get_chemical_formula()
            formula_reduced = Composition(formula_full).reduced_formula
            relaxed_structures[formula_reduced] = relaxed.copy()

            e_per_atom = e_total / len(atoms)
            print(f"     ✓ 완료: {e_per_atom:.4f} eV/atom")

            # 상세 데이터 추가
            detailed_data.append({
                'system': f"{element_A}-{element_B}-{element_C}",
                'formula': formula_reduced,
                'ratio_tuple': str((1, 0, 0) if elem == element_A else (0, 1, 0) if elem == element_B else (0, 0, 1)),
                'is_pure': True,
                'base_element': elem,
                'num_atoms': len(relaxed),
                'energy_total': e_total,
                'energy_per_atom': e_per_atom,
            })

        except Exception as e:
            print(f"     ❌ 오류 발생: {e}")
            return {"system": f"{element_A}-{element_B}-{element_C}", "error": str(e)}

    # =========================================================================
    # Phase 1-2: 조성별 합금 생성 및 이완
    # =========================================================================
    print("\n=== [Phase 1-2] 조성별 합금 구조 생성 및 이완 ===")

    # 조성 리스트 생성 (모드별로 다르게)
    if SimConfig.TERNARY_COMPOSITION_MODE == "mined":
        # Materials Project에서 실제 비율 마이닝
        print(f"   🔎 조성 모드: Materials Project 마이닝")

        try:
            ternary_miner = TernaryMaterialMiner(api_key=SimConfig.MP_API_KEY)
            mined_results = ternary_miner.search_ternary_alloys(element_A, element_B, element_C)

            # 마이닝 결과 요약 출력
            ternary_miner.print_summary(mined_results)

            # 중복 제거한 비율 추출
            compositions = ternary_miner.get_unique_ratios(mined_results)

            # 최대 개수 제한
            if SimConfig.TERNARY_MINING_MAX_RATIOS and len(compositions) > SimConfig.TERNARY_MINING_MAX_RATIOS:
                compositions = compositions[:SimConfig.TERNARY_MINING_MAX_RATIOS]
                print(f"   ℹ️  최대 비율 제한: {SimConfig.TERNARY_MINING_MAX_RATIOS}개로 제한")

            if not compositions:
                print(f"   ⚠️  Materials Project에서 {element_A}-{element_B}-{element_C} 조성을 찾지 못했습니다.")
                print(f"   → 균등 분할 모드로 자동 전환합니다.")
                compositions = TernaryAlloyMixer.generate_composition_ratios(
                    SimConfig.TERNARY_COMPOSITION_TOTAL
                )

        except Exception as e:
            print(f"   ⚠️  마이닝 중 오류: {e}")
            print(f"   → 균등 분할 모드로 자동 전환합니다.")
            compositions = TernaryAlloyMixer.generate_composition_ratios(
                SimConfig.TERNARY_COMPOSITION_TOTAL
            )

    else:
        # 균등 분할 방식으로 생성
        print(f"   🔧 조성 모드: 균등 분할 생성")
        compositions = TernaryAlloyMixer.generate_composition_ratios(
            SimConfig.TERNARY_COMPOSITION_TOTAL
        )
        print(f"   ℹ️  조성 범위: {SimConfig.TERNARY_COMPOSITION_TOTAL}")

    print(f"   ℹ️  총 조성 개수: {len(compositions)}개")

    for idx, ratio_tuple in enumerate(compositions, 1):
        print(f"   [{idx}/{len(compositions)}] 조성 {ratio_tuple}: {element_A}:{element_B}:{element_C}")

        try:
            # 3원소 합금 구조 생성
            atoms = mixer.generate_ternary_structure(
                ratio_tuple,
                supercell_size=SimConfig.TERNARY_SUPERCELL_SIZE
            )
            atoms.calc = calc

            # 구조 이완
            relaxed, e_total = relaxer.run(atoms, save_traj=SimConfig.SAVE_RELAX_TRAJ)

            # StabilityAnalyzer에 등록
            analyzer.add_result(relaxed, e_total)

            # 저장
            formula_full = relaxed.get_chemical_formula()
            formula_reduced = Composition(formula_full).reduced_formula
            relaxed_structures[formula_reduced] = relaxed.copy()

            e_per_atom = e_total / len(atoms)
            print(f"     ✓ 완료: {formula_reduced} = {e_per_atom:.4f} eV/atom")

            # 상세 데이터 추가
            composition_dict = atoms.info.get('composition', {})
            detailed_data.append({
                'system': f"{element_A}-{element_B}-{element_C}",
                'formula': formula_reduced,
                'ratio_tuple': str(ratio_tuple),
                'is_pure': False,
                'base_element': atoms.info.get('base_element', mixer.base_element),
                'num_atoms': len(relaxed),
                'energy_total': e_total,
                'energy_per_atom': e_per_atom,
                'composition': str(composition_dict),
            })

        except Exception as e:
            print(f"     ❌ 오류 발생: {e}")
            continue

    # =========================================================================
    # Phase 2: 안정성 필터링
    # =========================================================================
    print("\n=== [Phase 2] 안정성 분석 및 필터링 ===")

    results_df = analyzer.analyze()

    if results_df.empty:
        print("   ⚠️  분석 결과가 없습니다.")
        return {"system": f"{element_A}-{element_B}-{element_C}", "stable_count": 0}

    stable_structures = results_df[results_df['is_stable'] == True]
    print(f"   ✅ 안정 구조: {len(stable_structures)}/{len(results_df)}개")

    # 안정성 결과를 detailed_data에 병합
    for i, row in results_df.iterrows():
        formula = row['formula']
        # detailed_data에서 해당 formula 찾아서 안정성 정보 추가
        for data in detailed_data:
            if data['formula'] == formula:
                data['energy_above_hull'] = row.get('energy_above_hull', None)
                data['is_stable'] = row.get('is_stable', False)

    # =========================================================================
    # Phase 3: MD 시뮬레이션 (안정한 구조만)
    # =========================================================================
    print("\n=== [Phase 3] MD 시뮬레이션 (안정 구조만) ===")

    if len(stable_structures) == 0:
        print("   ℹ️  안정한 구조가 없어 MD를 건너뜁니다.")
    else:
        for idx, row in stable_structures.iterrows():
            formula = row['formula']
            print(f"   🔥 {formula} MD 시작...")

            try:
                atoms = relaxed_structures.get(formula)

                if atoms is None:
                    print(f"     ⚠️  구조를 찾을 수 없습니다: {formula}")
                    continue

                atoms.calc = calc

                # MD 실행
                final_atoms, traj_file = md_sim.run(
                    atoms,
                    temperature=SimConfig.MD_TEMPERATURE,
                    steps=SimConfig.MD_STEPS,
                    save_interval=50
                )

                print(f"     ✓ MD 완료: {traj_file}")

                # MD 분석
                if traj_file and os.path.exists(traj_file):
                    md_analyzer = MDAnalyzer(traj_file)
                    md_results = md_analyzer.analyze()

                    # detailed_data에 MD 결과 추가
                    for data in detailed_data:
                        if data['formula'] == formula:
                            data['md_traj_file'] = traj_file
                            data['md_avg_energy'] = md_results.get('avg_energy_per_atom', None)
                            data['md_final_density'] = md_results.get('final_density', None)

            except Exception as e:
                print(f"     ❌ MD 실패: {e}")
                continue

    # =========================================================================
    # 결과 저장
    # =========================================================================
    print("\n=== [결과 저장] ===")
    save_ternary_results(results_df, element_A, element_B, element_C, detailed_data)

    return {
        "system": f"{element_A}-{element_B}-{element_C}",
        "total_structures": len(results_df),
        "stable_count": len(stable_structures),
        "base_element": mixer.base_element,
    }

# ============================================================================
# 메인 함수
# ============================================================================
def main():
    """메인 실행 함수"""
    print("="*70)
    print("  MatterSim Digital Twin - 3원소 합금 파이프라인")
    print("="*70)

    # 설정 초기화
    SimConfig.setup()

    # 3원소 모드 활성화 체크
    if not SimConfig.ENABLE_TERNARY_ALLOY:
        print("\n⚠️  3원소 합금 모드가 비활성화되어 있습니다.")
        print("   config.py에서 ENABLE_TERNARY_ALLOY = True로 설정하세요.")
        return

    print(f"\n📋 설정 정보:")
    print(f"   - 모드: {SimConfig.PIPELINE_MODE}")
    print(f"   - 디바이스: {SimConfig.DEVICE}")
    print(f"   - 슈퍼셀 크기: {SimConfig.TERNARY_SUPERCELL_SIZE}")
    print(f"   - 조성 모드: {SimConfig.TERNARY_COMPOSITION_MODE}")
    if SimConfig.TERNARY_COMPOSITION_MODE == "generated":
        print(f"   - 조성 범위: {SimConfig.TERNARY_COMPOSITION_TOTAL}")
    else:
        print(f"   - 마이닝 최대 비율: {SimConfig.TERNARY_MINING_MAX_RATIOS if SimConfig.TERNARY_MINING_MAX_RATIOS else '전체'}")
    print(f"   - 안정성 임계값: {SimConfig.TERNARY_STABILITY_THRESHOLD} eV/atom")
    print(f"   - MD 온도: {SimConfig.MD_TEMPERATURE} K")
    print(f"   - MD 스텝: {SimConfig.MD_STEPS}")

    # 계산기 초기화
    print(f"\n🔧 MatterSim 계산기 초기화 중...")
    calc = get_calculator(device=SimConfig.DEVICE)
    relaxer = StructureRelaxer(calculator=calc)
    md_sim = MDSimulator(calculator=calc)
    print("   ✓ 계산기 준비 완료")

    # =========================================================================
    # 모드별 실행
    # =========================================================================
    if SimConfig.PIPELINE_MODE == "auto":
        print("\n🤖 Auto 모드: CSV에서 3원소 시스템 자동 로드")

        triplets = load_element_triplets_from_csv(
            SimConfig.MINER_CSV_PATH,
            max_systems=SimConfig.MAX_SYSTEMS
        )

        if not triplets:
            print("⚠️  실행할 3원소 시스템이 없습니다.")
            return

        print(f"\n실행할 시스템: {len(triplets)}개")
        for elem_A, elem_B, elem_C in triplets:
            print(f"  - {elem_A}-{elem_B}-{elem_C}")

        # 각 시스템별 실행
        for idx, (elem_A, elem_B, elem_C) in enumerate(triplets, 1):
            print(f"\n\n{'#'*70}")
            print(f"# [{idx}/{len(triplets)}] {elem_A}-{elem_B}-{elem_C} 시스템 실행")
            print(f"{'#'*70}")

            result = run_ternary_experiment(elem_A, elem_B, elem_C, calc, relaxer, md_sim)
            print(f"\n결과: {result}")

    elif SimConfig.PIPELINE_MODE == "manual":
        print("\n✋ Manual 모드: 수동 지정 원소")
        print(f"   원소: {SimConfig.MANUAL_ELEMENT_A} - {SimConfig.MANUAL_ELEMENT_B} - {SimConfig.MANUAL_ELEMENT_C}")

        result = run_ternary_experiment(
            SimConfig.MANUAL_ELEMENT_A,
            SimConfig.MANUAL_ELEMENT_B,
            SimConfig.MANUAL_ELEMENT_C,
            calc, relaxer, md_sim
        )

        print(f"\n최종 결과: {result}")

    else:
        print(f"⚠️  알 수 없는 모드: {SimConfig.PIPELINE_MODE}")
        print("   config.py에서 PIPELINE_MODE를 'auto' 또는 'manual'로 설정하세요.")

    print("\n" + "="*70)
    print("  파이프라인 실행 완료")
    print("="*70)

if __name__ == "__main__":
    main()
