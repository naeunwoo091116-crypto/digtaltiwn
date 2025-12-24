import torch
from ase.calculators.calculator import Calculator

class MatterSimLoader:
    """
    MatterSim 모델을 로드하여 ASE Calculator로 반환하는 클래스
    """
    def __init__(self, model_path: str = None, device: str = "cuda"):
        self.device = device if torch.cuda.is_available() else "cpu"
        self.model_path = model_path
        print(f"✅ Engine setting: Using device '{self.device}'")

    def load(self) -> Calculator:
        """
        실제 MatterSim 모델을 로드하는 함수
        """
        try:
            # [중요] 실제 MatterSim 라이브러리 import
            # (설치된 라이브러리 이름에 따라 수정이 필요할 수 있습니다)
            from mattersim.forcefield import MatterSimCalculator
            
            # 모델 로드 (M3GNet, CHGNet 등 다른 모델로 교체하기도 쉬운 구조)
            calc = MatterSimCalculator(load_path=self.model_path, device=self.device)
            return calc
            
        except ImportError:
            print("⚠️ MatterSim 라이브러리를 찾을 수 없습니다.")
            print("테스트를 위해 가짜(Lennard-Jones) 계산기를 대신 반환합니다.")
            
            # 테스트용: 라이브러리가 없을 때 기본 물리 엔진 사용
            from ase.calculators.lj import LennardJones
            return LennardJones()

# 편의를 위해 인스턴스 없이 바로 부를 수 있는 헬퍼 함수
def get_calculator(device='cuda'):
    loader = MatterSimLoader(device=device)
    return loader.load()