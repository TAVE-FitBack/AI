# FastAPI 연동 요구사항

## 1. 목적과 범위

이 문서는 Fitback Spring Boot 서버가 FastAPI AI 서버에 요청하는 HTTP API 계약을 정의한다.
FastAPI 담당자는 아래 5개 엔드포인트를 구현하고, 요청/응답 JSON의 필드명과 타입을 그대로 맞춰야 한다.

| 기능 | Method | Path |
|---|---|---|
| 문의 내용 중간 점검 | `POST` | `/ai/v1/inquiries/check-preview` |
| 상담 내용 중간 점검 | `POST` | `/ai/v1/consultations/check-preview` |
| 상담 AI 분석 | `POST` | `/ai/v1/consultations/analyze` |
| 다음 행동 재생성 | `POST` | `/ai/v1/consultations/next-action` |
| 고객 메시지 생성 | `POST` | `/ai/v1/messages/generate` |

현재 Spring 서버의 기본 AI 서버 주소는 `http://localhost:8000`이며, 배포 환경에서는
`AI_BASE_URL` 환경 변수로 변경한다.

## 2. 공통 통신 규약

- 요청과 응답의 미디어 타입은 `application/json`이다.
- JSON 필드명은 **camelCase**를 사용한다. FastAPI/Pydantic 내부에서 snake_case를
  사용한다면 alias를 설정해 실제 JSON은 camelCase로 송수신해야 한다.
- UUID는 하이픈을 포함한 문자열로 송수신한다.
- 날짜(`LocalDate`)는 `YYYY-MM-DD` 형식이다.
- 일시(`OffsetDateTime`)는 UTC offset을 포함한 ISO 8601 문자열이다.
  예: `2026-07-09T14:30:00+09:00`
- Java enum은 아래에 명시한 **대문자 문자열**로 직렬화된다.
- 금액과 할인율(`BigDecimal`)은 JSON number로 송수신한다.
- 성공 시 JSON body가 있는 `2xx`를 반환한다. 권장 성공 코드는 `200 OK`이다.
- 실패 시 적절한 `4xx` 또는 `5xx`를 반환한다. Spring 서버는 FastAPI의 오류 body를
  업무 응답으로 사용하지 않으므로 오류 형식은 자유지만, 로그 추적을 위해 다음 형식을 권장한다.

```json
{
  "detail": "요청을 처리할 수 없는 이유",
  "code": "AI_PROCESSING_FAILED"
}
```

- 상담 분석, 다음 행동 재생성, 메시지 생성의 Spring 연결 제한 시간은 3초,
  응답 대기 제한 시간은 30초로 설정할 예정이다. 정상 요청은 반드시 30초 안에 응답해야 한다.
- 현재 서버 간 인증 헤더는 사용하지 않는다. 인증이 필요하면 Spring/FastAPI 양측에
  별도 합의 후 동시에 적용해야 한다.
- 알 수 없는 응답 필드는 Spring에서 무시하지만, 계약에 없는 필드 추가에 의존해서는 안 된다.

## 3. Enum 값

| 타입 | 허용 값 |
|---|---|
| `Gender` | `MALE`, `FEMALE` |
| `InquiryStatus` | `RECEIVED`, `VISIT_SCHEDULED`, `VISIT_CANCELED`, `CONVERTED` |
| `ConsultationStage` | `CONSULTATION`, `FIRST_FOLLOW_UP`, `SECOND_FOLLOW_UP`, `TRIAL`, `FINAL_DECISION` |
| `ConsultationSourceType` | `DIRECT`, `IMPORT`, `INQUIRY` |
| `ConsultationRegistrationStatus` | `REGISTERED`, `PENDING`, `SCHEDULED`, `LOST` |
| `CustomerStatus` | `REGISTERED`, `PENDING`, `SCHEDULED`, `LOST`, `NO_SHOW` |
| `PreferredContactChannel` | `SMS`, `PHONE`, `KAKAO` |
| `StoreType` | `GYM`, `OTHER` |
| `MessageTonePreset` | `FRIENDLY`, `PROFESSIONAL`, `SOFT` |
| `MessageVersionType` | `SHORT`, `STANDARD` |

응답의 `leadTemperature`, `reasonType`, `role`, `confidence`는 현재 Spring enum이 아닌
문자열로 저장된다. FastAPI 측에서 사용할 값의 목록과 의미를 별도 문서로 고정하는 것을 권장한다.

## 4. 문의 내용 중간 점검

### `POST /ai/v1/inquiries/check-preview`

문의 등록 전에 입력 내용을 AI로 점검한다.

요청:

```json
{
  "rawText": "가격과 주 3회 PT 가능 여부를 문의함",
  "serviceName": "퍼스널 트레이닝",
  "inquiryStatus": "RECEIVED",
  "customerInfo": {
    "name": "홍길동",
    "gender": "MALE",
    "birthDate": "1995-04-12"
  }
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `rawText` | string | Y | 문의 원문 |
| `serviceName` | string | Y | 문의 서비스명 |
| `inquiryStatus` | `InquiryStatus` | Y | 문의 상태 |
| `customerInfo` | object | Y | 고객 정보 |
| `customerInfo.name` | string | Y | 고객명 |
| `customerInfo.gender` | `Gender` | Y | 성별 |
| `customerInfo.birthDate` | date string | Y | 생년월일 |

응답은 현재 Spring에서 `Map<String, Object>`로 그대로 프론트엔드에 전달한다.
따라서 FastAPI 팀은 아래 스키마를 기준으로 점검 결과를 반환한다.
이 응답은 입력 원문에서 AI가 확인한 정보를 우측 `AI가 확인한 정보` 패널에 표시하기 위한 값이다.

```json
{
  "confirmedCount": 3,
  "totalCount": 7,
  "items": [
    {
      "key": "INTEREST_SERVICE",
      "label": "관심 상품",
      "confirmed": true,
      "value": "헬스 6개월, 12개월"
    },
    {
      "key": "EXERCISE_GOAL",
      "label": "운동 목적",
      "confirmed": true,
      "value": "다이어트"
    },
    {
      "key": "EXERCISE_EXPERIENCE",
      "label": "운동 경험",
      "confirmed": true,
      "value": "이전에 헬스장 다녔고 거기서 PT 6개월간 받은 경험이 있음"
    },
    {
      "key": "INJURY_HISTORY",
      "label": "부상 이력",
      "confirmed": false,
      "value": "아직 확인되지 않음"
    },
    {
      "key": "CUSTOMER_REQUEST",
      "label": "고객 요청",
      "confirmed": false,
      "value": "아직 확인되지 않음"
    },
    {
      "key": "COUNSELOR_RESPONSE",
      "label": "나의 응대",
      "confirmed": false,
      "value": "아직 확인되지 않음"
    },
    {
      "key": "SPECIAL_NOTE",
      "label": "특이사항",
      "confirmed": false,
      "value": "아직 확인되지 않음"
    }
  ]
}
```

필드 규칙:

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `confirmedCount` | integer | Y | `confirmed=true`인 항목 수 |
| `totalCount` | integer | Y | 전체 확인 항목 수. 현재 화면 기준 `7` |
| `items` | array | Y | AI 확인 항목 목록 |
| `items[].key` | string | Y | 항목 식별자 |
| `items[].label` | string | Y | 화면 표시명 |
| `items[].confirmed` | boolean | Y | 원문에서 해당 정보를 확인했는지 여부 |
| `items[].value` | string | Y | 확인된 값. 미확인 시 `아직 확인되지 않음` |

권장 항목과 순서:

| key | label |
|---|---|
| `INTEREST_SERVICE` | 관심 상품 |
| `EXERCISE_GOAL` | 운동 목적 |
| `EXERCISE_EXPERIENCE` | 운동 경험 |
| `INJURY_HISTORY` | 부상 이력 |
| `CUSTOMER_REQUEST` | 고객 요청 |
| `COUNSELOR_RESPONSE` | 나의 응대 |
| `SPECIAL_NOTE` | 특이사항 |

FastAPI는 위 7개 항목을 모두 반환해야 한다. 확인되지 않은 항목도 생략하지 않고 `confirmed=false`, `value="아직 확인되지 않음"`으로 반환한다.

빈 body 또는 JSON object가 아닌 응답은 허용하지 않는다.

## 5. 상담 내용 중간 점검

### `POST /ai/v1/consultations/check-preview`

상담 등록 전에 입력 내용을 AI로 점검한다.

요청:

```json
{
  "rawText": "체중 감량이 목표이며 평일 저녁 운동을 희망함",
  "serviceName": "퍼스널 트레이닝",
  "customerInfo": {
    "name": "홍길동",
    "gender": "MALE",
    "birthDate": "1995-04-12"
  }
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `rawText` | string | Y | 상담 원문 |
| `serviceName` | string | Y | 상담 서비스명 |
| `customerInfo` | object | Y | 고객 정보 |
| `customerInfo.name` | string | Y | 고객명 |
| `customerInfo.gender` | `Gender` | Y | 성별 |
| `customerInfo.birthDate` | date string | Y | 생년월일 |

응답은 문의 중간 점검과 동일한 `confirmedCount`, `totalCount`, `items` 스키마를 사용한다.
Spring은 응답을 `Map<String, Object>`로 받아 그대로 전달한다.

## 6. 상담 AI 분석

### `POST /ai/v1/consultations/analyze`

상담 저장 후 호출되며, 분석 결과를 고객 인사이트와 후속 관리 데이터로 저장한다.

요청 예시:

```json
{
  "customer": {
    "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
    "name": "홍길동",
    "gender": "MALE",
    "birthDate": "1995-04-12",
    "phoneNum": "010-1234-5678",
    "preferredContactChannel": "KAKAO",
    "status": "PENDING",
    "inflowPathId": "71564cdc-6ad1-4978-a74e-150c576ce13c",
    "inflowPathName": "인스타그램"
  },
  "consultation": {
    "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
    "sessionNo": 1,
    "consultedAt": "2026-07-09T14:30:00+09:00",
    "consultedServiceId": "88d53bb7-7210-4e77-a0c4-01778a54d68d",
    "stage": "CONSULTATION",
    "sourceType": "DIRECT",
    "rawText": "체중 감량이 목표이고 가격을 고민 중임"
  },
  "service": {
    "serviceId": "88d53bb7-7210-4e77-a0c4-01778a54d68d",
    "serviceName": "퍼스널 트레이닝",
    "description": "주 3회 1:1 트레이닝",
    "price": 600000
  },
  "storeContext": {
    "storeId": "28f43532-f2fc-4581-827e-880d06f3cd88",
    "storeType": "GYM",
    "registrationStatus": "PENDING"
  },
  "attachedMaterials": [
    {
      "materialType": "OTHER",
      "title": "kakao-chat",
      "content": "고객: PT 가격 문의드립니다.\n상담자: 현재 6개월권 이벤트가 있습니다."
    }
  ]
}
```

요청 필수 여부:

- 최상위 `customer`, `consultation`, `service`, `storeContext`, `attachedMaterials`는 필수이다.
- `consultation.stage`, `service.description`, `service.price`는 `null`일 수 있다.
- `attachedMaterials`는 상담자료가 없으면 빈 배열이다.
- `attachedMaterials[].materialType`, `attachedMaterials[].title`, `attachedMaterials[].content`는 Spring에서 문자열로 전달한다.
- 첨부자료는 AI 본분석 참고 입력으로만 사용하며, 첨부자료별 별도 분석 결과를 응답하지 않는다.
- 그 외 위 예시에 표시된 모든 필드는 Spring 도메인에서 필수값으로 구성된다.

정상 응답:

```json
{
  "summary": "체중 감량 목적의 PT 상담이며 가격 부담으로 결정을 보류함",
  "customerInsight": {
    "leadTemperature": "WARM",
    "temperatureBasis": "운동 목적과 일정은 구체적이나 가격을 고민하고 있음",
    "priorityScore": 75
  },
  "nonConversionReasons": [
    {
      "reasonType": "PRICE",
      "role": "PRIMARY",
      "reasonBasis": "가격 부담을 직접 언급함",
      "confidence": "HIGH"
    }
  ],
  "nextBestAction": {
    "title": "할인 가능한 상품 안내",
    "description": "예산에 맞는 횟수권과 현재 이벤트를 안내한다."
  },
  "followUp": {
    "recommendContactDate": "2026-07-12",
    "memo": "카카오톡으로 할인 상품 안내"
  },
  "followUpInsight": {
    "persuasionPoint": {
      "keyMessage": "목표에 맞춘 단계별 상품 제안"
    },
    "cautionNote": "가격 압박으로 느껴지지 않도록 선택지를 제시할 것",
    "actionBasis": {
      "title": "할인 가능한 상품 안내",
      "description": "예산에 맞는 횟수권과 현재 이벤트를 안내한다."
    }
  }
}
```

Spring이 응답 성공으로 인정하기 위한 필수 조건:

- `summary`: null/빈 문자열/공백 문자열 불가
- `customerInsight`: 필수
- `customerInsight.leadTemperature`: null/빈 문자열/공백 문자열 불가
- `nextBestAction`: 필수
- `nextBestAction.title`, `nextBestAction.description`: null/빈 문자열/공백 문자열 불가
- `followUp`: 필수
- `followUp.recommendContactDate`: 유효한 `YYYY-MM-DD` 필수

나머지 응답 필드는 현재 `null` 또는 빈 배열이 가능하다. 다만 안정적인 후속 기능을 위해
`nonConversionReasons`는 이유가 없을 때 `[]`로 반환하고, `priorityScore`,
`followUpInsight`도 가능한 한 항상 반환해야 한다.

## 7. 다음 행동 재생성

### `POST /ai/v1/consultations/next-action`

기존 상담 분석을 바탕으로 다음 행동과 연락 일정을 다시 생성한다.

요청:

```json
{
  "customer": {
    "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
    "status": "PENDING"
  },
  "latestConsultation": {
    "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
    "summary": "가격 부담으로 결정을 보류함",
    "rawText": "운동은 시작하고 싶지만 가격이 부담됨"
  },
  "aiAnalysis": {
    "leadTemperature": "WARM",
    "temperatureBasis": "운동 의사는 명확하지만 가격을 고민함",
    "nonConversionReasons": [
      {
        "reasonType": "PRICE",
        "role": "PRIMARY",
        "reasonBasis": "가격 부담을 직접 언급함"
      }
    ]
  }
}
```

정상 응답:

```json
{
  "priorityScore": 80,
  "nextBestAction": {
    "title": "맞춤 상품 재안내",
    "description": "예산별 상품 두 가지를 카카오톡으로 제안한다."
  },
  "followUp": {
    "recommendContactDate": "2026-07-11",
    "memo": "오후 시간에 카카오톡 발송"
  },
  "followUpInsight": {
    "persuasionPoint": {
      "keyMessage": "예산 내에서 시작할 수 있는 선택지"
    },
    "cautionNote": "과도한 할인 강조를 피할 것",
    "actionBasis": {
      "title": "맞춤 상품 재안내",
      "description": "가격이 핵심 미전환 사유임"
    }
  }
}
```

Spring이 응답 성공으로 인정하기 위한 필수 조건:

- `priorityScore`: JSON integer, `null` 불가
- `nextBestAction.title`, `nextBestAction.description`: null/빈 문자열/공백 문자열 불가
- `followUp.recommendContactDate`: 유효한 `YYYY-MM-DD`, `null` 불가
- `nextBestAction`, `followUp`: 객체 자체도 필수

`followUpInsight`는 현재 선택값이지만, 메시지 생성 품질과 후속 관리 저장을 위해 반환을 권장한다.

## 8. 고객 메시지 생성

### `POST /ai/v1/messages/generate`

고객, 상담 분석, 후속 행동 및 이벤트를 바탕으로 발송용 메시지 초안을 생성한다.

요청:

```json
{
  "customer": {
    "customerId": "6c2d9b87-90aa-4ce2-96cb-a0875f103f04",
    "name": "홍길동",
    "preferredContactChannel": "KAKAO",
    "status": "PENDING"
  },
  "latestConsultation": {
    "consultationId": "6570aa21-d458-4885-9e69-d984fea51830",
    "summary": "가격 부담으로 결정을 보류함"
  },
  "aiInsight": {
    "leadTemperature": "WARM",
    "priorityScore": 75
  },
  "nonConversionReasons": [
    {
      "reasonType": "PRICE",
      "role": "PRIMARY",
      "reasonBasis": "가격 부담을 직접 언급함"
    }
  ],
  "nextBestAction": {
    "title": "할인 가능한 상품 안내",
    "description": "예산에 맞는 상품을 제안한다.",
    "persuasionPoint": {
      "keyMessage": "목표에 맞춘 단계별 상품"
    },
    "cautionNote": "가격 압박을 피할 것",
    "actionBasis": {
      "title": "할인 가능한 상품 안내",
      "description": "가격이 핵심 미전환 사유임"
    }
  },
  "event": {
    "eventId": "7f3e50a8-3b22-4616-9663-0aa00e828f04",
    "title": "여름 PT 할인",
    "description": "PT 20회 등록 시 할인",
    "discountRate": 10.0
  },
  "messageOptions": {
    "tonePreset": "FRIENDLY",
    "versionType": "STANDARD",
    "additionalInstruction": "첫 문장에 고객 이름을 넣어 주세요."
  }
}
```

요청 시 다음 값은 `null`일 수 있다.

- `aiInsight.leadTemperature`, `aiInsight.priorityScore`
- `event` 전체: 이벤트를 선택하지 않은 경우 `null`
- `event.description`, `event.discountRate`
- `messageOptions.additionalInstruction`
- 분석 데이터에서 유래한 `nextBestAction` 내부 일부 값

`nonConversionReasons`는 이유가 없으면 빈 배열로 전달된다.

정상 응답:

```json
{
  "content": "홍길동님, 상담해 드린 목표에 맞춰 부담을 낮춘 PT 상품을 안내드려요.",
  "versionType": "STANDARD",
  "tonePreset": "FRIENDLY"
}
```

Spring이 응답 성공으로 인정하기 위한 필수 조건은 `content`가 null, 빈 문자열 또는
공백 문자열이 아닌 것이다. `versionType`과 `tonePreset`도 요청값과 동일하게 반환하는 것을
권장한다. 반환할 경우 반드시 위 Enum 값 중 하나여야 하며, 다른 문자열은 전체 응답 파싱 실패를
일으킨다.

## 9. FastAPI 구현 및 검수 체크리스트

- [ ] 5개 path와 `POST` method가 정확히 일치한다.
- [ ] 요청 JSON은 camelCase alias로 수신한다.
- [ ] 날짜, offset 포함 일시, UUID 및 Enum을 위 규칙대로 검증한다.
- [ ] 응답 모델 역시 camelCase JSON을 생성한다.
- [ ] 모든 성공 응답은 JSON object와 `application/json`을 반환한다.
- [ ] 필수 응답 문자열에 `null`이나 공백 문자열을 반환하지 않는다.
- [ ] 빈 목록은 `null` 대신 `[]`로 반환한다.
- [ ] 정상 처리 시간이 30초를 넘지 않는다.
- [ ] 잘못된 요청은 `422`, 처리 실패는 의미에 맞는 `4xx`/`5xx`로 반환한다.
- [ ] 각 API의 정상, validation 실패, 내부 오류 테스트를 작성한다.
- [ ] FastAPI의 OpenAPI 문서(`/docs`, `/openapi.json`)에서 실제 스키마를 확인한다.
- [ ] Spring 개발 환경에서 `AI_BASE_URL`을 FastAPI 주소로 설정해 통합 테스트한다.

## 10. 연동 시 주의할 현재 제약

1. 두 `check-preview` 응답은 명시적인 Spring DTO가 없고 프론트엔드로 그대로 전달된다.
   FastAPI는 이 문서의 `confirmedCount`, `totalCount`, `items` 스키마와 7개 고정 항목을 지켜야 한다.
2. `leadTemperature`, `reasonType`, `role`, `confidence`의 값 집합이 코드상 고정되어 있지 않다.
   AI 서버가 임의 문자열을 계속 생성하면 검색과 통계가 불안정해지므로 양 팀이 허용 값 목록을
   합의해야 한다.
3. 현재 재시도, circuit breaker, 서버 간 인증, request ID 전달은 구현되어 있지 않다.
   운영 안정성과 추적성이 필요하면 별도 작업으로 양측에 함께 추가해야 한다.
4. FastAPI 오류 응답의 상세 내용은 현재 최종 사용자에게 전달되지 않고 Spring 업무 오류로
   변환된다. 장애 분석에 필요한 정보는 FastAPI 로그에도 남겨야 한다.
