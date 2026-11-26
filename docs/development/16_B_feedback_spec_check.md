# Feedback 명세와 Task16-B 정합성 점검

저장소의 Feedback 작업 계약은 [AGENTS.md](../../AGENTS.md#feedback-에이전트-필수-설계-원칙)이며, 별도 Agent.md는 확인되지 않았다. 원인·검증 설계는 [Task12~20 설계](11_research_architecture_audit.md#8-feedback-원인연구-정책-및-ab-설계), 이전 실제 실행과 범위는 [Task16-B](16_B_research_feedback_cycle.md)를 대조했다.

| 명세 요구 | 상태와 실제 코드 근거 |
|---|---|
| 1. 시장 하락·대형주·장기투자 서사로 지속 부진 합리화 금지 | **보완.** 반복 부진의 출처가 있으면 일반 변동에 따른 MAINTAIN 분기를 사용하지 않는다. 부진을 기술 결함이나 특정 투자 행동의 인과로 단정할 근거도 별도로 요구한다. [판단](../../src/quant_harness/investment/research_feedback.py#L71) |
| 2. 동일 위험·노출의 시장·업종·ETF·대체 투자와 적립식 기회비용 | **부분.** 적격 비교 자료를 받는 분기와 기존 성숙 라벨·체결 감사가 있다. 반복 부진에 동일 자본·기간·노출·위험의 비용 후 비교를 명시하고, ETF 적립식 비교 시 동일 납입 일자·금액도 요구하도록 보완했다. Task16-B가 이 자료를 직접 구성하거나 업종·적립식 대안을 자동 계산하는 경로는 없다. [재평가 증거](../../src/quant_harness/investment/research_feedback.py#L132) · [성숙 라벨과 대안 점수](../../src/quant_harness/investment/review.py#L129) |
| 3. 반복 부진에 재평가 기한·증거 조건 | **보완.** 출처가 연결된 반복 부진에는 DEADLINE_REQUIRED, SCHEDULED, REVIEW_DUE를 반환한다. 호출자가 시간대가 있는 기한을 제공하며, 기한을 지난 경우 자동 주문·승격 없이 검토 필요 상태가 표시된다. 스케줄러는 이 작업의 범위에 포함되지 않는다. [입력 검사](../../src/quant_harness/investment/research_feedback.py#L63) · [재평가 상태](../../src/quant_harness/investment/research_feedback.py#L132) |
| 4. 추가매수·축소·청산·재진입을 검증할 선택지로 취급 | **부분.** 기존 Review는 입력에 있는 대조 행동과 체결·성숙 결과를 읽는다. Task16-B는 불일치 원장으로 투자 손익 원인을 확정하지 않으며, 허용 작업자는 공시 원문과 노출 적격성 두 종류다. 복수 정책의 동시 비교나 각 주문 행동의 독립 손익 귀속은 미구현이다. [대조 행동](../../src/quant_harness/investment/review.py#L201) · [체결 감사](../../src/quant_harness/investment/review_execution.py#L6) · [작업자 분기](../../src/quant_harness/investment/research_feedback_dispatch.py#L75) |
| 5. 정상 변동에 과잉 대응 금지 | **보완.** 정상 변동의 출처가 있고 반복 부진이 확인되지 않으면 유지할 수 있다. 미기각 정책의 비용 후 차이가 음수라도 불확실성 구간이 없거나 0을 포함하면 해당 점추정만으로 기각하지 않는다. 고정 사양의 과거 기각은 보존한다. [판정 분기](../../src/quant_harness/investment/research_feedback.py#L82) |
| 6. 과소·과잉 대응 회귀, 비용 후·위험 개선 전 운영 적용 금지 | **구현 및 한계 유지.** 자체 봉인 주입 사례와 추가 회귀로 두 방향의 판단 경계를 검사했다. Task17의 실제 비용 후·위험 우위는 미검증이다. [시험](../../experiments/task16_b/test_research_feedback.py) · [Task17 설계](11_research_architecture_audit.md#8-feedback-원인연구-정책-및-ab-설계) |
| 7. 실시간 Python과 비실시간 LLM 역할 분리 | **구현.** 모델 문장은 허용 경로와 제공된 증거 ID에 묶는 자문이다. 운영 경로와 분리된 Factory 진단에만 전달할 수 있으며 자본·Task15·승격 플래그는 꺼져 있다. [자문 검사](../../src/quant_harness/investment/research_feedback.py#L151) · [격리 경계](../../src/quant_harness/investment/research_feedback_dispatch.py#L103) |
| 증거 시점·이력·격리 예산·사람 승인 | **보완 및 기존 계약 유지.** 모호한 데이터 상태, 문자열 불리언, 빈 진단 출처, 불완전 구간을 거부한다. Factory에 전달하기 직전에 실제 파일의 해시를 확인한다. 기존 ID/계약 중복, 진단 한 건 및 파라미터 탐색 0회, 독립 승인 관문을 유지한다. 새 표현의 의미 중복 탐지나 신규 전략 연구 연결은 미검증이다. [증거 검사](../../src/quant_harness/investment/research_feedback.py#L23) · [파일 검증](../../src/quant_harness/investment/research_feedback_dispatch.py#L33) · [기존 Factory 예약](../../src/quant_harness/alpha_research_factory.py#L304) |

기존 봉인 출력은 덮어쓰지 않았다. 읽기 전용으로 기존 결정과 모델 자문 바인딩을 재계산해 일치를 확인했다. 이 점검의 모델 호출, Factory 신규 등록·예약, 통합 자율 알파 연구 Cycle 1 실행, 운영 및 자본 변경은 모두 0건이다. 독립 일반화·투자 경제성이 확인되지 않아 ALPHA_NOT_VALIDATED를 유지한다. [읽기 전용 검산](../../runtime/task16_b_spec_check/read_only_replay.json)

연구·Feedback 회귀 17건, 필수 안전 회귀 24건, compileall이 통과했다. [연구 회귀](../../runtime/task16_b_spec_check/research.log) · [안전 회귀](../../runtime/task16_b_spec_check/safety.log)

```bash
PYTHONPATH=src:. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q \
  experiments/task16_b/test_research_feedback.py experiments/task16_a/test_feedback.py
PYTHONPATH=src:. .venv/bin/python experiments/task16_b/audit.py
```
