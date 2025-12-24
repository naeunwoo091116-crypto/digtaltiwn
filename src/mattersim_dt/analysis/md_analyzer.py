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
        Trajectory 파일을 읽고 열적 물성을 분석

        Returns:
            dict: 분석 결과
        """
        try:
            # Trajectory 파일 읽기
            self.traj = Trajectory(self.traj_file, 'r')

            if len(self.traj) == 0:
                return {"error": "Empty trajectory"}

            # 1. 에너지 분석
            energies = []
            temperatures = []

            for atoms in self.traj:
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

            if not energies:
                return {"error": "No energy data available"}

            # 2. 구조 변화 분석 (RDF - 동경 분포 함수는 계산 비용이 크므로 생략)
            # 대신 원자 간 평균 거리 변화를 추적
            final_atoms = self.traj[-1]
            initial_atoms = self.traj[0]

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

            # 5. 구조 안정성 판정 (간단한 기준)
            # - 온도 변동이 5% 이하
            # - 부피 변화가 10% 이하
            is_thermally_stable = (temp_fluctuation < 5.0) and (abs(volume_change) < 10.0)

            results = {
                "trajectory_frames": len(self.traj),
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
