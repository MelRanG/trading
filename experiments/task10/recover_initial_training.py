from common import *
import shutil
freeze(B/'training_recovery.json',{'stage':'Beforeinitialstrategyseal orreplay','KR_attempt1':'240fitrows<256Qlibbatch, drop_last yieldedzerooptimizerbatches andNaNloss. Not successfultraining.','repair':'Effectivebatch=min(256,largestpoweroftwo<=fitrows),128forKR. Samecode/features/seed/epochs/splits, notreturn-basedoptimization. Preservefailedcheckpoint/preds/logs.','prefix_validation_comparison':'Validatepredictionwhereouterlabelavailable; missingfuturelabeldoesnotmakeforecastunavailable. Separatelyrunprefix-onlyinference forcausality, nofuturetargetfilter.'})
for branch in ['models','predictions']:
 p=B/branch/'initial/KR';target=B/branch/'initial_attempt1/KR';target.parent.mkdir(exist_ok=True)
 if p.exists() and not target.exists():shutil.move(p,target)
