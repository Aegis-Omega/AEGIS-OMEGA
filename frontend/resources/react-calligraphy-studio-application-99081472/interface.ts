// Defines the TypeScript interface for a saved prompt's configuration.
export interface Part {
  /** The text content of the part. */
  text?: string;
  /** Inline data, such as an image, in raw bytes. */
  inlineData?: {
    mimeType: string;
    data: string;
  };
}

export interface Content {
  /** The role of the entity that created the content, either 'user' or 'model'. */
  role: 'user' | 'model';
  /** A list of ordered parts that make up the message. */
  parts: Part[];
}

export interface SafetySetting {
  /** The safety category to configure a threshold for (e.g., HARM_CATEGORY_HATE_SPEECH). */
  category: string;
  /** The threshold for blocking responses (e.g., BLOCK_MEDIUM_AND_ABOVE). */
  threshold: string;
}

export interface GenerationConfig {
  /** Controls the degree of randomness in token selection. */
  temperature?: number;
  /** The cumulative probability cutoff for token selection. */
  topP?: number;
  /** The maximum number of tokens to consider when sampling. */
  topK?: number;
  /** The number of response variations to return. */
  candidateCount?: number;
  /** The maximum number of tokens that can be generated in the response. */
  maxOutputTokens?: number;
  /** A list of strings that tells the model to stop generating text. */
  stopSequences?: string[];
  /** The output response MIME type of the generated text (e.g., application/json). */
  responseMimeType?: string;
}

export interface Tool {
  /** A list of function declarations that the model can call. */
  functionDeclarations: any[]; // Simplified for developer clarity
}

export interface PromptConfig {
  /** The model to use for the generation request. */
  model: string;
  /** High-level instructions for the model to follow. */
  systemInstruction?: Content;
  /** Per-request settings for blocking unsafe content. */
  safetySettings?: SafetySetting[];
  /** Configuration settings for the generation request. */
  generationConfig?: GenerationConfig;
  /** A list of tools the model can use to perform actions. */
  tools?: Tool[];
}
