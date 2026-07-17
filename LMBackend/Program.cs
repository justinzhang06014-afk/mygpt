using System.Reflection;
using Microsoft.EntityFrameworkCore;
using LMBackend.Models;

var builder = WebApplication.CreateBuilder(args);

// 1. 設定資料庫連接字串並註冊 DbContext
var connectionString = builder.Configuration.GetConnectionString("PostgreSQLConnection");
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connectionString) .UseSnakeCaseNamingConvention());

// 2. 註冊 Controller 與 HttpClient
// 💡 請找到 builder.Services.AddControllers(); 改成下面這樣：
builder.Services.AddControllers()
    .AddJsonOptions(options =>
    {
        // 🌟 核心防禦：強迫 C# 忽略大小寫敏感，且完全支援小寫屬性映射
        options.JsonSerializerOptions.PropertyNamingPolicy = System.Text.Json.JsonNamingPolicy.CamelCase;
    });

builder.Services.AddHttpClient();

// 3. 註冊 Swagger 文件產生器
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(options =>
{
    var xmlFilename = $"{Assembly.GetExecutingAssembly().GetName().Name}.xml";
    var xmlPath = Path.Combine(AppContext.BaseDirectory, xmlFilename);
    if (File.Exists(xmlPath))
    {
        options.IncludeXmlComments(xmlPath);
    }
});

// 💡 修正 1：註冊一個徹底全開放、相容 Docker 內外網所有環境的 "AllowAll" 政策
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy =>
    {
        policy.AllowAnyOrigin()   // 允許任何來源（包含 Docker 與本機 Chrome）
              .AllowAnyHeader()   // 允許任何 HTTP 標頭
              .AllowAnyMethod()   // 允許 GET, POST, PUT, DELETE
              // 🔒 修正匯出下載 bug：瀏覽器預設會擋掉跨來源回應裡的 Content-Disposition，
              // 前端 chat.js 讀不到檔名，才會退回沒有副檔名的 "{agentId}_export"，
              // 看起來就像匯出失敗。這裡明確允許前端讀取這個標頭。
              .WithExposedHeaders("Content-Disposition");
    });
});

var app = builder.Build();

// 4. 啟用 Swagger 與配置符合您目標的 UI
app.UseSwagger();
app.UseSwaggerUI(c =>
{
    c.SwaggerEndpoint("/swagger/v1/swagger.json", "LM API V1");
    c.RoutePrefix = "swagger"; 
});

// 精準移到這裡：先允許跨域，再做權限驗證，最後才是 Map 路由
app.UseCors("AllowAll"); 

app.UseAuthorization();

// 5. 將網址路由對應到你的 Controllers 資料夾內
app.MapControllers();

// =========================================================================
// 💡 核心修正：改用 Migrate() 確保新表 ChatRooms 與新欄位能百分之百被自動補入
// =========================================================================
// =========================================================================
// 💡 自動同步資料表（必須寫在 app.Run() 之前）
// =========================================================================
using (var scope = app.Services.CreateScope())
{
    var services = scope.ServiceProvider;
    try
    {
        var context = services.GetRequiredService<AppDbContext>();
        Console.WriteLine("[🛠️ ULTRA-DB-CHECK] 正在進行強制建表與結構遷移...");
        
        // 🌟 自動讀取剛才建立的 CleanStart 檔案，在 PostgreSQL 中完美砸出小寫表！
        context.Database.Migrate(); 
        
        Console.WriteLine("[🛠️ ULTRA-DB-CHECK] ✅ 自動遷移檢查完畢！");
    }
    catch (Exception ex)
    {
        Console.WriteLine($"[🛠️ ULTRA-DB-CHECK] ❌ 開機同步失敗: {ex.Message}");
    }
}

// 🚀 啟動網頁伺服器監聽請求
app.Run();

// =========================================================================

app.Run();