import os
import torch

class SimConfig:
    """
    프로젝트 전체의 설정을 관리하는 컨트롤 타워
    """
    # ==========================================
    # [중요] API Key 중앙 관리
    # ==========================================
    # 여기에 본인의 키를 붙여넣으세요.
    # (환경 변수에 설정되어 있다면 그걸 우선 사용하고, 없으면 아래 문자열을 사용합니다)
    MP_API_KEY = os.environ.get("MP_API_KEY") or "5DPnayEkpta3vy5RiF6wNa2Am0O28x9s"

    # ==========================================
    # 시스템 설정
    # ==========================================
    DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
    SAVE_DIR = "data/final_results"
    
    # Miner (광부) 설정
    MINER_CSV_PATH = "auto_mining_results_final.csv"

    # Pipeline 설정
    PIPELINE_MODE = "manual"  # "auto": CSV에서 자동 로드, "manual": 수동으로 원소 지정
    MANUAL_ELEMENT_A = "Cu"  # PIPELINE_MODE="manual"일 때만 사용
    MANUAL_ELEMENT_B = "Ni"  # PIPELINE_MODE="manual"일 때만 사용
    MAX_SYSTEMS = None  # "auto" 모드에서 실험할 최대 시스템 수 (None이면 전체)

    # MD (가열 실험) 설정
    MD_TEMPERATURE = 1000.0  # 온도 (K)
    MD_STEPS = 5000         # 스텝 수
    MD_TIMESTEP = 1.0        # 시간 간격 (fs)

    # Trajectory 저장 설정
    SAVE_RELAX_TRAJ = True   # 구조 이완 과정 trajectory 저장 여부
    SAVE_MD_TRAJ = True      # MD 시뮬레이션 trajectory 저장 여부 (항상 True 권장)

    # 필터링 기준
    STABILITY_THRESHOLD = 0.05

    # 구조 생성 설정
    MIXING_RATIO_STEP = 0.1  # 혼합 비율 간격 (0.1 = 10%씩, 0.05 = 5%씩)
    SUPERCELL_SIZE = 4  # 슈퍼셀 크기

    # ==========================================
    # 병렬처리 설정
    # ==========================================
    # 1. 비율별 병렬 계산 (같은 시스템 내에서 여러 비율을 동시에 계산)
    #    단일 GPU에서도 효율적으로 작동 (배치 처리)
    PARALLEL_RATIO_CALCULATION = True  # True: 비율별 병렬, False: 순차 처리
    RATIO_BATCH_SIZE = 4  # 한 번에 계산할 비율 개수 (GPU 메모리에 따라 조절)

    # 2. 시스템별 병렬 계산 (여러 원소 조합을 동시에 계산)
    #    다중 GPU 환경에서 권장 (각 GPU에 다른 시스템 할당)
    PARALLEL_SYSTEM_CALCULATION = True  # True: 시스템별 병렬, False: 순차 처리
    NUM_GPUS = 1  # 사용 가능한 GPU 개수 (서버: 2~4, 개인PC: 1)

    # 3. MD 병렬 계산 (여러 온도 조건을 동시에 테스트)
    PARALLEL_MD_TEMPERATURES = False# True: 다중 온도 병렬, False: 단일 온도만
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