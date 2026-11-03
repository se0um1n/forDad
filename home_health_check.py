"""집에서 건강 체크 — 실행: streamlit run home_health_check.py
의료진의 진단·치료를 대체하지 않는 교육용 규칙 기반 프로토타입.
Python 3.10+, Streamlit. 외부 AI/API로 증상을 보내지 않습니다.
"""
from __future__ import annotations
import re
from urllib.parse import urlparse, quote

SYMPTOMS = ["기침", "콧물", "인후통", "발열", "두통", "메스꺼움", "구토", "설사", "복통", "속쓰림", "가려움", "발진", "배뇨통", "빈뇨", "허리통증", "근육통", "어지럼", "흉통", "호흡곤란"]
ALIASES = {
    "기침": ["기침"], "콧물": ["콧물", "코막힘"], "인후통": ["인후통", "목이 아", "목 아", "목통증"],
    "발열": ["발열", "열이 나", "열이 있", "고열"], "두통": ["두통", "머리가 아", "머리 아"],
    "메스꺼움": ["메스꺼", "메슥", "울렁"], "구토": ["구토", "토했", "토하고", "토해"],
    "설사": ["설사", "묽은 변"], "복통": ["복통", "배가 아", "배 아"], "속쓰림": ["속쓰림", "속이 쓰", "신물이"],
    "가려움": ["가려", "가렵"], "발진": ["발진", "두드러기"], "배뇨통": ["배뇨통", "소변 볼 때 아", "소변볼 때 아"],
    "빈뇨": ["빈뇨", "소변이 자주", "소변 자주"], "허리통증": ["허리통증", "허리 통증", "허리가 아"],
    "근육통": ["근육통", "몸살"], "어지럼": ["어지럼", "어지러"], "흉통": ["흉통", "가슴 통증", "가슴이 아"],
    "호흡곤란": ["호흡곤란", "숨이 차", "숨차", "숨쉬기 힘", "숨을 못"]
}
# 필수 증상 그룹을 모두 만족할 때만 후보 표시. 점수/확률/확정 진단은 산출하지 않음.
RULES = [
    {"name": "상기도 감염(감기 등)", "groups": [{"기침", "콧물", "인후통"}], "why": "상기도 점막의 감염·자극은 기침, 콧물, 인후통을 일으킬 수 있습니다.", "limits": "독감·코로나19·알레르기 등과 증상이 겹치며, 증상만으로 구별할 수 없습니다.", "care": "휴식하고 수분을 조금씩 섭취하세요. 기침이 있으면 환기와 마스크 등으로 전파를 줄이세요."},
    {"name": "인플루엔자·코로나19 등 호흡기 바이러스 감염", "groups": [{"발열"}, {"기침", "인후통", "근육통"}], "why": "발열과 호흡기 증상 또는 근육통은 바이러스 감염에서 함께 나타날 수 있습니다.", "limits": "병원체는 검사 없이 확정할 수 없습니다. 고위험군은 조기 치료 필요성을 의료진과 상의하세요.", "care": "접촉을 줄이고 휴식하세요. 검사와 진료 가능 여부를 전화로 먼저 확인하세요."},
    {"name": "위장관 감염·음식 관련 위장 증상", "groups": [{"설사", "구토"}], "why": "장관 감염이나 음식에 의한 자극은 설사·구토를 유발할 수 있습니다.", "limits": "약물 부작용이나 다른 복부 질환도 가능합니다. 혈변·심한 복통·탈수는 별도 평가가 필요합니다.", "care": "삼킬 수 있다면 물이나 경구수분보충액을 조금씩 자주 드세요. 수분을 유지하지 못하면 진료가 필요합니다."},
    {"name": "위식도역류·소화불량", "groups": [{"속쓰림"}], "why": "위 내용물의 역류나 위장 자극은 속쓰림과 신물 증상을 만들 수 있습니다.", "limits": "흉통을 속쓰림으로 오인할 수 있습니다. 새로 생긴 가슴 통증은 이 후보로 안심하면 안 됩니다.", "care": "과식과 식후 바로 눕기를 피하고, 증상을 유발하는 음식을 기록하세요."},
    {"name": "긴장형 두통·편두통 등 두통 질환", "groups": [{"두통"}], "why": "수면 부족, 근육 긴장, 편두통 등 다양한 원인으로 두통이 생길 수 있습니다.", "limits": "양상·진찰 없이 두통 종류를 구분할 수 없습니다. 갑작스러운 극심한 두통·마비·의식 변화는 응급 신호입니다.", "care": "조용한 곳에서 쉬고, 수분과 수면을 챙기며 시작 시점과 동반 증상을 기록하세요."},
    {"name": "접촉피부염·알레르기 등 피부 질환", "groups": [{"가려움", "발진"}], "why": "피부 자극이나 알레르기 반응은 발진과 가려움을 유발할 수 있습니다.", "limits": "감염 등 다른 원인도 있습니다. 입술·혀 부종이나 호흡곤란이 동반되면 즉시 응급 도움을 요청하세요.", "care": "새로 사용한 화장품·세제 등 의심 자극을 피하고 긁지 마세요. 넓게 번지거나 물집·발열이 있으면 진료하세요."},
    {"name": "요로감염 등 비뇨기 질환", "groups": [{"배뇨통", "빈뇨"}], "why": "요로의 감염·자극은 배뇨통이나 잦은 소변을 유발할 수 있습니다.", "limits": "소변검사 등이 필요합니다. 발열·옆구리 통증·임신 중 증상은 더 빠른 평가가 필요합니다.", "care": "남은 항생제를 임의로 먹지 말고 진료를 준비하세요. 증상이 지속되면 의료진과 상담하세요."},
    {"name": "근골격계 통증", "groups": [{"허리통증", "근육통"}], "why": "과사용이나 근육 긴장은 허리·근육 통증의 원인 중 하나입니다.", "limits": "감염, 신경 압박 등 다른 원인은 배제되지 않습니다. 새 마비·배뇨배변 조절 이상은 응급 평가가 필요합니다.", "care": "통증을 악화시키는 무리한 활동은 줄이되, 가능한 범위에서 가볍게 움직이세요."}
]
EMERGENCIES = [
    "심하게 숨이 차서 문장을 말하기 어렵거나 입술이 파래짐",
    "갑작스럽거나 지속되는 가슴 통증·압박감, 또는 식은땀·실신을 동반한 흉통",
    "갑자기 한쪽 팔·다리 힘이 빠짐, 얼굴 비대칭, 말이 어눌해짐",
    "의식 저하·실신·새로운 경련 또는 갑작스러운 극심한 두통",
    "입술·혀·목이 붓거나 알레르기 반응과 함께 숨쉬기 어려움",
    "멈추지 않는 출혈, 피 토함, 검은 변·혈변 또는 매우 심한 복통",
    "새로 생긴 다리 마비나 소변·대변 조절 이상",
    "약물 과다복용·중독·자해 또는 즉각적인 자해 위험"
]
SOURCES = {
    "NHS: 흉통": "https://www.nhs.uk/symptoms/chest-pain/",
    "NHS: 호흡곤란": "https://www.nhs.uk/symptoms/shortness-of-breath/",
    "NHS: 응급 도움을 요청해야 하는 경우": "https://www.nhs.uk/nhs-services/urgent-and-emergency-care-services/when-to-call-999/"
}


# 증상별 임시 대처. 원인 치료나 완치를 보장하지 않으며 진료를 대체하지 않음.
SYMPTOM_CARE = {
    "기침": ("물을 조금씩 마시고 담배 연기 등 자극을 피하세요. 환기하고 기침 예절을 지키세요.", "숨참·흉통·피 섞인 가래 또는 악화가 있으면 신속히 진료하세요."),
    "콧물": ("휴식하고 생리식염수 코 스프레이 등으로 불편함을 줄일 수 있습니다.", "고열·심한 얼굴 통증·오래 지속되는 증상은 진료가 필요합니다."),
    "인후통": ("삼킬 수 있다면 미지근한 물을 조금씩 마시고 자극적인 음식과 흡연을 피하세요.", "침도 삼키기 어렵거나 목이 붓고 숨쉬기 힘들면 응급 도움을 요청하세요."),
    "발열": ("체온을 기록하고 쉬세요. 수분 제한 처방이 없다면 수분을 조금씩 섭취하세요.", "고열·의식 변화·목 경직·심한 두통, 또는 면역저하 상태이면 신속히 의료진에게 연락하세요."),
    "두통": ("조용하고 어두운 곳에서 쉬고 수면·수분을 챙기세요. 시작 시점과 통증 양상을 기록하세요.", "갑작스러운 극심한 두통·마비·말 이상·의식 변화는 119가 우선입니다."),
    "메스꺼움": ("소량씩 천천히 먹고 강한 냄새와 기름진 음식을 피하세요. 물은 조금씩 마시세요.", "계속 토하거나 흉통·심한 복통·탈수가 동반되면 신속히 진료하세요."),
    "구토": ("의식이 명료하고 삼킬 수 있을 때만 물이나 경구수분보충액을 조금씩 자주 드세요.", "피를 토하거나 심한 복통이 있으면 응급 평가, 물도 유지하지 못하면 빠른 진료가 필요합니다."),
    "설사": ("수분과 전해질을 조금씩 보충하고 손을 자주 씻으세요. 먹을 수 있는 음식을 소량씩 드세요.", "혈변·검은 변·심한 복통·소변 감소가 있으면 신속히 도움을 요청하세요."),
    "복통": ("편한 자세로 쉬고 통증 위치와 시작 시점을 기록하세요. 과식·음주를 피하세요.", "갑작스럽고 심한 통증·배가 단단함·실신·혈변·임신 가능성이 있으면 지체하지 말고 평가받으세요."),
    "속쓰림": ("한 번에 많이 먹지 말고 식후 바로 눕지 마세요. 유발 음식과 음주를 피하세요.", "가슴 압박·식은땀·호흡곤란은 역류로 단정하지 말고 119에 연락하세요."),
    "가려움": ("의심되는 새 제품 사용을 중단하고 차가운 찜질과 순한 보습제를 사용하세요. 긁지 마세요.", "입술·혀가 붓거나 숨쉬기 어려우면 즉시 119에 연락하세요."),
    "발진": ("발진 사진과 시작 시점을 기록하고 새 화장품·세제 등 자극을 피하세요. 물집을 터뜨리지 마세요.", "호흡곤란·점막 부종은 응급입니다. 발열·빠른 확산·통증성 물집도 빠른 평가가 필요합니다."),
    "배뇨통": ("소변을 참지 말고 증상을 기록하세요. 남은 항생제를 임의로 복용하지 마세요.", "검사·치료가 필요할 수 있어 오늘 상담하세요. 발열·옆구리 통증·임신 중이면 더 신속히 평가받으세요."),
    "빈뇨": ("카페인·술을 줄이고 소변 횟수와 양을 기록하세요. 수분을 과하게 제한하거나 늘리지 마세요.", "혈뇨·발열·옆구리 통증·심한 갈증이 있으면 빠르게 진료받으세요."),
    "허리통증": ("무거운 물건 들기를 피하고 가능한 범위에서 가볍게 움직이세요. 무리한 교정은 하지 마세요.", "새 다리 마비·회음부 감각 저하·배뇨배변 조절 이상은 즉시 응급 평가가 필요합니다."),
    "근육통": ("무리한 운동을 쉬고 통증을 악화시키지 않는 범위에서 가볍게 움직이세요.", "심한 근력 저하·짙은 갈색 소변·고열이 있으면 신속히 진료받으세요."),
    "어지럼": ("넘어지지 않도록 앉거나 누우세요. 갑자기 일어나지 말고 운전·기계 조작은 피하세요.", "실신·흉통·갑작스러운 말 이상·한쪽 마비·걷기 어려움은 즉시 응급 평가가 필요합니다."),
    "흉통": ("활동을 멈추고 편한 자세로 쉬세요. 직접 운전하지 말고 주변 사람에게 도움을 요청하세요.", "새롭거나 지속되는 가슴 통증, 식은땀·숨참·팔이나 턱으로 퍼지는 통증이면 즉시 119에 연락하세요. 그 외에도 빠른 평가가 필요합니다."),
    "호흡곤란": ("활동을 멈추고 숨쉬기 편한 자세를 취하세요. 기존에 처방받은 응급 계획이 있다면 따르세요.", "문장을 말하기 어렵거나 입술이 파래짐·흉통·의식 변화가 있으면 즉시 119에 연락하세요. 새 호흡곤란은 빠른 평가가 필요합니다.")
}


def suggest_symptoms(text: str) -> list[str]:
    """간단한 단어 제안일 뿐 NLP가 아님. 사용자가 반드시 확인·수정."""
    clauses = re.split(r"[.!?\n,;]", text.lower())
    return [symptom for symptom, words in ALIASES.items()
            if any(any(word in clause for word in words)
                   and not re.search(r"없|아니|않|안\s|부인", clause) for clause in clauses)]


def assess(data: dict) -> dict:
    symptoms = set(data["symptoms"])
    reasons = []
    emergency = bool(data["emergencies"])
    if emergency:
        reasons.extend(data["emergencies"])
    if data["danger_answer"] == "잘 모르겠음":
        reasons.append("응급 신호의 유무를 확실하게 확인하지 못함")
    if symptoms & {"흉통", "호흡곤란"}:
        reasons.append("가슴 통증 또는 호흡곤란은 증상만으로 안전하게 구별할 수 없음")
    if data["severity"] >= 7:
        reasons.append("주관적인 증상 강도가 높음")
    if data["temperature"] is not None and data["temperature"] >= 39:
        reasons.append("측정한 체온이 39℃ 이상임")
    if data["vulnerable"]:
        reasons.append("임신·면역저하·중요 기저질환 등 별도 평가가 필요한 상태")
    if data["age_group"] != "18~64세":
        reasons.append("이 앱은 성인 중심의 제한된 규칙이며 소아·고령자는 별도 평가가 필요함")
    if data["duration"] in ["3~7일", "8일 이상"] or data["worsening"]:
        reasons.append("증상이 지속되거나 악화됨")
    if symptoms & {"배뇨통", "빈뇨"}:
        reasons.append("요로 증상은 검사와 치료 필요성 확인이 필요함")
    if not symptoms:
        reasons.append("확인된 증상이 없어 입력 내용을 평가할 수 없음")
    candidates = [r for r in RULES if all(symptoms & group for group in r["groups"])]
    if not candidates and symptoms:
        reasons.append("현재 규칙에서 설명할 수 있는 후보를 찾지 못함")
    if emergency:
        level = "즉시 응급 도움"
    elif reasons:
        level = "가급적 오늘 의료진과 상담"
    else:
        level = "원격 판단 불가 · 경과 기록 및 의료 상담"
    if emergency:
        seriousness = "🔴 응급 도움 필요"
    elif reasons:
        seriousness = "🟠 빠른 의료 상담 필요 · 심각도 확정 불가"
    else:
        seriousness = "🔵 현재 보고된 응급 신호 없음 · 안전 확정 아님"
    return {"level": level, "seriousness": seriousness, "reasons": reasons,
            "candidates": candidates, "emergency": emergency,
            "symptom_care": [{"symptom": s, "care": SYMPTOM_CARE[s][0], "warning": SYMPTOM_CARE[s][1]}
                             for s in data["symptoms"] if s in SYMPTOM_CARE]}



def valid_public_url(value: str) -> bool:
    try:
        p = urlparse(value)
        return p.scheme == "https" and bool(p.hostname) and not p.username and not p.password and not p.query and not p.fragment and len(value) <= 1000
    except ValueError:
        return False


def main():
    import streamlit as st
    st.set_page_config(page_title="집에서 건강 체크", page_icon="🩺", layout="centered")
    st.markdown("""<style>
    .block-container {max-width:760px;padding-top:2rem;padding-bottom:3rem;}
    .stButton button {min-height:48px;border-radius:12px;}
    div[data-testid='stMetric'] {background:#f0f7f7;padding:1rem;border-radius:14px;}
    </style>""", unsafe_allow_html=True)
    st.title("🩺 집에서 건강 체크")
    st.caption("증상 정리 → 응급 신호 확인 → 가능한 원인과 다음 행동")
    st.error("심한 호흡곤란·가슴 압박·갑작스러운 마비·의식 저하가 있으면 입력을 멈추고 119에 연락하세요. 대한민국 외 지역은 현지 응급번호를 이용하세요.")
    st.info("교육용 규칙 기반 도구입니다. AI 진단·확정 진단·의료기기가 아니며, 병원에 가지 않아도 안전하다는 판단을 제공하지 않습니다. 약물 처방과 복용량은 안내하지 않습니다.")
    entry, about, share = st.tabs(["증상 확인", "사용 안내·한계", "QR로 공유"])
    with about:
        st.markdown("""### 먼저 알아두세요
- 성인 중심의 제한된 교육용 예시입니다. 소아·임신부·고령자·면역저하자는 직접 상담이 우선입니다.
- 후보 질환은 빈도순·위험도순 순위가 아니며, 확률도 아닙니다. 목록 밖의 심각한 질환도 가능합니다.
- 자유 입력은 단어를 제안하는 용도입니다. 문맥·부정 표현·오타·희귀질환을 정확히 이해하지 못합니다.
- 질병 관심 분야는 화면 분류일 뿐 진단의 근거로 쓰지 않습니다.
- 증상은 외부 AI API·파일·데이터베이스에 저장하지 않습니다. 다만 실행 서버로 전송되어 세션 메모리에서 처리됩니다.
- 공유 기기에서 이름·주민번호·연락처를 적지 마세요. 세션 종료 시점과 운영 인프라 로그 보존은 배포 설정에 따릅니다.
- 실제 환자에게 공개하기 전 의료진 검토, 소아·임신 대응, 보안·개인정보 검토, 응급 안내 검증이 필요합니다.

### 배포
1. GitHub 저장소에 이 파일과 dependencies.txt를 올립니다.
2. Streamlit Community Cloud에서 저장소를 연결하고 **Main file path**를 `home_health_check.py`로 지정합니다.
3. Community Cloud는 `dependencies.txt`를 자동 설치 파일로 인식하지 않습니다. 이 앱은 기본 제공 Streamlit과 Python 표준 라이브러리만 사용하므로 추가 설치 없이 실행하도록 작성했습니다.
4. 다른 호스팅에서는 `python -m pip install -r dependencies.txt` 후 `streamlit run home_health_check.py`로 실행합니다.
5. 배포한 HTTPS 주소를 QR 탭에 붙여 넣습니다. QR은 앱을 설치하는 것이 아니라 브라우저로 해당 주소를 엽니다.

### 응급 안내 참고자료
아래는 응급 안내의 참고자료입니다. 질환 후보 규칙 전체가 검증되었다는 뜻이 아닙니다. 영국 자료의 999는 국내에서는 119로 안내합니다.
""")
        for title, url in SOURCES.items():
            st.markdown(f"- [{title}]({url})")
    with share:
        st.subheader("스마트폰으로 접속")
        public_url = st.text_input("배포된 앱의 공개 HTTPS 주소", placeholder="https://your-health-app.streamlit.app", max_chars=1000)
        st.caption("로그인 토큰·개인정보가 들어간 주소는 넣지 마세요. 쿼리·프래그먼트가 포함된 주소는 허용하지 않습니다.")
        allow_qr = st.checkbox("공개 앱 주소만 외부 QR 이미지 서비스(api.qrserver.com)에 전달하는 데 동의합니다.")
        if public_url:
            if not valid_public_url(public_url):
                st.warning("사용자정보·쿼리·프래그먼트가 없는 올바른 HTTPS 주소를 입력하세요.")
            else:
                st.link_button("앱 주소 열기", public_url)
                if allow_qr:
                    qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=280x280&data=" + quote(public_url, safe="")
                    st.image(qr_url, caption="휴대폰 기본 카메라로 스캔하세요.", width=280)
                    st.caption("외부 서비스 장애·네트워크 차단 시 QR 이미지가 표시되지 않을 수 있습니다. 위 링크로도 접속할 수 있습니다.")
    with entry:
        consent = st.checkbox("확정 진단이 아닌 참고 안내이며, 응급 상황에는 119가 우선임을 이해했습니다.", key="consent")
        st.selectbox("관심 카테고리", ["전체", "호흡기·감염", "소화기", "두통·신경", "피부·알레르기", "비뇨기", "근육·관절", "기타"], key="category")
        detail = st.text_area("상태를 자세히 적어주세요", placeholder="예: 어제부터 목이 아프고 기침이 나요. 체온은 38도이며 물은 마실 수 있어요. 복용약이나 평소 질환도 적어주세요.", max_chars=3000, height=140, key="detail")
        if st.button("텍스트에서 증상 후보 가져오기", use_container_width=True):
            proposed = suggest_symptoms(detail)
            st.session_state["symptoms"] = sorted(set(st.session_state.get("symptoms", [])) | set(proposed))
            st.session_state.pop("result", None)
            st.info("단어 기반 제안입니다. 아래에서 실제 있는 증상만 남겨주세요. 텍스트만으로 응급 신호를 자동 판별하지 않습니다.")
        with st.form("health_form"):
            symptoms = st.multiselect("현재 실제로 있는 증상 (텍스트 제안도 직접 확인)", SYMPTOMS, key="symptoms")
            st.caption("해당 증상이 없으면 선택하지 마세요. 자유 입력 자체는 질환 추론에 직접 사용되지 않습니다.")
            age = st.selectbox("연령대", ["18~64세", "18세 미만", "65세 이상"])
            duration = st.selectbox("증상 지속 기간", ["24시간 미만", "1~2일", "3~7일", "8일 이상"])
            severity = st.slider("전체 증상의 불편함 (0 없음 ~ 10 견디기 어려움)", 0, 10, 3)
            measured = st.checkbox("체온계로 체온을 측정했습니다")
            temperature = st.number_input("측정 체온 (℃) · 위 항목을 체크했을 때만 반영", min_value=30.0, max_value=45.0, value=36.5, step=0.1)
            vulnerable = st.checkbox("임신·산후, 면역저하, 중요한 심장·폐·신장 질환 등이 있습니다")
            worsening = st.checkbox("증상이 빠르게 악화되거나 물을 마시기 어렵고 소변이 현저히 줄었습니다")
            st.subheader("응급 신호 — 반드시 직접 확인")
            for item in EMERGENCIES:
                st.markdown(f"- {item}")
            danger = st.radio("위 응급 신호가 있나요?", ["있음", "없음", "잘 모르겠음"], index=None)
            emergencies = st.multiselect("있는 신호를 선택하세요 (모르면 비워두세요)", EMERGENCIES)
            submit = st.form_submit_button("가능한 원인과 다음 행동 확인", use_container_width=True)
        if submit:
            st.session_state.pop("result", None)
            if not consent:
                st.warning("안내 내용을 확인하고 동의해 주세요.")
            elif danger is None:
                st.warning("응급 신호의 유무를 먼저 선택하세요.")
            elif not symptoms and not detail.strip() and danger != "있음" and not emergencies:
                st.warning("증상을 선택하거나 상태를 적어주세요.")
            else:
                flags = list(emergencies)
                if danger == "있음" and not flags:
                    flags = ["사용자가 응급 신호가 있다고 응답함"]
                payload = {"symptoms": symptoms, "detail": detail.strip(), "age_group": age, "duration": duration, "severity": severity, "temperature": temperature if measured else None, "vulnerable": vulnerable, "worsening": worsening, "danger_answer": danger, "emergencies": flags}
                st.session_state["result"] = (payload, assess(payload))
        if "result" in st.session_state:
            payload, result = st.session_state["result"]
            st.divider()
            st.caption("아래는 마지막으로 제출한 입력의 결과입니다. 내용을 바꿨다면 다시 확인 버튼을 누르세요.")
            st.markdown("## 내 증상 확인 결과")
            st.subheader(result["seriousness"])
            st.write("**권장 행동:** " + result["level"])
            st.caption("증상 강도 점수는 본인이 느끼는 불편함입니다. 질병의 심각도나 응급도를 수치로 계산한 결과가 아닙니다.")
            st.write("**제출한 증상:** " + (", ".join(payload["symptoms"]) or "선택된 증상 없음"))
            if payload["detail"]:
                st.write("입력한 상세 상태:")
                st.text(payload["detail"])
            if result["emergency"]:
                st.error("119에 즉시 연락하고 위치와 증상을 말하세요. 직접 운전하지 마세요. 가능하면 주변 사람에게 도움을 요청하세요. 후보 질환은 응급 대응을 지연시킬 수 있어 표시하지 않습니다.")
            else:
                if result["reasons"]:
                    st.warning("가능하면 오늘 의료기관에 전화해 상담·진료 방법을 확인하세요. 호흡곤란·흉통이 심하거나 지속되면 119에 연락하세요. 이동할 수 없다면 주변 도움을 요청하세요.")
                else:
                    st.info("현재 선택 내용에서 특정 응급 신호가 보고되지 않았을 뿐, 안전이 확인된 것은 아닙니다. 악화·새 증상·지속 증상이 있으면 진료를 받으세요.")
            for reason in result["reasons"]:
                st.write("• " + reason)
            if not result["emergency"]:
                st.markdown("### 증상별 대처 방법")
                st.caption("원인 치료가 아닌 상담 전 임시 대처입니다. 처방받은 수분 제한·질환별 관리 지침이 있으면 의료진 지침을 우선하세요. 새 응급 신호가 생기면 아래 관리보다 119가 우선입니다.")
                if not result["symptom_care"]:
                    st.write("확인된 증상이 없어 맞춤 대처를 안내할 수 없습니다. 실제 있는 증상을 선택한 뒤 다시 확인하세요.")
                for item in result["symptom_care"]:
                    st.markdown("#### " + item["symptom"])
                    st.write("지금 할 수 있는 대처: " + item["care"])
                    st.write("진료·응급 전환 기준: " + item["warning"])
                st.markdown("### 가능한 원인·질환 후보 (확정 아님)")
                if not result["candidates"]:
                    st.write("입력된 증상으로 설명할 수 있는 후보가 없습니다. 정상이라는 뜻이 아니며 의료진의 평가가 필요합니다.")
                for rule in result["candidates"]:
                    matched = sorted(set(payload["symptoms"]) & set().union(*rule["groups"]))
                    with st.expander(rule["name"], expanded=True):
                        st.write("선택 증상과의 연결: " + ", ".join(matched))
                        st.write("가능한 설명: " + rule["why"])
                        st.write("확인할 점: " + rule["limits"])
                        st.write("상담을 기다리는 동안: " + rule["care"])
            st.info("결과와 대처 방법은 모두 이 화면에 표시됩니다. 별도 파일 다운로드는 필요하지 않습니다. 증상이 악화되거나 새 증상이 생기면 다시 평가받으세요.")
        if st.button("입력·결과 모두 지우기", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


if __name__ == "__main__":
    main()
