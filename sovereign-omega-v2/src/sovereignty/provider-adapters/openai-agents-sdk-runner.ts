import type { OpenAIAgentRunnerInputV1, OpenAIAgentRunnerOutputV1, OpenAIAgentRunnerV1 } from './openai-native-agent.js'
export interface OpenAIAgentsSdkResultV1 { readonly finalOutput?: unknown; readonly lastResponseId?: string }
export interface OpenAIAgentsSdkBindingsV1 {
  readonly Agent: new (config: { readonly name:string; readonly instructions:string; readonly model:string; readonly tools:readonly [] }) => unknown
  run(agent:unknown, task:string): Promise<OpenAIAgentsSdkResultV1>
}
export function createOpenAIAgentsSdkRunnerV1(options:{readonly bindings:OpenAIAgentsSdkBindingsV1;readonly model:string}):OpenAIAgentRunnerV1 {
  if (!options.model.trim()) throw new TypeError('OpenAI Agents SDK model must be non-empty')
  return { async run(input:OpenAIAgentRunnerInputV1):Promise<OpenAIAgentRunnerOutputV1> {
    const agent=new options.bindings.Agent({name:input.agent_name,instructions:input.instructions,model:options.model,tools:[]})
    const result=await options.bindings.run(agent,input.task)
    if (typeof result.lastResponseId!=='string'||!result.lastResponseId.trim()) throw new TypeError('OpenAI Agents SDK result must expose a stable run identifier')
    return {final_output:typeof result.finalOutput==='string'?result.finalOutput:JSON.stringify(result.finalOutput??null),run_id:result.lastResponseId,model:options.model}
  }}
}
