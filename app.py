import streamlit as st
import anthropic
from elevenlabs import ElevenLabs
import streamlit.components.v1 as components
from PyPDF2 import PdfReader
from duckduckgo_search import DDGS
import os
import base64

# ====================
# 設定
# ====================
WAKE_WORD = "バード"

# 管理者用招待コード
ADMIN_INVITE_CODES = [
    "ADMIN_BIRD_2025",
]

# 一般ユーザー用招待コード
USER_INVITE_CODES = [
    "BIRD2024TEST",
    "INVITE123ABC",
    "EMPLOYEE001",
]

# あなたの考え
MY_THINKING = """
【私の性格・価値観】
- 慎重派でリスクを避ける傾向がある
- 長期的な視点で判断する
- 実用性を重視する

【判断基準】
- 予算内 → 即決
- 予算超過10%以内 → 自分で判断
- 予算超過10%以上 → 上司確認

【返信の基準】
- クレーム → 24時間以内に対応
- 一般質問 → 48時間以内
- 単なる報告 → 週次でまとめて返信

【過去の判断例】
例1）取引先から値下げ要求 → 条件付きで承認（品質は妥協しない）
例2）部下の休暇申請（繁忙期）→ 承認（体調管理を優先）
例3）急ぎの依頼が重複 → 上長判断を優先
"""

MAX_PDF_CHARS = 50000

# ====================
# 招待コード認証
# ====================
def check_invite_code(code):
    if code in ADMIN_INVITE_CODES:
        return True, True
    elif code in USER_INVITE_CODES:
        return True, False
    else:
        return False, False

def generate_invite_code():
    import random
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

# ====================
# PDFテキスト抽出
# ====================
def extract_pdf_text(pdf_file):
    try:
        reader = PdfReader(pdf_file)
        text = ""
        total_pages = len(reader.pages)
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text, total_pages
    except Exception as e:
        return f"PDF読み込みエラー: {str(e)}", 0

# ====================
# Web検索（改善版）
# ====================
def web_search(query, max_results=3):
    try:
        results = []
        
        search_query = query
        search_query = search_query.replace("について教えて", "")
        search_query = search_query.replace("について", "")
        search_query = search_query.replace("教えて", "")
        search_query = search_query.replace("とは", "")
        search_query = search_query.replace("とは何", "")
        search_query = search_query.strip()
        
        search_query_en = search_query
        
        translations = {
            "有給休暇": "paid leave Japan",
            "有給": "paid leave Japan",
            "休暇": "vacation Japan",
            "残業": "overtime Japan",
            "給与": "salary Japan",
            "勤務": "work Japan",
            "退職": "resignation Japan",
            "採用": "hiring Japan",
            "労働": "labor Japan",
            "契約": "contract Japan",
        }
        
        for jp, en in translations.items():
            if jp in search_query:
                search_query_en = f"{search_query} {en}"
                break
        
        with DDGS() as ddgs:
            for result in ddgs.text(search_query_en, max_results=max_results):
                results.append(
                    f"タイトル: {result.get('title', '')}\n"
                    f"内容: {result.get('body', '')[:300]}...\n"
                    f"URL: {result.get('href', '')}\n"
                )
        
        if results:
            return f"【検索クエリ: {search_query_en}】\n\n" + "\n".join(results)
        else:
            return f"「{search_query}」の検索結果が見つかりませんでした。\nヒント: より具体的なキーワードで試してください。"
            
    except Exception as e:
        return f"検索エラー: {str(e)}\nしばらく時間を置いてから再試行してください。"

# ====================
# Claude API
# ====================
def get_ai_response(question, api_key, context=""):
    client = anthropic.Anthropic(api_key=api_key)
    
    system_prompt = (
        f"あなたは「バード」という名前のAIアシスタントです。\n\n"
        f"以下の人物の考え方で回答してください：\n\n{MY_THINKING}"
    )
    
    if context:
        system_prompt += f"\n\n以下のドキュメントの内容に基づいて回答してください：\n\n{context}"
    
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": question}]
    )
    return message.content[0].text

# ====================
# ElevenLabs音声合成
# ====================
def synthesize_voice(text, api_key, voice_id):
    client = ElevenLabs(api_key=api_key)
    
    audio_generator = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_multilingual_v2"
    )
    
    return b''.join(audio_generator)

# ====================
# 音声自動再生
# ====================
def play_audio_autoplay(audio_bytes):
    """音声を自動再生"""
    audio_base64 = base64.b64encode(audio_bytes).decode()
    audio_html = f"""
    <audio autoplay>
        <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
        お使いのブラウザは音声再生に対応していません。
    </audio>
    """
    components.html(audio_html, height=0)

# ====================
# セッション状態初期化
# ====================
def init_session_state():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    if "mode" not in st.session_state:
        st.session_state.mode = "text"
    if "recognized_text" not in st.session_state:
        st.session_state.recognized_text = ""
    if "pdf_documents" not in st.session_state:
        st.session_state.pdf_documents = []
    if "selected_category" not in st.session_state:
        st.session_state.selected_category = "すべて"
    if "autoplay" not in st.session_state:
        st.session_state.autoplay = True
    if "speech_text" not in st.session_state:
        st.session_state.speech_text = ""

# ====================
# 音声認識コンポーネント（自動転送版）
# ====================
def create_speech_component(key="speech"):
    """音声認識コンポーネントを作成し、認識テキストを返す"""
    
    html_code = """
    <div style="padding: 15px; border: 1px solid #ccc; border-radius: 10px; margin: 10px 0;">
        <button id="startBtn" style="padding: 12px 24px; font-size: 16px; background-color: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer; margin-right: 10px;">
            🎤 マイクで話す
        </button>
        <button id="clearBtn" style="padding: 12px 24px; font-size: 16px; background-color: #f44336; color: white; border: none; border-radius: 5px; cursor: pointer;">
            🗑️ クリア
        </button>
        <p id="status" style="margin-top: 10px; color: gray;">準備完了 - マイクボタンを押して話してください</p>
        <textarea id="result" style="width: 100%; height: 80px; margin-top: 10px; font-size: 16px; padding: 10px; border: 1px solid #ddd; border-radius: 5px;" placeholder="認識されたテキスト..."></textarea>
    </div>

    <script>
    // 親ウィンドウに値を送信する関数
    function sendToStreamlit(text) {
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            data: text
        }, '*');
    }
    
    document.getElementById('startBtn').addEventListener('click', function() {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            alert('お使いのブラウザは音声認識に対応していません。');
            return;
        }
        
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        recognition.lang = 'ja-JP';
        recognition.continuous = false;
        recognition.interimResults = false;
        
        recognition.onstart = function() {
            document.getElementById('status').innerText = '🎤 認識中... 話してください';
            document.getElementById('status').style.color = 'blue';
        };
        
        recognition.onresult = function(event) {
            const text = event.results[0][0].transcript;
            document.getElementById('result').value = text;
            document.getElementById('status').innerText = '✅ 認識完了！自動的に転送されます...';
            document.getElementById('status').style.color = 'green';
            
            // Streamlitに値を送信
            sendToStreamlit(text);
        };
        
        recognition.onerror = function(event) {
            let errorMessage = '❌ エラー: ';
            switch(event.error) {
                case 'network':
                    errorMessage += 'ネットワークエラー\\nVPNをオフにするか、別のネットワークで試してください';
                    break;
                case 'not-allowed':
                    errorMessage += 'マイクの使用が許可されていません';
                    break;
                case 'no-speech':
                    errorMessage += '音声が検出されませんでした';
                    break;
                default:
                    errorMessage += event.error;
            }
            document.getElementById('status').innerText = errorMessage;
            document.getElementById('status').style.color = 'red';
            alert(errorMessage);
        };
        
        recognition.start();
    });
    
    document.getElementById('clearBtn').addEventListener('click', function() {
        document.getElementById('result').value = '';
        document.getElementById('status').innerText = '準備完了';
        document.getElementById('status').style.color = 'gray';
        sendToStreamlit('');
    });
    </script>
    """
    
    # コンポーネントを表示し、結果を取得
    result = components.html(html_code, height=200)
    return result

# ====================
# 常にマイクモード用コンポーネント
# ====================
def create_continuous_speech_component(wake_word="バード"):
    """常にマイクモード用の音声認識コンポーネント"""
    
    html_code = f"""
    <div style="padding: 20px; border: 1px solid #4CAF50; border-radius: 10px; margin: 10px 0; background-color: #f9f9f9;">
        <p style="margin: 0 0 10px 0; font-weight: bold;">🎙️ 常にマイクモード</p>
        <p style="margin: 0 0 10px 0; font-size: 14px; color: #666;">
            「{wake_word}」と言ってから質問してください
        </p>
        <button id="startBtn" style="padding: 12px 24px; font-size: 16px; background-color: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer; margin-right: 10px;">
            🎤 開始
        </button>
        <button id="stopBtn" style="padding: 12px 24px; font-size: 16px; background-color: #f44336; color: white; border: none; border-radius: 5px; cursor: pointer;">
            ⏹️ 停止
        </button>
        <p id="status" style="margin-top: 10px; color: gray;">準備完了</p>
        <p id="interim" style="margin-top: 5px; color: #666; font-size: 14px;"></p>
    </div>

    <script>
    let recognition = null;
    let isListening = false;
    const wakeWord = '{wake_word}';
    
    function sendToStreamlit(text) {{
        window.parent.postMessage({{
            type: 'streamlit:setComponentValue',
            data: text
        }}, '*');
    }}
    
    document.getElementById('startBtn').addEventListener('click', function() {{
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {{
            alert('お使いのブラウザは音声認識に対応していません。');
            return;
        }}
        
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.lang = 'ja-JP';
        recognition.continuous = true;
        recognition.interimResults = true;
        
        recognition.onstart = function() {{
            document.getElementById('status').innerText = '🎤 待機中...「{wake_word}」と話しかけてください';
            document.getElementById('status').style.color = 'blue';
            isListening = true;
        }};
        
        recognition.onresult = function(event) {{
            let interimTranscript = '';
            let finalTranscript = '';
            
            for (let i = event.resultIndex; i < event.results.length; i++) {{
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {{
                    finalTranscript += transcript;
                }} else {{
                    interimTranscript += transcript;
                }}
            }}
            
            const fullText = finalTranscript || interimTranscript;
            if (fullText.includes(wakeWord)) {{
                const question = fullText.replace(wakeWord, '').trim();
                if (question.length > 0) {{
                    document.getElementById('status').innerText = '✅ 質問を検出！自動的に転送されます';
                    document.getElementById('status').style.color = 'green';
                    sendToStreamlit(question);
                }}
            }}
            
            if (interimTranscript) {{
                document.getElementById('interim').innerText = '認識中: ' + interimTranscript;
            }}
        }};
        
        recognition.onerror = function(event) {{
            let msg = '❌ エラー: ';
            switch(event.error) {{
                case 'network':
                    msg += 'ネットワークエラー';
                    break;
                case 'not-allowed':
                    msg += 'マイクの使用が許可されていません';
                    break;
                default:
                    msg += event.error;
            }}
            document.getElementById('status').innerText = msg;
            document.getElementById('status').style.color = 'red';
        }};
        
        recognition.onend = function() {{
            if (isListening) {{
                try {{
                    recognition.start();
                }} catch (e) {{
                    console.log('再開エラー:', e);
                }}
            }}
        }};
        
        recognition.start();
    }});
    
    document.getElementById('stopBtn').addEventListener('click', function() {{
        if (recognition) {{
            isListening = false;
            recognition.stop();
            recognition = null;
            document.getElementById('status').innerText = '⏹️ 停止中';
            document.getElementById('status').style.color = 'gray';
        }}
    }});
    </script>
    """
    
    result = components.html(html_code, height=250)
    return result

# ====================
# ログイン画面
# ====================
def show_login_screen():
    st.header("🔐 ログイン")
    
    if st.session_state.get("show_admin_panel", False):
        with st.expander("🔑 管理者用：招待コード発行", expanded=True):
            st.write("**管理者用招待コード:**")
            for code in ADMIN_INVITE_CODES:
                st.code(code)
            st.write("**一般ユーザー用招待コード:**")
            for code in USER_INVITE_CODES:
                st.code(code)
            st.divider()
            if st.button("新しい招待コードを生成"):
                new_code = generate_invite_code()
                st.success(f"生成されたコード: {new_code}")
    
    if st.button("管理者オプションを表示"):
        st.session_state.show_admin_panel = True
        st.rerun()
    
    st.divider()
    
    invite_code = st.text_input("招待コードを入力してください", type="password")
    
    if st.button("認証", type="primary"):
        is_valid, is_admin = check_invite_code(invite_code)
        if is_valid:
            st.session_state.authenticated = True
            st.session_state.is_admin = is_admin
            st.session_state.invite_code = invite_code
            if is_admin:
                st.success("管理者として認証成功！")
            else:
                st.success("認証成功！")
            st.rerun()
        else:
            st.error("無効な招待コード")

# ====================
# サイドバー
# ====================
def show_sidebar():
    st.sidebar.header("⚙️ 設定")
    
    # APIキー取得
    try:
        default_claude = st.secrets["CLAUDE_API_KEY"]
    except:
        default_claude = ""
    
    try:
        default_elevenlabs = st.secrets["ELEVENLABS_API_KEY"]
    except:
        default_elevenlabs = ""
    
    try:
        default_voice = st.secrets["ELEVENLABS_VOICE_ID"]
    except:
        default_voice = ""
    
    # 管理者のみAPIキー入力可能
    if st.session_state.is_admin:
        st.sidebar.subheader("🔑 API設定（管理者）")
        claude_api_key = st.sidebar.text_input(
            "Claude APIキー", 
            type="password", 
            value=default_claude,
            help="console.anthropic.comで取得"
        )
        elevenlabs_api_key = st.sidebar.text_input(
            "ElevenLabs APIキー", 
            type="password", 
            value=default_elevenlabs,
            help="elevenlabs.ioで取得"
        )
        elevenlabs_voice_id = st.sidebar.text_input(
            "Voice ID", 
            type="password", 
            value=default_voice,
            help="ElevenLabsで作成したボイスのID"
        )
        
        # PDF管理（管理者のみ）
        st.sidebar.header("📄 ドキュメント管理")
        
        pdf_categories = ["就業規則", "性格情報", "仕事マニュアル", "その他"]
        
        with st.sidebar.expander("➕ PDFを追加"):
            uploaded_pdf = st.file_uploader("PDFをアップロード", type="pdf")
            pdf_category = st.selectbox("カテゴリ", pdf_categories)
            
            if uploaded_pdf and st.button("追加"):
                pdf_text, total_pages = extract_pdf_text(uploaded_pdf)
                if "エラー" not in pdf_text:
                    existing_names = [doc["name"] for doc in st.session_state.pdf_documents]
                    if uploaded_pdf.name not in existing_names:
                        st.session_state.pdf_documents.append({
                            "name": uploaded_pdf.name,
                            "category": pdf_category,
                            "text": pdf_text[:MAX_PDF_CHARS],
                            "total_pages": total_pages,
                            "total_chars": len(pdf_text)
                        })
                        st.success(f"「{uploaded_pdf.name}」を追加")
                        st.rerun()
                    else:
                        st.warning("既に追加されています")
                else:
                    st.error(pdf_text)
        
        with st.sidebar.expander("📚 登録済みPDF"):
            if st.session_state.pdf_documents:
                for i, doc in enumerate(st.session_state.pdf_documents):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"📄 {doc['name']} ({doc['total_pages']}ページ)")
                    with col2:
                        if st.button("削除", key=f"del_{i}"):
                            st.session_state.pdf_documents.pop(i)
                            st.rerun()
            else:
                st.write("PDFが登録されていません")
        
        if st.session_state.pdf_documents:
            st.sidebar.subheader("使用するカテゴリ")
            categories = ["すべて"] + pdf_categories
            st.session_state.selected_category = st.sidebar.selectbox("カテゴリ", categories)
    
    else:
        # 一般ユーザー：Secretsから自動取得
        claude_api_key = default_claude
        elevenlabs_api_key = default_elevenlabs
        elevenlabs_voice_id = default_voice
        
        st.sidebar.info("🔓 一般ユーザーモード")
        st.sidebar.caption("APIキーは管理者が設定済み")
    
    st.sidebar.divider()
    
    # 音声自動再生の切り替え
    st.sidebar.subheader("🔊 音声設定")
    autoplay = st.sidebar.checkbox(
        "音声を自動再生する", 
        value=st.session_state.autoplay,
        help="ON: 回答後に自動で音声再生 / OFF: 手動で再生ボタンを押す"
    )
    st.session_state.autoplay = autoplay
    
    st.sidebar.divider()
    
    # ユーザー情報表示
    if st.session_state.is_admin:
        st.sidebar.caption("👤 管理者")
    else:
        st.sidebar.caption("👤 一般ユーザー")
    
    if st.sidebar.button("ログアウト"):
        st.session_state.authenticated = False
        st.session_state.is_admin = False
        st.rerun()
    
    return claude_api_key, elevenlabs_api_key, elevenlabs_voice_id

# ====================
# テキスト入力モード
# ====================
def show_text_mode(claude_api_key, elevenlabs_api_key, elevenlabs_voice_id):
    st.subheader("💬 テキスト入力")
    st.write("質問を入力してください（ウェイクワード不要）")
    
    if st.session_state.pdf_documents:
        total_chars = sum(
            min(doc['total_chars'], MAX_PDF_CHARS) 
            for doc in st.session_state.pdf_documents
        )
        st.info(f"📄 {len(st.session_state.pdf_documents)}個のPDF読み込み中（合計{total_chars}文字）")
    
    user_input = st.text_area("質問を入力してください", height=100)
    use_web_search = st.checkbox("情報がない場合はWeb検索する", value=False)
    
    if st.button("送信", type="primary"):
        if not user_input:
            st.warning("質問を入力してください")
        elif not claude_api_key or not elevenlabs_api_key or not elevenlabs_voice_id:
            st.warning("APIキーが設定されていません。管理者にお問い合わせください。")
        else:
            question = user_input.strip()
            st.write(f"**質問:** {question}")
            
            # コンテキスト準備
            context = ""
            if st.session_state.pdf_documents:
                filtered_docs = st.session_state.pdf_documents
                if st.session_state.selected_category != "すべて":
                    filtered_docs = [
                        doc for doc in st.session_state.pdf_documents 
                        if doc["category"] == st.session_state.selected_category
                    ]
                for doc in filtered_docs:
                    context += f"\n\n=== {doc['name']} ===\n{doc['text']}"
            
            # AI回答
            with st.spinner("考え中..."):
                answer = get_ai_response(question, claude_api_key, context)
            
            st.write(f"**回答:** {answer}")
            
            # Web検索
            if use_web_search:
                with st.spinner("Web検索中..."):
                    search_results = web_search(question)
                st.write(f"**Web検索結果:**\n{search_results}")
            
            # 音声合成
            with st.spinner("音声生成中..."):
                try:
                    audio_bytes = synthesize_voice(answer, elevenlabs_api_key, elevenlabs_voice_id)
                    st.audio(audio_bytes, format="audio/mp3")
                    if st.session_state.autoplay:
                        play_audio_autoplay(audio_bytes)
                except Exception as e:
                    st.error(f"音声生成エラー: {str(e)}")

# ====================
# マイク押下モード
# ====================
def show_push_mic_mode(claude_api_key, elevenlabs_api_key, elevenlabs_voice_id):
    st.subheader("🎤 マイク押下モード")
    st.write("マイクボタンを押して話してください")
    
    if st.session_state.pdf_documents:
        total_chars = sum(
            min(doc['total_chars'], MAX_PDF_CHARS) 
            for doc in st.session_state.pdf_documents
        )
        st.info(f"📄 {len(st.session_state.pdf_documents)}個のPDF読み込み中（合計{total_chars}文字）")
    
    use_web_search = st.checkbox("情報がない場合はWeb検索する", value=False, key="web_search_push")
    
    # 音声認識コンポーネントを表示
    speech_result = create_speech_component(key="push_mic")
    
    # 認識結果があればセッション状態を更新
    if speech_result:
        st.session_state.speech_text = speech_result
    
    st.write("---")
    st.write("📝 **認識されたテキスト**")
    
    # テキストエリア（認識結果を反映）
    recognized_text = st.text_area(
        "認識されたテキスト（編集可能）", 
        value=st.session_state.get("speech_text", ""),
        height=100,
        key="text_area_push"
    )
    
    # 送信ボタン
    if st.button("送信", type="primary"):
        if not recognized_text or not recognized_text.strip():
            st.warning("テキストを入力してください。マイクボタンを押して話すか、手動で入力してください。")
        elif not claude_api_key or not elevenlabs_api_key or not elevenlabs_voice_id:
            st.warning("APIキーが設定されていません。管理者にお問い合わせください。")
        else:
            question = recognized_text.strip()
            st.write(f"**質問:** {question}")
            
            # コンテキスト準備
            context = ""
            if st.session_state.pdf_documents:
                filtered_docs = st.session_state.pdf_documents
                if st.session_state.selected_category != "すべて":
                    filtered_docs = [
                        doc for doc in st.session_state.pdf_documents 
                        if doc["category"] == st.session_state.selected_category
                    ]
                for doc in filtered_docs:
                    context += f"\n\n=== {doc['name']} ===\n{doc['text']}"
            
            # AI回答
            with st.spinner("考え中..."):
                answer = get_ai_response(question, claude_api_key, context)
            
            st.write(f"**回答:** {answer}")
            
            # Web検索
            if use_web_search:
                with st.spinner("Web検索中..."):
                    search_results = web_search(question)
                st.write(f"**Web検索結果:**\n{search_results}")
            
            # 音声合成
            with st.spinner("音声生成中..."):
                try:
                    audio_bytes = synthesize_voice(answer, elevenlabs_api_key, elevenlabs_voice_id)
                    st.audio(audio_bytes, format="audio/mp3")
                    if st.session_state.autoplay:
                        play_audio_autoplay(audio_bytes)
                except Exception as e:
                    st.error(f"音声生成エラー: {str(e)}")

# ====================
# 常にマイクモード
# ====================
def show_continuous_mic_mode(claude_api_key, elevenlabs_api_key, elevenlabs_voice_id):
    st.subheader("🎙️ 常にマイクモード")
    st.write(f"「{WAKE_WORD}」と言ってから質問してください")
    
    if st.session_state.pdf_documents:
        total_chars = sum(
            min(doc['total_chars'], MAX_PDF_CHARS) 
            for doc in st.session_state.pdf_documents
        )
        st.info(f"📄 {len(st.session_state.pdf_documents)}個のPDF読み込み中（合計{total_chars}文字）")
    
    use_web_search = st.checkbox("情報がない場合はWeb検索する", value=False, key="web_search_continuous")
    
    # 常にマイクモード用コンポーネント
    speech_result = create_continuous_speech_component(WAKE_WORD)
    
    # 認識結果があればセッション状態を更新
    if speech_result:
        st.session_state.speech_text = speech_result
    
    st.write("---")
    st.write("📝 **認識されたテキスト**")
    
    # テキストエリア（認識結果を反映）
    recognized_text = st.text_area(
        "認識された質問（編集可能）", 
        value=st.session_state.get("speech_text", ""),
        height=100,
        key="text_area_continuous"
    )
    
    # 送信ボタン
    if st.button("送信", type="primary"):
        if not recognized_text or not recognized_text.strip():
            st.warning("テキストを入力してください。")
        elif not claude_api_key or not elevenlabs_api_key or not elevenlabs_voice_id:
            st.warning("APIキーが設定されていません。管理者にお問い合わせください。")
        else:
            question = recognized_text.strip()
            st.write(f"**質問:** {question}")
            
            # コンテキスト準備
            context = ""
            if st.session_state.pdf_documents:
                filtered_docs = st.session_state.pdf_documents
                if st.session_state.selected_category != "すべて":
                    filtered_docs = [
                        doc for doc in st.session_state.pdf_documents 
                        if doc["category"] == st.session_state.selected_category
                    ]
                for doc in filtered_docs:
                    context += f"\n\n=== {doc['name']} ===\n{doc['text']}"
            
            # AI回答
            with st.spinner("考え中..."):
                answer = get_ai_response(question, claude_api_key, context)
            
            st.write(f"**回答:** {answer}")
            
            # Web検索
            if use_web_search:
                with st.spinner("Web検索中..."):
                    search_results = web_search(question)
                st.write(f"**Web検索結果:**\n{search_results}")
            
            # 音声合成
            with st.spinner("音声生成中..."):
                try:
                    audio_bytes = synthesize_voice(answer, elevenlabs_api_key, elevenlabs_voice_id)
                    st.audio(audio_bytes, format="audio/mp3")
                    if st.session_state.autoplay:
                        play_audio_autoplay(audio_bytes)
                except Exception as e:
                    st.error(f"音声生成エラー: {str(e)}")

# ====================
# メインアプリ
# ====================
def main():
    st.set_page_config(
        page_title="AIアシスタント「バード」",
        page_icon="🤖",
        layout="wide"
    )
    
    st.title("🤖 AIアシスタント「バード」")
    
    # セッション状態初期化
    init_session_state()
    
    # 認証チェック
    if not st.session_state.authenticated:
        show_login_screen()
        return
    
    # サイドバー表示
    claude_api_key, elevenlabs_api_key, elevenlabs_voice_id = show_sidebar()
    
    st.divider()
    
    # モード切り替え
    st.subheader("モード選択")
    mode = st.radio(
        "入力方法を選択",
        ["⌨️ テキスト入力", "🎤 マイク押下", "🎙️ 常にマイク"],
        index=0,
        horizontal=True
    )
    
    # モード別説明
    if mode == "⌨️ テキスト入力":
        st.caption("キーボードで入力します")
    elif mode == "🎤 マイク押下":
        st.caption("マイクボタンを押して話します（認識結果が自動転送されます）")
    else:
        st.caption(f"常にマイクが有効です。「{WAKE_WORD}」と言ってから質問してください")
    
    st.session_state.mode = mode
    
    st.divider()
    
    # モード別表示
    if mode == "⌨️ テキスト入力":
        show_text_mode(claude_api_key, elevenlabs_api_key, elevenlabs_voice_id)
    elif mode == "🎤 マイク押下":
        show_push_mic_mode(claude_api_key, elevenlabs_api_key, elevenlabs_voice_id)
    else:
        show_continuous_mic_mode(claude_api_key, elevenlabs_api_key, elevenlabs_voice_id)

# ====================
# エントリーポイント
# ====================
if __name__ == "__main__":
    main()
