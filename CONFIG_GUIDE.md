# ⚙️ Config 설정 가이드

## 📍 파일 위치
`src/mattersim_dt/core/config.py`

---

## 🎯 주요 설정 항목

### 1. 파이프라인 모드 설정

```python
PIPELINE_MODE = "auto"  # "auto" 또는 "manual"
```

| 모드 | 설명 | 사용 예시 |
|------|------|-----------|
| `"auto"` | CSV 파일에서 원소 조합 자동 로드 | 대량 실험 |
| `"manual"` | 수동으로 원소 지정 | 특정 조합만 테스트 |

---

### 2. AUTO 모드 설정

```python
MINER_CSV_PATH = "auto_mining_results_final.csv"  # CSV 파일 경로
MAX_SYSTEMS = 5  # 실험할 최대 시스템 수
```

**MAX_SYSTEMS 옵션:**
- `5` → 상위 5개 시스템만 실험
- `10` → 상위 10개
- `None` → CSV의 모든 조합 실험 (매우 오래 걸림!)

---

### 3. MANUAL 모드 설정

```python
MANUAL_ELEMENT_A = "Cu"  # 첫 번째 원소
MANUAL_ELEMENT_B = "Ni"  # 두 번째 원소
```

**PIPELINE_MODE가 "manual"일 때만 사용됩니다.**

---

### 4. 혼합 비율 설정 ⭐ NEW!

```python
MIXING_RATIO_STEP = 0.1  # 비율 간격
```

**이제 간격만 지정하면 자동으로 비율 리스트가 생성됩니다!**

| STEP | 생성되는 비율 | 개수 |
|------|--------------|------|
| `0.05` | 0.05, 0.1, 0.15, ..., 0.9, 0.95 | 19개 |
| `0.1` | 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9 | 9개 |
| `0.2` | 0.2, 0.4, 0.6, 0.8 | 4개 |
| `0.25` | 0.25, 0.5, 0.75 | 3개 |
| `0.33` | 0.33, 0.66, 0.99 | 3개 |

**주의:**
- 0.0과 1.0은 자동으로 제외됩니다 (순수 원소는 별도 계산)
- step이 작을수록 실험 시간이 증가합니다

**예시:**

```python
# 빠른 테스트 (4개 비율만)
MIXING_RATIO_STEP = 0.2

# 기본 (9개 비율)
MIXING_RATIO_STEP = 0.1

# 세밀한 탐색 (19개 비율)
MIXING_RATIO_STEP = 0.05
```

---

### 5. 슈퍼셀 크기

```python
SUPERCELL_SIZE = 3  # 3x3x3 = 27배
```

| 크기 | 원자 개수 (대략) | 계산 시간 | 정확도 |
|------|-----------------|----------|--------|
| `2` | ~32개 | 빠름 ⚡ | 낮음 |
| `3` | ~108개 | 보통 ⏱️ | 적당 ✅ |
| `4` | ~256개 | 느림 🐌 | 높음 |

**주의:** 크기가 클수록 메모리 사용량과 계산 시간이 급증합니다!

---

### 6. MD 시뮬레이션 설정

```python
MD_TEMPERATURE = 1000.0  # 온도 (K)
MD_STEPS = 1000          # 스텝 수
MD_TIMESTEP = 1.0        # 시간 간격 (fs)
```

**온도 선택 가이드:**

| 온도 | 용도 |
|------|------|
| 300K | 실온 특성 확인 |
| 500-800K | 중온 특성 |
| 1000K+ | 고온 안정성 테스트 ✅ 기본값 |

---

### 7. 안정성 필터링 기준

```python
STABILITY_THRESHOLD = 0.05  # eV/atom
```

Energy above hull이 이 값 이하면 "안정"으로 판정됩니다.

- `0.01` → 매우 엄격 (거의 통과 못함)
- `0.05` → 적당 ✅ 기본값
- `0.1` → 관대함

---

## 📊 설정 조합 예시

### 예시 1: 빠른 테스트

```python
PIPELINE_MODE = "manual"
MANUAL_ELEMENT_A = "Cu"
MANUAL_ELEMENT_B = "Ni"
MIXING_RATIO_STEP = 0.2  # 4개 비율만
SUPERCELL_SIZE = 2
MD_TEMPERATURE = 300.0
```

**예상 시간:** ~5분

---

### 예시 2: 표준 실험 (권장)

```python
PIPELINE_MODE = "auto"
MAX_SYSTEMS = 5
MIXING_RATIO_STEP = 0.1  # 9개 비율
SUPERCELL_SIZE = 3
MD_TEMPERATURE = 1000.0
```

**예상 시간:** ~30-50분

---

### 예시 3: 정밀 탐색

```python
PIPELINE_MODE = "auto"
MAX_SYSTEMS = 10
MIXING_RATIO_STEP = 0.05  # 19개 비율
SUPERCELL_SIZE = 4
MD_TEMPERATURE = 1000.0
```

**예상 시간:** 몇 시간 이상

---

### 예시 4: 전체 데이터셋

```python
PIPELINE_MODE = "auto"
MAX_SYSTEMS = None  # 전체!
MIXING_RATIO_STEP = 0.1
SUPERCELL_SIZE = 3
MD_TEMPERATURE = 1000.0
```

**예상 시간:** 하루 이상 (수백 개 시스템)

---

## 🎮 설정 변경 후 실행

1. `config.py` 파일 열기
2. 원하는 값으로 수정
3. 파일 저장
4. 파이프라인 실행:

```bash
python run_pipeline.py
```

---

## 💡 팁

### 처음 사용할 때

```python
PIPELINE_MODE = "manual"
MANUAL_ELEMENT_A = "Cu"
MANUAL_ELEMENT_B = "Ni"
MAX_SYSTEMS = 1
MIXING_RATIO_STEP = 0.2  # 빠르게!
SUPERCELL_SIZE = 2
```

→ 빠르게 테스트해보고 시스템이 정상 작동하는지 확인

### 제대로 실험할 때

```python
PIPELINE_MODE = "auto"
MAX_SYSTEMS = 5
MIXING_RATIO_STEP = 0.1
SUPERCELL_SIZE = 3
```

→ 적당한 시간에 의미 있는 결과 획득

### 논문용 데이터

```python
PIPELINE_MODE = "auto"
MAX_SYSTEMS = None
MIXING_RATIO_STEP = 0.05
SUPERCELL_SIZE = 4
```

→ 최대한 정밀하게 (시간 충분히 확보)

---

## ⚠️ 주의사항

1. **MIXING_RATIO_STEP이 작을수록 시간 증가**
   - 0.05 = 19개 비율 → 0.1의 2배 시간

2. **SUPERCELL_SIZE가 클수록 메모리 증가**
   - 크기 4 = 크기 3의 약 2.5배 메모리

3. **MAX_SYSTEMS = None은 신중하게**
   - CSV에 200개 조합이 있으면 200번 실험!

4. **GPU 메모리 부족 시**
   - SUPERCELL_SIZE를 2로 줄이기
   - MIXING_RATIO_STEP을 0.2로 늘리기 (비율 개수 감소)

---

**설정에 대한 질문이 있으면 언제든지 물어보세요!** 🚀
