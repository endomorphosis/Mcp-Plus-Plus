//! MCP++ Protocol Validators (Rust)
//!
//! Provides strongly-typed validators for all MCP and MCP++ protocol profiles.
//! Uses Rust's type system and serde for compile-time and runtime validation.
//!
//! ## Features
//!
//! - **Strong Static Typing**: Rust's type system catches errors at compile time
//! - **Runtime Validation**: serde_valid provides declarative validation rules
//! - **Zero-Cost Abstractions**: No runtime overhead for type safety
//! - **Comprehensive Coverage**: All 7 MCP++ profiles supported
//!
//! ## Example
//!
//! ```rust
//! use mcp_validators::validators::MCPValidator;
//! use serde_json::json;
//!
//! let validator = MCPValidator::new();
//! let payload = json!({
//!     "jsonrpc": "2.0",
//!     "method": "tools/list",
//!     "id": 1
//! });
//!
//! match validator.validate_request(&payload) {
//!     Ok(result) => {
//!         if result.is_valid {
//!             println!("Valid MCP request!");
//!         } else {
//!             println!("Errors: {:?}", result.errors);
//!         }
//!     }
//!     Err(e) => eprintln!("Validation error: {}", e),
//! }
//! ```

pub mod models;
pub mod validators;

// Re-export commonly used types
pub use models::*;
pub use validators::*;
