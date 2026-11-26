from components import *
x=json.loads((B/'first_trigger.json').read_text());m=x['market'];stage=m+'_'+x['asof'];model=train_model(stage,m,frames(m,x['asof']));p=predict(stage,m,frames(m));p.to_csv(B/('rd_candidate_'+stage+'.csv'));print('NATIVE_MODEL_RETRAINED',model['asof'],model['train_rows'],model['outer_mse'],flush=True)
