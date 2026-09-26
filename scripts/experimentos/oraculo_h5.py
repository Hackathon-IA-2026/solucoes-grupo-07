"""H5: quanto valeria uma previsão meteorológica? Clima verificado do dia-alvo como oráculo."""
import json, time
from datetime import date, datetime, timedelta
import numpy as np, polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier as HC, HistGradientBoostingRegressor as HR
from sklearn.metrics import average_precision_score as ap
from curtamap.config import settings
from curtamap.previsao.avaliacao import load_base, FIRST_DAY, wape
from curtamap.previsao.calendario import load_calendar
from curtamap.previsao.features import OCCURRENCE, VOLUME, attach_targets, build_features, release_map
from curtamap.previsao.modelo import PARAMS, TRAIN_DAYS
cal=load_calendar()
base=load_base(settings.data_dir, datetime(2026,9,1))
clima=pl.read_parquet('data/interim/clima_estado.parquet').with_columns(pl.col('slot').cast(pl.Int8))
cd=clima.group_by('fonte','id_estado','dia').agg(pl.col('clima').mean().alias('clima_dia'))
T=clima.rename({'clima':'clima_T'}).join(cd.rename({'clima_dia':'clima_dia_T'}),on=['fonte','id_estado','dia'])
Lc=cd.rename({'dia':'ultimo_dia','clima_dia':'clima_dia_L'})
def rows(days):
    f=attach_targets(build_features(base, release_map(days, cal)), base).filter(pl.col('y_corte').is_not_null())
    return f.join(T,on=['fonte','id_estado','dia','slot'],how='left').join(Lc,on=['fonte','id_estado','ultimo_dia'],how='left')
sets={'produto':OCCURRENCE,'+clima_L (legítimo)':OCCURRENCE+['clima_dia_L'],'+clima_T (oráculo)':OCCURRENCE+['clima_T','clima_dia_T']}
out=[]
for mo in [5,6,7,8]:
    m=date(2026,mo,1); nxt=date(2026,mo+1,1)
    last=release_map([m],cal)['ultimo_dia'].item()
    tr=rows(pl.date_range(last-timedelta(days=TRAIN_DAYS-1),last,eager=True).to_list())
    te=rows(pl.date_range(m,nxt-timedelta(days=1),eager=True).to_list())
    for fo in ['eolica','fotovoltaica']:
        a=tr.filter(pl.col('fonte')==fo); z=te.filter(pl.col('fonte')==fo)
        r={'fonte':fo,'mes':mo,'ap_historico':ap(z['y_corte'],z['hist_28d'].fill_null(0))}
        for name,cols in sets.items():
            X=lambda f: f.select(pl.col(cols).cast(pl.Float32)).to_numpy()
            h=HC(**PARAMS).fit(X(a),a['y_corte'].to_numpy())
            r['ap_'+name]=ap(z['y_corte'].to_numpy(),h.predict_proba(X(z))[:,1])
            vc=VOLUME+[c for c in cols if c not in OCCURRENCE]
            XV=lambda f: f.select(pl.col(vc).cast(pl.Float32)).to_numpy()
            hv=HR(loss='poisson',**PARAMS).fit(XV(a),a['y_volume'].to_numpy())
            p=hv.predict(XV(z)); zz=z.with_columns(pl.Series('p',p))
            d=zz.group_by('id_ons','dia').agg(pl.col('y_volume').sum(),pl.col('p').sum())
            r['wape_'+name]=wape(z['y_volume'].to_numpy(),p); r['wape_diario_'+name]=wape(d['y_volume'].to_numpy(),d['p'].to_numpy())
        out.append(r); print(json.dumps({k:(round(v,3) if isinstance(v,float) else v) for k,v in r.items()},ensure_ascii=False),flush=True)
t=pl.DataFrame(out)
with pl.Config(tbl_cols=-1,tbl_width_chars=250,float_precision=3): print(t.drop('mes').group_by('fonte').mean())
t.write_csv('data/interim/oraculo_h5.csv')
