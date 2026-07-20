# BE 요청 사항: RDS 저장 완료 후 AuraDB Sync 호출 추가

## 배경

현재 AI 서버는 기존 상담 분석 API 계약을 유지합니다.

기존 BE 호출:

```http
POST /ai/v1/consultations/analyze
```

이 API는 그대로 동작하며, AuraDB에는 직접 쓰지 않습니다.

AuraDB는 RDS의 projection layer로 사용해야 하므로, AI 분석 응답 직후가 아니라 **BE가 RDS 저장을 완료한 뒤** 실제 RDS ID를 포함해서 별도 sync API를 호출해야 합니다.

## 새로 호출해야 할 AI API

```http
POST /ai/v1/graph/consultations/sync
```

## 호출 시점

`ConsultationAiAnalysisService`에서 AI 분석 응답을 받은 뒤, 아래 RDS 저장이 모두 끝난 다음 호출해주세요.

- `consultation.summary`
- `consultation.aiAnalysisStatus = COMPLETED`
- `consultation.aiParsedAt`
- `customer_ai_insight`
- `non_conversion_reason`
- `follow_up`, 단 `REGISTERED`/`LOST` 등 follow-up 미생성 케이스 제외
- `follow_up_ai_insight`, follow-up이 생성된 경우만

중요한 점은 `follow_up.id`, `non_conversion_reason.id`가 실제 DB에 생성된 뒤여야 한다는 것입니다.

## 왜 analyze 직후가 아니라 RDS 저장 후인가

AuraDB와 RDS 데이터가 일치해야 하기 때문입니다.

AI 서버가 `/analyze` 응답 직후 AuraDB에 쓰면 `followUpId`, `reasonId`를 알 수 없어서 임의 ID나 추측 ID가 들어가게 됩니다.

따라서 BE가 RDS 저장 완료 후 실제 UUID를 담아 `/graph/consultations/sync`를 호출해야 합니다.

## 요청 Payload 예시

```json
{
  "store": {
    "storeId": "28f43532-f2fc-4581-827e-880d06f3cd88",
    "storeType": "GYM"
  },
  "service": {
    "serviceId": "88d53bb7-7210-4e77-a0c4-01778a54d68d",
    "storeId": "28f43532-f2fc-4581-827e-880d06f3cd88",
    "serviceName": "PT",
    "description": "1:1 training",
    "price": 600000,
    "active": true
  },
  "customer": {
    "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
    "storeId": "28f43532-f2fc-4581-827e-880d06f3cd88",
    "registeredServiceId": null,
    "name": "홍길동",
    "gender": "MALE",
    "birthDate": "1995-04-12",
    "phoneNum": "010-1234-5678",
    "preferredContactChannel": "KAKAO",
    "status": "PENDING",
    "inflowPathId": "71564cdc-6ad1-4978-a74e-150c576ce13c",
    "inflowPathName": "Instagram",
    "registeredAt": null,
    "firstConsultAt": "2026-07-09",
    "latestConsultAt": "2026-07-09"
  },
  "consultation": {
    "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
    "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
    "consultedServiceId": "88d53bb7-7210-4e77-a0c4-01778a54d68d",
    "sessionNo": 1,
    "consultedAt": "2026-07-09T14:30:00+09:00",
    "stage": "CONSULTATION",
    "sourceType": "DIRECT",
    "rawText": "상담 원문",
    "summary": "AI 상담 요약",
    "aiAnalysisStatus": "COMPLETED",
    "aiParsedAt": "2026-07-09T14:31:00+09:00"
  },
  "customerAiInsight": {
    "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
    "leadTemperature": "WARM",
    "temperatureBasis": "관심은 있으나 가격 부담이 있음",
    "priorityScore": 78,
    "analyzedAt": "2026-07-09T14:31:00+09:00"
  },
  "nonConversionReasons": [
    {
      "reasonId": "f5ceceea-4fa4-4317-bf68-6752af1cc0bd",
      "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
      "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
      "reasonType": "PRICE",
      "role": "PRIMARY",
      "reasonBasis": "가격 부담을 언급함",
      "confidence": "HIGH"
    }
  ],
  "followUp": {
    "followUpId": "7e08bfd1-247d-4ca2-8038-5185945b7c37",
    "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
    "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
    "recommendContactDate": "2026-07-11",
    "status": "PENDING",
    "contactRound": 1,
    "hasReply": false,
    "repliedAt": null,
    "snoozedUntil": null,
    "memo": "예산 맞춤 옵션 안내"
  },
  "followUpAiInsight": {
    "followUpId": "7e08bfd1-247d-4ca2-8038-5185945b7c37",
    "persuasionPoint": {
      "main": "초기 비용 부담 완화"
    },
    "cautionNote": "무리한 결제 압박은 피할 것",
    "actionBasis": {
      "title": "예산 맞춤 옵션 안내",
      "description": "시작 부담이 낮은 옵션 제안"
    },
    "analyzedAt": "2026-07-09T14:31:00+09:00"
  }
}
```

## Follow-up이 없는 고객

`REGISTERED` 또는 `LOST`처럼 follow-up을 만들지 않는 경우에는 아래처럼 보내면 됩니다.

```json
{
  "followUp": null,
  "followUpAiInsight": null
}
```

`nonConversionReasons`가 없으면 빈 배열로 보내면 됩니다.

```json
{
  "nonConversionReasons": []
}
```

## 응답 예시

AuraDB persistence가 꺼져 있으면:

```json
{
  "persisted": false,
  "counts": null
}
```

AuraDB persistence가 켜져 있고 저장에 성공하면:

```json
{
  "persisted": true,
  "counts": {
    "...": 0
  }
}
```

`counts`는 Neo4j count 검증 값입니다.

## 검증 규칙

AI 서버는 payload 내부 RDS 참조 ID가 서로 안 맞으면 `422`로 거절합니다.

반드시 아래 관계가 맞아야 합니다.

- `service.storeId == store.storeId`
- `customer.storeId == store.storeId`
- `consultation.customerId == customer.customerId`
- `consultation.consultedServiceId == service.serviceId`
- `customerAiInsight.customerId == customer.customerId`
- 모든 `nonConversionReasons[].customerId == customer.customerId`
- 모든 `nonConversionReasons[].consultationId == consultation.consultationId`
- `followUp.customerId == customer.customerId`
- `followUp.consultationId == consultation.consultationId`
- `followUpAiInsight.followUpId == followUp.followUpId`

## 실패 처리 요청

sync API 실패가 RDS 저장 성공을 롤백하면 안 됩니다.

권장 처리:

1. RDS 저장 트랜잭션은 정상 완료
2. 트랜잭션 완료 후 sync API 호출
3. sync 실패 시 warn log 기록
4. 필요하면 재시도 큐/스케줄러 대상으로 저장

예시 흐름:

```java
AiConsultationAnalyzeResponse response = aiClient.analyzeConsultation(request);

SavedAnalysisResult saved = transactionTemplate.execute(status -> {
    // consultation summary/status 저장
    // customer_ai_insight 저장
    // non_conversion_reason 저장
    // follow_up 저장
    // follow_up_ai_insight 저장
    // 실제 저장된 entity id를 포함한 sync payload 생성
    return savedResult;
});

try {
    aiClient.syncConsultationGraph(saved.toGraphSyncRequest());
} catch (RuntimeException e) {
    log.warn("AuraDB graph sync failed. consultationId={}", saved.consultationId(), e);
}
```

## BE 수정 위치 후보

현재 구조 기준으로는 아래가 가장 적절합니다.

- `AiConsultationClient`
  - `POST /ai/v1/graph/consultations/sync` 호출 메서드 추가
- `ConsultationAiAnalysisService`
  - `saveAnalysisSuccess`에서 RDS 저장 완료 후 sync payload 생성
  - sync 호출은 RDS 저장 트랜잭션 밖에서 실행
- DTO 추가
  - `AiConsultationGraphSyncRequest` 같은 request DTO 추가

## 주의 사항

- 기존 `/ai/v1/consultations/analyze` 계약은 변경하지 않아도 됩니다.
- AI 서버만 먼저 배포해도 기존 BE 호출은 깨지지 않습니다.
- 하지만 BE가 `/ai/v1/graph/consultations/sync`를 호출하기 전까지 AuraDB 업로드는 발생하지 않습니다.
- AuraDB는 RDS 원천 데이터를 복제하는 projection으로 봐주세요.

## 현재 AI API 검증 결과

```text
/ai/v1/consultations/analyze              200
/ai/v1/consultations/next-action          200
/ai/v1/messages/generate                  200
/ai/v1/graph/consultations/sync           200, persisted=false when disabled
/ai/v1/graph/consultations/sync bad FK    422
pytest                                    47 passed
```
