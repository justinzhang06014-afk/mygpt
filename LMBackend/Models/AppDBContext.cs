// using Microsoft.EntityFrameworkCore;

// namespace LMBackend.Models;

// public class AppDbContext : DbContext
// {
//     public AppDbContext(DbContextOptions<AppDbContext> options) : base(options)
//     {
//     }

//     //告訴 EF Core 在資料庫中要有一張對應 Message 模型（Model）的資料表，通常對應的資料表名稱會叫做 Messages
//     public DbSet<ChatRoom> ChatRooms { get; set; }
//     public DbSet<Message> Messages { get; set; }

//     public DbSet<DocumentFile> DocumentFiles { get; set; }

//     // 💡 補上下方這段程式碼：強制指定 Migration 的歷史紀錄表行為
//     protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
//     {
        
//         if (!optionsBuilder.IsConfigured)
//         {
//             // 保持原本設定即可
//         }
//     }

//     protected override void OnModelCreating(ModelBuilder modelBuilder)
//     {
//         base.OnModelCreating(modelBuilder);
//         // 💡 告訴 EF Core 歷史紀錄表直接建立在公用架構下
//         modelBuilder.HasDefaultSchema("public");
//     }
// }
using Microsoft.EntityFrameworkCore;

namespace LMBackend.Models;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options)
    {
    }

    public DbSet<Agent> Agents { get; set; }

    public DbSet<ChatRoom> ChatRooms { get; set; }
    public DbSet<Message> Messages { get; set; }
    public DbSet<DocumentFile> DocumentFiles { get; set; }
    public DbSet<User> Users { get; set; }

    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
    {
        if (!optionsBuilder.IsConfigured)
        {
             optionsBuilder.UseNpgsql("你的連線字串");
        }
        // 確保無論如何都會套用小寫底線命名規則
        optionsBuilder.UseSnakeCaseNamingConvention();
    }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);
        modelBuilder.HasDefaultSchema("public");

        // 🌟 強制指定所有資料表名稱為全小寫蛇形
        modelBuilder.Entity<ChatRoom>().ToTable("chat_rooms");
        modelBuilder.Entity<Message>().ToTable("messages");
        modelBuilder.Entity<DocumentFile>().ToTable("document_files");
        // 🌟 1. 強制指定全新 agents 資料表名稱
        modelBuilder.Entity<Agent>().ToTable("agents");

            // 🎯 1. 連結線路一：強迫 ChatRoom 的 UserId 聽 User 的話
            modelBuilder.Entity<ChatRoom>()
                .HasOne<User>()                        // 每個房間都屬於一個 User
                .WithMany()                            // 一個 User 可以有多個房間
                .HasForeignKey(r => r.UserId)         // 透過小寫的 user_id 欄位（對應資料庫）
                .HasPrincipalKey(u => u.UserId)       // 對應到 users 資料表的 user_id
                .OnDelete(DeleteBehavior.Cascade);    // 防呆：使用者刪除時，他的房間自動連帶清空

            // 🎯 2. 連結線路二：強迫 Agent 的 UserId 聽 User 的話
            modelBuilder.Entity<Agent>()
                .HasOne<User>()                        // 每個私人 Agent 都屬於一個 User
                .WithMany()                            // 一個 User 可以捏造多個 Agent
                .HasForeignKey(a => a.UserId)         // 透過小寫的 user_id 欄位
                .HasPrincipalKey(u => u.UserId)       // 對應到 users 資料表的 user_id
                .OnDelete(DeleteBehavior.Cascade);    // 防呆：使用者刪除時，他的私人 Agent 自動全刪

        // 🌟 2. 強制指定 agents 的全小寫底線欄位
        modelBuilder.Entity<Agent>(entity =>
        {
            entity.Property(e => e.Id).HasColumnName("id");
            entity.Property(e => e.AgentId).HasColumnName("agent_id");
            entity.Property(e => e.Name).HasColumnName("name");
            entity.Property(e => e.SystemPrompt).HasColumnName("system_prompt");
            entity.Property(e => e.CreatedAt).HasColumnName("created_at");
            entity.Property(e => e.UserId).HasColumnName("user_id");

            // 建立索引，確保未來幾萬條對話依據 agent_id 查詢時快如閃電
            entity.HasIndex(e => e.AgentId).IsUnique();
        });
        // 🌟 強制指定所有欄位名稱對應為全小寫底線 (欄位對不上的地雷直接在這邊解掉)
        modelBuilder.Entity<ChatRoom>(entity =>
        {
            entity.Property(e => e.Id).HasColumnName("id");
            entity.Property(e => e.Title).HasColumnName("title");
            entity.Property(e => e.RoomType).HasColumnName("room_type");
            entity.Property(e => e.CreatedAt).HasColumnName("created_at");
            entity.Property(e => e.AgentId).HasColumnName("agent_id"); 
            entity.Property(e => e.UserId).HasColumnName("user_id");
        });

        modelBuilder.Entity<Message>(entity =>
        {
            entity.Property(e => e.Id).HasColumnName("id");
            entity.Property(e => e.ChatRoomId).HasColumnName("room_id"); // ⚠️ 對應您資料庫的 room_id
            entity.Property(e => e.UserInput).HasColumnName("user_input");
            entity.Property(e => e.Response).HasColumnName("response");
            entity.Property(e => e.SearchSources).HasColumnName("search_sources");
            entity.Property(e => e.Timestamp).HasColumnName("timestamp");
            entity.Property(e => e.RequestUuid).HasColumnName("request_uuid");
        });

        modelBuilder.Entity<DocumentFile>(entity =>
        {
            entity.Property(e => e.Id).HasColumnName("id");
            entity.Property(e => e.ChatRoomId).HasColumnName("room_id"); // ⚠️ 對應您資料庫的 room_id
            entity.Property(e => e.FileName).HasColumnName("file_name");
            entity.Property(e => e.FilePath).HasColumnName("file_path");
            entity.Property(e => e.FileSize).HasColumnName("file_size");
            entity.Property(e => e.UploadedAt).HasColumnName("uploaded_at");
        });
        // ==================== 🎯 就是這段！請補在方法結束的最後面 ====================
        
        // 🌟 核心修正：明確告訴 EF Core，這兩張表是用字串型的 AgentId 建立對等的一對多關係
        // 這行一下，剛才那個討人厭的 'AgentId1' 陰影狀態警告就會 100% 徹底消失！
        modelBuilder.Entity<ChatRoom>()
            .HasOne(c => c.Agent)
            .WithMany(a => a.ChatRooms)
            .HasForeignKey(c => c.AgentId)
            .HasPrincipalKey(a => a.AgentId);
            
        // =========================================================================
    }
}
