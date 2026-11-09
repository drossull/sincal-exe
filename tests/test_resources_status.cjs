const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
  const source=fs.readFileSync(path.join(__dirname,'../sincal/web/static/resources_status.js'),'utf8');
  const {createResourcePoller}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  const scheduled=[],notices=[];let busy=false,calls=0,offline=false;
  let status={available:true,source_commit:'revision-a',changed:1,removed:0};
  const poller=createResourcePoller({
    api:async route=>{assert.equal(route,'resources/status');calls++;if(offline)throw Error('offline');return status;},
    notify:text=>notices.push(text),isBusy:()=>busy,
    setTimer:(callback,delay)=>{assert.equal(delay,60000);scheduled.push(callback);return scheduled.length;},
    clearTimer:()=>{},
  });
  await poller.start();assert.equal(calls,1);assert.equal(notices.length,1);
  await scheduled.shift()();assert.equal(notices.length,1,'does not repeat a revision');
  offline=true;await scheduled.shift()();assert.equal(notices.length,1,'offline is silent');
  offline=false;busy=true;status={...status,source_commit:'revision-b'};
  await scheduled.shift()();assert.equal(notices.length,1,'does not overwrite an active job notice');
  busy=false;await scheduled.shift()();assert.equal(notices.length,2,'deferred notification is retained');
  status={...status,source_commit:'revision-c',changed:0};
  await scheduled.shift()();assert.equal(notices.length,2,'does not announce an installed revision');
  status={...status,removed:1};await scheduled.shift()();assert.equal(notices.length,3,'removals count as updates');
  poller.stop();const before=calls;await scheduled.shift()();assert.equal(calls,before);
  console.log('Resource polling: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
