using System;
using System.Collections.Generic;

namespace LMBackend.Models
{
    /// <summary>
    /// 🤖 核心新增：AI 專家大腦本體（如：寵物助理、植物助理）
    /// </summary>
    public class Agent
    {
        public int Id { get; set; }
        
        // 🎯 英文唯一識別碼，用來當作 Docker 內部的長期記憶資料夾名稱 (如: pet_doctor)
        public string AgentId { get; set; } = string.Empty;
        
        // 顯示在前端大廳卡片上的中文專家名稱 (如: 寵物溝通專家)
        public string Name { get; set; } = string.Empty;
        
        // 該 Agent 的核心大腦人設提示詞 (System Prompt)
        public string? SystemPrompt { get; set; }
        
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        
        // 💡 多租戶隔離：這個 Agent 屬於哪個帳號？
        // 💡 多租戶隔離：這個 Agent 屬於哪個帳號？
        public string? UserId { get; set; }

        public int? Port { get; set; } // 🎯 記錄這隻動態 Agent 在背景被分配到哪一個 Port

        // 導覽屬性：一個大腦專家，可以擁有多個聊天對話房間
        public ICollection<ChatRoom> ChatRooms { get; set; } = new List<ChatRoom>();

    }
}
