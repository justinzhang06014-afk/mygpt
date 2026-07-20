using System;
using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

namespace LMBackend.Migrations
{
    /// <inheritdoc />
    public partial class CleanStart : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.EnsureSchema(
                name: "public");

            migrationBuilder.CreateTable(
                name: "chat_rooms",
                schema: "public",
                columns: table => new
                {
                    id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    title = table.Column<string>(type: "text", nullable: false),
                    room_type = table.Column<string>(type: "text", nullable: false),
                    created_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_chat_rooms", x => x.id);
                });

            migrationBuilder.CreateTable(
                name: "document_files",
                schema: "public",
                columns: table => new
                {
                    id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    room_id = table.Column<int>(type: "integer", nullable: false),
                    file_name = table.Column<string>(type: "text", nullable: false),
                    file_path = table.Column<string>(type: "text", nullable: false),
                    file_size = table.Column<long>(type: "bigint", nullable: false),
                    uploaded_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_document_files", x => x.id);
                    table.ForeignKey(
                        name: "fk_document_files_chat_rooms_chat_room_id",
                        column: x => x.room_id,
                        principalSchema: "public",
                        principalTable: "chat_rooms",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "messages",
                schema: "public",
                columns: table => new
                {
                    id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    room_id = table.Column<int>(type: "integer", nullable: false),
                    user_input = table.Column<string>(type: "text", nullable: false),
                    response = table.Column<string>(type: "text", nullable: false),
                    search_sources = table.Column<string>(type: "text", nullable: true),
                    timestamp = table.Column<DateTime>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_messages", x => x.id);
                    table.ForeignKey(
                        name: "fk_messages_chat_rooms_chat_room_id",
                        column: x => x.room_id,
                        principalSchema: "public",
                        principalTable: "chat_rooms",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "ix_document_files_chat_room_id",
                schema: "public",
                table: "document_files",
                column: "room_id");

            migrationBuilder.CreateIndex(
                name: "ix_messages_chat_room_id",
                schema: "public",
                table: "messages",
                column: "room_id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "document_files",
                schema: "public");

            migrationBuilder.DropTable(
                name: "messages",
                schema: "public");

            migrationBuilder.DropTable(
                name: "chat_rooms",
                schema: "public");
        }
    }
}
