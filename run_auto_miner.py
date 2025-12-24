# run_auto_miner.py
from mattersim_dt.miner import MaterialMiner
from itertools import combinations
import pandas as pd
import time
import os

# [설정] 본인의 API Key
MY_API_KEY = "5DPnayEkpta3vy5RiF6wNa2Am0O28x9s"

def main():
    print("=== 🤖 MatterSim 오토 마이닝 시스템 (Auto-Miner) ===")
    
    # 1. 탐색할 '마스터 원소 풀' 정의
    # (산업적으로 의미 있는 금속 35종을 미리 선정했습니다)
    master_pool = [
        'Li', 'Be', 'Mg', 'Al',  # 경금속
        'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn', # 4주기 전이금속
        'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', # 5주기
        'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au'  # 6주기 (귀금속 포함)
    ]
    
    print(f"\n🎯 탐색 대상 원소: 총 {len(master_pool)}개")
    print(f"   {master_pool}")

    # 2. 모든 가능한 2원소 조합(Binary) 생성
    # combinations 함수가 알아서 중복 없이 짝을 지어줍니다.
    # 예: (Li, Be), (Li, Mg) ... (Pt, Au)
    all_pairs = list(combinations(master_pool, 2))
    total_pairs = len(all_pairs)
    
    print(f"📋 검색해야 할 전체 조합 수: {total_pairs}쌍")
    print("   (예상 소요 시간: 약 10~15분)")
    
    miner = MaterialMiner(api_key=MY_API_KEY)
    
    # 결과 저장용 리스트
    found_materials = []
    
    # 3. 자동화 루프 시작
    print("\n🚀 채굴 시작! (멈추려면 Ctrl+C를 누르세요)")
    
    try:
        for i, pair in enumerate(all_pairs):
            pair_list = list(pair)
            
            # 진행률 표시 (예: [5/435] 1.1% 완료...)
            progress = (i + 1) / total_pairs * 100
            print(f"\r[{i+1}/{total_pairs}] {progress:.1f}% | 🔎 {pair_list} 검색 중...", end="")
            
            # API 검색
            try:
                # search_metal_alloys 함수가 내부적으로 비금속 체크 등을 수행함
                results = miner.search_metal_alloys(pair_list)
                
                if results:
                    found_materials.extend(results)
                    print(f" -> ✨ {len(results)}건 발견!", end="")
                    
            except Exception as e:
                print(f" -> ⚠️ 에러: {e}", end="")

            # 서버 매너 타임 (너무 빠르면 차단당함)
            time.sleep(0.5)
            
            # 4. [안전 장치] 50번 검색할 때마다 중간 저장
            if (i + 1) % 50 == 0:
                save_to_csv(found_materials, "auto_mining_results_partial.csv")
                print(f"\n   💾 중간 저장 완료 ({len(found_materials)}개 누적)")

    except KeyboardInterrupt:
        print("\n\n🛑 사용자에 의해 중단되었습니다.")
    
    # 5. 최종 저장
    print("\n" + "="*50)
    print(f"🎉 탐색 종료! 총 {len(found_materials)}개의 합금을 발견했습니다.")
    save_to_csv(found_materials, "auto_mining_results_final.csv")

def save_to_csv(data, filename):
    if not data:
        return
    df = pd.DataFrame(data)
    # 필요한 컬럼만 깔끔하게
    cols = ['formula', 'id', 'energy', 'stability', 'structure', 'space_group']
    # 딕셔너리에 없는 키가 있을 수 있으니 안전하게 처리
    df = df.reindex(columns=[c for c in cols if c in df.columns])
    df.to_csv(filename, index=False)
    print(f" -> 파일 저장됨: {filename}")

if __name__ == "__main__":
    main()