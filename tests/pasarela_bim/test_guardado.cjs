'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createController}=require('../../pasarela_bim/web/guardado.js');
const doc=(id='one')=>({id,nombre:id+'.json',ruta:'C:/proyectos/'+id+'.json'});
function setup(){
  const s={model:{version:2,proyecto:{nombre:'Pasarela',unidades:'m'},nodos:[],tramos:[]},revision:1,dirty:true,calls:[],saved:0,opened:0};
  s.reply=async()=>({guardado:true,documento:doc()});
  s.files=createController({request:async(url,payload)=>{s.calls.push({url,payload});return s.reply();},getModel:()=>s.model,getRevision:()=>s.revision,toPortable:structuredClone,
    onSaved:()=>{s.dirty=false;s.saved++;},onOpen:model=>{if(s.rejectOpen)throw Error('Inválido');s.model=model;s.opened++;s.files.reset();s.revision++;s.dirty=false;}});
  return s;
}
test('primer guardado elige archivo, siguientes usan su identificador y Guardar como cambia destino',async()=>{
  const s=setup();await s.files.save();assert(!Object.hasOwn(s.calls[0].payload,'documento_id'));assert.equal(s.dirty,false);
  s.revision++;s.dirty=true;await s.files.save();assert.equal(s.calls[1].payload.documento_id,'one');assert.equal(s.calls[1].payload.guardar_como,false);
  s.reply=async()=>({guardado:true,documento:doc('two')});await s.files.save({saveAs:true});assert.equal(s.calls[2].payload.guardar_como,true);
  await s.files.save();assert.equal(s.calls[3].payload.documento_id,'two');
  assert.equal(s.model.documento_id,undefined);assert.equal(s.calls[3].payload.modelo.ruta,undefined);assert.equal(s.calls[3].payload.ruta,undefined);
  assert.equal(s.model.proyecto.guardado_en,undefined);assert(s.calls[0].payload.modelo.proyecto.guardado_en);
});
test('cancelar o fallar no modifica el destino ni elimina cambios pendientes',async()=>{
  const s=setup();await s.files.save();s.dirty=true;s.revision++;
  s.reply=async()=>({cancelado:true});assert.deepEqual(await s.files.save({saveAs:true}),{cancelado:true});assert.equal(s.files.snapshot().documento.id,'one');assert(s.dirty);
  s.reply=async()=>{throw Error('Archivo modificado externamente');};await assert.rejects(s.files.save(),/externamente/);assert(s.dirty);assert.equal(s.saved,1);assert.equal(s.files.snapshot().documento.id,'one');assert.equal(s.files.snapshot().busy,false);
});
test('sin confirmación completa no se da por guardado',async()=>{
  for(const response of [{},{guardado:false},{guardado:true,documento:{}},{guardado:true,documento:{id:'one'}}]){
    const s=setup();s.reply=async()=>response;await assert.rejects(s.files.save());assert(s.dirty);assert.equal(s.saved,0);assert.equal(s.files.snapshot().documento,null);
  }
});
test('edición durante escritura queda pendiente y no se duplica la operación',async()=>{
  const s=setup();let finish;s.reply=()=>new Promise(resolve=>{finish=resolve;});const writing=s.files.save();assert(s.files.snapshot().busy);
  assert.equal(await s.files.save(),null);assert.equal(await s.files.open(),null);s.revision++;s.model.proyecto.nombre='Modificado';finish({guardado:true,documento:doc()});
  const result=await writing;assert(result.pendiente);assert(s.dirty);assert.equal(s.saved,0);assert.equal(s.calls[0].payload.modelo.proyecto.nombre,'Pasarela');
  assert.equal(s.files.snapshot().documento.id,'one');
});
test('cambiar de proyecto durante escritura no asocia el archivo anterior al nuevo',async()=>{
  const s=setup();let finish;s.reply=()=>new Promise(resolve=>{finish=resolve;});const writing=s.files.save();s.files.reset();s.revision++;finish({guardado:true,documento:doc()});
  assert((await writing).anterior);assert.equal(s.files.snapshot().documento,null);assert.equal(s.saved,0);assert(s.dirty);
});
test('abrir vincula archivo para sobrescribir, pero cancelación o error conservan el anterior',async()=>{
  const s=setup();await s.files.save();const original=s.model;
  s.reply=async()=>({cancelado:true});await s.files.open();assert.equal(s.model,original);assert.equal(s.files.snapshot().documento.id,'one');
  s.rejectOpen=true;s.reply=async()=>({modelo:{},documento:doc('two')});await assert.rejects(s.files.open(),/Inválido/);assert.equal(s.files.snapshot().documento.id,'one');assert.equal(s.model,original);
  s.rejectOpen=false;s.reply=async()=>({modelo:structuredClone(original),documento:doc('two')});await s.files.open();assert.equal(s.opened,1);assert.equal(s.files.snapshot().documento.id,'two');
  s.reply=async()=>({guardado:true,documento:doc('two')});await s.files.save();assert.equal(s.calls.at(-1).payload.documento_id,'two');
});
test('abrir no reemplaza una edición realizada mientras el selector estaba abierto',async()=>{
  const s=setup();let finish;s.reply=()=>new Promise(resolve=>{finish=resolve;});const reading=s.files.open();s.revision++;finish({modelo:{},documento:doc()});
  await assert.rejects(reading,/proyecto cambió/);assert.equal(s.opened,0);assert(s.dirty);assert.equal(s.files.snapshot().documento,null);
});
