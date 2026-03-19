//! Minimal `.env` file loader/saver for `~/.openfang/.env`.
//!
//! No external crate needed — hand-rolled for simplicity.
//! Format: `KEY=VALUE` lines, `#` comments, optional quotes.

use std::collections::BTreeMap;
use std::path::PathBuf;

/// Get the OpenFang home directory, respecting OPENFANG_HOME env var.
fn dotenv_openfang_home() -> Option<PathBuf> {
    if let Ok(home) = std::env::var("OPENFANG_HOME") {
        return Some(PathBuf::from(home));
    }
    dirs::home_dir().map(|h| h.join(".openfang"))
}

/// Return the path to `~/.openfang/.env`.
pub fn env_file_path() -> Option<PathBuf> {
    dotenv_openfang_home().map(|h| h.join(".env"))
}

/// Load `~/.openfang/.env` and `~/.openfang/secrets.env` into `std::env`.
///
/// System env vars take priority — existing vars are NOT overridden.
/// `secrets.env` is loaded second so `.env` values take priority over secrets
/// (but both yield to system env vars).
/// Silently does nothing if the files don't exist.
pub fn load_dotenv() {
    load_env_file(env_file_path());
    // Also load secrets.env (written by dashboard "Set API Key" button)
    load_env_file(secrets_env_path());
}

/// Return the path to `~/.openfang/secrets.env`.
pub fn secrets_env_path() -> Option<PathBuf> {
    dotenv_openfang_home().map(|h| h.join("secrets.env"))
}

fn load_env_file(path: Option<PathBuf>) {
    let path = match path {
        Some(p) => p,
        None => return,
    };

    let content = match std::fs::read_to_string(&path) {
        Ok(c) => c,
        Err(_) => return,
    };

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }

        if let Some((key, value)) = parse_env_line(trimmed) {
            if std::env::var(&key).is_err() {
                std::env::set_var(&key, &value);
            }
        }
    }
}

/// Upsert a key in `~/.openfang/.env`.
///
/// Creates the file if missing. Sets 0600 permissions on Unix.
/// Also sets the key in the current process environment.
pub fn save_env_key(key: &str, value: &str) -> Result<(), String> {
    let path = env_file_path().ok_or("Could not determine home directory")?;

    // Ensure parent directory exists
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("Failed to create directory: {e}"))?;
    }

    let mut entries = read_env_file(&path);
    entries.insert(key.to_string(), value.to_string());
    write_env_file(&path, &entries)?;

    // Also set in current process
    std::env::set_var(key, value);

    Ok(())
}

/// Remove a key from `~/.openfang/.env`.
///
/// Also removes it from the current process environment.
pub fn remove_env_key(key: &str) -> Result<(), String> {
    let path = env_file_path().ok_or("Could not determine home directory")?;

    let mut entries = read_env_file(&path);
    entries.remove(key);
    write_env_file(&path, &entries)?;

    std::env::remove_var(key);

    Ok(())
}

/// List key names (without values) from `~/.openfang/.env`.
#[allow(dead_code)]
pub fn list_env_keys() -> Vec<String> {
    let path = match env_file_path() {
        Some(p) => p,
        None => return Vec::new(),
    };

    read_env_file(&path).into_keys().collect()
}

/// Check if the `.env` file exists.
#[allow(dead_code)]
pub fn env_file_exists() -> bool {
    env_file_path().map(|p| p.exists()).unwrap_or(false)
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/// Parse a single `KEY=VALUE` line. Handles optional quotes.
fn parse_env_line(line: &str) -> Option<(String, String)> {
    let eq_pos = line.find('=')?;
    let key = line[..eq_pos].trim().to_string();
    let mut value = line[eq_pos + 1..].trim().to_string();

    if key.is_empty() {
        return None;
    }

    // Strip matching quotes
    let quote_char = if value.starts_with('"') && value.ends_with('"') && value.len() >= 2 {
        Some('"')
    } else if value.starts_with('\'') && value.ends_with('\'') && value.len() >= 2 {
        Some('\'')
    } else {
        None
    };

    if let Some(quote_char) = quote_char {
        value = value[1..value.len() - 1].to_string();
        value = unescape_quoted_value(&value, quote_char);
    }

    Some((key, value))
}

fn unescape_quoted_value(value: &str, quote_char: char) -> String {
    let mut result = String::with_capacity(value.len());
    let mut chars = value.chars().peekable();

    while let Some(ch) = chars.next() {
        if ch == '\\' {
            match chars.peek().copied() {
                Some(next) if next == quote_char || next == '\\' => {
                    result.push(next);
                    chars.next();
                }
                _ => result.push(ch),
            }
        } else {
            result.push(ch);
        }
    }

    result
}

fn escape_quoted_value_for_write(value: &str) -> String {
    let mut escaped = String::with_capacity(value.len());

    for ch in value.chars() {
        match ch {
            '\\' => escaped.push_str("\\\\"),
            '"' => escaped.push_str("\\\""),
            _ => escaped.push(ch),
        }
    }

    escaped
}

/// Read all key-value pairs from the .env file.
fn read_env_file(path: &PathBuf) -> BTreeMap<String, String> {
    let mut map = BTreeMap::new();

    let content = match std::fs::read_to_string(path) {
        Ok(c) => c,
        Err(_) => return map,
    };

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        if let Some((key, value)) = parse_env_line(trimmed) {
            map.insert(key, value);
        }
    }

    map
}

/// Write key-value pairs back to the .env file with a header comment.
fn write_env_file(path: &PathBuf, entries: &BTreeMap<String, String>) -> Result<(), String> {
    let mut content =
        String::from("# OpenFang environment — managed by `openfang config set-key`\n");
    content.push_str("# Do not edit while the daemon is running.\n\n");

    for (key, value) in entries {
        // Quote values that contain spaces or special characters
        if value.contains(' ') || value.contains('#') || value.contains('"') {
            content.push_str(&format!(
                "{key}=\"{}\"\n",
                escape_quoted_value_for_write(value)
            ));
        } else {
            content.push_str(&format!("{key}={value}\n"));
        }
    }

    std::fs::write(path, &content).map_err(|e| format!("Failed to write .env file: {e}"))?;

    // Set 0600 permissions on Unix
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600));
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_env_line_simple() {
        let (k, v) = parse_env_line("FOO=bar").unwrap();
        assert_eq!(k, "FOO");
        assert_eq!(v, "bar");
    }

    #[test]
    fn test_parse_env_line_quoted() {
        let (k, v) = parse_env_line("KEY=\"hello world\"").unwrap();
        assert_eq!(k, "KEY");
        assert_eq!(v, "hello world");
    }

    #[test]
    fn test_parse_env_line_single_quoted() {
        let (k, v) = parse_env_line("KEY='value'").unwrap();
        assert_eq!(k, "KEY");
        assert_eq!(v, "value");
    }

    #[test]
    fn test_parse_env_line_unescapes_double_quotes() {
        let (k, v) = parse_env_line(r#"KEY="say \"hello\"""#).unwrap();
        assert_eq!(k, "KEY");
        assert_eq!(v, "say \"hello\"");
    }

    #[test]
    fn test_parse_env_line_unescapes_single_quotes() {
        let (k, v) = parse_env_line("KEY='it\\'s fine'").unwrap();
        assert_eq!(k, "KEY");
        assert_eq!(v, "it's fine");
    }

    #[test]
    fn test_parse_env_line_preserves_unrelated_backslashes() {
        let (k, v) = parse_env_line(r#"KEY="C:\\temp\\file.txt""#).unwrap();
        assert_eq!(k, "KEY");
        assert_eq!(v, r#"C:\temp\file.txt"#);
    }

    #[test]
    fn test_parse_env_line_spaces() {
        let (k, v) = parse_env_line("  KEY  =  value  ").unwrap();
        assert_eq!(k, "KEY");
        assert_eq!(v, "value");
    }

    #[test]
    fn test_parse_env_line_no_value() {
        let (k, v) = parse_env_line("KEY=").unwrap();
        assert_eq!(k, "KEY");
        assert_eq!(v, "");
    }

    #[test]
    fn test_parse_env_line_comment() {
        assert!(
            parse_env_line("# comment").is_none()
                || parse_env_line("# comment").unwrap().0.starts_with('#')
        );
        // Comments are filtered before reaching parse_env_line in production code
    }

    #[test]
    fn test_parse_env_line_no_equals() {
        assert!(parse_env_line("NOEQUALS").is_none());
    }

    #[test]
    fn test_parse_env_line_empty_key() {
        assert!(parse_env_line("=value").is_none());
    }

    #[test]
    fn test_write_env_file_round_trips_backslashes_and_quotes() {
        let dir = std::env::temp_dir().join(format!(
            "openfang-dotenv-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join(".env");
        let mut entries = BTreeMap::new();
        entries.insert(
            "WINDOWS_PATH".to_string(),
            "C:\\temp\\\"quoted\"\\file.txt".to_string(),
        );

        write_env_file(&path, &entries).unwrap();
        let parsed = read_env_file(&path);

        assert_eq!(
            parsed.get("WINDOWS_PATH").unwrap(),
            "C:\\temp\\\"quoted\"\\file.txt"
        );

        let _ = std::fs::remove_file(&path);
        let _ = std::fs::remove_dir(&dir);
    }
}
