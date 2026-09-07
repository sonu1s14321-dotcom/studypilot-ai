const API_URL=(import.meta.env.VITE_API_URL||'http://127.0.0.1:8000').replace(/\/$/,'')
export const tokenStore={get:()=>localStorage.getItem('studypilot_token'),set:t=>localStorage.setItem('studypilot_token',t),clear:()=>localStorage.removeItem('studypilot_token')}
export async function api(path,options={}){
  const headers={...(options.headers||{})}; if(!(options.body instanceof FormData)) headers['Content-Type']='application/json'
  const token=tokenStore.get(); if(token) headers.Authorization=`Bearer ${token}`
  const r=await fetch(`${API_URL}${path}`,{...options,headers}); const data=await r.json().catch(()=>({}))
  if(r.status===401){tokenStore.clear();window.dispatchEvent(new Event('studypilot:logout'))}
  if(!r.ok) throw new Error(data.detail||'Request failed'); return data
}
