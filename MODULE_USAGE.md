# 📦 MatterSim 모듈 사용 가이드

## 🎯 src 폴더 구조

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
│   ├── __init__.py          # get_calculator, StructureRelaxer, MDSimulator, BatchStructureRelaxer 노출
│   ├── calculator.py        # MatterSim Calculator
│   ├── relax.py             # 구조 이완 (화학식 기반 trajectory 저장)
│   ├── md.py                # 분자동역학 시뮬레이션 (화학식 기반 trajectory 저장)
│   └── batch_relax.py       # 배치 구조 이완 (병렬 처리)
│
├── analysis/
│   ├── __init__.py          # StabilityAnalyzer, MDAnalyzer 노출
│   ├── stability.py         # 열역학적 안정성 분석
│   └── md_analyzer.py       # MD Trajectory 분석
│
└── miner/
    ├── __init__.py          # MaterialMiner 노출
    └── mp_api.py            # Materials Project API
```

---

## ✅ run_pipeline.py에서 사용하는 모듈

### 1. SimConfig (설정 관리)

**임포트:**
```python
from mattersim_dt.core import SimConfig
```

**사용:**
```python
# 설정 초기화
SimConfig.setup()

# 설정 값 읽기
device = SimConfig.DEVICE
csv_path = SimConfig.MINER_CSV_PATH
max_systems = SimConfig.MAX_SYSTEMS
ratio_step = SimConfig.MIXING_RATIO_STEP
supercell_size = SimConfig.SUPERCELL_SIZE
threshold = SimConfig.STABILITY_THRESHOLD
temperature = SimConfig.MD_TEMPERATURE

# Trajectory 저장 설정 (NEW!)
save_relax_traj = SimConfig.SAVE_RELAX_TRAJ  # 구조 이완 trajectory 저장 여부
save_md_traj = SimConfig.SAVE_MD_TRAJ        # MD trajectory 저장 여부

# 비율 리스트 자동 생성
mixing_ratios = SimConfig.get_mixing_ratios()
```

**새로운 설정 옵션:**
```python
# config.py에서 설정
SAVE_RELAX_TRAJ = True   # 구조 이완 과정 trajectory 저장 여부
SAVE_MD_TRAJ = True      # MD 시뮬레이션 trajectory 저장 여부 (항상 True 권장)
```

---

### 2. RandomAlloyMixer (구조 생성)

**임포트:**
```python
from mattersim_dt.builder import RandomAlloyMixer
```

**사용:**
```python
# 1. 순수 원소 구조 생성
mixer = RandomAlloyMixer('Cu')  # 자동으로 격자 상수 선택
atoms = mixer.base_atoms

# 2. 합금 구조 생성
alloy = mixer.generate_structure(
    dopant_element='Ni',
    ratio=0.3,  # 30% Ni
    supercell_size=3
)
```

**특징:**
- 35개 주요 금속 원소의 격자 상수 내장
- 자동으로 적절한 결정 구조 선택 (fcc/bcc/hcp)
- 실패 시 자동 대체 (fcc, a=4.0)

---

### 3. get_calculator (MatterSim Calculator)

**임포트:**
```python
from mattersim_dt.engine import get_calculator
```

**사용:**
```python
# Calculator 생성
calc = get_calculator(device='cuda')  # 또는 'cpu'

# Atoms에 Calculator 할당
atoms.calc = calc
```

---

### 4. StructureRelaxer (구조 이완)

**임포트:**
```python
from mattersim_dt.engine import StructureRelaxer
```

**사용:**
```python
# Relaxer 생성
relaxer = StructureRelaxer(calculator=calc)

# 구조 이완 실행
relaxed_atoms, total_energy = relaxer.run(
    atoms,
    save_traj=SimConfig.SAVE_RELAX_TRAJ  # 설정에 따라 trajectory 저장
)
```

**반환값:**
- `relaxed_atoms`: 이완된 ASE Atoms 객체
- `total_energy`: 총 에너지 (eV)

**Trajectory 저장 (NEW!):**
- `save_traj=True`로 설정하면 `data/results/relax_{화학식}.traj` 파일 생성
- 예: `relax_AlCu.traj`, `relax_Mg49Pd5.traj`
- 화학식은 자동으로 추출되어 파일명에 포함됨
- 각 조합마다 고유한 파일이 생성되어 덮어쓰기 방지

---

### 5. MDSimulator (분자동역학)

**임포트:**
```python
from mattersim_dt.engine import MDSimulator
```

**사용:**
```python
# MDSimulator 생성
md_sim = MDSimulator(calculator=calc)

# 단일 온도 MD 실행
final_atoms, traj_file = md_sim.run(
    atoms,
    temperature=1000.0,  # K
    steps=1000,
    save_interval=50  # 50 step마다 저장
)

# 다중 온도 MD 실행 (NEW!)
md_results = md_sim.run_multi_temperature(
    atoms,
    temperatures=[300, 500, 1000, 1500],  # 여러 온도 조건
    steps=1000,
    save_interval=50
)
# 반환값: [(temp, final_atoms, traj_file), ...]
```

**기능:**
- 지정 온도에서 MD 시뮬레이션
- **Trajectory 자동 저장 (각 조합마다 고유 파일)**
- 에너지, 온도 등 통계 출력

**Trajectory 파일명 (NEW!):**
- **이전**: `md_1000K.traj` (마지막 조합만 저장, 덮어쓰기)
- **현재**: `md_{화학식}_{온도}K.traj` (각 조합마다 고유 파일)
- 예시:
  - `md_Al_1000K.traj` (순수 알루미늄)
  - `md_AlCu_1000K.traj` (알루미늄-구리 합금)
  - `md_Mg49Pd5_1000K.traj` (마그네슘-팔라듐 합금)
  - `md_AlCu_300K.traj`, `md_AlCu_500K.traj` (다중 온도)

---

### 6. StabilityAnalyzer (안정성 분석)

**임포트:**
```python
from mattersim_dt.analysis import StabilityAnalyzer
```

**사용:**
```python
# Analyzer 생성 (자동으로 config.py의 STABILITY_THRESHOLD 사용)
analyzer = StabilityAnalyzer()

# 결과 등록
analyzer.add_result(atoms, total_energy)

# Convex Hull 분석 및 안정성 판정
results = analyzer.analyze()

# 결과 확인
for res in results:
    formula = res['formula']
    e_hull = res['energy_above_hull']
    is_stable = res['is_stable']
```

**반환값 (analyze()):**
```python
[
    {
        "formula": "Cu",
        "energy_above_hull": 0.000000,
        "is_stable": True
    },
    {
        "formula": "Cu3Ni",
        "energy_above_hull": 0.012345,
        "is_stable": True
    },
    ...
]
```

---

### 7. BatchStructureRelaxer (배치 구조 이완)

**임포트:**
```python
from mattersim_dt.engine import BatchStructureRelaxer
```

**사용:**
```python
# BatchRelaxer 생성
batch_relaxer = BatchStructureRelaxer(
    calculator=calc,
    batch_size=4  # 한 번에 처리할 구조 개수
)

# 여러 구조를 배치로 이완
atoms_list = [atoms1, atoms2, atoms3, ...]  # 여러 구조
batch_results = batch_relaxer.run_batch(
    atoms_list,
    save_traj=SimConfig.SAVE_RELAX_TRAJ
)

# 결과 처리
for relaxed_atoms, total_energy in batch_results:
    if total_energy != float('inf'):
        # 성공한 구조만 처리
        print(f"에너지: {total_energy} eV")
```

**특징:**
- 여러 구조를 효율적으로 병렬 처리
- GPU 메모리를 최대한 활용
- 각 구조마다 고유한 trajectory 파일 저장
- 실패한 구조는 `float('inf')` 에너지로 반환

---

### 8. MDAnalyzer (MD 결과 분석)

**임포트:**
```python
from mattersim_dt.analysis import MDAnalyzer
```

**사용:**
```python
# Analyzer 생성
md_analyzer = MDAnalyzer(traj_file="data/results/md_AlCu_1000K.traj")

# 분석 수행
results = md_analyzer.analyze()

# 결과 출력
md_analyzer.print_summary(results)
```

**분석 항목:**
- 평균 온도 및 온도 변동률
- 평균 에너지 (원자당)
- 부피 변화율
- 열적 안정성 판정

**반환값:**
```python
{
    "avg_temperature": 1005.3,           # 평균 온도 (K)
    "temperature_fluctuation_percent": 2.1,  # 온도 변동률 (%)
    "avg_energy_per_atom": -3.456,       # 평균 에너지 (eV/atom)
    "volume_change_percent": 1.2,        # 부피 변화율 (%)
    "is_thermally_stable": True,         # 열적 안정성
    "trajectory_frames": 100             # 총 프레임 수
}
```

---

## 🔄 전체 파이프라인 흐름

### Phase 1: Mix + Relax

```python
# 1. 구조 생성
mixer = RandomAlloyMixer('Cu')
atoms = mixer.generate_structure('Ni', ratio=0.3, supercell_size=3)

# 2. Calculator 할당
atoms.calc = calc

# 3. 구조 이완 (trajectory 저장)
relaxed, energy = relaxer.run(atoms, save_traj=SimConfig.SAVE_RELAX_TRAJ)
# → data/results/relax_Cu3Ni.traj 생성 (save_traj=True일 때)

# 4. 분석기에 등록
analyzer.add_result(relaxed, energy)
```

**병렬 처리 방식 (여러 비율 동시 계산):**
```python
# 여러 비율의 구조 생성
atoms_list = []
for ratio in [0.1, 0.2, 0.3, 0.4, 0.5]:
    atoms = mixer.generate_structure('Ni', ratio=ratio, supercell_size=3)
    atoms_list.append(atoms)

# 배치 이완 (병렬 처리)
batch_relaxer = BatchStructureRelaxer(calc, batch_size=4)
batch_results = batch_relaxer.run_batch(atoms_list, save_traj=SimConfig.SAVE_RELAX_TRAJ)

# 결과 등록
for relaxed_atoms, energy in batch_results:
    if energy != float('inf'):
        analyzer.add_result(relaxed_atoms, energy)
```

### Phase 2: Stability Filter

```python
# Convex Hull 분석
results = analyzer.analyze()

# 안정한 구조만 필터링
stable_formulas = [
    res['formula'] for res in results if res['is_stable']
]
```

### Phase 3: MD Simulation

```python
# 안정한 구조만 MD 실행
for formula in stable_formulas:
    atoms = relaxed_structures[formula]

    # MD 실행 (trajectory 자동 저장)
    final_atoms, traj_file = md_sim.run(
        atoms,
        temperature=1000.0,
        steps=1000,
        save_interval=50
    )
    # → data/results/md_{formula}_1000K.traj 생성

    # MD 결과 분석
    md_analyzer = MDAnalyzer(traj_file)
    md_results = md_analyzer.analyze()
    md_analyzer.print_summary(md_results)
```

**다중 온도 MD:**
```python
# 여러 온도에서 동시 테스트
for formula in stable_formulas:
    atoms = relaxed_structures[formula]

    # 다중 온도 MD
    md_results_list = md_sim.run_multi_temperature(
        atoms,
        temperatures=[300, 500, 1000, 1500],
        steps=1000
    )
    # → md_{formula}_300K.traj, md_{formula}_500K.traj, ... 생성

    # 각 온도별 분석
    for temp, final_atoms, traj_file in md_results_list:
        md_analyzer = MDAnalyzer(traj_file)
        results = md_analyzer.analyze()
        print(f"{temp}K: 안정성 = {results['is_thermally_stable']}")
```

---

## 📚 모듈별 의존성

```
SimConfig (config.py)
    ↓
get_calculator (calculator.py)
    ↓
StructureRelaxer (relax.py)
MDSimulator (md.py)
RandomAlloyMixer (mixer.py)
StabilityAnalyzer (stability.py) ← SimConfig.STABILITY_THRESHOLD
```

---

## 🎓 주요 개선사항 (이전 vs 현재)

### ❌ 이전 (잘못된 방식)

```python
# 모듈을 임포트만 하고 사용 안 함
from mattersim_dt.builder import RandomAlloyMixer
from mattersim_dt.engine import get_calculator, StructureRelaxer, MDSimulator

# 실제로는 다른 방식으로 구현
# (MPRester, AseAtomsAdaptor 등을 직접 사용)
```

### ✅ 현재 (올바른 방식)

```python
# src 모듈을 제대로 활용
from mattersim_dt.core import SimConfig
from mattersim_dt.builder import RandomAlloyMixer
from mattersim_dt.engine import get_calculator, StructureRelaxer, MDSimulator
from mattersim_dt.analysis import StabilityAnalyzer

# 모든 기능을 모듈을 통해 사용
calc = get_calculator(device=SimConfig.DEVICE)
relaxer = StructureRelaxer(calculator=calc)
md_sim = MDSimulator(calculator=calc)
analyzer = StabilityAnalyzer()
mixer = RandomAlloyMixer(element)
```

---

## 💡 핵심 포인트

1. **모든 설정은 SimConfig에서**
   - 직접 하드코딩하지 않고 `SimConfig.XXX` 사용

2. **Calculator는 한 번만 생성**
   - `get_calculator()` 한 번 호출 후 재사용

3. **모듈 인터페이스 활용**
   - `__init__.py`에 노출된 클래스/함수만 사용
   - 내부 구현은 신경 쓰지 않음

4. **에러 처리는 모듈이 담당**
   - try-except는 최소한으로
   - 모듈 자체에 에러 처리 내장

---

## 🚀 실행 방법

```bash
# 모듈이 제대로 임포트되는지 확인
python -c "from mattersim_dt.core import SimConfig; print(SimConfig.DEVICE)"

# 파이프라인 실행
python run_pipeline.py
```

---

**이제 src 모듈을 제대로 활용하는 깔끔한 파이프라인이 완성되었습니다!** 🎉
