"""집에서 체크 — Streamlit Community Cloud에서 health_check.py로 실행.
설치: pip install -r requirements.txt
실행: streamlit run health_check.py
선택 설정: Streamlit Secrets에 PUBLIC_APP_URL = "https://your-app.streamlit.app".
임상 검증 전 교육용 시제품. 질병 진단/치료/처방 또는 의료기기가 아님.
"""
from datetime import datetime
from io import BytesIO
from urllib.parse import urlparse
import re
import streamlit as st
import qrcode

SOURCES = {
    "응급 도움을 요청해야 하는 상황 (NHS)": "https://www.nhs.uk/nhs-services/urgent-and-emergency-care-services/when-to-call-999/",
    "뇌졸중 증상 (NHS)": "https://www.nhs.uk/conditions/stroke/symptoms/",
    "가슴 통증 (NHS)": "https://www.nhs.uk/symptoms/chest-pain/",
}
RED_FLAGS = [
    "심한 호흡곤란 / 입술이 파래짐 / 말하기 힘든 숨참",
    "지속되는 갑작스러운 가슴 통증 또는 압박감",
    "갑작스러운 한쪽 마비·얼굴 처짐·말이 어눌해짐 (지금 호전되어도 포함)",
    "의식 저하 / 실신 후 회복되지 않음 / 경련",
    "멈추지 않는 심한 출혈 / 피를 토함 / 검은 변과 심한 어지럼",
    "목·혀가 붓거나 숨쉬기 힘든 알레르기 반응",
    "갑작스럽고 매우 심한 두통 / 심한 복통",
    "자해·자살 충동으로 지금 안전을 지키기 어려움",
]
CATEGORIES = {
    "호흡기·감기 증상": ["기침", "콧물", "인후통", "가래", "숨참"],
    "소화기·복부 증상": ["복통", "메스꺼움", "구토", "설사", "변비"],
    "머리·신경 증상": ["두통", "어지럼", "저림", "시야 변화"],
    "피부·알레르기 증상": ["가려움", "발진", "두드러기", "붓기"],
    "근육·관절 증상": ["근육통", "관절통", "허리 통증", "움직임 제한"],
    "비뇨기 증상": ["배뇨통", "잦은 소변", "혈뇨", "옆구리 통증"],
    "마음·수면 증상": ["불안", "우울감", "불면", "심한 스트레스"],
    "기타 / 잘 모르겠음": ["피로", "발열", "식욕 저하", "기타"],
}
DISEASES = ["해당 없음 / 잘 모르겠음", "고혈압", "당뇨병", "천식", "심장질환", "신장질환", "간질환", "암 치료 중", "기타 질환"]


def assess(data):
    """보수적 안내용 규칙. 진단 점수나 검증된 임상 분류가 아니다."""
    if data['red_flags']:
        return 'emergency', ['선택한 응급 신호가 있습니다.']
    reasons = []
    # 미확인 또는 불확실한 응급 선별은 낮은 위험으로 처리하지 않는다.
    if data['emergency_status'] != '위 항목에 해당하지 않음':
        reasons.append('응급 신호 유무를 확실하게 확인하지 못했습니다.')
    if data['severity'] >= 7:
        reasons.append('증상의 불편 정도가 높습니다.')
    if data['worsening']:
        reasons.append('증상이 악화되고 있습니다.')
    if data['daily_problem']:
        reasons.append('수분 섭취·소변·일상 활동 유지가 어렵습니다.')
    if data['temperature'] is not None and data['temperature'] >= 38:
        reasons.append('입력한 체온이 38°C 이상입니다. 체온만으로 원인을 판단할 수 없습니다.')
    if data['duration'] in ['3~6일', '1주 이상']:
        reasons.append('증상이 지속되고 있습니다.')
    if data['vulnerable'] or any(x != DISEASES[0] for x in data['diseases']):
        reasons.append('연령·임신·면역 상태 또는 기저질환을 고려한 개별 상담이 필요합니다.')
    if any(x in data['symptoms'] for x in ['숨참', '시야 변화', '혈뇨', '옆구리 통증']):
        reasons.append('선택 증상은 의료진의 확인이 필요합니다.')
    return ('prompt', reasons) if reasons else ('consult', ['선택 항목만으로 원인이나 안전성을 판단할 수 없습니다.'])


def valid_public_url(value):
    try:
        p = urlparse(value.strip())
        host = p.hostname or ''
        return (p.scheme == 'https' and bool(host) and not p.username and not p.password
                and host not in ['localhost', '127.0.0.1', '0.0.0.0']
                and not p.query and not p.fragment and not re.match(r'^\d+\.\d+\.\d+\.\d+$', host))
    except ValueError:
        return False


def clear_inputs():
    for key in list(st.session_state):
        del st.session_state[key]


def main():
    st.set_page_config(page_title='집에서 체크 | 증상·진료 안내', page_icon='🌿', layout='centered')
    st.markdown('''<style>
    .stApp {background:#f6faf9;}
    .block-container {max-width:760px;padding-top:2rem;padding-bottom:3rem;}
    h1,h2,h3 {color:#154e48;}
    .stButton>button {min-height:48px;border-radius:12px;}
    div[data-testid="stTextArea"] textarea {font-size:16px;}
    </style>''', unsafe_allow_html=True)
    st.title('🌿 집에서 체크')
    st.caption('스마트폰으로 증상을 정리하고, 다음 행동을 확인하세요.')
    st.error('🚑 심한 숨참, 지속되는 가슴 통증, 갑작스러운 마비·언어 이상 등이 있다면 입력을 중단하고 대한민국에서는 119에 연락하세요. 해외에서는 현지 응급번호를 이용하세요.')
    st.warning('이 앱은 교육용 시제품입니다. 질병을 확정하거나 응급질환을 배제하지 못하며 진료·처방을 대체하지 않습니다. 병원에 갈 수 없더라도 응급 상황에서는 도움을 요청해야 합니다.')
    tab_check, tab_qr, tab_info = st.tabs(['증상 확인', 'QR로 열기', '이용 안내'])
    with tab_check:
        st.button('입력과 결과 초기화', on_click=clear_inputs, use_container_width=True)
        consent = st.checkbox('앱의 한계를 이해했으며, 이름·주민번호·연락처 등 식별정보를 입력하지 않겠습니다.', key='consent')
        st.subheader('1. 먼저 응급 신호를 확인하세요')
        flags = st.multiselect('현재 해당하는 항목을 모두 선택하세요', RED_FLAGS, key='flags')
        if flags:
            st.error('다른 입력이나 결과를 기다리지 말고 119 또는 현지 응급서비스에 도움을 요청하세요. 혼자 운전하지 마세요.')
            st.link_button('대한민국 응급의료포털 E-Gen', 'https://www.e-gen.or.kr/', use_container_width=True)
        emergency_status = st.radio('위 응급 항목을 확인했나요?', ['아직 확인하지 않음', '위 항목에 해당하지 않음', '잘 모르겠음'], key='emergency_status')
        if emergency_status == '잘 모르겠음':
            st.warning('응급인지 판단하기 어렵고 상태가 심하거나 빠르게 나빠지면 119에 상담·도움을 요청하세요.')
        st.subheader('2. 증상과 건강 상태')
        category = st.selectbox('주된 증상 카테고리', list(CATEGORIES), key='category')
        symptoms = st.multiselect('해당 증상 (복수 선택)', CATEGORIES[category], key='symptoms_' + category)
        diseases = st.multiselect('알고 있는 기저질환 (질병명으로 진단하는 기능은 아닙니다)', DISEASES, key='diseases')
        age = st.selectbox('연령대', ['선택하세요', '만 18~64세', '만 65세 이상', '만 18세 미만'], key='age')
        vulnerable = st.multiselect('추가로 고려할 상태', ['임신 중 / 출산 후', '면역저하 / 면역억제제 사용'], key='vulnerable')
        if age == '만 18세 미만':
            st.warning('소아·청소년용 평가 규칙은 제공하지 않습니다. 보호자와 함께 의료진에게 상담하세요. 영아의 발열·수유 저하 등은 지체하지 말고 의료진에게 문의하세요.')
        duration = st.selectbox('증상이 시작된 시점', ['24시간 이내', '1~2일', '3~6일', '1주 이상'], key='duration')
        severity = st.slider('주관적 불편 정도 (0=불편 없음, 10=가장 심함)', 0, 10, 3, key='severity')
        measured = st.checkbox('체온계로 측정한 체온이 있습니다', key='measured')
        temperature = st.number_input('측정 체온 (°C)', 30.0, 45.0, 36.5, 0.1, key='temperature') if measured else None
        worsening = st.checkbox('시간이 지나면서 증상이 악화됩니다', key='worsening')
        daily_problem = st.checkbox('물을 마시거나 유지하기 어렵거나 소변이 크게 줄고, 일상 활동이 어렵습니다', key='daily_problem')
        detail = st.text_area('상태를 자세히 적어주세요', placeholder='예: 어제 저녁부터 목이 아프고 기침이 있습니다. 체온은 37.4도이며 물은 마실 수 있습니다. 복용약·알레르기가 있다면 적어주세요.', max_chars=3000, height=150, key='detail')
        st.caption('자유 서술은 요약문에 그대로 포함됩니다. AI 또는 자연어 분석을 하지 않으며, 응급 표현을 자동 판독하지 않습니다. 중요한 신호는 위 항목에도 반드시 표시하세요.')
        if st.button('다음 행동 안내 확인', type='primary', use_container_width=True):
            st.session_state.pop('result', None)
            if not consent:
                st.warning('앱의 한계와 개인정보 안내를 먼저 확인해주세요.')
            elif age == '선택하세요':
                st.warning('연령대를 선택해주세요.')
            elif not symptoms and not detail.strip() and not flags:
                st.warning('증상을 선택하거나 상세 상태를 입력해주세요.')
            else:
                data = dict(red_flags=flags, emergency_status=emergency_status, symptoms=symptoms,
                            diseases=diseases, severity=severity, worsening=worsening,
                            daily_problem=daily_problem, temperature=temperature, duration=duration,
                            vulnerable=bool(vulnerable) or age != '만 18~64세')
                level, reasons = assess(data)
                titles = {'emergency':'지금 응급 도움을 요청하세요', 'prompt':'가능한 한 오늘 의료진과 상담하세요', 'consult':'의료진 상담을 계획하고 변화를 관찰하세요'}
                report = '\n'.join([
                    '집에서 체크 — 의료진에게 보여줄 증상 메모 (진단서 아님)',
                    '작성 시각 (UTC): ' + datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
                    '연령: ' + age, '증상 분류: ' + category,
                    '선택 증상: ' + (', '.join(symptoms) or '없음'),
                    '기저질환: ' + (', '.join(diseases) or '미입력'),
                    '추가 상태: ' + (', '.join(vulnerable) or '없음'),
                    '기간: ' + duration, '불편 정도: ' + str(severity) + '/10',
                    '측정 체온: ' + (str(temperature) + '°C' if temperature is not None else '미측정'),
                    '악화: ' + ('예' if worsening else '아니오'),
                    '수분·소변·일상 어려움: ' + ('예' if daily_problem else '아니오'),
                    '응급 확인: ' + emergency_status,
                    '응급 신호: ' + (', '.join(flags) or '선택 없음'),
                    '상세 상태 (자동 분석하지 않음): ' + (detail.strip() or '미입력'),
                    '안내: ' + titles[level], '근거: ' + ' / '.join(reasons),
                    '검증되지 않은 규칙 기반 안내이며 의료진 판단을 대체하지 않습니다.'
                ])
                st.session_state.result = dict(level=level, title=titles[level], reasons=reasons, report=report)
        result = st.session_state.get('result')
        if result:
            st.divider()
            st.subheader('다음 행동 안내')
            st.caption('아래 결과는 마지막으로 확인 버튼을 누른 시점의 입력입니다. 내용을 변경했다면 다시 확인하세요.')
            if result['level'] == 'emergency':
                st.error(result['title'] + ' — 대한민국 119 / 해외 현지 응급번호')
            else:
                st.warning(result['title'])
            for reason in result['reasons']:
                st.write('• ' + reason)
            st.write('이 결과가 응급질환이 없다는 뜻은 아닙니다. 새로운 응급 신호가 생기거나 빠르게 악화되면 즉시 도움을 요청하세요. 이동이 어렵다면 보호자·지인에게 도움을 요청하고, 의료기관에 전화하여 가능한 상담과 진료 방법을 확인하세요.')
            st.info('상담 전에는 무리하지 말고 쉬세요. 마실 수 있고 수분 제한 지시가 없다면 조금씩 수분을 섭취하세요. 기존 처방약을 임의로 중단·증량하거나 새 약을 임의로 복용하지 마세요.')
            st.download_button('증상 메모 내려받기 (.txt)', result['report'], file_name='symptom_note.txt', mime='text/plain', use_container_width=True)
            st.caption('다운로드한 메모에는 건강정보가 포함됩니다. 공유 기기에 남기지 않도록 주의하세요.')
    with tab_qr:
        st.subheader('QR로 앱 열기')
        st.write('GitHub에 올린 뒤 Streamlit Community Cloud에 배포한 공개 HTTPS 주소를 입력하세요. GitHub 저장소 주소가 아니라 실행 중인 앱 주소여야 합니다.')
        try:
            default_url = str(st.secrets.get('PUBLIC_APP_URL', ''))
        except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
            default_url = ''
        url = st.text_input('배포된 앱 주소', value=default_url, placeholder='https://your-app.streamlit.app', key='public_url').strip()
        if st.button('QR 만들기', use_container_width=True):
            if not valid_public_url(url):
                st.error('쿼리·앵커·로그인 정보가 없는 공개 HTTPS 주소를 입력하세요. 로컬 주소는 스마트폰에서 사용할 수 없습니다.')
            else:
                image = qrcode.make(url)
                buf = BytesIO()
                image.save(buf, format='PNG')
                st.session_state.qr_result = (url, buf.getvalue())
        if 'qr_result' in st.session_state:
            qr_url, qr_bytes = st.session_state.qr_result
            st.image(qr_bytes, width=240, caption='연결 주소: ' + qr_url)
            st.download_button('QR 이미지 내려받기', qr_bytes, 'app_qr.png', 'image/png')
        st.caption('QR에는 앱 주소만 포함합니다. 입력한 증상이나 건강정보는 넣지 않습니다. 주소를 바꾸면 QR도 다시 만드세요.')
    with tab_info:
        st.subheader('배포 방법')
        st.markdown('1. GitHub 저장소에 **health_check.py**, **requirements.txt** 두 파일을 올립니다.\n2. Streamlit Community Cloud에서 저장소와 브랜치를 연결하고 실행 파일을 **health_check.py**로 지정합니다.\n3. 배포 후 표시되는 HTTPS 주소로 앱을 엽니다.\n4. QR 탭에 그 주소를 넣고 QR을 내려받습니다.\n5. 선택 사항: 앱 설정의 Secrets에 `PUBLIC_APP_URL = "배포된 HTTPS 주소"`를 넣으면 주소가 미리 채워집니다.')
        st.subheader('개인정보와 한계')
        st.write('이 코드는 데이터베이스 저장·외부 AI 전송·사용자 추적 기능을 구현하지 않습니다. 입력은 앱 서버의 세션 메모리에서 처리되며, 새로고침·연결 종료 등으로 사라질 수 있습니다. 초기화 버튼으로 현재 세션의 입력과 결과를 지울 수 있습니다. 호스팅 제공자의 접속 로그·보안·보관 정책은 별도로 확인해야 합니다. 민감정보를 입력하지 마세요.')
        st.write('초기 버전은 성인 중심의 검증되지 않은 규칙 기반 시제품입니다. 자유 텍스트에서 질병이나 위험을 추론하지 않고, 질병별 가능성·확률·약물 용량을 제공하지 않습니다. 실제 공개 서비스 전 의료진의 규칙 검토, 소아·임신부 등 대상별 기준, 사용성 및 임상 안전성 검증, 개인정보 처리와 서비스 운영 검토가 필요합니다.')
        st.subheader('참고 자료')
        for name, link in SOURCES.items():
            st.markdown(f'- [{name}]({link})')
        st.caption('응급 증상 예시 참고: NHS. 이 앱의 전체 분류 규칙이 해당 기관에서 검증·승인되었다는 뜻은 아닙니다. 영국 자료의 응급번호 999가 아니라 대한민국에서는 119를 이용하세요. 참고 확인일: 2026-10-30.')
    st.caption('집에서 체크 · 증상 정리 및 진료 안내용 시제품 · 의료진의 진단을 대체하지 않습니다.')


if __name__ == '__main__':
    main()
