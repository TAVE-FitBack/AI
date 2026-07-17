# Fitback AI Ontology

Fitback AI는 미전환 사유, 추천 행동, 리드 온도를 하나의 경량 온톨로지로 관리한다.
이 온톨로지는 RDF/OWL 표준 파일이 아니라 Python 코드북과 Neo4j 의미 그래프로 표현된다.

## 목적

- LLM이 `reasonType`, `leadTemperature`, `confidence`를 임의 문자열로 만들지 않게 한다.
- 휴리스틱 provider, OpenAI provider, 실제 서비스 데이터 적재, Neo4j GraphRAG가 같은 의미 체계를 공유한다.
- Spring/FastAPI public API field name과 endpoint는 유지한다.

## 주요 개념

### ReasonConcept

| code | label | category | default action |
|---|---|---|---|
| `PRICE` | 가격 부담 | `ECONOMIC` | `BUDGET_OPTION_GUIDE` |
| `SCHEDULE` | 일정 충돌 | `TIME` | `SCHEDULE_RECONFIRM` |
| `FAMILY_DISCUSSION` | 가족 상의 | `DECISION` | `DECISION_SUMMARY_SEND` |
| `NO_RESPONSE` | 무응답 | `ENGAGEMENT` | `RESPONSE_REMINDER` |
| `COMPARING_OPTIONS` | 대안 비교 | `DECISION` | `COMPARISON_SUPPORT` |
| `NEEDS_FOLLOW_UP` | 후속 확인 필요 | `ENGAGEMENT` | `GENERAL_FOLLOW_UP` |

### LeadTemperatureConcept

| code | meaning |
|---|---|
| `HOT` | 등록 또는 체험 예약처럼 전환 행동이 구체적인 상태 |
| `WARM` | 관심은 있으나 가격, 일정, 비교 이슈로 후속 설득이 필요한 상태 |
| `COLD` | 관심 신호가 약하거나 후속 근거가 부족한 상태 |

### ActionConcept

| code | label |
|---|---|
| `BUDGET_OPTION_GUIDE` | 예산 맞춤 상품 안내 |
| `SCHEDULE_RECONFIRM` | 가능 시간 재확인 |
| `DECISION_SUMMARY_SEND` | 결정 요약 전달 |
| `RESPONSE_REMINDER` | 응답 리마인드 |
| `COMPARISON_SUPPORT` | 비교 기준 지원 |
| `GENERAL_FOLLOW_UP` | 일반 후속 연락 |

## Neo4j 의미 그래프

온톨로지 노드는 실제 서비스 데이터와 별개로 유지되지만, 적재 시 Python 코드북과 동기화된다.
처음 데이터가 없는 상태에서도 schema와 온톨로지 노드는 생성되며, 현재 코드북에 없는 stale `OntologyConcept` 노드는 삭제된다.

```cypher
(:ReasonConcept)-[:BELONGS_TO]->(:ReasonCategory)
(:ReasonConcept)-[:RECOMMENDS_ACTION]->(:ActionConcept)
(:NonConversionReason)-[:INSTANCE_OF]->(:ReasonConcept)
(:CustomerAiInsight)-[:HAS_TEMPERATURE]->(:LeadTemperatureConcept)
```

예시 조회:

```cypher
MATCH (customer:Customer)-[:HAS_NON_CONVERSION_REASON]->(reason:NonConversionReason)
MATCH (reason)-[:INSTANCE_OF]->(concept:ReasonConcept)-[:RECOMMENDS_ACTION]->(action:ActionConcept)
RETURN customer.name, concept.code, concept.label, action.code, action.label
LIMIT 20;
```

## LLM 사용 규칙

- `reasonType`은 `ReasonConcept.code` 중 하나만 사용한다.
- `leadTemperature`는 `HOT`, `WARM`, `COLD` 중 하나만 사용한다.
- `confidence`는 `LOW`, `MEDIUM`, `HIGH` 중 하나만 사용한다.
- 명확한 사유가 없으면 `NEEDS_FOLLOW_UP`을 사용하고 사유를 단정하지 않는다.
- OpenAI 응답이 허용되지 않은 제어 코드를 반환하면 조용히 다른 코드로 바꾸지 않고 처리 실패로 간주한다.
- 과거 legacy 값은 적재 전에 canonical code로 저장하고, 원래 값은 `originalReasonType` 또는 `originalLeadTemperature`로 보존한다.
