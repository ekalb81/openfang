//! Native OpenAI OAuth support for OpenFang.
//!
//! This module implements the credential storage and token exchange/refresh pieces
//! needed for first-class OpenAI OAuth in OpenFang. The API layer can drive the
//! browser flow and then persist credentials here.

use base64::Engine;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use tracing::warn;
use uuid::Uuid;
use zeroize::Zeroizing;

pub const OPENAI_AUTH_URL: &str = "https://auth.openai.com/oauth/authorize";
pub const OPENAI_TOKEN_URL: &str = "https://auth.openai.com/oauth/token";
pub const DEFAULT_REDIRECT_URI: &str = "http://127.0.0.1:1455/api/providers/openai/oauth/callback";

fn default_provider() -> String {
    "openai".to_string()
}

fn default_mode() -> String {
    "oauth".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenAIOAuthCredentials {
    #[serde(default = "default_provider")]
    pub provider: String,
    #[serde(default = "default_mode")]
    pub mode: String,
    pub access: String,
    pub refresh: String,
    pub expires: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub account_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub email: Option<String>,
}

#[derive(Debug, Clone)]
pub struct OpenAIOAuthStart {
    pub auth_url: String,
    pub state: String,
    pub verifier: String,
    pub challenge: String,
    pub redirect_uri: String,
}

#[derive(Debug, Deserialize)]
struct TokenResponse {
    access_token: String,
    #[serde(default)]
    refresh_token: String,
    #[serde(default)]
    expires_in: i64,
    #[serde(default)]
    id_token: Option<String>,
}

fn unix_now_secs() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs() as i64
}

fn oauth_home_dir() -> PathBuf {
    std::env::var("OPENFANG_HOME")
        .ok()
        .filter(|s| !s.trim().is_empty())
        .map(PathBuf::from)
        .or_else(|| dirs::home_dir().map(|p| p.join(".openfang")))
        .unwrap_or_else(|| PathBuf::from(".openfang"))
}

pub fn default_profile_id() -> String {
    std::env::var("OPENFANG_OPENAI_OAUTH_PROFILE")
        .ok()
        .filter(|s| !s.trim().is_empty())
        .unwrap_or_else(|| "default".to_string())
}

pub fn store_path_for_profile(profile_id: Option<&str>) -> PathBuf {
    let profile_id = profile_id
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string())
        .unwrap_or_else(default_profile_id);

    if let Ok(path) = std::env::var("OPENFANG_OPENAI_OAUTH_PATH") {
        if !path.trim().is_empty() {
            let base = PathBuf::from(path);
            if profile_id == "default" {
                return base;
            }
            let parent = base.parent().map(PathBuf::from).unwrap_or_default();
            let stem = base
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("openai-oauth");
            let ext = base.extension().and_then(|s| s.to_str()).unwrap_or("json");
            return parent.join(format!("{}-{}.{}", stem, profile_id, ext));
        }
    }

    let root = oauth_home_dir().join("openai-oauth");
    root.join(format!("{}.json", profile_id))
}

pub fn default_store_path() -> PathBuf {
    store_path_for_profile(None)
}

pub fn load_credentials(path: &Path) -> Option<OpenAIOAuthCredentials> {
    let content = std::fs::read_to_string(path).ok()?;
    let creds: OpenAIOAuthCredentials = serde_json::from_str(&content).ok()?;
    if creds.access.trim().is_empty() {
        return None;
    }
    Some(creds)
}

pub fn save_credentials(path: &Path, creds: &OpenAIOAuthCredentials) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("Failed to create OAuth dir: {e}"))?;
    }

    let json = serde_json::to_string_pretty(creds)
        .map_err(|e| format!("Failed to serialize OAuth credentials: {e}"))?;

    let file_name = path
        .file_name()
        .and_then(|name| name.to_str())
        .filter(|name| !name.is_empty())
        .ok_or_else(|| "Failed to determine OAuth credential file name".to_string())?;
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
                .map_err(|e| format!("Failed to create temporary OAuth credentials file: {e}"))?;
            file.write_all(json.as_bytes())
                .map_err(|e| format!("Failed to write OAuth credentials: {e}"))?;
            file.sync_all()
                .map_err(|e| format!("Failed to sync OAuth credentials: {e}"))?;
        }

        #[cfg(not(unix))]
        {
            use std::io::Write;

            let mut file = std::fs::File::create(&tmp_path)
                .map_err(|e| format!("Failed to create temporary OAuth credentials file: {e}"))?;
            file.write_all(json.as_bytes())
                .map_err(|e| format!("Failed to write OAuth credentials: {e}"))?;
            file.sync_all()
                .map_err(|e| format!("Failed to sync OAuth credentials: {e}"))?;
        }

        std::fs::rename(&tmp_path, path)
            .map_err(|e| format!("Failed to persist OAuth credentials atomically: {e}"))?;
        Ok(())
    })();

    if write_result.is_err() {
        let _ = std::fs::remove_file(&tmp_path);
    }

    write_result
}

pub fn remove_credentials(path: &Path) -> Result<(), String> {
    if !path.exists() {
        return Ok(());
    }
    std::fs::remove_file(path).map_err(|e| format!("Failed to remove OAuth credentials: {e}"))
}

pub fn credentials_valid(creds: &OpenAIOAuthCredentials) -> bool {
    !creds.access.trim().is_empty() && creds.expires > unix_now_secs() + 30
}

pub fn read_access_token(path: &Path) -> Option<String> {
    let creds = load_credentials(path)?;
    if credentials_valid(&creds) {
        Some(creds.access)
    } else {
        None
    }
}

/// Best-effort synchronous token resolution for runtime call sites that are not async.
///
/// If cached credentials are still valid, returns the current access token.
/// If expired and `OPENAI_OAUTH_CLIENT_ID` / `OPENAI_CLIENT_ID` is configured,
/// attempts a refresh on a short-lived Tokio runtime in a helper thread.
pub fn ensure_access_token_sync(path: &Path) -> Option<String> {
    let creds = load_credentials(path)?;
    if credentials_valid(&creds) {
        return Some(creds.access);
    }

    let client_id = std::env::var("OPENAI_OAUTH_CLIENT_ID")
        .ok()
        .filter(|s| !s.trim().is_empty())
        .or_else(|| {
            std::env::var("OPENAI_CLIENT_ID")
                .ok()
                .filter(|s| !s.trim().is_empty())
        })?;

    let path_buf = path.to_path_buf();
    let join = std::thread::spawn(move || {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .ok()?;
        let refreshed = rt.block_on(refresh_credentials(&client_id, &creds)).ok()?;
        save_credentials(&path_buf, &refreshed).ok()?;
        Some(refreshed.access)
    });

    join.join().ok().flatten()
}

fn base64url_no_pad(bytes: &[u8]) -> String {
    base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(bytes)
}

pub fn generate_pkce_start(client_id: &str, redirect_uri: Option<&str>) -> OpenAIOAuthStart {
    let verifier = format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple());
    let challenge = base64url_no_pad(Sha256::digest(verifier.as_bytes()).as_slice());
    let state = Uuid::new_v4().to_string();
    let requested_redirect_uri = redirect_uri.unwrap_or(DEFAULT_REDIRECT_URI).trim();
    let redirect_uri = match reqwest::Url::parse(requested_redirect_uri) {
        Ok(_) => requested_redirect_uri.to_string(),
        Err(err) => {
            warn!(
                redirect_uri = requested_redirect_uri,
                error = %err,
                fallback = DEFAULT_REDIRECT_URI,
                "invalid OpenAI OAuth redirect URI; falling back to default"
            );
            DEFAULT_REDIRECT_URI.to_string()
        }
    };

    let auth_url = reqwest::Url::parse_with_params(
        OPENAI_AUTH_URL,
        &[
            ("response_type", "code"),
            ("client_id", client_id),
            ("redirect_uri", redirect_uri.as_str()),
            ("scope", "openid profile email offline_access"),
            ("code_challenge", challenge.as_str()),
            ("code_challenge_method", "S256"),
            ("state", state.as_str()),
        ],
    )
    .expect("valid OpenAI auth URL")
    .to_string();

    OpenAIOAuthStart {
        auth_url,
        state,
        verifier,
        challenge,
        redirect_uri,
    }
}

pub async fn exchange_code(
    client_id: &str,
    code: &str,
    verifier: &str,
    redirect_uri: &str,
) -> Result<OpenAIOAuthCredentials, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .user_agent(crate::USER_AGENT)
        .build()
        .map_err(|e| format!("HTTP client error: {e}"))?;

    let resp = client
        .post(OPENAI_TOKEN_URL)
        .form(&[
            ("grant_type", "authorization_code"),
            ("client_id", client_id),
            ("code", code),
            ("code_verifier", verifier),
            ("redirect_uri", redirect_uri),
        ])
        .send()
        .await
        .map_err(|e| format!("OAuth token exchange failed: {e}"))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        return Err(format!("OAuth token exchange returned {status}: {body}"));
    }

    let token: TokenResponse = resp
        .json()
        .await
        .map_err(|e| format!("Failed to parse OpenAI token response: {e}"))?;

    let access_token = token.access_token;
    let refresh_token = token.refresh_token;
    let id_token = token.id_token;
    let expires_in = token.expires_in;

    let account_id = id_token
        .as_deref()
        .and_then(extract_claim_subject)
        .or_else(|| extract_claim_subject(&access_token));
    let email = id_token
        .as_deref()
        .and_then(extract_claim_email)
        .or_else(|| extract_claim_email(&access_token));

    Ok(OpenAIOAuthCredentials {
        provider: "openai".to_string(),
        mode: "oauth".to_string(),
        access: access_token,
        refresh: refresh_token,
        expires: unix_now_secs() + expires_in.max(60),
        account_id,
        email,
    })
}

pub async fn refresh_credentials(
    client_id: &str,
    creds: &OpenAIOAuthCredentials,
) -> Result<OpenAIOAuthCredentials, String> {
    if creds.refresh.trim().is_empty() {
        return Err("Stored OpenAI OAuth credentials do not include a refresh token".to_string());
    }

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .user_agent(crate::USER_AGENT)
        .build()
        .map_err(|e| format!("HTTP client error: {e}"))?;

    let refresh = Zeroizing::new(creds.refresh.clone());
    let resp = client
        .post(OPENAI_TOKEN_URL)
        .form(&[
            ("grant_type", "refresh_token"),
            ("client_id", client_id),
            ("refresh_token", refresh.as_str()),
        ])
        .send()
        .await
        .map_err(|e| format!("OAuth refresh failed: {e}"))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        return Err(format!("OAuth refresh returned {status}: {body}"));
    }

    let token: TokenResponse = resp
        .json()
        .await
        .map_err(|e| format!("Failed to parse OpenAI refresh response: {e}"))?;

    let access_token = token.access_token;
    let refresh_token = token.refresh_token;
    let id_token = token.id_token;
    let expires_in = token.expires_in;

    let account_id = id_token
        .as_deref()
        .and_then(extract_claim_subject)
        .or_else(|| extract_claim_subject(&access_token))
        .or_else(|| creds.account_id.clone());
    let email = id_token
        .as_deref()
        .and_then(extract_claim_email)
        .or_else(|| extract_claim_email(&access_token))
        .or_else(|| creds.email.clone());

    Ok(OpenAIOAuthCredentials {
        provider: creds.provider.clone(),
        mode: "oauth".to_string(),
        access: access_token,
        refresh: if refresh_token.trim().is_empty() {
            creds.refresh.clone()
        } else {
            refresh_token
        },
        expires: unix_now_secs() + expires_in.max(60),
        account_id,
        email,
    })
}

pub fn extract_claim_subject(jwt: &str) -> Option<String> {
    extract_jwt_claim(jwt, "sub")
}

pub fn extract_claim_email(jwt: &str) -> Option<String> {
    extract_jwt_claim(jwt, "email")
}

fn extract_jwt_claim(jwt: &str, key: &str) -> Option<String> {
    let parts: Vec<&str> = jwt.split('.').collect();
    if parts.len() < 2 {
        return None;
    }
    let decoded = base64::engine::general_purpose::URL_SAFE_NO_PAD
        .decode(parts[1])
        .ok()?;
    let value: serde_json::Value = serde_json::from_slice(&decoded).ok()?;
    value.get(key)?.as_str().map(|s| s.to_string())
}

#[cfg(test)]
mod tests {
    use super::{
        DEFAULT_REDIRECT_URI, OpenAIOAuthCredentials, default_mode, default_provider,
        generate_pkce_start, load_credentials, save_credentials,
    };
    use tempfile::tempdir;

    #[test]
    fn generate_pkce_start_preserves_valid_redirect_uri() {
        let start = generate_pkce_start("client-id", Some("http://localhost:3000/callback"));

        assert_eq!(start.redirect_uri, "http://localhost:3000/callback");
        assert!(
            start
                .auth_url
                .contains("redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fcallback")
        );
    }

    #[test]
    fn generate_pkce_start_falls_back_for_invalid_redirect_uri() {
        let start = generate_pkce_start("client-id", Some("not a valid uri"));

        assert_eq!(start.redirect_uri, DEFAULT_REDIRECT_URI);
        assert!(start.auth_url.contains(
            "redirect_uri=http%3A%2F%2F127.0.0.1%3A1455%2Fapi%2Fproviders%2Fopenai%2Foauth%2Fcallback"
        ));
    }

    #[test]
    fn load_credentials_accepts_legacy_json_without_provider_or_mode() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("openai-oauth.json");
        std::fs::write(
            &path,
            r#"{
  "access": "access-token",
  "refresh": "refresh-token",
  "expires": 1234567890
}"#,
        )
        .unwrap();

        let creds = load_credentials(&path).expect("legacy credentials should load");

        assert_eq!(creds.provider, default_provider());
        assert_eq!(creds.mode, default_mode());
        assert_eq!(creds.access, "access-token");
        assert_eq!(creds.refresh, "refresh-token");
        assert_eq!(creds.expires, 1234567890);
        assert_eq!(creds.account_id, None);
        assert_eq!(creds.email, None);
    }

    #[test]
    fn save_credentials_writes_atomically_without_leaving_temp_files() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("openai-oauth.json");
        let creds = OpenAIOAuthCredentials {
            provider: "openai".to_string(),
            mode: "oauth".to_string(),
            access: "access-token".to_string(),
            refresh: "refresh-token".to_string(),
            expires: 1234567890,
            account_id: Some("acct_123".to_string()),
            email: Some("user@example.com".to_string()),
        };

        save_credentials(&path, &creds).expect("credentials should save");

        let loaded = load_credentials(&path).expect("saved credentials should load");
        assert_eq!(loaded.provider, creds.provider);
        assert_eq!(loaded.mode, creds.mode);
        assert_eq!(loaded.access, creds.access);
        assert_eq!(loaded.refresh, creds.refresh);
        assert_eq!(loaded.expires, creds.expires);
        assert_eq!(loaded.account_id, creds.account_id);
        assert_eq!(loaded.email, creds.email);

        let tmp_files: Vec<_> = std::fs::read_dir(dir.path())
            .unwrap()
            .filter_map(Result::ok)
            .filter(|entry| entry.file_name().to_string_lossy().contains(".tmp-"))
            .collect();
        assert!(tmp_files.is_empty(), "temporary OAuth files should be cleaned up");
    }
}
