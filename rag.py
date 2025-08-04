! pip install google-genai
! pip install -q wikipedia # Wikipedia APIラッパーのインストール
from google import genai
from google.genai import types
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch
from google.colab import userdata
userdata.get('GOOGLE_API_KEY')

import wikipedia
wikipedia.set_lang("ja") # 日本語Wikipediaから取得

# 取得したAPIキーを設定
api_key='AIzaSyAZuRCKW5ap98_M13q0To7FcUEkjS8F45s'

# モデル名を指定
model_name = 'gemini-2.0-flash-001'

query = "空飛ぶスパゲティモンスター教"
summary = wikipedia.summary(query, sentences=10) # フランスに関する要約文を2文取得
print("取得した外部情報:¥n", summary, "¥n") # 確認用に取得情報を表示
client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version='v1alpha'))
system_instruction = summary

# 初期条件の設定
config = types.GenerateContentConfig(
    tools = [Tool(google_search=GoogleSearch())],# Google検索ツールの設定
    response_modalities=["TEXT"],
    max_output_tokens=256 # 新たに生成するトークン数上限
    )

prompt = summary +  "n質問: 空飛ぶスパゲティモンスター教とは何ですか"
response = client.models.generate_content( model=model_name,contents=prompt, config=config)
print(f"model:{response.text}")