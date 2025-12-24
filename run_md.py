# run_md.py
from mattersim_dt.builder import RandomAlloyMixer
from mattersim_dt.engine import get_calculator, StructureRelaxer, MDSimulator

def main():
    print("=== MatterSim 고온 가열 실험 (Molecular Dynamics) ===")

    # 1. 엔진 준비 (GPU 권장)
    calc = get_calculator(device='cuda')

    # 2. 구조 생성 (Cu-Ni 합금)
    print("\n[Step 1] 합금 구조 생성 중...")
    mixer = RandomAlloyMixer('Cu')
    # MD는 원자가 많아야 움직임이 잘 보입니다. size=4 (64개) 정도로 설정
    atoms = mixer.generate_structure('Ni', ratio=0.3, supercell_size=4)
    print(f" -> 원자 개수: {len(atoms)}개")

    # 3. (선택사항) 구조 최적화 (Relaxation)
    # MD를 돌리기 전에, 일단 안정된 자세를 잡고 시작하는 것이 좋습니다.
    print("\n[Step 2] 초기 구조 안정화 (Relaxation)...")
    relaxer = StructureRelaxer(calculator=calc)
    relaxer.run(atoms, fmax=0.1) # 대충 0.1 정도면 충분

    # 4. MD 시뮬레이션 (가열)
    target_temp = 1000  # 1000 Kelvin (약 726도)
    md_steps = 500      # 테스트용이라 짧게 (실제 연구용은 10000 이상)
    
    print(f"\n[Step 3] {target_temp}K 로 가열 시작! ({md_steps} steps)")
    simulator = MDSimulator(calculator=calc)
    
    # 실행!
    final_atoms = simulator.run(atoms, temperature=target_temp, steps=md_steps, time_step=1.0)

    print("\n💡 팁: 생성된 'data/results/md_1000K.traj' 파일을 'ase gui' 명령어로 열어보세요.")
    print("   명령어: ase gui data/results/md_1000K.traj")

if __name__ == "__main__":
    main()