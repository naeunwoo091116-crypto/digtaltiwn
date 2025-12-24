from ase import Atoms
from ase.optimize import BFGS
from ase.io import write
import os

class StructureRelaxer:
    """
    주어진 원자 구조의 위치를 미세 조정하여 에너지를 최소화(안정화)하는 클래스
    """
    def __init__(self, calculator):
        self.calculator = calculator

    def run(self, atoms: Atoms, fmax: float = 0.05, steps: int = 100, save_traj: bool = False):
        """
        구조 최적화 실행

        :param atoms: Builder에서 만든 Atoms 객체
        :param fmax: 수렴 기준 (힘이 0.05 eV/A 이하가 될 때까지)
        :param steps: 최대 반복 횟수
        :param save_traj: 최적화 과정을 파일로 저장할지 여부
        :return: 최적화된 Atoms 객체, 최종 에너지
        """
        # 1. 계산기 장착 (MatterSim 연결)
        atoms.calc = self.calculator

        # 2. 최적화 로그 파일 설정
        logfile = None
        trajfile = None

        if save_traj:
            os.makedirs("data/results", exist_ok=True)
            # 화학식을 파일명에 포함하여 각 조합마다 고유한 파일 생성
            from pymatgen.core import Composition
            formula_full = atoms.get_chemical_formula()
            formula_reduced = Composition(formula_full).reduced_formula
            # 파일명에서 사용할 수 없는 문자 제거
            formula_safe = formula_reduced.replace('/', '_')
            trajfile = f"data/results/relax_{formula_safe}.traj" # ASE 전용 트라젝토리 파일
            logfile = f"data/results/relax_{formula_safe}.log"

        # 3. 최적화 알고리즘 선택 (BFGS가 가장 무난하고 빠름)
        optimizer = BFGS(atoms, logfile=logfile, trajectory=trajfile)
        
        print(f"🚀 구조 최적화 시작 (Initial Energy: {atoms.get_potential_energy():.3f} eV)")
        
        # 4. 실행
        optimizer.run(fmax=fmax, steps=steps)
        
        final_energy = atoms.get_potential_energy()
        print(f"✅ 최적화 완료 (Final Energy: {final_energy:.3f} eV)")
        
        return atoms, final_energy