# test_mixer.py - RandomAlloyMixer 테스트 스크립트
from mattersim_dt.builder import RandomAlloyMixer

print("="*70)
print("🧪 RandomAlloyMixer 테스트")
print("="*70)

# 테스트할 원소들 (문제가 있었던 Be 포함)
test_elements = ['Be', 'Li', 'Mg', 'Al', 'Cu', 'Ni', 'Fe', 'Ti', 'Au', 'Pt']

print("\n📊 원소별 구조 생성 테스트:\n")

success_count = 0
fail_count = 0

for elem in test_elements:
    try:
        mixer = RandomAlloyMixer(elem)
        atoms = mixer.base_atoms

        # 격자 정보 가져오기
        if elem in mixer.LATTICE_DATA:
            structure, lattice = mixer.LATTICE_DATA[elem]
            status = f"✅ {structure.upper()}, a={lattice:.2f}Å"
        else:
            status = "✅ ASE 기본값"

        print(f"   {elem:<4} | {len(atoms)}원자 | {status}")
        success_count += 1

    except Exception as e:
        print(f"   {elem:<4} | ❌ 실패: {e}")
        fail_count += 1

print("\n" + "="*70)
print(f"✅ 성공: {success_count}개 / ❌ 실패: {fail_count}개")
print("="*70)

# Be-Li 합금 생성 테스트
print("\n🔬 Be-Li 합금 생성 테스트:")

try:
    mixer = RandomAlloyMixer('Be')
    alloy = mixer.generate_structure('Li', ratio=0.3, supercell_size=3)

    print(f"   ✅ 성공!")
    print(f"   - 총 원자: {len(alloy)}개")
    print(f"   - 화학식: {alloy.get_chemical_formula()}")
    print(f"   - 구조: {alloy.cell}")

except Exception as e:
    print(f"   ❌ 실패: {e}")

print("\n" + "="*70)
print("테스트 완료!")
print("="*70)
