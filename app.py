import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import hmac
import hashlib
import base64
import requests
import json
import uuid

# Flask 앱 생성
app = Flask(__name__)
# CORS 설정 - 프론트엔드에서 오는 요청 허용
CORS(app, resources={r"/chat": {"origins": ["http://localhost:5000", "http://localhost:3000", "http://localhost:5173","https://movie-fr-six.vercel.app"]}})

# 환경변수에서 키 읽어오기
CLOVA_INVOKE_URL = os.environ.get('CHATBOT_INVOKE_URL')
CLOVA_SECRET_KEY = os.environ.get('CHATBOT_SECRET_KEY')

def generate_signature(secret_key, request_body_string):
    """CLOVA Chatbot API용 HMAC-SHA256 서명을 생성합니다."""
    secret_key_bytes = bytes(secret_key, 'UTF-8')
    request_body_bytes = bytes(request_body_string, 'UTF-8')
    
    # HMAC-SHA256 해시 생성
    signature = hmac.new(
        secret_key_bytes,
        request_body_bytes,
        hashlib.sha256
    ).digest()
    
    # Base64로 인코딩하여 문자열로 반환
    return base64.b64encode(signature).decode('UTF-8')

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'message': '챗봇 백엔드 API 서버입니다.',
        'endpoints': {
            '/chat': 'POST - 챗봇과 대화',
            '/health': 'GET - 서버 상태 확인'
        },
        'status': 'running'
    })

@app.route('/chat', methods=['POST'])
def chat():
    try:
        # 환경변수 확인
        if not CLOVA_INVOKE_URL or not CLOVA_SECRET_KEY:
            return jsonify({'reply': '챗봇 설정이 올바르지 않습니다. 관리자에게 문의해주세요.'}), 500

        # 리액트가 보낸 메시지 받기
        request_data = request.get_json(silent=True)
        if not isinstance(request_data, dict):
            return jsonify({'reply': '올바른 JSON 객체가 필요합니다.'}), 400
        
        user_message = request_data.get('message', '')
        if not user_message.strip():
            return jsonify({'reply': '메시지를 입력해주세요.'}), 400

        print(f"사용자 메시지: {user_message}")

        # 현재 시간을 밀리초 단위로 변환
        timestamp_millis = int(time.time() * 1000)
        
        # API 요청 본문 구성
        request_body = {
            'version': 'v2',
            'userId': str(uuid.uuid4()),
            'timestamp': timestamp_millis,
            'bubbles': [
                {
                    'type': 'text',
                    'data': {'description': user_message}
                }
            ],
            'event': 'send'
        }
        
        # 요청 본문을 JSON 문자열로 변환 (한글 처리 개선)
        request_body_string = json.dumps(request_body, ensure_ascii=False)

        # API 서명 생성
        signature = generate_signature(CLOVA_SECRET_KEY, request_body_string)
        
        # API 호출 헤더 구성
        headers = {
            'Content-Type': 'application/json; charset=UTF-8',
            'X-NCP-CHATBOT_SIGNATURE': signature
        }

        # CLOVA API에 요청 보내기 (수정: /message 제거)
        response = requests.post(
            CLOVA_INVOKE_URL,  # /message 제거됨
            data=request_body_string,
            headers=headers,
            timeout=10
        )
        
        response.raise_for_status()
        
        # CLOVA 챗봇의 답변 파싱
        response_data = response.json()
        print(f"클로바 응답: {response_data}")
        
        # 챗봇의 답변 텍스트 추출
        if 'bubbles' in response_data and len(response_data['bubbles']) > 0:
            bot_reply = response_data['bubbles'][0]['data']['description']
        else:
            bot_reply = "죄송합니다. 응답을 생성할 수 없습니다."
        
        print(f"최종 답변: {bot_reply}")
        return jsonify({'reply': bot_reply})

    except requests.exceptions.RequestException as e:
        print(f"API 호출 오류: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"상태 코드: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
            
            if e.response.status_code == 404:
                error_msg = "챗봇 API 주소가 올바르지 않습니다."
            elif e.response.status_code in [401, 403]:
                error_msg = "챗봇 인증에 실패했습니다."
            else:
                error_msg = f"챗봇 서비스 오류 ({e.response.status_code})"
        else:
            error_msg = "챗봇 서비스에 연결할 수 없습니다."
        
        return jsonify({'reply': error_msg}), 500
    
    except Exception as e:
        print(f"기타 오류: {e}")
        return jsonify({'reply': '서버 내부 오류가 발생했습니다.'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': '백엔드 서버가 정상 작동 중입니다.'})

if __name__ == '__main__':
    print("백엔드 서버를 시작합니다...")
    print(f"CLOVA API URL: {CLOVA_INVOKE_URL[:50] + '...' if CLOVA_INVOKE_URL else 'None'}")
    print(f"CLOVA SECRET KEY: {'설정됨' if CLOVA_SECRET_KEY else '설정되지 않음'}")
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)