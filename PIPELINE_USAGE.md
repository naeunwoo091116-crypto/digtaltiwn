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
| Phase 3 | `mattersim_dt.engine.BatchMDSimulator` | 배치 MD 시뮬레이션 (병렬) |
| Phase 3 | `mattersim_dt.analysis.MDAnalyzer` | MD 결과 분석 |
| 병렬 | `mattersim_dt.engine.ParallelSystemRunner` | 다중 GPU 시스템 병렬 실행 |
| 검증 | `mattersim_dt.analysis.MaterialValidator` | 시뮬레이션 vs 실험 데이터 비교 |
| 데이터 | `mattersim_dt.miner.ExperimentalDataMiner` | 실험 데이터 마이닝 (27개 원소 DB) |

### 🔀 데이터 흐름

```
src/mattersim_dt/
├── core/
│   ├── __init__.py          # SimConfig 노출
│   └── config.py            # 설정 관리 (Trajectory 저장 옵션 추가)
│
├── builder/
│   ├── __init__.py          # RandomAlloyMixer 노출
│   ├── mixer.py             # 합금 구조 생성
│   ├── prototypes.py        # 프로토타입 구조
│   └── supercell.py         # 슈퍼셀 생성
│
├── engine/
│   ├── __init__.py          # get_calculator, StructureRelaxer, MDSimulator, BatchStructureRelaxer, BatchMDSimulator, ParallelSystemRunner 노출
│   ├── calculator.py        # MatterSim Calculator
│   ├── relax.py             # 구조 이완 (화학식 기반 trajectory 저장)
│   ├── md.py                # 분자동역학 시뮬레이션 (NPT Ensemble, 화학식 기반 trajectory 저장)
│   ├── batch_relax.py       # 배치 구조 이완 (병렬 처리)
│   ├── batch_md.py          # 배치 MD 시뮬레이션 (병렬 처리)
│   └── parallel_system.py   # 다중 GPU 시스템 병렬 실행
│
├── analysis/
│   ├── __init__.py          # StabilityAnalyzer, MDAnalyzer, MaterialValidator 노출
│   ├── stability.py         # 열역학적 안정성 분석
│   ├── md_analyzer.py       # MD Trajectory 분석 (평형화 자동 처리)
│   └── validator.py         # 시뮬레이션 vs 실험 데이터 검증 및 채점
│
└── miner/
    ├── __init__.py          # MaterialMiner, ExperimentalDataMiner 노출
    ├── mp_api.py            # Materials Project API
    └── exp_reference.py     # 실험 데이터 마이닝 (27개 원소 문헌 데이터베이스)
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

# 검증 및 채점 설정
ENABLE_VALIDATION = True            # 실험 데이터 비교 및 채점 수행 여부
VALIDATION_SAVE_EXP_DATA = True     # 실험 데이터 CSV 저장 여부
VALIDATION_SAVE_REPORT = True       # 채점 리포트 CSV 저장 여부

# 실험 데이터 소스 설정
VALIDATION_DATA_SOURCE = "auto"     # "materials_project": MP API만, "literature": 문헌만, "auto": MP 시도 후 문헌
VALIDATION_USE_THEORETICAL = False  # Materials Project에서 theoretical 데이터 포함 여부 (False: 실험만)
CUSTOM_EXP_DATA_CSV = None          # 사용자 정의 CSV 경로 (None이면 위 설정 사용)

# 병렬 처리 설정
PARALLEL_RATIO_CALCULATION = True   # 비율별 병렬 계산
RATIO_BATCH_SIZE = 4                # 한 번에 계산할 비율 개수
PARALLEL_SYSTEM_CALCULATION = False # 시스템별 병렬 (Windows에서는 False 권장)
NUM_GPUS = 1                        # 사용 가능한 GPU 개수
PARALLEL_MD_EXECUTION = True        # MD 병렬 실행
MD_NUM_PROCESSES = 2                # MD 병렬 프로세스 수

# Trajectory 저장 설정
SAVE_RELAX_TRAJ = True              # 구조 이완 과정 저장 여부
SAVE_MD_TRAJ = True                 # MD 시뮬레이션 과정 저장 여부

# Resume 설정
RESUME_MODE = True                  # 완료된 결과 건너뛰기
RESUME_CSV_PATH = None              # 특정 CSV 지정 (None이면 최신 파일 자동 찾기)
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

### 검증 및 채점 설정

```python
# 시나리오 1: 전체 검증 활성화 (기본값)
ENABLE_VALIDATION = True
VALIDATION_SAVE_EXP_DATA = True
VALIDATION_SAVE_REPORT = True

# 시나리오 2: 검증만 수행, 파일 저장 안 함
ENABLE_VALIDATION = True
VALIDATION_SAVE_EXP_DATA = False
VALIDATION_SAVE_REPORT = False

# 시나리오 3: 검증 완전히 비활성화 (빠른 시뮬레이션)
ENABLE_VALIDATION = False
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

### 병렬 처리 ⚙️ 신규 기능!

파이프라인은 다양한 레벨에서 병렬 처리를 지원합니다:

#### 1️⃣ 비율별 병렬 계산 (권장)

같은 시스템 내에서 여러 혼합 비율을 동시에 계산합니다.

```python
# config.py
PARALLEL_RATIO_CALCULATION = True
RATIO_BATCH_SIZE = 4  # 한 번에 4개 비율 동시 계산
```

**효과:**
- Al-Li 시스템에서 0.1, 0.2, 0.3, 0.4 비율을 동시에 계산
- GPU 활용률 극대화
- 단일 GPU에서도 효과적

#### 2️⃣ MD 병렬 실행

안정한 구조들에 대해 MD를 병렬로 실행합니다.

```python
# config.py
PARALLEL_MD_EXECUTION = True
MD_NUM_PROCESSES = 2  # 2개 프로세스로 병렬 실행
```

**효과:**
- 여러 안정 구조에 대한 MD를 동시 실행
- CPU 멀티코어 활용

#### 3️⃣ 시스템별 병렬 계산 (다중 GPU 전용)

여러 원소 조합을 다른 GPU에서 동시에 실행합니다.

```python
# config.py (Linux 환경 권장)
PARALLEL_SYSTEM_CALCULATION = True
NUM_GPUS = 4  # 4개 GPU 사용
```

**주의:**
- Windows에서는 `False` 권장 (multiprocessing 제약)
- Linux 환경에서 다중 GPU가 있을 때만 활성화
- GPU별로 독립적인 프로세스 실행

**동작 방식:**
```
GPU 0: Al-Li 시스템 전체 실행
GPU 1: Cu-Ni 시스템 전체 실행
GPU 2: Fe-Co 시스템 전체 실행
GPU 3: Mg-Zn 시스템 전체 실행
```

#### 4️⃣ Resume 모드 (중단된 작업 이어서 하기)

이미 완료된 시스템을 건너뛰고 나머지만 실행합니다.

```python
# config.py
RESUME_MODE = True
RESUME_CSV_PATH = None  # 최신 결과 파일 자동 찾기
```

**효과:**
- 파이프라인이 중단되어도 처음부터 다시 시작할 필요 없음
- `pipeline_results_YYYYMMDD_HHMMSS.csv`에서 완료 여부 확인
- 특정 파일 지정도 가능: `RESUME_CSV_PATH = "pipeline_results_20251229_132400.csv"`

---

## 📞 지원

문제가 발생하면 다음을 확인하세요:

1. Python 버전: 3.8 이상
2. 필수 패키지 설치: `pip install -r requirements.txt`
3. API Key 설정: config.py의 `MP_API_KEY`

---

## 🎯 고급 기능

### 1. 실험 데이터 검증 및 채점 ⭐ 설정 가능!

시뮬레이션 결과를 실험 데이터와 자동으로 비교하고 정확도를 채점합니다.

## 📊 실험 데이터 소스

현재 파이프라인은 다음 3가지 실험 데이터 소스를 지원합니다:

### 1️⃣ Materials Project API (기본값)
- **출처**: Materials Project Database
- **데이터**: 실제 실험 측정값 (`theoretical=False`)
- **장점**: 방대한 실험 데이터베이스 (27개 원소 지원)
- **단점**: API 키 필요, 네트워크 연결 필요

### 2️⃣ 문헌 기반 데이터베이스
- **출처**: NIST, ASM Handbook 등의 문헌값
- **데이터**: 순수 원소 격자상수 + Vegard's Law로 합금 추정
- **장점**: API 키 불필요, 오프라인 사용 가능
- **단점**: 제한적인 원소 (현재 9개), 합금은 추정값

**지원 원소 (문헌 DB):**
```
Cu, Ni, Al, Mg, Fe, Co, Ti, V, Cr, Zn
```

### 3️⃣ 사용자 정의 CSV
- **출처**: 사용자가 직접 준비한 실험 데이터
- **데이터**: 사용자가 측정/수집한 값
- **장점**: 자유롭게 데이터 커스터마이징 가능
- **단점**: 직접 CSV 파일 준비 필요

---

## ⚙️ config.py 설정

```python
# 검증 및 채점 설정
ENABLE_VALIDATION = True            # False로 설정하면 검증 단계를 완전히 건너뜀
VALIDATION_SAVE_EXP_DATA = True     # False로 설정하면 실험 데이터 CSV 저장 안 함
VALIDATION_SAVE_REPORT = True       # False로 설정하면 채점 리포트 CSV 저장 안 함

# 실험 데이터 소스 설정
VALIDATION_DATA_SOURCE = "auto"     # 데이터 소스 선택 (아래 참조)
VALIDATION_USE_THEORETICAL = False  # MP에서 theoretical 데이터 포함 여부
CUSTOM_EXP_DATA_CSV = None          # 사용자 정의 CSV 경로
```

### VALIDATION_DATA_SOURCE 옵션:

| 값 | 동작 | 사용 시나리오 |
|---|---|---|
| `"auto"` | MP API 시도 → 실패 시 문헌 DB로 자동 대체 | **권장**: 안정적이고 유연함 |
| `"materials_project"` | MP API만 사용 (실패 시 빈 데이터) | MP 데이터만 신뢰할 때 |
| `"literature"` | 문헌 DB만 사용 (MP 건너뜀) | 오프라인 환경, API 키 없을 때 |

### VALIDATION_USE_THEORETICAL 옵션:

| 값 | MP에서 가져오는 데이터 | 설명 |
|---|---|---|
| `False` | 실험 데이터만 (`theoretical=False`) | **권장**: 실제 측정값만 |
| `True` | 실험 + 이론 데이터 (`theoretical=True/False 모두`) | 더 많은 데이터 포함 |

---

## 🎯 사용 시나리오

1. **전체 검증 활성화** (기본값, 권장)
   ```python
   ENABLE_VALIDATION = True
   VALIDATION_SAVE_EXP_DATA = True
   VALIDATION_SAVE_REPORT = True
   ```
   - 실험 데이터 다운로드 → 검증 수행 → 리포트 저장

2. **검증만 수행, 파일 저장 안 함**
   ```python
   ENABLE_VALIDATION = True
   VALIDATION_SAVE_EXP_DATA = False
   VALIDATION_SAVE_REPORT = False
   ```
   - 터미널에 채점 결과만 출력, CSV 파일 생성 안 함

3. **검증 완전히 비활성화** (빠른 시뮬레이션만 원할 때)
   ```python
   ENABLE_VALIDATION = False
   ```
   - 시뮬레이션만 수행, 검증 단계 완전 건너뜀
   - Materials Project API 호출 없음 (API 키 불필요)

4. **문헌 데이터만 사용** (오프라인 환경)
   ```python
   ENABLE_VALIDATION = True
   VALIDATION_DATA_SOURCE = "literature"
   ```
   - Materials Project API 건너뜀
   - NIST/ASM Handbook 문헌값 사용
   - API 키 없이도 검증 가능

5. **사용자 정의 실험 데이터 사용**
   ```python
   ENABLE_VALIDATION = True
   CUSTOM_EXP_DATA_CSV = "my_experimental_data.csv"
   ```
   - 자체 실험 데이터로 검증
   - CSV 형식 요구사항은 아래 참조

---

## 📂 사용자 정의 CSV 형식

자체 실험 데이터를 사용하려면 다음 형식의 CSV 파일을 준비하세요:

### 필수 컬럼:
| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| `formula` | 화학식 | Cu, Ni, CuNi |
| `exp_lattice_a` | 격자 상수 a (Å) | 3.6147 |
| `exp_density` | 밀도 (g/cm³) | 8.96 |

### 선택 컬럼 (자동 채워짐):
| 컬럼명 | 기본값 | 설명 |
|--------|---------|------|
| `exp_lattice_b` | = lattice_a | 격자 상수 b |
| `exp_lattice_c` | = lattice_a | 격자 상수 c |
| `mp_id` | CUSTOM-{formula} | 식별자 |
| `exp_formation_energy` | 0.0 | 생성 에너지 |
| `exp_e_above_hull` | 0.0 | Hull 위 에너지 |
| `crystal_system` | Unknown | 결정계 |

### 예시 CSV 파일:

```csv
formula,exp_lattice_a,exp_density,crystal_system
Cu,3.6147,8.96,Fm-3m
Ni,3.5238,8.90,Fm-3m
CuNi,3.5693,8.93,Fm-3m
Fe,2.8665,7.87,Im-3m
Cr,2.8846,7.19,Im-3m
FeCr,2.8756,7.53,Im-3m
```

### 사용 방법:

```python
# config.py
CUSTOM_EXP_DATA_CSV = "my_experimental_data.csv"
```

또는 프로그래밍 방식:

```python
from mattersim_dt.miner import ExperimentalDataMiner

miner = ExperimentalDataMiner()
exp_df = miner.load_custom_csv("my_experimental_data.csv")
```

---

**프로그래밍 방식 사용:**

```python
from mattersim_dt.miner import ExperimentalDataMiner
from mattersim_dt.analysis import MaterialValidator

# 1. 실험 데이터 가져오기
miner = ExperimentalDataMiner()
exp_data_df = miner.fetch_binary_alloy_references("Cu", "Ni")
exp_data_df.to_csv("data/final_results/experimental_references.csv", index=False)

# 2. 시뮬레이션 결과와 비교
validator = MaterialValidator("pipeline_results_20251229_132400.csv")
report_df = validator.calculate_score(exp_data_df)
validator.print_summary(report_df)

# 3. 검증 보고서 저장
report_df.to_csv("validation_report.csv", index=False)
```

**채점 기준:**
- **격자 상수 오차** (가중치 60%): `|sim - exp| / exp × 100`
- **밀도 오차** (가중치 40%): `|sim - exp| / exp × 100`
- **최종 점수**: `max(0, 100 - total_error)`

**슈퍼셀 자동 정규화:**
- 시뮬레이션이 슈퍼셀인 경우 자동으로 단위셀로 변환
- 예: `Cu64` (슈퍼셀) → `Cu` (단위셀) 로 변환하여 비교

**예시 출력:**
```
======================================================================
📊 시뮬레이션 vs 실험 데이터 검증 보고서
======================================================================

실험 화학식 | 시뮬 화학식 | 격자 오차(%) | 밀도 오차(%) | 정확도 점수
----------------------------------------------------------------------
Cu          | Cu64        | 0.00         | 0.05         | 99.97
Ni          | Ni64        | 0.12         | 0.08         | 99.88
CuNi        | Cu32Ni32    | 1.20         | 0.85         | 98.27
----------------------------------------------------------------------

평균 정확도: 99.37/100
```

### 2. 실험 데이터 마이닝 (27개 원소 지원)

Materials Project API와 문헌 데이터베이스를 활용하여 실험 레퍼런스를 생성합니다.

**지원 원소 (27개):**
```
Li, Be, Mg, Al, Ti, V, Cr, Mn, Fe, Co, Ni, Cu, Zn,
Zr, Nb, Mo, Tc, Ru, Rh, Pd, Ag, Cd, Hf, Ta, W, Re,
Os, Ir, Pt, Au
```

**사용 방법:**

```python
from mattersim_dt.miner import ExperimentalDataMiner

miner = ExperimentalDataMiner()

# 방법 1: Materials Project에서 가져오기 (Cu-Ni 특화)
exp_df = miner.fetch_cu_ni_references()

# 방법 2: 범용 2원계 합금 (임의의 A-B 조합)
exp_df = miner.fetch_binary_alloy_references("Al", "Cu")

# 방법 3: 문헌 데이터베이스 사용 (API 실패 시 자동 대체)
exp_df = miner.get_manual_cu_ni_references()
exp_df = miner._get_manual_binary_references("Fe", "Co")

# 저장
miner.save_to_csv(exp_df, "experimental_references_AlCu.csv")
```

**Vegard's Law 기반 추정:**
- 합금의 격자 상수: `a_alloy = x·a_A + (1-x)·a_B`
- 합금의 밀도: `ρ_alloy = (x·M_A + (1-x)·M_B) / V_cell`

**데이터 구조:**
```python
{
    "formula": "CuNi",
    "lattice_a": 3.5693,  # Angstrom
    "density": 8.93,      # g/cm³
    "crystal_system": "Fm-3m",
    "data_source": "literature"  # 또는 "Materials Project"
}
```

### 3. 배치 MD 시뮬레이션

여러 구조를 한 번에 묶어서 MD를 효율적으로 실행합니다.

**사용 방법:**

```python
from mattersim_dt.engine import BatchMDSimulator, get_calculator

calculator = get_calculator(device='cuda')
batch_md = BatchMDSimulator(calculator, batch_size=4)

# 여러 구조를 리스트로 전달
atoms_list = [cu_atoms, ni_atoms, cuni_atoms, cu3ni_atoms]

# 배치로 MD 실행
traj_files = batch_md.run_batch(
    atoms_list=atoms_list,
    temperature=1000.0,
    steps=1000,
    time_step=1.0,
    save_interval=50
)

print(f"생성된 trajectory 파일: {traj_files}")
# ['data/results/md_batch_Cu_1000K_0.traj', 'data/results/md_batch_Ni_1000K_1.traj', ...]
```

**장점:**
- GPU 메모리 효율적 활용
- 한 번에 여러 구조 처리 (기본값: 4개)
- 자동 파일명 생성 (중복 방지)

### 4. 다중 온도 MD 테스트

하나의 구조를 여러 온도에서 동시에 테스트합니다.

**사용 방법:**

```python
from mattersim_dt.engine import MDSimulator, get_calculator

calculator = get_calculator(device='cuda')
md_sim = MDSimulator(calculator)

# 다중 온도 테스트
temperatures = [300, 500, 1000, 1500]  # K
results = md_sim.run_multi_temperature(
    atoms=cuni_atoms,
    temperatures=temperatures,
    steps=1000,
    time_step=1.0
)

# 각 온도별 결과 분석
for temp, final_atoms, traj_file in results:
    print(f"{temp}K: {traj_file}")
```

**파일명 패턴:**
```
data/results/md_CuNi_300K.traj
data/results/md_CuNi_500K.traj
data/results/md_CuNi_1000K.traj
data/results/md_CuNi_1500K.traj
```

### 5. Trajectory 파일 이름 규칙

모든 trajectory 파일은 화학식 기반 자동 명명 규칙을 따릅니다:

**구조 이완:**
```
data/results/relax_{formula_reduced}.traj
예: relax_Cu.traj, relax_Ni.traj, relax_Cu3Ni.traj
```

**MD 시뮬레이션:**
```
data/results/md_{formula_reduced}_{temperature}K.traj
예: md_Cu_1000K.traj, md_CuNi_1000K.traj
```

**배치 MD:**
```
data/results/md_batch_{formula}_{temperature}K_{index}.traj
예: md_batch_Cu_1000K_0.traj, md_batch_Cu_1000K_1.traj
```

**슈퍼셀 자동 감지:**
- `Cu64` → `relax_Cu64.traj` (원래 화학식 유지)
- 파일명에서 `/` 같은 특수문자는 `_`로 자동 변환

### 6. NPT Ensemble MD (압력 조절)

기본 MD는 NPT (등온-등압) 앙상블을 사용하여 부피 변화를 허용합니다.

**설정:**
```python
# md.py 내부 (자동 설정됨)
dyn = NPT(
    atoms,
    timestep=1.0 * units.fs,
    temperature_K=1000.0,
    externalstress=0.0,        # 0 GPa (대기압)
    ttime=25.0 * units.fs,     # 온도 조절 시상수
    pfactor=75.0 * units.GPa,  # 압력 조절 계수
    trajectory=None
)
```

**효과:**
- 온도와 압력이 일정하게 유지됨
- 격자 상수가 자유롭게 변할 수 있음
- 실제 실험 조건에 더 가까움

### 7. MD 분석 자동 평형화 처리

MD 궤적 분석 시 초기 평형화 구간을 자동으로 제외합니다.

**동작:**
```python
# md_analyzer.py 내부 (자동 처리됨)
total_frames = len(traj)
equilibration_cutoff = int(0.2 * total_frames)  # 초기 20% 제외
analyzed_traj = traj[equilibration_cutoff:]     # 평형 구간만 분석
```

**열적 안정성 판정 기준:**
```python
is_thermally_stable = (
    temperature_fluctuation < 10.0  # 온도 변동 10% 이내
    and abs(volume_change) < 15.0   # 부피 변화 ±15% 이내
)
```

---

## 🔺 3원소 합금 시뮬레이션 (Ternary Alloy) ⭐ 신규!

### 📌 개요

3원소 합금 기능은 기존 2원소 파이프라인을 확장하여 3개 원소의 조합을 시뮬레이션할 수 있습니다.

**주요 특징:**
- ✅ 균등 분할 방식의 조성 생성 (1:1:1, 2:1:1, 1:2:1 등)
- ✅ 결정구조 우선순위로 base 원소 자동 선택 (FCC > BCC > HCP)
- ✅ 2원소 파이프라인과 독립적으로 실행 (기존 기능 보존)
- ✅ StabilityAnalyzer, MDSimulator 등 기존 분석 도구 재사용

---

### 🔧 설정 방법

[config.py](src/mattersim_dt/core/config.py)에서 다음 설정을 수정하세요:

```python
# 3원소 합금 설정
ENABLE_TERNARY_ALLOY = True  # 3원소 모드 활성화

# Manual 모드용 설정
PIPELINE_MODE = "manual"  # "auto" 또는 "manual"
MANUAL_ELEMENT_A = "Fe"   # 첫 번째 원소
MANUAL_ELEMENT_B = "Cr"   # 두 번째 원소
MANUAL_ELEMENT_C = "Ni"   # 세 번째 원소

# 조성 생성 설정
TERNARY_COMPOSITION_MODE = "generated"  # "generated": 균등분할 생성, "mined": MP에서 실제 비율 추출
TERNARY_COMPOSITION_TOTAL = [3, 4, 5, 6]  # "generated" 모드: 균등 분할 총합 범위
TERNARY_MINING_MAX_RATIOS = None  # "mined" 모드: 최대 비율 개수 (None이면 전체)

# 슈퍼셀 크기 (조합이 많아서 2원소보다 작게 권장)
TERNARY_SUPERCELL_SIZE = 3

# 안정성 임계값
TERNARY_STABILITY_THRESHOLD = 0.05  # eV/atom
```

---

### 📐 조성 생성 방법

3원소 합금 파이프라인은 2가지 조성 생성 방법을 지원합니다:

#### 1️⃣ Generated 모드 (균등 분할)

정수 비율 (a, b, c)의 합이 특정 값(예: 3, 4, 5, 6)이 되도록 조합을 생성합니다.

```python
TERNARY_COMPOSITION_MODE = "generated"
TERNARY_COMPOSITION_TOTAL = [3, 4, 5, 6]
```

**생성되는 조성:**
```
총합 = 3: (1,1,1) → 1개
총합 = 4: (2,1,1), (1,2,1), (1,1,2) → 3개
총합 = 5: (3,1,1), (1,3,1), (1,1,3), (2,2,1), (2,1,2), (1,2,2) → 6개
총합 = 6: (4,1,1), ..., (2,2,2) → 10개

기본 설정 [3,4,5,6]: 총 20개 조성
```

**Fe-Cr-Ni 예시:**

| 비율 튜플 | 조성 | 설명 |
|----------|------|------|
| (1,1,1) | Fe₃₃Cr₃₃Ni₃₄ | 균등 분포 |
| (2,1,1) | Fe₅₀Cr₂₅Ni₂₅ | Fe 50% |
| (1,2,1) | Fe₂₅Cr₅₀Ni₂₅ | Cr 50% |
| (1,1,2) | Fe₂₅Cr₂₅Ni₅₀ | Ni 50% |
| (2,2,2) | Fe₃₃Cr₃₃Ni₃₄ | (1,1,1)과 동일 |

#### 2️⃣ Mined 모드 (Materials Project 마이닝) ⭐ 신규!

Materials Project에서 **실제 연구된 3원소 합금**의 조성 비율을 자동으로 추출합니다.

```python
TERNARY_COMPOSITION_MODE = "mined"
TERNARY_MINING_MAX_RATIOS = None  # 전체 (또는 10 등으로 제한)
```

**장점:**
- ✅ **실제 연구된 조성**: 이미 실험적으로 검증된 비율만 사용
- ✅ **자동 비율 추출**: Pymatgen Composition에서 정수 비율로 자동 변환
- ✅ **안정성 보장**: Materials Project의 안정한 구조만 선택 (energy_above_hull < 0.1 eV)
- ✅ **API 자동 대체**: 마이닝 실패 시 자동으로 균등 분할 모드로 전환

**동작 예시 (Fe-Cr-Ni):**
```
⛏️ [TernaryMiner] Fe-Cr-Ni 3원소 합금 탐색 중...
   🔎 검색된 총 데이터: 47개
   ✅ 발견된 3원소 합금: 12개

======================================================================
📊 3원소 합금 마이닝 결과 요약
======================================================================
Material ID     Formula         Ratio (a:b:c)   E_hull (eV)
----------------------------------------------------------------------
mp-1234         FeCrNi          1:1:1                 0.0023
mp-5678         Fe2CrNi         2:1:1                 0.0156
mp-9101         FeCr2Ni         1:2:1                 0.0089
mp-1121         FeCrNi2         1:1:2                 0.0034
...
======================================================================

중복 제거된 조성 비율: 8개
조성 리스트:
  (1, 1, 1) → Fe 33.3% : Cr 33.3% : Ni 33.3%
  (2, 1, 1) → Fe 50.0% : Cr 25.0% : Ni 25.0%
  (1, 2, 1) → Fe 25.0% : Cr 50.0% : Ni 25.0%
  ...
```

**테스트 방법:**
```bash
# 마이닝 테스트 실행
python test_ternary_mining.py
```

**프로그래밍 방식 사용:**
```python
from mattersim_dt.miner import TernaryMaterialMiner

miner = TernaryMaterialMiner()

# Fe-Cr-Ni 합금 마이닝
results = miner.search_ternary_alloys("Fe", "Cr", "Ni")

# 결과 요약
miner.print_summary(results)

# 중복 제거한 비율 추출
unique_ratios = miner.get_unique_ratios(results)
print(f"발견된 조성: {unique_ratios}")
# [(1, 1, 1), (2, 1, 1), (1, 2, 1), ...]
```

**주의사항:**
- Materials Project API 키 필요
- 모든 3원소 조합에 데이터가 있는 것은 아님
- 마이닝 실패 시 자동으로 균등 분할 모드로 전환됨

---

### 🏗️ Base 원소 선택 로직

**결정구조 우선순위:**

```python
CRYSTAL_PRIORITY = {
    'fcc': 3,  # Face-Centered Cubic (최우선)
    'bcc': 2,  # Body-Centered Cubic
    'hcp': 1   # Hexagonal Close-Packed
}
```

**선택 예시:**

| 시스템 | 결정구조 | Base 원소 | 이유 |
|--------|---------|----------|------|
| Fe-Cr-Ni | BCC, BCC, FCC | **Ni** | FCC 우선순위 가장 높음 |
| Al-Cu-Mg | FCC, FCC, HCP | **Al** | 동점이면 알파벳순 |
| Ti-V-Cr | HCP, BCC, BCC | **V** (또는 Cr) | BCC > HCP, 알파벳순 |

**선택된 base 원소의 격자 구조를 슈퍼셀로 확장한 후, 3원소를 비율에 맞게 치환합니다.**

---

### 🚀 실행 방법

#### 1️⃣ Manual 모드 - Generated (균등 분할)

```bash
# config.py 설정:
ENABLE_TERNARY_ALLOY = True
PIPELINE_MODE = "manual"
MANUAL_ELEMENT_A = "Fe"
MANUAL_ELEMENT_B = "Cr"
MANUAL_ELEMENT_C = "Ni"
TERNARY_COMPOSITION_MODE = "generated"
TERNARY_COMPOSITION_TOTAL = [3, 4]  # 간단히 테스트

# 실행
python run_ternary_pipeline.py
```

#### 1️⃣-B Manual 모드 - Mined (실제 비율 마이닝) ⭐ 신규!

```bash
# config.py 설정:
ENABLE_TERNARY_ALLOY = True
PIPELINE_MODE = "manual"
MANUAL_ELEMENT_A = "Fe"
MANUAL_ELEMENT_B = "Cr"
MANUAL_ELEMENT_C = "Ni"
TERNARY_COMPOSITION_MODE = "mined"  # Materials Project에서 비율 추출
TERNARY_MINING_MAX_RATIOS = 10      # 최대 10개 비율만 사용 (None이면 전체)

# 실행
python run_ternary_pipeline.py
```

**예상 출력:**
```
🎯 Target System: Fe - Cr - Ni

=== [Phase 1-1] 순수 원소 기준 구조 계산 ===
   🔹 Fe 순수 구조 이완 중...
     ✓ 완료: -8.2341 eV/atom
   🔹 Cr 순수 구조 이완 중...
     ✓ 완료: -9.5104 eV/atom
   🔹 Ni 순수 구조 이완 중...
     ✓ 완료: -5.4562 eV/atom

=== [Phase 1-2] 조성별 합금 구조 생성 및 이완 ===
   ℹ️  조성 범위: [3, 4]
   ℹ️  총 조성 개수: 4개
   [1/4] 조성 (1, 1, 1): Fe:Cr:Ni
     ✓ 완료: CrFeNi = -7.3251 eV/atom
   [2/4] 조성 (2, 1, 1): Fe:Cr:Ni
     ✓ 완료: Cr2Fe4Ni2 = -7.8342 eV/atom
   ...

=== [Phase 2] 안정성 분석 및 필터링 ===
   ✅ 안정 구조: 5/7개

=== [Phase 3] MD 시뮬레이션 (안정 구조만) ===
   🔥 CrFeNi MD 시작...
     ✓ MD 완료: data/results/md_CrFeNi_1000K.traj
   ...
```

#### 2️⃣ Auto 모드 (CSV에서 자동 로드)

```bash
# config.py 설정:
ENABLE_TERNARY_ALLOY = True
PIPELINE_MODE = "auto"
MINER_CSV_PATH = "auto_mining_results_final.csv"
MAX_SYSTEMS = 3  # 테스트용으로 3개만

# 실행
python run_ternary_pipeline.py
```

**CSV 파일 요구사항:**
- `formula` 컬럼에 3원소 화학식 포함 (예: "FeCrNi", "AlCuMg")
- Pymatgen Composition으로 파싱 가능해야 함

---

### 📊 파이프라인 흐름도

```
TernaryAlloyMixer(element_A, element_B, element_C)
  ↓
Base 원소 선택 (FCC > BCC > HCP)
  ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 1-1: 순수 원소 기준값 계산 (3개)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
generate_pure_element_structure(Fe) → Relax
generate_pure_element_structure(Cr) → Relax
generate_pure_element_structure(Ni) → Relax
  ↓
StabilityAnalyzer.add_result() × 3
  ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 1-2: 조성별 합금 생성 (20개)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
generate_composition_ratios([3,4,5,6])
  ↓
For each (a, b, c):
  generate_ternary_structure((a,b,c)) → Relax
  StabilityAnalyzer.add_result()
  ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 2: 안정성 필터링
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
StabilityAnalyzer.analyze()
  ↓
Convex Hull 계산 (3원소 Phase Diagram)
  ↓
energy_above_hull < TERNARY_STABILITY_THRESHOLD
  ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 3: MD 시뮬레이션 (안정 구조만)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For each stable structure:
  MDSimulator.run() → Trajectory
  MDAnalyzer.analyze()
  ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
결과 저장
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ternary_stability_{system}_{timestamp}.csv
ternary_details_{system}_{timestamp}.csv
```

---

### 📁 결과 파일

**1. 안정성 분석 결과:**

파일명: `ternary_stability_Fe-Cr-Ni_20251229_123456.csv`

| formula | energy_per_atom | energy_above_hull | is_stable |
|---------|----------------|-------------------|-----------|
| Fe | -8.2341 | 0.0000 | True |
| Cr | -9.5104 | 0.0000 | True |
| Ni | -5.4562 | 0.0000 | True |
| CrFeNi | -7.3251 | 0.0123 | True |
| Cr2Fe4Ni2 | -7.8342 | 0.0891 | False |

**2. 상세 물성 데이터:**

파일명: `ternary_details_Fe-Cr-Ni_20251229_123456.csv`

| system | formula | ratio_tuple | base_element | energy_per_atom | is_stable | md_traj_file |
|--------|---------|-------------|--------------|----------------|-----------|--------------|
| Fe-Cr-Ni | Fe | (1,0,0) | Fe | -8.2341 | True | data/results/md_Fe_1000K.traj |
| Fe-Cr-Ni | CrFeNi | (1,1,1) | Ni | -7.3251 | True | data/results/md_CrFeNi_1000K.traj |

---

### 🧪 테스트 스크립트

**test_ternary_mixer.py**를 실행하여 TernaryAlloyMixer 기능을 검증할 수 있습니다:

```bash
python test_ternary_mixer.py
```

**테스트 내용:**
1. 조성 생성 알고리즘 검증 (20개 조성 생성)
2. Base 원소 선택 검증 (Fe-Cr-Ni → Ni)
3. 3원소 구조 생성 검증 (ASE Atoms 생성)
4. 순수 원소 구조 생성 검증

**예상 출력:**
```
[테스트 1] 조성 생성 알고리즘
조성 범위: [3, 4, 5, 6]
총 조성 개수: 20개
✅ 조성 개수 검증 통과: 20개

[테스트 2] Base 원소 선택
Fe(BCC) - Cr(BCC) - Ni(FCC) → Base: Ni
✅ Fe-Cr-Ni Base 선택 검증 통과: Ni

[테스트 3] 3원소 구조 생성
✅ 구조 생성 검증 통과

✅ 모든 테스트 통과!
```

---

### ⏱️ 계산 시간 예상

**Fe-Cr-Ni 시스템 (TERNARY_COMPOSITION_TOTAL=[3,4,5,6], 슈퍼셀=3):**

| 단계 | 구조 개수 | 예상 시간 (GPU) |
|------|----------|----------------|
| 순수 원소 (Phase 1-1) | 3개 | ~6분 (각 2분) |
| 조성별 합금 (Phase 1-2) | 20개 | ~40분 (각 2분) |
| **Phase 1 총계** | **23개** | **~46분** |
| 안정 구조 (예상 ~10개) | 10개 | - |
| MD 시뮬레이션 (Phase 3) | 10개 | ~50분 (각 5분) |
| **전체 파이프라인** | - | **~1.5-2시간** |

**계산 시간 단축 방법:**
- `TERNARY_COMPOSITION_TOTAL = [3, 4]`: 4개 조성만 테스트 → ~20분
- `MD_STEPS = 1000`: MD 스텝 감소 → MD 시간 1/5 단축
- `TERNARY_SUPERCELL_SIZE = 2`: 슈퍼셀 감소 → 이완 시간 단축 (정확도↓)

---

### ⚠️ 주의사항

#### 1. 결정구조 우선순위
- FCC > BCC > HCP로 고정됨
- 동점일 경우 알파벳순으로 결정
- 필요시 코드 수정으로 수동 지정 가능

#### 2. 조성 개수
- `TERNARY_COMPOSITION_TOTAL = [3,4,5,6]`: 20개 조성
- 슈퍼셀 크기 3 기준: 각 구조당 ~100원자 (4³ × 4 × 조성비)
- **계산량**: 2원소 대비 약 2-3배

#### 3. 실험 데이터 부족
- 3원소 합금 실험 데이터는 매우 제한적
- Materials Project에도 데이터가 적음
- **사용자 정의 CSV 권장** (CUSTOM_EXP_DATA_CSV 설정)

#### 4. Convex Hull 계산
- StabilityAnalyzer는 n-원소 자동 지원
- 3원소 Phase Diagram 사용
- 4개 이상 원소는 Convex Hull 계산 복잡도 증가

---

### 💡 향후 확장 가능성

#### 1. SQS (Special Quasirandom Structures)
- **현재**: 완전 무작위 치환
- **개선**: SQS 알고리즘으로 통계적으로 최적화된 구조 생성
- **장점**: 실제 무작위 합금과 더 유사한 단거리 질서 구현

#### 2. 4원소 이상 (Quaternary Alloy)
- 현재 설계를 n-원소로 일반화
- 조성 생성 알고리즘 확장 필요
- Convex Hull 계산 복잡도 증가

#### 3. Cluster Expansion
- 3원소 상호작용 에너지 고려
- Vegard's Law 대신 더 정확한 예측
- 기계학습 기반 에너지 예측

---

### 📚 참고 자료

**관련 파일:**
- [ternary_mixer.py](src/mattersim_dt/builder/ternary_mixer.py) - TernaryAlloyMixer 클래스
- [mp_api.py](src/mattersim_dt/miner/mp_api.py) - TernaryMaterialMiner 클래스 (마이닝 엔진)
- [run_ternary_pipeline.py](run_ternary_pipeline.py) - 3원소 파이프라인 실행 스크립트
- [test_ternary_mixer.py](test_ternary_mixer.py) - 구조 생성 테스트 스크립트
- [test_ternary_mining.py](test_ternary_mining.py) - 마이닝 기능 테스트 스크립트
- [config.py](src/mattersim_dt/core/config.py) - 설정 파일 (라인 65-85)

**학술 참고 문헌:**
1. **Vegard's Law**: Vegard, L. (1921). "Die Konstitution der Mischkristalle"
2. **Convex Hull**: Pymatgen documentation - Phase Diagram analysis
3. **SQS**: Zunger et al. (1990). "Special quasirandom structures"

---

**Happy Material Discovery! 🔬✨**
