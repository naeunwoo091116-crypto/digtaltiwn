"""
Trajectory 파일의 화학 구조 정보를 자세히 출력하는 스크립트
"""
from ase.io import Trajectory
from collections import Counter

def show_trajectory_info(traj_file):
    """
    Trajectory 파일의 상세 정보를 출력

    :param traj_file: trajectory 파일 경로
    """
    print("=" * 70)
    print(f"📂 Trajectory 파일: {traj_file}")
    print("=" * 70)

    # Trajectory 읽기
    traj = Trajectory(traj_file, 'r')

    # 첫 번째 프레임 (초기 구조)
    first_atoms = traj[0]

    # 1. 기본 정보
    print("\n🔬 화학 구조 정보:")
    print(f"   화학식: {first_atoms.get_chemical_formula()}")
    print(f"   Hill 표기법: {first_atoms.get_chemical_formula('hill')}")
    print(f"   총 원자 개수: {len(first_atoms)} 개")

    # 2. 원소별 개수
    symbols = first_atoms.get_chemical_symbols()
    symbol_counts = Counter(symbols)
    print(f"\n📊 원소별 구성:")
    for element, count in sorted(symbol_counts.items()):
        percentage = (count / len(first_atoms)) * 100
        print(f"   {element}: {count}개 ({percentage:.1f}%)")

    # 3. 원자 위치 (처음 10개만)
    print(f"\n📍 원자 위치 (처음 10개):")
    positions = first_atoms.get_positions()
    for i in range(min(10, len(first_atoms))):
        x, y, z = positions[i]
        print(f"   {i+1:3d}. {symbols[i]:2s}: ({x:8.4f}, {y:8.4f}, {z:8.4f}) Å")

    if len(first_atoms) > 10:
        print(f"   ... (나머지 {len(first_atoms) - 10}개 원자 생략)")

    # 4. 셀 정보
    if first_atoms.cell is not None and any(first_atoms.pbc):
        cell = first_atoms.get_cell()
        print(f"\n📦 시뮬레이션 셀:")
        print(f"   크기: {cell[0][0]:.3f} x {cell[1][1]:.3f} x {cell[2][2]:.3f} Å")
        print(f"   부피: {first_atoms.get_volume():.2f} ų")
        print(f"   주기 경계 조건: {first_atoms.pbc}")

    # 5. Trajectory 정보
    print(f"\n🎬 Trajectory 정보:")
    print(f"   총 프레임 수: {len(traj)} 개")

    # 에너지 정보 확인 (가능한 경우)
    try:
        first_energy = first_atoms.get_potential_energy()
        last_energy = traj[-1].get_potential_energy()
        print(f"   초기 에너지: {first_energy:.4f} eV")
        print(f"   최종 에너지: {last_energy:.4f} eV")
        print(f"   에너지 변화: {last_energy - first_energy:.4f} eV")
    except:
        print(f"   (에너지 정보 없음)")

    # 6. 구조 변화 (첫 프레임 vs 마지막 프레임)
    last_atoms = traj[-1]
    first_pos = first_atoms.get_positions()
    last_pos = last_atoms.get_positions()

    # RMSD (Root Mean Square Deviation) 계산
    rmsd = ((first_pos - last_pos) ** 2).sum(axis=1).mean() ** 0.5
    max_displacement = ((first_pos - last_pos) ** 2).sum(axis=1).max() ** 0.5

    print(f"\n📏 구조 변화:")
    print(f"   평균 원자 이동 (RMSD): {rmsd:.4f} Å")
    print(f"   최대 원자 이동: {max_displacement:.4f} Å")

    # 7. 전체 원자 목록 (간단히)
    print(f"\n🧬 전체 원자 목록:")
    atom_string = ' '.join([f"{s}{i+1}" for i, s in enumerate(symbols)])
    # 한 줄에 10개씩 출력
    words = atom_string.split()
    for i in range(0, len(words), 10):
        print(f"   {' '.join(words[i:i+10])}")

    print("\n" + "=" * 70)

    traj.close()


if __name__ == "__main__":
    import sys

    # 명령줄 인자로 파일 경로를 받거나 기본값 사용
    if len(sys.argv) > 1:
        traj_file = sys.argv[1]
    else:
        traj_file = "data/results/md_1000K.traj"

    show_trajectory_info(traj_file)
