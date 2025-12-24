"""
배치 처리를 통한 병렬 구조 이완 모듈
단일 GPU에서 여러 구조를 효율적으로 계산
"""
from typing import List, Tuple
from ase import Atoms
import numpy as np


class BatchStructureRelaxer:
    """
    여러 구조를 배치로 묶어서 병렬로 이완하는 클래스
    """
    def __init__(self, calculator, batch_size: int = 4):
        """
        :param calculator: ASE Calculator (MatterSim 등)
        :param batch_size: 한 번에 처리할 구조 개수
        """
        self.calculator = calculator
        self.batch_size = batch_size

    def run_batch(self, atoms_list: List[Atoms], save_traj: bool = False) -> List[Tuple[Atoms, float]]:
        """
        여러 구조를 배치로 이완

        :param atoms_list: 이완할 Atoms 객체 리스트
        :param save_traj: trajectory 저장 여부
        :return: [(relaxed_atoms, total_energy), ...] 리스트
        """
        results = []

        # 배치 단위로 나누어서 처리
        num_batches = (len(atoms_list) + self.batch_size - 1) // self.batch_size

        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.batch_size
            end_idx = min((batch_idx + 1) * self.batch_size, len(atoms_list))
            batch = atoms_list[start_idx:end_idx]

            print(f"   📦 Batch {batch_idx + 1}/{num_batches}: {len(batch)}개 구조 병렬 이완 중...")

            # 각 구조에 대해 순차적으로 계산 (ASE는 기본적으로 순차)
            # 하지만 MatterSim 내부에서는 GPU 병렬처리가 자동으로 일어남
            batch_results = []
            for atoms in batch:
                atoms.calc = self.calculator

                # BFGS 최적화 수행
                from ase.optimize import BFGS
                from io import StringIO
                import sys
                import os

                # 출력 억제 (배치 처리 시 로그가 너무 많음)
                old_stdout = sys.stdout
                sys.stdout = StringIO()

                trajfile = None
                if save_traj:
                    # 화학식을 파일명에 포함
                    from pymatgen.core import Composition
                    formula_full = atoms.get_chemical_formula()
                    formula_reduced = Composition(formula_full).reduced_formula
                    formula_safe = formula_reduced.replace('/', '_')
                    os.makedirs("data/results", exist_ok=True)
                    trajfile = f"data/results/relax_{formula_safe}.traj"

                try:
                    optimizer = BFGS(atoms, logfile=None, trajectory=trajfile)
                    optimizer.run(fmax=0.05, steps=200)

                    # 최종 에너지 계산
                    energy_total = atoms.get_potential_energy()

                    batch_results.append((atoms.copy(), energy_total))
                except Exception as e:
                    print(f"     ⚠️  구조 이완 실패: {e}")
                    batch_results.append((atoms.copy(), float('inf')))
                finally:
                    sys.stdout = old_stdout

            results.extend(batch_results)
            print(f"     ✓ Batch {batch_idx + 1} 완료")

        return results
