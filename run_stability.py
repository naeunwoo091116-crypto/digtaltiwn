# run_stability.py (업그레이드 버전)
from mattersim_dt.builder import RandomAlloyMixer
from mattersim_dt.engine import get_calculator, StructureRelaxer
from mattersim_dt.analysis import StabilityAnalyzer

def calculate_energy(element_name, ratio_ni, calc, relaxer, size=1):
    """구조를 만들고 에너지를 계산하는 헬퍼 함수"""
    print(f"\n🧪 시뮬레이션: Cu-Ni (Ni 비율: {ratio_ni*100}%)")
    
    if ratio_ni == 0: # 순수 Cu
        mixer = RandomAlloyMixer('Cu')
        atoms = mixer.base_atoms
    elif ratio_ni == 1: # 순수 Ni
        mixer = RandomAlloyMixer('Ni')
        atoms = mixer.base_atoms
    else: # 합금
        mixer = RandomAlloyMixer('Cu')
        atoms = mixer.generate_structure('Ni', ratio=ratio_ni, supercell_size=3)
        
    atoms.calc = calc
    relaxed_atoms, energy = relaxer.run(atoms, save_traj=False)
    return relaxed_atoms, energy

def main():
    print("=== MatterSim x Pymatgen 고정밀 안정성 분석 ===")
    
    # 1. 엔진 준비
    calc = get_calculator(device='cuda')
    relaxer = StructureRelaxer(calculator=calc)
    
    # 2. 분석기(Pymatgen) 준비
    analyzer = StabilityAnalyzer()

    # --- 데이터 수집 단계 ---
    # 정확한 분석을 위해선 [순수 A], [순수 B], [합금 AB] 데이터가 모두 분석기에 들어가야 합니다.
    
    # (1) 순수 구리 (Cu)
    atoms_cu, e_cu = calculate_energy('Cu', 0.0, calc, relaxer)
    analyzer.add_result(atoms_cu, e_cu)
    
    # (2) 순수 니켈 (Ni)
    atoms_ni, e_ni = calculate_energy('Ni', 1.0, calc, relaxer)
    analyzer.add_result(atoms_ni, e_ni)
    
    # (3) 우리가 궁금한 합금 (Cu 7 : Ni 3)
    atoms_alloy, e_alloy = calculate_energy('Cu', 0.3, calc, relaxer)
    analyzer.add_result(atoms_alloy, e_alloy)

    # --- 최종 분석 단계 ---
    print("\n📊 ---------------- 결과 리포트 ---------------- 📊")
    results = analyzer.analyze()
    
    for res in results:
        status = "✅ 안정 (Stable)" if res['is_stable'] else "❌ 불안정 (Unstable)"
        print(f"물질: {res['formula']:<10} | 상태: {status} | 불안정도(E_above_hull): {res['energy_above_hull']:.4f} eV/atom")
        
        if not res['is_stable']:
            print(f"   ㄴ 설명: 이 물질은 {res['energy_above_hull']:.4f} eV 만큼 에너지가 높아서 분해될 것입니다.")

if __name__ == "__main__":
    main()