"""
MD Trajectory 파일 분석 및 시각화 스크립트
"""
from ase.io import Trajectory
import matplotlib.pyplot as plt
import numpy as np
from ase import units

def analyze_trajectory(traj_file):
    """
    Trajectory 파일 분석

    :param traj_file: trajectory 파일 경로
    """
    print(f"📂 Trajectory 파일 로딩: {traj_file}")

    # Trajectory 읽기
    traj = Trajectory(traj_file, 'r')

    print(f"✅ 총 {len(traj)}개 프레임")

    # 에너지 및 온도 추출
    energies = []
    temperatures = []

    for atoms in traj:
        if atoms.calc is None:
            continue

        try:
            epot = atoms.get_potential_energy()
            ekin = atoms.get_kinetic_energy()
            temp = ekin / (1.5 * len(atoms) * units.kB)

            energies.append(epot)
            temperatures.append(temp)
        except:
            continue

    # 그래프 그리기
    fig, axes = plt.subplots(2, 1, figsize=(10, 8))

    # 1. 에너지 변화
    axes[0].plot(energies, 'b-', linewidth=1)
    axes[0].set_xlabel('MD Step')
    axes[0].set_ylabel('Potential Energy (eV)')
    axes[0].set_title('Energy Evolution')
    axes[0].grid(True, alpha=0.3)

    # 2. 온도 변화
    axes[1].plot(temperatures, 'r-', linewidth=1)
    axes[1].set_xlabel('MD Step')
    axes[1].set_ylabel('Temperature (K)')
    axes[1].set_title('Temperature Evolution')
    axes[1].axhline(y=np.mean(temperatures), color='k', linestyle='--',
                    label=f'Average: {np.mean(temperatures):.1f} K')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    plt.tight_layout()
    plt.savefig('trajectory_analysis.png', dpi=150)
    print(f"✅ 그래프 저장: trajectory_analysis.png")
    plt.show()

    # 통계 출력
    print(f"\n📊 통계:")
    print(f"   평균 에너지: {np.mean(energies):.4f} ± {np.std(energies):.4f} eV")
    print(f"   평균 온도: {np.mean(temperatures):.1f} ± {np.std(temperatures):.1f} K")
    print(f"   에너지 범위: {min(energies):.4f} ~ {max(energies):.4f} eV")
    print(f"   온도 범위: {min(temperatures):.1f} ~ {max(temperatures):.1f} K")

    # 구조 정보
    final_atoms = traj[-1]
    print(f"\n🔬 구조 정보:")
    print(f"   화학식: {final_atoms.get_chemical_formula()}")
    print(f"   원자 개수: {len(final_atoms)}")
    print(f"   부피: {final_atoms.get_volume():.2f} Ų")

    traj.close()


if __name__ == "__main__":
    # 분석할 trajectory 파일 경로
    traj_file = "data/results/md_1000K.traj"

    analyze_trajectory(traj_file)
