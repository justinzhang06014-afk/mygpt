using System;

namespace LMBackend.Models
{
    public class Message
    {
        public int Id { get; set; }
        
        // 💡 核心新增：這條訊息是屬於哪一個聊天室的
        public int ChatRoomId { get; set; } 
        
        public string UserInput { get; set; } = string.Empty;
        public string Response { get; set; } = string.Empty;
        public string? SearchSources { get; set; }
        public DateTime Timestamp { get; set; } = DateTime.UtcNow;
        // 💡 關鍵新增：對應你剛剛 ALTER 加上去的 request_uuid
        public string? RequestUuid { get; set; }
        // 導覽屬性
        public ChatRoom? ChatRoom { get; set; }
    }
}
