from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5


SERVICES = [
    ("헬스", "개인 운동 루틴과 시설 이용권"),
    ("스피닝", "음악 기반 그룹 사이클 수업"),
    ("PT", "개인 맞춤 트레이닝"),
]
INFLOW_PATHS = ["워크인", "네이버예약", "전화", "지인소개", "법인제휴", "네이버톡톡", "기타"]
GENDERS = ["남", "여"]
CONSULTANTS = ["이시원", "장성길", "송대원", "전기제", "나현석"]
REASONS = ["PRICE_CONCERN", "SCHEDULE_CONFLICT", "FAMILY_DISCUSSION", "NO_RESPONSE", "COMPARING_OPTIONS"]
SIGNALS = ["TRIAL_BOOKED", "POSITIVE_REACTION", "PRICE_SENSITIVE", "FOLLOW_UP_NEEDED", "REFERRED_BY_FRIEND"]


def generate_records(count: int, store_id: str, batch_id: str) -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    store = {
        "id": store_id,
        "name": "핏백 테스트 매장",
        "storeType": "FITNESS",
        "phone": "02-0000-0000",
        "mockBatchId": batch_id,
    }
    users = [
        {
            "id": stable_id(batch_id, "user", name),
            "storeId": store_id,
            "nickname": name,
            "email": f"{idx + 1:02d}-{name}@fitback.test",
            "role": "STAFF",
            "mockBatchId": batch_id,
        }
        for idx, name in enumerate(CONSULTANTS)
    ]
    services = [
        {
            "id": stable_id(batch_id, "service", name),
            "storeId": store_id,
            "name": name,
            "description": description,
            "isActive": True,
            "mockBatchId": batch_id,
        }
        for name, description in SERVICES
    ]
    events = [
        {
            "id": stable_id(batch_id, "event", service["name"]),
            "storeId": store_id,
            "serviceId": service["id"],
            "title": f"{service['name']} 재방문 전환 이벤트",
            "eventType": "REACTIVATION",
            "description": f"{service['name']} 상담 후 미등록 고객을 위한 7일 한정 혜택",
            "status": "ACTIVE",
            "mockBatchId": batch_id,
        }
        for service in services
    ]

    consultations = []
    for idx in range(count):
        service = services[idx % len(services)]
        event = events[idx % len(events)]
        user = users[idx % len(users)]
        reason = REASONS[idx % len(REASONS)]
        signal = SIGNALS[idx % len(SIGNALS)]
        registered = idx % 5 == 0
        customer_id = stable_id(batch_id, "customer", str(idx))
        consultation_id = stable_id(batch_id, "consultation", str(idx))
        follow_up_id = stable_id(batch_id, "follow-up", str(idx))
        consult_date = date.today() - timedelta(days=idx % 45)
        raw_text = consultation_text(idx, service["name"], reason, signal)
        consultations.append(
            {
                "customer": {
                    "id": customer_id,
                    "storeId": store_id,
                    "registeredServiceId": service["id"] if registered else None,
                    "name": f"테스트고객{idx + 1:03d}",
                    "gender": GENDERS[idx % 2],
                    "phoneNum": f"010-{1000 + idx:04d}-{2000 + idx:04d}",
                    "preferredContactChannel": "SMS",
                    "inflowPath": INFLOW_PATHS[idx % len(INFLOW_PATHS)],
                    "status": "REGISTERED" if registered else "UNREGISTERED",
                    "mockBatchId": batch_id,
                },
                "consultation": {
                    "id": consultation_id,
                    "customerId": customer_id,
                    "userId": user["id"],
                    "consultedServiceId": service["id"],
                    "consultedAt": f"{consult_date.isoformat()}T10:00:00+00:00",
                    "sessionNo": 1,
                    "stage": "CONSULTATION",
                    "summary": summarize_text(service["name"], reason),
                    "sourceType": "MOCK",
                    "rawText": raw_text,
                    "visitPurpose": f"{service['name']} 상담",
                    "positiveSignal": signal,
                    "mockBatchId": batch_id,
                },
                "followUp": {
                    "id": follow_up_id,
                    "consultationId": consultation_id,
                    "recommendContactDate": (consult_date + timedelta(days=3)).isoformat(),
                    "status": "DONE" if registered else "PENDING",
                    "memo": follow_up_text(reason, service["name"]),
                    "mockBatchId": batch_id,
                },
                "nonConversionReason": {
                    "id": stable_id(batch_id, "reason", str(idx)),
                    "customerId": customer_id,
                    "consultationId": consultation_id,
                    "reasonType": reason,
                    "role": "PRIMARY",
                    "reasonBasis": raw_text,
                    "confidence": "HIGH" if idx % 3 else "MEDIUM",
                    "mockBatchId": batch_id,
                },
                "consultationSignal": {
                    "id": stable_id(batch_id, "signal", str(idx)),
                    "consultationId": consultation_id,
                    "signalType": signal,
                    "signalValue": service["name"],
                    "confidence": "HIGH",
                    "evidenceText": raw_text,
                    "mockBatchId": batch_id,
                },
                "customerAiInsight": {
                    "customerId": customer_id,
                    "leadTemperature": "HOT" if registered or signal == "TRIAL_BOOKED" else "WARM",
                    "temperatureBasis": f"{service['name']} 관심과 {reason} 패턴을 함께 고려했습니다.",
                    "priorityScore": 90 - (idx % 30) if not registered else 60,
                    "analyzedAt": now.isoformat(),
                    "mockBatchId": batch_id,
                },
                "eventTarget": {
                    "id": stable_id(batch_id, "event-target", str(idx)),
                    "customerId": customer_id,
                    "eventId": event["id"],
                    "status": "PENDING" if not registered else "SKIPPED_REGISTERED",
                    "mockBatchId": batch_id,
                },
                "messageTemplate": {
                    "id": stable_id(batch_id, "message", str(idx)),
                    "customerId": customer_id,
                    "followUpId": follow_up_id,
                    "eventTargetId": stable_id(batch_id, "event-target", str(idx)),
                    "content": message_text(service["name"], reason),
                    "versionType": "STANDARD",
                    "tonePreset": "FRIENDLY",
                    "deliveryStatus": "DRAFT",
                    "mockBatchId": batch_id,
                },
                "contactResult": {
                    "id": stable_id(batch_id, "contact-result", str(idx)),
                    "customerId": customer_id,
                    "followUpId": follow_up_id,
                    "resultStatus": "REGISTERED" if registered else "NOT_CONTACTED",
                    "resultDate": consult_date.isoformat(),
                    "memo": "mock verification contact result",
                    "mockBatchId": batch_id,
                },
            }
        )

    return {
        "store": store,
        "users": users,
        "services": services,
        "events": events,
        "consultationRows": consultations,
        "generatedAt": now.isoformat(),
        "recordCount": count,
        "mockBatchId": batch_id,
    }


def stable_id(*parts: str) -> str:
    return str(uuid5(NAMESPACE_URL, ":".join(parts)))


def consultation_text(idx: int, service: str, reason: str, signal: str) -> str:
    return (
        f"{service} 상담 고객입니다. {signal} 신호가 있었고 "
        f"{reason} 이슈로 바로 등록하지 않았습니다. "
        f"{idx + 1}번 mock 상담 메모입니다."
    )


def summarize_text(service: str, reason: str) -> str:
    return f"{service} 관심 고객이며 주요 보류 사유는 {reason}입니다."


def follow_up_text(reason: str, service: str) -> str:
    return f"{reason}을 고려해 {service} 체험/혜택 안내 리마인드가 필요합니다."


def message_text(service: str, reason: str) -> str:
    return f"안녕하세요. 지난 {service} 상담 관련해 {reason} 부분을 도와드릴 수 있는 혜택을 안내드립니다."
