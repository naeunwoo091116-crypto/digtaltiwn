from ase import Atoms, units
# Langevin 대신 NPT 임포트
from ase.md.npt import NPT 
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution, Stationary
from ase.io import Trajectory
import os
import numpy as np

class MDSimulator:
    """
    MatterSim을 엔진으로 사용하여 분자 동역학(MD) 시뮬레이션을 수행하는 클래스
    """
    def __init__(self, calculator):
        self.calculator = calculator

    def run_multi_temperature(self, atoms: Atoms, temperatures: list, steps: int,
                              time_step: float = 1.0, save_interval: int = 10):
        """
        여러 온도 조건에서 MD 시뮬레이션 병렬 실행

        :param atoms: 시뮬레이션할 원자 구조
        :param temperatures: 온도 리스트 (예: [300, 500, 1000])
        :param steps: 각 온도당 스텝 수
        :return: [(temperature, final_atoms, traj_file), ...] 리스트
        """
        print(f"🔥 다중 온도 MD 시작: {temperatures} K")
        results = []

        for temp in temperatures:
            print(f"\n   ⚙️  {temp}K 조건으로 MD 실행 중...")
            # 각 온도마다 독립적인 구조 복사본 사용
            atoms_copy = atoms.copy()
            final_atoms, traj_file = self.run(
                atoms_copy,
                temperature=temp,
                steps=steps,
                time_step=time_step,
                save_interval=save_interval
            )
            results.append((temp, final_atoms, traj_file))

        print(f"\n✅ 다중 온도 MD 완료: {len(temperatures)}개 조건")
        return results

    def run(self, atoms: Atoms, temperature: float, steps: int, time_step: float = 1.0, save_interval: int = 10):
       

        """
        MD 시뮬레이션 실행 (NVT 앙상블: 입자수, 부피, 온도 고정)

        :param atoms: 시뮬레이션할 원자 구조
        :param temperature: 목표 온도 (Kelvin, 예: 300)
        :param steps: 총 시뮬레이션 스텝 수 (예: 1000)
        :param time_step: 시간 간격 (femtosecond 단위, 보통 1.0 ~ 2.0 사용)
        :param save_interval: 몇 스텝마다 저장할지 (너무 자주 저장하면 파일이 커짐)
        """
        # 1. 계산기 장착
        atoms.calc = self.calculator

        # 2. 초기 속도 부여 (Maxwell-Boltzmann 분포)
        # 지정된 온도에 맞는 랜덤한 속도를 원자들에게 부여합니다.
        MaxwellBoltzmannDistribution(atoms, temperature_K=temperature)
        Stationary(atoms) # 전체 시스템이 둥둥 떠다니지 않게 무게중심 고정

        print(f"🔥 초기 온도 설정 완료: {temperature} K")

        # 3. MD 엔진 설정 (Langevin Dynamics 사용)
        # Langevin은 외부 열원(Heat Bath)과 상호작용하여 온도를 일정하게 유지해줍니다.
        dyn = NPT(
            atoms,
            timestep=time_step * units.fs,
            temperature_K=temperature,
            externalstress=0.0,           # 외부 압력 0 (대기압 상태)
            ttime=25.0 * units.fs,        # 온도 조절 시상수 (작을수록 강하게 조절)
            pfactor=75.0 * units.GPa,     # 압력 조절 계수 (부피 변화 허용)
            trajectory=None
        )

        # 4. 결과 저장 설정
        os.makedirs("data/results", exist_ok=True)
        # 화학식을 파일명에 포함하여 각 조합마다 고유한 파일 생성
        from pymatgen.core import Composition
        formula_full = atoms.get_chemical_formula()
        formula_reduced = Composition(formula_full).reduced_formula
        # 파일명에서 사용할 수 없는 문자 제거
        formula_safe = formula_reduced.replace('/', '_')
        file_name = f"data/results/md_{formula_safe}_{int(temperature)}K.traj"
        traj = Trajectory(file_name, 'w', atoms)
        
        # 저장 함수 정의 (Langevin 엔진이 실행될 때마다 호출됨)
        def write_frame():
            traj.write()
            
        # 몇 스텝마다 저장할지 설정
        dyn.attach(write_frame, interval=save_interval)
        
        # 로그 출력 함수
        def print_status():
            epot = atoms.get_potential_energy()
            ekin = atoms.get_kinetic_energy()
            current_temp = ekin / (1.5 * len(atoms) * units.kB)
            print(f"Step {dyn.nsteps}/{steps} | Temp: {current_temp:.1f} K | Epot: {epot:.3f} eV")
            
        dyn.attach(print_status, interval=steps // 10) # 10번만 출력

        print(f"🚀 MD 시뮬레이션 시작 (총 {steps} steps)...")
        dyn.run(steps)
        print(f"✅ MD 완료! 결과 저장됨: {file_name}")

        traj.close()
        return atoms, file_name  # trajectory 파일 경로도 반환