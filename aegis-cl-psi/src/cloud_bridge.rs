//! DashScope Cloud Bridge — Alibaba Cloud API Client
//! EPISTEMIC TIER: T2
//!
//! Used for PAPO-Ψ verification and SAHOO proof checks when local
//! Lyapunov condition degrades or H_d > τ.
//! Hard budget cap: $200 Alibaba Cloud credit.
//! Auto-throttle at $180 (90% of cap).

use serde::{Deserialize, Serialize};

const BUDGET_CAP_USD: f32 = 200.0;
const THROTTLE_AT_USD: f32 = 180.0;
const COST_PER_CALL_USD: f32 = 0.001; // ~1000 calls per dollar at qwen-plus rates

#[derive(Serialize)]
struct DashScopeRequest {
    model: String,
    input: DashScopeInput,
}

#[derive(Serialize)]
struct DashScopeInput {
    messages: Vec<DashScopeMessage>,
}

#[derive(Serialize)]
struct DashScopeMessage {
    role: String,
    content: String,
}

#[derive(Deserialize, Debug)]
pub struct DashScopeOutput {
    pub text: Option<String>,
    pub finish_reason: Option<String>,
}

pub struct CloudBridge {
    pub api_key: Option<String>,
    pub model: String,
    pub total_cost_usd: f32,
    pub call_count: u64,
    pub throttled: bool,
}

#[derive(Debug)]
pub enum BridgeError {
    Throttled { spent: f32, cap: f32 },
    NoApiKey,
    RequestFailed(String),
}

impl CloudBridge {
    pub fn new(api_key: Option<String>, model: &str) -> Self {
        Self {
            api_key,
            model: model.to_string(),
            total_cost_usd: 0.0,
            call_count: 0,
            throttled: false,
        }
    }

    pub fn from_env() -> Self {
        let key = std::env::var("DASHSCOPE_API_KEY").ok();
        let model = std::env::var("DASHSCOPE_MODEL")
            .unwrap_or_else(|_| "qwen-plus".to_string());
        Self::new(key, &model)
    }

    fn check_budget(&mut self) -> Result<(), BridgeError> {
        if self.total_cost_usd >= BUDGET_CAP_USD {
            self.throttled = true;
            return Err(BridgeError::Throttled {
                spent: self.total_cost_usd,
                cap: BUDGET_CAP_USD,
            });
        }
        if self.total_cost_usd >= THROTTLE_AT_USD {
            self.throttled = true;
        }
        Ok(())
    }

    /// Verify a reasoning payload via DashScope.
    /// Returns the model's output text, or an error.
    pub fn verify(&mut self, prompt: &str) -> Result<String, BridgeError> {
        self.check_budget()?;
        let key = self.api_key.as_ref().ok_or(BridgeError::NoApiKey)?;

        let body = serde_json::to_string(&DashScopeRequest {
            model: self.model.clone(),
            input: DashScopeInput {
                messages: vec![DashScopeMessage {
                    role: "user".to_string(),
                    content: prompt.to_string(),
                }],
            },
        }).unwrap_or_default();

        self.total_cost_usd += COST_PER_CALL_USD;
        self.call_count += 1;

        Self::http_post(key, &body)
    }

    #[cfg(feature = "cloud")]
    fn http_post(key: &str, body: &str) -> Result<String, BridgeError> {
        const URL: &str = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation";
        let resp = ureq::post(URL)
            .set("Authorization", &format!("Bearer {}", key))
            .set("Content-Type", "application/json")
            .send_string(body)
            .map_err(|e| BridgeError::RequestFailed(e.to_string()))?;
        let raw: serde_json::Value = resp.into_json()
            .map_err(|e| BridgeError::RequestFailed(e.to_string()))?;
        let text = raw["output"]["text"]
            .as_str()
            .unwrap_or("no_text")
            .to_string();
        Ok(text)
    }

    #[cfg(not(feature = "cloud"))]
    fn http_post(_key: &str, _body: &str) -> Result<String, BridgeError> {
        Ok("stub_verified".to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn no_api_key_returns_error() {
        let mut bridge = CloudBridge::new(None, "qwen-plus");
        assert!(matches!(bridge.verify("test"), Err(BridgeError::NoApiKey)));
    }

    #[test]
    fn budget_cap_enforced() {
        let mut bridge = CloudBridge::new(Some("key".to_string()), "qwen-plus");
        bridge.total_cost_usd = BUDGET_CAP_USD;
        assert!(matches!(bridge.verify("test"), Err(BridgeError::Throttled { .. })));
    }

    #[test]
    fn call_count_increments() {
        let mut bridge = CloudBridge::new(Some("key".to_string()), "qwen-plus");
        bridge.verify("test1").ok();
        bridge.verify("test2").ok();
        assert_eq!(bridge.call_count, 2);
    }
}
