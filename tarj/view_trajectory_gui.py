"""
ASE GUI를 사용한 Trajectory 3D 시각화
"""
from ase.io import Trajectory
from ase.visualize import view

def view_trajectory_3d(traj_file):
    """
    ASE GUI로 trajectory를 3D 애니메이션으로 시각화

    :param traj_file: trajectory 파일 경로
    """
    print(f"📂 Trajectory 파일 로딩: {traj_file}")

    # Trajectory 읽기
    traj = Trajectory(traj_file, 'r')

    print(f"✅ 총 {len(traj)}개 프레임")
    print(f"🎬 ASE GUI 시작 중... (창이 열립니다)")

    # ASE GUI로 시각화
    # 화살표 키로 프레임 이동 가능
    view(traj)


if __name__ == "__main__":
    # 시각화할 trajectory 파일 경로
    traj_file = "data/results/md_1000K.traj"

    view_trajectory_3d(traj_file)
