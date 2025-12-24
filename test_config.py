# test_config.py - Config 설정 테스트 스크립트
from mattersim_dt.core import SimConfig

print("="*70)
print("⚙️  현재 Config 설정 확인")
print("="*70)

print("\n📂 [파이프라인 모드]")
print(f"   PIPELINE_MODE: {SimConfig.PIPELINE_MODE}")

if SimConfig.PIPELINE_MODE == "auto":
    print(f"   CSV 경로: {SimConfig.MINER_CSV_PATH}")
    print(f"   최대 시스템 수: {SimConfig.MAX_SYSTEMS}")
elif SimConfig.PIPELINE_MODE == "manual":
    print(f"   원소 A: {SimConfig.MANUAL_ELEMENT_A}")
    print(f"   원소 B: {SimConfig.MANUAL_ELEMENT_B}")

print("\n🔢 [혼합 비율 설정]")
print(f"   MIXING_RATIO_STEP: {SimConfig.MIXING_RATIO_STEP}")

mixing_ratios = SimConfig.get_mixing_ratios()
print(f"   생성된 비율 개수: {len(mixing_ratios)}개")
print(f"   비율 리스트: {mixing_ratios}")

print("\n🧊 [구조 설정]")
print(f"   슈퍼셀 크기: {SimConfig.SUPERCELL_SIZE}x{SimConfig.SUPERCELL_SIZE}x{SimConfig.SUPERCELL_SIZE}")

print("\n🔥 [MD 시뮬레이션 설정]")
print(f"   온도: {SimConfig.MD_TEMPERATURE} K")
print(f"   스텝 수: {SimConfig.MD_STEPS}")
print(f"   시간 간격: {SimConfig.MD_TIMESTEP} fs")

print("\n✅ [필터링 기준]")
print(f"   안정성 임계값: {SimConfig.STABILITY_THRESHOLD} eV/atom")

print("\n💾 [저장 설정]")
print(f"   결과 저장 폴더: {SimConfig.SAVE_DIR}")
print(f"   디바이스: {SimConfig.DEVICE}")

print("\n" + "="*70)
print("✅ 설정 확인 완료!")
print("="*70)

# 예상 계산량 추정
if SimConfig.PIPELINE_MODE == "auto":
    num_systems = SimConfig.MAX_SYSTEMS if SimConfig.MAX_SYSTEMS else "전체"
else:
    num_systems = 1

num_ratios = len(mixing_ratios)
total_structures = num_ratios + 2  # 비율 + 순수 원소 2개

print(f"\n📊 예상 계산량:")
print(f"   - 시스템 수: {num_systems}")
print(f"   - 시스템당 구조 수: {total_structures}개")
if isinstance(num_systems, int):
    print(f"   - 총 구조 수: {num_systems * total_structures}개")
    print(f"   - 예상 소요 시간: 약 {num_systems * total_structures * 0.5:.0f}분 (GPU 기준)")

print("\n💡 설정을 변경하려면 src/mattersim_dt/core/config.py를 수정하세요.")
