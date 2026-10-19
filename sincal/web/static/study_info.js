// Documentary metadata is deliberately outside the CAD scene and drawing builder.
export function studyInformation(profile,node){
  const box=node('fieldset');box.className='study-information';
  box.append(node('legend','Empresa y estudio · solo consulta'));
  box.append(node('p','Información transcrita del informe. Este cuadro no se inserta en AutoCAD / ZWCAD.','muted'));
  const info=profile.study_info||{},list=node('dl');
  const labels={company:'Empresa',method:'Método',document:'Documento',date:'Fecha del informe',
    prepared_by:'Elaborado por',approved_by:'Aprobado por',address:'Dirección',email:'Correo',phone:'Teléfono',website:'Sitio web',source_page:'Página de origen'};
  for(const [key,label]of Object.entries(labels)){
    if(info[key])list.append(node('dt',label),node('dd',info[key]));
  }
  if(!info.company)box.append(node('p','Empresa no identificada automáticamente. Consulta el informe original.'));
  box.append(list);return box;
}
