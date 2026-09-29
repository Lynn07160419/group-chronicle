const $ = id => document.getElementById(id);
const days = ['周一','周二','周三','周四','周五','周六','周日'];
const normalize = s => s.normalize('NFKC').toLowerCase().replace(/[\s\p{Cf}]/gu, '');
let records = [], page = 1, ready = false, saving = false;
const pageSize = 12;
const entryEnabled = false;
$('exportExcel').onclick=async()=>{
  const button=$('exportExcel'), status=$('exportStatus');
  button.disabled=true;button.textContent='正在导出…';status.hidden=true;
  try {
    const response=await fetch('/api/export.xlsx');
    if(!response.ok)throw new Error('导出失败，请稍后重试。');
    const blob=await response.blob(), url=URL.createObjectURL(blob);
    const filename=response.headers.get('Content-Disposition')?.match(/filename\*=UTF-8''([^;]+)/)?.[1];
    const link=document.createElement('a');link.href=url;
    link.download=filename?decodeURIComponent(filename):'小团编年史.xlsx';
    document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
  } catch(error) {status.textContent='无法导出，请确认本地服务已启动后重试。';status.hidden=false;}
  finally {button.disabled=false;button.textContent='导出全部 Excel';}
};
function option(value, label=value) { const el=document.createElement('option'); el.value=value; el.textContent=label; return el; }
days.forEach(day => { $('dayFilter').append(option(day)); $('newDay').append(option(day)); });
const now=new Date(), academicYear=now.getMonth()>=8?now.getFullYear():now.getFullYear()-1;
for(let year=Math.max(2008,academicYear+5);year>=2008;year--) $('year').append(option(String(year),`${year} — ${year+1} 学年`));
$('year').value=String(academicYear);
$('term').value=now.getMonth()>=1&&now.getMonth()<8?'下':'上';
async function api(path, options) {
  const res=await fetch(path,options); let data;
  try { data=await res.json(); } catch { throw new Error('无法读取档案，请检查本地服务是否已启动。'); }
  if(!res.ok) { const error=new Error(data.error||'操作失败，请稍后重试。'); error.matches=data.matches; throw error; }
  return data;
}
function duplicateMatches(name) {
  const keys = name.split(/[/／]/).map(normalize).filter(Boolean);
  return records.filter(r=>r.name.split(/[/／]/).some(x=>keys.includes(normalize(x))));
}
function validateName() {
  if(!entryEnabled){$('save').disabled=true;$('nameStatus').textContent='录入暂未开放';return;}
  const name=$('newName').value.trim(), status=$('nameStatus'), found=duplicateMatches(name);
  status.replaceChildren(); status.className='nameStatus';
  const valid=Boolean(normalize(name)) && name.split(/[/／]/).every(x=>normalize(x));
  if(!name) status.textContent='输入团名后自动查重';
  else if(!ready) status.textContent='档案尚未加载，暂时无法查重';
  else if(!valid) {status.classList.add('bad');status.textContent='团名或别名不能为空';}
  else if(found.length) {
    status.classList.add('bad');status.textContent='这个团名已使用，不能重复录入';
    const detail=document.createElement('small');
    detail.textContent=[...new Set(found.map(r=>`${r.name} · ${r.semester} · ${r.weekday}`))].join('；');status.append(detail);
  } else { status.classList.add('good');status.textContent='暂未发现重名，可以录入'; }
  $('save').disabled=!ready||!valid||found.length>0||saving;
}
function render() {
  const q=normalize($('search').value), semester=$('semesterFilter').value, day=$('dayFilter').value;
  const filtered=records.filter(r=>(!q||normalize(r.name+' '+(r.leader||'')).includes(q))&&(!semester||r.semester===semester)&&(!day||r.weekday===day));
  const pages=Math.max(1,Math.ceil(filtered.length/pageSize));page=Math.min(page,pages);
  $('resultCount').textContent=`找到 ${filtered.length} 条记录`;
  $('results').replaceChildren();
  filtered.slice((page-1)*pageSize,page*pageSize).forEach(r=>{
    const tr=document.createElement('tr');
    [r.name,r.semester,r.weekday,r.leader||'待补充'].forEach((v,i)=>{const td=document.createElement('td');if(i===2){const badge=document.createElement('span');badge.className='day';badge.textContent=v;td.append(badge);}else td.textContent=v;tr.append(td);});
    $('results').append(tr);
  });
  $('empty').hidden=filtered.length!==0;
  $('pageInfo').textContent=`${page} / ${pages} 页`;
  $('prev').disabled=page===1;$('next').disabled=page===pages;
}
async function load() {
  const data=await api('/api/records');records=data.records;ready=true;
  const semesters=[...new Set(records.map(r=>r.semester))].sort().reverse();
  const selected=$('semesterFilter').value;$('semesterFilter').replaceChildren(option('','全部学期'));
  semesters.forEach(s=>$('semesterFilter').append(option(s)));$('semesterFilter').value=selected;
  $('recordCount').textContent=records.length;$('nameCount').textContent=new Set(records.map(r=>normalize(r.name))).size;
  $('range').textContent=`${semesters.at(-1)?.slice(0,2)?'20'+semesters.at(-1).slice(0,2):'—'} — ${semesters[0]?'20'+semesters[0].slice(3,5):'—'}`;
  $('connection').hidden=true;render();validateName();
}
function showConnection(error){$('connection').textContent=error.message+' 可刷新页面重试。';$('connection').hidden=false;}
['search','semesterFilter','dayFilter'].forEach(id=>$(id).addEventListener(id==='search'?'input':'change',()=>{page=1;render();}));
$('reset').onclick=()=>{['search','semesterFilter','dayFilter'].forEach(id=>$(id).value='');page=1;render();};
$('prev').onclick=()=>{page--;render();};$('next').onclick=()=>{page++;render();};
$('newName').oninput=()=>{$('saveStatus').textContent='';validateName();};
$('entryForm').onsubmit=async e=>{
  e.preventDefault();if(!entryEnabled||$('save').disabled)return;
  saving=true;validateName();$('saveStatus').textContent='正在查重并保存…';
  const year=Number($('year').value), semester=`${String(year%100).padStart(2,'0')}-${String((year+1)%100).padStart(2,'0')}${$('term').value}学期`;
  try {
    const result=await api('/api/records',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:$('newName').value.trim(),semester,weekday:$('newDay').value})});
    $('newName').value='';$('saveStatus').textContent=`「${result.record.name}」已保存 · ${semester} · ${result.record.weekday}`;
    $('search').value=result.record.name;$('semesterFilter').value='';$('dayFilter').value='';page=1;
    try {await load();} catch(error){showConnection(error);}
  } catch(error) {
    $('saveStatus').textContent=error.message;
    if(error.matches) {try {await load();}catch(loadError){showConnection(loadError);}}
  } finally {saving=false;validateName();}
};
load().catch(error=>{showConnection(error);$('resultCount').textContent='档案未能加载';});
if (document.modelContext?.registerTool) {
  try {
    Promise.resolve(document.modelContext.registerTool({
      name:'search_group_archive',title:'查询小团编年史',
      description:'按团名关键词、学期或星期查询本地小团档案，并在网页上展示结果。',
      inputSchema:{type:'object',properties:{name:{type:'string'},semester:{type:'string'},weekday:{type:'string'}},additionalProperties:false},
      annotations:{readOnlyHint:true,untrustedContentHint:true},
      async execute(input) {
        if(!input||typeof input!=='object'||Object.entries(input).some(([k,v])=>!['name','semester','weekday'].includes(k)||typeof v!=='string'))throw new Error('查询参数不正确');
        await load();
        if(input.semester&&!records.some(r=>r.semester===input.semester))throw new Error('档案中没有这个学期');
        if(input.weekday&&!days.includes(input.weekday))throw new Error('星期不正确');
        $('search').value=input.name||'';$('semesterFilter').value=input.semester||'';$('dayFilter').value=input.weekday||'';page=1;render();
        return records.filter(r=>(!input.name||normalize(r.name).includes(normalize(input.name)))&&(!input.semester||r.semester===input.semester)&&(!input.weekday||r.weekday===input.weekday));
      }
    })).catch(()=>{});
  } catch {}
}
