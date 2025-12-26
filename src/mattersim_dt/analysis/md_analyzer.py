from ase.io import Trajectory
from ase import units
import numpy as np

class MDAnalyzer:
    """
    MD 시뮬레이션 결과(trajectory)를 분석하여 열적 물성을 계산하는 클래스
    """

    def __init__(self, traj_file: str):
        """
        :param traj_file: MD trajectory 파일 경로 (예: "md_1000K.traj")
        """
        self.traj_file = traj_file
        self.traj = None

    def analyze(self):
        """
        Trajectory 파일을 읽고 열적 물성을 분석 (초기 20% 평형화 구간 제외)
        """
        try:
            # Trajectory 파일 읽기
            self.traj = Trajectory(self.traj_file, 'r')

            if len(self.traj) == 0:
                return {"error": "Empty trajectory"}

            # ---------------------------------------------------------
            # [수정안 2 적용] 초기 20% 프레임 건너뛰기 (Equilibration 제외)
            # ---------------------------------------------------------
            total_frames = len(self.traj)
            skip_frames = int(total_frames * 0.2)  # 앞부분 20% 계산
            analyzed_traj = self.traj[skip_frames:] # 분석에 사용할 구간 슬라이싱
            
            if len(analyzed_traj) == 0:
                analyzed_traj = self.traj # 혹시 데이터가 너무 적으면 전체 사용
            # ---------------------------------------------------------

            # 1. 에너지 및 온도 분석
            energies = []
            temperatures = []

            # self.traj 대신 analyzed_traj를 사용하여 반복문 실행
            for atoms in analyzed_traj:
                if atoms.calc is None:
                    continue

                try:
                    epot = atoms.get_potential_energy()
                    ekin = atoms.get_kinetic_energy()
                    # 온도 계산 (K)
                    temp = ekin / (1.5 * len(atoms) * units.kB)

                    energies.append(epot)
                    temperatures.append(temp)
                except:
                    continue

            if not energies:
                return {"error": "No energy data available"}

            # 2. 구조 변화 분석
            final_atoms = analyzed_traj[-1]
            initial_atoms = self.traj[0] # 부피 변화는 '최초' 구조와 비교해야 하므로 self.traj[0] 유지

            # 초기 대비 최종 구조의 부피 변화율
            volume_change = (final_atoms.get_volume() - initial_atoms.get_volume()) / initial_atoms.get_volume() * 100

            # 3. 온도 안정성 분석
            temp_mean = np.mean(temperatures)
            temp_std = np.std(temperatures)
            temp_fluctuation = (temp_std / temp_mean * 100) if temp_mean > 0 else 0

            # 4. 에너지 안정성 분석
            energy_mean = np.mean(energies)
            energy_std = np.std(energies)
            energy_per_atom_mean = energy_mean / len(final_atoms)
            energy_per_atom_std = energy_std / len(final_atoms)

            # 5. 구조 안정성 판정 (수정안 1의 완화된 기준 적용)
            # 온도 변동 10%, 부피 변화 15%로 기준 완화
            is_thermally_stable = (temp_fluctuation < 10.0) and (abs(volume_change) < 15.0)

            results = {
                "trajectory_frames": len(analyzed_traj),
                "total_frames_original": total_frames,
                "avg_temperature": temp_mean,
                "temperature_std": temp_std,
                "temperature_fluctuation_percent": temp_fluctuation,
                "avg_energy_per_atom": energy_per_atom_mean,
                "energy_std_per_atom": energy_per_atom_std,
                "volume_change_percent": volume_change,
                "is_thermally_stable": is_thermally_stable,
                "final_formula": final_atoms.get_chemical_formula()
            }

            return results

        except Exception as e:
            return {"error": str(e)}
        finally:
            if self.traj is not None:
                self.traj.close()

    def print_summary(self, results: dict):
        """
        분석 결과를 보기 좋게 출력
        """
        if "error" in results:
            print(f"   ❌ 분석 오류: {results['error']}")
            return

        print(f"\n   📊 MD 분석 결과:")
        print(f"      - Trajectory 프레임: {results['trajectory_frames']}개")
        print(f"      - 평균 온도: {results['avg_temperature']:.1f} ± {results['temperature_std']:.1f} K")
        print(f"      - 온도 변동: {results['temperature_fluctuation_percent']:.2f}%")
        print(f"      - 평균 에너지: {results['avg_energy_per_atom']:.4f} ± {results['energy_std_per_atom']:.4f} eV/atom")
        print(f"      - 부피 변화: {results['volume_change_percent']:.2f}%")

        if results['is_thermally_stable']:
            print(f"      - 열적 안정성: ✅ 안정")
        else:
            print(f"      - 열적 안정성: ⚠️  불안정 (온도/부피 변동 큼)")