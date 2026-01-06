from mp_api.client import MPRester
from pymatgen.core.periodic_table import Element
from itertools import combinations
import os

class MaterialMiner:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("MP_API_KEY")
        if not self.api_key:
            raise ValueError("❌ MP_API_KEY가 필요합니다.")

    def _is_metal_element(self, symbol: str) -> bool:
        try:
            el = Element(symbol)
            return el.is_metal or el.is_transition_metal or el.is_alkali or el.is_alkaline
        except:
            return False

    def search_metal_alloys(self, candidates: list) -> list:
        # 1. 비금속 거르기
        valid_metals = [el for el in candidates if self._is_metal_element(el)]
        ignored = set(candidates) - set(valid_metals)
        if ignored:
            print(f"⚠️ [System] 비금속 제외됨: {ignored}")
        
        if len(valid_metals) < 2:
            print("❌ 금속 원소가 최소 2개 이상 필요합니다.")
            return []

        results = []
        seen_ids = set() # 중복 방지용

        print(f"⛏️ [Miner] '{valid_metals}' 내부의 모든 합금 조합을 탐색합니다...")

        # 2. 조합 생성 (2개짜리 쌍 ~ 전체 개수까지)
        # 예: [Cu, Ni, Fe] -> (Cu, Ni), (Cu, Fe), (Ni, Fe), (Cu, Ni, Fe) 순서로 검색
        search_queue = []
        for r in range(2, len(valid_metals) + 1):
            search_queue.extend(list(combinations(valid_metals, r)))

        with MPRester(self.api_key) as mpr:
            for combo in search_queue:
                elements = list(combo)
                print(f"   🔎 검색 중: {elements} 조합...", end=" ")
                
                try:
                    # 안정성 조건 완화: is_stable=False로 하고, 나중에 에너지로 직접 필터링
                    docs = mpr.materials.summary.search(
                        elements=elements,
                        is_metal=True,
                        fields=["material_id", "formula_pretty", "formation_energy_per_atom", 
                                "structure", "symmetry", "energy_above_hull"]
                    )
                except Exception as e:
                    print(f"(API 에러: {e}) -> 건너뜀")
                    continue

                # 3. 데이터 필터링 (순수 해당 원소들로만 구성된 것 + 준안정 상태 포함)
                count = 0
                for doc in docs:
                    # 이미 찾은 건 패스
                    if doc.material_id in seen_ids:
                        continue
                    
                    # 다른 불순물이 섞였는지 확인
                    comp_elements = set([str(e) for e in doc.structure.composition.elements])
                    if not comp_elements.issubset(set(valid_metals)):
                        continue
                        
                    # [중요] 에너지 필터링 (완벽히 안정하진 않아도, 0.05 eV 이내면 합격)
                    if doc.energy_above_hull > 0.05:
                        continue

                    # 합격!
                    data = {
                        "id": doc.material_id,
                        "formula": doc.formula_pretty,
                        "energy": doc.formation_energy_per_atom,
                        "stability": doc.energy_above_hull,
                        "structure": doc.structure
                    }
                    results.append(data)
                    seen_ids.add(doc.material_id)
                    count += 1
                
                print(f"-> {count}개 발견")

        print(f"✅ 최종 확보된 합금 데이터: 총 {len(results)}개")
        return results


class TernaryMaterialMiner:
    """
    Materials Project에서 3원소 합금을 마이닝하고 실제 조성 비율을 추출하는 클래스
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("MP_API_KEY")
        if not self.api_key:
            raise ValueError("❌ MP_API_KEY가 필요합니다.")

    def _is_metal_element(self, symbol: str) -> bool:
        """금속 원소 여부 확인"""
        try:
            el = Element(symbol)
            return el.is_metal or el.is_transition_metal or el.is_alkali or el.is_alkaline
        except:
            return False

    def search_ternary_alloys(self, element_A: str, element_B: str, element_C: str) -> list:
        """
        특정 3원소 조합에 대해 Materials Project에서 실제 연구된 합금을 검색

        Args:
            element_A, element_B, element_C: 원소 기호 (예: "Fe", "Cr", "Ni")

        Returns:
            list: 발견된 3원소 합금 데이터
                  각 항목은 {'formula': str, 'composition_ratio': tuple, 'energy': float, ...}
        """
        # 1. 금속 원소 검증
        elements = [element_A, element_B, element_C]
        valid_metals = [el for el in elements if self._is_metal_element(el)]

        if len(valid_metals) < 3:
            non_metals = set(elements) - set(valid_metals)
            print(f"❌ 비금속 원소 포함: {non_metals}")
            return []

        results = []
        seen_ids = set()

        print(f"⛏️ [TernaryMiner] {element_A}-{element_B}-{element_C} 3원소 합금 탐색 중...")

        with MPRester(self.api_key) as mpr:
            try:
                # 3원소 조합 검색
                docs = mpr.materials.summary.search(
                    elements=elements,
                    is_metal=True,
                    fields=["material_id", "formula_pretty", "formula_anonymous",
                            "formation_energy_per_atom", "structure", "symmetry",
                            "energy_above_hull", "composition"]
                )
            except Exception as e:
                print(f"❌ API 에러: {e}")
                return []

            # 2. 정확히 3원소로만 구성된 합금 필터링
            print(f"   🔎 검색된 총 데이터: {len(docs)}개")

            for doc in docs:
                # 이미 찾은 건 패스
                if doc.material_id in seen_ids:
                    continue

                # 다른 불순물이 섞였는지 확인
                comp_elements = set([str(e) for e in doc.structure.composition.elements])

                # 정확히 3원소만 포함된 것만 선택
                if comp_elements != set(elements):
                    continue

                # 에너지 필터링 (준안정 상태 포함: 0.1 eV 이내)
                if doc.energy_above_hull > 0.1:
                    continue

                # 조성 비율 추출 (정수 비율로 변환)
                composition = doc.structure.composition
                ratio_tuple = self._extract_composition_ratio(
                    composition, element_A, element_B, element_C
                )

                # 합격!
                data = {
                    "id": doc.material_id,
                    "formula": doc.formula_pretty,
                    "composition_ratio": ratio_tuple,  # (a, b, c) 형태
                    "energy": doc.formation_energy_per_atom,
                    "stability": doc.energy_above_hull,
                    "structure": doc.structure,
                    "crystal_system": doc.symmetry.crystal_system if hasattr(doc, 'symmetry') else "Unknown"
                }
                results.append(data)
                seen_ids.add(doc.material_id)

        print(f"   ✅ 발견된 3원소 합금: {len(results)}개")

        # 조성 비율별로 정렬
        results.sort(key=lambda x: x['composition_ratio'])

        return results

    def _extract_composition_ratio(self, composition, element_A: str, element_B: str, element_C: str) -> tuple:
        """
        Pymatgen Composition에서 정수 비율 추출

        Args:
            composition: Pymatgen Composition 객체
            element_A, element_B, element_C: 원소 기호

        Returns:
            tuple: (a, b, c) 정수 비율
        """
        from fractions import Fraction

        # 각 원소의 비율 추출
        amt_A = composition.get_atomic_fraction(element_A)
        amt_B = composition.get_atomic_fraction(element_B)
        amt_C = composition.get_atomic_fraction(element_C)

        # 분수로 변환하여 최소 공배수 찾기
        # 0.333... → 1/3, 0.5 → 1/2 등
        frac_A = Fraction(amt_A).limit_denominator(100)
        frac_B = Fraction(amt_B).limit_denominator(100)
        frac_C = Fraction(amt_C).limit_denominator(100)

        # 공통 분모로 통일
        from math import gcd
        denominators = [frac_A.denominator, frac_B.denominator, frac_C.denominator]

        # 최소공배수 계산
        def lcm(a, b):
            return abs(a * b) // gcd(a, b)

        common_denom = denominators[0]
        for d in denominators[1:]:
            common_denom = lcm(common_denom, d)

        # 정수 비율로 변환
        ratio_A = int(frac_A * common_denom)
        ratio_B = int(frac_B * common_denom)
        ratio_C = int(frac_C * common_denom)

        # 최대공약수로 나누어 최소 정수 비율로 만들기
        ratio_gcd = gcd(gcd(ratio_A, ratio_B), ratio_C)

        if ratio_gcd > 0:
            ratio_A //= ratio_gcd
            ratio_B //= ratio_gcd
            ratio_C //= ratio_gcd

        return (ratio_A, ratio_B, ratio_C)

    def print_summary(self, results: list):
        """
        마이닝 결과 요약 출력

        Args:
            results: search_ternary_alloys()의 반환값
        """
        if not results:
            print("검색된 3원소 합금이 없습니다.")
            return

        print("\n" + "="*70)
        print("📊 3원소 합금 마이닝 결과 요약")
        print("="*70)
        print(f"{'Material ID':<15} {'Formula':<15} {'Ratio (a:b:c)':<15} {'E_hull (eV)':<12}")
        print("-"*70)

        for item in results:
            ratio_str = f"{item['composition_ratio'][0]}:{item['composition_ratio'][1]}:{item['composition_ratio'][2]}"
            print(f"{item['id']:<15} {item['formula']:<15} {ratio_str:<15} {item['stability']:>10.4f}")

        print("="*70)
        print(f"총 {len(results)}개 발견")
        print()

    def get_unique_ratios(self, results: list) -> list:
        """
        마이닝 결과에서 중복 제거한 조성 비율 리스트 추출

        Args:
            results: search_ternary_alloys()의 반환값

        Returns:
            list: [(a, b, c), ...] 중복 제거된 비율 튜플 리스트
        """
        unique_ratios = set()

        for item in results:
            ratio = item['composition_ratio']
            unique_ratios.add(ratio)

        return sorted(list(unique_ratios))