/** AEGIS Ω command navigation: pure, locally testable, published routes only. */
export type CommandRoute = Readonly<{href:string;label:string;detail:string}>

export const COMMAND_ROUTES = [
  { href:'/',label:'Overview',detail:'AEGIS command homepage' },
  { href:'/platform',label:'ResearchOS',detail:'Curated research sources' },
  { href:'/console',label:'Console',detail:'Observed operator state' },
  { href:'/runtime',label:'Runtime',detail:'Verification and system boundaries' },
  { href:'/compliance',label:'Governance',detail:'Control mappings and limits' },
  { href:'/docs',label:'Developers',detail:'API reference' },
  { href:'/tools',label:'Tools',detail:'Creator tools and access' },
  { href:'/pricing',label:'Access',detail:'Plans and provisioning' },
  { href:'/claim-sponsor',label:'Sponsor claim',detail:'Existing sponsor access process' },
] as const satisfies readonly CommandRoute[]

export type PaletteDirection = 'ArrowUp'|'ArrowDown'|'Home'|'End'

export function filterCommandRoutes(query:string, routes:readonly CommandRoute[]=COMMAND_ROUTES): CommandRoute[] {
  const needle=query.trim().toLocaleLowerCase()
  if(!needle) return [...routes]
  return routes.filter(route=>(route.label+' '+route.detail).toLocaleLowerCase().includes(needle))
}

/** -1 means focus the search input; no wrap to a nonexistent result. */
export function nextPaletteIndex(index:number,total:number,key:PaletteDirection):number {
  if(!Number.isInteger(total)||total<=0) return -1
  if(key==='Home') return 0
  if(key==='End') return total-1
  if(key==='ArrowDown') return index<0?0:(index+1)%total
  if(key==='ArrowUp') return index<0?total-1:index===0?-1:index-1
  return -1
}
