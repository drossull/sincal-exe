"""Cell patches on explicitly selected DWGs; New Revision is unaffected."""
from pathlib import Path
import uuid
from sincal.cad.dwgprops import CadBatch, CadUnavailable, process_file


def edits(value, snapshot):
    if not isinstance(value,list) or not 1<=len(value)<=3000:
        raise ValueError('Selecciona entre 1 y 3000 celdas modificadas.')
    tables={t['id']:t for t in snapshot['tables']}
    seen=set(); properties={}; result=[]
    for item in value:
        if not isinstance(item,dict) or set(item)!={'table','row','column','value'}:
            raise ValueError('Cambio de celda no válido.')
        table,r,c,text=(item[k] for k in ('table','row','column','value'))
        if (not isinstance(table,str) or table not in tables or type(r) is not int or type(c) is not int
                or not 0<=r<len(tables[table]['cells']) or not 0<=c<len(tables[table]['cells'][r])
                or (table,r,c) in seen):
            raise ValueError('Celda inexistente o repetida.')
        seen.add((table,r,c));cell=tables[table]['cells'][r][c]
        if not cell['editable']:
            raise ValueError('FIELD protegido: esta celda no se puede editar.')
        if not isinstance(text,str) or len(text)>250 or any(ord(x)<32 for x in text) or any(x in text for x in ('%<','\\','{','}')):
            raise ValueError('Usa texto simple de hasta 250 caracteres.')
        key=cell.get('property')
        if key:
            key=key.casefold()
            if key in properties and properties[key]!=text:
                raise ValueError('Valores contradictorios para una misma propiedad DWG.')
            properties[key]=text
        result.append(dict(item))
    return result


def read(service,job,payload):
    if payload.get('folder'):
        folder=service.files.get(payload['folder'],'folder')
        paths=sorted(p for p in folder.iterdir() if p.is_file() and not p.is_symlink() and p.suffix.lower()=='.dwg')
    else:
        ids=payload.get('files')
        if not isinstance(ids,list) or any(not isinstance(k,str) for k in ids):
            raise ValueError('Selecciona archivos DWG o una carpeta.')
        paths=list(dict.fromkeys(service.files.get(k,'dwg') for k in ids))
    if not 1<=len(paths)<=500: raise ValueError('Selecciona entre 1 y 500 DWG.')
    if not service.cad_lock.acquire(blocking=False): raise ValueError('Hay otra operación CAD en curso.')
    batch=CadBatch(service.runtime/job.id,payload.get('engine'));batch.request_options={'revisionEditorRead':True}
    rows=[]; snapshots={}
    try:
        for index,path in enumerate(paths):
            if job.cancelled.is_set(): break
            key=uuid.uuid4().hex;job.update(f'Leyendo tablas VIÑETA · {path.name}',index*100/len(paths))
            try:
                result=process_file(path,service.runtime/job.id/key,worker=batch)
                editor=batch.result['revisionEditor']
                snapshots[key]={'path':path,'engine':payload.get('engine'),'editor':editor,**result}
                rows.append({'id':key,'name':path.name,'path':str(path),'editor':editor})
            except Exception as error:
                rows.append({'name':path.name,'error':str(error)})
                if isinstance(error,CadUnavailable):
                    rows.extend({'name':rest.name,'error':'No leído: el motor CAD dejó de responder.'} for rest in paths[index+1:])
                    break
        return {'snapshot':service.remember(service.revision_editor_snapshots,snapshots),'files':rows,'cancelled':job.cancelled.is_set()}
    finally:
        try: batch.close()
        finally: service.cad_lock.release()


def write(service,job,payload):
    if payload.get('confirm') is not True: raise ValueError('Confirma el guardado con respaldo.')
    with service.lock:
        snapshot=service.revision_editor_snapshots.get(payload.get('snapshot'))
        files=payload.get('files');selected=[];seen=set()
        if not snapshot or not isinstance(files,list) or not 1<=len(files)<=500: raise ValueError('Vuelve a leer los archivos.')
        for file in files:
            if not isinstance(file,dict) or not isinstance(file.get('id'),str) or file['id'] not in snapshot or file['id'] in seen:
                raise ValueError('Archivo inexistente o repetido.')
            seen.add(file['id']);item=dict(snapshot[file['id']])
            selected.append((file['id'],item,edits(file.get('changes'),item['editor'])))
    if not service.cad_lock.acquire(blocking=False): raise ValueError('Hay otra operación CAD en curso.')
    batch=CadBatch(service.runtime/job.id,selected[0][1].get('engine'));rows=[]
    try:
        for index,(key,item,changes) in enumerate(selected):
            if job.cancelled.is_set(): break
            path=Path(item['path']);job.update(f'Guardando tabla sin desplazar historial · {path.name}',index*100/len(selected))
            try:
                batch.request_options={'revisionEdits':changes}
                result=process_file(path,service.runtime/job.id/key,expected=item['fingerprint'],worker=batch,write=True)
                editor=batch.result['revisionEditor']
                with service.lock: snapshot[key]={**item,**result,'editor':editor}
                rows.append({'id':key,'name':path.name,'status':'Guardado','editor':editor,'backup':result['backup']})
            except Exception as error:
                rows.append({'id':key,'name':path.name,'status':'No modificado','error':str(error)})
                if isinstance(error,CadUnavailable):
                    rows.extend({'id':rest_key,'name':Path(rest['path']).name,'status':'No modificado',
                                 'error':'No procesado: el motor CAD dejó de responder.'}
                                for rest_key,rest,_ in selected[index+1:])
                    break
        return {'files':rows,'cancelled':job.cancelled.is_set()}
    finally:
        try: batch.close()
        finally: service.cad_lock.release()
