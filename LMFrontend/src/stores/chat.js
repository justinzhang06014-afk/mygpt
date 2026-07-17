import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import axios from 'axios';

// 🔀 baseURL 留空 = 相對於瀏覽器目前開啟的網址(同一個 origin)。
// 不管是從你自己電腦、還是小美小王的電腦打開 http://<伺服器IP>:5173，
// 都會打回同一台伺服器，由 nginx 反向代理轉給 C# 後端，不再寫死 127.0.0.1。
const api = axios.create({
    baseURL: '',
    timeout: 6000000,
    headers: {
        'Content-Type': 'application/json'
    }
});

export const useChatStore = defineStore('chat', () => {
    // 💡 多聊天室核心狀態
    const rooms = ref([]);             // 左側所有聊天室列表
    const currentRoomId = ref(localStorage.getItem('CORE_CURRENT_ROOM_ID') || null);   // 當前選中的聊天室 ID
    const messages = ref([]);          // 當前聊天室的訊息紀錄
    const isLoading = ref(false);       // 全域 AI 思考鎖
    const currentRoomFiles = ref([]);  //記住現在使用者正聊天的視窗(F5)也不會重製

    // ✨ 多智慧體（Multi-Agent）大廳狀態
    const agents = ref([]);              // 大廳渲染用的專家卡片清單
    const currentAgentId = ref(localStorage.getItem('CORE_CURRENT_AGENT_ID') || null);     // 當前身處哪位 AI 專家的辦公室 (null 代表一般 RAG)
    const isAgentMarketMode = ref(false); // 控制右側 UI 是否切換為「專家卡片大廳」
    // ==========================================
    // 🧠 🚀 新增：雙軌記憶體與細胞分裂核心狀態
    // ==========================================
    // 1. 記憶體大禮包的響應式容器 (分流儲存，互不污染)
    const memoryPackage = ref({ meta: {}, categories: [], memories: [] }); // 存放 memory.md 數據
    const userPackage = ref({ meta: {}, categories: [], memories: [] });   // 存放 user.md 數據
    
    // 2. 細胞分裂可用清單 (下拉選單渲染用)
    const availableForkAgents = ref([]);
    // 使用者 (🔒 從 localStorage 恢復登入身份)
    const currentUserId = ref(localStorage.getItem('CORE_CURRENT_USER_ID') || '');
    // 🎯 核心智慧過濾線（動態虛擬視圖）
    // 🎯 核心智慧過濾線 (🔒 解決痛點 1：徹底隔離左側房間清單污染)
    // 🎯 核心智慧過濾線 (🔒 解決痛點 1：徹底隔離左側房間清單污染)


    const filteredRooms = computed(() => {
        if (currentAgentId.value) {
            return rooms.value.filter(room => {
                const aId = room.agent_id || room.agentId;
                return aId === currentAgentId.value;
            });
        }
        return rooms.value.filter(room => {
            const hasAgentId = !!(room.agent_id || room.agentId);
            const isAgentType = room.room_type === 'hermes_agent' || room.roomType === 'hermes_agent';
            return !hasAgentId && !isAgentType; 
        });
    });

    const currentAgent = computed(() => {
        return agents.value.find(a => a.agent_id === currentAgentId.value) || null;
    });
    
    // // 💡 確保這段撈取目前房間文件清單的 Action 在儲存庫內
    // const currentRoomFiles = ref([]); // 當前聊天室擁有的 RAG 文件標籤陣列

    // 🚀 1.【查】讀取當前使用者專屬的聊天室房間清單 (多租戶隔離版)
    const fetchRoomsAction = async () => {
        try {
            // 💡 企業級防呆：如果還沒登入，不向後端發送請求
            if (!currentUserId.value) {
                console.warn("[Pinia] 未偵測到登入的 UserId，暫緩拉取清單。");
                return;
            }

            console.log(`[Pinia] 正在自資料庫拉取用戶 [${currentUserId.value}] 的專屬房間列表...`);
            
            // 💡 關鍵修正：透過 Query String 把當前登入的英數字帳號 (aaa / xiaomei) 帶給 C# 後端
            const res = await api.get(`/api/rooms?userId=${currentUserId.value}`);
            rooms.value = res.data;
            
            // 防呆錨定：如果按 F5 重新整理，依照當前續命的專家身份，自動把畫面的房間歸位
            if (filteredRooms.value.length > 0) {
                const isCurrentValid = filteredRooms.value.some(r => r.id === currentRoomId.value);
                if (!isCurrentValid) {
                    await switchRoomAction(filteredRooms.value[0].id);
                }
            } else {
                currentRoomId.value = null;
                messages.value = [];
            }
        } catch (err) {
            console.error('無法讀取聊天室清單，請檢查後端服務是否啟動:', err);
        }
    };

// 🚀 2.【增】建立綁定用戶的空白聊天室房間
    const createNewRoomAction = async () => {
        try {
            if (currentAgentId.value) {
                await createAgentRoomAction("專屬助理小幫手");
            } else {
                // 💡 關鍵修正：在建立新房間時，將當前的 currentUserId 放入 Payload 傳給 C# 後端
                const payload = { 
                    title: "新對話聊天室",
                    userId: currentUserId.value, // 👈 讓 C# 知道這個房間是屬於 aaa 還是 xiaomei 的
                    user_id: currentUserId.value // 👈 預留 Python / Docker 擴充用的字段
                };
                
                const res = await api.post('/api/rooms', payload);
                rooms.value.unshift(res.data);
                await switchRoomAction(res.data.id);
            }
        } catch (err) {
            console.error('建立聊天室失敗:', err);
        }
    };

// 🚀 2. 新增：提供給登入畫面呼叫的「隨意登入鎖定 Action」
    const loginUserAction = async (username, password) => {
        if (!username || !password) return false;
        
        try {
            const res = await api.post('/api/auth/login', {
                username: username.trim(),
                password: password
            });
            
            // 驗證成功，正式充電鎖定身分
            currentUserId.value = res.data.userId;
            console.log(`[Pinia] 用戶 [${currentUserId.value}] 資料庫驗證成功，準備注入狀態...`);
            
            // 洗牌左側列表
            await fetchRoomsAction();
            return true; // 🌟 成功：回傳 true
        } catch (err) {
            // 攔截後端的 400 錯誤訊息（"帳號或密碼錯誤！"）
            const errorMsg = err.response?.data?.message || '登入失敗，請檢查帳號密碼';
            alert(errorMsg);
            return false; // 🌟 失敗：回傳 false，阻斷後續通電
        }
    };



// 🚀 3. 新增：提供給登出按鈕呼叫的 Action (🔒 徹底清除所有痕跡)
    const logoutUserAction = () => {
        console.log(`[Pinia] 用戶 [${currentUserId.value}] 執行登出，清除所有狀態...`);
        currentUserId.value = '';
        currentRoomId.value = null;
        currentAgentId.value = null;
        rooms.value = [];
        messages.value = [];
        agents.value = [];
        memoryPackage.value = { meta: {}, categories: [], memories: [] };
        userPackage.value = { meta: {}, categories: [], memories: [] };
        isAgentMarketMode.value = false;
        currentRoomFiles.value = [];
        // 🔒 清除所有 localStorage 痕跡
        localStorage.removeItem('CORE_CURRENT_USER_ID');
        localStorage.removeItem('CORE_CURRENT_ROOM_ID');
        localStorage.removeItem('CORE_CURRENT_AGENT_ID');
        localStorage.removeItem('CORE_CURRENT_AGENT_NAME');
        localStorage.removeItem('active_agent_id');
    };


    // 🚀 3.【查】點擊切換聊天室並抓取該房間專屬子訊息
    const switchRoomAction = async (roomId) => {
        if (!roomId) return;
        currentRoomId.value = roomId;
        // 🔒 重新整理防禦線：刻進瀏覽器硬碟
        localStorage.setItem('CORE_CURRENT_ROOM_ID', roomId);
        messages.value = []; 
        currentRoomFiles.value = [];
        
        try {
            const res = await api.get(`/api/rooms/${roomId}/messages`);
            if (currentRoomId.value !== roomId) return; // 時序鎖
            
            messages.value = res.data.map(m => ({
                id: m.id,
                role: m.role,
                content: m.content,
                searchSources: m.searchSources ? (typeof m.searchSources === 'string' ? JSON.parse(m.searchSources) : m.searchSources) : []
            }));
            
            const targetRoom = rooms.value.find(r => r.id === roomId);
            if (targetRoom && !targetRoom.agent_id) {
                await fetchCurrentRoomFilesAction(roomId);
            }
        } catch (err) {
            console.error('載入房間聊天歷史失敗:', err);
        }
    };

    // 🚀 4.【刪】刪除特定聊天室房間 🗑️ (🔒 多租戶隔離：帶 userId)
    const deleteRoomAction = async (roomId) => {
        try {
            await api.delete(`/api/rooms/${roomId}?userId=${currentUserId.value}`);
            rooms.value = rooms.value.filter(r => r.id !== roomId);
            if (currentRoomId.value === roomId) {
                currentRoomId.value = null;
                localStorage.removeItem('CORE_CURRENT_ROOM_ID');
                if (filteredRooms.value.length > 0) {
                    await switchRoomAction(filteredRooms.value[0].id);
                } else {
                    currentRoomId.value = null;
                    messages.value = [];
                    currentRoomFiles.value = [];
                }
            }
        } catch (err) {
            console.error('刪除聊天室失敗:', err);
        }
    };


    // 🚀 新增：修改特定聊天室房間標題
    const updateRoomTitleAction = async (roomId, newTitle) => {
        if (!newTitle.trim()) return false;
        try {
            const res = await api.put(`/api/rooms/${roomId}`, { title: newTitle });
            
            // 💡 核心聯動：即時更新前端側邊欄陣列裡對應房間的標題
            rooms.value = rooms.value.map(r => {
                if (r.id === roomId) {
                    return { ...r, title: res.data.title };
                }
                return r;
            });
            return true;
        } catch (err) {
            console.error('Pinia 修改聊天室名稱失敗:', err);
            return false;
        }
    };

   // =========================================================================
    // 🚀 核心重構：雙軌獨立發送新訊息 (原生支援 SSE 流式打字機與相容性閉環)
    // =========================================================================
    const sendMessageAction = async ({ roomId, content, isWebSearch = false }) => {
        if (!content || !content.trim()) return;
        
        // 1. 建立並推入使用者的原始訊息 (同時滿足 content 與 userInput 欄位，確保共用畫面渲染不穿幫)
        const userMsgIndex = messages.value.push({ 
            id: null, 
            role: 'user', 
            content: content,
            userInput: content,
            timestamp: new Date().toISOString()
        }) - 1;
        
        isLoading.value = true;

        const currentRoomObj = rooms.value.find(r => r.id === roomId);
        const sendAgentId = currentRoomObj ? (currentRoomObj.agent_id || currentRoomObj.agentId) : null;

        // =========================================================================
        // 🤖 軌道 B：Hermes 專家房 ── 高效能流式打字機中轉管線
        // =========================================================================
        if (sendAgentId) {
          // 先在畫面上推入一條 AI 占位訊息，準備長出打字機效果
          const aiTempId = Date.now();
          const aiMsgIndex = messages.value.push({
              id: aiTempId,
              role: 'assistant',
              content: '',
              response: '', // 滿足 template 中的 msg.response 欄位需求
              searchSources: [],
              timestamp: new Date().toISOString()
          }) - 1;

          try {
                // 使用原生 fetch 連向 C# 後端已改裝、支援 HttpCompletionOption.ResponseHeadersRead 的 SSE 控制器
                // 🔀 相對路徑：透過 nginx 反向代理走同一個 origin，不寫死 127.0.0.1
                const response = await fetch('/api/chat', {
                  method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        // 🌟 終極修正：明確宣告前端期待接收 text/event-stream 串流，徹底根除 406 衝突！
                        'Accept': 'text/event-stream'
                    },
                    body: JSON.stringify({
                        chatRoomId: roomId,
                        roomId: roomId,
                        message: content,
                        isWebSearch: false,
                        agentId: sendAgentId,
                        userId: currentUserId.value
                    })
                });

              if (!response.ok) throw new Error(`後端網關拒絕連線: ${response.status}`);

              const reader = response.body.getReader();
              const decoder = new TextDecoder('utf-8');
              let buffer = '';

              // 💡 串流建立成功，Header 已讀到，立刻把「思考中」閃爍動畫關掉，交給打字機流暢印出！
              isLoading.value = false;

                while (true) {
                  const { value, done } = await reader.read();
                  if (done) break;

                  // 🔒 時序鎖防禦：如果使用者在流式傳輸中切換了房間，立刻熔斷，拒絕污染新房間
                  if (currentRoomId.value !== roomId) break;

                  buffer += decoder.decode(value, { stream: true });
                  const lines = buffer.split('\n\n');
                  buffer = lines.pop() || ''; // 保留未完整的片段

                    // 🔒 請確保包含此區塊的父函數（通常是讀取 Stream 的 read 迴圈）前方有宣告 async
                    // 範例：async function processStreamChunks() { ... }

                    for (const line of lines) {
                        if (!line.trim()) continue;

                        // 🎯 情況一：處理最末發的實體落盤相容數據 event: final_result
                        if (line.startsWith('event: final_result')) {
                            const dataIndex = line.indexOf('data: ');
                            if (dataIndex !== -1) {
                                try {
                                    const jsonStr = line.substring(dataIndex + 6).trim();
                                    const finalData = JSON.parse(jsonStr);
                                    
                                    // 🔒 終極數據閉環：覆蓋臨時 ID 與最終完整文本
                                    if (currentRoomId.value === roomId && messages.value[aiMsgIndex]) {
                                        messages.value[aiMsgIndex].id = finalData.id;
                                        messages.value[aiMsgIndex].content = finalData.reply;
                                        messages.value[aiMsgIndex].response = finalData.reply;
                                    }
                                } catch (jsonEx) {
                                    console.error('[Pinia 串流] 解析 final_result JSON 失敗:', jsonEx);
                                }
                            }
                            continue;
                        }

                        // 🎯 情況二：處理常規的 data: Token 區段 (打字機本體)
                        if (line.startsWith('data: ')) {
                            const token = line.substring(6);
                            // 🐛 0716 修正：這些結構化事件（__APPROVAL_REQUIRED__ / __ACP_TOOL__ 等）本身就是
                            // 合法 JSON，字串內容裡的 \n 已經是 JSON 自己的跳脫序列（例如 raw_input 裡完整的
                            // 檔案內容）。先做過一次「\\n → 真換行」的全域反轉義，會把 JSON 字串裡合法的
                            // \n 變成字面上的真實換行字元，讓 JSON.parse 直接判定為非法語法（JSON 字串裡
                            // 不允許出現未跳脫的控制字元），結果就是 catch 後退化成「只給拒絕」——這正是
                            // approve-write 彈窗只剩拒絕按鈕的根因。改成：只有最後真的要當純文字渲染到
                            // 泡泡裡的分支才做這個反轉義，所有結構化事件一律解析未經改動的原始 token。
                            if (token.includes('__APPROVAL_REQUIRED__')) {
                                console.warn('⚠️ [Pinia 串流攔截線] 捕捉到記憶衝突訊號！強制凍結異步 Reader，等待前端人工審查裁決。');

                                // 1. 全域 isLoading 思考鎖維持 true，讓前端主視窗套用半透明磨砂凍結狀態
                                isLoading.value = true;

                                // 2. 跨檔案安全觸發前端組件，讓主畫面的審查彈窗跳出來
                                if (typeof window.__triggerApprovalModal === 'function') {
                                    window.__triggerApprovalModal(token.replace('__APPROVAL_REQUIRED__:', '').trim());
                                } else {
                                    console.error('❌ [錯誤防禦] 前端 ChatRoom.vue 尚未註冊 window.__triggerApprovalModal 觸發器！');
                                }

                                // 3. 【核心關鍵】利用 Promise 異步阻塞當前的 for 迴圈與 while 讀取線
                                // 讓整個 Pinia 執行緒在原地靜止，直到使用者在彈窗點擊按鈕，回呼解除鎖定
                                await new Promise((resolve) => {
                                    window.__releaseApprovalLock = resolve;
                                });

                                console.log('🟢 [Pinia 串流攔截線] 人工審查完畢，封印解除！重啟打字機繼續讀取後續串流。');
                                continue; // 攔截碼本身是控制指令，不需要當作聊天內容渲染到畫面上，直接 continue 跳過
                            }

                            // =========================================================================
                            // 🧭 Skill 推薦攔截點：非阻塞，不用暫停打字機，直接把建議掛到這則訊息上，
                            // 讓 MessageBubble.vue 在泡泡下方渲染一張可點擊安裝的卡片
                            // =========================================================================
                            if (token.includes('__SKILL_SUGGESTED__')) {
                                try {
                                    const payloadText = token.replace('__SKILL_SUGGESTED__:', '').trim();
                                    const suggestion = JSON.parse(payloadText);
                                    if (currentRoomId.value === roomId && messages.value[aiMsgIndex]) {
                                        messages.value[aiMsgIndex].skillSuggestion = suggestion;
                                    }
                                } catch (parseErr) {
                                    console.error('❌ [Skill 推薦] 解析建議內容失敗:', parseErr);
                                }
                                continue; // 控制指令，不算聊天內容
                            }

                            // =========================================================================
                            // 🆕 0716：hermes acp 結構化事件——思考過程/工具呼叫/計畫更新/用量統計。
                            // 全部是 main.py 直接轉發 hermes 自己吐出來的真實資料，不是我們猜的。
                            // =========================================================================
                            if (token.includes('__ACP_THOUGHT__')) {
                                try {
                                    const body = JSON.parse(token.replace('__ACP_THOUGHT__:', '').trim());
                                    const msg = messages.value[aiMsgIndex];
                                    if (currentRoomId.value === roomId && msg) {
                                        msg.thoughts = (msg.thoughts || '') + (body.text || '');
                                    }
                                } catch (e) { console.error('❌ [ACP] 解析思考過程失敗:', e); }
                                continue;
                            }
                            if (token.includes('__ACP_TOOL__')) {
                                try {
                                    const body = JSON.parse(token.replace('__ACP_TOOL__:', '').trim());
                                    const msg = messages.value[aiMsgIndex];
                                    if (currentRoomId.value === roomId && msg) {
                                        if (!msg.toolCalls) msg.toolCalls = [];
                                        const existing = msg.toolCalls.find(t => t.tool_call_id === body.tool_call_id);
                                        if (existing) Object.assign(existing, body);
                                        else msg.toolCalls.push(body);
                                    }
                                } catch (e) { console.error('❌ [ACP] 解析工具呼叫事件失敗:', e); }
                                continue;
                            }
                            if (token.includes('__ACP_PLAN__')) {
                                try {
                                    const body = JSON.parse(token.replace('__ACP_PLAN__:', '').trim());
                                    const msg = messages.value[aiMsgIndex];
                                    if (currentRoomId.value === roomId && msg) {
                                        msg.plan = body.entries || [];
                                    }
                                } catch (e) { console.error('❌ [ACP] 解析計畫更新失敗:', e); }
                                continue;
                            }
                            if (token.includes('__ACP_USAGE__')) {
                                try {
                                    const body = JSON.parse(token.replace('__ACP_USAGE__:', '').trim());
                                    const msg = messages.value[aiMsgIndex];
                                    if (currentRoomId.value === roomId && msg) {
                                        msg.usage = body;
                                    }
                                } catch (e) { console.error('❌ [ACP] 解析用量統計失敗:', e); }
                                continue;
                            }

                            // 4. 常規打字機特效渲染邏輯 (🔒 房號一致性極限防禦)
                            // 只有真的要當聊天文字印出來的這一刻，才把 C# 轉義的 \n 還原成真換行
                            if (currentRoomId.value === roomId && messages.value[aiMsgIndex]) {
                                const cleanToken = token.replace(/\\n/g, '\n');
                                messages.value[aiMsgIndex].content += cleanToken;
                                // 💡 體驗細節進化：確保 response 同步更新，驅動前端 Markdown 與打字機流暢渲染
                                messages.value[aiMsgIndex].response = messages.value[aiMsgIndex].content;
                            }
                        }
                    }


                }
          } catch (err) {
              console.error('Hermes 串流接收發生崩潰:', err);
              if (currentRoomId.value === roomId && messages.value[aiMsgIndex]) {
                  messages.value[aiMsgIndex].content = '❌ 系統錯誤：無法從記憶隔離引擎接收即時串流。';
                  messages.value[aiMsgIndex].response = '❌ 系統錯誤：無法從記憶隔離引擎接收即時串流。';
              }
          } finally {
              isLoading.value = false;
          }

        // =========================================================================
        // 📄 軌道 A：一般舊 RAG 房 ── 100% 穩健、完全原封不動的整塊回傳模式
        // =========================================================================
        } else {
          try {
              const res = await api.post('/api/chat', { 
                  chatRoomId: roomId,      
                  roomId: roomId,          
                  message: content,        
                  isWebSearch: isWebSearch,
                  agentId: null,
                  userId: currentUserId.value
              });
              
              if (currentRoomId.value !== roomId) return; // 既有時序鎖防禦
              messages.value[userMsgIndex].id = res.data.id;
              messages.value.push({ 
                  id: res.data.id, 
                  role: 'assistant', 
                  content: res.data.reply,
                  response: res.data.reply, // 雙重安全對齊
                  searchSources: res.data.searchSources
              });
          } catch (err) {
              console.error('發送訊息至傳統後端失敗:', err);
              if (currentRoomId.value === roomId) {
                  messages.value.push({ id: null, role: 'assistant', content: '❌ 系統錯誤：無法連接到後端服務。', response: '❌ 系統錯誤：無法連接到後端服務。' });
              }
          } finally {
              isLoading.value = false;
          }
        }
    };


    // 🚀 6.【改】修改舊問題 (🔒 多租戶隔離：帶 userId)
    const updateMessage = async (messageId, newText, isWebSearch = false) => {
        if (!messageId || !newText.trim()) return false;
        isLoading.value = true;

        try {
            const res = await api.put(`/api/messages/${messageId}?userId=${currentUserId.value}`, {
                Message: newText,
                isWebSearch: isWebSearch
            });
            
            messages.value = messages.value.map(msg => {
                if (msg.id === messageId) {
                    if (msg.role === 'user') {
                        return { ...msg, content: newText };
                    } else if (msg.role === 'assistant') {
                        return { 
                            ...msg, 
                            content: res.data.reply, 
                            searchSources: res.data.searchSources 
                        };
                    }
                }
                return msg;
            });
            return true;
        } catch (err) {
            console.error('修改訊息失敗:', err);
            return false;
        } finally {
            isLoading.value = false;
        }
    };

    // 🚀 7.【刪】收回個別訊息功能 (🔒 多租戶隔離：帶 userId)
    const deleteMessage = async (messageId) => {
        if (!messageId) return;
        try {
            await api.delete(`/api/messages/${messageId}?userId=${currentUserId.value}`);
            messages.value = messages.value.filter(msg => msg.id !== messageId);
            return true;
        } catch (err) {
            console.error('收回訊息失敗:', err);
            return false;
        }
    };

    const fetchCurrentRoomFilesAction = async (roomId) => {
        if (!roomId) return;
        try {
            const res = await api.get(`/api/rooms/${roomId}/files?userId=${currentUserId.value}`);
            currentRoomFiles.value = res.data;
        } catch (err) {
            currentRoomFiles.value = []; 
        }
    };

    const deleteRoomFileAction = async (roomId, fileName) => {
        try {
            await api.delete(`/api/rooms/${roomId}/files`, {
                params: { fileName: fileName, userId: currentUserId.value }
            });
            if (currentRoomFiles.value) {
                currentRoomFiles.value = currentRoomFiles.value.filter(
                    f => (f.file_name || f.fileName) !== fileName
                );
            }
        } catch (err) {
            console.error('[Pinia Store 錯誤] 刪除文件失敗:', err);
            throw err;
        }
    };

    // 🚀 建立 Agent 專屬對話房 (精準外鍵綁定大腦) (🔒 多租戶隔離：帶 userId)
    const createAgentRoomAction = async (title) => {
        try {
            const response = await api.post('/api/agent/rooms', { 
                title: title || "專屬助理小幫手",
                room_type: "Agent", 
                agent_id: currentAgentId.value,
                userId: currentUserId.value, // 🔒 多租戶隔離
                user_id: currentUserId.value // 💡 預留 Python / Docker 擴充
            });
            rooms.value.unshift(response.data);
            await switchRoomAction(response.data.id); 
            return response.data; 
        } catch (error) {
            console.error("建立 Agent 房間失敗:", error);
        }
    };

        // ✨ 拉取 AI 專家大廳清單 (🔒 多租戶隔離：帶 userId)
        const fetchAgentsAction = async () => {
            try {
                if (!currentUserId.value) {
                    console.warn("[Pinia] 未偵測到登入的 UserId，暫緩拉取 Agent 清單。");
                    return;
                }
                const res = await api.get(`/api/agents?userId=${currentUserId.value}`);
                agents.value = res.data;
            } catch (err) {
                console.error('拉取 AI 專家大廳失敗:', err);
            }
        };
        // ✨ 捏造全新大腦助理 (🔒 多租戶隔離：帶 userId)
        const createCustomAgentAction = async (name, systemPrompt = '') => {
            if (!name.trim()) return;
            try {
                const res = await api.post('/api/agents', {
                    name: name.trim(),
                    system_prompt: systemPrompt,
                    user_id: currentUserId.value
                });
            agents.value.unshift(res.data);
            return res.data;
        } catch (err) {
            console.error('捏造大腦助理失敗:', err);
        }
    };

    // ✨ 進入特定專家的專屬辦公室
    const enterAgentWorkspace = async (agentId) => {
        currentAgentId.value = agentId;
        isAgentMarketMode.value = false; // 離開大廳，進入房間
        
        // 🔒 重新整理防禦線：刻進瀏覽器硬碟
        localStorage.setItem('CORE_CURRENT_AGENT_ID', agentId); 
        
        // 🔒 【終極全名物理鎖】：憑 ID 瞬間抓出助理真實全名刻進硬碟
        if (agents.value && agents.value.length > 0) {
            const foundAgent = agents.value.find(a => a.agent_id === agentId || a.id === agentId);
            if (foundAgent && foundAgent.name) {
                console.log("💾 [Pinia 持久化鎖] 成功將助理全名刻進硬碟:", foundAgent.name);
                localStorage.setItem('CORE_CURRENT_AGENT_NAME', foundAgent.name);
            }
        }
        
        messages.value = [];
        currentRoomFiles.value = [];

        // 🎯 房號比對與自動配平防線
        const agentRooms = rooms.value.filter(r => r.agent_id === agentId);
        
        if (agentRooms.length > 0) {
            // 情況 A：如果此助理有歷史對話，直接切換進去最舊（或最新）的對話
            await switchRoomAction(agentRooms[0].id); 
        } else {
            // 情況 B：【冷啟動安全防禦】如果此助理是剛捏出來的、底下全空無對話房間
            console.log("🔮 [房間自動配平] 偵測到新助理無對話歷史，自動熱觸發建立首發房間...");
            
            // 💡 呼叫您 Pinia 現有的創房 Action，在後端為此 Agent 自動持久化建一間房
            // 提示：請確保您的 createNewRoomAction 支援帶入 agentId，或會自動關聯當前的 currentAgentId
            if (typeof createNewRoomAction === 'function') {
                await createNewRoomAction(); 
            } else {
                // 如果創房需要帶參數，請根據您的 chat.js 設計微調（如：await createNewRoomAction(agentId)）
                currentRoomId.value = null;
                localStorage.removeItem('CORE_CURRENT_ROOM_ID');
            }
        }
    };


    // ✨ 退回一般 RAG 舊世界模式
    const exitToGeneralRag = async () => {
        currentAgentId.value = null;
        localStorage.removeItem('active_agent_id'); // 👈 抹除實體金鑰
        isAgentMarketMode.value = false;
        messages.value = [];
        currentRoomFiles.value = [];

        const firstGeneralRoom = rooms.value.find(r => !r.agent_id);
        if (firstGeneralRoom) {
            await switchRoomAction(firstGeneralRoom.id);
        } else {
            currentRoomId.value = null;
        }
    };

    // ✨ 【全新新增】一鍵抹除自訂專家大腦 (🔒 多租戶隔離：帶 userId)
    const deleteAgentAction = async (agentId) => {
        if (!agentId) return false;
        try {
            console.warn(`[Pinia 抄家] 正在向後端申請銷毀專家: ${agentId}`);
            await api.delete(`/api/agents/${agentId}?userId=${currentUserId.value}`);
            
            // 1. 畫面連動：立刻從大廳卡片陣列與房間列表中排除
            agents.value = agents.value.filter(a => a.agent_id !== agentId);
            rooms.value = rooms.value.filter(r => (r.agent_id || r.agentId) !== agentId);
            
            // 2. 終極安全防禦防呆：如果使用者剛好身處在「目前被刪除」的專家辦公室中，立刻強制踢回一般世界！
            if (currentAgentId.value === agentId) {
                console.log("[Pinia 防爆] 偵測到身處已被銷毀的辦公室，執行緊急退回一般 RAG 模式...");
                await exitToGeneralRag();
            }
            return true;
        } catch (err) {
            console.error('Pinia 銷毀 Agent 失敗:', err);
            return false;
        }
    };

    // ==========================================
    // ✨ 🧠 底下記憶
    // ======

    // ==========================================
    // ✨ 🧠 新增：雙軌制記憶與細胞分裂核心 Actions
    // ==========================================

    /**
     * 0. 掃描細胞庫：拉取目前全平台現存可供拷貝的 Agent 清單 (🔒 多租戶隔離)
     */
    async function fetchAvailableForkAgents() {
        try {
            const response = await api.get('/api/Chat/agent/available-list', {
                params: { userId: currentUserId.value }
            });
            if (response.data && response.data.status === 'success') {
                availableForkAgents.value = response.data.agents;
            }
        } catch (error) {
            console.error('❌ [Store] 拉取細胞分裂清單失敗:', error);
        }
    }

    /**
     * 1. 逆向解封印：使用者在核准彈窗點擊某個選項時呼叫 (🔒 多租戶隔離)
     * 🆕 0716：改用 hermes acp 的 request_permission，option_id 是 hermes 自己提供的
     * 選項 id（常見值：allow_once/allow_session/allow_always/reject_once/reject_always），
     * 不再是單純的布林值。
     * @param {string} roomId 房間 ID
     * @param {string} optionId 使用者選擇的核准選項 id
     */
    async function submitApproveDecision(roomId, optionId) {
        try {
            await api.post('/api/Chat/agent/approve-write', {
                room_id: roomId,
                option_id: optionId
            }, {
                params: { userId: currentUserId.value }
            });
        } catch (error) {
            console.error('❌ [Store] 逆向注入審查訊號失敗:', error);
            throw error;
        }
    }

    /**
     * 2. 雙軌讀取大禮包：一併或單獨刷出右側大腦與人設面板 (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     * @param {string} fileType 'memory' 或 'user'
     */
    async function fetchAgentMemories(agentId, fileType) {
        const type = fileType.toLowerCase();
        try {
            const response = await api.get(`/api/Chat/agent/${agentId}/memories/${type}`, {
                params: { userId: currentUserId.value }
            });
            
            if (type === 'memory') {
                memoryPackage.value = response.data;
            } else {
                userPackage.value = response.data;
            }
        } catch (error) {
            console.error(`❌ [Store] 讀取 ${type} 大禮包失敗:`, error);
        }
    }

    /**
     * 3. 手動點擊刪除特定卡片 (🗑️) (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     * @param {string} fileType 'memory' 或 'user'
     * @param {string} factId 卡片唯一 ID (例如 memory_fact_001)
     */
    async function deleteSpecificFact(agentId, fileType, factId) {
        const type = fileType.toLowerCase();
        try {
            const response = await api.delete(`/api/Chat/agent/${agentId}/memories/${type}/${factId}`, {
                params: { userId: currentUserId.value }
            });
            
            // 就地響應式刷新，前端 UI 瞬間變動
            if (type === 'memory') {
                memoryPackage.value = response.data;
            } else {
                userPackage.value = response.data;
            }
        } catch (error) {
            console.error(`❌ [Store] 刪除 ${type} 紀錄失敗:`, error);
            throw error;
        }
    }

    /**
     * 4. 軌道二：手動強制灌輸與大量匯入 (記住這句話 / 檔案上傳) (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     * @param {string} fileType 'memory' 或 'user'
     * @param {Array<string>} textList 純文字字串陣列
     */
    async function importBulkMemories(agentId, fileType, textList) {
        const type = fileType.toLowerCase();
        try {
            const response = await api.post(`/api/Chat/agent/${agentId}/memories/import`, {
                file_type: type,
                texts: textList
            }, {
                params: { userId: currentUserId.value }
            });
            
            // 就地刷新，大禮包自動帶回最新動態關鍵字歸類與飽和度
            if (type === 'memory') {
                memoryPackage.value = response.data;
            } else {
                userPackage.value = response.data;
            }
        } catch (error) {
            console.error(`❌ [Store] 批次匯入 ${type} 失敗:`, error);
            throw error;
        }
    }

    /**
     * 5. 真．複製：走 hermes profile create --clone-from，長出一個全新 Agent(非合併目前 Agent) (🔒 多租戶隔離)
     * @param {string} name 新 Agent 名稱
     * @param {string} systemPrompt 新 Agent 自己的系統提示詞
     * @param {string} sourceAgentId 作為複製範本的現存 Agent
     */
    async function cloneAgentAction(name, systemPrompt, sourceAgentId) {
        const response = await api.post('/api/Chat/agent/clone', {
            Name: name,
            SystemPrompt: systemPrompt,
            SourceAgentId: sourceAgentId
        }, {
            params: { userId: currentUserId.value }
        });
        agents.value.unshift({
            id: response.data.id,
            agent_id: response.data.agent_id,
            name: response.data.name,
            system_prompt: response.data.system_prompt,
            created_at: response.data.created_at
        });
        return response.data;
    }

    /**
     * 6. 匯出 Agent：三種格式擇一下載 (hermes 原生 tar.gz／zip／Skill 標準 markdown) (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     * @param {'hermes'|'zip'|'skill'} format 匯出格式
     */
    async function exportAgentAction(agentId, format = 'hermes') {
        const response = await api.get(`/api/Chat/agent/${agentId}/export`, {
            params: { format, userId: currentUserId.value },
            responseType: 'blob'
        });
        const disposition = response.headers['content-disposition'] || '';
        const match = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
        const filename = match ? decodeURIComponent(match[1]) : `${agentId}_export`;

        const blobUrl = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(blobUrl);
    }

    /**
     * 7. 匯入技能：上傳一份 SKILL.md，透過 hermes skills install 安裝進指定 Agent (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     * @param {string} skillName 技能名稱
     * @param {File} file 上傳的 SKILL.md 檔案
     */
    async function importSkillAction(agentId, skillName, file) {
        const formData = new FormData();
        formData.append('name', skillName);
        formData.append('file', file);
        formData.append('userId', currentUserId.value);
        const response = await api.post(`/api/Chat/agent/${agentId}/skills/import`, formData, {
            params: { userId: currentUserId.value },
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return response.data;
    }

    /**
     * 8. 安全掃描：hermes security audit(OSV.dev 供應鏈漏洞掃描) (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     */
    async function runSecurityAuditAction(agentId) {
        const response = await api.get(`/api/Chat/agent/${agentId}/security-audit`, {
            params: { userId: currentUserId.value }
        });
        return response.data;
    }

    /**
     * 9. Skill 商城搜尋：hermes skills search --json(官方市集) (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     * @param {string} query 搜尋關鍵字
     * @param {string} source 來源篩選
     */
    async function searchSkillsHubAction(agentId, query, source = 'all') {
        const response = await api.get(`/api/Chat/agent/${agentId}/skills/search`, {
            params: { query, source, limit: 24, userId: currentUserId.value }
        });
        return response.data;
    }

    /**
     * 10. Skill 商城安裝：hermes skills install <identifier> (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     * @param {string} identifier Skill 識別碼
     * @param {boolean} force 使用者已看過資安風險說明、仍決定安裝時傳 true
     * @returns {Promise<{status:string, stdout:string, outcome:'installed'|'blocked'|'unknown', security_report:string|null}>}
     */
    async function installSkillFromHubAction(agentId, identifier, force = false) {
        const response = await api.post(`/api/Chat/agent/${agentId}/skills/install-from-hub`, {
            Identifier: identifier,
            Force: force
        }, {
            params: { userId: currentUserId.value }
        });
        return response.data;
    }

    /**
     * 12a. 查看某個 Agent 目前所有待審核的技能寫入 (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     */
    async function listPendingSkillWritesAction(agentId) {
        const response = await api.get(`/api/Chat/agent/${agentId}/skills/pending`, {
            params: { userId: currentUserId.value }
        });
        return response.data?.pending || [];
    }

    /**
     * 12b. 核准一筆待審核的技能寫入 (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     * @param {string} pendingId 待審核項目 ID
     */
    async function approvePendingSkillWriteAction(agentId, pendingId) {
        const response = await api.post(`/api/Chat/agent/${agentId}/skills/pending/${pendingId}/approve`, {}, {
            params: { userId: currentUserId.value }
        });
        return response.data;
    }

    /**
     * 12c. 拒絕（丟棄）一筆待審核的技能寫入 (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     * @param {string} pendingId 待審核項目 ID
     */
    async function rejectPendingSkillWriteAction(agentId, pendingId) {
        const response = await api.post(`/api/Chat/agent/${agentId}/skills/pending/${pendingId}/reject`, {}, {
            params: { userId: currentUserId.value }
        });
        return response.data;
    }

    /**
     * 13a. MCP 商店：讀取全平台共用的母版目錄（不需要 agentId）
     */
    async function fetchMcpCatalogAction() {
        const response = await api.get(`/api/Chat/mcp/catalog`);
        return response.data?.mcpServers || {};
    }

    /**
     * 13a-2. Skill 精選清單：管理員在後台挑的技能起手式，建立 agent 時可以直接勾選（不需要 agentId）
     */
    async function fetchSkillsCatalogAction() {
        const response = await api.get(`/api/Chat/skills/catalog`);
        return response.data?.skills || {};
    }

    /**
     * 13b. MCP 商店：讀取這個 agent 目前擁有哪些 MCP（常駐/選配/未選、憑證有沒有填）(🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     */
    async function fetchAgentMcpStateAction(agentId) {
        const response = await api.get(`/api/Chat/agent/${agentId}/mcp`, {
            params: { userId: currentUserId.value }
        });
        return response.data?.servers || {};
    }

    /**
     * 13c. MCP 商店：設為常駐 / 選配安裝 / 移除 (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     * @param {string} mcpName MCP 名稱
     * @param {string|null} selection null(移除) / "resident"(常駐) / "optional_installed"(選配已安裝)
     */
    async function setAgentMcpSelectionAction(agentId, mcpName, selection) {
        const response = await api.post(`/api/Chat/agent/${agentId}/mcp/${mcpName}/selection`, {
            Selection: selection
        }, {
            params: { userId: currentUserId.value }
        });
        return response.data;
    }

    /**
     * 13d. MCP 商店：填寫這個 MCP 的憑證欄位，實際值只會落地到該 agent 自己的 .env (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     * @param {string} mcpName MCP 名稱
     * @param {Object<string,string>} credentials 憑證欄位 key -> 值
     */
    async function setAgentMcpCredentialsAction(agentId, mcpName, credentials) {
        const response = await api.post(`/api/Chat/agent/${agentId}/mcp/${mcpName}/credentials`, {
            Credentials: credentials
        }, {
            params: { userId: currentUserId.value }
        });
        return response.data;
    }

    /**
     * 13e. Approval 設定：讀取這個 agent 目前的三個開關（mode/memory/skills）(🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     */
    async function fetchAgentApprovalsAction(agentId) {
        const response = await api.get(`/api/Chat/agent/${agentId}/approvals`, {
            params: { userId: currentUserId.value }
        });
        return response.data?.settings || {};
    }

    /**
     * 13f. Approval 設定：更新這個 agent 的三個開關，只更新有傳的欄位 (🔒 多租戶隔離)
     * @param {string} agentId 專家 ID
     * @param {{mode?: string, memoryWriteApproval?: boolean, skillsWriteApproval?: boolean}} settings
     */
    async function setAgentApprovalsAction(agentId, settings) {
        const response = await api.post(`/api/Chat/agent/${agentId}/approvals`, {
            Mode: settings.mode ?? null,
            MemoryWriteApproval: settings.memoryWriteApproval ?? null,
            SkillsWriteApproval: settings.skillsWriteApproval ?? null
        }, {
            params: { userId: currentUserId.value }
        });
        return response.data?.settings || {};
    }


    return {
        // 核心狀態
        rooms, currentRoomId, messages, isLoading, currentRoomFiles,
        // 用戶身分
        currentUserId,
        loginUserAction,
        logoutUserAction,
        // 房間操作
        fetchCurrentRoomFilesAction,
        fetchRoomsAction,
        createNewRoomAction,
        switchRoomAction,
        deleteRoomAction,
        updateMessage,
        updateRoomTitleAction,
        deleteRoomFileAction,
        // 訊息操作
        sendMessageAction,
        deleteMessage,
        // Agent 房間
        createAgentRoomAction,
        // Agent 大廳
        agents,
        currentAgentId,
        isAgentMarketMode,
        filteredRooms,
        currentAgent,
        fetchAgentsAction,
        createCustomAgentAction,
        enterAgentWorkspace,
        exitToGeneralRag,
        deleteAgentAction,
        // 🧠 雙軌記憶
        memoryPackage,
        userPackage,
        availableForkAgents,
        fetchAvailableForkAgents,
        submitApproveDecision,
        fetchAgentMemories,
        deleteSpecificFact,
        importBulkMemories,
        cloneAgentAction,
        exportAgentAction,
        importSkillAction,
        runSecurityAuditAction,
        searchSkillsHubAction,
        installSkillFromHubAction,
        listPendingSkillWritesAction,
        approvePendingSkillWriteAction,
        rejectPendingSkillWriteAction,
        fetchMcpCatalogAction,
        fetchSkillsCatalogAction,
        fetchAgentMcpStateAction,
        setAgentMcpSelectionAction,
        setAgentMcpCredentialsAction,
        fetchAgentApprovalsAction,
        setAgentApprovalsAction
    };
});