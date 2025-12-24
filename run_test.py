# run_test.py
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
# 1. 모듈 불러오기
from mattersim_dt.builder import RandomAlloyMixer
from mattersim_dt.engine import get_calculator, StructureRelaxer

def main():
    print("=== MatterSim Digital Twin Test ===")

    # [Step 1] Builder: 구조 생성 (Cu-Ni 합금)
    print("\n1. 구조 생성 중...")
    mixer = RandomAlloyMixer(base_element='Cu')
    raw_structure = mixer.generate_structure('Ni', ratio=0.3, supercell_size=3)
    print(f" -> 생성됨: {raw_structure.get_chemical_formula()}")

    # [Step 2] Engine: MatterSim 로딩
    print("\n2. MatterSim 엔진 시동...")
    calc = get_calculator(device='cuda') # <--- 'cuda'로 변경! # GPU 없으면 cpu, 있으면 cuda
    
    # [Step 3] Engine: 구조 최적화 (Relaxation)
    print("\n3. 구조 최적화(Relaxation) 수행...")
    relaxer = StructureRelaxer(calculator=calc)
    
    # 최적화 실행 (결과는 data/results 폴더에 저장됨)
    final_structure, energy = relaxer.run(raw_structure, save_traj=True)
    
    print("\n=== 모든 작업 완료 ===")
    print(f"최종 에너지: {energy:.4f} eV")

if __name__ == "__main__":
    main()