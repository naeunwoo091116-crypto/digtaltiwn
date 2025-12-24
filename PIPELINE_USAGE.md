# 🌐 MatterSim Pipeline 사용 가이드

## 📋 개요

MatterSim 파이프라인은 CSV 파일에서 원소 조합을 자동으로 읽어와 다음 3단계를 수행합니다:

1. **Phase 1**: 비율별 혼합 및 구조 이완 (Mix + Relax)
2. **Phase 2**: 열역학적 안정성 필터링 (Stability Filter)
3. **Phase 3**: 분자동역학 시뮬레이션 (MD - 안정 구조만)

---

## 🔄 모듈 호출 순서

파이프라인은 다음과 같은 순서로 모듈을 호출합니다:

### 0️⃣ 초기화 단계
```
SimConfig.setup()
  ↓
get_calculator(device)          # MatterSim Calculator 생성
  ↓
StructureRelaxer(calculator)    # 구조 이완 엔진 생성
  ↓
MDSimulator(calculator)         # MD 시뮬레이터 생성
```

### 1️⃣ Phase 1: 구조 생성 및 이완
**각 원소 조합에 대해 반복:**

```
RandomAlloyMixer(element_A)
  ↓
mixer.base_atoms                    # 순수 원소 A 구조 생성
  ↓
StructureRelaxer.run()              # 구조 이완
  ↓
StabilityAnalyzer.add_result()      # 결과 등록
```

```
RandomAlloyMixer(element_B)
  ↓
mixer.base_atoms                    # 순수 원소 B 구조 생성
  ↓
StructureRelaxer.run()              # 구조 이완
  ↓
StabilityAnalyzer.add_result()      # 결과 등록
```

**비율별 합금 생성 (MIXING_RATIO_STEP에 따라):**

```
RandomAlloyMixer(element_A)
  ↓
mixer.generate_structure(element_B, ratio)  # 합금 구조 생성
  ↓
StructureRelaxer.run()                      # 구조 이완
  ↓
StabilityAnalyzer.add_result()              # 결과 등록
```

**병렬 모드 (PARALLEL_RATIO_CALCULATION = True 시):**

```
RandomAlloyMixer(element_A)
  ↓
[모든 비율에 대해 구조 생성]
  ↓
BatchStructureRelaxer.run_batch()   # 배치 이완
  ↓
StabilityAnalyzer.add_result()      # 결과 등록
```

### 2️⃣ Phase 2: 안정성 필터링

```
StabilityAnalyzer.analyze()
  ↓
Pymatgen Convex Hull 계산          # 열역학 안정성 분석
  ↓
energy_above_hull 계산              # Convex Hull 위 에너지
  ↓
is_stable 판정                      # 안정성 필터링 (threshold 기준)
```

### 3️⃣ Phase 3: 분자동역학 시뮬레이션

**안정한 구조만 대상:**

```
MDSimulator.run(atoms, temperature, steps)
  ↓
NVT Ensemble MD 실행                # Nose-Hoover 온도 조절
  ↓
Trajectory 저장                     # 궤적 파일 (.traj)
  ↓
MDAnalyzer(traj_file)
  ↓
MDAnalyzer.analyze()
  ↓
물성 계산:
  - 평균 온도
  - 온도 변동률
  - 평균 에너지
  - 부피 변화율
  - 열적 안정성 판정
```

**다중 온도 병렬 MD (PARALLEL_MD_TEMPERATURES = True 시):**

```
MDSimulator.run_multi_temperature(atoms, temperatures, steps)
  ↓
[각 온도별로 병렬 MD 실행]
  ↓
[각 온도별 MDAnalyzer.analyze()]
  ↓
온도별 물성 비교
```

### 📦 사용되는 주요 모듈

| 단계 | 모듈 | 역할 |
|------|------|------|
| 초기화 | `mattersim_dt.core.SimConfig` | 설정 관리 |
| 초기화 | `mattersim_dt.engine.get_calculator` | MatterSim 계산기 생성 |
| Phase 1 | `mattersim_dt.builder.RandomAlloyMixer` | 구조 생성 (순수 원소 + 합금) |
| Phase 1 | `mattersim_dt.engine.StructureRelaxer` | 구조 이완 |
| Phase 1 | `mattersim_dt.engine.BatchStructureRelaxer` | 배치 구조 이완 (병렬) |
| Phase 2 | `mattersim_dt.analysis.StabilityAnalyzer` | Convex Hull 안정성 분석 |
| Phase 3 | `mattersim_dt.engine.MDSimulator` | 분자동역학 시뮬레이션 |
| Phase 3 | `mattersim_dt.analysis.MDAnalyzer` | MD 결과 분석 |

### 🔀 데이터 흐름

```
CSV 파일 (auto_mining_results_final.csv)
  ↓
원소 조합 추출 (Al-Li, Cu-Ni, ...)
  ↓
[각 조합마다]
  ↓
  [Phase 1] 구조 생성 → 이완 → relaxed_structures{}
  ↓
  [Phase 2] 안정성 분석 → stable_formulas[]
  ↓
  [Phase 3] MD 시뮬레이션 → 물성 계산
  ↓
detailed_data[] (CSV 저장용)
  ↓
pipeline_results_YYYYMMDD_HHMMSS.csv
```

---

## ⚙️ 설정 방법

### 1. config.py 설정

파일 위치: `src/mattersim_dt/core/config.py`

```python
# Pipeline 설정
PIPELINE_MODE = "auto"  # "auto" 또는 "manual"
MANUAL_ELEMENT_A = "Cu"  # manual 모드일 때만 사용
MANUAL_ELEMENT_B = "Ni"  # manual 모드일 때만 사용
MAX_SYSTEMS = 5  # auto 모드에서 실험할 최대 시스템 수 (None이면 전체)

# Miner (광부) 설정
MINER_CSV_PATH = "auto_mining_results_final.csv"  # CSV 파일 경로

# 구조 생성 설정
MIXING_RATIO_STEP = 0.1  # 혼합 비율 간격 (0.1 = 10%씩, 0.05 = 5%씩)
SUPERCELL_SIZE = 3

# MD 설정
MD_TEMPERATURE = 1000.0  # 온도 (K)
MD_STEPS = 1000
MD_TIMESTEP = 1.0

# 필터링 기준
STABILITY_THRESHOLD = 0.05
```

---

## 🎮 사용 모드

### Mode 1: AUTO (CSV 자동 로드) ✅ 권장

CSV 파일에서 원소 조합을 자동으로 읽어와 실험합니다.

**설정:**
```python
PIPELINE_MODE = "auto"
MINER_CSV_PATH = "auto_mining_results_final.csv"
MAX_SYSTEMS = 5  # 상위 5개만 실험 (None이면 전체)
```

**실행:**
```bash
python run_pipeline.py
```

**동작:**
- `auto_mining_results_final.csv`에서 2원소 조합 추출
- 중복 제거 후 최대 `MAX_SYSTEMS`개 선택
- 각 조합에 대해 전체 파이프라인 실행

**예시 출력:**
```
📂 CSV 파일 로딩 중: auto_mining_results_final.csv
✅ 총 50개의 2원소 시스템 발견

🚀 총 5개 시스템에 대해 파이프라인 실행 시작

######################################################################
# [1/5] 시스템 실행 중
######################################################################

======================================================================
🎯 Target System: Al - Li
======================================================================

=== [Phase 1] 비율별 혼합 및 구조 이완 ===
...
=== [Phase 2] 열역학적 안정성 필터링 ===
...
=== [Phase 3] 분자동역학 시뮬레이션 (안정 구조만) ===
...

   ✅ Al-Li 완료
      - 총 구조: 11개
      - 안정 구조: 3개
      - MD 완료: 3개
```

---

### Mode 2: MANUAL (수동 지정)

특정 원소 조합만 테스트할 때 사용합니다.

**설정:**
```python
PIPELINE_MODE = "manual"
MANUAL_ELEMENT_A = "Cu"
MANUAL_ELEMENT_B = "Ni"
```

**실행:**
```bash
python run_pipeline.py
```

**동작:**
- Cu-Ni 조합에 대해서만 실험 수행

---

## 📊 최종 결과 요약

파이프라인이 끝나면 전체 요약 테이블이 출력됩니다:

```
======================================================================
🎯 전체 파이프라인 실행 완료
======================================================================

System               | Structures   | Stable     | MD Done
----------------------------------------------------------------------
Al-Li                | 11           | 3          | 3
Cu-Ni                | 11           | 5          | 5
Fe-Co                | 11           | 2          | 2
Mg-Zn                | 11           | 1          | 1
Ti-V                 | 11           | 4          | 4
----------------------------------------------------------------------
TOTAL                |              | 15         | 15
======================================================================
```

---

## 🔧 세부 설정 옵션

### 혼합 비율 조정 ⭐ 간편해짐!

**이제 간격(step)만 지정하면 자동 생성됩니다:**

```python
# 기본 (10% 단위) → 0.1, 0.2, 0.3, ..., 0.9
MIXING_RATIO_STEP = 0.1

# 5% 단위로 변경 → 0.05, 0.1, 0.15, ..., 0.95
MIXING_RATIO_STEP = 0.05

# 20% 단위로 빠르게 → 0.2, 0.4, 0.6, 0.8
MIXING_RATIO_STEP = 0.2

# 25% 단위 → 0.25, 0.5, 0.75
MIXING_RATIO_STEP = 0.25
```

**자동 생성 규칙:**
- 0.0과 1.0은 자동으로 제외 (순수 원소는 별도 계산)
- 부동소수점 오차 자동 보정

### 슈퍼셀 크기 조정

더 큰 시스템으로 실험하려면:

```python
# 기본 (3x3x3 = 27배)
SUPERCELL_SIZE = 3

# 더 크게 (4x4x4 = 64배)
SUPERCELL_SIZE = 4

# 주의: 크기가 클수록 계산 시간 급증!
```

### MD 온도 조정

```python
# 실온 (300K)
MD_TEMPERATURE = 300.0

# 고온 (1000K) - 기본값
MD_TEMPERATURE = 1000.0

# 극고온 (2000K)
MD_TEMPERATURE = 2000.0
```

---

## 📁 파일 구조

```
digtaltiwn/
├── run_pipeline.py                    # 메인 파이프라인 실행 파일
├── auto_mining_results_final.csv      # CSV 데이터 (run_auto_miner.py로 생성)
├── src/
│   └── mattersim_dt/
│       ├── core/
│       │   └── config.py             # 설정 파일 ★
│       ├── builder/
│       │   └── mixer.py              # 구조 생성
│       ├── engine/
│       │   ├── relax.py              # 구조 이완
│       │   └── md.py                 # MD 시뮬레이션
│       └── analysis/
│           └── stability.py          # 안정성 분석
└── data/
    └── final_results/                # 결과 저장 폴더
```

---

## 🚀 빠른 시작

### 1. CSV 생성 (처음 1회만)

```bash
python run_auto_miner.py
```
→ `auto_mining_results_final.csv` 생성됨

### 2. config.py 설정

```python
PIPELINE_MODE = "auto"
MAX_SYSTEMS = 3  # 처음엔 작은 수로 테스트
```

### 3. 파이프라인 실행

```bash
python run_pipeline.py
```

### 4. 결과 확인

터미널에 출력되는 요약 테이블을 확인하세요!

---

## ⚠️ 주의사항

1. **계산 시간**: 1개 시스템당 약 5-10분 소요 (GPU 사용 시)
2. **메모리**: 슈퍼셀 크기가 클수록 메모리 사용량 증가
3. **CSV 형식**: `formula` 컬럼이 반드시 필요합니다
4. **API Key**: config.py에 Materials Project API 키가 설정되어 있어야 합니다

---

## 🐛 문제 해결

### CSV를 찾을 수 없습니다

```
⚠️  CSV 파일을 찾을 수 없습니다: auto_mining_results_final.csv
```

**해결:** `run_auto_miner.py`를 먼저 실행하세요.

### 원소 조합이 없습니다

```
✅ 총 0개의 2원소 시스템 발견
```

**해결:** CSV 파일이 비어있거나 형식이 잘못되었습니다. CSV 파일을 확인하세요.

### CUDA 메모리 부족

**해결:** config.py에서 다음 값을 줄이세요:
- `SUPERCELL_SIZE = 2` (더 작게)
- `MIXING_RATIOS`의 개수 줄이기

---

## 📈 성능 최적화

### GPU 사용 확인

```python
# config.py
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
```

터미널에서 GPU 사용 여부 확인:
```bash
python -c "import torch; print(torch.cuda.is_available())"
```

### 병렬 처리

현재는 순차 실행입니다. 여러 GPU가 있다면 시스템별로 병렬 처리 가능합니다.

---

## 📞 지원

문제가 발생하면 다음을 확인하세요:

1. Python 버전: 3.8 이상
2. 필수 패키지 설치: `pip install -r requirements.txt`
3. API Key 설정: config.py의 `MP_API_KEY`

---

**Happy Material Discovery! 🔬✨**
