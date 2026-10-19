import csv, json, hashlib, itertools, sys, platform
from pathlib import Path
import numpy as np
import sklearn
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score, adjusted_rand_score
BASE=Path(__file__).resolve().parent
SEED=20261019
rng=np.random.default_rng(SEED)
records=[]; latent=[]
# Three artificial profiles overlap; no actual electoral facts are represented.
profiles=[(.49,[.50,.30,.13,.07]),(.67,[.64,.20,.10,.06]),(.83,[.79,.10,.07,.04])]
for g,(mu,composition) in enumerate(profiles):
    for j in range(200):
        n=int(rng.integers(500,2501)); rate=float(np.clip(rng.normal(mu,.05),.22,.97)); b=int(round(n*rate))
        invalid=int(rng.binomial(b,.018)); valid=b-invalid
        outside=int(rng.binomial(b,float(np.clip(rng.normal(.075,.018),.01,.18))))
        probs=rng.dirichlet(np.array(composition)*180)
        votes=rng.multinomial(valid,probs)
        idx=g*200+j
        # Mixed groups in each fictional territory
        tik=f'T{(idx%12)+1:02d}'; uik=f'U{(idx+1):04d}'
        row=dict(election_id='SYNTHETIC_2026_TEST',territory_code=tik,precinct_code=uik,registered_voters=n,ballots_in_boxes=b,outside_ballots=outside,valid_ballots=valid,invalid_ballots=invalid, candidate_A=int(votes[0]),candidate_B=int(votes[1]),candidate_C=int(votes[2]),candidate_D=int(votes[3]))
        assert sum(votes)==valid and valid+invalid==b and outside<=b<=n
        records.append(row); latent.append(g)
# Ordering and file bytes are fixed by explicit UTF-8 + LF and column ordering
cols=list(records[0]); path=BASE/'Ляхович_синтетические_данные_2026.csv'
with path.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=cols,lineterminator='\n');w.writeheader();w.writerows(records)
labels_path=BASE/'Ляхович_эталонные_группы_ТОЛЬКО_для_проверки.csv'
with labels_path.open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f,lineterminator='\n');w.writerow(['territory_code','precinct_code','synthetic_group']);w.writerows((r['territory_code'],r['precinct_code'],g) for r,g in zip(records,latent))
n=np.array([r['registered_voters'] for r in records]); b=np.array([r['ballots_in_boxes'] for r in records]);v=np.array([r['valid_ballots'] for r in records]); out=np.array([r['outside_ballots'] for r in records]); inv=np.array([r['invalid_ballots'] for r in records]);
X=np.column_stack([100*b/n,100*out/b,100*inv/b,*[100*np.array([r[f'candidate_{c}'] for r in records])/v for c in 'BCD']])
feature_names=['T','H','I','B','C','D']
# 22 subsets containing turnout and at least one candidate; 5 values of k = 110 models.
subsets=[s for q in range(2,5) for s in itertools.combinations(range(6),q) if 0 in s and any(t in s for t in (3,4,5))]
assert len(subsets)==22,len(subsets)
models=[]
for comb in subsets:
    Z=StandardScaler().fit_transform(X[:,comb]);
    for k in range(2,7):
        y=KMeans(n_clusters=k,init='k-means++',n_init=20,random_state=SEED,algorithm='lloyd',max_iter=300,tol=1e-4).fit_predict(Z)
        counts=np.bincount(y,minlength=k)
        if min(counts)<max(5,int(np.ceil(.05*len(y)))):continue
        models.append(dict(features='+'.join(feature_names[t] for t in comb),indices=comb,k=k,sil=float(silhouette_score(Z,y)),ch=float(calinski_harabasz_score(Z,y)),db=float(davies_bouldin_score(Z,y)),smallest=int(min(counts)),external_ari=float(adjusted_rand_score(latent,y))))
# Percentile usefulness ranks (tie-average) with CH and Sil high, DB low.
def normalized_rank(values):
    vals=np.array(values);order=np.argsort(vals,kind='stable');ranks=np.empty(len(vals),float);i=0
    while i<len(vals):
        j=i+1
        while j<len(vals) and vals[order[j]]==vals[order[i]]:j+=1
        ranks[order[i:j]]=(i+j-1)/2
        i=j
    return (ranks/(len(vals)-1)) if len(vals)>1 else np.ones(len(vals))
a=normalized_rank([x['sil'] for x in models]);c=normalized_rank([x['ch'] for x in models]);d=normalized_rank([-x['db'] for x in models]);
for i,m in enumerate(models):m['score']=float(.45*a[i]+.30*c[i]+.25*d[i])
models.sort(key=lambda x:(-x['score'],len(x['indices']),x['k'],x['features']))
for m in models[:5]:
    ix=m['indices'];Z=StandardScaler().fit_transform(X[:,ix]);k=m['k'];orig=KMeans(n_clusters=k,n_init=20,random_state=SEED,algorithm='lloyd').fit_predict(Z)
    rr=np.random.default_rng(SEED+100+k+sum(ix));aris=[]
    by_tik={t:np.array([i for i,r in enumerate(records) if r['territory_code']==t]) for t in sorted({r['territory_code'] for r in records})}
    for rep in range(100):
        take=np.sort(np.concatenate([rr.choice(ids,size=int(np.floor(.8*len(ids))),replace=False) for ids in by_tik.values()]))
        zz=StandardScaler().fit_transform(X[take][:,ix]); yy=KMeans(n_clusters=k,n_init=20,random_state=SEED+rep,algorithm='lloyd').fit_predict(zz)
        aris.append(float(adjusted_rand_score(orig[take],yy)))
    m['ari_mean']=float(np.mean(aris));m['ari_p10']=float(np.percentile(aris,10));m['ari_sd']=float(np.std(aris));m['ari_p90']=float(np.percentile(aris,90))
# Negative control: unstructured Gaussian data, same search, does not establish false discovery rate
rn=np.random.default_rng(SEED+500);null=rn.normal(size=(600,6));best_null=None
for comb in subsets:
    Z=StandardScaler().fit_transform(null[:,comb])
    for k in range(2,7):
        y=KMeans(n_clusters=k,n_init=20,random_state=SEED,algorithm='lloyd').fit_predict(Z)
        if np.bincount(y).min()<30:continue
        s=float(silhouette_score(Z,y))
        if best_null is None or s>best_null['sil']:
            best_null=dict(features='+'.join(feature_names[i] for i in comb),k=k,sil=s)
report={'purpose':'Synthetic validation only; no real voting data', 'seed':SEED, 'rows':len(records),'territories':12,'latent_groups':3,'subset_count':len(subsets),'admissible_models':len(models),'pipeline':'StandardScaler, KMeans n_init=20, k=2..6, 5% min, rank weights .45/.30/.25, top-5 subsampling 100x at 80% stratified by territory','software':{'python':platform.python_version(),'numpy':np.__version__,'scikit_learn':sklearn.__version__},'files':{},'top5':[{k:v for k,v in m.items() if k!='indices'} for m in models[:5]],'null_control_best_silhouette':best_null,'limitations':['Synthetic latent groups are not empirical observations','External ARI uses hidden labels only after unsupervised ranking','No validation of web implementation or real-world applicability','Synthetic generator and evaluation are supplied for independent reproduction']}
for pp in [path,labels_path]:report['files'][pp.name]=hashlib.sha256(pp.read_bytes()).hexdigest()
manifest=BASE/'Ляхович_паспорт_эксперимента_2026.json';manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
