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