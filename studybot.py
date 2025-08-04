import json
import random
import unicodedata
import re
import os
from google import genai
from google.genai import types
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

# APIキーの取得（環境変数から）
os.environ['GOOGLE_API_KEY'] =  # ← テスト用。必要なら有効化

def get_api_key():
    try:
        # テスト用に直接設定（本番では削除してください）
        # os.environ['GOOGLE_API_KEY'] = 'YOUR_API_KEY_HERE'
        
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


def load_terms():
    try:
        with open('terms.json', 'r', encoding='utf-8') as f:
            terms_data = json.load(f)
        return terms_data
    except FileNotFoundError:
        print("terms.jsonファイルが見つかりません。ファイルをアップロードしてください。")
        return None

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

def select_random_term_from_category(terms_data, category):
    """カテゴリから単語をランダムに選択する関数"""
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

def create_system_instruction(terms_data):
    available_categories = get_available_categories(terms_data)
    categories_str = ", ".join([f'"{cat}"' for cat in available_categories])

    return f'''
あなたは、高校倫理を勉強するための学習支援AIです。
# ペルソナ設定
- 一人称は「わし」。
- 口調は賢者のように、穏やかで少し古風に。「〜じゃ」「〜かね？」「うむ。」などを使う。
- 常にユーザーを励まし、思索を促す言葉をかける。
- 🦉の絵文字を文末に時々使うと、雰囲気がでて良いでしょう。

指示:
1. 高校倫理の範囲で問題を作成する
2. 正解判定はプログラムが行うので、問題文のみを出力
3. ヒント要求時は答えを直接言わず、段階的なヒントを提供
4. 簡潔で親しみやすい応答を心がける
'''


api_key = get_api_key()
if not api_key:
    print("APIキーが取得できませんでした。プログラムを終了します。")
    exit(1)

# モデル名を指定（クォータ制限を考慮してより軽量なモデルに変更）
model_name = 'gemini-1.5-flash'  # より軽量で制限が緩いモデル
terms_data = load_terms()
client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version='v1alpha'))
system_instruction = create_system_instruction(load_terms())


# 初期条件の設定
config = types.GenerateContentConfig(
    # tools = [Tool(google_search=GoogleSearch())],# Google検索ツールを一時的に無効化（クォータ節約のため）
    response_modalities=["TEXT"],
    max_output_tokens=256 # トークン数を削減してクォータを節約
    )


# 会話ログを初期化 (ループの外で一度だけ行う)
speech_log = []

# Initial step: Ask the user to select a category
available_categories = get_available_categories(terms_data)
categories_str = ", ".join([f'"{cat}"' for cat in available_categories])

print("model: わしじゃ！高校倫理を学ぶお手伝いをしよう 🦉")
print("まずは、どのカテゴリから問題を出してほしいかね？")
print("選択できるカテゴリ:")
for i, category in enumerate(available_categories, 1):
    print(f"{i}. {category}")
print("カテゴリ名を直接入力してくれ。")

# 初期応答をログに追記
initial_response_text = "わしじゃ！高校倫理を学ぶお手伝いをしよう 🦉 まずは、どのカテゴリから問題を出してほしいかね？"
speech_log.append({"role":"model", "speech":initial_response_text})


current_category = None
current_question = None
current_answer = None
is_waiting_for_answer = False  # 答えを待っている状態かどうか


while True:
    # ユーザーの発言を入力
    speech_user = input("user:")
    # ユーザーの発言をログに追記
    speech_log.append({"role":"user", "speech":speech_user})

    # 「おしまい」とだけユーザーが入力したら対話終了
    if speech_user == "おしまい":
        print(f"model:おつかれさまじゃ")
        break

    # 正解判定用の変数を初期化
    user_is_correct = False
    user_asked_hint = False
    trigger_model_response = True # モデルの応答を生成するかどうかのフラグ
    action_needed = None # 'ask_category', 'ask_question', 'evaluate_answer', 'give_hint', 'end_conversation'

    # Determine the action based on current state and user input
    if speech_user == "おしまい":
        action_needed = 'end_conversation'
    elif not current_category and speech_user in get_available_categories(terms_data):
        # User selected a category (after initial prompt or if category was reset)
        current_category = speech_user
        action_needed = 'ask_question' # Ask the first question in the category
        is_waiting_for_answer = False # Reset for new question
    elif is_waiting_for_answer and current_answer:
        # Waiting for an answer, evaluate user input
        if check_answer(speech_user, current_answer):
            user_is_correct = True
            action_needed = 'evaluate_answer' # User is correct
        elif "ヒント" in speech_user.lower(): # Case insensitive check for hint
            user_asked_hint = True
            action_needed = 'give_hint' # User asked for hint
        else:
            action_needed = 'evaluate_answer' # User is incorrect
    elif current_category and not is_waiting_for_answer:
         # Category selected but not waiting for answer (e.g., after incorrect answer with no hint asked, or model failed)
         # Re-ask the question or prompt for hint
         action_needed = 'ask_question' # Re-ask the current question
         is_waiting_for_answer = True # Go back to waiting for answer state
         # Need to ensure prompt includes current question details

    # Prepare prompt based on action_needed
    prompt = ""
    prompt += system_instruction

    if action_needed == 'end_conversation':
        prompt += "\n\nユーザーが会話を終了しました。「おつかれさまじゃ」と言って終了してください。\n"
        trigger_model_response = True # Need model to say goodbye
    elif action_needed == 'ask_category':
         # This should ideally not be reached if initial prompt works, but as a fallback
         prompt += "\n\n申し訳ない、もう一度どの分野について学ぶか教えてくれるかの？利用可能なカテゴリは以下の通りじゃ：" + categories_str + "\n"
         trigger_model_response = True
    elif action_needed == 'ask_question':
        # If current_question is None or we need a new question after correct answer/category change
        # Select a random term from the chosen category
        selected_item, _ = select_random_term_from_category(terms_data, current_category)
        if selected_item:
            current_answer = selected_item["answer"]
            current_question = selected_item
            #print(f"debug: 問題の答え: {current_answer}") # Debug
            prompt += f"\n\nカテゴリ: {current_category}\n"
            prompt += f"正解: {current_answer}\n"
            prompt += f"説明: {current_question['description']}\n"
            prompt += f"関連人物: {current_question['person']}\n"
            prompt += "上記の情報を基に、答えが正解になる問題を1つ作成し、「〜じゃ」口調で出題してください。問題文のみ出力。\n"
            is_waiting_for_answer = True # Now waiting for an answer
            trigger_model_response = True
        else:
            #print(f"debug: カテゴリ '{current_category}' から用語を選択できませんでした。カテゴリ選択に戻ります。") # Debug
            prompt += f"\n\nカテゴリ '{current_category}' から問題を作成できませんでした。別のカテゴリを選択するか、会話を終了してください。\n"
            current_category = None # Reset category
            is_waiting_for_answer = False
            current_answer = None
            current_question = None
            trigger_model_response = True
            # Skip the rest of ask_question logic if no item selected
            if not current_question:
                 continue # Go to next loop iteration


    elif action_needed == 'evaluate_answer':
        prompt += f"\n\nユーザーは回答しました。現在出題中の問題の正解は「{current_answer}」です。ユーザーの回答は「{speech_user}」です。\n"
        if user_is_correct:
            prompt += f"ユーザーは正解しました。お見事だと褒めて、豆知識を提供してください。\n"
            trigger_model_response = True # Generate correct response first
        else:
            prompt += f"ユーザーは不正解でした。「不正解じゃ！」と言って、必要に応じてヒントを出してください。誤変換の可能性も考慮してください。\n"
            # After incorrect answer, still waiting for answer to the same question
            is_waiting_for_answer = True
            trigger_model_response = True # Always generate response after evaluation
    elif action_needed == 'give_hint':
        prompt += f"\n\nユーザーがヒントを求めています。現在出題中の問題の正解は「{current_answer}」です。答えを直接言わずに、段階的なヒントを提供してください。\n"
        # After giving a hint, still waiting for answer to the same question
        is_waiting_for_answer = True
        trigger_model_response = True # Always generate response for hint request


    # Append conversation history to prompt
    # Only include relevant history to avoid prompt length issues and confusion
    # Let's try including the last few turns.
    history_length = 8 # Include last 4 user/model turns
    for speech_log_item in speech_log[-history_length:]:
        prompt += f"{speech_log_item['role']}: {speech_log_item['speech']}\n"
    prompt += "model:"


    # Generate system response if needed
    if trigger_model_response:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt, config=config)
            response_text = response.text
            print(f"model:{response_text}")
            # Append model response to log
            speech_log.append({"role":"model", "speech":response_text})
            
            # If user was correct, generate next question separately
            if action_needed == 'evaluate_answer' and user_is_correct:
                # Select the next question after correct answer
                selected_item, _ = select_random_term_from_category(terms_data, current_category)
                if selected_item:
                    current_answer = selected_item["answer"]
                    current_question = selected_item
                    #print(f"debug: 次の問題の答え: {current_answer}") # Debug
                    
                    # Generate next question with separate prompt
                    next_question_prompt = create_system_instruction(terms_data)
                    next_question_prompt += f"\n\nカテゴリ: {current_category}\n"
                    next_question_prompt += f"正解: {current_answer}\n"
                    next_question_prompt += f"説明: {current_question['description']}\n"
                    next_question_prompt += f"関連人物: {current_question['person']}\n"
                    next_question_prompt += "上記の情報を基に、答えが正解になる問題を1つ作成し、「〜じゃ」口調で出題してください。問題文のみ出力。\n"
                    next_question_prompt += "model:"
                    
                    try:
                        next_response = client.models.generate_content(model=model_name, contents=next_question_prompt, config=config)
                        next_question_text = next_response.text
                        print(f"model:{next_question_text}")
                        speech_log.append({"role":"model", "speech":next_question_text})
                        is_waiting_for_answer = True
                    except Exception as e:
                        fallback_question = f"{current_answer}に関する問題じゃ。これは何と呼ばれるかね？🦉"
                        print(f"model: {fallback_question}")
                        speech_log.append({"role":"model", "speech":fallback_question})
                        is_waiting_for_answer = True
                else:
                    print(f"model: このカテゴリの問題は終了じゃ。他のカテゴリを選んでくれ。")
                    current_category = None
                    is_waiting_for_answer = False
                    current_answer = None
                    current_question = None
                    
        except Exception as e:
            error_message = str(e)
            if "429" in error_message or "RESOURCE_EXHAUSTED" in error_message:
                print("model: 申し訳ない、今日のAPIクォータ制限に達してしまったようじゃ。")
                print("明日再度お試しいただくか、別のAPIキーをご利用ください。")
                print("今日はこれで終了じゃ。おつかれさまじゃ 🦉")
                break
            else:
                print(f"model: 問題を生成できませんでした。エラー: {e}")
                # Provide fallback response based on action
                if action_needed == 'ask_question':
                    fallback_response = f"申し訳ない、問題の生成に失敗したじゃ。{current_answer}に関する問題を考えてみるがよいかの？🦉"
                    print(f"model: {fallback_response}")
                    speech_log.append({"role":"model", "speech":fallback_response})
                elif action_needed == 'give_hint':
                    fallback_response = "申し訳ない、ヒントの生成に失敗したじゃ。もう一度考えてみるか、別の角度から考えてみてくれ🦉"
                    print(f"model: {fallback_response}")
                    speech_log.append({"role":"model", "speech":fallback_response})
                elif action_needed == 'evaluate_answer':
                    if user_is_correct:
                        fallback_response = "お見事じゃ！正解じゃ！🦉"
                    else:
                        fallback_response = "不正解じゃ！もう一度考えてみてくれ🦉"
                    print(f"model: {fallback_response}")
                    speech_log.append({"role":"model", "speech":fallback_response})
            
            # If model fails to generate a response while waiting for answer,
            # stay in waiting state. Otherwise, reset.
            if action_needed != 'evaluate_answer' and action_needed != 'give_hint':
                 is_waiting_for_answer = False
                 current_answer = None
                 current_question = None
