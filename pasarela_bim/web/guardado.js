/* File associations belong to this editor session, never to the portable JSON. */
(function(root){
  'use strict';
  function createController({request,getModel,getRevision,toPortable,onState=()=>{},onSaved=()=>{},onOpen=()=>{}}){
    let documento=null,operation='',epoch=0;
    const snapshot=()=>({documento:documento?{...documento}:null,busy:!!operation,operation,epoch});
    const notify=()=>onState(snapshot());
    function checked(value){
      if(!value||typeof value.id!=='string'||!value.id||typeof value.nombre!=='string'||!value.nombre)throw Error('El programa no confirmó el archivo de destino. Conserva tus cambios y vuelve a guardar.');
      return {id:value.id,nombre:value.nombre,ruta:typeof value.ruta==='string'?value.ruta:''};
    }
    return {
      snapshot,
      reset(){documento=null;epoch++;notify();},
      async save({saveAs=false}={}){
        if(operation||!getModel())return null;
        const revision=getRevision(),started=epoch,modelo=toPortable(getModel());
        modelo.proyecto.guardado_en=new Date().toISOString();
        const payload={modelo,guardar_como:saveAs,nombre_sugerido:(modelo.proyecto.nombre||'pasarela').replace(/[<>:"/\\|?*\x00-\x1f]/g,'_')+'.json'};
        if(documento)payload.documento_id=documento.id;
        operation='save';notify();
        try{
          const result=await request('/api/proyecto/guardar',payload);
          if(result.cancelado)return {cancelado:true};
          if(result.guardado!==true)throw Error('El programa no confirmó el guardado. Los cambios siguen pendientes.');
          const file=checked(result.documento);
          if(started!==epoch)return {guardado:true,anterior:true,documento:file};
          documento=file;
          const unchanged=getRevision()===revision;
          if(unchanged)onSaved(modelo.proyecto.guardado_en);
          return {guardado:true,pendiente:!unchanged,documento:file};
        }finally{operation='';notify();}
      },
      async open(){
        if(operation)return null;
        const started=epoch,revision=getRevision();operation='open';notify();
        try{
          const result=await request('/api/proyecto/abrir',{});
          if(result.cancelado)return {cancelado:true};
          const file=checked(result.documento);
          if(started!==epoch||getRevision()!==revision)throw Error('El proyecto cambió mientras se abría el archivo. Vuelve a abrirlo cuando termines la edición.');
          // Let the editor validate the contents before replacing its file binding.
          onOpen(result.modelo);documento=file;notify();return result;
        }finally{operation='';notify();}
      }
    };
  }
  root.PasarelaFiles={createController};
  if(typeof module!=='undefined')module.exports=root.PasarelaFiles;
})(typeof window!=='undefined'?window:globalThis);
