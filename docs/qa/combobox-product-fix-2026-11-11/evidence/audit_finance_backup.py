import hashlib,json
from pathlib import Path
import psycopg
from psycopg import sql
names={'backup':'gym_finance_backup_audit_20261111_test','current':'gym_finance_sandbox_v2'}
conns={k:psycopg.connect(host='127.0.0.1',user='postgres',dbname=v) for k,v in names.items()}
try:
 for conn in conns.values():conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
 def tables(conn):return {r[0] for r in conn.execute("select table_name from information_schema.tables where table_schema='public' and table_name like 'finance_%'")}
 def cols(conn,t):return {r[0] for r in conn.execute("select column_name from information_schema.columns where table_schema='public' and table_name=%s",(t,))}
 def rows(conn,t,columns):
  query=sql.SQL('select row_to_json(x)::text from (select {} from {} order by id) x').format(sql.SQL(',').join(map(sql.Identifier,sorted(columns))),sql.Identifier(t))
  return [json.loads(r[0]) for r in conn.execute(query)]
 def digest(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 sets={k:tables(c) for k,c in conns.items()}
 out={'method':'read-only repeatable-read transactions; all finance tables, all common columns, rows ordered by id; canonical JSON SHA256','revisions':{k:conn.execute('select version_num from alembic_version').fetchone()[0] for k,conn in conns.items()},'tables':{}}
 for t in sorted(sets['backup']|sets['current']):
  if t not in sets['backup'] or t not in sets['current']:
   out['tables'][t]={'only_in':'backup' if t in sets['backup'] else 'current'};continue
  cs={k:cols(c,t) for k,c in conns.items()};common=cs['backup']&cs['current']
  data={k:rows(c,t,common) for k,c in conns.items()}
  h={k:digest(x) for k,x in data.items()}
  byid={k:{r['id']:r for r in x} for k,x in data.items()}
  changed={i:[f for f in sorted(common) if byid['backup'][i][f]!=byid['current'][i][f]] for i in byid['backup'].keys()&byid['current'].keys() if byid['backup'][i]!=byid['current'][i]}
  out['tables'][t]={'rows':{k:len(x) for k,x in data.items()},'sha256':h,'common_content_equal':h['backup']==h['current'],'new_columns':sorted(cs['current']-cs['backup']),'removed_columns':sorted(cs['backup']-cs['current']),'added_rows':len(byid['current'].keys()-byid['backup'].keys()),'removed_rows':len(byid['backup'].keys()-byid['current'].keys()),'changed_existing_rows':changed}
 Path('/private/tmp/gym-combobox-fix-20261111/backup-content-audit.json').write_text(json.dumps(out,indent=2))
 print(json.dumps({'revisions':out['revisions'],'table_count':len(out['tables']),'differences':{t:r for t,r in out['tables'].items() if not r.get('common_content_equal',False)}},indent=2))
finally:
 for c in conns.values():c.rollback();c.close()
