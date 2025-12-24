import numpy as np
import random
from ase import Atoms
from ase.build import bulk, make_supercell

class RandomAlloyMixer:
    """
    주어진 기본 원소 구조를 바탕으로, 비율에 맞춰 다른 원소를 무작위 치환(Substitution)하여
    합금(Alloy) 구조를 생성하는 클래스
    """

    # 주요 금속 원소의 격자 상수 및 결정 구조 데이터베이스 (Angstrom 단위)
    # 출처: Materials Project, ICSD
    LATTICE_DATA = {
        # 경금속
        'Li': ('bcc', 3.51),
        'Be': ('hcp', 2.29),  # a축
        'Mg': ('hcp', 3.21),
        'Al': ('fcc', 4.05),
        # 4주기 전이금속
        'Ti': ('hcp', 2.95),
        'V': ('bcc', 3.03),
        'Cr': ('bcc', 2.88),
        'Mn': ('bcc', 8.91),  # 복잡한 구조, bcc 근사
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

    def __init__(self, base_element: str, crystal_structure: str = None, lattice_constant: float = None):
        """
        :param base_element: 주 원소 (예: 'Cu')
        :param crystal_structure: 결정 구조 ('fcc', 'bcc', 'hcp' 등) - None이면 자동 선택
        :param lattice_constant: 격자 상수 (None이면 데이터베이스에서 자동 선택)
        """
        # 1. 격자 상수 및 결정 구조 결정
        if base_element in self.LATTICE_DATA:
            default_structure, default_a = self.LATTICE_DATA[base_element]
            structure = crystal_structure or default_structure
            a = lattice_constant or default_a
        else:
            # 데이터베이스에 없으면 기본값 사용
            structure = crystal_structure or 'fcc'
            a = lattice_constant

        # 2. 기본 뼈대(Primitive Cell) 생성
        try:
            if a is not None:
                self.base_atoms = bulk(base_element, structure, a=a)
            else:
                self.base_atoms = bulk(base_element, structure)
        except Exception as e:
            # ASE가 실패하면 fcc 구조로 기본 격자 상수와 함께 재시도
            print(f"⚠️  {base_element}의 구조 생성 실패, fcc 구조로 대체 (a=4.0)")
            self.base_atoms = bulk(base_element, 'fcc', a=4.0)
            
    def generate_structure(self, dopant_element: str, ratio: float, supercell_size: int = 4) -> Atoms:
        """
        실제 섞는 작업을 수행하는 함수
        
        :param dopant_element: 섞을 원소 (예: 'Ni')
        :param ratio: 섞을 비율 (0.0 ~ 1.0, 예: 0.3은 30%)
        :param supercell_size: 구조를 몇 배로 확장할지 (클수록 다양한 배치 가능)
        :return: 생성된 ASE Atoms 객체
        """
        # 2. 슈퍼셀 확장 (공간 늘리기)
        # 예: size=4 이면 4x4x4 = 64배로 원자 개수가 늘어남
        multiplier = np.array([[supercell_size, 0, 0], [0, supercell_size, 0], [0, 0, supercell_size]])
        atoms = make_supercell(self.base_atoms, multiplier)
        
        # 3. 바꿔치기할 개수 계산
        total_atoms = len(atoms)
        num_substitute = int(total_atoms * ratio)
        
        if num_substitute == 0 and ratio > 0:
            print(f"Warning: 슈퍼셀이 너무 작아서 {dopant_element}를 하나도 넣을 수 없습니다. size를 키우세요.")
            return atoms

        # 4. 무작위 섞기 (Random Shuffle)
        indices = list(range(total_atoms))
        random.shuffle(indices)
        
        # 5. 원소 기호 변경
        target_indices = indices[:num_substitute]
        chemical_symbols = atoms.get_chemical_symbols()
        
        for idx in target_indices:
            chemical_symbols[idx] = dopant_element
            
        atoms.set_chemical_symbols(chemical_symbols)
        
        # 나중에 분석하기 좋게 info에 메타데이터 저장
        atoms.info['composition'] = {
            self.base_atoms.get_chemical_symbols()[0]: 1.0 - ratio,
            dopant_element: ratio
        }
        
        return atoms

# 테스트용 코드 (이 파일만 실행했을 때 작동)
if __name__ == "__main__":
    # 구리(Cu) 뼈대에 니켈(Ni)을 30% 섞어보기
    mixer = RandomAlloyMixer(base_element='Cu', crystal_structure='fcc')
    
    # 3x3x3 크기로 확장해서 생성
    alloy = mixer.generate_structure(dopant_element='Ni', ratio=0.3, supercell_size=3)
    
    print(f"총 원자 개수: {len(alloy)}")
    print(f"화학식: {alloy.get_chemical_formula()}")
    print(f"설정된 정보: {alloy.info}")
    
    # 시각화 (GUI 창이 뜸) - 필요하면 주석 해제
    # from ase.visualize import view
    # view(alloy)