Deno.serve((_req: Request) => {
  const present = (name: string) => Boolean((Deno.env.get(name) ?? '').trim())
  return new Response(JSON.stringify({
    schema: 'aegis.provider-secret-status.v1',
    providers: {
      dashscope: {
        api_key_present: present('DASHSCOPE_API_KEY'),
      },
      openai: {
        api_key_present: present('OPENAI_API_KEY'),
        model_present: present('OPENAI_MODEL'),
        enabled: Deno.env.get('CHAT_ENABLE_OPENAI') === 'true',
      },
      anthropic: {
        api_key_present: present('ANTHROPIC_API_KEY'),
      },
      fireworks: {
        api_key_present: present('FIREWORKS_API_KEY'),
      },
      openrouter: {
        api_key_present: present('OPENROUTER_API_KEY'),
      },
      google: {
        api_key_present: present('GOOGLE_API_KEY') || present('GEMINI_API_KEY'),
      },
      nebius: {
        api_key_present: present('NEBIUS_API_KEY'),
        model_present: present('NEBIUS_MODEL'),
        enabled: Deno.env.get('CHAT_ENABLE_NEBIUS') === 'true',
      },
      azure: {
        api_key_present: present('AZURE_OPENAI_API_KEY'),
        deployment_present: present('AZURE_OPENAI_DEPLOYMENT'),
        endpoint_present: present('AZURE_OPENAI_ENDPOINT'),
        enabled: Deno.env.get('CHAT_ENABLE_AZURE') === 'true',
      },
    },
    authority_effect: 'NONE',
  }), {
    headers: { 'content-type': 'application/json' },
  })
})
