// 資料庫完整 CRUD 與 多聊天室(一對多) Google 聯網控制中心
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using System.Text;
using System.Text.Json;
using System.Net;
// using Microsoft.Data.SqlClient; // 如果有需要
using Npgsql; // 💡 確保頂部有引入 PostgreSQL 的驅動套件
// 💡 關鍵引用：引入您的 Models 檔案
using LMBackend; // 🌟 拿掉 .Data，直接參照根目錄
using LMBackend.Models; 
using UglyToad.PdfPig; // 🚀 引入 PdfPig 核心解析套件

using System.Text.Json.Serialization; // 🌟 確保這行有加，否則 [JsonPropertyName] 會報錯
using System.Net.Http.Json;           // 🌟 確保這行有加，否則 PostAsJsonAsync 與 ReadFromJsonAsync 會報錯
using LMBackend.Controllers;

namespace LMBackend.Controllers;

[ApiController]
[Route("api/[controller]")]
public class ChatController : ControllerBase
{
    private readonly AppDbContext _context;
    private readonly ILogger<ChatController> _logger;
    private readonly IHttpClientFactory _httpClientFactory; 
    public ChatController(AppDbContext context, ILogger<ChatController> logger, IHttpClientFactory httpClientFactory)
    {
        _context = context;
        _logger = logger;
        _httpClientFactory = httpClientFactory;
    }

    /// <summary>
    /// 核心共用引擎：將「Google 搜尋 ＋ 欄位大小寫忽略防禦 ＋ 呼叫 Python AI」完全封裝
    /// </summary>
/// <summary>
    /// 📄 穩健共用 RAG 引擎：完全保留您原本呼叫外層 Python app.py 的神聖邏輯，並注入連線池優化
    /// </summary>
    private async Task<(string Reply, string? SearchSources)> CallAIEngineAsync(string userMessage, bool isWebSearch, int roomId)
    {
        string? searchSourcesJson = null;
        _logger.LogInformation("[RAG-Engine] 🚀 進入舊 RAG 處理流程...");

        // 💡 升級：全面採用 _httpClientFactory，解決原有 new HttpClient() 的高併發 Socket 耗盡隱患
        var pythonClient = _httpClientFactory.CreateClient();
        pythonClient.Timeout = TimeSpan.FromMinutes(30); 

        _logger.LogInformation("[RAG-Engine] [C# 診斷] 前端傳入的 roomId 參數值為: {RoomId}", roomId);

        // 打包與原本一模一樣的 CamelCase Payload
        var llmRequest = new 
        { 
            userMessage = userMessage,   
            isWebSearch = isWebSearch,     
            max_tokens = 512,
            roomId = roomId,
        };
        
        var serializeOptions = new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };
        var jsonPayload = JsonSerializer.Serialize(llmRequest, serializeOptions);
        var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

        _logger.LogInformation("[RAG-Engine] 📡 準備連結 Python LLM Server...");
        
        // 直轟專案外層 docker app.py 的端點
        var llmResponse = await pythonClient.PostAsync("http://llm-service:8000/api/chat", content).ConfigureAwait(false);
        
        if (!llmResponse.IsSuccessStatusCode)
        {
            _logger.LogError("[RAG-Engine] ❌ Python LLM Server 回傳錯誤。狀態碼: {StatusCode}", llmResponse.StatusCode);
            throw new Exception($"Python LLM Server 回傳錯誤或拒絕連線。狀態碼: {llmResponse.StatusCode}");
        }
        
        var responseString = await llmResponse.Content.ReadAsStringAsync().ConfigureAwait(false);
        using var doc = JsonDocument.Parse(responseString);
        var rootElement = doc.RootElement;

        string reply = "";
        var replyProp = rootElement.GetProperty("reply");
        
        // 完美保留您對 Array 型態與 String 型態的雙向防禦
        if (replyProp.ValueKind == JsonValueKind.Array && replyProp.GetArrayLength() > 0)
        {
            reply = replyProp.GetString() ?? "";
        }
        else
        {
            reply = replyProp.GetString() ?? "";
        }

        if (rootElement.TryGetProperty("searchSources", out var sourcesProp) && sourcesProp.ValueKind == JsonValueKind.String)
        {
            searchSourcesJson = sourcesProp.GetString();
        }

        _logger.LogInformation("[RAG-Engine] 🎉 Python LLM 處理完畢，順利交棒。");
        
        return (reply, searchSourcesJson);
    }

    // =========================================================================
    // 此區塊為 聊天室(房間) 新增、刪除、查看 聊天室 以及 更新聊天室名稱
    // =========================================================================
    // =========================================================================
    // 💡Room 查詢(R) 所有聊天室端點：【查】撈取過往「所有聊天室清單」（用於左側邊欄渲染）
    // 前端：chat.js 函式：const switchRoomAction（查看使用者點選）
    // =========================================================================
    [HttpGet]
    [Route("/api/rooms")]
    public async Task<IActionResult> GetRooms([FromQuery] string? userId)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(userId))
            {
                return Ok(new List<object>());
            }

            var rooms = await _context.ChatRooms
                .Where(r => r.UserId == userId)
                .OrderByDescending(r => r.CreatedAt)
                .ToListAsync();
            return Ok(rooms);
        }
        catch (Exception ex)
        {
            return StatusCode(500, $"無法讀取聊天室清單: {ex.Message}");
        }
    }

    // =========================================================================
    // 💡 Room 新增(C) 新增一個聊天室端點：【增】點擊「+ 新增對話」時建立一個全新空白聊天室
    // 前端：chat.js 函式：const createNewRoomAction（新增一個空白的）
    // =========================================================================
    [HttpPost]
    [Route("/api/rooms")]
    public async Task<IActionResult> CreateRoom([FromBody] ChatRoomCreateDto? request)
    {
        try
        {
            var newRoom = new ChatRoom
            {
                Title = (request == null || string.IsNullOrWhiteSpace(request.Title)) ? "新的聊天對話" : request.Title,
                CreatedAt = DateTime.UtcNow,
                UserId = request?.UserId,
                AgentId = string.IsNullOrWhiteSpace(request?.AgentId) ? null : request.AgentId.Trim()
            };
            _context.ChatRooms.Add(newRoom);
            await _context.SaveChangesAsync();
            return Ok(newRoom);
        }
        catch (Exception ex)
        {
            return StatusCode(500, $"建立聊天室失敗: {ex.Message}");
        }
    }
    // =========================================================================
    // 💡 Room 刪除(D) 刪除一個聊天室端點：【刪】點擊「垃圾桶 刪除對話」時刪除一個舊有的聊天室
    // 前端：chat.js 函式：const deleteRoomAction（新增一個空白的）
    // =========================================================================
    [HttpDelete("/api/rooms/{roomId}")] // 👈 這裡必須是 HttpDelete，且前面要有斜線 /
    public async Task<IActionResult> DeleteRoom(int roomId, [FromQuery] string? userId)
    {
        try
        {
            var room = await _context.ChatRooms.FindAsync(roomId);
            if (room == null) return NotFound(new { message = "找不到該聊天室" });
            if (!string.IsNullOrWhiteSpace(userId) && room.UserId != userId) return StatusCode(403, new { message = "無權刪除其他使用者的聊天室" });

            _context.ChatRooms.Remove(room);
            await _context.SaveChangesAsync();

            return Ok(new { message = "聊天室已成功刪除" });
        }
        catch (Exception ex)
        {
            return StatusCode(500, $"刪除聊天室失敗: {ex.Message}");
        }
    }

    // =========================================================================
    // 💡 Room 更新(U) 更新一個聊天室端點名稱：【更】點擊「筆」時更新一個聊天室名稱
    // 前端：chat.js 函式：const updateRoomTitleAction（修改指定聊天室名稱）
    // =========================================================================
    [HttpPut("/api/rooms/{roomId}")] // 👈 加上前導斜線 / 進行絕對路由強制定位
    public async Task<IActionResult> UpdateRoomTitle(int roomId, [FromBody] RoomUpdateDto dto, [FromQuery] string? userId)
    {
        if (dto == null || string.IsNullOrWhiteSpace(dto.Title))
        {
            return BadRequest("聊天室名稱不能為空");
        }

        try
        {
            var room = await _context.ChatRooms.FindAsync(roomId);
            if (room == null) return NotFound(new { message = "找不到該聊天室" });
            if (!string.IsNullOrWhiteSpace(userId) && room.UserId != userId) return StatusCode(403, new { message = "無權修改其他使用者的聊天室" });

            room.Title = dto.Title;
            await _context.SaveChangesAsync();

            return Ok(new { id = room.Id, title = room.Title });
        }
        catch (Exception ex)
        {
            return StatusCode(500, $"修改聊天室名稱失敗: {ex.Message}");
        }
    }

    // 搭配的 DTO 類別
    public class RoomUpdateDto
    {
        public string Title { get; set; } = string.Empty;
    }



    // =========================================================================
    // 💡 messages 查詢(R) 聊天內容端點：【查】點擊某一間聊天室時，精準撈出「該聊天室內部」的歷史對話
    // 前端：chat.js 函式：const sendMessageAction（修改指定聊天室名稱）
    // =========================================================================
    [HttpGet]
    [Route("/api/rooms/{roomId}/messages")]
    public async Task<IActionResult> GetRoomMessages(int roomId, [FromQuery] string? userId)
    {
        try
        {
            var room = await _context.ChatRooms.FirstOrDefaultAsync(r => r.Id == roomId);
            if (room == null)
            {
                return NotFound(new { message = "找不到指定的聊天室。" });
            }
            if (!string.IsNullOrWhiteSpace(userId) && room.UserId != userId)
            {
                return StatusCode(403, new { message = "無權查看其他使用者的聊天室" });
            }

            // 💡 精準過濾：只抓出屬於特定 ChatRoomId 的子對話紀錄
            var dbMessages = await _context.Messages
                .Where(m => m.ChatRoomId == roomId)
                .OrderBy(m => m.Timestamp)
                .ToListAsync();

            var history = new List<object>();
            
            foreach (var msg in dbMessages)
            {
                var sourcesObj = !string.IsNullOrEmpty(msg.SearchSources) 
                    ? JsonSerializer.Deserialize<object>(msg.SearchSources) 
                    : null;

                history.Add(new { Id = msg.Id, Role = "user", Content = msg.UserInput, RequestUuid = msg.RequestUuid });
                history.Add(new { Id = msg.Id, Role = "assistant", Content = msg.Response, SearchSources = sourcesObj, RequestUuid = msg.RequestUuid });
            }
            return Ok(history);
        }
        catch (Exception ex) 
        { 
            return StatusCode(500, $"無法讀取歷史紀錄: {ex.Message}"); 
        }
    }

    // ===================================================================================================================================
    // 此區塊為 聊天訊息 使用者 傳送(輸入) 以及 刪除、查看、更新(重新詢問) 問題 
    // ===================================================================================================================================


    /// <summary>
    /// 【增】接收使用者發問、呼叫共用 AI 引擎並存入指定聊天室
    /// </summary>
    // =========================================================================
    // 💡 messages 新增(C) 使用者Prompt傳過來訊息的端點
    // 前端：chat.js 函式：const sendMessageAction（使用者傳輸的訊息）
    // LLM 端：app.py 函式：async def chat(request: ChatRequest)（往後交給LLM處理）
    // 分流：Hermas-Agent輸入 與 普通LLM+RAG輸入做個區隔
    // =========================================================================
    /// <summary>
    /// 【升級版】接收使用者發問、自動判定房間型態（純 RAG vs Hermes Agent）並動態路由分流
    /// </summary>
       /// <summary>
    /// 【旗艦升級版】接收使用者發問、自動判定房間型態（純 RAG vs Hermes Agent）並動態路由分流
    /// </summary>
   [HttpPost("/api/chat")] 
    public async Task SendMessage([FromBody] JsonElement rawJson) // 💡 修正 1：回傳值改為 Task，不回傳 IActionResult
    {
        var response = HttpContext.Response;

        try
        {
            // 🆔 當次對話專屬 UUID：一進入就生成，貫穿整個請求生命週期
            string currentRequestUuid = Guid.NewGuid().ToString("D");

            // 💡 1. 從前端 JSON 中精準拔出所需的欄位
            string message = rawJson.TryGetProperty("message", out var mProp) ? mProp.GetString() ?? "" : "";
            bool isWebSearch = rawJson.TryGetProperty("isWebSearch", out var wProp) && wProp.GetBoolean(); 
            
            int chatRoomId = 0;
            if (rawJson.TryGetProperty("roomId", out var rProp)) chatRoomId = rProp.GetInt32();
            else if (rawJson.TryGetProperty("chatRoomId", out var crProp)) chatRoomId = crProp.GetInt32();

            if (string.IsNullOrWhiteSpace(message))
            {
                response.StatusCode = 400;
                await response.WriteAsync("訊息內容不能為空");
                return;
            }
            if (chatRoomId <= 0)
            {
                response.StatusCode = 400;
                await response.WriteAsync("未指定有效的聊天室 ID");
                return;
            }

            // 直接查詢該房間是否綁定 agent_id，並同步拉出母表的 system_prompt
            var roomInfo = await _context.ChatRooms
                .Where(r => r.Id == chatRoomId)
                .Select(r => new {
                    r.AgentId, 
                    r.UserId,
                    SystemPrompt = _context.Agents.Where(a => a.AgentId == r.AgentId).Select(a => a.SystemPrompt).FirstOrDefault()
                })
                .FirstOrDefaultAsync();

            if (roomInfo == null)
            {
                _logger.LogWarning("找不到指定的聊天室 ID: {ChatRoomId}", chatRoomId);
                response.StatusCode = 404;
                await response.WriteAsync("找不到指定的聊天室資訊");
                return;
            }

            // =========================================================================
            // 🚀 核心智慧分流路徑（依據 AgentId 存在與否完美分流）
            // =========================================================================
            if (!string.IsNullOrEmpty(roomInfo.AgentId))
            {
                _logger.LogInformation("房間 {RoomId} 已綁定 Agent [{AgentId}]，啟動 Hermes 記憶隔離高效能串流管線...", chatRoomId, roomInfo.AgentId);
                
                // 🤖 助理模式：直接全面接管 HttpContext.Response，徹底繞過 406 內容協商防禦
                response.StatusCode = 200;
                response.ContentType = "text/event-stream";
                response.Headers.CacheControl = "no-cache";
                response.Headers.Connection = "keep-alive";
                response.Headers.TryAdd("X-Accel-Buffering", "no"); // 防禦 Nginx 緩衝

                var fullReplyBuilder = new StringBuilder();

                // 🚀 每位使用者專屬 Hermes Runtime：先跟 Runtime Provisioner 要到這個使用者的專屬容器網址
                string hermesBaseUrl = await EnsureUserHermesRuntimeAsync(roomInfo.UserId);

                // 依標準 SSE 格式送出一段安全文字（沒有特殊控制標記的一般聊天內容）
                async Task WriteSseDataAsync(string text)
                {
                    if (text.Length == 0) return;
                    var safeText = text.Replace("\r", "").Replace("\n", "\\n");
                    await response.WriteAsync($"data: {safeText}\n\n");
                    await response.Body.FlushAsync();
                }

                // 🛡️ 重組緩衝區：CallAgentEngineStreamAsync 是用固定大小的原始位元組緩衝區在讀取，
                // 完全不保證 Python 那邊一行一行 yield 出來的界線（例如 __APPROVAL_REQUIRED__:...、
                // __SKILL_SUGGESTED__:... 這些控制標記）不會被硬切成兩半、分散在兩個獨立的 SSE 封包裡。
                // 一旦切斷，前端的 cleanToken.includes('__XXX__') 永遠抓不到完整字串。這裡改成先在
                // 後端把原始串流重組成完整的行／標記，才轉發給前端。未來新增其他標記只要加進這個陣列即可。
                // 🆕 0716：main.py 全面改用 hermes acp 之後多了 4 種結構化事件標記，
                // 一併加進重組緩衝區的辨識清單，否則會被硬切成兩半、前端永遠抓不到完整 JSON
                string[] markerPrefixes = {
                    "__APPROVAL_REQUIRED__:", "__SKILL_SUGGESTED__:",
                    "__ACP_THOUGHT__:", "__ACP_TOOL__:", "__ACP_PLAN__:", "__ACP_USAGE__:"
                };
                int maxMarkerPrefixLength = markerPrefixes.Max(p => p.Length);
                string pendingTail = "";

                // 呼叫改裝後的異步流式傳輸引擎
                await foreach (var rawToken in CallAgentEngineStreamAsync(message, roomInfo.AgentId, chatRoomId, roomInfo.SystemPrompt ?? "", hermesBaseUrl))
                {
                    string combined = pendingTail + rawToken;
                    pendingTail = "";

                    while (true)
                    {
                        // 找出目前緩衝區裡「最早出現」的任何一種控制標記
                        int markerIdx = -1;
                        string matchedPrefix = null;
                        foreach (var prefix in markerPrefixes)
                        {
                            int idx = combined.IndexOf(prefix, StringComparison.Ordinal);
                            if (idx >= 0 && (markerIdx < 0 || idx < markerIdx))
                            {
                                markerIdx = idx;
                                matchedPrefix = prefix;
                            }
                        }
                        if (markerIdx < 0) break;

                        // 標記前面的部分是正常聊天內容，先落袋
                        string before = combined.Substring(0, markerIdx);
                        fullReplyBuilder.Append(before);
                        await WriteSseDataAsync(before);

                        string afterMarkerStart = combined.Substring(markerIdx + matchedPrefix.Length);
                        int newlineIdx = afterMarkerStart.IndexOf('\n');
                        if (newlineIdx < 0)
                        {
                            // 標記內容還沒收全（被切在中間），整段先掛起等下一批資料
                            pendingTail = combined.Substring(markerIdx);
                            combined = "";
                            break;
                        }

                        // 標記本體已完整收到：當成獨立的控制訊號送出，不算進聊天回覆內容
                        string markerContent = afterMarkerStart.Substring(0, newlineIdx);
                        await WriteSseDataAsync($"{matchedPrefix}{markerContent}");

                        combined = afterMarkerStart.Substring(newlineIdx + 1);
                    }

                    if (combined.Length == 0) continue;

                    // 沒偵測到完整標記，但結尾可能是某個標記前綴的開頭片段，保留一小段當緩衝，其餘正常送出
                    int keepBack = Math.Min(combined.Length, maxMarkerPrefixLength - 1);
                    string safeToFlush = combined.Substring(0, combined.Length - keepBack);
                    pendingTail += combined.Substring(combined.Length - keepBack);

                    fullReplyBuilder.Append(safeToFlush);
                    await WriteSseDataAsync(safeToFlush);
                }

                // 串流結束後，殘留的緩衝一定不是控制標記了（否則就是格式異常），照普通文字送出即可
                if (pendingTail.Length > 0)
                {
                    fullReplyBuilder.Append(pendingTail);
                    await WriteSseDataAsync(pendingTail);
                }

                string finalReply = fullReplyBuilder.ToString();

                // 💡 串流結束後，後端默默進行「記憶落盤與相容性儲存」
                var messageLog = new Message
                {
                    ChatRoomId = chatRoomId, 
                    UserInput = message,
                    Response = finalReply,
                    SearchSources = null,
                    RequestUuid = currentRequestUuid,
                    Timestamp = DateTime.UtcNow
                };

                _context.Messages.Add(messageLog);
                await _context.SaveChangesAsync();

                // 💡 發送最後一發特殊 SSE 封包，將與原本格式完全一致的 JSON 推給前端
                var finalJson = JsonSerializer.Serialize(new { 
                    id = messageLog.Id, 
                    reply = finalReply, 
                    searchSources = Array.Empty<object>(),
                    requestUuid = currentRequestUuid
                });
                
                await response.WriteAsync($"event: final_result\ndata: {finalJson}\n\n");
                await response.Body.FlushAsync();

                return; // 💡 修正 2：直接 return 結束方法，不透過 MVC Result 機制，徹底根除 406
            }
            else
            {
                // 📄 軌道 A：純 RAG 模式（完全維持你原本穩健的共用 AI 引擎與整塊回傳邏輯，互不干擾）
                _logger.LogInformation("房間 {RoomId} 為一般聊天室，啟動純 RAG 模式...", chatRoomId);
                
                var aiResult = await CallAIEngineAsync(message, isWebSearch, chatRoomId);
                
                var messageLog = new Message
                {
                    ChatRoomId = chatRoomId, 
                    UserInput = message,
                    Response = aiResult.Reply,
                    SearchSources = aiResult.SearchSources,
                    RequestUuid = currentRequestUuid,
                    Timestamp = DateTime.UtcNow
                };

                _context.Messages.Add(messageLog);
                await _context.SaveChangesAsync();

                // 💡 修正 3：傳統模式也改用 WriteAsJsonAsync 直接輸出，繞過 406 內容協商
                response.StatusCode = 200;
                response.ContentType = "application/json";
                await response.WriteAsJsonAsync(new { 
                    id = messageLog.Id, 
                    reply = aiResult.Reply, 
                    searchSources = messageLog.SearchSources != null ? JsonSerializer.Deserialize<object>(messageLog.SearchSources) : Array.Empty<object>(),
                    requestUuid = currentRequestUuid
                });
                return;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "處理發送訊息時發生系統內部錯誤。");
            
            // 💡 修正 4：異常處理也直接寫入 Response Body
            if (!response.HasStarted)
            {
                response.StatusCode = 500;
                response.ContentType = "text/plain; charset=utf-8";
                await response.WriteAsync($"系統內部錯誤: {ex.Message}");
            }
        }
    }


    /// <summary>
    /// 🚀 Runtime Provisioner 客戶端：跟「離 Hermes 最近」的前門服務要一個該使用者專屬的
    /// Hermes Runtime 容器（不存在就請它建立），回傳可直接呼叫的內部網址。
    /// backend 本身完全不碰 Docker，權限收斂在 hermes-agent-proxy 那一側。
    /// </summary>
    private async Task<string> EnsureUserHermesRuntimeAsync(string? userId)
    {
        // 沒有 userId 的舊資料/測試房間，暫時退回共用前門服務，避免中斷既有流程
        if (string.IsNullOrWhiteSpace(userId))
        {
            return "http://hermes-agent-proxy:8643";
        }

        var client = _httpClientFactory.CreateClient();
        // 🚀 給足時間讓 Python 端等新容器的 uvicorn 真正就緒（那邊內部最長會等 30 秒）
        client.Timeout = TimeSpan.FromSeconds(45);

        var response = await client.PostAsJsonAsync("http://hermes-agent-proxy:8643/api/runtime/ensure", new { user_id = userId });

        if (!response.IsSuccessStatusCode)
        {
            var errorDetail = await response.Content.ReadAsStringAsync();
            _logger.LogError("[Runtime Provisioner] 為使用者 {UserId} 建立專屬 Runtime 失敗: {Detail}", userId, errorDetail);
            throw new Exception($"無法建立使用者專屬 Hermes Runtime: {errorDetail}");
        }

        var result = await response.Content.ReadFromJsonAsync<JsonElement>();
        return result.GetProperty("base_url").GetString() ?? "http://hermes-agent-proxy:8643";
    }

    /// <summary>
    /// 🚀 依 AgentId 查出真正的擁有者 UserId 來解析 Runtime 位址（比信任呼叫端傳入的 userId 更準確），
    /// 找不到 Agent 紀錄時退回呼叫端傳入的 userId，維持向下相容。
    /// </summary>
    private async Task<string> ResolveHermesBaseUrlForAgentAsync(string agentId, string? fallbackUserId)
    {
        var ownerUserId = await _context.Agents
            .Where(a => a.AgentId == agentId)
            .Select(a => a.UserId)
            .FirstOrDefaultAsync();

        return await EnsureUserHermesRuntimeAsync(ownerUserId ?? fallbackUserId);
    }

    /// <summary>
    /// 🚀 拓荒通訊命脈：改裝為基於 ResponseHeadersRead 的高效能流式傳輸中轉管線
    /// 💡 使用官方標準的 async + yield return 寫法，徹底排除編編錯誤，絕對穩健！
    /// </summary>
    private async IAsyncEnumerable<string> CallAgentEngineStreamAsync(
        string message,
        string agentId,
        int roomId,
        string systemPrompt,
        string hermesBaseUrl,
        [System.Runtime.CompilerServices.EnumeratorCancellation] System.Threading.CancellationToken cancellationToken = default)
    {
        // 🚀 改為打向該使用者專屬的 Hermes Runtime 容器，而非固定共用位址
        string url = $"{hermesBaseUrl}/api/agent/chat/stream";

        var payload = new
        {
            agent_id = agentId,
            room_id = roomId.ToString(),
            system_prompt = systemPrompt,
            message = message
        };

        var client = _httpClientFactory.CreateClient();
        client.Timeout = TimeSpan.FromMinutes(30); // 確保大模型長文本推理不逾時

        var jsonContent = new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json");

        // 建立請求並手動設定為 POST
        using var request = new HttpRequestMessage(HttpMethod.Post, url) { Content = jsonContent };

        // 🌟 核心關鍵：使用 HttpCompletionOption.ResponseHeadersRead 
        // 只要 Python 網關一回傳 Header，C# 立刻放行向下走，絕不在記憶體中緩衝整個 Body！
        using var response = await client.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            string errorDetail = await response.Content.ReadAsStringAsync(cancellationToken);
            _logger.LogError("[C# 交通警察] ❌ Hermes 串流容器拒絕請求。狀態碼: {StatusCode}, 詳情: {Detail}", response.StatusCode, errorDetail);
            throw new Exception($"Hermes 串流引擎錯誤 ({response.StatusCode}): {errorDetail}");
        }

        // 讀取底層網路流，來一個字元處理一個字元
        using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var reader = new StreamReader(stream, Encoding.UTF8);

        char[] buffer = new char[1024]; // 緩衝區大小
        int bytesRead;

        _logger.LogInformation("[C# 交通警察] 📡 Hermes 串流管線已成功建立，開始即時泵出 Token... Agent: {AgentId}, Room: {RoomId}", agentId, roomId);

        // 使用標準的 yield return，讓 C# 狀態機自動幫我們處理 IAsyncEnumerable 的迭代細節
        while ((bytesRead = await reader.ReadAsync(buffer, 0, buffer.Length)) > 0)
        {
            if (cancellationToken.IsCancellationRequested) break;
            yield return new string(buffer, 0, bytesRead);
        }
        
        _logger.LogInformation("[C# 交通警察] 🎉 Hermes 串流完全終止且回收完成。");
    }

    /// <summary>
    /// 🚀 拓荒通訊命脈：將物理隔離金鑰打包，轟向 Docker 內部的 Hermes 引擎
    /// </summary>
    // private async Task<string> CallAgentEngineAsync(string message, string agentId, int roomId, string systemPrompt)
    // {
    //     // 💡 萬能終點：直轟我們在 docker-compose 內定義的全新獨立 hermes-agent 容器（8643埠）
    //     string url = "http://hermes-agent:8643/api/agent/chat"; 

    //     // 💡 交通警察極簡通訊協定：將大腦提示詞、物理隔離金鑰與房間 ID 一併打包送過去
    //     // 讓 Python Hermes 中控在完全不連 PostgreSQL 的情況下，盲目收下參數並進行實體硬碟讀寫
    //     var payload = new
    //     {
    //         agent_id = agentId,
    //         room_id = roomId.ToString(),
    //         system_prompt = systemPrompt,
    //         message = message
    //     };

    //     var jsonContent = new StringContent(
    //         JsonSerializer.Serialize(payload),
    //         Encoding.UTF8,
    //         "application/json"
    //     );

    //     var client = _httpClientFactory.CreateClient();
    //     client.Timeout = TimeSpan.FromMinutes(30); // 給予大模型足夠的推理思考緩衝時間
        
    //     try
    //     {
    //         _logger.LogInformation("[C# 交通警察] 📡 正在將專家請求轉發給 Hermes 中控... Agent: {AgentId}, Room: {RoomId}", agentId, roomId);
    //         var response = await client.PostAsync(url, jsonContent);
            
    //         if (!response.IsSuccessStatusCode)
    //         {
    //             string errorDetail = await response.Content.ReadAsStringAsync();
    //             _logger.LogError("[C# 交通警察] ❌ Hermes 中控容器拒絕請求。狀態碼: {StatusCode}, 詳情: {Detail}", response.StatusCode, errorDetail);
    //             throw new Exception($"Hermes 中控引擎錯誤 ({response.StatusCode}): {errorDetail}");
    //         }

    //         string jsonResult = await response.Content.ReadAsStringAsync();
    //         using var doc = JsonDocument.Parse(jsonResult);
            
    //         // 💡 精準解析 Python Hermes 中控回傳的極簡規格 {"reply": "..."}
    //         if (doc.RootElement.TryGetProperty("reply", out var replyProp))
    //         {
    //             _logger.LogInformation("[C# 交通警察] 🎉 Hermes 中控成功完成記憶沉澱與模型推理，已安全回收回覆！");
    //             return replyProp.GetString() ?? "助理未能產生有效回覆。";
    //         }
            
    //         return jsonResult;
    //     }
    //     catch (HttpRequestException ex)
    //     {
    //         _logger.LogError(ex, "[C# 交通警察] 🚨 連線至 Hermes 中控服務失敗。請檢查 8643 埠口是否成功通電。");
    //         throw new Exception($"無法連線至 Hermes 記憶隔離網關。內部訊息: {ex.Message}");
    //     }
    // }



    public class AIResult
    {
        public string Reply { get; set; } = string.Empty;
        public string? SearchSources { get; set; }
    }
    /// <summary>
    /// 【改】修改舊問題、調用共用 AI 引擎並更新覆蓋 PostgreSQL 欄位
    /// </summary>
    // =========================================================================
    // 💡 messages 修改(U) 修改使用者已經有的訊息 並重新詢問
    // 前端：chat.js 函式：const updateMessage（使用者修改的訊息）
    // LLM 端：app.py 函式：async def chat(request: ChatRequest)（將修改過的往後交給LLM處理）
    // =========================================================================
    [HttpPut]
    [Route("/api/messages/{id}")]
    public async Task<IActionResult> UpdateMessage(int id, [FromBody] ChatRequest request, [FromQuery] string? userId)
    {
        if (request == null || string.IsNullOrWhiteSpace(request.Message))
        {
            return BadRequest("修改內容不能為空");
        }

        try
        {
            var existingMessage = await _context.Messages.FindAsync(id);
            if (existingMessage == null)
            {
                return NotFound(new { message = "找不到此訊息，無法修改。" });
            }

            // 💡 多租戶防護：確保該訊息屬於請求的 userId
            if (!string.IsNullOrWhiteSpace(userId))
            {
                var room = await _context.ChatRooms.FindAsync(existingMessage.ChatRoomId);
                // ✨ 修正後的正確寫法
                if (room == null || room.UserId != userId)
                {
                    return StatusCode(403, new { message = "無權修改其他使用者的訊息。" });
                }

            }

            var aiResult = await CallAIEngineAsync(request.Message, request.IsWebSearch,request.RoomId);

            existingMessage.UserInput = request.Message;
            existingMessage.Response = aiResult.Reply;
            existingMessage.SearchSources = aiResult.SearchSources; 
            existingMessage.Timestamp = DateTime.UtcNow;

            await _context.SaveChangesAsync();

            return Ok(new { 
                id = existingMessage.Id, 
                reply = aiResult.Reply, 
                searchSources = aiResult.SearchSources != null ? JsonSerializer.Deserialize<object>(aiResult.SearchSources) : null 
            });
        }
        catch (Exception ex)
        {
            return StatusCode(500, $"修改訊息失敗: {ex.Message}");
        }
    }

    /// <summary>
    /// 【刪】收回聊天紀錄
    /// </summary>
    // =========================================================================
    // 💡 messages 刪除(D) 收回使用者訊息
    // 前端：chat.js 函式：const deleteMessage（刪除使用者訊息）
    // =========================================================================
    [HttpDelete]
    [Route("/api/messages/{id}")]
    public async Task<IActionResult> DeleteMessage(int id, [FromQuery] string? userId)
    {
        try
        {
            var message = await _context.Messages.FindAsync(id);
            if (message == null) 
            {
                return NotFound(new { message = "找不到此訊息，無法收回。" });
            }

            // 💡 多租戶防護：通過 room 反查 userId
            if (!string.IsNullOrWhiteSpace(userId))
            {
                var room = await _context.ChatRooms.FindAsync(message.ChatRoomId);
                // ✨ 修正後的正確寫法
                if (room == null || room.UserId != userId)
                {
                    return StatusCode(403, new { message = "無權刪除其他使用者的訊息。" });
                }

            }

            _context.Messages.Remove(message);
            await _context.SaveChangesAsync();
            return Ok(new { message = "訊息已成功收回" });
        }
        catch (Exception ex) 
        { 
            return StatusCode(500, $"收回訊息失敗: {ex.Message}"); 
        }
    }

    /// <summary>
    /// 【刪】刪除聊天室 + 檢查多租戶隔離
    /// </summary>
    // [HttpDelete("/api/rooms/{id}")]
    // public async Task<IActionResult> DeleteRoom(int id, [FromQuery] string? userId)
    // {
    //     try
    //     {
    //         var room = await _context.ChatRooms.FindAsync(id);
    //         if (room == null) return NotFound(new { message = "找不到指定的聊天室。" });

    //         // 💡 多租戶防護：確保該房間屬於請求的 userId
    //         // ✨ 修正後的正確寫法
    //         if (!string.IsNullOrWhiteSpace(userId) && room.UserId != userId)
    //         {
    //             return StatusCode(403, new { message = "無權刪除其他使用者的聊天室。" });
    //         }


    //         _context.ChatRooms.Remove(room);
    //         await _context.SaveChangesAsync();
    //         return Ok(new { message = "聊天室已成功刪除！" });
    //     }
    //     catch (Exception ex)
    //     {
    //         return StatusCode(500, $"後端刪除錯誤: {ex.Message}");
    //     }
    // }

    // ===================================================================================================================================
    // 此區塊為 RAG 新增、刪除、查看 文件
    // ===================================================================================================================================

    // =========================================================================
    // 🚀 新增RAG端點：【增】POST /api/rooms/{roomId}/upload - 接收拉入的檔案並推入 RAG
    // 前端：chat.js 函式：const fetchCurrentRoomFilesAction（接收 RAG 由前端來的文件）
    // LLM RAG端：app.py 函式：async def rag_upload_document (推送給python進行RAG Chunk切分)
    // =========================================================================
    [HttpPost("/api/rooms/{roomId}/upload")]
    public async Task<IActionResult> UploadDocumentForRag(int roomId, IFormFile file, [FromQuery] string? userId)
    {
        // 1. 安全防禦：檢查聊天室是否存在，以及檔案是否有效
        if (file == null || file.Length == 0)
        {
            return BadRequest("上傳的檔案無效或內容為空");
        }

        // 💡 多租戶防護：確保該房間屬於請求的 userId
        var room = await _context.ChatRooms.FindAsync(roomId);
        if (room == null)
        {
            return NotFound(new { message = "找不到指定的聊天室，無法綁定知識庫" });
        }
        // ✨ 修正後的正確寫法
        if (!string.IsNullOrWhiteSpace(userId) && room.UserId != userId)
        {
            return StatusCode(403, new { message = "無權上傳檔案到其他使用者的聊天室。" });
        }


        // 2. 放寬限制：允許 .txt, .md 以及全新的開源解析 .pdf
        var extension = Path.GetExtension(file.FileName).ToLower();
        var allowedExtensions = new[] { ".txt", ".md", ".pdf" };

        if (!allowedExtensions.Contains(extension))
        {
            return BadRequest("目前知識庫僅支援純文字檔案 (.txt)、Markdown (.md) 以及文件檔案 (.pdf)");
        }

        try
        {
            // 3. 根據副檔名分流：讀取檔案內部的純文字大字串
            string fileContent = string.Empty;

            if (extension == ".pdf")
            {
                // 🚀 使用 PdfPig 在記憶體內逐頁將 PDF 實體文字摳出來
                using (var stream = file.OpenReadStream())
                using (var pdfDocument = PdfDocument.Open(stream))
                {
                    var sb = new StringBuilder();
                    foreach (var page in pdfDocument.GetPages())
                    {
                        // 為每一頁加上頁碼標記，這能讓 Python 切片時保留頁碼上下文，極度有利於 RAG 溯源
                        sb.AppendLine($"--- Page {page.Number} ---");
                        sb.AppendLine(page.Text);
                    }
                    fileContent = sb.ToString();
                }
            }
            else
            {
                // 原有的 .txt 與 .md 讀取邏輯保持不變
                using (var reader = new StreamReader(file.OpenReadStream(), Encoding.UTF8))
                {
                    fileContent = await reader.ReadToEndAsync();
                }
            }

            // 安全防禦：避免塞入空字串導致 Python 的 ai_client.embeddings 崩潰
            if (string.IsNullOrWhiteSpace(fileContent))
            {
                return BadRequest("檔案內容解析失敗或內容為空（若為 PDF，請檢查是否為全圖片構成的掃描件）。");
            }
            // =========================================================================
            // 💡 🛡️ 發送訊息給App.py 
            //  發送函式：async def rag_upload_document(req: RagUploadRequest):
            //  發送路由：@app.post("/api/rag/upload")
            //  發送格式：json
            // =========================================================================
            // 4. 跨容器通訊：完全對齊您的 app.py Payload 欄位規格 (roomId, fileName, fileContent)
            using var pythonClient = new HttpClient();
            pythonClient.Timeout = TimeSpan.FromMinutes(30); // 給予充足的轉向量緩衝時間
            // =========================================================================
            // class RagUploadRequest(BaseModel):
            //      roomId: str
            //      fileName: Optional[str] = "unknown_file"
            //      fileContent: str
            // =========================================================================
            var ragPayload = new
            {
                roomId = roomId.ToString(),
                fileName = file.FileName,
                fileContent = fileContent // 這裡已完美熔接了 PDF 的大字串
            };

            var jsonPayload = JsonSerializer.Serialize(ragPayload, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase });
            var httpContent = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

            Console.WriteLine($"[C# RAG-FORWARD] 正在將檔案 {file.FileName} 轉發給 Python 向量化中...");
            // 精準對齊您的容器域名與 Python /api/rag/upload 路由
            var pythonResponse = await pythonClient.PostAsync("http://llm-service:8000/api/rag/upload", httpContent);
            
            if (!pythonResponse.IsSuccessStatusCode)
            {
                var errBody = await pythonResponse.Content.ReadAsStringAsync();
                throw new Exception($"Python RAG 服務端回傳錯誤: {errBody}");
            }

             // 5. 💡 終極防禦：維持您的高容錯原生 SQL 寫入（全小寫 document_files 結構）
             string sql = @"
                INSERT INTO document_files (room_id, file_name, file_path, file_size, uploaded_at) 
                VALUES ({0}, {1}, {2}, {3}, {4})";
                
            await _context.Database.ExecuteSqlRawAsync(sql, 
                roomId, 
                file.FileName, 
                "Docker_Volume_Chroma_Indexed", 
                file.Length, 
                DateTime.UtcNow
            );

            // 6. 讀取 Python 回傳的切片統計資訊並回傳前端 Vue 3
            var responseString = await pythonResponse.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(responseString);
            int chunksCount = doc.RootElement.GetProperty("chunksCount").GetInt32();

            Console.WriteLine($"[C# RAG-FORWARD] ✅ 檔案 {file.FileName} 已成功透過原生 SQL 入庫！切片數: {chunksCount}");
            return Ok(new
            {
                message = "知識庫文件已成功上傳並完成向量化切片",
                fileName = file.FileName,
                chunksCount = chunksCount
            });

        }
        catch (Exception ex)
        {
            Console.WriteLine($"[❌ C# RAG-UPLOAD 內部崩潰]: {ex.Message}");
            return StatusCode(500, $"後端 RAG 處理失敗: {ex.Message}");
        }
    }
    
    // =========================================================================
    // 🚀 新增端點：【查】GET /api/rooms/{roomId}/files - 獲取該房間已綁定的文件標籤清單
    // =========================================================================
    // =========================================================================
    // 🚀 修正版：改用 FromSqlRaw 進行原生 SQL 查詢，100% 免疫 EF Core 內存結構衝突！
    // =========================================================================
    [HttpGet("/api/rooms/{roomId}/files")]
    public async Task<IActionResult> GetRoomUploadedFiles(int roomId, [FromQuery] string? userId)
    {
        // 💡 多租戶防護：確保該房間屬於請求的 userId
        var room = await _context.ChatRooms.FindAsync(roomId);
        if (room == null)
        {
            return NotFound(new { message = "找不到指定的聊天室。" });
        }
        // ✨ 修正後的正確寫法
        if (!string.IsNullOrWhiteSpace(userId) && room.UserId != userId)
        {
            return StatusCode(403, new { message = "無權查看其他使用者的文件。" });
        }


        var fileList = new List<object>();
        
        try
        {
            // 1. 直接向 DbContext 借用最底層、最真實的資料庫連線字串
            var connString = _context.Database.GetConnectionString();
            
            // 2. 使用 NpgsqlConnection 建立純粹的 ADO.NET 資料庫通道
            using (var conn = new NpgsqlConnection(connString))
            {
                await conn.OpenAsync();
                
                // 3. 執行最純粹的全小寫 SQL 指令
                string sql = "SELECT id, room_id, file_name, file_size FROM document_files WHERE room_id = @roomId ORDER BY uploaded_at ASC";
                
                using (var cmd = new NpgsqlCommand(sql, conn))
                {
                    cmd.Parameters.AddWithValue("@roomId", roomId);
                    
                    using (var reader = await cmd.ExecuteReaderAsync())
                    {
                        while (await reader.ReadAsync())
                        {
                            // 4. 手動一筆一筆拔出欄位，精準組裝成前端需要的小寫 DTO 格式
                            fileList.Add(new {
                                id = reader.GetInt32(0),
                                roomId = reader.GetInt32(1),
                                fileName = reader.GetString(2),
                                fileSize = reader.GetInt64(3)
                            });
                        }
                    }
                }
            }

            Console.WriteLine($"[C# RAG-FETCH] 成功為房間 {roomId} 撈出 {fileList.Count} 個知識庫標籤。");
            return Ok(fileList);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[❌ GetRoomUploadedFiles 終極崩潰]: {ex.Message}");
            return StatusCode(500, $"撈取文件標籤清單失敗: {ex.Message}");
        }
    }


    // =========================================================================
    // 🚀 補齊 RAG CRUD [D]：【刪】DELETE /api/rooms/{roomId}/files - 同步擦除知識庫
    // 前端：chat.js 函式：const deleteRoomFileAction（刪除既有的 RAG 知識庫）
    // LLM RAG端：app.py 函式：async def rag_delete_document (推送給python進行RAG 刪除處理)
    // =========================================================================
    [HttpDelete("/api/rooms/{roomId}/files")]
    public async Task<IActionResult> DeleteDocumentForRag(int roomId, [FromQuery] string fileName, [FromQuery] string? userId)
    {
        // 💡 多租戶防護：確保該房間屬於請求的 userId
        var room = await _context.ChatRooms.FindAsync(roomId);
        if (room == null)
        {
            return NotFound(new { message = "找不到指定的聊天室。" });
        }
        // ✨ 修正後的正確寫法
        if (!string.IsNullOrWhiteSpace(userId) && room.UserId != userId)
        {
            return StatusCode(403, new { message = "無權刪除其他使用者的文件。" });
        }


        if (string.IsNullOrWhiteSpace(fileName))
        {
            return BadRequest("未指定要刪除的檔案名稱。");
        }

        try
        {
            Console.WriteLine($"[C# RAG-DELETE] 準備刪除房間 {roomId} 的文件: {fileName}");

            // 1. 跨容器通訊：通知 Python 抹除向量 (URL 帶入 Query String，符合 Python 端接收規範)
            using var pythonClient = new HttpClient();
            pythonClient.Timeout = TimeSpan.FromSeconds(30);

            // 確保檔案名稱有進行 URL 編碼，防止特殊字元或副檔名點號造成路徑解析出錯
            var encodedFileName = Uri.EscapeDataString(fileName);
            var pythonUrl = $"http://llm-service:8000/api/rag/delete?room_id={roomId}&file_name={encodedFileName}";

            var pythonResponse = await pythonClient.DeleteAsync(pythonUrl);
            
            if (!pythonResponse.IsSuccessStatusCode)
            {
                var errBody = await pythonResponse.Content.ReadAsStringAsync();
                throw new Exception($"Python 向量刪除失敗: {errBody}");
            }

            // 2. 💡 終極防禦：改用 ExecuteSqlRawAsync，直接對 SQL 資料庫高容錯刪除紀錄
            // 延續全小寫的資料表結構設計
            string sql = "DELETE FROM document_files WHERE room_id = {0} AND file_name = {1}";
            int affectedRows = await _context.Database.ExecuteSqlRawAsync(sql, roomId, fileName);

            Console.WriteLine($"[C# RAG-DELETE] ✅ 文件 {fileName} 已成功從 SQL 庫與 ChromaDB 同步抹除！受影響列數: {affectedRows}");
            
            return Ok(new
            {
                message = "該文件的向量索引與資料庫紀錄已成功同步抹除！",
                fileName = fileName,
                room_id = roomId
            });
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[❌ C# RAG-DELETE 內部崩潰]: {ex.Message}");
            return StatusCode(500, $"後端刪除 RAG 知識失敗: {ex.Message}");
        }
    }



    // ===================================================================================================================================
    // 🛠️ 任務 1：【後端 API 拓荒】動態 Agent 大腦管理端點 (全面統一 EF Core 10)
    // ===================================================================================================================================

    /// <summary>
    /// 【讀取】
    /// 🌐 【對外 API】大廳拉取所有自訂 AI 專家卡片
    /// 網址：GET /api/agents
    /// </summary>
    [HttpGet("/api/agents")]
    public async Task<IActionResult> GetAgents([FromQuery] string? userId)
    {
        try
        {
            // 🌟 EF Core 寫法：極度優雅，一行 LINQ 搞定
            // 🔒 多租戶隔離：這裡原本被註解掉，導致大廳會把「所有使用者」的 Agent 全部秀出來，
            // 造成使用者 A 能看到使用者 B 的 Agent 卡片。改回依 userId 過濾，只回傳自己的。
            IQueryable<Agent> query = _context.Agents;
            if (!string.IsNullOrWhiteSpace(userId))
            {
                query = query.Where(a => a.UserId == userId);
            }
            else
            {
                return Ok(new List<object>());
            }

            var agents = await query
                .OrderByDescending(a => a.CreatedAt)
                .Select(a => new
                {
                    id = a.Id,
                    agent_id = a.AgentId,
                    name = a.Name,
                    system_prompt = a.SystemPrompt,
                    created_at = a.CreatedAt
                })
                .ToListAsync();

            return Ok(agents);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "使用 EF Core 拉取大廳 Agent 清單失敗");
            return StatusCode(500, $"大廳讀取錯誤: {ex.Message}");
        }
    }

    /// <summary>
    /// 【新增】
    /// ✨ 【對外 API】捏造全新的 AI 大腦助理 (寫入 agents 母表)
    /// 網址：POST /api/agents
    /// </summary>
    [HttpPost("/api/agents")]
    public async Task<IActionResult> CreateAgent([FromBody] CreateAgentRequestDto? request)
    {
        if (request == null || string.IsNullOrWhiteSpace(request.Name)) 
            return BadRequest("專家名稱不能為空");

        try
        {
            string generatedAgentId = $"agent_{Guid.NewGuid().ToString("n").Substring(0, 12)}";
            string finalName = request.Name.Trim();
            string finalPrompt = string.IsNullOrWhiteSpace(request.SystemPrompt)
                ? $"你是一位專業的{finalName}。請盡可能提供精準、客觀且具備深度的分析。"
                : request.SystemPrompt.Trim();

            // 🌟 EF Core 寫法：直接實體化 C# 物件
            var newAgent = new Agent
            {
                AgentId = generatedAgentId,
                Name = finalName,
                SystemPrompt = finalPrompt,
                UserId = request.UserId,
                CreatedAt = DateTime.UtcNow
            };

            // 🌟 告訴 EF 追蹤這個新物件，並實寫入庫
            _context.Agents.Add(newAgent);
            await _context.SaveChangesAsync(); // 這裡會自動生成 INSERT SQL 並安全返回自增 ID

            return Ok(new
            {
                id = newAgent.Id, // EF Core 儲存成功後，會自動把資料庫產生的 ID 填回這個欄位！
                agent_id = newAgent.AgentId,
                name = newAgent.Name,
                system_prompt = newAgent.SystemPrompt,
                created_at = newAgent.CreatedAt,
                message = "大功告成！全新的 Agent 大腦已透過 EF Core 實寫成功！"
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "使用 EF Core 捏造 Agent 大腦失敗");
            return StatusCode(500, $"大腦捏造失敗: {ex.Message}");
        }
    }

    
    // ===================================================================================================================================
    // 此區塊為 Hermas-Agent 
    // ===================================================================================================================================

    // =========================================================================
    // 串聯已經設計好的docker hermas-Agent內容
    // docker串聯地方："http://hermes-agent:8643/api/v1/chat"
    // =========================================================================
    
    /// <summary>
    /// 【對外 API】提供前端發送對話訊息給 Agent 的端點
    /// 網址：POST /api/agent/rooms
    /// 💡 升級說明：新增支援接收 agent_id，讓子房間能精準綁定特定的專家大腦，做到記憶分流！
    /// </summary>
    [HttpPost("/api/agent/rooms")] 
    public async Task<IActionResult> CreateAgentRoom([FromBody] ChatRoomCreateDto? request)
    {
        if (request == null) return BadRequest("請求不能為空");

        // 🔒 多租戶防護：不能讓房間綁定到「不屬於自己」的 Agent，否則等於能看到別人專家的
        // 名稱/系統提示詞，即使實際聊天內容因為 Runtime 隔離不會外洩，這裡還是要擋在最前面。
        if (!string.IsNullOrWhiteSpace(request.AgentId))
        {
            var boundAgent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == request.AgentId.Trim());
            if (boundAgent == null)
            {
                return NotFound(new { message = "找不到指定的 Agent" });
            }
            if (!string.IsNullOrWhiteSpace(request.UserId) && boundAgent.UserId != request.UserId)
            {
                return StatusCode(403, new { message = "無權綁定其他使用者的 Agent" });
            }
        }

        try
        {
            string finalTitle = request.Title ?? "專屬助理";
            if (request.RoomType == "Agent" && !finalTitle.Contains("[Agent]"))
            {
                finalTitle += " [Agent]"; 
            }

            string roomTypeField = "hermes_agent";

            // 🌟 EF Core 寫法：告別純手寫 SQL 參數綁定！
            var newRoom = new ChatRoom
            {
                Title = finalTitle,
                RoomType = roomTypeField,
                // 如果前端傳 null，C# 的 null 會被 EF Core 完美翻譯成 PostgreSQL 的 DB Null，天然向下相容
                AgentId = string.IsNullOrWhiteSpace(request.AgentId) ? null : request.AgentId.Trim(),
                UserId = request.UserId,
                CreatedAt = DateTime.UtcNow
            };

            // 🌟 塞入 DbContext 並存檔
            _context.ChatRooms.Add(newRoom);
            await _context.SaveChangesAsync(); // 自動返回剛產生的 Serial ID

            return Ok(new { 
                id = newRoom.Id, // EF Core 會把資料庫自增的 id 自動灌回 newRoom.Id
                title = newRoom.Title,
                room_type = newRoom.RoomType,
                agent_id = newRoom.AgentId, 
                created_at = newRoom.CreatedAt,
                message = "大功告成！Agent 房間已透過 EF Core 成功建立，外鍵完美綁定！"
            });
        }
        catch (Exception ex)
        {
            return StatusCode(500, $"後端寫入錯誤: {ex.Message}");
        }
    }

    /// <summary>
    /// 🗑️ 【全新新增】一鍵抄家：從資料庫實體抹除 Agent，並通知 Hermes 銷毀實體硬碟記憶
    /// 網址：DELETE /api/agents/{agentId}
    /// </summary>
    [HttpDelete("/api/agents/{agentId}")]
    public async Task<IActionResult> DeleteAgent(string agentId, [FromQuery] string? userId)
    {
        if (string.IsNullOrWhiteSpace(agentId)) return BadRequest("未指定有效的專家識別碼");

        try
        {
            _logger.LogWarning("[C# 交通警察] 🚨 開始執行專家 [{AgentId}] 的全系統除名與抄家作業...", agentId);

            // 1. 🌟 EF Core 寫法：撈出實體 Agent 母體
            var targetAgent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (targetAgent == null)
            {
                return NotFound("找不到指定的 AI 專家紀錄");
            }
            // 💡 多租戶防護：如果傳了 userId，確保這隻 Agent 屬於該用戶
            if (!string.IsNullOrWhiteSpace(userId) && targetAgent.UserId != userId)
            {
                return StatusCode(403, new { message = "無權刪除其他使用者的 Agent" });
            }

            // 2. 🌟 級聯刪除：利用資料庫外鍵約束，當母表 Agent 被刪除時，
            // PostgreSQL 會自動將 chat_rooms 表中所有對應的子對話房間一併連坐抹除！
            _context.Agents.Remove(targetAgent);
            await _context.SaveChangesAsync();

            _context.ChatRooms.RemoveRange(_context.ChatRooms.Where(r => r.AgentId == agentId));
            await _context.SaveChangesAsync();

            // 3. 📡 橫向聯動：通知該使用者專屬的 Hermes Runtime 容器進行實體硬碟總日記的大掃除
            var client = _httpClientFactory.CreateClient();
            client.Timeout = TimeSpan.FromSeconds(30);

            try
            {
                string hermesBaseUrl = await EnsureUserHermesRuntimeAsync(targetAgent.UserId ?? userId);
                string hermesUrl = $"{hermesBaseUrl}/api/agent/{agentId}";
                var response = await client.DeleteAsync(hermesUrl);
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError("[C# 交通警察] ❌ 資料庫已刪，但 Hermes 物理抄家失敗。狀態碼: {StatusCode}", response.StatusCode);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "[C# 交通警察] ⚠️ 無法連線至 Hermes 執行硬碟掃除，可能容器未通電，跳過物理步驟。");
            }

            return Ok(new { message = "大功告成！該專家大腦、子聊天室以及硬碟實體記憶已全數灰飛煙滅！" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "刪除 Agent 發生內部錯誤。AgentId: {AgentId}", agentId);
            return StatusCode(500, $"大腦銷毀失敗: {ex.Message}");
        }
    }
    // ===================================================================================================================================
    // DTO 定義區塊
    // ===================================================================================================================================

    public class ChatRoomCreateDto
    {
        [JsonPropertyName("title")]
        public string? Title { get; set; }

        [JsonPropertyName("room_type")]
        public string? RoomType { get; set; }

        // 💡 升級：承接前端傳過來的當前專家隔離識別碼 (若為 null 則代表是一般 RAG 舊房間)
        [JsonPropertyName("agent_id")]
        public string? AgentId { get; set; }

        // 💡 多租戶：承接前端傳過來的用戶識別碼
        [JsonPropertyName("user_id")]
        public string? UserId { get; set; }
    }

    public class CreateAgentRequestDto
    {
        [JsonPropertyName("name")]
        public string Name { get; set; } = string.Empty;

        [JsonPropertyName("system_prompt")]
        public string? SystemPrompt { get; set; }

        // 💡 多租戶：承接前端傳過來的用戶識別碼
        [JsonPropertyName("user_id")]
        public string? UserId { get; set; }
    }



        // =====================================================================
    // 🧠 底下是記憶部份
    // =====================================================================

    // =====================================================================
    // 🧠 雙軌制記憶體與用戶畫像（Memory/User）通用增刪改查網關對接
    // =====================================================================

    /// <summary>
    /// 0. 拉取全平台可用 Agent 清單 (供前端 Vue 渲染繼承下拉選單)
    /// GET: api/Chat/agent/available-list
    /// </summary>
    [HttpGet("agent/available-list")]
    public async Task<IActionResult> GetAvailableAgentsList([FromQuery] string? userId)
    {
        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");

            // 🚀 先解析出這個使用者專屬的 Hermes Runtime，可用清單只在他自己的 Runtime 內查
            string hermesBaseUrl = await EnsureUserHermesRuntimeAsync(userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agents/available-list";
            if (!string.IsNullOrWhiteSpace(userId))
            {
                pythonUrl += $"?userId={Uri.EscapeDataString(userId)}";
            }
            var response = await client.GetAsync(pythonUrl);
            
            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"無法取得可用 Agent 清單: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "拉取可用 Agent 清單時發生異常");
            return StatusCode(500, new { error = $"網關通訊失敗: {ex.Message}" });
        }
    }

    // 🐛 0716 新增：JsonElement.GetString() 只認 JSON 字串型別，room_id 這類欄位
    // 前端可能送字串也可能送數字，統一在這裡轉成字串，避免各處重複踩到同一個型別地雷。
    private static string? GetStringOrNumber(JsonElement el) => el.ValueKind switch
    {
        JsonValueKind.String => el.GetString(),
        JsonValueKind.Number => el.GetRawText(),
        _ => null
    };

    /// <summary>
    /// 1. 逆向注入解封印網關 (前端 Vue 彈窗同意/拒絕後由 chat.js 呼叫)
    /// POST: api/Chat/agent/approve-write
    /// </summary>
    [HttpPost("agent/approve-write")]
    public async Task<IActionResult> ApproveWrite([FromBody] JsonElement payload, [FromQuery] string? userId)
    {
        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");

            // 🚀 這個進行中的對話是在使用者自己的 Runtime 裡跑的，解封印訊號要送對地方
            string hermesBaseUrl = await EnsureUserHermesRuntimeAsync(userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/approve-write";

            // 🔒 根因修復：JsonElement 反序列化成 dynamic 後不支援自由屬性存取
            // （JsonElement 沒有 roomId 成員，dynamic 綁定會直接丟 RuntimeBinderException，
            // 被外層 catch 接住變成 500）。改用 TryGetProperty 明確讀值，同時相容
            // camelCase(roomId) 與前端實際送出的 snake_case(room_id)。
            // 🐛 0716 修正：room_id 前端實際送出的是 JSON 數字（不是字串），GetString()
            // 只認字串型別，碰到數字直接丟 InvalidOperationException，變成無論按哪個
            // 核准按鈕都 500——這裡改成同時支援字串與數字兩種型別。
            string? roomId = payload.TryGetProperty("room_id", out var ridProp) ? GetStringOrNumber(ridProp)
                : payload.TryGetProperty("roomId", out var ridProp2) ? GetStringOrNumber(ridProp2) : null;

            // 🆕 0716：main.py 全面改用 hermes acp 的 request_permission 之後，選項不再是
            // 單純 true/false，而是 hermes 自己提供的 option_id（實測常見值：allow_once/
            // allow_session/allow_always/reject_once/reject_always）。同時保留舊的
            // approve(bool) 相容判斷，避免還沒更新的舊前端呼叫直接壞掉。
            string? optionId = payload.TryGetProperty("option_id", out var optProp) ? optProp.GetString()
                : payload.TryGetProperty("optionId", out var optProp2) ? optProp2.GetString()
                : payload.TryGetProperty("approve", out var approveProp)
                    ? (approveProp.GetBoolean() ? "allow_once" : "reject_once")
                    : null;

            var pythonPayload = new
            {
                room_id = roomId,
                user_id = userId,
                option_id = optionId
            };
            
            var response = await client.PostAsJsonAsync(pythonUrl, pythonPayload);
            
            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"Python 審查解封印失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "轉發審查解封印請求時發生異常");
            return StatusCode(500, new { error = $"網關轉發失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 2. 雙軌讀取大禮包 (由網址決定讀 memory 還是 user)
    /// GET: api/Chat/agent/{agentId}/memories/{fileType}
    /// </summary>
    [HttpGet("agent/{agentId}/memories/{fileType}")]
    public async Task<IActionResult> GetAgentMemories([FromRoute] string agentId, [FromRoute] string fileType, [FromQuery] string? userId)
    {
        var lowerType = fileType.ToLower();
        if (lowerType != "memory" && lowerType != "user")
        {
            return BadRequest(new { error = "fileType 路由參數必須為 'memory' 或 'user'" });
        }

        // 💡 多租戶防護：確保 agent 屬於請求者
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            // ✨ 修正後的正確寫法
            if (agent.UserId != userId) 
                return StatusCode(403, new { error = "無權存取此 Agent 的記憶" });

        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            
            // 🚀 解析出此 Agent 擁有者專屬的 Hermes Runtime
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/{agentId}/memories/{lowerType}";
            // 💡 多租戶：把 userId 傳給 Python 端
            if (!string.IsNullOrWhiteSpace(userId))
            {
                pythonUrl += $"?userId={Uri.EscapeDataString(userId)}";
            }
            var response = await client.GetAsync(pythonUrl);

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogError($"無法取得 Agent {agentId} 的 {lowerType} 大禮包");
                return StatusCode((int)response.StatusCode, new { error = $"無法取得 {lowerType} 記憶大禮包" });
            }

            var memories = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(memories);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, $"讀取 Agent {agentId} 的 {lowerType} 記憶時發生異常");
            return StatusCode(500, new { error = $"網關通訊異常: {ex.Message}" });
        }
    }

    /// <summary>
    /// 3. 手動點擊刪除特定記憶卡片 (支援動態雙軌刪除 🗑️)
    /// DELETE: api/Chat/agent/{agentId}/memories/{fileType}/{factId}
    /// </summary>
    [HttpDelete("agent/{agentId}/memories/{fileType}/{factId}")]
    public async Task<IActionResult> DeleteAgentMemory([FromRoute] string agentId, [FromRoute] string fileType, [FromRoute] string factId, [FromQuery] string? userId)
    {
        var lowerType = fileType.ToLower();
        if (lowerType != "memory" && lowerType != "user")
        {
            return BadRequest(new { error = "fileType 路由參數必須為 'memory' 或 'user'" });
        }

        // 💡 多租戶防護：確保 agent 屬於請求者
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            // if (agent.UserId != userId) return Forbidden(new { error = "無權修改此 Agent 的記憶" });
            // ✨ 修正後的正確寫法
            if (agent.UserId != userId) 
                return StatusCode(403, new { error = "無權存取此 Agent 的記憶" });

        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            
            // 🚀 解析出此 Agent 擁有者專屬的 Hermes Runtime
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/{agentId}/memories/{lowerType}/{factId}";
            if (!string.IsNullOrWhiteSpace(userId))
            {
                pythonUrl += $"?userId={Uri.EscapeDataString(userId)}";
            }
            var response = await client.DeleteAsync(pythonUrl);

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogError($"刪除 Agent {agentId} 的 {lowerType} 片斷 {factId} 失敗");
                return StatusCode((int)response.StatusCode, new { error = "刪除資料失敗或該紀錄不存在" });
            }

            var updatedMemories = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(updatedMemories);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, $"刪除 Agent {agentId} 的 {lowerType} 記憶時發生異常");
            return StatusCode(500, new { error = $"網關刪除異步操作失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 4. 批次大量匯入與強制灌輸 (由前端 Payload 的 file_type 決定軌道)
    /// POST: api/Chat/agent/{agentId}/memories/import
    /// </summary>
    [HttpPost("agent/{agentId}/memories/import")]
    public async Task<IActionResult> ImportAgentMemories([FromRoute] string agentId, [FromBody] JsonElement payload, [FromQuery] string? userId)
    {
        // 💡 多租戶防護：確保 agent 屬於請求者
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            // if (agent.UserId != userId) return Forbidden(new { error = "無權修改此 Agent 的記憶" });
            // ✨ 修正後的正確寫法
            if (agent.UserId != userId) 
                return StatusCode(403, new { error = "無權存取此 Agent 的記憶" });

        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            
            // 🚀 解析出此 Agent 擁有者專屬的 Hermes Runtime
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/{agentId}/memories/import";
            var response = await client.PostAsJsonAsync(pythonUrl, new {
                file_type = payload.GetProperty("file_type").GetString(),
                texts = payload.GetProperty("texts"),
                user_id = userId
            });

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"Agent {agentId} 批次匯入失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = "批次匯入記憶失敗" });
            }

            var updatedMemories = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(updatedMemories);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, $"Agent {agentId} 匯入記憶時發生異常");
            return StatusCode(500, new { error = $"網關匯入操作失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 5. 真．細胞分裂：一鍵繼承快照、脫鉤各自發展
    /// POST: api/Chat/agent/{agentId}/inherit-fork
    /// </summary>
    [HttpPost("agent/{agentId}/inherit-fork")]
    public async Task<IActionResult> InheritForkAgent([FromRoute] string agentId, [FromBody] JsonElement payload, [FromQuery] string? userId)
    {
        // 💡 多租戶防護：確保 agent 屬於請求者
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            // if (agent.UserId != userId) return Forbidden(new { error = "無權從此 Agent 分裂" });
            // ✨ 修正後的正確寫法
            if (agent.UserId != userId) 
                return StatusCode(403, new { error = "無權從此 Agent 分裂" });

        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            
            // 🚀 解析出此 Agent 擁有者專屬的 Hermes Runtime
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/{agentId}/inherit-fork";
            var response = await client.PostAsJsonAsync(pythonUrl, new {
                user_id = userId
            });

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"Agent {agentId} 快照複製繼承失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, $"Agent {agentId} 執行細胞分裂繼承時發生異常");
            return StatusCode(500, new { error = $"網關跨體複製失敗: {ex.Message}" });
        }
    }


    // =====================================================================
    // 🧬 真．複製新 Agent／匯出匯入／安全掃描 (全部走 hermes 原生指令)
    // =====================================================================

    public class CloneAgentRequestDto
    {
        public string? Name { get; set; }
        public string? SystemPrompt { get; set; }
        public string? SourceAgentId { get; set; }
        public string? UserId { get; set; }
    }

    /// <summary>
    /// 6. 真．複製：寫入 Agent DB 記錄後呼叫 Python 端 hermes profile create --clone-from，
    /// 失敗時回滾剛寫入的 DB 記錄，絕不假裝成功。
    /// POST: api/Chat/agent/clone
    /// </summary>
    [HttpPost("agent/clone")]
    public async Task<IActionResult> CloneAgent([FromBody] CloneAgentRequestDto? request)
    {
        if (request == null || string.IsNullOrWhiteSpace(request.Name) || string.IsNullOrWhiteSpace(request.SourceAgentId))
            return BadRequest(new { error = "新 Agent 名稱與來源 Agent 不能為空" });

        // 🐛 0716：原本只有傳 userId 時才查來源 Agent，導致沒機會拿到它真正的 system_prompt。
        // 來源 Agent 沒查到一律視為不存在（不管有沒有帶 userId 都要查，多租戶檢查只是額外加碼）。
        var sourceAgent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == request.SourceAgentId);
        if (sourceAgent == null)
            return NotFound(new { error = "找不到來源 Agent" });
        if (!string.IsNullOrWhiteSpace(request.UserId) && sourceAgent.UserId != request.UserId)
            return StatusCode(403, new { error = "無權複製其他使用者的 Agent" });

        string generatedAgentId = $"agent_{Guid.NewGuid().ToString("n").Substring(0, 12)}";
        string finalName = request.Name.Trim();
        string finalPrompt = string.IsNullOrWhiteSpace(request.SystemPrompt)
            ? $"你是一位專業的{finalName}。請盡可能提供精準、客觀且具備深度的分析。"
            : request.SystemPrompt.Trim();

        var newAgent = new Agent
        {
            AgentId = generatedAgentId,
            Name = finalName,
            SystemPrompt = finalPrompt,
            UserId = request.UserId,
            CreatedAt = DateTime.UtcNow
        };
        _context.Agents.Add(newAgent);
        await _context.SaveChangesAsync();

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            // 🚀 新 Agent 的擁有者就是 request.UserId，直接用它解析出專屬 Runtime
            string hermesBaseUrl = await EnsureUserHermesRuntimeAsync(request.UserId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/{generatedAgentId}/clone-from/{request.SourceAgentId.Trim()}";
            // 🐛 0716 修正：來源 Agent 如果建立後從沒聊過天，hermes 自己的 profile 目錄根本不存在，
            // --clone-from 會直接失敗（"尚未初始化過"）。把來源 Agent 真正的 system_prompt 一併帶給
            // Python 端，讓它需要臨時補初始化來源時，用的是來源自己真正的人設，不是隨便塞預設值。
            var response = await client.PostAsJsonAsync(pythonUrl, new { system_prompt = finalPrompt, source_system_prompt = sourceAgent.SystemPrompt });

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"真複製失敗，回滾 DB 記錄 {generatedAgentId}: {errorMsg}");
                _context.Agents.Remove(newAgent);
                await _context.SaveChangesAsync();
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            return Ok(new
            {
                id = newAgent.Id,
                agent_id = newAgent.AgentId,
                name = newAgent.Name,
                system_prompt = newAgent.SystemPrompt,
                created_at = newAgent.CreatedAt,
                message = "🧬 複製成功！新的 Agent 已透過 hermes 原生指令繼承來源的記憶與技能。"
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, $"複製 Agent 時發生異常，回滾 DB 記錄 {generatedAgentId}");
            _context.Agents.Remove(newAgent);
            await _context.SaveChangesAsync();
            return StatusCode(500, new { error = $"複製失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 7. 匯出 Agent：hermes 原生 tar.gz／轉封裝 zip／Skill 標準 markdown 三選一
    /// GET: api/Chat/agent/{agentId}/export?format=hermes|zip|skill
    /// </summary>
    [HttpGet("agent/{agentId}/export")]
    public async Task<IActionResult> ExportAgent([FromRoute] string agentId, [FromQuery] string format = "hermes", [FromQuery] string? userId = null)
    {
        // 💡 多租戶防護：確保 agent 屬於請求者
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            // ✨ 修正後的正確寫法
            if (agent.UserId != userId) 
                return StatusCode(403, new { error = "無權匯出此 Agent" });

        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            client.Timeout = TimeSpan.FromMinutes(5);
            // 🚀 解析出此 Agent 擁有者專屬的 Hermes Runtime
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/{agentId}/export?format={Uri.EscapeDataString(format)}";
            if (!string.IsNullOrWhiteSpace(userId))
            {
                pythonUrl += $"&userId={Uri.EscapeDataString(userId)}";
            }
            var response = await client.GetAsync(pythonUrl);

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"Agent {agentId} 匯出失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var bytes = await response.Content.ReadAsByteArrayAsync();
            var contentType = response.Content.Headers.ContentType?.ToString() ?? "application/octet-stream";
            var fileName = (response.Content.Headers.ContentDisposition?.FileNameStar
                ?? response.Content.Headers.ContentDisposition?.FileName
                ?? $"{agentId}_export").Trim('"');
            return File(bytes, contentType, fileName);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, $"Agent {agentId} 匯出時發生異常");
            return StatusCode(500, new { error = $"網關匯出失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 8. 匯入技能：轉發上傳的 SKILL.md 給 Python，由 hermes skills install 安裝
    /// POST: api/Chat/agent/{agentId}/skills/import
    /// </summary>
    [HttpPost("agent/{agentId}/skills/import")]
    public async Task<IActionResult> ImportSkillToAgent([FromRoute] string agentId, [FromForm] string name, IFormFile file, [FromQuery] string? userId = null)
    {
        if (file == null || file.Length == 0)
            return BadRequest(new { error = "上傳的技能檔案無效或內容為空" });
        if (string.IsNullOrWhiteSpace(name))
            return BadRequest(new { error = "技能名稱不能為空" });

        // 🐛 0717：一律查一次 agent（不只在有 userId 時），才能拿到它真正的 system_prompt
        var targetAgentForImport = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
        if (targetAgentForImport == null) return NotFound(new { error = "找不到 Agent" });
        if (!string.IsNullOrWhiteSpace(userId) && targetAgentForImport.UserId != userId)
            return StatusCode(403, new { error = "無權向此 Agent 安裝技能" });

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            // 🚀 解析出此 Agent 擁有者專屬的 Hermes Runtime
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/{agentId}/skills/import";

            using var multipartContent = new MultipartFormDataContent();
            using var fileStream = file.OpenReadStream();
            using var streamContent = new StreamContent(fileStream);
            multipartContent.Add(new StringContent(name), "name");
            multipartContent.Add(streamContent, "file", file.FileName);
            multipartContent.Add(new StringContent(targetAgentForImport.SystemPrompt ?? ""), "system_prompt");
            if (!string.IsNullOrWhiteSpace(userId))
            {
                multipartContent.Add(new StringContent(userId), "user_id");
            }

            var response = await client.PostAsync(pythonUrl, multipartContent);

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"Agent {agentId} 匯入技能失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, $"Agent {agentId} 匯入技能時發生異常");
            return StatusCode(500, new { error = $"網關匯入技能失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 9. 安全掃描：hermes security audit (OSV.dev 供應鏈漏洞掃描)
    /// GET: api/Chat/agent/{agentId}/security-audit
    /// </summary>
    [HttpGet("agent/{agentId}/security-audit")]
    public async Task<IActionResult> RunSecurityAudit([FromRoute] string agentId, [FromQuery] string? userId = null)
    {
        // 💡 多租戶防護：確保 agent 屬於請求者
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            if (agent.UserId != userId) 
            {
                return StatusCode(403, new { error = "無權掃描此 Agent" });
            }
        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            client.Timeout = TimeSpan.FromSeconds(90);
            // 🚀 解析出此 Agent 擁有者專屬的 Hermes Runtime
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/{agentId}/security-audit";
            if (!string.IsNullOrWhiteSpace(userId))
            {
                pythonUrl += $"?userId={Uri.EscapeDataString(userId)}";
            }
            var response = await client.GetAsync(pythonUrl);

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"Agent {agentId} 安全掃描失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, $"Agent {agentId} 安全掃描時發生異常");
            return StatusCode(500, new { error = $"網關安全掃描失敗: {ex.Message}" });
        }
    }

    public class SkillInstallRequestDto
    {
        public string? Identifier { get; set; }
        public string? Name { get; set; }
        // 🛡️ 使用者已經看過 hermes 資安掃描的風險說明、仍然決定要裝時才會是 true
        public bool Force { get; set; } = false;
    }

    /// <summary>
    /// 10. Skill 商城搜尋：hermes skills search --json(官方 8 萬 8 千多個技能市集)
    /// GET: api/Chat/agent/{agentId}/skills/search
    /// </summary>
    [HttpGet("agent/{agentId}/skills/search")]
    public async Task<IActionResult> SearchSkillsHub([FromRoute] string agentId, [FromQuery] string query, [FromQuery] string source = "all", [FromQuery] int limit = 24, [FromQuery] string? userId = null)
    {
        // 🐛 0717：一律查一次 agent（不只在有 userId 時），才能拿到它真正的 system_prompt
        var targetAgentForSearch = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
        if (targetAgentForSearch == null) return NotFound(new { error = "找不到 Agent" });
        if (!string.IsNullOrWhiteSpace(userId) && targetAgentForSearch.UserId != userId)
            return StatusCode(403, new { error = "無權為此 Agent 搜尋技能" });

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            client.Timeout = TimeSpan.FromSeconds(30);
            // 🚀 解析出此 Agent 擁有者專屬的 Hermes Runtime
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/{agentId}/skills/search?query={Uri.EscapeDataString(query)}&source={Uri.EscapeDataString(source)}&limit={limit}&system_prompt={Uri.EscapeDataString(targetAgentForSearch.SystemPrompt ?? "")}";
            if (!string.IsNullOrWhiteSpace(userId))
            {
                pythonUrl += $"&userId={Uri.EscapeDataString(userId)}";
            }
            var response = await client.GetAsync(pythonUrl);

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"Skill 商城搜尋失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, $"Skill 商城搜尋時發生異常");
            return StatusCode(500, new { error = $"網關搜尋失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 11. Skill 商城安裝：hermes skills install <identifier>
    /// POST: api/Chat/agent/{agentId}/skills/install-from-hub
    /// </summary>
    [HttpPost("agent/{agentId}/skills/install-from-hub")]
    public async Task<IActionResult> InstallSkillFromHub([FromRoute] string agentId, [FromBody] SkillInstallRequestDto? request, [FromQuery] string? userId = null)
    {
        if (request == null || string.IsNullOrWhiteSpace(request.Identifier))
            return BadRequest(new { error = "Skill identifier 不能為空" });

        // 🐛 0717：一律查一次來源 Agent（不只在有 userId 時），才能拿到它真正的 system_prompt，
        // 剛建立、從沒聊過天的 agent 需要它來補初始化 profile 目錄（跟 clone-from 同一個修法）。
        var targetAgentForSkill = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
        if (targetAgentForSkill == null) return NotFound(new { error = "找不到 Agent" });
        if (!string.IsNullOrWhiteSpace(userId) && targetAgentForSkill.UserId != userId)
            return StatusCode(403, new { error = "無權為此 Agent 安裝技能" });

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            client.Timeout = TimeSpan.FromSeconds(60);
            // 🚀 解析出此 Agent 擁有者專屬的 Hermes Runtime
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/{agentId}/skills/install-from-hub";
            var response = await client.PostAsJsonAsync(pythonUrl, new { identifier = request.Identifier, name = request.Name, force = request.Force, user_id = userId, system_prompt = targetAgentForSkill.SystemPrompt });

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"Skill 安裝失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, $"Skill 安裝時發生異常");
            return StatusCode(500, new { error = $"網關安裝失敗: {ex.Message}" });
        }
    }

    // =====================================================================
    // 🗂️ 12. Skill 待審核清單：Agent 的 skills.write_approval 開啟後，Hermes 自己建立/修改
    // 技能檔案時會先暫存待審核，而不是直接落盤。這裡三支端點對應「查看清單／核准／拒絕」。
    // =====================================================================

    /// <summary>
    /// 12a. 查看某個 Agent 目前所有待審核的技能寫入
    /// GET: api/Chat/agent/{agentId}/skills/pending
    /// </summary>
    [HttpGet("agent/{agentId}/skills/pending")]
    public async Task<IActionResult> ListPendingSkillWrites([FromRoute] string agentId, [FromQuery] string? userId = null)
    {
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            if (agent.UserId != userId)
                return StatusCode(403, new { error = "無權查看此 Agent 的待審核清單" });
        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            client.Timeout = TimeSpan.FromSeconds(30);
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            var response = await client.GetAsync($"{hermesBaseUrl}/api/agent/{agentId}/skills/pending");

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"查詢 Skill 待審核清單失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "查詢 Skill 待審核清單時發生異常");
            return StatusCode(500, new { error = $"網關查詢失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 12b. 核准某一筆待審核的技能寫入（真的套用到硬碟上）
    /// POST: api/Chat/agent/{agentId}/skills/pending/{pendingId}/approve
    /// </summary>
    [HttpPost("agent/{agentId}/skills/pending/{pendingId}/approve")]
    public async Task<IActionResult> ApprovePendingSkillWrite([FromRoute] string agentId, [FromRoute] string pendingId, [FromQuery] string? userId = null)
    {
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            if (agent.UserId != userId)
                return StatusCode(403, new { error = "無權核准此 Agent 的待審核項目" });
        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            client.Timeout = TimeSpan.FromSeconds(30);
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            var response = await client.PostAsync($"{hermesBaseUrl}/api/agent/{agentId}/skills/pending/{pendingId}/approve", null);

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"核准 Skill 待審核項目失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "核准 Skill 待審核項目時發生異常");
            return StatusCode(500, new { error = $"網關核准失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 12c. 拒絕（丟棄）某一筆待審核的技能寫入
    /// POST: api/Chat/agent/{agentId}/skills/pending/{pendingId}/reject
    /// </summary>
    [HttpPost("agent/{agentId}/skills/pending/{pendingId}/reject")]
    public async Task<IActionResult> RejectPendingSkillWrite([FromRoute] string agentId, [FromRoute] string pendingId, [FromQuery] string? userId = null)
    {
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            if (agent.UserId != userId)
                return StatusCode(403, new { error = "無權拒絕此 Agent 的待審核項目" });
        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            client.Timeout = TimeSpan.FromSeconds(30);
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            var response = await client.PostAsync($"{hermesBaseUrl}/api/agent/{agentId}/skills/pending/{pendingId}/reject", null);

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"拒絕 Skill 待審核項目失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "拒絕 Skill 待審核項目時發生異常");
            return StatusCode(500, new { error = $"網關拒絕失敗: {ex.Message}" });
        }
    }


    // =====================================================================
    // 🔌 13. MCP 商店：母版目錄 + 每個 agent 自己的 mcp.json/config.yaml
    // 完全比照上面 Skill 商城的寫法——ResolveHermesBaseUrlForAgentAsync 會先用
    // agentId 反查 Postgres 裡真正的擁有者 UserId（不信任呼叫端傳入的 userId），
    // 再去問共用 proxy 拿到「那個使用者專屬」Runtime 容器的網址，請求才轉發過去，
    // 物理上不可能讀寫到別的使用者的 profiles 資料夾。
    // =====================================================================
    public class McpSelectionRequestDto
    {
        // null(移除) / "resident"(常駐) / "optional_installed"(選配已安裝)
        public string? Selection { get; set; }
    }

    public class McpCredentialsRequestDto
    {
        public Dictionary<string, string> Credentials { get; set; } = new();
    }

    // 🐛 0716：approve-write 那次 500 錯誤就是用 JsonElement 手動解析踩到型別地雷（room_id
    // 數字被當字串讀）。這裡改用強型別 DTO，讓 ASP.NET 自己做型別轉換，不用再手動判斷。
    public class AgentApprovalsRequestDto
    {
        public string? Mode { get; set; }
        public bool? MemoryWriteApproval { get; set; }
        public bool? SkillsWriteApproval { get; set; }
    }

    /// <summary>
    /// 母版目錄：全平台共用，不需要指定 agent，固定打共用 proxy 就好
    /// GET: api/Chat/mcp/catalog
    /// </summary>
    [HttpGet("mcp/catalog")]
    public async Task<IActionResult> GetMcpMasterCatalog()
    {
        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            var response = await client.GetAsync("http://hermes-agent-proxy:8643/api/mcp/catalog");
            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }
            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "讀取 MCP 母版目錄時發生異常");
            return StatusCode(500, new { error = $"網關通訊失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 精選技能清單：建立 agent 時可以直接勾選安裝，全平台共用
    /// GET: api/Chat/skills/catalog
    /// </summary>
    [HttpGet("skills/catalog")]
    public async Task<IActionResult> GetSkillsMasterCatalog()
    {
        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            var response = await client.GetAsync("http://hermes-agent-proxy:8643/api/skills/catalog");
            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }
            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "讀取精選技能清單時發生異常");
            return StatusCode(500, new { error = $"網關通訊失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 這個 agent 目前擁有哪些 MCP（常駐/選配/未選、憑證有沒有填）
    /// GET: api/Chat/agent/{agentId}/mcp
    /// </summary>
    [HttpGet("agent/{agentId}/mcp")]
    public async Task<IActionResult> GetAgentMcpState([FromRoute] string agentId, [FromQuery] string? userId = null)
    {
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            if (agent.UserId != userId)
                return StatusCode(403, new { error = "無權查看此 Agent 的 MCP 設定" });
        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            var response = await client.GetAsync($"{hermesBaseUrl}/api/agent/{agentId}/mcp");
            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }
            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "讀取 Agent MCP 狀態時發生異常");
            return StatusCode(500, new { error = $"網關通訊失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 設為常駐 / 選配安裝 / 移除
    /// POST: api/Chat/agent/{agentId}/mcp/{mcpName}/selection
    /// </summary>
    [HttpPost("agent/{agentId}/mcp/{mcpName}/selection")]
    public async Task<IActionResult> SetAgentMcpSelection([FromRoute] string agentId, [FromRoute] string mcpName, [FromBody] McpSelectionRequestDto request, [FromQuery] string? userId = null)
    {
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            if (agent.UserId != userId)
                return StatusCode(403, new { error = "無權修改此 Agent 的 MCP 設定" });
        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/{agentId}/mcp/{mcpName}/selection";
            var response = await client.PostAsJsonAsync(pythonUrl, new { selection = request.Selection });

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"設定 MCP selection 失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "設定 MCP selection 時發生異常");
            return StatusCode(500, new { error = $"網關通訊失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 填寫這個 MCP 的憑證欄位（API Key/帳密），實際值只會落地到該 agent 自己的 .env
    /// POST: api/Chat/agent/{agentId}/mcp/{mcpName}/credentials
    /// </summary>
    [HttpPost("agent/{agentId}/mcp/{mcpName}/credentials")]
    public async Task<IActionResult> SetAgentMcpCredentials([FromRoute] string agentId, [FromRoute] string mcpName, [FromBody] McpCredentialsRequestDto request, [FromQuery] string? userId = null)
    {
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            if (agent.UserId != userId)
                return StatusCode(403, new { error = "無權修改此 Agent 的 MCP 憑證" });
        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/{agentId}/mcp/{mcpName}/credentials";
            var response = await client.PostAsJsonAsync(pythonUrl, new { credentials = request.Credentials });

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"設定 MCP 憑證失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "設定 MCP 憑證時發生異常");
            return StatusCode(500, new { error = $"網關通訊失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 這個 agent 目前的三個 approval 開關（mode/memory/skills）
    /// GET: api/Chat/agent/{agentId}/approvals
    /// </summary>
    [HttpGet("agent/{agentId}/approvals")]
    public async Task<IActionResult> GetAgentApprovals([FromRoute] string agentId, [FromQuery] string? userId = null)
    {
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            if (agent.UserId != userId)
                return StatusCode(403, new { error = "無權查看此 Agent 的 approval 設定" });
        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            var response = await client.GetAsync($"{hermesBaseUrl}/api/agent/{agentId}/approvals");
            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }
            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "讀取 Agent approval 設定時發生異常");
            return StatusCode(500, new { error = $"網關通訊失敗: {ex.Message}" });
        }
    }

    /// <summary>
    /// 更新這個 agent 的 approval 設定
    /// POST: api/Chat/agent/{agentId}/approvals
    /// </summary>
    [HttpPost("agent/{agentId}/approvals")]
    public async Task<IActionResult> SetAgentApprovals([FromRoute] string agentId, [FromBody] AgentApprovalsRequestDto request, [FromQuery] string? userId = null)
    {
        if (!string.IsNullOrWhiteSpace(userId))
        {
            var agent = await _context.Agents.FirstOrDefaultAsync(a => a.AgentId == agentId);
            if (agent == null) return NotFound(new { error = "找不到 Agent" });
            if (agent.UserId != userId)
                return StatusCode(403, new { error = "無權修改此 Agent 的 approval 設定" });
        }

        try
        {
            var client = _httpClientFactory.CreateClient("PythonAgentService");
            string hermesBaseUrl = await ResolveHermesBaseUrlForAgentAsync(agentId, userId);
            string pythonUrl = $"{hermesBaseUrl}/api/agent/{agentId}/approvals";
            var response = await client.PostAsJsonAsync(pythonUrl, new
            {
                mode = request.Mode,
                memory_write_approval = request.MemoryWriteApproval,
                skills_write_approval = request.SkillsWriteApproval
            });

            if (!response.IsSuccessStatusCode)
            {
                var errorMsg = await response.Content.ReadAsStringAsync();
                _logger.LogError($"設定 Agent approval 失敗: {errorMsg}");
                return StatusCode((int)response.StatusCode, new { error = errorMsg });
            }

            var result = await response.Content.ReadFromJsonAsync<JsonElement>();
            return Ok(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "設定 Agent approval 時發生異常");
            return StatusCode(500, new { error = $"網關通訊失敗: {ex.Message}" });
        }
    }


    // 帳號密碼註冊
    public class AuthDto
    {
        public string Username { get; set; } = string.Empty;
        public string Password { get; set; } = string.Empty;
    }

    // 🌐 1. 正式註冊 API：會存進資料庫
    [HttpPost("/api/auth/register")]
    public async Task<IActionResult> Register([FromBody] AuthDto dto)
    {
        if (string.IsNullOrWhiteSpace(dto.Username) || string.IsNullOrWhiteSpace(dto.Password))
        {
            return BadRequest(new { message = "帳號與密碼不能為空" });
        }

        try
        {
            var userExists = await _context.Users.AnyAsync(u => u.UserId == dto.Username.Trim());
            if (userExists)
            {
                return BadRequest(new { message = "此帳號已被註冊" });
            }

            var newUser = new User
            {
                UserId = dto.Username.Trim(),
                PasswordText = dto.Password, // 開發階段先存純文字
                CreatedAt = DateTime.UtcNow
            };

            _context.Users.Add(newUser);
            await _context.SaveChangesAsync();

            return Ok(new { message = "註冊成功" });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { message = $"註冊失敗: {ex.Message}" });
        }
    }

    // 🌐 2. 正式登入驗證 API：去資料庫比對帳密
    [HttpPost("/api/auth/login")]
    public async Task<IActionResult> LoginVerify([FromBody] AuthDto dto)
    {
        try
        {
            var user = await _context.Users
                .FirstOrDefaultAsync(u => u.UserId == dto.Username.Trim() && u.PasswordText == dto.Password);

            if (user == null)
            {
                return BadRequest(new { message = "帳號或密碼錯誤！" });
            }

            return Ok(new { userId = user.UserId, message = "驗證成功" });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { message = $"登入驗證崩潰: {ex.Message}" });
        }
    }



}




