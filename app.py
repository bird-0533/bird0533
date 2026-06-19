import streamlit as st
import anthropic
from elevenlabs import ElevenLabs
import streamlit.components.v1 as components
from PyPDF2 import PdfReader
from duckduckgo_search import DDGS
import os

# ====================
# 設定
# ====================
WAKE_WORD = "バード"

# 招待コード（簡易版 - 必要に応じて追加）
VALID_INVITE_CODES = [
    "BIRD2024TEST",
    "INVITE123ABC",
    # 必要なコードをここに追加
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

# PDFの最大文字数（変更可能）
MAX_PDF_CHARS = 50000

# ====================
# 招待コード認証（簡易版）
# ====================
def check_invite_code(code):
    """招待コードが有効かチェック"""
    return code in VALID_INVITE_CODES

def generate_invite_code():
    """新しい招待コードを生成（管理用）"""
    import random
    import string
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    return code

# ====================
# PDFテキスト抽出
# ====================
def extract_pdf_text(pdf_file):
    """PDFからテキストを抽出"""
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
# Web検索
# ====================
def web_search(query, max_results=3):
    """DuckDuckGoでWeb検索"""
    try:
        results = []
        with DDGS() as ddgs:
            for result in ddgs.text(query, max_results=max_results):
                results.append(
                    f"タイトル: {result.get('title', '')}\n"
                    f"内容: {result.get('body', '')}\n"
                    f"URL: {result.get('href', '')}\n"
                )
        return "\n".join(results) if results else "検索結果が見つかりませんでした。"
    except Exception as e:
        return f"検索エラー: {str(e)}"

# ====================
# Claude API
# ====================
def get_ai_response(question, api_key, context=""):
    """Claude APIで回答を生成"""
    client = anthropic.Anthropic(api_key=api_key)
    
    system_prompt = (
        f"あなたは「バード」という名前のAIアシスタントです。\n\n"
        f"以下の人物の考え方で回答してください：\n\n{MY_THINKING}"
    )
    
    if context:
        system_prompt += f"\n\n以下のドキュメントの内容に基づいて回答してください：\n\n{context}"
    
    message = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=4000,
        system=system_prompt,
        messages=[
            {"role": "user", "content": question}
        ]
    )
    return message.content[0].text

# ====================
# ElevenLabs音声合成
# ====================
def synthesize_voice(text, api_key, voice_id):
    """ElevenLabsで音声を合成"""
    client = ElevenLabs(api_key=api_key)
    
    audio_generator = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_multilingual_v2"
    )
    
    audio_bytes = b''.join(audio_generator)
    return audio_bytes

# ====================
# セッション状態の初期化
# ====================
def init_session_state():
    """セッション状態を初期化"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "mode" not in st.session_state:
        st.session_state.mode = "text"
    if "recognized_text" not in st.session_state:
        st.session_state.recognized_text = ""
    if "pdf_documents" not in st.session_state:
        st.session_state.pdf_documents = []
    if "selected_category" not in st.session_state:
        st.session_state.selected_category = "すべて"

# ====================
# 音声入力HTML
# ====================
def get_speech_recognition_html():
    """Web Speech APIのHTMLを返す"""
    return """
    <script>
    function startRecognition() {
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
            document.getElementById('status').innerText = '🎤 認識中...';
        };
        
        recognition.onresult = function(event) {
            const text = event.results[0][0].transcript;
            document.getElementById('result').value = text;
            document.getElementById('status').innerText = '✅ 認識完了';
            // Streamlitにテキストを渡す
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: text}, '*');
        };
        
        recognition.onerror = function(event) {
            document.getElementById('status').innerText = '❌ エラー: ' + event.error;
        };
        
        recognition.start();
    }
    </script>
    
    <div style="padding: 20px; border: 1px solid #ccc; border-radius: 10px; margin: 10px 0;">
        <button onclick="startRecognition()" style="padding: 10px 20px; font-size: 16px; background-color: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer;">
            🎤 マイクで話す
        </button>
        <p id="status" style="margin-top: 10px;">準備完了</p>
        <textarea id="result" style="width: 100%; height: 100px; margin-top: 10px;" placeholder="認識されたテキスト..."></textarea>
    </div>
    """

# ====================
# ログイン画面
# ====================
def show_login_screen():
    """ログイン画面を表示"""
    st.header("🔐 ログイン")
    
    # 管理者用：招待コード生成
    with st.expander("管理者用：招待コード生成"):
        st.write("※この機能はテスト用です。実際の運用では削除してください。")
        if st.button("招待コードを生成"):
            new_code = generate_invite_code()
            st.success(f"招待コード: {new_code}")
            st.info("このコードをユーザーに共有してください")
        
        st.caption("現在の有効なコード:")
        for code in VALID_INVITE_CODES:
            st.code(code)
    
    st.divider()
    
    # 招待コード入力
    invite_code = st.text_input("招待コードを入力してください", type="password")
    
    if st.button("認証", type="primary"):
        if check_invite_code(invite_code):
            st.session_state.authenticated = True
            st.session_state.invite_code = invite_code
            st.success("認証成功！アプリを起動しています...")
            st.rerun()
        else:
            st.error("無効な招待コードです")

# ====================
# サイドバー
# ====================
def show_sidebar():
    """サイドバーを表示"""
    # API設定
    st.sidebar.header("⚙️ API設定")
    
    # 環境変数から取得、なければ空文字
    default_claude = os.environ.get("CLAUDE_API_KEY", "")
    default_elevenlabs = os.environ.get("ELEVENLABS_API_KEY", "")
    default_voice = os.environ.get("ELEVENLABS_VOICE_ID", "")
    
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
    
    # ドキュメント管理
    st.sidebar.header("📄 ドキュメント管理")
    
    pdf_categories = ["就業規則", "性格情報", "仕事マニュアル", "その他"]
    
    # PDF追加
    with st.sidebar.expander("➕ PDFを追加"):
        uploaded_pdf = st.file_uploader("PDFをアップロード", type="pdf")
        pdf_category = st.selectbox("カテゴリ", pdf_categories)
        
        if uploaded_pdf is not None:
            if st.button("追加", key="add_pdf"):
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
                        st.success(f"「{uploaded_pdf.name}」を追加しました（{total_pages}ページ）")
                        st.rerun()
                    else:
                        st.warning("このファイルは既に追加されています")
                else:
                    st.error(pdf_text)
    
    # PDF一覧
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
    
    # カテゴリ選択
    if st.session_state.pdf_documents:
        st.sidebar.subheader("使用するカテゴリ")
        categories = ["すべて"] + pdf_categories
        st.session_state.selected_category = st.sidebar.selectbox("カテゴリ", categories)
    
    st.sidebar.divider()
    
    # ログアウト
    if st.sidebar.button("ログアウト"):
        st.session_state.authenticated = False
        st.rerun()
    
    return claude_api_key, elevenlabs_api_key, elevenlabs_voice_id

# ====================
# テキスト入力モード
# ====================
def show_text_mode(claude_api_key, elevenlabs_api_key, elevenlabs_voice_id):
    """テキスト入力モードを表示"""
    st.subheader("💬 質問を入力")
    st.write(f"「{WAKE_WORD}」を含めて質問してください")
    
    # PDF情報表示
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
            st.warning("サイドバーでAPIキーを入力してください")
        elif WAKE_WORD in user_input:
            question = user_input.replace(WAKE_WORD, "").strip()
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
                except Exception as e:
                    st.error(f"音声生成エラー: {str(e)}")
        else:
            st.warning(f"「{WAKE_WORD}」を含めて質問してください")

# ====================
# 音声入力モード
# ====================
def show_voice_mode(claude_api_key, elevenlabs_api_key, elevenlabs_voice_id):
    """音声入力モードを表示"""
    st.subheader("🎤 音声入力")
    st.write("マイクボタンを押して話してください")
    
    # PDF情報表示
    if st.session_state.pdf_documents:
        total_chars = sum(
            min(doc['total_chars'], MAX_PDF_CHARS) 
            for doc in st.session_state.pdf_documents
        )
        st.info(f"📄 {len(st.session_state.pdf_documents)}個のPDF読み込み中（合計{total_chars}文字）")
    
    # 音声認識コンポーネント
    components.html(get_speech_recognition_html(), height=300)
    
    st.write("---")
    
    # 手動入力（音声認識が動作しない場合の代替）
    recognized_text = st.text_area(
        "認識されたテキスト（編集可能）", 
        st.session_state.recognized_text, 
        height=100
    )
    use_web_search = st.checkbox("情報がない場合はWeb検索する", value=False)
    
    if st.button("送信", type="primary"):
        if not recognized_text:
            st.warning("テキストを入力してください")
        elif not claude_api_key or not elevenlabs_api_key or not elevenlabs_voice_id:
            st.warning("サイドバーでAPIキーを入力してください")
        elif WAKE_WORD in recognized_text:
            question = recognized_text.replace(WAKE_WORD, "").strip()
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
                except Exception as e:
                    st.error(f"音声生成エラー: {str(e)}")
        else:
            st.warning(f"「{WAKE_WORD}」を含めて話してください")

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
        ["📝 テキスト入力", "🎤 音声入力"],
        index=0 if st.session_state.mode == "text" else 1,
        horizontal=True
    )
    
    if mode == "📝 テキスト入力":
        st.session_state.mode = "text"
    else:
        st.session_state.mode = "voice"
    
    st.divider()
    
    # モード別表示
    if st.session_state.mode == "text":
        show_text_mode(claude_api_key, elevenlabs_api_key, elevenlabs_voice_id)
    else:
        show_voice_mode(claude_api_key, elevenlabs_api_key, elevenlabs_voice_id)

# ====================
# エントリーポイント
# ====================
if __name__ == "__main__":
    main()
