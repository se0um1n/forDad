"""장보기 알림 메모
실행: streamlit run app.py
배포: GitHub에 이 파일과 requirements.txt 업로드 → Streamlit Community Cloud
       → app.py 선택 → Deploy. 배포 주소를 앱의 'QR / 안내'에서 QR로 변환.
데이터: 접속별 세션 메모리. 새로고침/연결 종료/서버 재시작 시 사라질 수 있음.
QR은 앱 주소 공유용이며 장보기 데이터는 다른 기기와 공유되지 않음.
"""
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from uuid import uuid4

import qrcode
import streamlit as st


def line_total(unit_price, quantity):
    """원 단위 반올림. 부동소수점 합계 오차 방지."""
    return int((Decimal(str(unit_price)) * Decimal(str(quantity))).quantize(
        Decimal('1'), rounding=ROUND_HALF_UP))


def cart_total(items):
    return sum(line_total(x['price'], x['qty']) for x in items if x['status'] == 'cart')


CATEGORIES = ['🥬 야채', '🍎 과일', '🥩 육류·달걀', '🐟 수산물', '🥛 유제품',
              '🍚 쌀·곡물', '🍜 가공식품', '🧂 양념', '🧻 생활용품', '🛒 기타']
PRIORITIES = {1: '1 · 꼭 필요', 2: '2 · 가격이 괜찮으면', 3: '3 · 여유가 있으면'}


def main():
    st.set_page_config(page_title='장보기 메모', page_icon='🛒', layout='centered',
                       initial_sidebar_state='collapsed')
    st.markdown('''<style>
    .block-container {max-width:520px;padding:0.65rem 0.8rem 1rem;}
    [data-testid="stVerticalBlock"] {gap:0.38rem;}
    [data-testid="stHorizontalBlock"] {gap:0.45rem;}
    h1 {font-size:1.45rem !important;padding:0 !important;}
    p {margin-bottom:0.2rem;}
    [data-testid="stMetricValue"] {font-size:1.45rem;}
    [data-testid="stMetricLabel"] {font-size:0.78rem;}
    [data-testid="stForm"] {padding:0.55rem;border-radius:14px;}
    .stButton button, .stFormSubmitButton button {min-height:2.5rem;}
    [data-testid="stCaptionContainer"] {font-size:0.75rem;}
    </style>''', unsafe_allow_html=True)
    if 'items' not in st.session_state:
        st.session_state['items'] = []
    if 'notice' in st.session_state:
        st.toast(st.session_state.pop('notice'))
    items = st.session_state['items']
    st.title('🛒 장보기 메모')
    pending = [x for x in items if x['status'] == 'pending']
    held = [x for x in items if x['status'] == 'held']
    bought = [x for x in items if x['status'] == 'cart']
    a, b, c = st.columns(3)
    a.metric('살 물건', f'{len(pending)}종')
    b.metric('카트 / 보류', f'{len(bought)} / {len(held)}종')
    c.metric('카트 총액', f'{cart_total(items):,}원')

    with st.form('add', clear_on_submit=True, border=True):
        a, b = st.columns([1, 1.35])
        category = a.selectbox('카테고리', CATEGORIES, label_visibility='collapsed')
        name = b.text_input('상품명', placeholder='상품명 · 예: 방울토마토',
                            max_chars=50, label_visibility='collapsed')
        a, b = st.columns([1.7, 1])
        priority = a.selectbox('중요도', [1, 2, 3], format_func=PRIORITIES.get,
                               label_visibility='collapsed')
        add = b.form_submit_button('＋ 추가', use_container_width=True)
    if add:
        if not name.strip():
            st.warning('상품명을 적어 주세요.')
        elif len(items) >= 200:
            st.warning('최대 200개입니다. 불필요한 메모를 정리해 주세요.')
        else:
            items.append(dict(id=uuid4().hex, category=category, name=name.strip(),
                              priority=priority, status='pending', price=0, qty=1))
            st.session_state['notice'] = '장보기 목록에 추가했어요.'
            st.rerun()

    a, b = st.columns([1, 2])
    a.markdown('**살 물건**')
    scope = b.selectbox('목록 범위', ['살 물건', '보류한 물건'], label_visibility='collapsed')
    candidates = sorted(pending if scope == '살 물건' else held,
                        key=lambda x: (x['priority'], x['category'], x['name']))
    if candidates:
        lookup = {x['id']: x for x in candidates}
        selected_id = st.selectbox('장보기 상품 선택', list(lookup),
            format_func=lambda i: f"{lookup[i]['priority']}순위 | {lookup[i]['category']} · {lookup[i]['name']}",
            label_visibility='collapsed', key='selected_pending')
        item = lookup[selected_id]
        st.caption('1 꼭 필요 · 2 가격이 괜찮으면 · 3 여유가 있으면 | 비싸면 보류 가능')
        # 상품별 키를 써서 다른 상품의 가격/수량이 잘못 이어지지 않도록 함.
        with st.form(f"purchase_{item['id']}"):
            a, b = st.columns([1.4, 1])
            price = a.number_input('개당 가격(원)', min_value=0, max_value=100000000,
                                   value=0, step=100)
            qty = b.number_input('수량', min_value=1, max_value=10000, value=1, step=1)
            a, b = st.columns(2)
            buy = a.form_submit_button('🛒 담기', type='primary', use_container_width=True)
            hold = b.form_submit_button('↩ 다시 살 목록' if scope != '살 물건' else '비싸면 보류',
                                       use_container_width=True)
        if buy:
            if price <= 0:
                st.warning('실제 개당 가격을 1원 이상 입력해 주세요. 수량은 묶음 상품이면 묶음 수입니다.')
            else:
                item.update(status='cart', price=int(price), qty=int(qty))
                st.session_state['notice'] = f"{item['name']} · {line_total(price, qty):,}원 담았어요."
                st.rerun()
        if hold:
            item['status'] = 'pending' if scope != '살 물건' else 'held'
            st.session_state['notice'] = '다시 살 목록에 넣었어요.' if scope != '살 물건' else '삭제하지 않고 보류했어요.'
            st.rerun()
    else:
        st.caption('보류한 상품이 없어요.' if scope != '살 물건' else '상품을 추가해 주세요. 담은 상품은 아래 카트에서 확인해요.')

    # 접힌 영역으로 기본 화면 높이를 줄인다. 카트도 한 번에 한 품목씩 확인.
    with st.expander(f'🧾 카트 확인·수정 ({len(bought)}종) / 메모 삭제', expanded=False):
        if bought:
            lookup = {x['id']: x for x in bought}
            selected = st.selectbox('담은 상품', list(lookup), key='selected_cart',
                format_func=lambda i: f"{lookup[i]['name']} · {lookup[i]['qty']}개 · {line_total(lookup[i]['price'], lookup[i]['qty']):,}원")
            entry = lookup[selected]
            with st.form(f"edit_{entry['id']}_{entry['price']}_{entry['qty']}"):
                a, b = st.columns(2)
                new_price = a.number_input('개당 가격 수정(원)', min_value=1,
                    max_value=100000000, value=int(entry['price']), step=100)
                new_qty = b.number_input('수량 수정', min_value=1, max_value=10000,
                    value=int(entry['qty']), step=1)
                a, b = st.columns(2)
                save = a.form_submit_button('금액 수정', use_container_width=True)
                undo = b.form_submit_button('카트에서 빼기', use_container_width=True)
            if save:
                entry.update(price=int(new_price), qty=int(new_qty))
                st.rerun()
            if undo:
                entry.update(status='pending', price=0, qty=1)
                st.session_state['notice'] = '살 목록으로 복원하고 카트 합계에서 뺐어요.'
                st.rerun()
        else:
            st.caption('아직 카트가 비어 있어요.')
        deletable = [x for x in items if x['status'] != 'cart']
        if deletable:
            lookup_delete = {x['id']: x for x in deletable}
            with st.form('delete_note'):
                target = st.selectbox('필요 없는 메모 삭제', list(lookup_delete),
                    format_func=lambda i: f"{lookup_delete[i]['name']} ({'보류' if lookup_delete[i]['status'] == 'held' else '살 물건'})")
                if st.form_submit_button('선택한 메모 삭제'):
                    items[:] = [x for x in items if x['id'] != target]
                    st.rerun()

    with st.expander('📱 QR / 안내 / 내역 저장', expanded=False):
        st.caption('QR은 배포한 앱을 여는 용도입니다. 알림은 앱 안의 메모이며 푸시 알림은 아닙니다.')
        url = st.text_input('Streamlit 배포 주소', placeholder='https://your-app.streamlit.app')
        if url.strip():
            from urllib.parse import urlparse
            parsed = urlparse(url.strip())
            if parsed.scheme in ('https', 'http') and parsed.netloc:
                qr = qrcode.make(url.strip())
                buf = BytesIO()
                qr.save(buf, format='PNG')
                st.image(buf.getvalue(), width=150)
                st.download_button('QR 저장', buf.getvalue(), 'shopping_qr.png', 'image/png')
            else:
                st.caption('https://로 시작하는 실제 배포 주소를 입력해 주세요.')
        if items:
            import csv
            from io import StringIO
            text = StringIO()
            writer = csv.writer(text)
            writer.writerow(['카테고리', '상품명', '중요도', '상태', '개당가격(원)', '수량', '합계(원)'])
            labels = {'pending': '살 물건', 'held': '보류', 'cart': '카트'}
            for x in items:
                # 스프레드시트에서 상품명이 수식으로 실행되지 않도록 보호.
                safe_name = "'" + x['name'] if x['name'].startswith(('=', '+', '-', '@', '\t', '\r')) else x['name']
                writer.writerow([x['category'], safe_name, x['priority'], labels[x['status']],
                    x['price'] if x['status'] == 'cart' else '',
                    x['qty'] if x['status'] == 'cart' else '',
                    line_total(x['price'], x['qty']) if x['status'] == 'cart' else ''])
            st.download_button('장보기 내역 CSV 저장', text.getvalue().encode('utf-8-sig'),
                               'shopping.csv', 'text/csv')
        st.caption('각 접속의 임시 메모입니다. 새로고침·연결 종료·서버 재시작 시 데이터가 사라질 수 있으며 다른 기기와 동기화되지 않습니다. 중요한 내역은 CSV로 저장하세요.')
        st.caption('배포: 두 파일을 GitHub 저장소 루트에 올린 뒤 Streamlit Community Cloud에서 저장소와 app.py를 선택하세요. 배포 주소를 위에 붙여 QR을 만드세요.')


if __name__ == '__main__':
    main()
