import { PromptConfig, Content } from './interface';

/**
 * Runtime Configuration:
 * This object contains the specific model parameters, system instructions, and
 * tools that the generated application MUST use for its own AI-powered features.
 * Import this object directly into your application code.
 */
export const runtimeConfig: PromptConfig = {
  "title": "React Calligraphy Studio Application",
  "description": "",
  "parameters": {
    "temperature": 1,
    "tokenLimits": 65535,
    "topP": 0.95,
    "groundingPromptConfig": {
      "disabled": false,
      "groundingConfig": {
        "sources": [
          {
            "type": "WEB"
          }
        ]
      }
    },
    "tools": [
      {
        "googleSearch": {}
      }
    ],
    "thinkingBudget": null,
    "thinkingLevel": "HIGH",
    "safetyCatFilters": [
      {
        "category": "HATE_SPEECH",
        "threshold": "OFF"
      },
      {
        "category": "DANGEROUS_CONTENT",
        "threshold": "OFF"
      },
      {
        "category": "SEXUALLY_EXPLICIT_CONTENT",
        "threshold": "OFF"
      },
      {
        "category": "HARASSMENT_CONTENT",
        "threshold": "OFF"
      }
    ]
  },
  "testDataV2": [
    {
      "testData": {}
    }
  ],
  "type": "multimodal_chat",
  "examples": [],
  "model": "google/gemini-3.1-pro-preview"
};

/**
 * Build-Time Context:
 * This chat history is provided as a reference for the model during application
 * generation. It is used to understand the user's intent and the desired
 * functionality of the AI.
 *
 * IMPORTANT: This conversation history MAY OR MAY NOT be 
 * included in the runtime calls of the final generated application based on
 * the user's intent and desired behavior.
 */
export const buildContextMessages: Content[] = [];
