// Type-only stubs for offline checking. Not production source or a bypass.
declare const Deno: {
  env: { get(name: string): string | undefined }
  serve(handler: (request: Request) => Response | Promise<Response>): void
}
declare module 'https://esm.sh/@supabase/supabase-js@2' {
  export function createClient(url: string, key: string, options?: { auth: { persistSession: boolean } }): {
    auth: { getUser(jwt: string): Promise<{ data: { user: { id: string } | null }; error: unknown | null }> }
    from(table: string): any
    rpc(name: string, args: { p_kind: 'slack' | 'operator'; p_actor_id: string; p_request_key: string }):
      PromiseLike<{ data: unknown; error: unknown }>
  }
}
