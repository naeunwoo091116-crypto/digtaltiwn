import os
import pandas as pd
from mp_api.client import MPRester
from mattersim_dt.core import SimConfig

class ExperimentalDataMiner:
    """
    Materials Project API를 사용하여 실제 실험(Theoretical=False) 데이터를 
    추출하고 검증용 레퍼런스로 변환하는 클래스
    """
    def __init__(self, api_key: str = None, data_source: str = None, use_theoretical: bool = None):
        """
        Args:
            api_key: Materials Project API 키 (None이면 config에서 가져옴)
            data_source: 데이터 소스 ("materials_project", "literature", "auto")
            use_theoretical: theoretical 데이터 포함 여부 (None이면 config 설정 사용)
        """
        self.api_key = api_key or SimConfig.MP_API_KEY
        self.data_source = data_source or SimConfig.VALIDATION_DATA_SOURCE
        self.use_theoretical = use_theoretical if use_theoretical is not None else SimConfig.VALIDATION_USE_THEORETICAL

        # 환경 변수가 있으면 우선 사용
        env_key = os.environ.get("MP_API_KEY")
        if env_key:
            self.api_key = env_key

        # literature 모드가 아닌 경우에만 API 키 체크
        if self.data_source != "literature":
            if not self.api_key:
                raise ValueError("❌ 유효한 MP_API_KEY가 설정되지 않았습니다.")

            # API 키 유효성 간단 체크 (길이가 너무 짧으면 잘못된 키)
            if len(self.api_key) < 20:
                raise ValueError(f"❌ MP_API_KEY가 너무 짧습니다 (현재: {len(self.api_key)}자). 올바른 키를 config.py에 설정하세요.")

    def get_manual_cu_ni_references(self) -> pd.DataFrame:
        """
        문헌에서 가져온 Cu-Ni 합금의 실험 데이터 (수동 입력)
        출처: ASM Handbook, NIST, 과학 논문 등의 실험값

        ⚠️ 주의: 아래 값들은 대표적인 문헌값입니다.
        더 정확한 실험값이 있다면 이 데이터를 수정하세요!
        """
        print(f"📚 문헌 기반 Cu-Ni 실험 데이터 로드 중...")

        # 실험 데이터 (문헌값 - 필요시 수정 가능)
        experimental_data = [
            {
                "mp_id": "MANUAL-Cu",
                "formula": "Cu",
                "exp_lattice_a": 3.6147,  # 순수 Cu FCC 격자상수 (Å) - NIST
                "exp_lattice_b": 3.6147,
                "exp_lattice_c": 3.6147,
                "exp_density": 8.96,      # 밀도 (g/cm³) - ASM Handbook
                "exp_formation_energy": 0.0,
                "exp_e_above_hull": 0.0,
                "crystal_system": "Fm-3m"
            },
            {
                "mp_id": "MANUAL-Ni",
                "formula": "Ni",
                "exp_lattice_a": 3.5238,  # 순수 Ni FCC 격자상수 (Å) - NIST
                "exp_lattice_b": 3.5238,
                "exp_lattice_c": 3.5238,
                "exp_density": 8.90,      # 밀도 (g/cm³) - ASM Handbook
                "exp_formation_energy": 0.0,
                "exp_e_above_hull": 0.0,
                "crystal_system": "Fm-3m"
            },
            # Cu-Ni 합금 (1:1 조성) - Vegard's Law 기반 추정
            # 실제 실험값이 있다면 아래 값을 교체하세요!
            {
                "mp_id": "MANUAL-CuNi",
                "formula": "CuNi",
                "exp_lattice_a": 3.5692,  # Vegard's Law: (3.6147 + 3.5238) / 2
                "exp_lattice_b": 3.5692,
                "exp_lattice_c": 3.5692,
                "exp_density": 8.93,      # 평균 밀도 추정
                "exp_formation_energy": -0.015,  # 문헌값 (약간의 혼합 에너지)
                "exp_e_above_hull": 0.0,
                "crystal_system": "Fm-3m"
            }
        ]

        df = pd.DataFrame(experimental_data)
        print(f"✅ 총 {len(df)}개의 문헌 기반 레퍼런스 로드 완료")
        print(f"   📋 화학식: {', '.join(df['formula'].tolist())}")
        print(f"   💡 Tip: exp_reference.py에서 실험값을 수정할 수 있습니다.")
        return df

    def fetch_cu_ni_references(self) -> pd.DataFrame:
        """
        Cu-Ni 시스템의 실험 기반 데이터를 검색하여 데이터프레임으로 반환
        config.py의 VALIDATION_DATA_SOURCE 설정에 따라 동작 방식 결정
        """
        # literature 모드: Materials Project 건너뛰고 문헌 데이터만 사용
        if self.data_source == "literature":
            print(f"📚 문헌 데이터 모드: Materials Project 건너뜀")
            return self.get_manual_cu_ni_references()

        # materials_project 또는 auto 모드
        data_type = "실험" if not self.use_theoretical else "실험+이론"
        print(f"⛏️  Materials Project에서 Cu-Ni {data_type} 데이터 검색 중...")

        try:
            with MPRester(self.api_key) as mpr:
                # 1. API 쿼리 실행
                docs = mpr.materials.summary.search(
                    elements=["Cu", "Ni"],
                    is_metal=True,
                    theoretical=not self.use_theoretical,  # config 설정에 따라 결정
                    fields=[
                        "material_id", 
                        "formula_pretty", 
                        "structure", 
                        "density", 
                        "formation_energy_per_atom", 
                        "energy_above_hull"
                    ]
                )

                if not docs:
                    print("⚠️  검색된 실험 데이터가 없습니다.")
                    if self.data_source == "auto":
                        print("   🔄 문헌 기반 레퍼런스로 전환합니다...")
                        return self.get_manual_cu_ni_references()
                    return pd.DataFrame()

                # 2. 데이터 파싱 (Cu-Ni 순수 합금만 필터링)
                extracted_data = []
                for doc in docs:
                    struct = doc.structure

                    # 원소 체크: Cu와 Ni만 포함하는지 확인
                    comp = struct.composition
                    elements = set([str(el) for el in comp.elements])

                    # Cu-Ni 합금만 선택 (다른 원소 제외)
                    if elements <= {"Cu", "Ni"}:  # Cu, Ni 또는 둘 다만 포함
                        data = {
                            "mp_id": str(doc.material_id),
                            "formula": doc.formula_pretty,
                            "exp_lattice_a": round(struct.lattice.a, 4),
                            "exp_lattice_b": round(struct.lattice.b, 4),
                            "exp_lattice_c": round(struct.lattice.c, 4),
                            "exp_density": round(doc.density, 4),
                            "exp_formation_energy": round(doc.formation_energy_per_atom, 4),
                            "exp_e_above_hull": round(doc.energy_above_hull, 4),
                            "crystal_system": struct.get_space_group_info()[0]
                        }
                        extracted_data.append(data)

                if not extracted_data:
                    print("⚠️  Cu-Ni 순수 합금 데이터가 Materials Project에 없습니다.")
                    if self.data_source == "auto":
                        print("   🔄 문헌 기반 레퍼런스로 전환합니다...")
                        return self.get_manual_cu_ni_references()
                    return pd.DataFrame()

                df = pd.DataFrame(extracted_data)

                # 3. 중복 제거 (동일 화학식 중 가장 안정한 e_above_hull 기준 정렬)
                df = df.sort_values("exp_e_above_hull").drop_duplicates("formula")

                print(f"✅ 총 {len(df)}개의 Cu-Ni 순수 합금 레퍼런스 확보 (Materials Project)")
                print(f"   📋 화학식: {', '.join(df['formula'].tolist())}")
                return df

        except Exception as e:
            print(f"❌ MP API 호출 중 오류 발생: {e}")
            if self.data_source == "auto":
                print("   🔄 문헌 기반 레퍼런스로 전환합니다...")
                return self.get_manual_cu_ni_references()
            elif self.data_source == "materials_project":
                print("   ⚠️  materials_project 모드에서는 대체 데이터를 사용하지 않습니다.")
                return pd.DataFrame()
            else:
                return self.get_manual_cu_ni_references()

    def fetch_binary_alloy_references(self, element_a: str, element_b: str) -> pd.DataFrame:
        """
        임의의 2원계 합금(A-B) 실험 데이터를 가져옵니다.
        config.py의 VALIDATION_DATA_SOURCE 설정에 따라 동작 방식 결정

        Args:
            element_a: 첫 번째 원소 (예: "Cu")
            element_b: 두 번째 원소 (예: "Ni")

        Returns:
            실험 레퍼런스 DataFrame
        """
        # literature 모드: Materials Project 건너뛰고 문헌 데이터만 사용
        if self.data_source == "literature":
            print(f"📚 문헌 데이터 모드: Materials Project 건너뜀")
            return self._get_manual_binary_references(element_a, element_b)

        # materials_project 또는 auto 모드
        data_type = "실험" if not self.use_theoretical else "실험+이론"
        print(f"⛏️  Materials Project에서 {element_a}-{element_b} {data_type} 데이터 검색 중...")

        try:
            with MPRester(self.api_key) as mpr:
                # API 쿼리 실행
                docs = mpr.materials.summary.search(
                    elements=[element_a, element_b],
                    is_metal=True,
                    theoretical=not self.use_theoretical,  # config 설정에 따라 결정
                    fields=[
                        "material_id",
                        "formula_pretty",
                        "structure",
                        "density",
                        "formation_energy_per_atom",
                        "energy_above_hull"
                    ]
                )

                if not docs:
                    print(f"⚠️  {element_a}-{element_b} 실험 데이터가 없습니다.")
                    if self.data_source == "auto":
                        print("   🔄 문헌 기반 레퍼런스로 전환합니다...")
                        return self._get_manual_binary_references(element_a, element_b)
                    return pd.DataFrame()

                # 순수 합금만 필터링 (다른 원소 제외)
                extracted_data = []
                for doc in docs:
                    struct = doc.structure
                    comp = struct.composition
                    elements = set([str(el) for el in comp.elements])

                    if elements <= {element_a, element_b}:
                        data = {
                            "mp_id": str(doc.material_id),
                            "formula": doc.formula_pretty,
                            "exp_lattice_a": round(struct.lattice.a, 4),
                            "exp_lattice_b": round(struct.lattice.b, 4),
                            "exp_lattice_c": round(struct.lattice.c, 4),
                            "exp_density": round(doc.density, 4),
                            "exp_formation_energy": round(doc.formation_energy_per_atom, 4),
                            "exp_e_above_hull": round(doc.energy_above_hull, 4),
                            "crystal_system": struct.get_space_group_info()[0]
                        }
                        extracted_data.append(data)

                if not extracted_data:
                    print(f"⚠️  {element_a}-{element_b} 순수 합금 데이터가 Materials Project에 없습니다.")
                    if self.data_source == "auto":
                        print("   🔄 문헌 기반 레퍼런스로 전환합니다...")
                        return self._get_manual_binary_references(element_a, element_b)
                    return pd.DataFrame()

                df = pd.DataFrame(extracted_data)
                df = df.sort_values("exp_e_above_hull").drop_duplicates("formula")

                print(f"✅ 총 {len(df)}개의 {element_a}-{element_b} 순수 합금 레퍼런스 확보 (Materials Project)")
                print(f"   📋 화학식: {', '.join(df['formula'].tolist())}")
                return df

        except Exception as e:
            print(f"❌ MP API 호출 중 오류 발생: {e}")
            if self.data_source == "auto":
                print("   🔄 문헌 기반 레퍼런스로 전환합니다...")
                return self._get_manual_binary_references(element_a, element_b)
            elif self.data_source == "materials_project":
                print("   ⚠️  materials_project 모드에서는 대체 데이터를 사용하지 않습니다.")
                return pd.DataFrame()
            else:
                return self._get_manual_binary_references(element_a, element_b)

    def _get_manual_binary_references(self, element_a: str, element_b: str) -> pd.DataFrame:
        """
        범용 2원계 합금 문헌 데이터 생성 (Vegard's Law 사용)

        주요 원소의 격자상수와 밀도 데이터베이스를 사용하여 추정값 생성
        """
        print(f"📚 {element_a}-{element_b} 문헌 기반 레퍼런스 생성 중 (Vegard's Law)...")

        # 주요 금속 원소의 실험값 데이터베이스 (NIST/ASM Handbook)
        element_data = {
            "Cu": {"lattice_a": 3.6147, "density": 8.96, "crystal": "Fm-3m"},
            "Ni": {"lattice_a": 3.5238, "density": 8.90, "crystal": "Fm-3m"},
            "Al": {"lattice_a": 4.0495, "density": 2.70, "crystal": "Fm-3m"},
            "Mg": {"lattice_a": 3.2094, "density": 1.74, "crystal": "P63/mmc"},
            "Fe": {"lattice_a": 2.8665, "density": 7.87, "crystal": "Im-3m"},
            "Co": {"lattice_a": 3.5447, "density": 8.90, "crystal": "Fm-3m"},
            "Ti": {"lattice_a": 2.9508, "density": 4.51, "crystal": "P63/mmc"},
            "V":  {"lattice_a": 3.0240, "density": 6.11, "crystal": "Im-3m"},
            "Cr": {"lattice_a": 2.8846, "density": 7.19, "crystal": "Im-3m"},
            "Zn": {"lattice_a": 2.6650, "density": 7.14, "crystal": "P63/mmc"},
        }

        if element_a not in element_data or element_b not in element_data:
            print(f"⚠️  {element_a} 또는 {element_b}의 문헌 데이터가 없습니다.")
            return pd.DataFrame()

        data_a = element_data[element_a]
        data_b = element_data[element_b]

        experimental_data = [
            {
                "mp_id": f"MANUAL-{element_a}",
                "formula": element_a,
                "exp_lattice_a": data_a["lattice_a"],
                "exp_lattice_b": data_a["lattice_a"],
                "exp_lattice_c": data_a["lattice_a"],
                "exp_density": data_a["density"],
                "exp_formation_energy": 0.0,
                "exp_e_above_hull": 0.0,
                "crystal_system": data_a["crystal"]
            },
            {
                "mp_id": f"MANUAL-{element_b}",
                "formula": element_b,
                "exp_lattice_a": data_b["lattice_a"],
                "exp_lattice_b": data_b["lattice_a"],
                "exp_lattice_c": data_b["lattice_a"],
                "exp_density": data_b["density"],
                "exp_formation_energy": 0.0,
                "exp_e_above_hull": 0.0,
                "crystal_system": data_b["crystal"]
            },
            # 1:1 합금 (Vegard's Law)
            {
                "mp_id": f"MANUAL-{element_a}{element_b}",
                "formula": f"{element_a}{element_b}",
                "exp_lattice_a": (data_a["lattice_a"] + data_b["lattice_a"]) / 2,
                "exp_lattice_b": (data_a["lattice_a"] + data_b["lattice_a"]) / 2,
                "exp_lattice_c": (data_a["lattice_a"] + data_b["lattice_a"]) / 2,
                "exp_density": (data_a["density"] + data_b["density"]) / 2,
                "exp_formation_energy": -0.01,
                "exp_e_above_hull": 0.0,
                "crystal_system": data_a["crystal"]
            }
        ]

        df = pd.DataFrame(experimental_data)
        print(f"✅ 총 {len(df)}개의 {element_a}-{element_b} 문헌 기반 레퍼런스 생성 완료")
        print(f"   📋 화학식: {', '.join(df['formula'].tolist())}")
        print(f"   💡 Tip: exp_reference.py에서 원소 데이터를 추가할 수 있습니다.")
        return df

    def load_custom_csv(self, csv_path: str) -> pd.DataFrame:
        """
        사용자 정의 CSV 파일에서 실험 데이터 로드

        CSV 형식 요구사항:
        - formula: 화학식 (필수)
        - exp_lattice_a: 격자 상수 a (필수)
        - exp_density: 밀도 (필수)
        - exp_lattice_b, exp_lattice_c: 선택사항
        - mp_id, exp_formation_energy, exp_e_above_hull, crystal_system: 선택사항

        Args:
            csv_path: CSV 파일 경로

        Returns:
            실험 데이터 DataFrame
        """
        print(f"📂 사용자 정의 CSV 파일 로드 중: {csv_path}")

        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"❌ CSV 파일을 찾을 수 없습니다: {csv_path}")

        try:
            df = pd.read_csv(csv_path)

            # 필수 컬럼 체크
            required_cols = ["formula", "exp_lattice_a", "exp_density"]
            missing_cols = [col for col in required_cols if col not in df.columns]

            if missing_cols:
                raise ValueError(f"❌ 필수 컬럼이 누락되었습니다: {', '.join(missing_cols)}")

            # 선택사항 컬럼 자동 채우기
            if "exp_lattice_b" not in df.columns:
                df["exp_lattice_b"] = df["exp_lattice_a"]
            if "exp_lattice_c" not in df.columns:
                df["exp_lattice_c"] = df["exp_lattice_a"]
            if "mp_id" not in df.columns:
                df["mp_id"] = "CUSTOM-" + df["formula"]
            if "exp_formation_energy" not in df.columns:
                df["exp_formation_energy"] = 0.0
            if "exp_e_above_hull" not in df.columns:
                df["exp_e_above_hull"] = 0.0
            if "crystal_system" not in df.columns:
                df["crystal_system"] = "Unknown"

            print(f"✅ 총 {len(df)}개의 사용자 정의 레퍼런스 로드 완료")
            print(f"   📋 화학식: {', '.join(df['formula'].tolist())}")
            return df

        except Exception as e:
            raise ValueError(f"❌ CSV 파일 로드 중 오류 발생: {e}")

    def save_to_csv(self, df, filename="experimental_references.csv"):
        """추출된 데이터를 CSV로 저장"""
        if not df.empty:
            save_path = os.path.join(SimConfig.SAVE_DIR, filename)
            df.to_csv(save_path, index=False, encoding='utf-8-sig')
            print(f"💾 실험 레퍼런스 저장 완료: {save_path}")
            return save_path
        return None

# 테스트 실행부
if __name__ == "__main__":
    miner = ExperimentalDataMiner()
    ref_df = miner.fetch_cu_ni_references()
    print(ref_df)