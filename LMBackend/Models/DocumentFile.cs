using System;
using System.ComponentModel.DataAnnotations.Schema;
namespace LMBackend.Models
{
    /// <summary>
    /// 💡 新增：使用者上傳的 RAG 參考知識庫文件紀錄
    /// </summary>
    [Table("document_files")] 
    public class DocumentFile
    {
        public int Id { get; set; }
        
        // 核心外鍵：這份文件是上傳給哪一個聊天室當小抄的
        public int ChatRoomId { get; set; }
        
        public string FileName { get; set; } = string.Empty;
        public string FilePath { get; set; } = string.Empty; // 存在硬碟的物理路徑
        public long FileSize { get; set; }
        public DateTime UploadedAt { get; set; } = DateTime.UtcNow;

        // 導覽屬性
        public ChatRoom? ChatRoom { get; set; }
    }
}
