//! Workspace context auto-detection.
//!
//! Scans the workspace root for project type indicators (Cargo.toml, package.json, etc.),
//! context files (AGENTS.md, SOUL.md, TOOLS.md, IDENTITY.md, HEARTBEAT.md), and OpenFang
//! state files. Provides mtime-cached file reads to avoid redundant I/O.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::time::SystemTime;
use tracing::{debug, warn};
use uuid::Uuid;

/// Maximum file size to read for context files (32KB).
const MAX_FILE_SIZE: u64 = 32_768;

/// Known context file names scanned in the workspace root.
const CONTEXT_FILES: &[&str] = &[
    "AGENTS.md",
    "SOUL.md",
    "TOOLS.md",
    "IDENTITY.md",
    "HEARTBEAT.md",
];

/// Detected project type based on marker files.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ProjectType {
    Rust,
    Node,
    Python,
    Go,
    Java,
    DotNet,
    Unknown,
}

impl ProjectType {
    /// Human-readable label.
    pub fn label(&self) -> &'static str {
        match self {
            Self::Rust => "Rust",
            Self::Node => "Node.js",
            Self::Python => "Python",
            Self::Go => "Go",
            Self::Java => "Java",
            Self::DotNet => ".NET",
            Self::Unknown => "Unknown",
        }
    }
}

/// Cached file content with modification time.
#[derive(Debug, Clone)]
struct CachedFile {
    content: String,
    mtime: SystemTime,
}

/// Workspace context information gathered from the project root.
#[derive(Debug)]
pub struct WorkspaceContext {
    /// The workspace root path.
    pub workspace_root: PathBuf,
    /// Detected project type.
    pub project_type: ProjectType,
    /// Whether this is a git repository.
    pub is_git_repo: bool,
    /// Whether .openfang/ directory exists.
    pub has_openfang_dir: bool,
    /// Cached context files.
    cache: HashMap<String, CachedFile>,
}

impl WorkspaceContext {
    /// Detect workspace context from the given root directory.
    pub fn detect(root: &Path) -> Self {
        let project_type = detect_project_type(root);
        let is_git_repo = root.join(".git").exists();
        let has_openfang_dir = root.join(".openfang").exists();

        let mut cache = HashMap::new();
        for &name in CONTEXT_FILES {
            let file_path = root.join(name);
            if let CachedFileRead::Loaded(cached) = read_cached_file(&file_path) {
                debug!(file = name, "Loaded workspace context file");
                cache.insert(name.to_string(), cached);
            }
        }

        Self {
            workspace_root: root.to_path_buf(),
            project_type,
            is_git_repo,
            has_openfang_dir,
            cache,
        }
    }

    /// Get the content of a cached context file, refreshing if mtime changed.
    pub fn get_file(&mut self, name: &str) -> Option<&str> {
        let file_path = self.workspace_root.join(name);
        let had_cached = self.cache.contains_key(name);

        // Check if we have a cached version
        if let Some(cached) = self.cache.get(name) {
            // Verify mtime hasn't changed
            if let Ok(meta) = std::fs::metadata(&file_path) {
                if let Ok(mtime) = meta.modified() {
                    if mtime == cached.mtime {
                        return self.cache.get(name).map(|c| c.content.as_str());
                    }
                }
            }
        }

        // Cache miss or mtime changed — re-read.
        match read_cached_file(&file_path) {
            CachedFileRead::Loaded(new_cached) => {
                self.cache.insert(name.to_string(), new_cached);
                self.cache.get(name).map(|c| c.content.as_str())
            }
            CachedFileRead::Missing | CachedFileRead::Oversized => {
                self.cache.remove(name);
                None
            }
            CachedFileRead::Unreadable => {
                if had_cached {
                    self.cache.get(name).map(|c| c.content.as_str())
                } else {
                    None
                }
            }
        }
    }

    /// Build a prompt context section summarizing the workspace.
    pub fn build_context_section(&mut self) -> String {
        let mut parts = Vec::new();

        parts.push(format!(
            "## Workspace Context\n- Project: {} ({})",
            self.workspace_root
                .file_name()
                .map(|n| n.to_string_lossy().to_string())
                .unwrap_or_else(|| "workspace".to_string()),
            self.project_type.label(),
        ));

        if self.is_git_repo {
            parts.push("- Git repository: yes".to_string());
        }

        // Include context file summaries in a stable order so prompt context
        // doesn't vary across runs due to HashMap iteration.
        let mut file_names: Vec<String> = self.cache.keys().cloned().collect();
        file_names.sort();
        for name in file_names {
            if let Some(content) = self.get_file(&name) {
                // Take first 200 chars as preview
                let preview = if content.len() > 200 {
                    format!("{}...", crate::str_utils::safe_truncate_str(content, 200))
                } else {
                    content.to_string()
                };
                parts.push(format!("### {}\n{}", name, preview));
            }
        }

        parts.join("\n")
    }
}

/// Result of attempting to refresh a cached workspace context file.
enum CachedFileRead {
    Loaded(CachedFile),
    Missing,
    Oversized,
    Unreadable,
}

/// Read a file into the cache if it exists and is under the size limit.
fn read_cached_file(path: &Path) -> CachedFileRead {
    let meta = match std::fs::metadata(path) {
        Ok(meta) => meta,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return CachedFileRead::Missing,
        Err(error) => {
            warn!(
                path = %path.display(),
                %error,
                "Failed to stat workspace context file; skipping"
            );
            return CachedFileRead::Unreadable;
        }
    };
    if meta.len() > MAX_FILE_SIZE {
        debug!(
            path = %path.display(),
            size = meta.len(),
            "Skipping oversized context file"
        );
        return CachedFileRead::Oversized;
    }
    let mtime = match meta.modified() {
        Ok(mtime) => mtime,
        Err(error) => {
            warn!(
                path = %path.display(),
                %error,
                "Failed to read workspace context file metadata; skipping"
            );
            return CachedFileRead::Unreadable;
        }
    };
    let content = match std::fs::read_to_string(path) {
        Ok(content) => content,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return CachedFileRead::Missing,
        Err(error) => {
            warn!(
                path = %path.display(),
                %error,
                "Failed to read workspace context file; skipping"
            );
            return CachedFileRead::Unreadable;
        }
    };
    CachedFileRead::Loaded(CachedFile { content, mtime })
}

/// Detect project type from marker files in the root.
fn detect_project_type(root: &Path) -> ProjectType {
    if is_file(root, "Cargo.toml") {
        ProjectType::Rust
    } else if is_file(root, "package.json") {
        ProjectType::Node
    } else if is_file(root, "pyproject.toml")
        || is_file(root, "setup.py")
        || is_file(root, "requirements.txt")
    {
        ProjectType::Python
    } else if is_file(root, "go.mod") {
        ProjectType::Go
    } else if is_file(root, "pom.xml") || is_file(root, "build.gradle") {
        ProjectType::Java
    } else if has_extension_in_dir(root, "csproj") || has_extension_in_dir(root, "sln") {
        ProjectType::DotNet
    } else {
        ProjectType::Unknown
    }
}

fn is_file(root: &Path, name: &str) -> bool {
    root.join(name).is_file()
}

/// Check if any file with the given extension exists in a directory.
fn has_extension_in_dir(dir: &Path, ext: &str) -> bool {
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            if let Some(e) = entry.path().extension() {
                if e == ext {
                    return true;
                }
            }
        }
    }
    false
}

/// Persistent workspace state, saved to `.openfang/workspace-state.json`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceState {
    /// State format version.
    #[serde(default = "default_version")]
    pub version: u32,
    /// Timestamp when bootstrap was first seeded.
    pub bootstrap_seeded_at: Option<String>,
    /// Timestamp when onboarding was completed.
    pub onboarding_completed_at: Option<String>,
}

fn default_version() -> u32 {
    1
}

impl Default for WorkspaceState {
    fn default() -> Self {
        Self {
            version: default_version(),
            bootstrap_seeded_at: None,
            onboarding_completed_at: None,
        }
    }
}

impl WorkspaceState {
    /// Load state from the workspace's `.openfang/workspace-state.json`.
    pub fn load(workspace_root: &Path) -> Self {
        let path = workspace_root
            .join(".openfang")
            .join("workspace-state.json");
        match std::fs::read_to_string(&path) {
            Ok(json) => match serde_json::from_str(&json) {
                Ok(state) => state,
                Err(error) => {
                    warn!(
                        path = %path.display(),
                        %error,
                        "Failed to parse workspace state; falling back to defaults"
                    );
                    Self::default()
                }
            },
            Err(error) => {
                if error.kind() != std::io::ErrorKind::NotFound {
                    warn!(
                        path = %path.display(),
                        %error,
                        "Failed to read workspace state; falling back to defaults"
                    );
                }
                Self::default()
            }
        }
    }

    /// Save state to the workspace's `.openfang/workspace-state.json`.
    pub fn save(&self, workspace_root: &Path) -> Result<(), String> {
        let dir = workspace_root.join(".openfang");
        std::fs::create_dir_all(&dir)
            .map_err(|e| format!("Failed to create .openfang dir: {e}"))?;
        let path = dir.join("workspace-state.json");
        let json = serde_json::to_string_pretty(self)
            .map_err(|e| format!("Failed to serialize state: {e}"))?;

        let file_name = path
            .file_name()
            .and_then(|name| name.to_str())
            .filter(|name| !name.is_empty())
            .ok_or_else(|| "Failed to determine workspace state file name".to_string())?;
        let tmp_path = path.with_file_name(format!(".{file_name}.tmp-{}", Uuid::new_v4()));

        let write_result = (|| -> Result<(), String> {
            #[cfg(unix)]
            {
                use std::fs::OpenOptions;
                use std::io::Write;
                use std::os::unix::fs::OpenOptionsExt;

                let mut file = OpenOptions::new()
                    .write(true)
                    .create_new(true)
                    .mode(0o600)
                    .open(&tmp_path)
                    .map_err(|e| format!("Failed to create temporary workspace state file: {e}"))?;
                file.write_all(json.as_bytes())
                    .map_err(|e| format!("Failed to write workspace state: {e}"))?;
                file.sync_all()
                    .map_err(|e| format!("Failed to sync workspace state: {e}"))?;
            }

            #[cfg(not(unix))]
            {
                use std::io::Write;

                let mut file = std::fs::File::create(&tmp_path)
                    .map_err(|e| format!("Failed to create temporary workspace state file: {e}"))?;
                file.write_all(json.as_bytes())
                    .map_err(|e| format!("Failed to write workspace state: {e}"))?;
                file.sync_all()
                    .map_err(|e| format!("Failed to sync workspace state: {e}"))?;
            }

            std::fs::rename(&tmp_path, &path)
                .map_err(|e| format!("Failed to persist workspace state atomically: {e}"))?;
            Ok(())
        })();

        if write_result.is_err() {
            let _ = std::fs::remove_file(&tmp_path);
        }

        write_result
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_rust_project() {
        let dir = std::env::temp_dir().join("openfang_ws_rust_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("Cargo.toml"), "[package]\nname = \"test\"").unwrap();
        assert_eq!(detect_project_type(&dir), ProjectType::Rust);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_detect_node_project() {
        let dir = std::env::temp_dir().join("openfang_ws_node_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("package.json"), "{}").unwrap();
        assert_eq!(detect_project_type(&dir), ProjectType::Node);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_detect_python_project() {
        let dir = std::env::temp_dir().join("openfang_ws_py_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("pyproject.toml"), "[tool.poetry]").unwrap();
        assert_eq!(detect_project_type(&dir), ProjectType::Python);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_detect_go_project() {
        let dir = std::env::temp_dir().join("openfang_ws_go_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("go.mod"), "module example.com/test").unwrap();
        assert_eq!(detect_project_type(&dir), ProjectType::Go);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_detect_dotnet_project_from_csproj() {
        let dir = std::env::temp_dir().join("openfang_ws_dotnet_csproj_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(
            dir.join("Example.csproj"),
            "<Project Sdk=\"Microsoft.NET.Sdk\" />",
        )
        .unwrap();
        assert_eq!(detect_project_type(&dir), ProjectType::DotNet);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_detect_dotnet_project_from_sln() {
        let dir = std::env::temp_dir().join("openfang_ws_dotnet_sln_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(
            dir.join("Example.sln"),
            "Microsoft Visual Studio Solution File",
        )
        .unwrap();
        assert_eq!(detect_project_type(&dir), ProjectType::DotNet);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_detect_unknown_project() {
        let dir = std::env::temp_dir().join("openfang_ws_unk_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        assert_eq!(detect_project_type(&dir), ProjectType::Unknown);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_detect_project_type_ignores_directory_markers() {
        let dir = std::env::temp_dir().join("openfang_ws_marker_dirs_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(dir.join("Cargo.toml")).unwrap();
        std::fs::create_dir_all(dir.join("package.json")).unwrap();
        std::fs::create_dir_all(dir.join("pyproject.toml")).unwrap();
        std::fs::create_dir_all(dir.join("go.mod")).unwrap();
        std::fs::create_dir_all(dir.join("pom.xml")).unwrap();
        std::fs::create_dir_all(dir.join("Example.csproj")).unwrap();
        std::fs::create_dir_all(dir.join("Example.sln")).unwrap();

        assert_eq!(detect_project_type(&dir), ProjectType::Unknown);

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_detect_project_type_prefers_real_file_over_directory_marker() {
        let dir = std::env::temp_dir().join("openfang_ws_real_file_over_dir_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(dir.join("Cargo.toml")).unwrap();
        std::fs::write(dir.join("package.json"), "{}").unwrap();

        assert_eq!(detect_project_type(&dir), ProjectType::Node);

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_workspace_context_detect() {
        let dir = std::env::temp_dir().join("openfang_ws_ctx_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("Cargo.toml"), "[package]").unwrap();
        std::fs::create_dir_all(dir.join(".git")).unwrap();
        std::fs::write(dir.join("AGENTS.md"), "# Agent Guidelines\nBe helpful.").unwrap();

        let ctx = WorkspaceContext::detect(&dir);
        assert_eq!(ctx.project_type, ProjectType::Rust);
        assert!(ctx.is_git_repo);
        assert!(ctx.cache.contains_key("AGENTS.md"));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_get_file_cache_hit() {
        let dir = std::env::temp_dir().join("openfang_ws_cache_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("SOUL.md"), "I am a helpful agent.").unwrap();

        let mut ctx = WorkspaceContext::detect(&dir);
        let content1 = ctx.get_file("SOUL.md").map(|s| s.to_string());
        let content2 = ctx.get_file("SOUL.md").map(|s| s.to_string());
        assert_eq!(content1, content2);
        assert!(content1.unwrap().contains("helpful agent"));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_file_size_cap() {
        let dir = std::env::temp_dir().join("openfang_ws_cap_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        // Write a file larger than 32KB
        let big = "x".repeat(40_000);
        std::fs::write(dir.join("AGENTS.md"), &big).unwrap();

        let ctx = WorkspaceContext::detect(&dir);
        assert!(!ctx.cache.contains_key("AGENTS.md"));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_get_file_keeps_cached_content_when_refresh_becomes_unreadable() {
        let dir = std::env::temp_dir().join("openfang_ws_cache_unreadable_refresh_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("SOUL.md"), "original soul").unwrap();

        let mut ctx = WorkspaceContext::detect(&dir);
        assert_eq!(ctx.get_file("SOUL.md"), Some("original soul"));

        std::fs::remove_file(dir.join("SOUL.md")).unwrap();
        std::fs::create_dir_all(dir.join("SOUL.md")).unwrap();

        assert_eq!(ctx.get_file("SOUL.md"), Some("original soul"));
        assert!(ctx.cache.contains_key("SOUL.md"));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_get_file_removes_cached_content_when_file_disappears() {
        let dir = std::env::temp_dir().join("openfang_ws_cache_missing_refresh_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("SOUL.md"), "original soul").unwrap();

        let mut ctx = WorkspaceContext::detect(&dir);
        assert_eq!(ctx.get_file("SOUL.md"), Some("original soul"));

        std::fs::remove_file(dir.join("SOUL.md")).unwrap();

        assert_eq!(ctx.get_file("SOUL.md"), None);
        assert!(!ctx.cache.contains_key("SOUL.md"));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_detect_skips_unreadable_context_entry_without_panicking() {
        let dir = std::env::temp_dir().join("openfang_ws_bad_context_entry_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(dir.join("AGENTS.md")).unwrap();

        let ctx = WorkspaceContext::detect(&dir);
        assert!(!ctx.cache.contains_key("AGENTS.md"));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_build_context_section() {
        let dir = std::env::temp_dir().join("openfang_ws_section_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("Cargo.toml"), "[package]").unwrap();
        std::fs::create_dir_all(dir.join(".git")).unwrap();
        std::fs::write(dir.join("SOUL.md"), "Be nice").unwrap();

        let mut ctx = WorkspaceContext::detect(&dir);
        let section = ctx.build_context_section();
        assert!(section.contains("Rust"));
        assert!(section.contains("Git repository: yes"));
        assert!(section.contains("SOUL.md"));
        assert!(section.contains("Be nice"));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_build_context_section_sorts_context_files() {
        let dir = std::env::temp_dir().join("openfang_ws_section_sort_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("Cargo.toml"), "[package]").unwrap();
        std::fs::write(dir.join("SOUL.md"), "Soul preview").unwrap();
        std::fs::write(dir.join("AGENTS.md"), "Agents preview").unwrap();
        std::fs::write(dir.join("TOOLS.md"), "Tools preview").unwrap();

        let mut ctx = WorkspaceContext::detect(&dir);
        let section = ctx.build_context_section();

        let agents_pos = section.find("### AGENTS.md").unwrap();
        let soul_pos = section.find("### SOUL.md").unwrap();
        let tools_pos = section.find("### TOOLS.md").unwrap();

        assert!(agents_pos < soul_pos);
        assert!(soul_pos < tools_pos);

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_workspace_state_round_trip() {
        let dir = std::env::temp_dir().join("openfang_ws_state_test");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let state = WorkspaceState {
            version: 1,
            bootstrap_seeded_at: Some("2026-01-01T00:00:00Z".to_string()),
            onboarding_completed_at: None,
        };
        state.save(&dir).unwrap();

        let loaded = WorkspaceState::load(&dir);
        assert_eq!(loaded.version, 1);
        assert_eq!(
            loaded.bootstrap_seeded_at.as_deref(),
            Some("2026-01-01T00:00:00Z")
        );
        assert!(loaded.onboarding_completed_at.is_none());

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_workspace_state_missing_file() {
        let dir = std::env::temp_dir().join("openfang_ws_state_missing");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let state = WorkspaceState::load(&dir);
        assert_eq!(state.version, 1);
        assert!(state.bootstrap_seeded_at.is_none());
        assert!(state.onboarding_completed_at.is_none());

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_workspace_state_missing_version_defaults_to_current_format() {
        let dir = std::env::temp_dir().join("openfang_ws_state_missing_version");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(dir.join(".openfang")).unwrap();
        std::fs::write(
            dir.join(".openfang").join("workspace-state.json"),
            r#"{"bootstrap_seeded_at":"2026-01-01T00:00:00Z"}"#,
        )
        .unwrap();

        let state = WorkspaceState::load(&dir);
        assert_eq!(state.version, 1);
        assert_eq!(
            state.bootstrap_seeded_at.as_deref(),
            Some("2026-01-01T00:00:00Z")
        );
        assert!(state.onboarding_completed_at.is_none());

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_workspace_state_save_writes_atomically_without_leaving_temp_files() {
        let dir = std::env::temp_dir().join("openfang_ws_state_atomic_save");
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();

        let state = WorkspaceState {
            version: 1,
            bootstrap_seeded_at: Some("2026-01-01T00:00:00Z".to_string()),
            onboarding_completed_at: Some("2026-01-02T00:00:00Z".to_string()),
        };
        state.save(&dir).unwrap();

        let loaded = WorkspaceState::load(&dir);
        assert_eq!(loaded.version, state.version);
        assert_eq!(loaded.bootstrap_seeded_at, state.bootstrap_seeded_at);
        assert_eq!(loaded.onboarding_completed_at, state.onboarding_completed_at);

        let tmp_files: Vec<_> = std::fs::read_dir(dir.join(".openfang"))
            .unwrap()
            .filter_map(Result::ok)
            .filter(|entry| entry.file_name().to_string_lossy().contains(".tmp-"))
            .collect();
        assert!(
            tmp_files.is_empty(),
            "temporary workspace state files should be cleaned up"
        );

        let _ = std::fs::remove_dir_all(&dir);
    }
}
