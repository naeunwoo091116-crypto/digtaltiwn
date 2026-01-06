import os
import torch

class SimConfig:
    """
    프로젝트 전체의 설정을 관리하는 컨트롤 타워
    """
    # ==========================================
    # [중요] API Key 중앙 관리
    # ==========================================
    MP_API_KEY = os.environ.get("MP_API_KEY")
    DB_URL = os.environ.get("DB_URL", "postgresql://mattersim:mattersim_password@localhost:5432/mattersim_dt")

    # .env 파일 로드 시도
    try:
        from dotenv import load_dotenv
        load_dotenv()
        if not MP_API_KEY:
            MP_API_KEY = os.environ.get("MP_API_KEY")
    except ImportError:
        pass
        
    if not MP_API_KEY:
         # Fallback for user who might not have set env yet (Optional: remove this if strict security is needed)
         # Leaving empty to enforce env var usage or handled by validation later
         MP_API_KEY = ""

    # ==========================================
    # 시스템 설정
    # ==========================================
    DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
    SAVE_DIR = "data/final_results"
    
    # Miner (광부) 설정
    MINER_CSV_PATH = "auto_mining_results_final.csv"

    # Pipeline 설정
    # Pipeline 설정
    PIPELINE_MODE = "auto"  # "auto": CSV에서 자동 로드, "manual": 수동으로 원소 지정
    MANUAL_ELEMENT_A = "Fe"  # PIPELINE_MODE="manual"일 때만 사용 (예: "Cu", "Al", "Fe" 등)
    MANUAL_ELEMENT_B = "Cr"  # PIPELINE_MODE="manual"일 때만 사용 (예: "Ni", "Mg", "Cr" 등)
    MAX_SYSTEMS = None  # "auto" 모드에서 실험할 최대 시스템 수 (None이면 전체)

    # ⚠️ 중요: Windows에서는 아래 병렬 옵션을 모두 False로 설정하는 것을 권장합니다
    # GPU 메모리 경합과 multiprocessing 충돌로 시스템이 멈출 수 있습니다

    # Resume 설정 (이어하기 기능)
    RESUME_MODE = True  # True: 기존 결과 있으면 건너뛰기, False: 항상 새로 계산
    RESUME_CSV_PATH = "pipeline_results_20251229_132400.csv"  # 특정 CSV 지정 (None이면 최신 파일 자동 찾기)

    # MD (가열 실험) 설정
    MD_TEMPERATURE = 1000.0  # 온도 (K)
    MD_STEPS = 1000        # 스텝 수 (권장: 테스트 1000, 실제 5000-10000)
    MD_TIMESTEP = 1.0        # 시간 간격 (fs)

    # Trajectory 저장 설정
    SAVE_RELAX_TRAJ = False   # 구조 이완 과정 trajectory 저장 여부
    SAVE_MD_TRAJ = False      # MD 시뮬레이션 trajectory 저장 여부 (항상 True 권장)

    # 필터링 기준
    STABILITY_THRESHOLD = 0.05

    # 검증 및 채점 설정
    ENABLE_VALIDATION = False  # True: 실험 데이터 비교 및 채점 수행, False: 건너뛰기
    VALIDATION_SAVE_EXP_DATA = False  # True: 실험 데이터 CSV 저장, False: 저장 안 함
    VALIDATION_SAVE_REPORT = False  # True: 채점 리포트 CSV 저장, False: 저장 안 함

    # 실험 데이터 소스 설정
    VALIDATION_DATA_SOURCE = "materials_project"  # "materials_project": MP API 사용, "literature": 문헌 데이터만 사용, "auto": MP 시도 후 실패 시 문헌
    VALIDATION_USE_THEORETICAL = False  # Materials Project에서 theoretical 데이터 포함 여부 (False: 실험 데이터만)

    # 사용자 정의 실험 데이터 (선택사항)
    CUSTOM_EXP_DATA_CSV = None  # CSV 파일 경로 지정 시 해당 파일의 실험 데이터 사용 (None이면 기본 소스 사용)

    # 구조 생성 설정
    MIXING_RATIO_STEP = 0.1  # 혼합 비율 간격 (0.1 = 10%씩, 0.05 = 5%씩)
    SUPERCELL_SIZE = 4  # 슈퍼셀 크기

    # 2원소 조성 모드 설정
    BINARY_COMPOSITION_MODE = "generated"  # "generated": MIXING_RATIO_STEP 사용, "mined": Materials Project에서 실제 비율 추출
    BINARY_MINING_MAX_RATIOS = None  # "mined" 모드에서 사용할 최대 비율 개수 (None이면 전체)

    # ==========================================
    # 3원소 합금 설정 (Ternary Alloy)
    # ==========================================
    ENABLE_TERNARY_ALLOY = True  # True: 3원소 모드 활성화, False: 2원소 모드만 사용

    # Manual 모드용 설정
    MANUAL_ELEMENT_C = "Ni"  # 세 번째 원소 (PIPELINE_MODE="manual"일 때만 사용)

    # 조성 생성 설정
    TERNARY_COMPOSITION_TOTAL = [3, 4, 5, 6]  # 균등 분할 총합 범위
    # 예: [3,4,5,6]이면 (1,1,1), (2,1,1), (1,2,1), ... 등 총 20개 조합 생성

    # 3원소 전용 슈퍼셀 크기 (조합이 많아서 2원소보다 작게 설정)
    TERNARY_SUPERCELL_SIZE = 3  # 기본값: 3 (2원소는 4)

    # 3원소 안정성 임계값
    TERNARY_STABILITY_THRESHOLD = 0.05  # eV/atom (energy_above_hull 기준)

    # 3원소 조성 모드 설정
    TERNARY_COMPOSITION_MODE = "generated"  # "generated": 균등분할로 생성, "mined": Materials Project에서 실제 비율 추출
    TERNARY_MINING_MAX_RATIOS = None  # "mined" 모드에서 사용할 최대 비율 개수 (None이면 전체)

    # ==========================================
    # 병렬처리 설정
    # ==========================================
    # 1. 비율별 병렬 계산 (같은 시스템 내에서 여러 비율을 동시에 계산)
    #    단일 GPU에서도 효율적으로 작동 (배치 처리)
    PARALLEL_RATIO_CALCULATION = True  # True: 비율별 병렬, False: 순차 처리
    RATIO_BATCH_SIZE = 4  # 한 번에 계산할 비율 개수 (GPU 메모리에 따라 조절)

    # 2. 시스템별 병렬 계산 (여러 원소 조합을 동시에 계산)
    #    ⚠️ Windows + GPU 환경에서는 False 권장 (메모리 충돌 위험)
    PARALLEL_SYSTEM_CALCULATION = False  # True: 시스템별 병렬, False: 순차 처리
    NUM_GPUS = 1  # 사용 가능한 GPU 개수 (서버: 2~4, 개인PC: 1)

    # 3. MD 병렬 실행 (같은 온도에서 여러 구조를 동시에 계산)
    #    ⚠️ Windows 사용자: False 권장 (메모리 경합 및 프로세스 폭발 위험)
    #    ✅ Linux/서버 사용자: True 권장 (큰 성능 향상, 특히 다중 GPU 환경)
    PARALLEL_MD_EXECUTION = False  # True: 병렬 MD, False: 순차 MD
    MD_NUM_PROCESSES = 2  # 병렬 실행 시 프로세스 수 (GPU 메모리에 따라 조절: 2-4 권장)

    # 4. MD 다중 온도 테스트 (미래 기능, 현재 미사용)
    PARALLEL_MD_TEMPERATURES = False  # True: 다중 온도 병렬, False: 단일 온도만
    MD_TEMPERATURE_RANGE = [300, 500, 1000, 1500]  # 테스트할 온도 리스트 (K)

    # 자동 생성된 비율 리스트 (0.0과 1.0 제외, 순수 원소는 별도 계산)
    @staticmethod
    def get_mixing_ratios():
        """MIXING_RATIO_STEP을 기반으로 비율 리스트 자동 생성"""
        import numpy as np
        step = SimConfig.MIXING_RATIO_STEP
        # 0.0 제외, 1.0 제외 (순수 원소는 별도로 계산)
        ratios = np.arange(step, 1.0, step)
        return [round(r, 10) for r in ratios]  # 부동소수점 오차 제거

    @staticmethod
    def setup():
        """결과 저장 폴더 생성"""
        os.makedirs(SimConfig.SAVE_DIR, exist_ok=True)
        
        # API 키가 제대로 설정되었는지 체크하는 안전장치
        if "여기에" in SimConfig.MP_API_KEY:
            print("⚠️ [Warning] core/config.py에 API Key가 설정되지 않았습니다!")