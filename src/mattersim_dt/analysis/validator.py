# src/mattersim_dt/analysis/validator.py
import numpy as np
import pandas as pd
from pymatgen.core import Composition

class MaterialValidator:
    """
    시뮬레이션 데이터와 실험 데이터를 비교하여 채점하는 클래스
    """
    def __init__(self, sim_csv_path):
        self.sim_data = pd.read_csv(sim_csv_path)

    def _normalize_formula(self, formula):
        """화학식을 정규화된 reduced formula로 변환"""
        try:
            comp = Composition(formula)
            return comp.reduced_formula
        except:
            return formula

    def _find_matching_formula(self, exp_formula):
        """
        실험 데이터 화학식과 가장 유사한 시뮬레이션 화학식 찾기
        1. 정확한 매칭 시도
        2. Reduced formula 매칭 시도
        3. 순수 원소 매칭 (Cu, Ni)
        """
        # 1. 정확한 매칭
        exact_match = self.sim_data[self.sim_data['formula'] == exp_formula]
        if not exact_match.empty:
            return exact_match.iloc[0]

        # 2. Reduced formula 매칭
        exp_reduced = self._normalize_formula(exp_formula)
        for _, row in self.sim_data.iterrows():
            sim_reduced = self._normalize_formula(row['formula'])
            if sim_reduced == exp_reduced:
                return row

        # 3. 순수 원소 매칭 (Cu <-> Cu, Ni <-> Ni)
        if exp_formula in ['Cu', 'Ni']:
            match = self.sim_data[self.sim_data['formula'] == exp_formula]
            if not match.empty:
                return match.iloc[0]

        return None

    def calculate_score(self, exp_data: dict):
        """
        :param exp_data: { "formula": {"lattice_a": 3.61, "density": 8.96}, ... }
        :return: 채점 결과 리포트
        """
        reports = []
        matched_count = 0

        for formula, exp_val in exp_data.items():
            # 시뮬레이션 데이터에서 매칭되는 화학식 찾기
            row = self._find_matching_formula(formula)
            if row is None:
                continue

            matched_count += 1

            # 1. 격자 상수 오차 (Lattice Error)
            sim_a_raw = row.get('lattice_a', 0)
            exp_a = exp_val.get('lattice_a', 0)

            # 슈퍼셀 크기 자동 감지 및 단위 셀로 변환
            # 실험값(3-4 Å)보다 시뮬값이 3배 이상 크면 슈퍼셀로 판단
            if sim_a_raw > exp_a * 2.5:
                # 슈퍼셀 배수 추정 (가장 가까운 정수로 반올림)
                supercell_factor = round(sim_a_raw / exp_a)
                sim_a = sim_a_raw / supercell_factor
                print(f"   🔍 {row['formula']}: 슈퍼셀 감지 ({sim_a_raw:.2f} Å) → 단위셀로 변환 ({sim_a:.4f} Å, {supercell_factor}x{supercell_factor}x{supercell_factor})")
            else:
                sim_a = sim_a_raw

            a_error = abs(sim_a - exp_a) / exp_a * 100 if exp_a > 0 else 0
            
            # 2. 밀도 오차 (Density Error)
            sim_rho = row.get('density', 0)
            exp_rho = exp_val.get('density', 0)
            rho_error = abs(sim_rho - exp_rho) / exp_rho * 100 if exp_rho > 0 else 0
            
            # 3. 종합 점수 (100점 만점 기준, 오차율의 가중 평균)
            # 오차가 0%면 100점, 5%면 95점...
            total_error = (a_error * 0.6) + (rho_error * 0.4)
            score = max(0, 100 - total_error)
            
            reports.append({
                "exp_formula": formula,
                "sim_formula": row['formula'],
                "sim_lattice_a": round(sim_a, 4),
                "exp_lattice_a": round(exp_a, 4),
                "lattice_error_pct": round(a_error, 2),
                "sim_density": round(sim_rho, 4),
                "exp_density": round(exp_rho, 4),
                "density_error_pct": round(rho_error, 2),
                "accuracy_score": round(score, 2)
            })

        print(f"\n   📊 매칭 결과: 실험 데이터 {len(exp_data)}개 중 {matched_count}개 매칭됨")

        return pd.DataFrame(reports)

    def print_summary(self, report_df):
        print("\n" + "="*70)
        print("🎯 Digital Twin vs Experiment Validation")
        print("="*70)

        if report_df.empty:
            print("⚠️  매칭된 데이터가 없습니다.")
            return

        avg_score = report_df['accuracy_score'].mean()
        avg_lattice_err = report_df['lattice_error_pct'].mean()
        avg_density_err = report_df['density_error_pct'].mean()

        print(f"\n📊 종합 통계:")
        print(f"   - 전체 평균 정확도: {avg_score:.2f} / 100")
        print(f"   - 평균 격자 오차: {avg_lattice_err:.2f}%")
        print(f"   - 평균 밀도 오차: {avg_density_err:.2f}%")

        print("\n" + "-" * 70)
        print(f"{'화학식':<10} | {'시뮬 격자(Å)':<12} | {'실험 격자(Å)':<12} | {'격자오차%':<10} | {'정확도':<8}")
        print("-" * 70)

        for _, row in report_df.iterrows():
            print(f"{row['exp_formula']:<10} | {row['sim_lattice_a']:<12.4f} | {row['exp_lattice_a']:<12.4f} | {row['lattice_error_pct']:<10.2f} | {row['accuracy_score']:<8.2f}")

        print("=" * 70)