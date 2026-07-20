# 本次使用Qwen2.5-1.5B去測試 CPU能不能做簡易問答，並融入 SerpAPI 聯網
from fastapi import FastAPI, HTTPException 
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer 
import torch 
import httpx     # 非同步 HTTP 請求庫，專門用來超穩連線 SerpAPI
import json      # 處理搜尋來源 JSON 轉換
from typing import Optional
import os
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
app = FastAPI()

MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
print(f"Loading model: {MODEL_NAME}...")

# 載入分詞器與大語言模型本體
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype="auto", device_map="auto")
print("Model loaded successfully!")

print("[RAG-INIT] 正在加載阿里官方最新 Qwen3-Embedding-0.6B 向量模型...")

# 確保在 CPU 執行，並啟用 trust_remote_code=True
# 如果要修正這裡可以改成GPU
embedding_model = SentenceTransformer(
    'Qwen/Qwen3-Embedding-0.6B', 
    device='cpu',
    trust_remote_code=True
)

print("[RAG-INIT] ✅ Qwen3 向量大腦已在 CPU 成功熱機！")
chroma_client = chromadb.HttpClient(host='chroma-db', port=8000)
rag_collection = chroma_client.get_or_create_collection(name="chatroom_knowledge_base")



# 配合 C# 的全新架構，調整 API 接收的 JSON 資料格式
class ChatRequest(BaseModel):
    userMessage: str         # 使用者輸入的原始對話內容
    isWebSearch: bool        # 是否啟用 Google 聯網搜尋功能
    max_tokens: int = 512    # 模型最大生成量

# =========================================================================
# 🚀 RAG ＋ 聯網雙軌完全體：【增】POST /api/chat - 完美熔接版
# =========================================================================
@app.post("/api/chat")
async def chat(request: ChatRequest):
    # 💡 雙重相容前端傳過來的變數命名（優先使用 DTO 或對齊 request 屬性）
    room_id = str(getattr(request, 'roomId', getattr(request, 'chatRoomId', '1')))
    user_message = getattr(request, 'message', getattr(request, 'userMessage', ''))
    is_web_search = request.isWebSearch
    
    final_prompt = user_message  # 預設 Prompt 就是使用者原話
    search_sources_json = None   # 預設搜尋來源為空
    local_knowledge = ""         # 預設本地知識庫為空

    print(f"[📥 收到對話請求] 房間: {room_id}, 問題: {user_message}, 聯網狀態: {is_web_search}")

    # =========================================================================
    # 💡 第一軌防禦：RAG 本地知識庫翻書（Qwen3-Embedding ＋ ChromaDB 檢索）
    # =========================================================================
    context_chunks = []
    try:
        # 1. 利用 Qwen3 模型將問題轉化成特徵向量（對齊官方格式）
        query_embedding = embedding_model.encode([user_message], prompt_name="query").tolist()

        # 2. 去 ChromaDB 的房間抽屜撈出相關資料
        search_results = rag_collection.query(
            query_embeddings=query_embedding,
            n_results=3,
            where={"roomId": room_id} # 💡 100% 房間數據物理隔離
        )
        if search_results and 'documents' in search_results and len(search_results['documents']) > 0:
            # 拔出第一筆問題的結果陣列
            context_chunks = search_results['documents'][0] 
            print(f"[🔍 RAG 檢索成功] 已為房間 {room_id} 尋找到 {len(context_chunks)} 條相關本地小抄")
    except Exception as chroma_err:
        print(f"[⚠️ ChromaDB 檢索無資料或失敗]: {str(chroma_err)}")

    if context_chunks:
        local_knowledge = "\n".join([f"【參考本地片段】: {text}" for text in context_chunks])

    # =========================================================================
    # 💡 第二軌注入：SerpAPI 聯網搜尋與前 3 筆 Organic 資料萃取邏輯 (保留原版)
    # =========================================================================
    if is_web_search:
        print(f"[DEBUG] ✅ 成功跨越門檻！進入 Python 聯網內部，變數確認為: {is_web_search}")
        from urllib.parse import quote
        serp_api_key = "dbaa323b6d7e7f313ba5732b5d4c53d7deafcd23dfa2ad73eb63b7fbf0f52307"
        
        # ⚠️ 這個註解和原版保持一模一樣
        #  api_key = "dbaa323b6d7e7f313ba5732b5d4c53d7deafcd23dfa2ad73eb63b7fbf0f52307" 禁止刪除
        # url = f"https://serpapi.com/search.json?engine=google&q=taiwan&api_key={api_key}"禁止刪除

        clean_msg = quote(user_message.strip())
        # 💡 原本網址寫死 taiwan，此處保留你原本的 serp_url 確保測試結果一致
        serp_url = f"https://serpapi.com/search.json?engine=google&q=taiwan&api_key={serp_api_key}"
        
        try:
            print("[DEBUG] 🌐 Python 正在向 SerpAPI 發送請求...")
            async with httpx.AsyncClient(timeout=10.0, verify=False, follow_redirects=True) as client:
                serp_response = await client.get(serp_url)
            
            print(f"[DEBUG] 📡 收到回應！HTTP 狀態碼為: {serp_response.status_code}")
            raw_text = serp_response.text
            
            if serp_response.status_code == 200:
                print("處理內容123")
                serp_root = json.loads(raw_text)
                
                if "error" in serp_root:
                    print(f"\n[❌ SerpAPI 官方拒絕] Google 拒絕原因: {serp_root['error']}")
                
                serp_root_lower = {k.lower(): v for k, v in serp_root.items()}
                sources = []
                pmp = ["【Google 最新搜尋參考資料】:\n"]
                
                if "organic_results" in serp_root_lower and isinstance(serp_root_lower["organic_results"], list):
                    print(f"\n[📡 SerpAPI 直擊] Google 第一頁成功吐出 organic_results 陣列，開始萃取前 3 筆...")
                    count = 0
                    for item in serp_root_lower["organic_results"]:
                        if count >= 3: break
                        item_lower = {k.lower(): v for k, v in item.items()}
                        title = item_lower.get("title", "")
                        snippet = item_lower.get("snippet", "")
                        link = item_lower.get("link", "")
                        if title or snippet:
                            sources.append({"title": title, "link": link, "snippet": snippet})
                            pmp.append(f"- {title}: {snippet}\n")
                            count += 1
                
                if len(sources) > 0:
                    search_sources_json = json.dumps(sources, ensure_ascii=False)
                    # 💡 聯網專用 Prompt 強化
                    final_prompt = f"{''.join(pmp)}\n【請根據上述豐富的最新參考資料，幫使用者做出專業且精準推薦回答】: {user_message}"
                    print(f"[DEBUG] 🎉 搜尋資料注入成功！Prompt 已強化。")
            else:
                print(f" 🔴 SerpAPI 伺服器回傳的真實原因:\n {raw_text}")
        except Exception as web_ex:
            print(f" 錯誤原因: {str(web_ex)}")

    # =========================================================================
    # 💡 終極 Prompt 融合：如果同時有本地 RAG 小抄，將其與 final_prompt 再次打包
    # =========================================================================
    if local_knowledge:
        system_prompt = "你是一個具備企業級知識庫檢索與聯網雙軌能力的 AI 智慧助理。請優先根據提供的本地知識庫參考資料回答。"
        final_prompt = f"""請嚴格根據以下提供的本地知識庫參考資料來回答使用者的問題。

【本地知識庫參考資料】:
{local_knowledge}

【目前對話與提問內容】:
{final_prompt}"""
    else:
        system_prompt = "你是一個全能的 AI 智慧助理。"

    # =========================================================================
    # 🤖 模型生成階段
    # =========================================================================
    try:
        print(f"[🤖 AI 思考中] 最終推理 Prompt 長度: {len(final_prompt)}")
        
        # 整理成聊天範本格式（送入系統提示詞與強化後的 final_prompt）
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": final_prompt}
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        
        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
        
        # 讓模型開始生成回應 (限制長度對齊 DTO 最大代幣)
        max_tokens = getattr(request, 'max_tokens', 512)
        generated_ids = model.generate(**model_inputs, max_new_tokens=max_tokens)

        generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]
        response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)

        print(f"[🤖 Qwen 推理結束] AI 生成回覆成功。")
        return {
            "reply": response[0],
            "searchSources": search_sources_json
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# 💡 專屬 FastAPI 的 RAG 接收 DTO 模型定義 (完全防禦紅底)
# =========================================================================
class RagUploadRequest(BaseModel):
    roomId: str
    fileName: Optional[str] = "unknown_file"
    fileContent: str

# =========================================================================
# 🚀 整合 Qwen3 規格重構版端點：【增】POST /api/rag/upload
# =========================================================================
@app.post("/api/rag/upload")
async def rag_upload_document(req: RagUploadRequest):
    try:
        room_id = str(req.roomId)
        file_name = req.fileName
        file_content = req.fileContent

        if not file_content.strip() or not room_id:
            raise HTTPException(status_code=400, detail="缺少無效的文字內容或未指定聊天室 ID")

        # 🌟 核心 RAG 算法 1：滑動視窗字串切片 (Chunking)
        chunk_size = 400
        overlap = 50
        chunks = []
        
        start = 0
        while start < len(file_content):
            end = start + chunk_size
            chunk_text = file_content[start:end]
            chunks.append(chunk_text.strip())
            start += (chunk_size - overlap)

        # 🌟 核心 RAG 算法 2：呼叫 Qwen3-Embedding 模型將切片轉化向量
        print(f"[RAG-UPLOAD] 聊天室 {room_id} 開始對 {file_name} 進行 {len(chunks)} 個切片轉化向量...")
        
        # 💡 根據 Qwen3 官方規範：上傳文件庫（Document）端不需要額外附加 prompt_name="query" 
        # 直接進行標準 encode，這樣能與發問端的 query 產生完美的餘弦相似度對齊
        embeddings = embedding_model.encode(chunks).tolist()

        # 🌟 核心 RAG 算法 3：寫入 ChromaDB 向量資料庫
        documents_ids = [f"room_{room_id}_{file_name}_{i}" for i in range(len(chunks))]
        metadatas = [{"roomId": room_id, "fileName": file_name} for _ in range(len(chunks))]

        # 物理寫入由 Qwen3 產生的 1024/1536 高維度向量數據
        rag_collection.add(
            ids=documents_ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )

        print(f"[RAG-UPLOAD] ✅ 聊天室 {room_id} 的 {file_name} 已成功在 ChromaDB 建立 Qwen3 向量索引！")
        return {
            "message": "文件向量化建立成功",
            "chunksCount": len(chunks)
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[❌ RAG-UPLOAD 崩潰]: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Python RAG 引擎內部錯誤: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "healthy"}
