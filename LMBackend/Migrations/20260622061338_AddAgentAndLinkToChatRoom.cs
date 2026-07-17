using System;
using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

namespace LMBackend.Migrations
{
    /// <inheritdoc />
    public partial class AddAgentAndLinkToChatRoom : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "agent_id",
                schema: "public",
                table: "chat_rooms",
                type: "text",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "agents",
                schema: "public",
                columns: table => new
                {
                    id = table.Column<int>(type: "integer", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    agent_id = table.Column<string>(type: "text", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    system_prompt = table.Column<string>(type: "text", nullable: true),
                    created_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_agents", x => x.id);
                    table.UniqueConstraint("ak_agents_agent_id", x => x.agent_id);
                });

            migrationBuilder.CreateIndex(
                name: "ix_chat_rooms_agent_id",
                schema: "public",
                table: "chat_rooms",
                column: "agent_id");

            migrationBuilder.CreateIndex(
                name: "ix_agents_agent_id",
                schema: "public",
                table: "agents",
                column: "agent_id",
                unique: true);

            migrationBuilder.AddForeignKey(
                name: "fk_chat_rooms_agents_agent_id",
                schema: "public",
                table: "chat_rooms",
                column: "agent_id",
                principalSchema: "public",
                principalTable: "agents",
                principalColumn: "agent_id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "fk_chat_rooms_agents_agent_id",
                schema: "public",
                table: "chat_rooms");

            migrationBuilder.DropTable(
                name: "agents",
                schema: "public");

            migrationBuilder.DropIndex(
                name: "ix_chat_rooms_agent_id",
                schema: "public",
                table: "chat_rooms");

            migrationBuilder.DropColumn(
                name: "agent_id",
                schema: "public",
                table: "chat_rooms");
        }
    }
}
