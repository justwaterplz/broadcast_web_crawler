"""Bounded feasibility checks; original application modules are not changed."""
import argparse,json,sys,re,time,hashlib
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports'/'platform-feasibility-20261014'
sys.path.insert(0,str(ROOT/'src'))
p=argparse.ArgumentParser();p.add_argument('stage',choices=['tving','tving-current','tvn-assets','tvn-inventory','requests']);args=p.parse_args()
def get(url):
    req=Request(url,headers={'User-Agent':'broadcast-metadata-probe/0.1'})
    with urlopen(req,timeout=30) as r:
        data=r.read(10000001)
        if len(data)>10000000:raise ValueError('response over 10 MB')
        return data.decode('utf-8'),r.status,r.url
def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
if args.stage=='tving':
    from broadcast_web_crawler.tving_batch import discover_programs
    from broadcast_web_crawler.tving import collect_program_with_report
    report={'input_url':'https://www.tving.com/more/genre/PCA','details':[]}
    try:
        listing=discover_programs(report['input_url'],limit=21,start_rank=1,max_pages=2)
        save('tving-listing.json',listing)
        report['listing']={k:v for k,v in listing.items() if k!='programs'}
        report['listing']['program_count']=len(listing['programs'])
        for i in [0,20]:
            entry=listing['programs'][i]
            try:
                cap=collect_program_with_report(entry['url'],OUT/('tving-'+str(entry['rank'])))
                report['details'].append({'rank':entry['rank'],'title':entry['title'],'status':'success','content_info_fields':list(cap['bundle']['contentInfo']),'episodes':cap['episode_list']['collected_count'],'total_count':cap['episode_list']['total_count'],'complete':cap['episode_list']['complete_for_current_api_listing']})
            except Exception as e:report['details'].append({'rank':entry['rank'],'title':entry['title'],'status':'error','error':str(e)})
            time.sleep(1)
    except Exception as e:report['error']=str(e)
    save('tving-verification.json',report);print(json.dumps(report,ensure_ascii=True,indent=2))
elif args.stage=='tvn-assets':
    urls=json.loads((OUT/'tvn-script-urls.json').read_text(encoding='utf8'))
    dest=OUT/'tvn-scripts';dest.mkdir(exist_ok=True)
    def task(part):
        url=urljoin('https://tvn.cjenm.com',part);name=part.rsplit('/',1)[-1]
        try:
            body,status,final=get(url);(dest/name).write_text(body,encoding='utf8');return {'file':name,'status':status,'bytes':len(body)}
        except Exception as e:return {'file':name,'error':str(e)}
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(task,urls))
    save('tvn-assets-results.json',rows);print(json.dumps(rows,ensure_ascii=True))
elif args.stage=='requests':
    manifest=json.loads((OUT/'request-manifest.json').read_text(encoding='utf8'));rows=[]
    for item in manifest:
        try:
            body,status,final=get(item['url']);(OUT/item['file']).write_text(body,encoding='utf8');row={**item,'status':status,'final_url':final,'bytes':len(body)}
        except Exception as e:row={**item,'error':str(e)}
        rows.append(row);time.sleep(1)
    save('request-results.json',rows);print(json.dumps(rows,ensure_ascii=True,indent=2))

elif args.stage=='tving-current':
    from urllib.parse import urlencode
    from broadcast_web_crawler.tving import parse_episodes,extract_public_client_key
    script=(OUT/'tving-app-current.js').read_text(encoding='utf8')
    module=script[script.index('46900:function'):script.index('46900:function')+1800]
    variable=re.search(r'q1:function\(\)\{return (\w+)\}',module).group(1)
    key=re.search(r'\b'+re.escape(variable)+r'="([^"]+)"',module).group(1)
    old=extract_public_client_key(script)
    report={'old_extractor_returned_url_prefix':old=='https://','current_export':'q1','current_variable':variable,'details':[]}
    for rank in [1,21]:
        bundle=json.loads((OUT/('tving-'+str(rank))/'metadata.json').read_text(encoding='utf8'))
        code=bundle['contentInfo']['program_code']
        params={'order':'new','cacheType':'main','pageSize':20,'adult':'all','free':'all','guest':'all','scope':'all','screenCode':'CSSD0100','networkCode':'CSND0900','osCode':'CSOD0900','teleCode':'CSCD0900','apiKey':key}
        try:
            text,status,final=get('https://api.tving.com/v2/media/frequency/program/'+code+'?'+urlencode(params))
            payload=json.loads(text);save('tving-current-episodes-'+str(rank)+'.json',payload)
            episodes=parse_episodes(payload,code)
            bundle['episodeApi']=payload;bundle['collection'].update(status='collected',complete_for_current_api_listing=episodes['complete_for_current_api_listing'],verification='current public q1 configuration')
            save('tving-current-metadata-'+str(rank)+'.json',bundle)
            report['details'].append({'rank':rank,'program_code':code,'title':bundle['contentInfo']['title'],'http_status':status,'api_status':episodes['api_status'],'episodes':episodes['collected_count'],'total_count':episodes['total_count'],'complete':episodes['complete_for_current_api_listing'],'nonempty_synopses':sum(bool(e.get('synopsis')) for e in episodes['episodes'])})
        except Exception as e:report['details'].append({'rank':rank,'error':type(e).__name__+': '+str(e).split('?')[0]})
        time.sleep(1)
    save('tving-current-verification.json',report);print(json.dumps(report,ensure_ascii=True,indent=2))
elif args.stage=='tvn-inventory':
    folder=OUT/'tvn-listing-pages';folder.mkdir(exist_ok=True)
    summary=[];programs=[];errors=[]
    for num in range(1,34):
        url='https://poc-cf-api.cjenm.com/apis/v1/tmplModul/14382?removeCacheYn=N&repGenreCdList=ALL&sortType=MC010207&pageNum='+str(num)+'&searchTlviseStatCd=ALL&searchChnCd=ALL'
        try:
            existing=OUT/('tvn-api-page'+str(num)+'.json')
            text=existing.read_text(encoding='utf8') if existing.exists() else get(url)[0]
            payload=json.loads(text);data=payload['result']['data']['dataInfo']
            if payload.get('resultCd')!='0000' or data['pageNum']!=num:raise ValueError('page mismatch or API error')
            (folder/(str(num)+'.json')).write_text(text,encoding='utf8')
            summary.append({key:data[key] for key in ['pageNum','total','pages','size','isLastPage']})
            programs.extend(data['list'])
        except Exception as e:errors.append({'page':num,'error':str(e)});break
        time.sleep(.5)
    ids=[p['pgmSeq'] for p in programs]
    report={'pages_read':len(summary),'reported_total':summary[0]['total'] if summary else None,'collected_rows':len(programs),'unique_program_ids':len(set(ids)),'duplicate_ids':len(ids)-len(set(ids)),'complete':not errors and len(summary)==33 and summary[-1]['isLastPage'] and len(set(ids))==summary[0]['total'],'with_detail_url':sum(bool(p.get('frontDetailUrlAddr')) for p in programs),'errors':errors,'pages':summary,'programs':programs}
    save('tvn-full-inventory.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ['pages','programs']},ensure_ascii=True,indent=2))
