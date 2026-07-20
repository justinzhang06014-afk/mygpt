//新增為母聊天室 為了多種聊天室設計
//母表
using System;
using System.Collections.Generic;
using System.Text.Json.Serialization; // 💡 確保有引入這個命名空間
namespace LMBackend.Models
{
    public class ChatRoom
    {
        public int Id { get; set; }
        public string Title { get; set; } = "新增聊天室";
        public string RoomType { get; set; } = "default";
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

        // 🎯 核心新增：這個聊天室是隸屬於哪一個 Agent 大腦的？
        // 如果是 NULL，代表這是一般 RAG 聊天室，天然維持向下相容！
        public string? AgentId { get; set; }
         // 💡 關鍵新增：對應你剛剛 ALTER 加上去的 user_id
        public string? UserId { get; set; }
        // 導覽屬性：建立一對多的父子關係
        public ICollection<Message> Messages { get; set; } = new List<Message>();

        public ICollection<DocumentFile> DocumentFiles { get; set; } = new List<DocumentFile>();

         // 導覽屬性：指向所屬的 Agent
        public Agent? Agent { get; set; }
    }
}
