"""
Trajectory에서 특정 프레임 추출 스크립트
"""
from ase.io import Trajectory, write

def extract_frames(traj_file, output_format='xyz'):
    """
    Trajectory에서 주요 프레임을 추출하여 저장

    :param traj_file: trajectory 파일 경로
    :param output_format: 출력 형식 ('xyz', 'cif', 'pdb' 등)
    """
    print(f"📂 Trajectory 파일 로딩: {traj_file}")

    traj = Trajectory(traj_file, 'r')
    print(f"✅ 총 {len(traj)}개 프레임")

    # 첫 번째 프레임 (초기 구조)
    initial_atoms = traj[0]
    initial_file = f"initial_structure.{output_format}"
    write(initial_file, initial_atoms)
    print(f"💾 초기 구조 저장: {initial_file}")

    # 마지막 프레임 (최종 구조)
    final_atoms = traj[-1]
    final_file = f"final_structure.{output_format}"
    write(final_file, final_atoms)
    print(f"💾 최종 구조 저장: {final_file}")

    # 중간 프레임 (선택적)
    if len(traj) > 10:
        mid_idx = len(traj) // 2
        mid_atoms = traj[mid_idx]
        mid_file = f"middle_structure.{output_format}"
        write(mid_file, mid_atoms)
        print(f"💾 중간 구조 저장: {mid_file}")

    # 모든 프레임을 하나의 XYZ 파일로 저장 (애니메이션용)
    all_file = f"all_frames.{output_format}"
    write(all_file, traj)
    print(f"💾 전체 프레임 저장: {all_file}")

    traj.close()
    print(f"\n✅ 완료! {output_format} 파일들을 생성했습니다.")


if __name__ == "__main__":
    # 추출할 trajectory 파일 경로
    traj_file = "data/results/md_1000K.traj"

    # XYZ 형식으로 추출 (대부분의 분자 시각화 도구 지원)
    extract_frames(traj_file, output_format='xyz')
