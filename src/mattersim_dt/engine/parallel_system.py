"""
다중 GPU 환경에서 여러 시스템을 병렬로 처리하는 모듈
"""
import multiprocessing as mp
from typing import List, Tuple, Callable, Any
import os


def run_system_on_gpu(gpu_id: int, element_pair: Tuple[str, str],
                      pipeline_func: Callable, *args) -> Any:
    """
    특정 GPU에서 하나의 시스템을 실행

    :param gpu_id: 사용할 GPU ID (0, 1, 2, ...)
    :param element_pair: (element_A, element_B) 튜플
    :param pipeline_func: 실행할 파이프라인 함수
    :param args: 추가 인자들
    :return: 파이프라인 실행 결과
    """
    # GPU 할당 (환경변수로 제어)
    os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)

    print(f"🚀 GPU {gpu_id}: {element_pair[0]}-{element_pair[1]} 시스템 시작")

    try:
        result = pipeline_func(element_pair[0], element_pair[1], *args)
        return result
    except Exception as e:
        print(f"❌ GPU {gpu_id} 오류: {e}")
        return None


class ParallelSystemRunner:
    """
    여러 원소 조합을 다중 GPU에서 병렬로 실행하는 클래스
    """
    def __init__(self, num_gpus: int = 1):
        """
        :param num_gpus: 사용 가능한 GPU 개수
        """
        self.num_gpus = num_gpus

    def run_parallel(self, element_pairs: List[Tuple[str, str]],
                     pipeline_func: Callable, *args) -> List[Any]:
        """
        여러 시스템을 병렬로 실행

        :param element_pairs: [(elem_A, elem_B), ...] 리스트
        :param pipeline_func: 각 시스템에 대해 실행할 함수
        :param args: 추가 인자들
        :return: 결과 리스트
        """
        if self.num_gpus <= 1:
            # 단일 GPU: 순차 실행
            print("ℹ️  단일 GPU 모드: 순차 실행")
            results = []
            for elem_A, elem_B in element_pairs:
                result = pipeline_func(elem_A, elem_B, *args)
                results.append(result)
            return results

        # 다중 GPU: 병렬 실행
        print(f"🚀 다중 GPU 모드: {self.num_gpus}개 GPU 사용")

        # 프로세스 풀 생성
        with mp.Pool(processes=self.num_gpus) as pool:
            # GPU를 순환하면서 할당
            tasks = []
            for idx, (elem_A, elem_B) in enumerate(element_pairs):
                gpu_id = idx % self.num_gpus
                task = pool.apply_async(
                    run_system_on_gpu,
                    args=(gpu_id, (elem_A, elem_B), pipeline_func, *args)
                )
                tasks.append(task)

            # 모든 작업 완료 대기
            results = [task.get() for task in tasks]

        return results
