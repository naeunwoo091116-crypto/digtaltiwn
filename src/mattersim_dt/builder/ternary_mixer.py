import numpy as np
import random
from ase import Atoms
from ase.build import bulk, make_supercell

class TernaryAlloyMixer:
    """
    3원소 합금 구조를 생성하는 클래스
    - 균등 분할 방식의 조성 생성 (1:1:1, 2:1:1 등)
    - 결정구조 우선순위로 base 원소 선택 (FCC > BCC > HCP)
    """

    # 주요 금속 원소의 격자 상수 및 결정 구조 데이터베이스 (Angstrom 단위)
    # RandomAlloyMixer와 동일한 데이터베이스 사용
    LATTICE_DATA = {
        # 경금속
        'Li': ('bcc', 3.51),
        'Be': ('hcp', 2.29),
        'Mg': ('hcp', 3.21),
        'Al': ('fcc', 4.05),
        # 4주기 전이금속
        'Ti': ('hcp', 2.95),
        'V': ('bcc', 3.03),
        'Cr': ('bcc', 2.88),
        'Mn': ('bcc', 8.91),
        'Fe': ('bcc', 2.87),
        'Co': ('hcp', 2.51),
        'Ni': ('fcc', 3.52),
        'Cu': ('fcc', 3.61),
        'Zn': ('hcp', 2.66),
        # 5주기 전이금속
        'Zr': ('hcp', 3.23),
        'Nb': ('bcc', 3.30),
        'Mo': ('bcc', 3.15),
        'Tc': ('hcp', 2.74),
        'Ru': ('hcp', 2.71),
        'Rh': ('fcc', 3.80),
        'Pd': ('fcc', 3.89),
        'Ag': ('fcc', 4.09),
        'Cd': ('hcp', 2.98),
        # 6주기 전이금속
        'Hf': ('hcp', 3.20),
        'Ta': ('bcc', 3.31),
        'W': ('bcc', 3.16),
        'Re': ('hcp', 2.76),
        'Os': ('hcp', 2.74),
        'Ir': ('fcc', 3.84),
        'Pt': ('fcc', 3.92),
        'Au': ('fcc', 4.08),
    }

    # 결정구조 우선순위 (FCC > BCC > HCP)
    CRYSTAL_PRIORITY = {
        'fcc': 3,
        'bcc': 2,
        'hcp': 1
    }

    def __init__(self, element_A: str, element_B: str, element_C: str):
        """
        3원소 합금 mixer 초기화

        Args:
            element_A: 첫 번째 원소 (예: 'Fe')
            element_B: 두 번째 원소 (예: 'Cr')
            element_C: 세 번째 원소 (예: 'Ni')
        """
        self.elements = [element_A, element_B, element_C]

        # Base 원소 선택 (결정구조 우선순위 기반)
        self.base_element = self._select_base_element()

        # Base 원소로 기본 구조 생성
        if self.base_element in self.LATTICE_DATA:
            structure, a = self.LATTICE_DATA[self.base_element]
        else:
            structure, a = 'fcc', 4.0  # 기본값

        try:
            self.base_atoms = bulk(self.base_element, structure, a=a, cubic=True)
        except Exception as e:
            print(f"Warning: {self.base_element} 구조 생성 실패, fcc로 대체")
            self.base_atoms = bulk(self.base_element, 'fcc', a=4.0, cubic=True)

    def _select_base_element(self) -> str:
        """
        결정구조 우선순위로 base 원소 선택
        FCC > BCC > HCP 순서
        동점이면 알파벳순

        Returns:
            선택된 base 원소
        """
        priorities = []

        for elem in self.elements:
            if elem in self.LATTICE_DATA:
                crystal_structure = self.LATTICE_DATA[elem][0]
                priority = self.CRYSTAL_PRIORITY.get(crystal_structure, 0)
            else:
                priority = 0

            # (우선순위, 역알파벳순) - max()가 우선순위 높은 것 선택, 동점이면 알파벳순
            priorities.append((priority, elem))

        # 가장 높은 우선순위 선택
        selected = max(priorities, key=lambda x: (x[0], x[1]))

        return selected[1]

    @staticmethod
    def generate_composition_ratios(total_atoms_range=None) -> list:
        """
        균등 분할 방식으로 3원소 조성 생성

        Args:
            total_atoms_range: 정수 합의 범위 리스트 (예: [3,4,5,6])
                              None이면 [3,4,5,6] 사용

        Returns:
            [(a, b, c), ...] 형태의 정수 비율 튜플 리스트
            예: [(1,1,1), (2,1,1), (1,2,1), (1,1,2), ...]
        """
        if total_atoms_range is None:
            total_atoms_range = [3, 4, 5, 6]

        compositions = []

        for total in total_atoms_range:
            # 3개 원소에 total을 분배하는 모든 조합 생성
            for a in range(1, total - 1):
                for b in range(1, total - a):
                    c = total - a - b
                    if c >= 1:
                        compositions.append((a, b, c))

        return compositions

    def generate_ternary_structure(
        self,
        ratio_tuple: tuple,
        supercell_size: int = 3
    ) -> Atoms:
        """
        3원소 합금 구조 생성

        Args:
            ratio_tuple: 정수 비율 튜플 (a, b, c)
                        예: (2, 1, 1) → 2:1:1 비율
            supercell_size: 슈퍼셀 크기 (기본값: 3)

        Returns:
            ASE Atoms 객체 (3원소가 혼합된 합금 구조)
        """
        # 1. Base 원소로 슈퍼셀 생성
        multiplier = np.array([
            [supercell_size, 0, 0],
            [0, supercell_size, 0],
            [0, 0, supercell_size]
        ])
        atoms = make_supercell(self.base_atoms, multiplier)

        # 2. 비율 계산
        total_parts = sum(ratio_tuple)
        ratios = [r / total_parts for r in ratio_tuple]

        # 3. 원소별 원자 개수 계산
        total_atoms = len(atoms)
        counts = [int(total_atoms * ratio) for ratio in ratios]

        # 반올림 오차 보정 (남은 원자를 첫 번째 원소에 추가)
        remaining = total_atoms - sum(counts)
        if remaining > 0:
            counts[0] += remaining

        # 4. 무작위 인덱스 생성 및 섞기
        indices = list(range(total_atoms))
        random.shuffle(indices)

        # 5. 원소 치환
        symbols = atoms.get_chemical_symbols()
        offset = 0

        for elem, count in zip(self.elements, counts):
            for idx in indices[offset:offset + count]:
                symbols[idx] = elem
            offset += count

        atoms.set_chemical_symbols(symbols)

        # 6. 메타데이터 저장
        atoms.info['composition'] = dict(zip(self.elements, ratios))
        atoms.info['ratio_tuple'] = ratio_tuple
        atoms.info['base_element'] = self.base_element

        return atoms

    def generate_pure_element_structure(
        self,
        element: str,
        supercell_size: int = 3
    ) -> Atoms:
        """
        순수 원소 구조 생성 (3원소 파이프라인에서 기준값으로 사용)

        Args:
            element: 원소 기호
            supercell_size: 슈퍼셀 크기

        Returns:
            ASE Atoms 객체
        """
        if element in self.LATTICE_DATA:
            structure, a = self.LATTICE_DATA[element]
        else:
            structure, a = 'fcc', 4.0

        try:
            base_atoms = bulk(element, structure, a=a, cubic=True)
        except Exception:
            base_atoms = bulk(element, 'fcc', a=4.0, cubic=True)

        multiplier = np.array([
            [supercell_size, 0, 0],
            [0, supercell_size, 0],
            [0, 0, supercell_size]
        ])
        atoms = make_supercell(base_atoms, multiplier)

        atoms.info['composition'] = {element: 1.0}
        atoms.info['ratio_tuple'] = None
        atoms.info['is_pure'] = True

        return atoms


# 테스트용 코드
if __name__ == "__main__":
    print("=== 3원소 합금 구조 생성 테스트 ===\n")

    # 1. 조성 생성 테스트
    print("[1] 조성 생성 테스트")
    compositions = TernaryAlloyMixer.generate_composition_ratios([3, 4])
    print(f"총 조성 개수: {len(compositions)}")
    print(f"조성 리스트: {compositions}\n")

    # 2. Base 원소 선택 테스트
    print("[2] Base 원소 선택 테스트")
    mixer = TernaryAlloyMixer("Fe", "Cr", "Ni")
    print(f"원소: Fe(BCC), Cr(BCC), Ni(FCC)")
    print(f"선택된 Base 원소: {mixer.base_element} (FCC 우선)\n")

    # 3. 구조 생성 테스트
    print("[3] 구조 생성 테스트")
    atoms = mixer.generate_ternary_structure((2, 1, 1), supercell_size=3)
    print(f"총 원자 개수: {len(atoms)}")
    print(f"화학식: {atoms.get_chemical_formula()}")
    print(f"조성 비율: {atoms.info['composition']}")
    print(f"비율 튜플: {atoms.info['ratio_tuple']}")
    print(f"Base 원소: {atoms.info['base_element']}\n")

    # 4. 순수 원소 구조 생성 테스트
    print("[4] 순수 원소 구조 생성 테스트")
    pure_fe = mixer.generate_pure_element_structure("Fe", supercell_size=3)
    print(f"Fe 순수 구조: {len(pure_fe)}개 원자")
    print(f"화학식: {pure_fe.get_chemical_formula()}")

    print("\n✅ 모든 테스트 완료")
