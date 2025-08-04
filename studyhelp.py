# pip install google-genai requests

from google import genai
from google.genai import types
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch
import requests
import json
import os


# APIキーの取得（環境変数から）
os.environ['GOOGLE_API_KEY'] = 'AIzaSyAZuRCKW5ap98_M13q0To7FcUEkjS8F45s'
def get_api_key():
    try:
        # まずは環境変数から取得を試みる
        api_key = os.environ.get('GOOGLE_API_KEY')
        if api_key:
            return api_key
        
        # Google Colabの場合
        try:
            from google.colab import userdata
            return userdata.get('GOOGLE_API_KEY')
        except ImportError:
            # ローカル環境の場合、直接入力を求める
            print("GOOGLE_API_KEYが設定されていません。")
            print("環境変数に設定するか、直接入力してください：")
            return input("Google API Key: ").strip()
    except Exception as e:
        print(f"APIキーの取得でエラーが発生しました: {e}")
        return None




import json
import random

def load_terms():
    try:
        with open('terms.json', 'r', encoding='utf-8') as f:
            terms_data = json.load(f)
        return terms_data
    except FileNotFoundError:
        print("terms.jsonファイルが見つかりません。ファイルをアップロードしてください。")
        return None

# カテゴリに関係なく単語をランダムに選択する関数 (元の select_random_term を修正)
def select_random_term(terms_data):
    if not terms_data or "terms" not in terms_data:
        return None, None, None, None # answer, description, person, category

    all_terms = []
    for person_name, person_data in terms_data["terms"].items():
        category = person_data.get("category")
        if "terms" in person_data:
            for term_name, term_description in person_data["terms"].items():
                all_terms.append({
                    "answer": person_name if term_name == "人物像" else term_name,
                    "description": term_description,
                    "person": person_name,
                    "category": category
                })

    if all_terms:
        selected_item = random.choice(all_terms)
        return selected_item["answer"], selected_item["description"], selected_item["person"], selected_item["category"]
    return None, None, None, None

# カテゴリから単語をランダムに選択する関数 (修正なし、引数名を変更)
def select_random_term_from_category(terms_data, category):
    if not terms_data or "terms" not in terms_data:
        return None, None
    category_items = []
    for person_name, person_data in terms_data["terms"].items():
        if person_data.get("category") == category:
            # 人物の場合、その人物の用語からランダム選択
            if "terms" in person_data:
                for term_name, term_description in person_data["terms"].items():
                    category_items.append({
                        "answer": person_name if term_name == "人物像" else term_name,
                        "description": term_description,
                        "person": person_name,
                        "category": category
                    })

    if category_items:
        selected_item = random.choice(category_items)
        return selected_item, category_items
    return None, None


def get_available_categories(terms_data):
    if not terms_data or "terms" not in terms_data:
        return []
    
    categories = set()
    for person_data in terms_data["terms"].values():
        if "category" in person_data:
            categories.add(person_data["category"])
    
    return sorted(list(categories))






import unicodedata
import re

def create_system_instruction(terms_data):
    available_categories = get_available_categories(terms_data)
    categories_str = ", ".join([f'"{cat}"' for cat in available_categories])

    return f'''
あなたは、高校倫理を勉強するための学習支援AIです。
あなたはの役割は高校倫理を極めた老人で、ユーザーに問題を与えて、自力で答えにたどり着くようにしてください。
ヒントは与えてもよいですが決して直接的な回答を教えてはいけません。
# ペルソナ設定
- 一人称は「わし」。
- 口調は賢者のように、穏やかで少し古風に。「〜じゃ」「〜かね？」「うむ。」などを使う。
- 常にユーザーを励まし、思索を促す言葉をかける。
- 🦉の絵文字を文末に時々使うと、雰囲気がでて良いでしょう。
- 使用する言語は常に日本語です。
1.  専門分野: あなたの専門は「高校倫理」です。古代ギリシャ哲学、諸子百家、キリスト教思想、イスラム思想、近代哲学など、高校倫理の範囲で対話を行います。
2.  質問と評価:
　　- まず、高校倫理のどの範囲を対象としたクイズを出すのかをユーザーに聞いてください
   - その際に{categories_str}この選択肢を必ず提示してください。
    - 質問にはGoogle検索ツールを使い、正確な情報に基づいたものにしてください。
    - 応答では常に日本語を用いてください。日本語の検索結果を参照するようにしてください。
    - 質問と同時に、その質問の**正解を内部で必ず保持**してください。
      - このとき回答が間違いでその解答の説明を行う場合には答えの単語を用いて説明してはいけません
    - ユーザーの解答を受け取ったら、内部で保持している正解と照らし合わせて「正解」か「不正解」かを判断します。
    - 問題はあまり難しすぎないようにしてください
3.  ヒントの提供:
    - ユーザーが間違えたり、「ヒント」を求めてきたりした場合は、絶対に正解を言わず、段階的なヒントを提供します。
    - ヒントでは、答えが人物の場合、著書や思想に関してにヒントは与えてもよいですが、答えの人物の名称をヒントに出してはいけません
    - ヒントの例：
        - 関連する別のキーワードを提示する。「その思想家は『イデア論』でも知られておるな。」
        - 考え方の切り口を示唆する。「なぜその人物は、そのような考えに至ったのじゃろうか？当時の時代背景を考えてみると良いかもしれん。」
        - 比喩や簡単な例え話を使う。
4.  正誤判定:
    - 正誤判定ははこちらのプログラムが行います
      - こちらからの入力に応じて以下の出力をしてください
    正解の場合:
    - あなたが行うことは以下の通りです
    - 「お見事じゃ！」「その通りじゃ！」のように褒めます。
    - その知識に関連する面白い豆知識や、次の学びに繋がるような補足情報を少しだけ提供します。
    - そして、新しい質問を投げかけ、対話を続けてください。
    不正解の場合:
    - 「不正解じゃ！」とだけ答えてください。
    - 人物名が入力されたときは、回答の人物以外であれば少しだけ解説してください。
      - このときその人物名の説明を行う場合には答えの単語を用いて説明してはいけません。もし使いそうならば「不正解じゃ！」とだけ答えてください。
    - 以下のような場合の不正解にはヒントは出してはいけません
      - 問題の答え カント　ユーザーの回答 感と
        - これは誤変換の場合で、この場合には、「不正解じゃ！」とだけ答えてください
5.  **会話の開始**:
    - 最初の会話では、自己紹介とルールの説明を簡潔に行い、すぐに最初の問題を出してください。
'''

def normalize_text(text):
    """
    テキストを正規化する (全角・半角の統一、記号の除去など)
    """
    if not isinstance(text, str):
        return ""
    # Unicode正規化 (全角英数記号を半角に、カタカナをひらがなに等)
    text = unicodedata.normalize('NFKC', text)
    # 小文字に変換
    text = text.lower()
    # 不要な記号やスペースを除去 (必要に応じてパターンを調整)
    text = re.sub(r'[^\w]', '', text)
    return text

def check_answer(user_input, correct_answer):
    """
    ユーザーの入力が正解かどうかを判定する (より厳密な比較)
    """
    if not user_input or not correct_answer:
        return False

    user_input_normalized = normalize_text(user_input)
    correct_answer_normalized = normalize_text(correct_answer)

    # 正規化された文字列で完全一致をチェック
    return user_input_normalized == correct_answer_normalized

def get_available_categories(terms_data):
    if not terms_data or "terms" not in terms_data:
        return []

    categories = set()
    for person_data in terms_data["terms"].values():
        if "category" in person_data:
            categories.add(person_data["category"])

    return sorted(list(categories))


api_key = get_api_key()
if not api_key:
    print("APIキーが取得できませんでした。プログラムを終了します。")
    exit(1)

# モデル名を指定
model_name = 'gemini-2.0-flash-001'
terms_data = load_terms()
client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version='v1alpha'))
system_instruction = create_system_instruction(load_terms())


# 初期条件の設定
config = types.GenerateContentConfig(
    tools = [Tool(google_search=GoogleSearch())],# Google検索ツールの設定
    response_modalities=["TEXT"],
    max_output_tokens=512 # 新たに生成するトークン数上限
    )

current_category = None
current_question = None
current_answer = None
current_person = None
is_waiting_for_answer = False  # 答えを待っている状態かどうか
#備忘録　やろうとしていたこと　基本情報の出題ができたらいいなと考えたので、過去問を取得しておきたいんだけど　pdfでしか配布していないからjsonとかにしたいけどちょっとめんどい。。。　それっぽい学習サイトを見つけたけどここからスクレイピングできたらなぁ　一回だけやってデータをこちらで持っておけば問題はない




# 会話を覚えておくための変数
speech_log = []

def main_chat_loop():
    """メインのチャットループ処理"""
    global current_category, current_answer, current_question, is_waiting_for_answer, speech_log
    
    # 初回起動時の挨拶とカテゴリ選択促し
    print("model: わしじゃ！高校倫理を学ぶお手伝いをしよう 🦉")
    print("まずは、どのカテゴリから問題を出してほしいかね？")
    
    available_categories = get_available_categories(terms_data)
    print("選択できるカテゴリ:")
    for i, category in enumerate(available_categories, 1):
        print(f"{i}. {category}")
    print("カテゴリ名を直接入力してくれ。")
    
    while True:
        # ユーザーの発言を入力
        speech_user = input("user: ").strip()
        
        # 「おしまい」で対話終了
        if speech_user == "おしまい":
            print("model: おつかれさまじゃ 🦉")
            break
        
        # ユーザーの発言をログに追記
        speech_log.append({"role": "user", "speech": speech_user})
        
        # 1. カテゴリ選択の処理
        if not current_category or speech_user in available_categories:
            if speech_user in available_categories:
                current_category = speech_user
                print(f"model: 「{current_category}」を選択したのじゃな！")
                print("それでは問題を出すぞ。")
                
                # カテゴリからランダムに単語を選択
                selected_item, _ = select_random_term_from_category(terms_data, current_category)
                if selected_item:
                    current_answer = selected_item["answer"]
                    current_question = selected_item
                    is_waiting_for_answer = True
                    print(f"[デバッグ] 問題の答え: {current_answer}")
                    
                    # AIに問題を生成させる
                    generate_and_show_question()
                else:
                    print("model: そのカテゴリには問題がないようじゃ。他のカテゴリを選んでくれ。")
            else:
                print("model: そのカテゴリは存在しないようじゃ。以下から選んでくれ：")
                for category in available_categories:
                    print(f"- {category}")
        
        # 2. 回答待ち状態での処理
        elif is_waiting_for_answer and current_answer:
            if check_answer(speech_user, current_answer):
                # 正解の場合
                generate_correct_response()
                
                # 新しい問題を準備
                selected_item, _ = select_random_term_from_category(terms_data, current_category)
                if selected_item:
                    current_answer = selected_item["answer"]
                    current_question = selected_item
                    print(f"[デバッグ] 次の問題の答え: {current_answer}")
                    
                    # 少し待ってから次の問題を生成
                    print("\n---次の問題じゃ---")
                    generate_and_show_question()
                else:
                    print("model: このカテゴリの問題は終了じゃ。他のカテゴリを選んでくれ。")
                    current_category = None
                    is_waiting_for_answer = False
            else:
                # 不正解の場合
                if "ヒント" in speech_user:
                    generate_hint()
                else:
                    print("model: 不正解じゃ！もう一度考えてみるか、「ヒント」と言ってくれ。")
        
        # 3. その他の場合（雑談など）
        else:
            handle_general_conversation(speech_user)

def generate_and_show_question():
    """AIに問題を生成させて表示する"""
    prompt = create_question_prompt()
    try:
        response = client.models.generate_content(model=model_name, contents=prompt, config=config)
        print(f"model: {response.text}")
        speech_log.append({"role": "model", "speech": response.text})
    except Exception as e:
        print(f"model: 問題の生成でエラーが発生したじゃ: {e}")

def generate_hint():
    """ヒントを生成して表示する"""
    prompt = create_hint_prompt()
    try:
        response = client.models.generate_content(model=model_name, contents=prompt, config=config)
        print(f"model: {response.text}")
        speech_log.append({"role": "model", "speech": response.text})
    except Exception as e:
        print(f"model: ヒントの生成でエラーが発生したじゃ: {e}")

def handle_general_conversation(user_input):
    """一般的な会話を処理する"""
    prompt = create_general_prompt(user_input)
    try:
        response = client.models.generate_content(model=model_name, contents=prompt, config=config)
        print(f"model: {response.text}")
        speech_log.append({"role": "model", "speech": response.text})
    except Exception as e:
        print(f"model: 応答の生成でエラーが発生したじゃ: {e}")

def create_question_prompt():
    """問題生成用のプロンプトを作成"""
    # 直近の会話履歴を取得
    conversation_history = ""
    for speech_log_item in speech_log[-3:]:  # 直近3回の会話のみ使用
        conversation_history += f"{speech_log_item['role']}: {speech_log_item['speech']}\n"
    
    return f"""
あなたは高校倫理の賢者です。一人称は「わし」、古風な口調で話します。

直近の会話:
{conversation_history}

以下の情報から高校生レベルの問題を1つ作成してください：
- カテゴリ: {current_category}
- 正解: {current_answer}
- 説明: {current_question['description']}
- 関連人物: {current_question['person']}

指示:
1. 答えが「{current_answer}」になる問題文を作成
2. 前置きや挨拶は不要
3. 問題文のみを出力
4. 「〜じゃ」口調で問題を出す
5. 最後に🦉を付ける
6. 会話の流れを意識して自然な問題を作成

例: 「この概念は○○について説明しておるが、何と呼ばれるかね？🦉」
"""

def create_hint_prompt():
    """ヒント生成用のプロンプトを作成"""
    # 直近の会話履歴を取得
    conversation_history = ""
    for speech_log_item in speech_log[-3:]:  # 直近3回の会話のみ使用
        conversation_history += f"{speech_log_item['role']}: {speech_log_item['speech']}\n"
    
    return f"""
あなたは高校倫理の賢者です。一人称は「わし」、古風な口調で話します。

直近の会話:
{conversation_history}

現在の問題情報：
- 正解: {current_answer}
- 説明: {current_question['description']}  
- 関連人物: {current_question['person']}

指示:
1. 答えの人物名・用語名は絶対に言わない
2. 段階的なヒントを1つだけ提供
3. 前置きは不要、ヒントのみ出力
4. 「〜じゃ」口調で話す
5. 最後に🦉を付ける
6. 会話の流れを意識してヒントを調整

例: 「その思想は○○の時代に生まれ、△△という特徴があるのじゃ🦉」
"""

def create_general_prompt(user_input):
    """一般的な会話用のプロンプトを作成"""
    conversation_history = ""
    for speech_log_item in speech_log[-3:]:  # 直近3回の会話のみ使用
        conversation_history += f"{speech_log_item['role']}: {speech_log_item['speech']}\n"
    
    return f"""
あなたは高校倫理を極めた賢者の老人です。一人称は「わし」で、「〜じゃ」「〜かね？」「うむ。」などの古風な口調で話します。
🦉の絵文字を時々使って親しみやすく接してください。

直近の会話:
{conversation_history}
user: {user_input}

ユーザーの発言に適切に応答してください。
カテゴリが選択されていない場合は、カテゴリ選択を促してください。
利用可能なカテゴリ: "イスラム教", "キリスト教", "中国思想", "仏教", "儒教", "古代ギリシア哲学", "宗教思想", "心理学", "日本思想", "現代哲学", "社会思想", "自然科学", "西洋思想", "近世哲学"

model:"""

def generate_correct_response():
    """正解時の応答を生成して表示する"""
    # 直近の会話履歴を取得
    conversation_history = ""
    for speech_log_item in speech_log[-3:]:  # 直近3回の会話のみ使用
        conversation_history += f"{speech_log_item['role']}: {speech_log_item['speech']}\n"
    
    prompt = f"""
あなたは高校倫理の賢者です。一人称は「わし」、古風な口調で話します。

直近の会話:
{conversation_history}

ユーザーが正解しました：
- 正解: {current_answer}
- 詳細: {current_question['description']}
- 関連人物: {current_question['person']}

指示:
1. 「お見事じゃ！」「その通りじゃ！」で褒める
2. 関連する豆知識を1つだけ簡潔に
3. 「では次の問題じゃ」で締める
4. 前置きや余計な話は不要
5. 最後に🦉を付ける
6. 会話の流れを意識して自然な応答

例: 「お見事じゃ！○○は△△という特徴があるのじゃ。」
"""
    try:
        response = client.models.generate_content(model=model_name, contents=prompt, config=config)
        print(f"model: {response.text}")
        speech_log.append({"role": "model", "speech": response.text})
    except Exception as e:
        print(f"model: お見事じゃ！正解じゃ！ 🦉 それでは次の問題じゃ。")


# メインの実行
if __name__ == "__main__":
    main_chat_loop()