using System;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace LMBackend.Models
{
    [Table("users", Schema = "public")]
    public class User
    {
        [Key]
        [Column("id")]
        public int Id { get; set; }

        [Required]
        [Column("user_id")]
        [StringLength(100)]
        public string UserId { get; set; } = string.Empty;

        [Required]
        [Column("password_text")]
        public string PasswordText { get; set; } = string.Empty;

        [Required]
        [Column("created_at")]
        public DateTime CreatedAt { get; set; }
    }
}
