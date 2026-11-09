// Read-only polling; downloads remain an explicit action in the synchronizer.
export function createResourcePoller({api,notify,isBusy=()=>false,setTimer=setTimeout,clearTimer=clearTimeout}){
  let running=false,inFlight=false,timer=null;
  const notified=new Set();
  async function check(){
    if(!running||inFlight)return;
    inFlight=true;
    try{
      const status=await api('resources/status');
      const revision=status.source_commit||status.tree_sha;
      if(running&&status.available&&revision&&(status.changed>0||status.removed>0)&&!isBusy()&&!notified.has(revision)){
        notify('Hay recursos SINCAL actualizados. En Home → Sincronizador pulsa Comprobar recursos para revisarlos.');
        notified.add(revision);
      }
    }catch{
      // A disconnected workstation keeps its local resources and remains usable.
    }finally{
      inFlight=false;
      if(running)timer=setTimer(check,60000);
    }
  }
  return {
    start(){if(running)return;running=true;return check();},
    stop(){running=false;if(timer!==null)clearTimer(timer);timer=null;},
  };
}
