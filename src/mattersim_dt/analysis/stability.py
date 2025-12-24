from pymatgen.core import Composition
from pymatgen.entries.computed_entries import ComputedEntry
from pymatgen.analysis.phase_diagram import PhaseDiagram
from ase import Atoms
import numpy as np

class StabilityAnalyzer:
    """
    Pymatgen을 사용하여 전문적인 열역학적 안정성(Convex Hull)을 분석하는 클래스
    """
    def __init__(self, stability_threshold=None):
        """
        :param stability_threshold: 안정성 판정 임계값 (eV/atom)
                                   None이면 config.py의 STABILITY_THRESHOLD 사용
        """
        self.entries = [] # 계산된 결과들을 모아두는 리스트

        # config.py에서 임계값 가져오기
        if stability_threshold is None:
            from mattersim_dt.core import SimConfig
            self.threshold = SimConfig.STABILITY_THRESHOLD
        else:
            self.threshold = stability_threshold

    def add_result(self, atoms: Atoms, total_energy: float):
        """
        MatterSim 계산 결과를 분석기에 등록하는 함수
        :param atoms: ASE Atoms 객체
        :param total_energy: 계산된 총 에너지 (eV)
        """
        # 1. ASE Atoms -> Pymatgen Composition 변환
        formula = atoms.get_chemical_formula()
        composition = Composition(formula)
        
        # 2. ComputedEntry 생성 (Pymatgen이 이해하는 데이터 포맷)
        # (에너지가 자동으로 원자당 에너지가 아니라 '구조 전체 에너지'로 입력되어야 함에 주의)
        entry = ComputedEntry(composition, total_energy)
        self.entries.append(entry)
        
        print(f"📥 데이터 등록 완료: {formula} (Energy: {total_energy:.3f} eV)")

    def analyze(self):
        """
        등록된 모든 데이터를 바탕으로 Phase Diagram을 그리고 안정성을 판정
        """
        if not self.entries:
            print("❌ 분석할 데이터가 없습니다.")
            return

        print("\n🔍 Pymatgen Phase Diagram 분석 시작...")
        
        # 1. 상태도(Phase Diagram) 생성 (이 한 줄이 핵심!)
        # 이 함수가 내부적으로 Convex Hull을 그리고 안정성을 계산합니다.
        pd = PhaseDiagram(self.entries)
        
        results = []
        for entry in self.entries:
            # 2. 분해 에너지(Decomposition Energy) 계산
            # 이 값이 0이면 안정, 0보다 크면 불안정
            e_above_hull = pd.get_e_above_hull(entry)

            # config.py의 STABILITY_THRESHOLD 사용
            is_stable = (e_above_hull <= self.threshold)

            results.append({
                "formula": entry.composition.reduced_formula,
                "energy_above_hull": e_above_hull,
                "is_stable": is_stable
            })

        return results