namespace LMBackend.Models;

using System.Text.Json.Serialization; // 💡 1. 必須引入這個命名空間

/// <summary>
/// 前端發送聊天請求的資料格式
/// </summary>
public class ChatRequest
{
    /// <summary>
    /// 使用者輸入的文字訊息 (對齊前端 chat.js 的 content)
    /// </summary>
    [JsonPropertyName("content")] // 💡 新增：強制將前端傳來的 content 映射到 Message
    public string Message { get; set; } = string.Empty;

    /// <summary>
    /// 網路搜尋功能 允許前端傳入是否開啟 Web 搜尋
    /// </summary>
    [JsonPropertyName("isWebSearch")] 
    public bool IsWebSearch { get; set; } = false; 

    /// <summary>
    /// 原有的聊天室主鍵 ID
    /// </summary>
    public int ChatRoomId { get; set; } 

    /// <summary>
    /// 新增：對齊前端 chat.js 的 roomId 屬性
    /// </summary>
    [JsonPropertyName("roomId")] // 💡 新增：強制將前端傳來的 roomId 映射到這裡
    public int RoomId { get; set; }

    [JsonPropertyName("room_type")] // 🎯 強制指定接收前端的小寫底線格式
    public string RoomType { get; set; } = string.Empty;
}

/// <summary>
/// 後端回傳聊天紀錄的單條訊息格式
/// </summary>
public class ChatMessageDto
{
    /// <summary>
    /// 發言角色 (user 或 assistant)
    /// </summary>
    public string Role { get; set; } = string.Empty;

    /// <summary>
    /// 訊息內容
    /// </summary>
    public string Content { get; set; } = string.Empty;
}
