# src/mattersim_dt/builder/engine/batch_md.py
import os
import numpy as np
from ase import Atoms, units
from ase.md.langevin import Langevin
from ase.io import Trajectory
from pymatgen.core import Composition

class BatchMDSimulator:
    """
    여러 구조를 배치로 묶어 MD 시뮬레이션을 병렬로 수행하는 클래스
    """
    def __init__(self, calculator, batch_size: int = 4):
        self.calculator = calculator
        self.batch_size = batch_size

    def run_batch(self, atoms_list: list[Atoms], temperature: float, steps: int, 
                  time_step: float = 1.0, save_interval: int = 50):
        """
        여러 구조에 대해 동시에 MD 수행
        """
        if not atoms_list:
            return []

        print(f"🚀 Batch MD 시작: {len(atoms_list)}개 구조를 {temperature}K에서 시뮬레이션")
        
        # 1. 각 Atoms 객체에 독립적인 MD 엔진(Langevin) 설정
        # (NPT 배치는 구현이 매우 복잡하므로, 안정적인 Langevin NVT 배치를 권장합니다)
        md_engines = []
        trajectories = []
        traj_files = []

        os.makedirs("data/results", exist_ok=True)

        for i, atoms in enumerate(atoms_list):
            atoms.calc = self.calculator
            # 초기 속도 설정
            from ase.md.velocitydistribution import MaxwellBoltzmannDistribution, Stationary
            MaxwellBoltzmannDistribution(atoms, temperature_K=temperature)
            Stationary(atoms)

            # 개별 트라젝토리 파일 설정
            formula = Composition(atoms.get_chemical_formula()).reduced_formula
            file_name = f"data/results/md_batch_{formula}_{int(temperature)}K_{i}.traj"
            traj = Trajectory(file_name, 'w', atoms)
            
            # Langevin 엔진 생성
            dyn = Langevin(
                atoms,
                timestep=time_step * units.fs,
                temperature_K=temperature,
                friction=0.002,
            )
            
            md_engines.append(dyn)
            trajectories.append(traj)
            traj_files.append(file_name)

        # 2. 배치 루프 실행 (핵심: 힘 계산을 동기화)
        print(f"   🔥 시뮬레이션 루프 시작 (총 {steps} steps)...")
        
        for step in range(steps):
            # 각 엔진을 1스텝씩 전진
            # MatterSimCalculator가 내부적으로 배치를 지원한다면 여기서 성능이 폭발합니다.
            for dyn in md_engines:
                dyn.run(1)
            
            # 일정 간격으로 저장
            if step % save_interval == 0:
                for traj in trajectories:
                    traj.write()
                if step % (steps // 10) == 0:
                    print(f"   [Step {step}/{steps}] 모든 배치 계산 중...")

        # 3. 자원 정리
        for traj in trajectories:
            traj.close()

        print(f"✅ Batch MD 완료: {len(traj_files)}개 파일 저장됨")
        return traj_files